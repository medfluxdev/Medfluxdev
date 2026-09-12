from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


@dataclass(frozen=True)
class ScopeContext:
    organization_slug: str | None = None
    hospital_id: UUID | None = None
    department_id: UUID | None = None


_scope: ContextVar[ScopeContext] = ContextVar("medflux_scope", default=ScopeContext())


def current_scope_context() -> ScopeContext:
    return _scope.get()


def _uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


class ScopeContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = _scope.set(ScopeContext(
            organization_slug=request.query_params.get("organization_slug"),
            hospital_id=_uuid(request.query_params.get("hospital_id")),
            department_id=_uuid(request.query_params.get("department_id")),
        ))
        try:
            return await call_next(request)
        finally:
            _scope.reset(token)
