"""Medflux Backend – Einstiegspunkt (FastAPI)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    ai,
    auth,
    contracts,
    dashboard,
    demo,
    documents,
    equipment,
    health,
    intelligence,
    operations,
    work_queue,
)
from app.auth.middleware import LocalAuthMiddleware
from app.auth.provenance import register_auth_provenance_hooks
from app.core.config import settings
from app.security.headers import SecurityHeadersMiddleware

register_auth_provenance_hooks()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Lokales KI-System zur Analyse und Überwachung "
        "von Wartungs- und Serviceverträgen."
    ),
)

# Globale Sicherheitsheader zuerst registrieren; Starlette fuehrt Middleware in
# umgekehrter Registrierungsreihenfolge aus und setzt die Header so auch auf
# Auth-/Fehlerantworten.
app.add_middleware(SecurityHeadersMiddleware)

# STEP 16: bei aktivierter lokaler Anmeldung schuetzt die zentrale Middleware
# alle nicht-oeffentlichen API-Routen und bindet organization_slug an die
# authentifizierte Organisation.
app.add_middleware(LocalAuthMiddleware)

# Lokale Entwicklung: erlaube die konfigurierten Frontend-Origins (Standard:
# http://localhost:3000). Der Origin-Set wird über settings.cors_origins
# gesteuert (Umgebung/.env). Erlaubt nur die vom Frontend benötigten Methoden
# und Header – kein Wildcard. Cookies werden nur bei aktivierter Auth freigegeben.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.auth_enabled,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(auth.audit_router)
app.include_router(ai.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
app.include_router(contracts.router)
app.include_router(equipment.router)
app.include_router(work_queue.router)
app.include_router(intelligence.router)
app.include_router(operations.router)
app.include_router(demo.router)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "version": settings.app_version}
