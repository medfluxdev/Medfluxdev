"""FastAPI-Auth-Kontext und rollenbasierte Zugriffskontrolle (STEP 16)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.auth.security import AuthSecurityError, decode_session_token
from app.auth.service import AuthIdentity, get_identity_by_id
from app.core.config import settings
from app.database.session import create_session


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Anmeldung erforderlich.",
    )


def optional_identity(request: Request) -> AuthIdentity | None:
    """Liest die lokale Sitzung; im Entwicklungsmodus ist Identitaet optional."""
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None
    try:
        payload = decode_session_token(token, secret=settings.app_secret_key)
        user_id = uuid.UUID(payload["sub"])
    except (AuthSecurityError, ValueError):
        return None
    session = create_session()
    try:
        identity = get_identity_by_id(session, user_id)
        if identity is None:
            return None
        if str(identity.organization_id) != payload["org"] or identity.role != payload["role"]:
            return None
        return identity
    finally:
        session.close()


def require_identity(request: Request) -> AuthIdentity:
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lokale Anmeldung ist nicht aktiviert.",
        )
    identity = optional_identity(request)
    if identity is None:
        raise _unauthorized()
    return identity


def require_role(*roles: str) -> Callable[[Request], AuthIdentity]:
    allowed = frozenset(roles)

    def dependency(request: Request) -> AuthIdentity:
        identity = require_identity(request)
        if identity.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Keine Berechtigung fuer diese Aktion.",
            )
        return identity

    return dependency


def enforce_org(identity: AuthIdentity, requested_slug: str) -> None:
    """Verhindert, dass organization_slug als Autorisierungs-Credential missbraucht wird."""
    if identity.organization_slug != requested_slug:
        # 404 statt 403 vermeidet Organisations-Enumeration.
        raise HTTPException(status_code=404, detail="Ressource nicht gefunden.")
