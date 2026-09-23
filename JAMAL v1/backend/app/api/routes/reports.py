"""Portfolio reporting built from canonical backend state."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.core.scope_context import current_scope_context
from app.database.models import Contract, WorkItem
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/portfolio")
def portfolio_report(organization_slug: str):
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        scope = current_scope_context()
        allowed = scoped_contract_ids(session, org.id, scope.hospital_id, scope.department_id)

        contract_filter = [Contract.organization_id == org.id, Contract.lifecycle_state == "active"]
        if allowed is not None:
            contract_filter.append(Contract.id.in_(allowed))

        total = session.scalar(select(func.count()).select_from(Contract).where(*contract_filter)) or 0
        archived = session.scalar(
            select(func.count()).select_from(Contract).where(*contract_filter, Contract.is_archived.is_(True))
        ) or 0
        active = session.scalar(
            select(func.count()).select_from(Contract).where(*contract_filter, Contract.is_archived.is_(False))
        ) or 0
        risk_rows = session.execute(
            select(Contract.risk_level, func.count()).where(*contract_filter).group_by(Contract.risk_level)
        ).all()

        work_filter = [WorkItem.organization_id == org.id, WorkItem.active.is_(True)]
        if allowed is not None:
            work_filter.append(WorkItem.contract_id.in_(allowed))
        work_rows = session.execute(
            select(WorkItem.status, func.count()).where(*work_filter).group_by(WorkItem.status)
        ).all()
        severity_rows = session.execute(
            select(WorkItem.severity, func.count()).where(*work_filter).group_by(WorkItem.severity)
        ).all()

        return {
            "contracts": {
                "total": total,
                "active": active,
                "archived": archived,
                "by_risk": {str(key or "unknown"): count for key, count in risk_rows},
            },
            "work_queue": {
                "by_status": {str(key): count for key, count in work_rows},
                "by_severity": {str(key): count for key, count in severity_rows},
            },
            "scope": {
                "hospital_id": str(scope.hospital_id) if scope.hospital_id else None,
                "department_id": str(scope.department_id) if scope.department_id else None,
            },
        }
    finally:
        session.close()
