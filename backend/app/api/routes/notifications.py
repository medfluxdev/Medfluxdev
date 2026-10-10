"""Scoped in-app notification feed derived from canonical operational truth.

Notifications are projections, not a second source of truth: open work items and
pending intelligence approvals remain authoritative in their own domains.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import ActionProposalRecord, WorkItem
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session
from app.work_queue.derive import task_items_only

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _work_statements(org_id: uuid.UUID, allowed: Optional[set[uuid.UUID]]):
    work_stmt = select(WorkItem).where(
        WorkItem.organization_id == org_id,
        WorkItem.active.is_(True),
        WorkItem.status != "resolved",
        task_items_only(WorkItem.item_type),
    )
    action_stmt = select(ActionProposalRecord).where(
        ActionProposalRecord.organization_id == org_id,
        ActionProposalRecord.status == "proposed",
        ActionProposalRecord.requires_human_approval.is_(True),
    )
    if allowed is not None:
        work_stmt = work_stmt.where(WorkItem.contract_id.in_(allowed))
        action_stmt = action_stmt.where(ActionProposalRecord.contract_id.in_(allowed))
    return work_stmt, action_stmt


def work_queue_count(session: Session, org_id: uuid.UUID, allowed: Optional[set[uuid.UUID]]) -> int:
    """Offener Arbeitsvorrat (Aufgaben + Freigaben) – dieselbe Abfrage wie die Liste."""
    work_stmt, action_stmt = _work_statements(org_id, allowed)
    return (
        (session.scalar(select(func.count()).select_from(work_stmt.subquery())) or 0)
        + (session.scalar(select(func.count()).select_from(action_stmt.subquery())) or 0)
    )


@router.get("")
def notification_feed(
    request: Request,
    organization_slug: str,
    limit: int = Query(default=100, ge=1, le=500),
):
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        actor = getattr(request.state, "actor", None)
        if org is None or (actor is None and settings.auth_enabled) or (actor is not None and actor.organization_id != org.id):
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        scope = current_scope_context()
        allowed = scoped_contract_ids(session, org.id, scope.hospital_id, scope.department_id)

        work_stmt, action_stmt = _work_statements(org.id, allowed)

        work_items = session.scalars(work_stmt.order_by(WorkItem.last_seen_at.desc()).limit(limit)).all()
        actions = session.scalars(action_stmt.limit(limit)).all()
        items = [
            {
                "id": f"work:{row.id}",
                "kind": "work_item",
                "severity": row.severity,
                "title": row.title_de,
                "message": row.why_de,
                "contract_id": str(row.contract_id),
                "target_date": row.target_date,
                "href": f"/contracts/{row.contract_id}?tab=deadlines" if row.contract_id else "/fristen?ansicht=aufgaben",
            }
            for row in work_items
        ]
        items.extend(
            {
                "id": f"action:{row.id}",
                "kind": "approval_required",
                "severity": "high",
                "title": "Freigabe erforderlich",
                "message": row.reason,
                "contract_id": str(row.contract_id) if row.contract_id else None,
                "target_date": None,
                "href": f"/contracts/{row.contract_id}" if row.contract_id else "/admin",
            }
            for row in actions
        )
        return {"items": items[:limit], "total": work_queue_count(session, org.id, allowed)}
    finally:
        session.close()
