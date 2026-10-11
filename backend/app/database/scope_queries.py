from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.models.contract import Contract
from app.database.models.organization_structure import ContractDepartment, Department
from app.auth.runtime import current_identity
from app.database.models.register import CatalogContractType, ContractAccessGrant, ContractHospital


def hidden_confidential_ids(session: Session, organization_id: UUID) -> set[UUID]:
    """H8.2: Vertrauliche Vertraege, die die aktuelle Identitaet nicht sehen darf.

    Sichtbar fuer Administration/Entwicklung, die verantwortliche Person und
    explizit freigegebene Konten. Ohne bekannte Identitaet bleibt alles
    Vertrauliche verborgen (fail-closed).
    """
    identity = current_identity()
    if identity is not None and (getattr(identity, "is_developer", False) or getattr(identity, "role", None) == "admin"):
        return set()
    confidential_types = select(CatalogContractType.id).where(
        CatalogContractType.organization_id == organization_id, CatalogContractType.is_confidential.is_(True)
    )
    rows = session.execute(
        select(Contract.id, Contract.responsible_account_id).where(
            Contract.organization_id == organization_id,
            or_(Contract.is_confidential.is_(True), Contract.contract_type_id.in_(confidential_types)),
        )
    ).all()
    if not rows:
        return set()
    account_id = getattr(identity, "account_id", None) if identity is not None else None
    if account_id is None:
        return {contract_id for contract_id, _ in rows}
    granted = set(session.scalars(
        select(ContractAccessGrant.contract_id).where(
            ContractAccessGrant.account_id == account_id,
            ContractAccessGrant.contract_id.in_([contract_id for contract_id, _ in rows]),
        )
    ).all())
    from app.database.models import ContractResponsible

    further = set(session.scalars(
        select(ContractResponsible.contract_id).where(
            ContractResponsible.account_id == account_id,
            ContractResponsible.contract_id.in_([contract_id for contract_id, _ in rows]),
        )
    ).all())
    return {
        contract_id for contract_id, responsible in rows
        if responsible != account_id and contract_id not in granted and contract_id not in further
    }


def scoped_contract_ids(
    session: Session,
    organization_id: UUID,
    hospital_id: UUID | None,
    department_id: UUID | None,
) -> set[UUID] | None:
    """Sichtbare Vertrags-IDs (None = keine Einschraenkung)."""
    visible = _scope_ids(session, organization_id, hospital_id, department_id)
    hidden = hidden_confidential_ids(session, organization_id)
    if not hidden:
        return visible
    if visible is None:
        visible = set(session.scalars(select(Contract.id).where(Contract.organization_id == organization_id)).all())
    return visible - hidden


def _scope_ids(
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
