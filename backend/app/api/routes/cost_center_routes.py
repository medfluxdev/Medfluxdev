from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.dependencies import current_actor
from app.core.scope_context import current_scope_context
from app.database.models import Department, Hospital, Organization
from app.database.models.activity_log import ActivityLog
from app.database.models.organization_structure import CostCenter
from app.database.session import create_session

router = APIRouter(prefix="/api/cost-centers", tags=["cost-centers"])


class CostCenterPayload(BaseModel):
    hospital_id: UUID
    department_id: UUID | None = None
    code: str
    name: str


def _organization(session, organization_slug: str):
    organization = session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if organization is None:
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    return organization


@router.get("")
def list_items(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        if organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        stmt = select(CostCenter).where(CostCenter.organization_id == organization.id)
        if actor.role != "admin" and not actor.is_developer:
            scope = current_scope_context()
            if scope.hospital_id is None:
                return {"items": []}
            stmt = stmt.where(CostCenter.hospital_id == scope.hospital_id)
            if scope.department_id is not None:
                stmt = stmt.where(
                    (CostCenter.department_id.is_(None))
                    | (CostCenter.department_id == scope.department_id)
                )
        rows = session.scalars(stmt.order_by(CostCenter.code.asc())).all()
        return {
            "items": [
                {
                    "id": str(row.id),
                    "hospital_id": str(row.hospital_id),
                    "department_id": str(row.department_id) if row.department_id else None,
                    "code": row.code,
                    "name": row.name,
                    "is_active": row.is_active,
                }
                for row in rows
            ]
        }
    finally:
        session.close()


@router.post("")
def add_item(payload: CostCenterPayload, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    if actor.role != "admin" and not actor.is_developer:
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen Kostenstellen anlegen.")
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        if organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        hospital = session.get(Hospital, payload.hospital_id)
        if hospital is None or hospital.organization_id != organization.id:
            raise HTTPException(status_code=422, detail="Ungültiges Krankenhaus.")
        department = session.get(Department, payload.department_id) if payload.department_id else None
        if department is not None and department.hospital_id != hospital.id:
            raise HTTPException(status_code=422, detail="Die Abteilung gehört nicht zum Krankenhaus.")
        code = payload.code.strip().upper()
        name = payload.name.strip()
        if not code or not name:
            raise HTTPException(status_code=422, detail="Code und Bezeichnung sind erforderlich.")
        row = CostCenter(
            organization_id=organization.id,
            hospital_id=hospital.id,
            department_id=department.id if department else None,
            code=code,
            name=name,
            is_active=True,
        )
        session.add(row)
        session.flush()
        session.add(
            ActivityLog(
                organization_id=actor.organization_id,
                hospital_id=row.hospital_id,
                department_id=row.department_id,
                account_id=actor.account_id,
                display_name_snapshot=actor.display_name,
                role_snapshot="developer" if actor.is_developer else actor.role,
                event_name="cost_center.created",
                object_type="cost_center",
                object_id=row.id,
                context_data={"code": row.code, "name": row.name},
            )
        )
        session.commit()
        return {"id": str(row.id), "code": row.code, "name": row.name}
    finally:
        session.close()
