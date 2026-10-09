"""H6.2 Historie: organisationsweites Protokoll mit Filtern/Export und Vertragshistorie."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select

from app.auth.dependencies import current_actor
from app.auth.permissions import is_admin, require
from app.core.scope_context import current_scope_context
from app.database.models import Contract
from app.database.models.activity_log import ActivityLog
from app.database.scope_queries import intersect_ids, scoped_contract_ids
from app.database.session import create_session
from app.demo.workspace import workspace_contract_ids
from app.history.service import (
    CATEGORIES,
    HistoryFilter,
    contract_history,
    history_actors,
    history_csv,
    organization_history,
)

router = APIRouter(tags=["history"])

EXPORT_LIMIT = 10000
# Stammdaten, deren Einzelhistorie abgefragt werden kann.
MASTER_DATA_OBJECT_TYPES = frozenset({
    "contract_partner", "hospital", "department", "cost_center",
    "catalog_contract_type", "catalog_contract_category", "lookup_value", "contract_rule",
})


def _filters(
    account_id: Optional[UUID], category: Optional[str], contract_id: Optional[UUID],
    date_from: Optional[date], date_to: Optional[date],
    object_type: Optional[str] = None, object_id: Optional[UUID] = None,
) -> HistoryFilter:
    if category and category not in CATEGORIES:
        raise HTTPException(status_code=422, detail="Unbekannter Bereich.")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Der Zeitraum ist ungültig.")
    if (object_type is None) != (object_id is None):
        raise HTTPException(status_code=422, detail="Objektart und Objekt gehören zusammen.")
    if object_type is not None and object_type not in MASTER_DATA_OBJECT_TYPES:
        raise HTTPException(status_code=422, detail="Unbekannte Objektart.")
    return HistoryFilter(
        account_id=account_id, category=category or None, contract_id=contract_id, date_from=date_from, date_to=date_to,
        object_type=object_type, object_id=object_id,
    )


def _query(session, actor, filters: HistoryFilter, limit: int, offset: int) -> dict:
    scope = current_scope_context()
    visible = intersect_ids(
        workspace_contract_ids(session),
        scoped_contract_ids(session, actor.organization_id, scope.hospital_id, scope.department_id),
    )
    return organization_history(
        session, actor.organization_id, filters, visible=visible,
        hospital_id=scope.hospital_id, department_id=scope.department_id, limit=limit, offset=offset,
    )


@router.get("/api/history")
def list_history(
    request: Request,
    organization_slug: str,
    account_id: Optional[UUID] = None,
    category: Optional[str] = None,
    contract_id: Optional[UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    object_type: Optional[str] = None,
    object_id: Optional[UUID] = None,
    limit: int = 100,
    offset: int = 0,
):
    actor = current_actor(request, organization_slug)
    require(actor, "audit.view")
    filters = _filters(account_id, category, contract_id, date_from, date_to, object_type, object_id)
    session = create_session()
    try:
        result = _query(session, actor, filters, min(max(limit, 1), 500), offset)
        return {
            **result,
            "actors": history_actors(session, actor.organization_id),
            "categories": [{"key": key, "label": label} for key, label in CATEGORIES.items()],
        }
    finally:
        session.close()


@router.get("/api/history/export")
def export_history(
    request: Request,
    organization_slug: str,
    account_id: Optional[UUID] = None,
    category: Optional[str] = None,
    contract_id: Optional[UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    actor = current_actor(request, organization_slug)
    require(actor, "audit.view")
    require(actor, "export")
    filters = _filters(account_id, category, contract_id, date_from, date_to)
    session = create_session()
    try:
        result = _query(session, actor, filters, EXPORT_LIMIT, 0)
        scope = current_scope_context()
        session.add(ActivityLog(
            organization_id=actor.organization_id,
            hospital_id=scope.hospital_id,
            department_id=scope.department_id,
            account_id=actor.account_id,
            display_name_snapshot=actor.display_name,
            role_snapshot="developer" if actor.is_developer else actor.role,
            event_name="history.exported",
            object_type="organization",
            object_id=actor.organization_id,
            context_data={
                "row_count": len(result["items"]),
                "filters": {key: str(value) for key, value in vars(filters).items() if value is not None},
            },
        ))
        session.commit()
        return Response(
            content=history_csv(result["items"]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="medflux-historie-{date.today().isoformat()}.csv"'},
        )
    finally:
        session.close()


@router.get("/api/contracts/{contract_id}/history")
def get_contract_history(contract_id: UUID, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    require(actor, "audit.view")
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
        return {"items": contract_history(session, contract)}
    finally:
        session.close()
