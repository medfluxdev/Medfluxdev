"""Arbeitslisten-Routen (PR-4) – GET /api/work-queue, PATCH /api/work-queue/{id}.

Dünne READ/UPDATE-Schicht -> `app.work_queue`. Org-gebunden via
`organization_slug`; Status-Transitionen sind der menschliche Lebenszyklus.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.database.services import PersistenceError, get_organization
from app.database.session import create_session
from app.work_queue.models import WorkItemList, WorkItemStatusUpdate, WorkItemSummary
from app.work_queue.service import (
    WORK_ITEM_STATUS_ALLOWED,
    get_work_item_dto,
    list_work_items_dto,
    set_work_item_status,
)

router = APIRouter(prefix="/api/work-queue", tags=["work-queue"])

SEVERITY_ALLOWED = {"critical", "high", "medium", "low", "info"}
WORKITEM_TYPE_ALLOWED = {
    "cancellation_deadline", "contract_expiry", "contract_expired",
    "automatic_renewal", "manual_review", "missing_cost",
    "equipment_coverage_review", "equipment_relationship_ambiguous", "sla_issue",
}


@router.get("", response_model=WorkItemList)
def work_queue_list(
    organization_slug: str,
    active: bool = Query(default=True),
    status: list[str] = Query(default=[]),
    severity: list[str] = Query(default=[]),
    item_type: list[str] = Query(default=[]),
    limit: int = Query(default=200, ge=1, le=1000),
) -> WorkItemList:
    for v in status:
        if v not in WORK_ITEM_STATUS_ALLOWED:
            raise HTTPException(status_code=422, detail=f"Ungueltiger status: {v!r}")
    for v in severity:
        if v not in SEVERITY_ALLOWED:
            raise HTTPException(status_code=422, detail=f"Ungueltige severity: {v!r}")
    for v in item_type:
        if v not in WORKITEM_TYPE_ALLOWED:
            raise HTTPException(status_code=422, detail=f"Ungueltiger item_type: {v!r}")

    items = []
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        scope = dict(
            session=session,
            organization_id=org.id,
            active_only=active,
            statuses=status or None,
            severities=severity or None,
            item_types=item_type or None,
            limit=limit,
        )
        raw = list_work_items_dto(**scope)
        return WorkItemList(items=[WorkItemSummary(**r) for r in raw], total=len(raw))
    finally:
        session.close()


@router.patch("/{work_item_id}", response_model=WorkItemSummary)
def work_item_status_update(
    organization_slug: str, work_item_id: UUID, body: WorkItemStatusUpdate
) -> WorkItemSummary:
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        try:
            _ = set_work_item_status(
                session, organization_id=org.id, work_item_id=work_item_id,
                status=body.status,
            )
            dto = get_work_item_dto(
                session, organization_id=org.id, work_item_id=work_item_id
            )
            if dto is None:
                raise HTTPException(status_code=404, detail="Arbeitselement nicht gefunden.")
            response = WorkItemSummary(**dto)
            session.commit()
        except PersistenceError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(exc))
        except SQLAlchemyError as exc:
            # Persistenz-/Commit-Fehler (z. B. transienter DB-Konflikt) ehrlich
            # zurueckgeben statt eines nackten 500 – der Client kann den Grund
            # anzeigen und erneut versuchen.
            session.rollback()
            raise HTTPException(
                status_code=503,
                detail="Datenbankkonflikt beim Aktualisieren – bitte erneut versuchen.",
            ) from exc
        except ValidationError as exc:
            session.rollback()
            raise HTTPException(
                status_code=500,
                detail="Arbeitselement konnte nicht serialisiert werden – bitte prüfen.",
            ) from exc
        return response
    finally:
        session.close()
