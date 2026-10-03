"""Geräte-Routen (PR-4) – GET /api/equipment, GET /api/equipment/{id}.

Dünne READ-Schicht -> `app.equipment`. Org-gebunden via `organization_slug`.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import Equipment
from app.database.services import get_organization
from app.database.session import create_session
from app.equipment.models import EquipmentDetail, EquipmentSummary
from app.equipment.service import get_equipment_detail, list_equipment

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


@router.get("", response_model=list[EquipmentSummary])
def equipment_list(
    request: Request,
    organization_slug: str,
    q: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[EquipmentSummary]:
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        actor = getattr(request.state, "actor", None)
        if org is None or (actor is None and settings.auth_enabled) or (actor is not None and actor.organization_id != org.id):
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        scope = current_scope_context()
        return list_equipment(
            session,
            organization_id=org.id,
            search=q,
            limit=limit,
            hospital_id=scope.hospital_id,
            department_id=scope.department_id,
        )
    finally:
        session.close()


@router.get("/{equipment_id}", response_model=EquipmentDetail)
def equipment_detail(request: Request, organization_slug: str, equipment_id: UUID) -> EquipmentDetail:
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        actor = getattr(request.state, "actor", None)
        if org is None or (actor is None and settings.auth_enabled) or (actor is not None and actor.organization_id != org.id):
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        scope = current_scope_context()
        if scope.hospital_id is not None or scope.department_id is not None:
            row = session.get(Equipment, equipment_id)
            if row is None or row.organization_id != org.id:
                raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
            if (
                scope.department_id is not None
                and row.department_id != scope.department_id
            ):
                raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
            if (
                scope.department_id is None
                and scope.hospital_id is not None
                and row.hospital_id != scope.hospital_id
            ):
                raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
        detail = get_equipment_detail(
            session, organization_id=org.id, equipment_id=equipment_id
        )
        if detail is None:
            raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
        return detail
    finally:
        session.close()
