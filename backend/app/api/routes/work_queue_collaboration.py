"""Human collaboration API layered on top of canonical Work Queue items."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import Account, AccountMembership, WorkItem, WorkItemCollaboration, WorkItemComment
from app.database.models.activity_log import ActivityLog
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/work-queue", tags=["work-queue-collaboration"])


class CollaborationUpdate(BaseModel):
    assignee_account_id: UUID | None = None
    owner_note: str | None = Field(default=None, max_length=4000)
    remind_at: datetime | None = None
    escalation_level: int = Field(default=0, ge=0, le=5)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


def _context(session, organization_slug: str, work_item_id: UUID):
    org = get_organization(session, organization_slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    work = session.get(WorkItem, work_item_id)
    if work is None or work.organization_id != org.id:
        raise HTTPException(status_code=404, detail="Arbeitselement nicht gefunden.")
    scope = current_scope_context()
    allowed = scoped_contract_ids(session, org.id, scope.hospital_id, scope.department_id)
    if allowed is not None and work.contract_id not in allowed:
        raise HTTPException(status_code=404, detail="Arbeitselement nicht gefunden.")
    return org, work, scope


def _collab_payload(row: WorkItemCollaboration | None) -> dict:
    if row is None:
        return {"assignee_account_id": None, "assignee_display_name": None, "owner_note": None, "remind_at": None, "escalation_level": 0}
    return {
        "assignee_account_id": str(row.assignee_account_id) if row.assignee_account_id else None,
        "owner_note": row.owner_note,
        "remind_at": row.remind_at,
        "escalation_level": row.escalation_level,
    }


@router.get("/{work_item_id}/collaboration")
def get_collaboration(request: Request, work_item_id: UUID, organization_slug: str):
    session = create_session()
    try:
        org, work, _ = _context(session, organization_slug, work_item_id)
        actor = getattr(request.state, "actor", None)
        if (actor is None and settings.auth_enabled) or (actor is not None and actor.organization_id != org.id):
            raise HTTPException(status_code=404, detail="Arbeitselement nicht gefunden.")
        row = session.scalars(
            select(WorkItemCollaboration).where(
                WorkItemCollaboration.organization_id == org.id,
                WorkItemCollaboration.work_item_id == work.id,
            )
        ).first()
        payload = _collab_payload(row)
        if row and row.assignee_account_id:
            account = session.get(Account, row.assignee_account_id)
            payload["assignee_display_name"] = account.display_name if account else None
        comments = session.scalars(
            select(WorkItemComment).where(
                WorkItemComment.organization_id == org.id,
                WorkItemComment.work_item_id == work.id,
            ).order_by(WorkItemComment.created_at.asc())
        ).all()
        payload["comments"] = [
            {
                "id": str(comment.id),
                "account_id": str(comment.account_id) if comment.account_id else None,
                "display_name": comment.display_name_snapshot,
                "body": comment.body,
                "created_at": comment.created_at,
            }
            for comment in comments
        ]
        return payload
    finally:
        session.close()


@router.put("/{work_item_id}/collaboration")
def update_collaboration(request: Request, work_item_id: UUID, organization_slug: str, body: CollaborationUpdate):
    session = create_session()
    try:
        org, work, scope = _context(session, organization_slug, work_item_id)
        actor = getattr(request.state, "actor", None)
        if actor is None or actor.organization_id != org.id:
            raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Organisation.")
        if body.assignee_account_id is not None:
            membership = session.scalars(
                select(AccountMembership).where(
                    AccountMembership.organization_id == org.id,
                    AccountMembership.account_id == body.assignee_account_id,
                    AccountMembership.is_active.is_(True),
                )
            ).first()
            account = session.get(Account, body.assignee_account_id)
            if account is None or not account.is_active or membership is None:
                raise HTTPException(status_code=422, detail="Zugewiesener Benutzer gehört nicht zur Organisation.")

        row = session.scalars(
            select(WorkItemCollaboration).where(WorkItemCollaboration.organization_id == org.id, WorkItemCollaboration.work_item_id == work.id)
        ).first()
        if row is None:
            row = WorkItemCollaboration(organization_id=org.id, work_item_id=work.id)
            session.add(row)
        row.assignee_account_id = body.assignee_account_id
        row.owner_note = body.owner_note
        row.remind_at = body.remind_at
        row.escalation_level = body.escalation_level

        if actor is not None:
            session.add(ActivityLog(
                organization_id=actor.organization_id,
                hospital_id=scope.hospital_id,
                department_id=scope.department_id,
                account_id=actor.account_id,
                display_name_snapshot=actor.display_name,
                role_snapshot="developer" if actor.is_developer else actor.role,
                event_name="work_item.collaboration_updated",
                object_type="contract",
                object_id=work.contract_id,
                context_data={"work_item_id": str(work.id), "assignee_account_id": str(body.assignee_account_id) if body.assignee_account_id else None, "remind_at": body.remind_at.isoformat() if body.remind_at else None, "escalation_level": body.escalation_level},
            ))
        session.commit()
        return _collab_payload(row)
    finally:
        session.close()


@router.post("/{work_item_id}/comments")
def add_comment(request: Request, work_item_id: UUID, organization_slug: str, body: CommentCreate):
    session = create_session()
    try:
        org, work, scope = _context(session, organization_slug, work_item_id)
        actor = getattr(request.state, "actor", None)
        if actor is None or actor.organization_id != org.id:
            raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Organisation.")
        if not body.body.strip():
            raise HTTPException(status_code=422, detail="Kommentar darf nicht leer sein.")
        comment = WorkItemComment(
            organization_id=org.id,
            work_item_id=work.id,
            account_id=actor.account_id,
            display_name_snapshot=actor.display_name,
            body=body.body.strip(),
        )
        session.add(comment)
        session.add(ActivityLog(
            organization_id=actor.organization_id,
            hospital_id=scope.hospital_id,
            department_id=scope.department_id,
            account_id=actor.account_id,
            display_name_snapshot=actor.display_name,
            role_snapshot="developer" if actor.is_developer else actor.role,
            event_name="work_item.comment_added",
            object_type="contract",
            object_id=work.contract_id,
            context_data={"work_item_id": str(work.id)},
        ))
        session.commit()
        return {"id": str(comment.id), "display_name": comment.display_name_snapshot, "body": comment.body, "created_at": comment.created_at}
    finally:
        session.close()
