"""API integration coverage for department roles in the pytest-isolated schema."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import ownership
from app.database.models import Account, AccountMembership, Contract, ContractDepartment
from app.database.models.organization import Organization
from app.database.models.organization_structure import CostCenter, Department, Hospital
from app.database.session import create_session


def test_department_roles_roundtrip_scope_rejection_and_metadata_preservation(monkeypatch):
    organization_id = uuid4()
    hospital_a_id, hospital_b_id = uuid4(), uuid4()
    responsible_id, beneficiary_id, foreign_department_id = uuid4(), uuid4(), uuid4()
    account_id, contract_id, cost_center_id = uuid4(), uuid4(), uuid4()
    slug = f"roles-api-{uuid4().hex[:12]}"

    session = create_session()
    try:
        organization = Organization(id=organization_id, name="Synthetic Test Organization", slug=slug)
        session.add(organization)
        hospital_a = Hospital(id=hospital_a_id, organization_id=organization_id, name="Test Hospital A", code="A")
        hospital_b = Hospital(id=hospital_b_id, organization_id=organization_id, name="Test Hospital B", code="B")
        session.add_all([hospital_a, hospital_b])
        session.flush()

        responsible = Department(id=responsible_id, organization_id=organization_id, hospital_id=hospital_a_id,
                                 name="Responsible Department", code="RESP")
        beneficiary = Department(id=beneficiary_id, organization_id=organization_id, hospital_id=hospital_a_id,
                                 name="Beneficiary Department", code="BEN")
        foreign_department = Department(id=foreign_department_id, organization_id=organization_id,
                                        hospital_id=hospital_b_id, name="Foreign Department", code="FOREIGN")
        session.add_all([responsible, beneficiary, foreign_department])
        session.flush()
        center = CostCenter(id=cost_center_id, organization_id=organization_id, hospital_id=hospital_a_id,
                            department_id=responsible_id, code="TEST-4400", name="Synthetic Cost Center")
        account = Account(id=account_id, login_name=f"{slug}@example.invalid", display_name="Synthetic Test User",
                          credential_digest="test-only-digest")
        session.add_all([center, account])
        session.flush()
        session.add(AccountMembership(organization_id=organization_id, account_id=account_id,
                                      hospital_id=hospital_a_id, department_id=responsible_id, role="admin"))
        contract = Contract(id=contract_id, organization_id=organization_id, hospital_id=hospital_a_id,
                            scope_type="hospital", contract_number="SYNTHETIC-1", supplier="Synthetic Supplier")
        session.add(contract)
        session.commit()
    finally:
        session.close()

    actor = SimpleNamespace(
        organization_id=organization_id,
        account_id=account_id,
        role="admin",
        is_developer=False,
        display_name="Synthetic Test User",
    )
    monkeypatch.setattr(ownership, "current_actor", lambda request, organization_slug: actor)
    test_app = FastAPI()
    test_app.include_router(ownership.router)
    client = TestClient(test_app)
    base = f"/api/ownership/contracts/{contract_id}"
    query = {"organization_slug": slug}

    saved = client.put(
        f"{base}/department-roles",
        params=query,
        json={"responsible_department_id": str(responsible_id),
              "beneficiary_department_ids": [str(beneficiary_id)]},
    )
    assert saved.status_code == 200, saved.text

    read_back = client.get(f"{base}/department-roles", params=query)
    assert read_back.status_code == 200
    assert read_back.json()["responsible_department_id"] == str(responsible_id)
    assert read_back.json()["beneficiary_department_ids"] == [str(beneficiary_id)]

    rejected = client.put(
        f"{base}/department-roles",
        params=query,
        json={"responsible_department_id": str(responsible_id),
              "beneficiary_department_ids": [str(foreign_department_id)]},
    )
    assert rejected.status_code == 422

    metadata = client.patch(
        base,
        params=query,
        json={"hospital_id": str(hospital_a_id),
              "department_ids": [str(responsible_id), str(beneficiary_id)],
              "cost_center_id": str(cost_center_id),
              "responsible_account_id": str(account_id)},
    )
    assert metadata.status_code == 200, metadata.text
    assert metadata.json()["cost_center_id"] == str(cost_center_id)
    assert metadata.json()["responsible_account_id"] == str(account_id)

    roles_after_metadata = client.get(f"{base}/department-roles", params=query)
    assert roles_after_metadata.status_code == 200
    assert roles_after_metadata.json()["responsible_department_id"] == str(responsible_id)
    assert roles_after_metadata.json()["beneficiary_department_ids"] == [str(beneficiary_id)]

    session = create_session()
    try:
        links = session.scalars(select(ContractDepartment).where(
            ContractDepartment.contract_id == contract_id,
        )).all()
        assert {(link.department_id, link.relation_role) for link in links} == {
            (responsible_id, "responsible"),
            (beneficiary_id, "beneficiary"),
        }
    finally:
        session.close()
