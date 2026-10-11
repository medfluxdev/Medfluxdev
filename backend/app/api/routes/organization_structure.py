from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.organization_structure.placement import child_issues, placement_issue, rules_payload
from app.auth.dependencies import current_actor
from app.core.scope_context import current_scope_context
from app.database.models.activity_log import ActivityLog
from app.database.models.organization import Organization
from app.database.models.contract import Contract
from app.database.models.organization_structure import DEPARTMENT_UNIT_TYPES, ContractDepartment, CostCenter, Department, Hospital
from app.organization_structure.search import search_structure
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
    parent_id: UUID | None = None
    hospital_id: UUID
    name: str
    code: str
    unit_type: str | None = None
    # Optional: Nummer der Kostenstelle dieser Abteilung (neu anlegen oder bestehende verknüpfen).
    cost_center_code: str | None = None


class DepartmentUpdate(BaseModel):
    parent_id: UUID | None = None
    name: str | None = None
    code: str | None = None
    unit_type: str | None = None
    is_active: bool | None = None
    # Leer = Verknüpfung zur bisherigen Kostenstelle lösen (die Kostenstelle selbst bleibt).
    cost_center_code: str | None = None


def _attach_cost_center(session, *, organization_id: UUID, department: "Department", code: str | None) -> dict | None:
    """Kostenstelle zur Abteilung: bestehende Nummer verknüpfen (gleiches Krankenhaus, noch frei) oder neu anlegen.

    Leere Nummer: nichts tun. Eine Nummer, die schon einer anderen Abteilung gehört, wird abgelehnt.
    """
    value = (code or "").strip()
    if not value:
        return None
    center = session.scalars(select(CostCenter).where(CostCenter.organization_id == organization_id, CostCenter.code == value)).first()
    if center is None:
        center = CostCenter(organization_id=organization_id, hospital_id=department.hospital_id, department_id=department.id,
                            code=value, name=department.name, is_active=True)
        session.add(center)
        session.flush()
        return {"id": str(center.id), "code": center.code, "created": True}
    if center.hospital_id != department.hospital_id:
        raise HTTPException(status_code=422, detail=f"Kostenstelle {value} gehört zu einem anderen Krankenhaus.")
    if center.department_id is not None and center.department_id != department.id:
        owner = session.get(Department, center.department_id)
        raise HTTPException(status_code=409, detail=f"Kostenstelle {value} ist bereits der Abteilung „{owner.name if owner else 'unbekannt'}“ zugeordnet.")
    center.department_id = department.id
    center.is_active = True
    return {"id": str(center.id), "code": center.code, "created": False}


def _normalize_unit_type(value: str | None) -> str | None:
    """Lower-case German unit label or None; anything else is a 422 (never guessed)."""
    if value is None:
        return None
    cleaned = value.strip().casefold()
    if not cleaned:
        return None
    if cleaned not in DEPARTMENT_UNIT_TYPES:
        raise HTTPException(status_code=422, detail="Ungültiger Einheitentyp. Erlaubt: " + ", ".join(DEPARTMENT_UNIT_TYPES) + ".")
    return cleaned


def _validate_department_parent(session, *, organization_id: UUID, hospital_id: UUID, department_id: UUID | None, parent_id: UUID | None):
    """Validate same-scope parent and prevent cycles before any mutation."""
    if parent_id is None:
        return
    seen = set()
    cursor = parent_id
    for _ in range(1000):
        if cursor in seen or cursor == department_id:
            raise HTTPException(status_code=422, detail="Abteilungs-Hierarchie enthält einen Zyklus.")
        seen.add(cursor)
        parent = session.get(Department, cursor)
        if parent is None or parent.organization_id != organization_id or parent.hospital_id != hospital_id:
            raise HTTPException(status_code=422, detail="Übergeordnete Abteilung muss zum selben Krankenhaus gehören.")
        cursor = parent.parent_id
        if cursor is None:
            return
    raise HTTPException(status_code=422, detail="Abteilungs-Hierarchie ist zu tief.")


