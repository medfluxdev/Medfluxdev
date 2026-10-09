"""Stammdaten-API: Uebersicht, Verwendung in Vertraegen und CSV-Import.

Lesen duerfen alle Rollen (Struktur wie bei den Lese-Endpunkten nach Bereich
eingeschraenkt, Vertraege nach Sichtbarkeit). Importieren erfordert dieselbe
Berechtigung wie das Anlegen einzelner Eintraege.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import current_actor
from app.auth.permissions import is_admin, require
from app.core.scope_context import current_scope_context
from app.database.models import ActivityLog
from app.database.scope_queries import scoped_contract_ids
from app.database.session import create_session
from app.master_data import imports, service

router = APIRouter(prefix="/api/master-data", tags=["master-data"])

# Ereignisname und Objekttyp je importierbarer Datenart (wie bei den Einzel-Endpunkten).
_EVENTS = {
    "partner": ("partner", "contract_partner"),
    "department": ("department", "department"),
    "cost_center": ("cost_center", "cost_center"),
    "lookup": ("catalog.lookup", "lookup_value"),
}


class ImportRequest(BaseModel):
    rows: list[dict[str, Optional[str]]] = Field(max_length=imports.MAX_ROWS)
    dry_run: bool = True
    field_key: Optional[str] = Field(default=None, max_length=48)


def _visible(session, actor):
    scope = current_scope_context()
    return scoped_contract_ids(session, actor.organization_id, scope.hospital_id, scope.department_id)


@router.get("/summary")
def summary(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    scope = current_scope_context()
    session = create_session()
    try:
        restricted = not is_admin(actor)
        return service.summary(
            session,
            actor.organization_id,
            service.Scope(restricted, scope.hospital_id, scope.department_id),
            _visible(session, actor),
        )
    finally:
        session.close()


@router.get("/usage")
def usage(request: Request, organization_slug: str, kind: str = Query(max_length=32)):
    actor = current_actor(request, organization_slug)
    if kind not in service.KINDS:
        raise HTTPException(status_code=422, detail="Unbekannte Datenart.")
    session = create_session()
    try:
        return {
            "kind": kind,
            "counts": service.usage(session, actor.organization_id, kind, _visible(session, actor)),
            "tracked_lookup_fields": service.tracked_lookup_fields() if kind == "lookup" else None,
        }
    finally:
        session.close()


@router.post("/import/{kind}")
def import_master_data(kind: str, payload: ImportRequest, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    if kind not in imports.IMPORT_KINDS:
        raise HTTPException(status_code=404, detail="Diese Datenart kann nicht importiert werden.")
    require(actor, imports.PERMISSION_BY_KIND[kind], "Für diesen Import fehlt die Berechtigung.")
    prefix, object_type = _EVENTS[kind]
    scope = current_scope_context()
    session = create_session()

    def log(action: str, row: Any, context: dict) -> None:
        hospital_id = getattr(row, "hospital_id", None) if row is not None else None
        department_id = getattr(row, "department_id", None) if row is not None else None
        if kind == "department" and row is not None:
            department_id = row.id
        if row is not None:
            label = getattr(row, "short_name", None) or getattr(row, "label", None) or getattr(row, "name", None)
            context = {**context, "label": label, **({"code": row.code} if hasattr(row, "code") else {})}
        session.add(ActivityLog(
            organization_id=actor.organization_id,
            hospital_id=hospital_id or scope.hospital_id,
            department_id=department_id or scope.department_id,
            account_id=actor.account_id,
            display_name_snapshot=actor.display_name,
            role_snapshot="developer" if getattr(actor, "is_developer", False) else actor.role,
            event_name=f"{prefix}_{action}" if kind == "lookup" else f"{prefix}.{action}",
            object_type=object_type if row is not None else "organization",
            object_id=row.id if row is not None else actor.organization_id,
            context_data=context,
        ))

    try:
        return imports.import_rows(
            session, actor.organization_id, kind, payload.rows,
            dry_run=payload.dry_run, field_key=payload.field_key, log=log,
        )
    finally:
        session.close()
