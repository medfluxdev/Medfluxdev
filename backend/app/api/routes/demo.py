"""Demo-/UAT-Arbeitsbereich – globaler Diagnosemodus.

Der Modus beeinflusst die sichtbare Vertragsmenge installationsweit und ist
therefore ausschließlich ein Developer-/UAT-Werkzeug.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core.config import settings
from app.demo.workspace import set_workspace_enabled, workspace_status
from app.database.session import create_session

router = APIRouter(prefix="/api/demo", tags=["demo"])


class WorkspaceResponse(BaseModel):
    enabled: bool
    contract_ids: list[str] = []
    contract_count: int = 0


class WorkspaceToggleResponse(BaseModel):
    enabled: bool


def _require_developer(request: Request) -> None:
    # development/test können bewusst ohne Auth laufen. In diesem lokalen Modus
    # gibt es keine Developer-Identität, deshalb bleibt das UAT-Werkzeug für den
    # lokalen Operator erreichbar. Mit aktivierter Authentifizierung gilt strikt
    # Developer-only.
    if not settings.auth_enabled:
        return
    if getattr(request.state, "is_developer", False):
        return
    raise HTTPException(
        status_code=403,
        detail="Der Demo-Arbeitsbereich ist ausschließlich für den Developer verfügbar.",
    )


@router.get("/workspace", response_model=WorkspaceResponse)
def get_workspace_status(request: Request) -> WorkspaceResponse:
    _require_developer(request)
    session = create_session()
    try:
        return WorkspaceResponse(**workspace_status(session))
    finally:
        session.close()


@router.post("/workspace/enable", response_model=WorkspaceToggleResponse)
def enable_workspace(request: Request) -> WorkspaceToggleResponse:
    _require_developer(request)
    session = create_session()
    try:
        set_workspace_enabled(session, enabled=True)
        session.commit()
        return WorkspaceToggleResponse(enabled=True)
    finally:
        session.close()


@router.post("/workspace/disable", response_model=WorkspaceToggleResponse)
def disable_workspace(request: Request) -> WorkspaceToggleResponse:
    _require_developer(request)
    session = create_session()
    try:
        set_workspace_enabled(session, enabled=False)
        session.commit()
        return WorkspaceToggleResponse(enabled=False)
    finally:
        session.close()
