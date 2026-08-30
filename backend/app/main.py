"""Medflux Backend – Einstiegspunkt (FastAPI)."""

from fastapi import FastAPI

from app.api.routes import ai, documents, health
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Lokales KI-System zur Analyse und Überwachung "
        "von Wartungs- und Serviceverträgen."
    ),
)

app.include_router(health.router)
app.include_router(ai.router)
app.include_router(documents.router)


@app.get("/")
def root() -> dict:
    return {"service": settings.app_name, "version": settings.app_version}
