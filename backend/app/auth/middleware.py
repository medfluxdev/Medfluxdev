"""Zentrale Auth-Grenze fuer den lokalen MedFlux-API-Prozess (STEP 16)."""

from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.auth.context import optional_identity
from app.core.config import settings

_PUBLIC_PREFIXES = (
    "/api/health",
    "/api/auth/login",
)


class LocalAuthMiddleware(BaseHTTPMiddleware):
    """Erzwingt bei AUTH_ENABLED jede nicht-oeffentliche API-Anfrage.

    Die Organisationszugehoerigkeit kommt aus der signierten Sitzung. Ein
    abweichender `organization_slug` wird als nicht vorhanden behandelt, damit
    der Query-Parameter niemals zu einem Autorisierungs-Credential wird.
    """

    async def dispatch(self, request: Request, call_next):
        if not settings.auth_enabled or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path == "/" or any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)

        if path.startswith("/api/"):
            identity = optional_identity(request)
            if identity is None:
                return JSONResponse(status_code=401, content={"detail": "Anmeldung erforderlich."})
            requested_slug = request.query_params.get("organization_slug")
            if requested_slug and requested_slug != identity.organization_slug:
                return JSONResponse(status_code=404, content={"detail": "Ressource nicht gefunden."})
            request.state.auth_identity = identity

        return await call_next(request)
