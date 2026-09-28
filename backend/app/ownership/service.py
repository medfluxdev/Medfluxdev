from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models import Contract, ContractDepartment, Department, Equipment, Hospital
from app.database.models.organization_structure import CostCenter


class OwnershipError(ValueError):
    pass


def _hospital(session: Session, organization_id: UUID, hospital_id: UUID | None):
    if hospital_id is None:
        return None
    row = session.get(Hospital, hospital_id)
    if row is None or row.organization_id != organization_id:
        raise OwnershipError("Krankenhaus gehört nicht zu dieser Organisation.")
    return row


def _departments(session: Session, organization_id: UUID, hospital_id: UUID | None, department_ids: list[UUID]):
    rows = []
    for department_id in department_ids:
        row = session.get(Department, department_id)
        if row is None or row.organization_id != organization_id:
            raise OwnershipError("Abteilung gehört nicht zu dieser Organisation.")
        if hospital_id is not None and row.hospital_id != hospital_id:
            raise OwnershipError("Abteilung gehört nicht zum gewählten Krankenhaus.")
        rows.append(row)
    return rows


def _cost_center(session: Session, organization_id: UUID, hospital_id: UUID | None, cost_center_id: UUID | None):
    if cost_center_id is None:
        return None
    row = session.get(CostCenter, cost_center_id)
    if row is None or row.organization_id != organization_id:
        raise OwnershipError("Kostenstelle gehört nicht zu dieser Organisation.")
    if hospital_id is not None and row.hospital_id != hospital_id:
        raise OwnershipError("Kostenstelle gehört nicht zum gewählten Krankenhaus.")
    return row


def assign_contract_ownership(
    session: Session,
    *,
    contract: Contract,
    hospital_id: UUID | None,
    department_ids: list[UUID],
    cost_center_id: UUID | None,
) -> Contract:
    # Serialize against the role-specific PUT endpoint, including non-HTTP callers.
    # A pre-check in the API alone would race with a concurrent role assignment.
    session.refresh(contract, with_for_update=True)
    if session.scalar(select(ContractDepartment.id).where(
        ContractDepartment.organization_id == contract.organization_id,
        ContractDepartment.contract_id == contract.id,
        ContractDepartment.relation_role.is_not(None),
    ).limit(1)) is not None:
        raise OwnershipError("Explizite Abteilungsrollen vorhanden; alte Zuordnung darf diese nicht überschreiben.")
    hospital = _hospital(session, contract.organization_id, hospital_id)
    departments = _departments(session, contract.organization_id, hospital_id, department_ids)
    cost_center = _cost_center(session, contract.organization_id, hospital_id, cost_center_id)

    contract.hospital_id = hospital.id if hospital else None
    contract.cost_center_id = cost_center.id if cost_center else None
    if departments:
        contract.scope_type = "department"
    elif hospital:
        contract.scope_type = "hospital"
    else:
        contract.scope_type = "organization"

    session.execute(delete(ContractDepartment).where(ContractDepartment.contract_id == contract.id))
    for department in departments:
        session.add(ContractDepartment(
            organization_id=contract.organization_id,
            contract_id=contract.id,
            department_id=department.id,
        ))
    session.flush()
    return contract


def assign_equipment_ownership(
    session: Session,
    *,
    equipment: Equipment,
    hospital_id: UUID | None,
    department_id: UUID | None,
    cost_center_id: UUID | None,
) -> Equipment:
    hospital = _hospital(session, equipment.organization_id, hospital_id)
    departments = _departments(session, equipment.organization_id, hospital_id, [department_id] if department_id else [])
    cost_center = _cost_center(session, equipment.organization_id, hospital_id, cost_center_id)
    department = departments[0] if departments else None

    if cost_center is not None and department is not None and cost_center.department_id not in (None, department.id):
        raise OwnershipError("Kostenstelle gehört nicht zur gewählten Abteilung.")

    equipment.hospital_id = hospital.id if hospital else None
    equipment.department_id = department.id if department else None
    equipment.cost_center_id = cost_center.id if cost_center else None
    session.flush()
    return equipment


def contract_department_ids(session: Session, contract_id: UUID) -> list[UUID]:
    return list(session.scalars(select(ContractDepartment.department_id).where(ContractDepartment.contract_id == contract_id)).all())
