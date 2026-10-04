"""MedFlux Backend – integrated JAMAL + Ahmad entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    activity,
    ai,
    auth,
    contract_billing,
    contracts,
    cost_center_routes,
    dashboard,
    documents,
    equipment,
    health,
    intelligence,
    intelligence_actions,
    intelligence_analytics,
    lifecycle,
    notifications,
    operations,
    organization_structure,
    ownership,
    processing_jobs,
    profile,
    reports,
    security_sessions,
    system_organizations,
    user_scopes,
    users,
    work_queue,
    work_queue_collaboration,
)
from app.auth.middleware import LocalAuthMiddleware
from app.auth.provenance import register_auth_provenance_hooks
from app.core.config import settings
from app.core.scope_context import ScopeContextMiddleware
from app.security.headers import SecurityHeadersMiddleware
from app.security.request_context import LoginRateLimitMiddleware, RequestIdMiddleware

register_auth_provenance_hooks()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Lokales KI-System zur Analyse und Überwachung "
        "von Wartungs- und Serviceverträgen."
    ),
)

# Scope runs after auth (Starlette executes middleware in reverse registration
# order), so account membership can make hospital/department scope authoritative.
app.add_middleware(ScopeContextMiddleware)
app.add_middleware(LocalAuthMiddleware)

# The frontend always uses credentials="include". CORS must therefore advertise
# credentials support in both auth-enabled and local auth-disabled modes.
# Wildcard origins are rejected by settings validation.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID"],
)
app.add_middleware(LoginRateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)

# Keep JAMAL security headers outermost.
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(auth.audit_router)
app.include_router(security_sessions.router)

# Ahmad account / organization administration.
app.include_router(profile.router)
app.include_router(users.router)
app.include_router(user_scopes.router)
app.include_router(system_organizations.router)
app.include_router(organization_structure.router)
app.include_router(cost_center_routes.router)
app.include_router(ownership.router)
app.include_router(activity.router)

# Existing JAMAL product APIs remain authoritative.
app.include_router(ai.router)
app.include_router(documents.router)
app.include_router(processing_jobs.router)
app.include_router(dashboard.router)
app.include_router(contracts.router)
app.include_router(equipment.router)
app.include_router(lifecycle.router)
app.include_router(work_queue.router)
app.include_router(work_queue_collaboration.router)
app.include_router(intelligence.router)
app.include_router(intelligence_actions.router)
app.include_router(intelligence_analytics.router)
app.include_router(contract_billing.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(operations.router)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "version": settings.app_version}
