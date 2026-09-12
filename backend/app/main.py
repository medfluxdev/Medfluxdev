"""Medflux Backend – Einstiegspunkt (FastAPI)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    ai,
    contracts,
    dashboard,
    demo,
    documents,
    equipment,
    health,
    work_queue,
)
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Lokales KI-System zur Analyse und Überwachung "
        "von Wartungs- und Serviceverträgen."
    ),
)

# Lokale Entwicklung: erlaube die konfigurierten Frontend-Origins (Standard:
# http://localhost:3000). Der Origin-Set wird über settings.cors_origins
# gesteuert (Umgebung/.env). Erlaubt nur die vom Frontend benötigten Methoden
# und Header – kein Wildcard, keine freigegebenen Credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.auth_enabled,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Content-Type"],
)

app.include_router(health.router)
app.include_router(ai.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
app.include_router(contracts.router)
app.include_router(equipment.router)
app.include_router(work_queue.router)
app.include_router(demo.router)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "version": settings.app_version}
