from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.database.models.organization import Organization
from app.database.models.organization_structure import Department, Hospital
from app.database.session import create_session

router = APIRouter(prefix="/api/organization-structure", tags=["organization-structure"])


@router.get("")
def structure(organization_slug: str):
    session = create_session()
    try:
        organization = session.scalar(select(Organization).where(Organization.slug == organization_slug))
        if organization is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        hospitals = session.scalars(select(Hospital).where(Hospital.organization_id == organization.id).order_by(Hospital.name.asc())).all()
        departments = session.scalars(select(Department).where(Department.organization_id == organization.id).order_by(Department.name.asc())).all()
        return {
            "hospitals": [{"id": str(row.id), "name": row.name, "code": row.code, "address": row.address, "is_active": row.is_active} for row in hospitals],
            "departments": [{"id": str(row.id), "hospital_id": str(row.hospital_id), "name": row.name, "code": row.code, "is_active": row.is_active} for row in departments],
        }
    finally:
        session.close()
