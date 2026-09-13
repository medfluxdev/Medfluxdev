"""Zentrale Auth-Grenze fuer den lokalen MedFlux-API-Prozess (STEP 16)."""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.auth.context import optional_identity
from app.auth.runtime import bind_identity, reset_identity
from app.core.config import settings

_PUBLIC_PREFIXES = (
    "/api/health",
    "/api/auth/login",
)
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _origin_allowed(origin: str) -> bool:
    normalized = origin.rstrip("/")
    return normalized in {value.rstrip("/") for value in settings.cors_origins_list}


class LocalAuthMiddleware(BaseHTTPMiddleware):
    """Erzwingt bei AUTH_ENABLED jede nicht-oeffentliche API-Anfrage.

    Die Organisationszugehoerigkeit kommt aus der signierten Sitzung. Ein
    abweichender `organization_slug` wird als nicht vorhanden behandelt, damit
    der Query-Parameter niemals zu einem Autorisierungs-Credential wird.
    Viewer duerfen lesen, aber keine fachlichen Mutationen ausloesen.
    """

    async def dispatch(self, request: Request, call_next):
        if not settings.auth_enabled or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path == "/" or any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)

        token = None
        if path.startswith("/api/"):
            identity = optional_identity(request)
            if identity is None:
                return JSONResponse(status_code=401, content={"detail": "Anmeldung erforderlich."})
            requested_slug = request.query_params.get("organization_slug")
            if requested_slug and requested_slug != identity.organization_slug:
                return JSONResponse(status_code=404, content={"detail": "Ressource nicht gefunden."})
            if request.method in _WRITE_METHODS:
                # Cookie-authenticated browser writes must originate from the
                # explicitly configured frontend. SameSite=Lax is useful
                # defense-in-depth but is not our only CSRF boundary.
                origin = request.headers.get("origin")
                if origin and not _origin_allowed(origin):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Ungueltiger Anfrage-Ursprung."},
                    )
            if (
                request.method in _WRITE_METHODS
                and identity.role == "viewer"
                and path != "/api/auth/logout"
            ):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Keine Berechtigung fuer diese Aktion."},
                )
            request.state.auth_identity = identity
            token = bind_identity(identity)

        try:
            return await call_next(request)
        finally:
            if token is not None:
                reset_identity(token)
