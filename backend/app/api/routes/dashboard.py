"""Dashboard-Uebersichts-Route (STEP 12)."""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.dashboard.models import DashboardOverview
from app.dashboard.service import DashboardError, build_dashboard_overview
from app.database.scope_queries import intersect_ids, scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session
from app.demo.workspace import workspace_contract_ids

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def dashboard_overview(
    organization_slug: str,
    as_of_date: Optional[date] = None,
    hospital_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
) -> DashboardOverview:
    today: date = as_of_date or date.today()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        scope_ids = scoped_contract_ids(session, org.id, hospital_id, department_id)
        visible_ids = intersect_ids(workspace_contract_ids(session), scope_ids)
        try:
            data = build_dashboard_overview(
                session,
                organization_id=org.id,
                as_of_date=today,
                workspace_contract_ids=visible_ids,
            )
        except DashboardError as exc:
            raise HTTPException(status_code=500, detail=exc.detail_de)
        return DashboardOverview.model_validate(data)
    finally:
        session.close()
