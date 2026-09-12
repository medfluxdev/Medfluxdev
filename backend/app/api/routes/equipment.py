"""Geräte-Routen (PR-4) – GET /api/equipment, GET /api/equipment/{id}.

Dünne READ-Schicht -> `app.equipment`. Org-gebunden via `organization_slug`.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.database.services import get_organization
from app.database.session import create_session
from app.equipment.models import EquipmentDetail, EquipmentSummary
from app.equipment.service import get_equipment_detail, list_equipment

router = APIRouter(prefix="/api/equipment", tags=["equipment"])


@router.get("", response_model=list[EquipmentSummary])
def equipment_list(
    organization_slug: str,
    q: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[EquipmentSummary]:
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        return list_equipment(session, organization_id=org.id, search=q, limit=limit)
    finally:
        session.close()


@router.get("/{equipment_id}", response_model=EquipmentDetail)
def equipment_detail(organization_slug: str, equipment_id: UUID) -> EquipmentDetail:
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        detail = get_equipment_detail(
            session, organization_id=org.id, equipment_id=equipment_id
        )
        if detail is None:
            raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
        return detail
    finally:
        session.close()
