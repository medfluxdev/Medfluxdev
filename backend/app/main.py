"""Medflux Backend – Einstiegspunkt (FastAPI)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    activity,
    ai,
    auth,
    contract_actions_secure,
    contracts,
    dashboard,
    demo,
    documents,
    equipment,
    health,
    organization_structure,
    profile,
    users,
    work_queue,
)
from app.auth.middleware import AuthenticationMiddleware as SessionGuardMiddleware
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Lokales KI-System zur Analyse und Überwachung "
        "von Wartungs- und Serviceverträgen."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)
app.add_middleware(SessionGuardMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(users.router)
app.include_router(organization_structure.router)
app.include_router(activity.router)
app.include_router(ai.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
app.include_router(contract_actions_secure.router)
app.include_router(contracts.router)
app.include_router(equipment.router)
app.include_router(work_queue.router)
app.include_router(demo.router)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "version": settings.app_version}
