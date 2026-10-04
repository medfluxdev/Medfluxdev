from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.auth.dependencies import current_actor
from app.auth.permissions import require
from app.core.scope_context import current_scope_context
from app.database.models.activity_log import ActivityLog
from app.database.scope_queries import intersect_ids, scoped_contract_ids
from app.database.session import create_session
from app.demo.workspace import workspace_contract_ids

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
def list_activity(
    request: Request,
    organization_slug: str,
    object_id: str | None = None,
    limit: int = 200,
):
    actor = current_actor(request, organization_slug)
    require(actor, "audit.view")

    object_uuid = None
    if object_id:
        try:
            object_uuid = UUID(object_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Ungültige Objekt-ID.")

    session = create_session()
    try:
        stmt = select(ActivityLog).where(
            ActivityLog.organization_id == actor.organization_id
        )
        if object_uuid is not None:
            stmt = stmt.where(ActivityLog.object_id == object_uuid)
        rows = session.scalars(
            stmt.order_by(ActivityLog.created_at.desc()).limit(min(max(limit, 1), 500))
        ).all()

        scope = current_scope_context()
        visible_contracts = intersect_ids(
            workspace_contract_ids(session),
            scoped_contract_ids(
                session,
                actor.organization_id,
                scope.hospital_id,
                scope.department_id,
            ),
        )
        if visible_contracts is not None:
            rows = [
                row
                for row in rows
                if row.object_type != "contract" or row.object_id in visible_contracts
            ]

        # Non-contract activity is also constrained by the persisted activity
        # scope when a hospital/department context is active. Global records with
        # no scope remain visible to organization-wide users only.
        if scope.department_id is not None:
            rows = [
                row
                for row in rows
                if row.object_type == "contract"
                or row.department_id == scope.department_id
            ]
        elif scope.hospital_id is not None:
            rows = [
                row
                for row in rows
                if row.object_type == "contract"
                or row.hospital_id == scope.hospital_id
            ]

        return {
            "items": [
                {
                    "id": str(row.id),
                    "account_id": str(row.account_id) if row.account_id else None,
                    "hospital_id": str(row.hospital_id) if row.hospital_id else None,
                    "department_id": str(row.department_id) if row.department_id else None,
                    "display_name": row.display_name_snapshot,
                    "role": row.role_snapshot,
                    "event_name": row.event_name,
                    "object_type": row.object_type,
                    "object_id": str(row.object_id) if row.object_id else None,
                    "context_data": row.context_data,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]
        }
    finally:
        session.close()
