"""A2 focused additive contract-department role invariants.

Runtime API and PostgreSQL concurrency/ACL testing is mandatory in OpenCode.
"""
from uuid import uuid4

import pytest
from sqlalchemy.schema import CheckConstraint, Index
from app.api.routes.ownership import ContractDepartmentRolesUpdate
from app.database.models.organization_structure import ContractDepartment
from app.ownership.service import OwnershipError, validate_classified_department_links


def test_role_payload_accepts_one_responsible_and_multiple_beneficiaries():
    responsible, beneficiary = uuid4(), uuid4()
    value = ContractDepartmentRolesUpdate(
        responsible_department_id=responsible,
        beneficiary_department_ids=[beneficiary],
    )
    assert value.responsible_department_id == responsible
    assert value.beneficiary_department_ids == [beneficiary]


def test_role_payload_defaults_to_no_beneficiaries():
    value = ContractDepartmentRolesUpdate(responsible_department_id=uuid4())
    assert value.beneficiary_department_ids == []


def test_historic_link_role_is_nullable_and_constraint_exists():
    column = ContractDepartment.__table__.c.relation_role
    assert column.nullable is True
    assert any(
        isinstance(item, CheckConstraint) and item.name == "ck_contract_department_ck_contract_department_relation_role"
        for item in ContractDepartment.__table__.constraints
    )
    assert any(
        isinstance(item, Index) and item.name == "uq_contract_department_one_responsible"
        and item.unique
        for item in ContractDepartment.__table__.indexes
    )


def test_metadata_update_may_keep_classified_department_links_unchanged():
    hospital_id, responsible_id, beneficiary_id = uuid4(), uuid4(), uuid4()
    links = [
        ContractDepartment(department_id=responsible_id, relation_role="responsible"),
        ContractDepartment(department_id=beneficiary_id, relation_role="beneficiary"),
    ]

    assert validate_classified_department_links(
        links, [responsible_id, beneficiary_id], hospital_id, hospital_id,
    ) is True


@pytest.mark.parametrize(
    ("department_ids", "hospital_id"),
    [([], "same"), (["new", "beneficiary"], "same"), (["responsible", "beneficiary"], "other")],
)
def test_metadata_update_cannot_overwrite_classified_department_links(department_ids, hospital_id):
    links = [
        ContractDepartment(department_id="responsible", relation_role="responsible"),
        ContractDepartment(department_id="beneficiary", relation_role="beneficiary"),
    ]

    with pytest.raises(OwnershipError):
        validate_classified_department_links(links, department_ids, hospital_id, "same")