def _validate_placement(session, *, unit_type: str | None, parent_id: UUID | None, department_id: UUID | None = None) -> None:
    """Typ-Regeln der Struktur (organization_structure/placement.py); Verstoß = 422 mit Regeltext."""
    parent = session.get(Department, parent_id) if parent_id else None
    issue = placement_issue(unit_type, parent_id is not None, parent.unit_type if parent else None)
    if issue:
        raise HTTPException(status_code=422, detail=f"{issue} Bitte eine passende übergeordnete Einheit wählen.")
    if department_id is not None:
        children = session.execute(
            select(Department.name, Department.unit_type).where(Department.parent_id == department_id)
        ).all()
        broken = child_issues(unit_type, children)
        if broken:
            raise HTTPException(
                status_code=422,
                detail="Mit diesem Typ passen untergeordnete Einheiten nicht mehr: " + ", ".join(broken[:5]) + (" …" if len(broken) > 5 else "") + ".",
            )


def _hospital_code_taken(session, organization_id: UUID, code: str, exclude: UUID | None = None) -> None:
    stmt = select(Hospital.id).where(Hospital.organization_id == organization_id, func.upper(Hospital.code) == code.upper())
    if exclude is not None:
        stmt = stmt.where(Hospital.id != exclude)
    if session.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail="Dieses Kürzel ist bereits einem Krankenhaus zugeordnet.")


def _department_code_taken(session, hospital_id: UUID, code: str, exclude: UUID | None = None) -> None:
    stmt = select(Department.id).where(Department.hospital_id == hospital_id, func.upper(Department.code) == code.upper())
    if exclude is not None:
        stmt = stmt.where(Department.id != exclude)
    if session.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail="Dieses Kürzel gibt es in diesem Krankenhaus bereits.")


def _required(value: str, label: str) -> str:
    text = value.strip()
    if not text:
        raise HTTPException(status_code=422, detail=f"{label} ist erforderlich.")
    return text


def _organization(session, organization_slug: str):
    organization = session.scalar(select(Organization).where(Organization.slug == organization_slug))
    if organization is None:
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    return organization


