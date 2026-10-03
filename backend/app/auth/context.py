"""FastAPI-Auth-Kontext und rollenbasierte Zugriffskontrolle (STEP 16)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.auth.security import AuthSecurityError, decode_session_token
from app.auth.service import (
    Actor,
    AuthIdentity,
    account_from_selector,
    actor_for_account,
    get_identity_by_id,
    memberships_for_account,
)
from app.core.config import settings
from app.database.session import create_session


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Anmeldung erforderlich.",
    )


def optional_identity(request: Request) -> AuthIdentity | Actor | None:
    """Resolve either JAMAL signed sessions or Ahmad revocable account sessions."""
    cached = getattr(request.state, "auth_identity", None)
    if isinstance(cached, (AuthIdentity, Actor)):
        return cached

    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None

    # JAMAL legacy signed-token session.
    try:
        payload = decode_session_token(token, secret=settings.app_secret_key)
        user_id = uuid.UUID(payload["sub"])
    except (AuthSecurityError, ValueError):
        payload = None
        user_id = None

    session = create_session()
    try:
        if payload is not None and user_id is not None:
            identity = get_identity_by_id(session, user_id)
            if identity is None:
                return None
            if (
                str(identity.organization_id) != payload["org"]
                or identity.role != payload["role"]
            ):
                return None
            request.state.auth_identity = identity
            return identity

        # Ahmad account selector session. Organization context remains explicit
        # in the request and is checked against account membership.
        account = account_from_selector(session, token)
        if account is None:
            return None
        requested_slug = request.query_params.get("organization_slug")
        if not requested_slug:
            memberships = memberships_for_account(session, account.id)
            if account.is_developer:
                return None
            if len(memberships) == 1:
                requested_slug = memberships[0][1].slug
            else:
                return None
        actor = actor_for_account(session, account, requested_slug)
        if actor is None:
            return None
        request.state.auth_identity = actor
        request.state.actor = actor
        request.state.account_id = account.id
        request.state.account_display_name = account.display_name
        request.state.account_login_name = account.login_name
        request.state.is_developer = bool(account.is_developer)
        return actor
    finally:
        session.close()


def require_identity(request: Request) -> AuthIdentity | Actor:
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
        raise HTTPException(status_code=404, detail="Ressource nicht gefunden.")


def reviewer_name(request: Request, client_value: str | None) -> str | None:
    """Bei aktiver Auth kommt die Reviewer-Identitaet ausschliesslich vom Server."""
    if settings.auth_enabled:
        identity = require_identity(request)
        if identity.role not in {"admin", "contract_manager", "reviewer"}:
            raise HTTPException(status_code=403, detail="Keine Berechtigung fuer diese Aktion.")
        return identity.display_name
    return client_value
