from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.models.contract import Contract
from app.database.models.organization_structure import ContractDepartment, Department
from app.database.models.register import ContractHospital


def scoped_contract_ids(
    session: Session,
    organization_id: UUID,
    hospital_id: UUID | None,
    department_id: UUID | None,
) -> set[UUID] | None:
    if hospital_id is None and department_id is None:
        return None

    if department_id is not None:
        return set(session.scalars(
            select(ContractDepartment.contract_id).where(
                ContractDepartment.organization_id == organization_id,
                ContractDepartment.department_id == department_id,
            )
        ).all())

    department_ids = select(Department.id).where(
        Department.organization_id == organization_id,
        Department.hospital_id == hospital_id,
    )
    linked_ids = select(ContractDepartment.contract_id).where(
        ContractDepartment.organization_id == organization_id,
        ContractDepartment.department_id.in_(department_ids),
    )
    hospital_links = select(ContractHospital.contract_id).where(
        ContractHospital.organization_id == organization_id,
        ContractHospital.hospital_id == hospital_id,
    )
    return set(session.scalars(
        select(Contract.id).where(
            Contract.organization_id == organization_id,
            or_(
                Contract.hospital_id == hospital_id,
                Contract.id.in_(linked_ids),
                Contract.id.in_(hospital_links),
            ),
        )
    ).all())


def intersect_ids(left: set[UUID] | None, right: set[UUID] | None) -> set[UUID] | None:
    if left is None:
        return right
    if right is None:
        return left
    return left & right