def _admin(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    if actor.role != "admin" and not actor.is_developer:
        raise HTTPException(status_code=403, detail="Nur Administratoren dürfen die Organisationsstruktur ändern.")
    return actor


def _record_activity(session, actor, *, event_name: str, object_type: str, object_id: UUID, hospital_id: UUID | None = None, department_id: UUID | None = None, context_data: dict | None = None) -> None:
    session.add(ActivityLog(
        organization_id=actor.organization_id,
        hospital_id=hospital_id,
        department_id=department_id,
        account_id=actor.account_id,
        display_name_snapshot=actor.display_name,
        role_snapshot="developer" if getattr(actor, "is_developer", False) else actor.role,
        event_name=event_name,
        object_type=object_type,
        object_id=object_id,
        context_data=context_data,
    ))


@router.get("")
def structure(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        if organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")

        hospital_stmt = select(Hospital).where(Hospital.organization_id == organization.id)
        department_stmt = select(Department).where(Department.organization_id == organization.id)
        if actor.role != "admin" and not actor.is_developer:
            scope = current_scope_context()
            if scope.hospital_id is None:
                # Should not happen for provisioned non-admin accounts; fail closed.
                return {"hospitals": [], "departments": []}
            hospital_stmt = hospital_stmt.where(Hospital.id == scope.hospital_id)
            department_stmt = department_stmt.where(Department.hospital_id == scope.hospital_id)
            if scope.department_id is not None:
                department_stmt = department_stmt.where(Department.id == scope.department_id)

        hospitals = session.scalars(hospital_stmt.order_by(Hospital.name.asc())).all()
        departments = session.scalars(department_stmt.order_by(Department.name.asc())).all()
        types = {row.id: row.unit_type for row in session.scalars(select(Department).where(Department.organization_id == organization.id)).all()}

        def issue(row):
            return placement_issue(row.unit_type, row.parent_id is not None, types.get(row.parent_id) if row.parent_id else None)

        return {
            "hospitals": [{"id": str(row.id), "name": row.name, "code": row.code, "address": row.address, "is_active": row.is_active} for row in hospitals],
            "departments": [{"id": str(row.id), "hospital_id": str(row.hospital_id), "parent_id": str(row.parent_id) if row.parent_id else None, "name": row.name, "code": row.code, "unit_type": row.unit_type, "is_active": row.is_active, "placement_issue": issue(row)} for row in departments],
            "unit_types": list(DEPARTMENT_UNIT_TYPES),
            "placement_rules": rules_payload(),
        }
    finally:
        session.close()


@router.post("/hospitals")
def add_hospital(payload: HospitalCreate, request: Request, organization_slug: str):
    actor = _admin(request, organization_slug)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        if organization.id != actor.organization_id:
            raise HTTPException(status_code=403, detail="Kein Zugriff auf diese Organisation.")
        name, code = _required(payload.name, "Name"), _required(payload.code, "Kürzel").upper()
        _hospital_code_taken(session, organization.id, code)
        row = Hospital(organization_id=organization.id, name=name, code=code, address=(payload.address or "").strip() or None, is_active=True)
        session.add(row)
        session.flush()
        _record_activity(session, actor, event_name="hospital.created", object_type="hospital", object_id=row.id, hospital_id=row.id, context_data={"name": row.name, "code": row.code})
        session.commit()
        return {"id": str(row.id), "name": row.name, "code": row.code}
    finally:
        session.close()


@router.patch("/hospitals/{hospital_id}")
def update_hospital(hospital_id: UUID, payload: HospitalUpdate, request: Request, organization_slug: str):
    actor = _admin(request, organization_slug)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        row = session.get(Hospital, hospital_id)
        if row is None or row.organization_id != organization.id or organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Krankenhaus nicht gefunden.")
        if payload.name is not None: row.name = payload.name.strip() or row.name
        if payload.code is not None and payload.code.strip():
            _hospital_code_taken(session, organization.id, payload.code.strip(), row.id)
            row.code = payload.code.strip().upper()
        if payload.address is not None: row.address = payload.address.strip() or None
        if payload.is_active is not None: row.is_active = payload.is_active
        _record_activity(session, actor, event_name="hospital.updated", object_type="hospital", object_id=row.id, hospital_id=row.id, context_data={"name": row.name, "code": row.code, "is_active": row.is_active})
        session.commit()
        return {"id": str(row.id), "name": row.name, "code": row.code, "address": row.address, "is_active": row.is_active}
    finally:
        session.close()


@router.post("/departments")
def add_department(payload: DepartmentCreate, request: Request, organization_slug: str):
    actor = _admin(request, organization_slug)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        hospital = session.get(Hospital, payload.hospital_id)
        if hospital is None or hospital.organization_id != organization.id or organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Krankenhaus nicht gefunden.")
        _validate_department_parent(session, organization_id=organization.id, hospital_id=hospital.id, department_id=None, parent_id=payload.parent_id)
        name, code = _required(payload.name, "Name"), _required(payload.code, "Kürzel").upper()
        _department_code_taken(session, hospital.id, code)
        unit_type = _normalize_unit_type(payload.unit_type)
        _validate_placement(session, unit_type=unit_type, parent_id=payload.parent_id)
        row = Department(organization_id=organization.id, hospital_id=hospital.id, parent_id=payload.parent_id, name=name, code=code, unit_type=unit_type, is_active=True)
        session.add(row)
        session.flush()
        center = _attach_cost_center(session, organization_id=organization.id, department=row, code=payload.cost_center_code)
        _record_activity(session, actor, event_name="department.created", object_type="department", object_id=row.id, hospital_id=row.hospital_id, department_id=row.id, context_data={"name": row.name, "code": row.code, "unit_type": row.unit_type, "cost_center": center})
        session.commit()
        return {"id": str(row.id), "hospital_id": str(row.hospital_id), "name": row.name, "code": row.code, "unit_type": row.unit_type, "cost_center": center}
    finally:
        session.close()


def _active_contract_link_count(session, *, organization_id: UUID, department_id: UUID) -> int:
    """Live (not deleted, not archived) contracts linked to the department."""
    return int(session.scalar(
        select(func.count(func.distinct(ContractDepartment.contract_id)))
        .join(Contract, Contract.id == ContractDepartment.contract_id)
        .where(
            ContractDepartment.organization_id == organization_id,
            ContractDepartment.department_id == department_id,
            Contract.organization_id == organization_id,
            Contract.deleted_at.is_(None),
            Contract.is_archived.is_(False),
        )
    ) or 0)


@router.patch("/departments/{department_id}")
def update_department(department_id: UUID, payload: DepartmentUpdate, request: Request, organization_slug: str):
    actor = _admin(request, organization_slug)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        row = session.get(Department, department_id)
        if row is None or row.organization_id != organization.id or organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Abteilung nicht gefunden.")
        if "parent_id" in payload.model_fields_set:
            # Serialize all hierarchy reparenting within one hospital. The lock is
            # transaction-scoped and released by commit/rollback; it MUST precede
            # the fresh validation reads. Hash collisions only over-serialize.
            session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtext("medflux.department.tree"),
                        func.hashtext(str(row.hospital_id)),
                    )
                )
            )
            # Discard any ORM state loaded before waiting for another writer.
            session.expire_all()
            row = session.get(Department, department_id)
            if row is None or row.organization_id != organization.id or organization.id != actor.organization_id:
                raise HTTPException(status_code=404, detail="Abteilung nicht gefunden.")
            _validate_department_parent(session, organization_id=organization.id, hospital_id=row.hospital_id, department_id=row.id, parent_id=payload.parent_id)
            row.parent_id = payload.parent_id
        if payload.name is not None: row.name = payload.name.strip() or row.name
        if payload.code is not None and payload.code.strip():
            _department_code_taken(session, row.hospital_id, payload.code.strip(), row.id)
            row.code = payload.code.strip().upper()
        if "unit_type" in payload.model_fields_set: row.unit_type = _normalize_unit_type(payload.unit_type)
        if {"unit_type", "parent_id"} & payload.model_fields_set:
            # Nur geänderte Einordnungen werden geprüft; bestehende Abweichungen bleiben und werden markiert.
            _validate_placement(session, unit_type=row.unit_type, parent_id=row.parent_id,
                                department_id=row.id if "unit_type" in payload.model_fields_set else None)
        if payload.is_active is False and row.is_active:
            linked = _active_contract_link_count(session, organization_id=organization.id, department_id=row.id)
            if linked:
                # WP1.7: a unit that still owns/benefits from live contracts must
                # not silently disappear from scope selection; reassign first.
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Abteilung ist noch mit {linked} aktiven Vertrag/Verträgen verknüpft. "
                        "Bitte die Verträge zuerst einer anderen Einheit zuordnen."
                    ),
                )
        if payload.is_active is not None: row.is_active = payload.is_active
        center = None
        if "cost_center_code" in payload.model_fields_set:
            wanted = (payload.cost_center_code or "").strip()
            linked = session.scalars(select(CostCenter).where(CostCenter.department_id == row.id)).all()
            # Genau eine bisherige Kostenstelle wird durch die neue ersetzt (Verknüpfung gelöst, Kostenstelle bleibt).
            if len(linked) == 1 and linked[0].code != wanted:
                linked[0].department_id = None
            center = _attach_cost_center(session, organization_id=organization.id, department=row, code=wanted)
        _record_activity(session, actor, event_name="department.updated", object_type="department", object_id=row.id, hospital_id=row.hospital_id, department_id=row.id, context_data={"name": row.name, "code": row.code, "is_active": row.is_active})
        session.commit()
        return {"id": str(row.id), "hospital_id": str(row.hospital_id), "name": row.name, "code": row.code, "unit_type": row.unit_type, "is_active": row.is_active}
    finally:
        session.close()


@router.get("/search")
def search(request: Request, organization_slug: str, q: str = Query("", max_length=120)):
    """WP1.3: find units and cost centers by name or code; every hit carries its full path and hospital."""
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        organization = _organization(session, organization_slug)
        if organization.id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        hospital_stmt = select(Hospital).where(Hospital.organization_id == organization.id)
        department_stmt = select(Department).where(Department.organization_id == organization.id)
        cost_center_stmt = select(CostCenter).where(CostCenter.organization_id == organization.id)
        if actor.role != "admin" and not actor.is_developer:
            scope = current_scope_context()
            if scope.hospital_id is None:
                return {"query": q, "items": []}
            hospital_stmt = hospital_stmt.where(Hospital.id == scope.hospital_id)
            department_stmt = department_stmt.where(Department.hospital_id == scope.hospital_id)
            cost_center_stmt = cost_center_stmt.where(CostCenter.hospital_id == scope.hospital_id)
        hits = search_structure(
            q,
            hospitals=session.scalars(hospital_stmt).all(),
            departments=session.scalars(department_stmt).all(),
            cost_centers=session.scalars(cost_center_stmt).all(),
        )
        return {"query": q, "items": [hit.as_dict() for hit in hits]}
    finally:
        session.close()
