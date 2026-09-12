from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.credential_store import derive_password
from app.auth.dependencies import current_actor
from app.auth.service import create_account, require_role
from app.database.models import Account, AccountMembership, Organization
from app.database.models.account import ACCOUNT_ROLES
from app.database.session import create_session

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreateRequest(BaseModel):
    email: str
    display_name: str
    password: str
    role: str = "viewer"


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


def _admin_actor(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    try:
        require_role(actor, "admin")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return actor


def _serialize(account: Account, membership: AccountMembership) -> dict:
    return {
        "id": str(account.id),
        "email": account.login_name,
        "display_name": account.display_name,
        "role": membership.role,
        "is_active": account.is_active and membership.is_active,
        "last_login_at": account.last_login_at.isoformat() if account.last_login_at else None,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }


@router.get("")
def list_users(request: Request, organization_slug: str):
    actor = _admin_actor(request, organization_slug)
    session = create_session()
    try:
        rows = session.execute(
            select(Account, AccountMembership)
            .join(AccountMembership, AccountMembership.account_id == Account.id)
            .where(AccountMembership.organization_id == actor.organization_id)
            .order_by(Account.display_name.asc(), Account.login_name.asc())
        ).all()
        return {"items": [_serialize(account, membership) for account, membership in rows]}
    finally:
        session.close()


@router.post("")
def add_user(request: Request, organization_slug: str, payload: UserCreateRequest):
    actor = _admin_actor(request, organization_slug)
    session = create_session()
    try:
        try:
            account = create_account(
                session,
                login_name=payload.email,
                display_name=payload.display_name,
                password=payload.password,
                organization_id=actor.organization_id,
                role=payload.role,
            )
            membership = session.scalar(select(AccountMembership).where(
                (AccountMembership.account_id == account.id)
                & (AccountMembership.organization_id == actor.organization_id)
            ))
            session.commit()
            return _serialize(account, membership)
        except ValueError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(exc))
    finally:
        session.close()


@router.patch("/{account_id}")
def update_user(request: Request, organization_slug: str, account_id: str, payload: UserUpdateRequest):
    actor = _admin_actor(request, organization_slug)
    try:
        account_uuid = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    session = create_session()
    try:
        row = session.execute(
            select(Account, AccountMembership)
            .join(AccountMembership, AccountMembership.account_id == Account.id)
            .where(
                (Account.id == account_uuid)
                & (AccountMembership.organization_id == actor.organization_id)
            )
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
        account, membership = row
        if payload.display_name is not None:
            account.display_name = payload.display_name.strip() or account.display_name
        if payload.role is not None:
            if payload.role not in ACCOUNT_ROLES:
                raise HTTPException(status_code=422, detail="Unbekannte Rolle.")
            membership.role = payload.role
        if payload.is_active is not None:
            if account.id == actor.account_id and payload.is_active is False:
                raise HTTPException(status_code=422, detail="Der eigene Benutzer kann nicht deaktiviert werden.")
            membership.is_active = payload.is_active
            account.is_active = payload.is_active
        if payload.password is not None:
            if len(payload.password) < 10:
                raise HTTPException(status_code=422, detail="Das Passwort muss mindestens 10 Zeichen lang sein.")
            account.credential_digest = derive_password(payload.password)
        session.commit()
        return _serialize(account, membership)
    finally:
        session.close()
