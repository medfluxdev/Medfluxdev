from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.database.models import AccountMembership
from app.database.session import create_session


@dataclass(frozen=True)
class ScopeContext:
    organization_slug: str | None = None
    hospital_id: UUID | None = None
    department_id: UUID | None = None


_scope: ContextVar[ScopeContext] = ContextVar("medflux_scope", default=ScopeContext())
_NO_SCOPE_HOSPITAL = UUID(int=0)


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
        organization_slug = request.query_params.get("organization_slug")
        hospital_id = _uuid(request.query_params.get("hospital_id"))
        department_id = _uuid(request.query_params.get("department_id"))

        actor = getattr(request.state, "actor", None)
        if actor is not None and actor.role != "admin" and not getattr(actor, "is_developer", False):
            session = create_session()
            try:
                membership = session.scalar(select(AccountMembership).where(
                    (AccountMembership.account_id == actor.account_id)
                    & (AccountMembership.organization_id == actor.organization_id)
                    & (AccountMembership.is_active.is_(True))
                ))
                if membership is not None:
                    # Normal users never get organization-wide visibility by
                    # accident. A membership without an assigned hospital is a
                    # provisioning state, not a global scope. UUID(0) is an
                    # impossible hospital FK and therefore yields an empty scope
                    # in all scoped contract/equipment queries until an admin
                    # assigns the user properly.
                    hospital_id = membership.hospital_id or _NO_SCOPE_HOSPITAL
                    department_id = membership.department_id
                else:
                    hospital_id = _NO_SCOPE_HOSPITAL
                    department_id = None
            finally:
                session.close()

        token = _scope.set(ScopeContext(
            organization_slug=organization_slug,
            hospital_id=hospital_id,
            department_id=department_id,
        ))
        try:
            return await call_next(request)
        finally:
            _scope.reset(token)
