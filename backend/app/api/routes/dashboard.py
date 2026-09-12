"""Dashboard-Uebersichts-Route (STEP 12).

Duenne READ-Schicht -> `app.dashboard.service`. Organisation wird server-seitig
ueber `organization_slug` aufgeloest und alle Abfragen sind org-gebunden
(Isolation). Kein Zugriff auf Vertraege anderer Organisationen.
`as_of_date` wird hier an der API-Grenze aufgeloest (explizit) und nach unten
gereicht – kein verstecktes date.today() in der Fachlogik.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.dashboard.models import DashboardOverview
from app.dashboard.service import DashboardError, build_dashboard_overview
from app.database.models import Organization
from app.database.services import get_organization
from app.database.session import create_session
from app.demo.workspace import workspace_contract_ids

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(
    organization_slug: str,
    as_of_date: Optional[date] = None,
) -> DashboardOverview:
    today: date = as_of_date or date.today()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        try:
            data = build_dashboard_overview(
                session,
                organization_id=org.id,
                as_of_date=today,
                workspace_contract_ids=workspace_contract_ids(session),
            )
        except DashboardError as exc:
            raise HTTPException(status_code=500, detail=exc.detail_de)
        return DashboardOverview.model_validate(data)
    finally:
        session.close()
