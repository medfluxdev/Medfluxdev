from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.dependencies import current_actor
from app.auth.service import require_role
from app.database.models import Account, AccountMembership
from app.database.models.activity_log import ActivityLog
from app.database.models.organization_structure import Department, Hospital
from app.database.session import create_session

router = APIRouter(prefix="/api/user-scopes", tags=["user-scopes"])


class ScopeUpdate(BaseModel):
    hospital_id: UUID | None = None
    department_id: UUID | None = None
    is_default: bool = True


def _admin(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    try:
        require_role(actor, "admin")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return actor


def _scope_payload(account: Account, membership: AccountMembership) -> dict:
    return {
        "account_id": str(account.id),
        "hospital_id": str(membership.hospital_id) if membership.hospital_id else None,
        "department_id": str(membership.department_id) if membership.department_id else None,
        "is_default": membership.is_default,
    }


def _log_scope_change(session, actor, account_id: UUID, before: dict, after: dict) -> None:
    session.add(
        ActivityLog(
            organization_id=actor.organization_id,
            account_id=actor.account_id,
            display_name_snapshot=actor.display_name,
            role_snapshot=actor.role,
            event_name="account.scope_updated",
            object_type="account",
            object_id=account_id,
            context_data={"before": before, "after": after},
        )
    )


@router.get("")
def list_scopes(request: Request, organization_slug: str):
    actor = _admin(request, organization_slug)
    session = create_session()
    try:
        rows = session.execute(
            select(Account, AccountMembership)
            .join(AccountMembership, AccountMembership.account_id == Account.id)
            .where(AccountMembership.organization_id == actor.organization_id)
            .order_by(Account.display_name.asc())
        ).all()
        return {"items": [_scope_payload(account, membership) for account, membership in rows]}
    finally:
        session.close()


@router.patch("/{account_id}")
def update_scope(request: Request, organization_slug: str, account_id: UUID, payload: ScopeUpdate):
    actor = _admin(request, organization_slug)
    session = create_session()
    try:
        row = session.execute(
            select(Account, AccountMembership)
            .join(AccountMembership, AccountMembership.account_id == Account.id)
            .where((Account.id == account_id) & (AccountMembership.organization_id == actor.organization_id))
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
        account, membership = row

        hospital = None
        if payload.hospital_id is not None:
            hospital = session.scalar(select(Hospital).where(
                (Hospital.id == payload.hospital_id)
                & (Hospital.organization_id == actor.organization_id)
                & (Hospital.is_active.is_(True))
            ))
            if hospital is None:
                raise HTTPException(status_code=422, detail="Krankenhaus ist für diese Organisation nicht verfügbar.")

        if payload.department_id is not None:
            department = session.scalar(select(Department).where(
                (Department.id == payload.department_id)
                & (Department.organization_id == actor.organization_id)
                & (Department.is_active.is_(True))
            ))
            if department is None:
                raise HTTPException(status_code=422, detail="Abteilung ist für diese Organisation nicht verfügbar.")
            if hospital is None or department.hospital_id != hospital.id:
                raise HTTPException(status_code=422, detail="Die Abteilung gehört nicht zum ausgewählten Krankenhaus.")

        if membership.role != "admin" and hospital is None:
            raise HTTPException(status_code=422, detail="Für normale Benutzer muss ein Krankenhaus festgelegt werden.")

        before = _scope_payload(account, membership)
        membership.hospital_id = payload.hospital_id
        membership.department_id = payload.department_id
        membership.is_default = payload.is_default
        after = _scope_payload(account, membership)
        if before != after:
            _log_scope_change(session, actor, account.id, before, after)
        session.commit()
        return after
    finally:
        session.close()
