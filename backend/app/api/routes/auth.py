"""Unified authentication API for the JAMAL + Ahmad integration branch."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.context import require_identity
from app.auth.security import AuthSecurityError, create_session_token
from app.auth.service import (
    Actor,
    AuthIdentity,
    account_from_selector,
    authenticate,
    authenticate_user,
    create_login_session,
    list_audit_events,
    memberships_for_account,
    record_audit_event,
    revoke_login_session,
)
from app.core.config import settings
from app.database.models import Organization
from app.database.session import create_session

router = APIRouter(tags=["auth"])
audit_router = APIRouter(prefix="/api/audit", tags=["audit"])


class LoginRequest(BaseModel):
    # Ahmad account login
    email: str | None = Field(default=None, max_length=320)
    # JAMAL STEP16 legacy login
    organization_slug: str | None = Field(default=None, max_length=80)
    username: str | None = Field(default=None, max_length=120)
    password: str = Field(min_length=1, max_length=512)


class AuditEventResponse(BaseModel):
    id: str
    user_id: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    details: dict[str, Any] | None
    created_at: datetime


def _account_payload(session, account) -> dict[str, Any]:
    memberships = memberships_for_account(session, account.id)
    organizations = []
    if account.is_developer:
        organizations = list(
            session.scalars(
                select(Organization)
                .where(Organization.is_active.is_(True))
                .order_by(Organization.name.asc())
            ).all()
        )

    membership_items = [
        {
            "organization_id": str(org.id),
            "organization_slug": org.slug,
            "organization_name": org.name,
            "role": membership.role,
            "hospital_id": str(membership.hospital_id)
            if membership.hospital_id
            else None,
            "department_id": str(membership.department_id)
            if membership.department_id
            else None,
            "is_default": membership.is_default,
        }
        for membership, org in memberships
    ]
    if account.is_developer:
        membership_items = [
            {
                "organization_id": str(org.id),
                "organization_slug": org.slug,
                "organization_name": org.name,
                "role": "admin",
                "hospital_id": None,
                "department_id": None,
                "is_default": False,
            }
            for org in organizations
        ]

    return {
        "id": str(account.id),
        "email": account.login_name,
        "display_name": account.display_name,
        "is_active": account.is_active,
        "is_developer": account.is_developer,
        "last_login_at": account.last_login_at.isoformat()
        if account.last_login_at
        else None,
        "profile_photo_data_url": account.profile_photo_data_url,
        "phone": account.phone,
        "job_title": account.job_title,
        "department": account.department,
        "bio": account.bio,
        "memberships": membership_items,
    }


def _legacy_payload(identity: AuthIdentity | Actor) -> dict[str, Any]:
    user_id = getattr(identity, "user_id", None) or getattr(identity, "account_id")
    username = getattr(identity, "username", None) or getattr(identity, "login_name", "")
    return {
        "id": str(user_id),
        "email": username,
        "display_name": identity.display_name,
        "is_active": True,
        "is_developer": bool(getattr(identity, "is_developer", False)),
        "last_login_at": None,
        "profile_photo_data_url": None,
        "phone": None,
        "job_title": None,
        "department": None,
        "bio": None,
        "memberships": [
            {
                "organization_id": str(identity.organization_id),
                "organization_slug": identity.organization_slug,
                "organization_name": identity.organization_slug,
                "role": identity.role,
                "hospital_id": None,
                "department_id": None,
                "is_default": True,
            }
        ],
    }


@router.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lokale Anmeldung ist nicht aktiviert.",
        )

    session = create_session()
    try:
        if payload.email:
            account = authenticate(session, payload.email, payload.password)
            if account is None:
                session.rollback()
                raise HTTPException(
                    status_code=401,
                    detail="Benutzername/E-Mail oder Passwort ist falsch.",
                )
            selector, _ = create_login_session(session, account.id)
            session.commit()
            response.set_cookie(
                key=settings.auth_cookie_name,
                value=selector,
                httponly=True,
                secure=settings.auth_cookie_secure,
                samesite=settings.auth_cookie_samesite,
                max_age=settings.auth_session_days * 24 * 60 * 60,
                path="/",
            )
            return {"ok": True}

        if not payload.organization_slug or not payload.username:
            raise HTTPException(
                status_code=422,
                detail="E-Mail oder Organisation + Benutzername erforderlich.",
            )

        identity = authenticate_user(
            session,
            organization_slug=payload.organization_slug.strip(),
            username=payload.username,
            password=payload.password,
        )
        if identity is None:
            session.rollback()
            raise HTTPException(status_code=401, detail="Anmeldedaten ungueltig.")

        record_audit_event(
            session,
            organization_id=identity.organization_id,
            user_id=identity.user_id,
            action="auth.login",
            entity_type="user",
            entity_id=str(identity.user_id),
        )
        session.commit()
        try:
            token = create_session_token(
                user_id=str(identity.user_id),
                organization_id=str(identity.organization_id),
                role=identity.role,
                secret=settings.app_secret_key,
                ttl_seconds=settings.auth_session_ttl_seconds,
            )
        except AuthSecurityError as exc:
            raise HTTPException(
                status_code=500,
                detail="Anmeldung ist nicht sicher konfiguriert.",
            ) from exc
        response.set_cookie(
            key=settings.auth_cookie_name,
            value=token,
            max_age=settings.auth_session_ttl_seconds,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite,
            path="/",
        )
        return {"ok": True}
    finally:
        session.close()


@router.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(settings.auth_cookie_name, "")
    session = create_session()
    try:
        account = account_from_selector(session, token)
        if account is not None:
            revoke_login_session(session, token)
            session.commit()
        else:
            identity = getattr(request.state, "auth_identity", None)
            if identity is not None and hasattr(identity, "organization_id"):
                record_audit_event(
                    session,
                    organization_id=identity.organization_id,
                    user_id=getattr(identity, "user_id", None),
                    action="auth.logout",
                    entity_type="user",
                    entity_id=str(getattr(identity, "user_id", "")) or None,
                )
                session.commit()
    finally:
        session.close()

    response.delete_cookie(settings.auth_cookie_name, path="/")
    return {"ok": True}


@router.get("/api/me")
def me(request: Request) -> dict[str, Any]:
    selector = request.cookies.get(settings.auth_cookie_name, "")
    session = create_session()
    try:
        account = account_from_selector(session, selector)
        if account is not None:
            return _account_payload(session, account)
    finally:
        session.close()

    identity = require_identity(request)
    return _legacy_payload(identity)


@router.get("/api/auth/me")
def auth_me(request: Request) -> dict[str, Any]:
    """Compatibility alias retained for JAMAL clients."""
    return me(request)


@audit_router.get("", response_model=list[AuditEventResponse])
def audit_list(
    limit: int = 200,
    identity: AuthIdentity | Actor = Depends(require_identity),
) -> list[AuditEventResponse]:
    limit = max(1, min(limit, 500))
    session = create_session()
    try:
        events = list_audit_events(
            session, organization_id=identity.organization_id, limit=limit
        )
        return [
            AuditEventResponse(
                id=str(event.id),
                user_id=str(event.user_id) if event.user_id else None,
                action=event.action,
                entity_type=event.entity_type,
                entity_id=event.entity_id,
                details=event.details,
                created_at=event.created_at,
            )
            for event in events
        ]
    finally:
        session.close()
