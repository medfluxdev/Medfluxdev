from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth.service import account_from_selector, actor_for_account
from app.core.config import settings
from app.database.session import create_session


_PUBLIC_PATHS = {"/", "/api/health", "/docs", "/openapi.json"}


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not settings.auth_enabled or path in _PUBLIC_PATHS or path.startswith("/api/auth/"):
            return await call_next(request)
        if not path.startswith("/api/"):
            return await call_next(request)

        selector = request.cookies.get(settings.auth_cookie_name, "")
        session = create_session()
        try:
            account = account_from_selector(session, selector)
            if account is None:
                return JSONResponse({"detail": "Bitte anmelden."}, status_code=401)
            request.state.account_id = account.id
            request.state.account_display_name = account.display_name
            request.state.account_login_name = account.login_name

            organization_slug = request.query_params.get("organization_slug")
            if organization_slug:
                actor = actor_for_account(session, account, organization_slug)
                if actor is None:
                    return JSONResponse({"detail": "Kein Zugriff auf diese Organisation."}, status_code=403)
                request.state.actor = actor
            return await call_next(request)
        finally:
            session.close()
