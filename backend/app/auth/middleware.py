"""Unified authentication boundary for JAMAL + Ahmad integration.

Supports both:
- JAMAL STEP16 signed app_user sessions
- Ahmad revocable account/login_session selectors

Organization authorization remains server-side and fail-closed.
"""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.auth.context import optional_identity
from app.auth.runtime import bind_identity, reset_identity
from app.auth.service import account_from_selector, actor_for_account
from app.core.config import settings
from app.database.session import create_session

_PUBLIC_PREFIXES = (
    "/api/health",
    "/api/auth/login",
)
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _origin_allowed(origin: str) -> bool:
    normalized = origin.rstrip("/")
    return normalized in {value.rstrip("/") for value in settings.cors_origins_list}


def _reviewer_mutation_allowed(path: str) -> bool:
    return (
        (
            path.startswith("/api/contracts/")
            and ("/fact-reviews" in path or "/review/" in path)
        )
        or path.startswith("/api/work-queue/")
    )


class LocalAuthMiddleware(BaseHTTPMiddleware):
    """Authenticate either session model without weakening organization isolation."""

    async def dispatch(self, request: Request, call_next):
        if not settings.auth_enabled or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path == "/" or any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)

        runtime_token = None
        if path.startswith("/api/"):
            identity = optional_identity(request)
            requested_slug = request.query_params.get("organization_slug")

            # Account sessions with multiple memberships cannot be represented by
            # one organization-bound identity until a slug is selected. They are
            # still valid for account-level endpoints such as /api/me/profile.
            if identity is None:
                selector = request.cookies.get(settings.auth_cookie_name, "")
                session = create_session()
                try:
                    account = account_from_selector(session, selector)
                    if account is None:
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "Anmeldung erforderlich."},
                        )
                    request.state.account_id = account.id
                    request.state.account_display_name = account.display_name
                    request.state.account_login_name = account.login_name
                    request.state.is_developer = bool(account.is_developer)

                    if requested_slug:
                        actor = actor_for_account(session, account, requested_slug)
                        if actor is None:
                            return JSONResponse(
                                status_code=404,
                                content={"detail": "Ressource nicht gefunden."},
                            )
                        identity = actor
                        request.state.actor = actor
                        request.state.auth_identity = actor
                finally:
                    session.close()

            if identity is not None:
                if (
                    requested_slug
                    and requested_slug != identity.organization_slug
                ):
                    return JSONResponse(
                        status_code=404,
                        content={"detail": "Ressource nicht gefunden."},
                    )

                if request.method in _WRITE_METHODS:
                    # Cookie-authenticated browser writes must originate from an
                    # explicitly configured frontend origin.
                    origin = request.headers.get("origin")
                    if origin and not _origin_allowed(origin):
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "Ungueltiger Anfrage-Ursprung."},
                        )
                    if identity.role == "viewer":
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "Keine Berechtigung fuer diese Aktion."},
                        )
                    if (
                        identity.role == "reviewer"
                        and not _reviewer_mutation_allowed(path)
                    ):
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "Für diese Änderung fehlt die Berechtigung."},
                        )

                request.state.auth_identity = identity
                if hasattr(identity, "account_id"):
                    request.state.actor = identity
                runtime_token = bind_identity(identity)

        try:
            return await call_next(request)
        finally:
            if runtime_token is not None:
                reset_identity(runtime_token)
