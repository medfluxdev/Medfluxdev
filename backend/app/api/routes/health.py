"""Operational health/readiness routes for MedFlux."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.config import settings
from app.database.session import create_session

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@router.get("/live")
def live() -> dict:
    """Process liveness: no dependency checks."""
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict:
    """Readiness: fail closed when the primary database is unavailable."""
    session = create_session()
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Datenbank nicht bereit.") from exc
    finally:
        session.close()
    return {
        "status": "ready",
        "environment": settings.app_env,
        "database": "ok",
    }
