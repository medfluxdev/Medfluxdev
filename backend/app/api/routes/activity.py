from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.auth.service import require_role
from app.database.models.activity_log import ActivityLog
from app.database.session import create_session

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("")
def list_activity(request: Request, organization_slug: str, object_id: str | None = None, limit: int = 200):
    actor = getattr(request.state, "actor", None)
    if actor is None:
        raise HTTPException(status_code=401, detail="Bitte anmelden.")
    try:
        require_role(actor, "admin", "contract_manager")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    object_uuid = None
    if object_id:
        try:
            object_uuid = UUID(object_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Ungültige Objekt-ID.")

    session = create_session()
    try:
        stmt = select(ActivityLog).where(ActivityLog.organization_id == actor.organization_id)
        if object_uuid is not None:
            stmt = stmt.where(ActivityLog.object_id == object_uuid)
        rows = session.scalars(stmt.order_by(ActivityLog.created_at.desc()).limit(min(max(limit, 1), 500))).all()
        return {
            "items": [
                {
                    "id": str(row.id),
                    "account_id": str(row.account_id) if row.account_id else None,
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
