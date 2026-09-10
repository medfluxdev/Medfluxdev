"""Demo-/UAT-Arbeitsbereich – API (Enable/Disable/Status).

Beispiel:
- `GET  /api/demo/workspace`    → {enabled, contract_count, ...}
- `POST /api/demo/workspace/enable`
- `POST /api/demo/workspace/disable`

Aktiv: Vertragsliste/Dashboard/Detail blenden auf den Demo-Bestand.
Inaktiv: Normales Portfolio (unverändert). Keine Bestandsveränderung.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.demo.workspace import (
    set_workspace_enabled,
    workspace_status,
)
from app.database.session import create_session

router = APIRouter(prefix="/api/demo", tags=["demo"])


class WorkspaceResponse(BaseModel):
    enabled: bool
    contract_ids: list[str] = []
    contract_count: int = 0


@router.get("/workspace", response_model=WorkspaceResponse)
def get_workspace_status() -> WorkspaceResponse:
    session = create_session()
    try:
        return WorkspaceResponse(**workspace_status(session))
    finally:
        session.close()


class WorkspaceToggleResponse(BaseModel):
    enabled: bool


@router.post("/workspace/enable", response_model=WorkspaceToggleResponse)
def enable_workspace() -> WorkspaceToggleResponse:
    session = create_session()
    try:
        set_workspace_enabled(session, enabled=True)
        session.commit()
        return WorkspaceToggleResponse(enabled=True)
    finally:
        session.close()


@router.post("/workspace/disable", response_model=WorkspaceToggleResponse)
def disable_workspace() -> WorkspaceToggleResponse:
    session = create_session()
    try:
        set_workspace_enabled(session, enabled=False)
        session.commit()
        return WorkspaceToggleResponse(enabled=False)
    finally:
        session.close()