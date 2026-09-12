from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.database.models.organization import Organization
from app.database.models.organization_structure import Department, Hospital
from app.database.session import create_session

router = APIRouter(prefix="/api/organization-structure", tags=["organization-structure"])


class HospitalCreate(BaseModel):
    name: str
    code: str
    address: str | None = None


class HospitalUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    address: str | None = None
    is_active: bool | None = None


class DepartmentCreate(BaseModel):
    hospital_id: UUID
    name: str
    code: str


class DepartmentUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None


def _organization(session, organization_slug: str):
    organization = session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if organization is None:
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    return organization


def _admin(request: Request):
    actor = getattr(request.state, "actor", None)
    if actor is None or actor.role != "admin":
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen die Organisationsstruktur ändern.")
    return actor


@router.get("")
def structure(organization_slug: str):
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        hospitals = session.scalars(select(Hospital).where(Hospital.organization_id == organization.id).order_by(Hospital.name.asc())).all()
        departments = session.scalars(select(Department).where(Department.organization_id == organization.id).order_by(Department.name.asc())).all()
        return {
            "hospitals": [{"id": str(row.id), "name": row.name, "code": row.code, "address": row.address, "is_active": row.is_active} for row in hospitals],
            "departments": [{"id": str(row.id), "hospital_id": str(row.hospital_id), "name": row.name, "code": row.code, "is_active": row.is_active} for row in departments],
        }
    finally:
        session.close()


@router.post("/hospitals")
def add_hospital(payload: HospitalCreate, request: Request, organization_slug: str):
    actor = _admin(request)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        if organization.id != actor.organization_id:
            raise HTTPException(status_code=403, detail="Kein Zugriff auf diese Organisation.")
        row = Hospital(organization_id=organization.id, name=payload.name.strip(), code=payload.code.strip().upper(), address=(payload.address or "").strip() or None, is_active=True)
        session.add(row); session.commit()
        return {"id": str(row.id), "name": row.name, "code": row.code}
    finally:
        session.close()


@router.patch("/hospitals/{hospital_id}")
def update_hospital(hospital_id: UUID, payload: HospitalUpdate, request: Request, organization_slug: str):
    actor = _admin(request)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        row = session.get(Hospital, hospital_id)
        if row is None or row.organization_id != organization.id or organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Krankenhaus nicht gefunden.")
        if payload.name is not None: row.name = payload.name.strip() or row.name
        if payload.code is not None: row.code = payload.code.strip().upper() or row.code
        if payload.address is not None: row.address = payload.address.strip() or None
        if payload.is_active is not None: row.is_active = payload.is_active
        session.commit()
        return {"id": str(row.id), "name": row.name, "code": row.code, "address": row.address, "is_active": row.is_active}
    finally:
        session.close()


@router.post("/departments")
def add_department(payload: DepartmentCreate, request: Request, organization_slug: str):
    actor = _admin(request)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        hospital = session.get(Hospital, payload.hospital_id)
        if hospital is None or hospital.organization_id != organization.id or organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Krankenhaus nicht gefunden.")
        row = Department(organization_id=organization.id, hospital_id=hospital.id, name=payload.name.strip(), code=payload.code.strip().upper(), is_active=True)
        session.add(row); session.commit()
        return {"id": str(row.id), "hospital_id": str(row.hospital_id), "name": row.name, "code": row.code}
    finally:
        session.close()


@router.patch("/departments/{department_id}")
def update_department(department_id: UUID, payload: DepartmentUpdate, request: Request, organization_slug: str):
    actor = _admin(request)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        row = session.get(Department, department_id)
        if row is None or row.organization_id != organization.id or organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Abteilung nicht gefunden.")
        if payload.name is not None: row.name = payload.name.strip() or row.name
        if payload.code is not None: row.code = payload.code.strip().upper() or row.code
        if payload.is_active is not None: row.is_active = payload.is_active
        session.commit()
        return {"id": str(row.id), "hospital_id": str(row.hospital_id), "name": row.name, "code": row.code, "is_active": row.is_active}
    finally:
        session.close()
