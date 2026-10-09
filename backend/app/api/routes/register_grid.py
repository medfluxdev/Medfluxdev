"""H7 Vertragsregister: Raster, gespeicherte Ansichten, Baum, Excel-Export,
Portfolio-Bericht und Deckblatt-PDF."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.ai.service import AIService
from app.auth.dependencies import current_actor
from app.auth.permissions import can, is_admin, require
from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import Contract
from app.database.models.activity_log import ActivityLog
from app.database.models.organization import Organization
from app.database.scope_queries import intersect_ids, scoped_contract_ids
from app.database.session import create_session
from app.demo.workspace import workspace_contract_ids
from app.reports.exports import cover_html, grid_xlsx, html_to_pdf, portfolio, portfolio_xlsx
from app.reports.grid import (
    COLUMN_BY_KEY,
    GridError,
    GridSpec,
    apply_filters,
    build_rows,
    cached_rows,
    columns_payload,
    display,
    distinct_values,
    groups,
    row_payload,
    sort_rows,
    totals,
    tree,
    visible_rows,
)
from app.reports.renewal import decision_summary, renewal_brief, upcoming_renewals, urgency
from app.reports.renewal_ai import summarize_brief
from app.reports.views import ViewError, create_view, delete_view, list_views, update_view, view_payload
from app.search.content import ensure_index, index_status, search_contents

router = APIRouter(tags=["register-grid"])
_ai_service = AIService(settings)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ViewBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    config: dict[str, Any] = Field(default_factory=dict)
    is_global: bool = False
    view_kind: str = "register"


def _spec(raw: Optional[str]) -> GridSpec:
    try:
        return GridSpec.parse(json.loads(raw) if raw else None)
    except (ValueError, GridError) as exc:
        raise HTTPException(status_code=422, detail=str(exc) if isinstance(exc, GridError) else "Ungültige Ansicht.")


def _visible(session, actor):
    scope = current_scope_context()
    return intersect_ids(
        workspace_contract_ids(session),
        scoped_contract_ids(session, actor.organization_id, scope.hospital_id, scope.department_id),
    )


def _rows(session, actor, spec: GridSpec, as_of: date, *, years: Optional[range] = None):
    rows = visible_rows(cached_rows(session, actor.organization_id, as_of, years=years, archived=spec.archived), _visible(session, actor))
    try:
        return rows, apply_filters(rows, spec, as_of, actor.account_id)
    except GridError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _log(session, actor, event_name: str, context: dict) -> None:
    scope = current_scope_context()
    session.add(ActivityLog(
        organization_id=actor.organization_id, hospital_id=scope.hospital_id, department_id=scope.department_id,
        account_id=actor.account_id, display_name_snapshot=actor.display_name,
        role_snapshot="developer" if actor.is_developer else actor.role, event_name=event_name,
        object_type="organization", object_id=actor.organization_id, context_data=context,
    ))


def _attachment(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content, media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/api/register/columns")
def get_columns(request: Request, organization_slug: str):
    current_actor(request, organization_slug)
    return {"columns": columns_payload()}


@router.get("/api/register/grid")
def get_grid(
    request: Request, organization_slug: str, spec: Optional[str] = None, offset: int = 0, limit: int = 100,
    include_tree: bool = False,
):
    actor = current_actor(request, organization_slug)
    parsed = _spec(spec)
    as_of = date.today()
    session = create_session()
    try:
        all_rows, rows = _rows(session, actor, parsed, as_of)
        ordered = sort_rows(rows, parsed)
        limit = min(max(limit, 1), 500)
        tree_payload = None
        if include_tree:
            tree_spec = GridSpec(**{**parsed.__dict__, "filters": [
                item for item in parsed.filters if item["column"] not in ("hospital", "department")
            ]})
            try:
                tree_payload = tree(apply_filters(all_rows, tree_spec, as_of, actor.account_id))
            except GridError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
        page = ordered[max(offset, 0):max(offset, 0) + limit]
        return {
            "as_of": as_of.isoformat(),
            "spec": parsed.as_dict(),
            "total": len(ordered),
            "totals": totals(ordered),
            "groups": groups(ordered, parsed),
            "items": [{**row_payload(row, parsed.columns), "group": [display(COLUMN_BY_KEY[key], row.values[key]) for key in parsed.group_by]} for row in page],
            **({"tree": tree_payload} if include_tree else {}),
        }
    finally:
        session.close()


@router.get("/api/register/grid/values")
def get_values(request: Request, organization_slug: str, column: str, spec: Optional[str] = None):
    actor = current_actor(request, organization_slug)
    parsed = _spec(spec)
    if column not in COLUMN_BY_KEY:
        raise HTTPException(status_code=422, detail="Unbekannte Spalte.")
    parsed.filters = [item for item in parsed.filters if item["column"] != column]
    session = create_session()
    try:
        _, rows = _rows(session, actor, parsed, date.today())
        return {"column": column, "values": distinct_values(rows, column)[:500]}
    finally:
        session.close()


@router.get("/api/register/grid/tree")
def get_tree(request: Request, organization_slug: str, spec: Optional[str] = None):
    actor = current_actor(request, organization_slug)
    parsed = _spec(spec)
    parsed.filters = [item for item in parsed.filters if item["column"] not in ("hospital", "department")]
    session = create_session()
    try:
        _, rows = _rows(session, actor, parsed, date.today())
        return {"total": len(rows), "hospitals": tree(rows)}
    finally:
        session.close()


@router.get("/api/register/grid/export.xlsx")
def export_grid(request: Request, organization_slug: str, spec: Optional[str] = None, title: Optional[str] = None):
    actor = current_actor(request, organization_slug)
    require(actor, "export")
    parsed = _spec(spec)
    as_of = date.today()
    session = create_session()
    try:
        _, rows = _rows(session, actor, parsed, as_of)
        ordered = sort_rows(rows, parsed)
        name = (title or "Vertragsregister").strip()[:80] or "Vertragsregister"
        content = grid_xlsx(ordered, parsed, title=name, as_of=as_of)
        _log(session, actor, "register.exported", {"row_count": len(ordered), "format": "xlsx", "view": name, "spec": parsed.as_dict()})
        session.commit()
        return _attachment(content, XLSX, f"medflux-vertragsregister-{as_of.isoformat()}.xlsx")
    finally:
        session.close()


def _report_years(as_of: date) -> range:
    return range(as_of.year - 2, as_of.year + 4)


@router.get("/api/register/reports/portfolio")
def get_portfolio(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    as_of = date.today()
    session = create_session()
    try:
        rows, _ = _rows(session, actor, GridSpec(), as_of, years=_report_years(as_of))
        return portfolio(rows, as_of, _report_years(as_of))
    finally:
        session.close()


@router.get("/api/register/reports/portfolio.xlsx")
def export_portfolio(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    require(actor, "export")
    as_of = date.today()
    session = create_session()
    try:
        rows, _ = _rows(session, actor, GridSpec(), as_of, years=_report_years(as_of))
        content = portfolio_xlsx(portfolio(rows, as_of, _report_years(as_of)))
        _log(session, actor, "register.report_exported", {"report": "portfolio", "format": "xlsx"})
        session.commit()
        return _attachment(content, XLSX, f"medflux-portfoliobericht-{as_of.isoformat()}.xlsx")
    finally:
        session.close()


@router.get("/api/contracts/{contract_id}/cover.pdf")
def get_cover(contract_id: UUID, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    as_of = date.today()
    session = create_session()
    try:
        contract = session.scalars(
            select(Contract).where(Contract.id == contract_id, Contract.organization_id == actor.organization_id)
        ).first()
        if contract is not None and not is_admin(actor):
            scope = current_scope_context()
            allowed = scoped_contract_ids(session, actor.organization_id, scope.hospital_id, scope.department_id)
            if allowed is not None and contract.id not in allowed:
                contract = None
        if contract is None:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        rows = build_rows(session, actor.organization_id, {contract.id}, as_of)
        if not rows:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        organization = session.get(Organization, actor.organization_id)
        content = html_to_pdf(cover_html(session, contract, rows[0], as_of, organization.name if organization else ""))
        number = contract.register_number or str(contract.id)[:8]
        return Response(
            content=content, media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(f'deckblatt-{number}.pdf')}"},
        )
    finally:
        session.close()


# --------------------------------------------------------------------------- saved views

def _view_http(exc: ViewError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail_de)


@router.get("/api/register/views")
def get_views(request: Request, organization_slug: str, kind: str = "register"):
    actor = current_actor(request, organization_slug)
    if kind not in ("register", "contracts"):
        raise HTTPException(status_code=422, detail="Unbekannte Ansichtsart.")
    session = create_session()
    try:
        items = list_views(session, actor.organization_id, actor.account_id, kind)
        session.commit()
        return {"items": items, "can_manage_global": can(actor, "views.global")}
    finally:
        session.close()


@router.post("/api/register/views")
def post_view(payload: ViewBody, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    if payload.is_global:
        require(actor, "views.global", "Globale Ansichten dürfen nur Administratoren speichern.")
    session = create_session()
    try:
        try:
            row = create_view(
                session, organization_id=actor.organization_id, account_id=actor.account_id,
                display_name=actor.display_name, name=payload.name, config=payload.config, is_global=payload.is_global,
                kind=payload.view_kind,
            )
        except ViewError as exc:
            session.rollback()
            raise _view_http(exc)
        session.commit()
        return view_payload(row, actor.account_id)
    finally:
        session.close()


@router.put("/api/register/views/{view_id}")
def put_view(view_id: UUID, payload: ViewBody, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        try:
            row = update_view(
                session, organization_id=actor.organization_id, account_id=actor.account_id,
                may_edit_global=can(actor, "views.global"), view_id=view_id, name=payload.name, config=payload.config,
            )
        except ViewError as exc:
            session.rollback()
            raise _view_http(exc)
        session.commit()
        return view_payload(row, actor.account_id)
    finally:
        session.close()


@router.delete("/api/register/views/{view_id}")
def remove_view(view_id: UUID, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        try:
            delete_view(
                session, organization_id=actor.organization_id, account_id=actor.account_id,
                may_edit_global=can(actor, "views.global"), view_id=view_id,
            )
        except ViewError as exc:
            session.rollback()
            raise _view_http(exc)
        session.commit()
        return {"deleted": True}
    finally:
        session.close()


# --------------------------------------------------------------------------- renewal briefs (13a)

@router.get("/api/register/renewals")
def get_renewals(request: Request, organization_slug: str, days: int = 120):
    actor = current_actor(request, organization_slug)
    as_of = date.today()
    session = create_session()
    try:
        rows, _ = _rows(session, actor, GridSpec(), as_of)
        upcoming = upcoming_renewals(rows, as_of, min(max(days, 1), 730))
        decisions = decision_summary(session, [row.contract_id for row in upcoming])
        return {
            "as_of": as_of.isoformat(),
            "days": days,
            "items": [
                {
                    "contract_id": str(row.contract_id),
                    "register_number": row.values["register_number"],
                    "short_description": row.values["short_description"],
                    "partner": row.values["partner"],
                    "cancel_by": row.values["cancel_by"].isoformat(),
                    "days_left": (row.values["cancel_by"] - as_of).days,
                    "urgency": urgency(row.values["cancel_by"], as_of),
                    "possible_end": row.values["possible_end"].isoformat() if row.values["possible_end"] else None,
                    "annual_cost": str(row.values["annual_cost"]) if row.values["annual_cost"] is not None else None,
                    "responsible": row.values["responsible"],
                    "decision": decisions.get(row.contract_id),
                }
                for row in upcoming
            ],
        }
    finally:
        session.close()


@router.get("/api/contracts/{contract_id}/renewal-brief")
def get_renewal_brief(contract_id: UUID, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        contract = session.scalars(
            select(Contract).where(Contract.id == contract_id, Contract.organization_id == actor.organization_id)
        ).first()
        visible = _visible(session, actor)
        if contract is not None and not is_admin(actor) and visible is not None and contract.id not in visible:
            contract = None
        if contract is None:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        return renewal_brief(session, contract, date.today(), visible)
    finally:
        session.close()


# --------------------------------------------------------------------------- content search (§4A)

@router.get("/api/register/content-search")
def content_search(request: Request, organization_slug: str, q: str = ""):
    actor = current_actor(request, organization_slug)
    if len(q) > 200:
        raise HTTPException(status_code=422, detail="Suchbegriff zu lang (max. 200 Zeichen).")
    session = create_session()
    try:
        ensure_index(session, actor.organization_id)
        session.commit()
        return search_contents(session, actor.organization_id, q, _visible(session, actor))
    finally:
        session.close()


@router.get("/api/register/content-search/status")
def content_search_status(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        return index_status(session, actor.organization_id)
    finally:
        session.close()


def _brief_for(request: Request, organization_slug: str, contract_id: UUID) -> dict:
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        contract = session.scalars(
            select(Contract).where(Contract.id == contract_id, Contract.organization_id == actor.organization_id)
        ).first()
        visible = _visible(session, actor)
        if contract is not None and not is_admin(actor) and visible is not None and contract.id not in visible:
            contract = None
        if contract is None:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        return renewal_brief(session, contract, date.today(), visible)
    finally:
        session.close()


@router.get("/api/contracts/{contract_id}/renewal-brief/summary")
async def get_renewal_summary(contract_id: UUID, request: Request, organization_slug: str):
    brief = await run_in_threadpool(_brief_for, request, organization_slug, contract_id)
    return await summarize_brief(_ai_service, brief)
