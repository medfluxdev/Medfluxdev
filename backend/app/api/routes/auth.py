"""Lokale Login-/Session-/Audit-API (STEP 16)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth.context import require_identity
from app.auth.security import AuthSecurityError, create_session_token
from app.auth.service import AuthIdentity, authenticate_user, list_audit_events, record_audit_event
from app.core.config import settings
from app.database.session import create_session

router = APIRouter(prefix="/api/auth", tags=["auth"])
audit_router = APIRouter(prefix="/api/audit", tags=["audit"])


class LoginRequest(BaseModel):
    organization_slug: str = Field(min_length=1, max_length=80)
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=512)


class IdentityResponse(BaseModel):
    user_id: str
    organization_id: str
    organization_slug: str
    username: str
    display_name: str
    role: str


class AuditEventResponse(BaseModel):
    id: str
    user_id: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    details: dict[str, Any] | None
    created_at: datetime


def _identity_response(identity: AuthIdentity) -> IdentityResponse:
    return IdentityResponse(
        user_id=str(identity.user_id),
        organization_id=str(identity.organization_id),
        organization_slug=identity.organization_slug,
        username=identity.username,
        display_name=identity.display_name,
        role=identity.role,
    )


@router.post("/login", response_model=IdentityResponse)
def login(payload: LoginRequest, response: Response) -> IdentityResponse:
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lokale Anmeldung ist nicht aktiviert.",
        )
    session = create_session()
    try:
        identity = authenticate_user(
            session,
            organization_slug=payload.organization_slug.strip(),
            username=payload.username,
            password=payload.password,
        )
        if identity is None:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Anmeldedaten ungueltig.",
            )
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
            raise HTTPException(status_code=500, detail="Anmeldung ist nicht sicher konfiguriert.") from exc
        response.set_cookie(
            key=settings.auth_cookie_name,
            value=token,
            max_age=settings.auth_session_ttl_seconds,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite=settings.auth_cookie_samesite,
            path="/",
        )
        return _identity_response(identity)
    finally:
        session.close()


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> Response:
    identity = require_identity(request)
    session = create_session()
    try:
        record_audit_event(
            session,
            organization_id=identity.organization_id,
            user_id=identity.user_id,
            action="auth.logout",
            entity_type="user",
            entity_id=str(identity.user_id),
        )
        session.commit()
    finally:
        session.close()
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=IdentityResponse)
def me(identity: AuthIdentity = Depends(require_identity)) -> IdentityResponse:
    return _identity_response(identity)


@audit_router.get("", response_model=list[AuditEventResponse])
def audit_list(
    limit: int = 200,
    identity: AuthIdentity = Depends(require_identity),
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
