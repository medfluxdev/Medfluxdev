"""A2 focused additive contract-department role invariants.

Runtime API and PostgreSQL concurrency/ACL testing is mandatory in OpenCode.
"""
from uuid import uuid4

import pytest
from sqlalchemy.schema import CheckConstraint, Index
from app.api.routes.ownership import ContractDepartmentRolesUpdate
from app.database.models.organization_structure import ContractDepartment


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
