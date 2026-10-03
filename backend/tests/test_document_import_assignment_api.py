"""Import assignment persistence and cross-hospital rejection in isolated pytest schema."""

from __future__ import annotations

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import documents
from app.database.models import Contract, ContractDepartment
from app.database.models.organization import Organization
from app.database.models.organization_structure import CostCenter, Department, Hospital
from app.database.session import create_session


def test_import_persists_assignment_and_rejects_foreign_hospital_department(monkeypatch):
    if os.environ.get("MEDFLUX_UNIT_ONLY") == "1":
        pytest.skip("Requires the pytest-isolated PostgreSQL schema")

    organization_id = uuid4()
    hospital_id, foreign_hospital_id = uuid4(), uuid4()
    responsible_id, beneficiary_id, foreign_department_id = uuid4(), uuid4(), uuid4()
    cost_center_id, contract_id = uuid4(), uuid4()
    slug = f"import-assignment-{uuid4().hex[:12]}"

    with create_session() as session:
        session.add(Organization(id=organization_id, name="Import Assignment Test", slug=slug))
        session.add_all([
            Hospital(id=hospital_id, organization_id=organization_id, name="Hospital A", code=f"A-{slug[-6:]}"),
            Hospital(id=foreign_hospital_id, organization_id=organization_id, name="Hospital B", code=f"B-{slug[-6:]}"),
        ])
        session.flush()
        session.add_all([
            Department(id=responsible_id, organization_id=organization_id, hospital_id=hospital_id,
                       name="Radiology", code="RAD"),
            Department(id=beneficiary_id, organization_id=organization_id, hospital_id=hospital_id,
                       name="Neurosurgery", code="NEU"),
            Department(id=foreign_department_id, organization_id=organization_id, hospital_id=foreign_hospital_id,
                       name="Foreign Department", code="FOREIGN"),
        ])
        session.flush()
        session.add_all([
            CostCenter(id=cost_center_id, organization_id=organization_id, hospital_id=hospital_id,
                       department_id=responsible_id, code=f"CC-{slug[-6:]}", name="Radiology costs"),
            Contract(id=contract_id, organization_id=organization_id, contract_number="IMPORT-TEST",
                     supplier="Synthetic Supplier", scope_type="organization"),
        ])
        session.commit()

    actor = SimpleNamespace(organization_id=organization_id, account_id=uuid4(), role="admin", is_developer=False)
    processed_files = []

    def process_upload(**kwargs):
        processed_files.append(kwargs["original_filename"])
        return SimpleNamespace(
            document_id="", document_version_id="", sha256="", original_filename="assignment.pdf",
            status="imported", contract_id=str(contract_id), analysis_status="success",
            requires_review=False, message=None,
        )

    monkeypatch.setattr(documents, "current_actor", lambda *_args: actor)
    monkeypatch.setattr(documents, "_processing_service", SimpleNamespace(process=process_upload))
    test_app = FastAPI()
    test_app.include_router(documents.router)
    client = TestClient(test_app)
    query = {"organization_slug": slug}
    files = [("files", ("assignment.pdf", b"%PDF-1.4 synthetic", "application/pdf"))]

    saved = client.post(
        "/api/documents/import", params=query, files=files,
        data={
            "assignment_hospital_id": str(hospital_id),
            "responsible_department_id": str(responsible_id),
            "beneficiary_department_ids": [str(beneficiary_id)],
            "cost_center_id": str(cost_center_id),
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["documents"][0]["contract_id"] == str(contract_id)

    with create_session() as session:
        contract = session.get(Contract, contract_id)
        assert contract is not None
        assert contract.hospital_id == hospital_id
        assert contract.cost_center_id == cost_center_id
        assert contract.scope_type == "department"
        relations = session.scalars(select(ContractDepartment).where(
            ContractDepartment.contract_id == contract_id,
        )).all()
        assert {(row.department_id, row.relation_role) for row in relations} == {
            (responsible_id, "responsible"),
            (beneficiary_id, "beneficiary"),
        }

    rejected = client.post(
        "/api/documents/import", params=query, files=files,
        data={
            "assignment_hospital_id": str(hospital_id),
            "responsible_department_id": str(responsible_id),
            "beneficiary_department_ids": [str(foreign_department_id)],
        },
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "Alle gewählten Bereiche müssen aktiv und im selben Krankenhaus sein."
    assert processed_files == ["assignment.pdf"]

    with create_session() as session:
        contract = session.get(Contract, contract_id)
        assert contract is not None and contract.hospital_id == hospital_id
        relations = session.scalars(select(ContractDepartment).where(
            ContractDepartment.contract_id == contract_id,
        )).all()
        assert {(row.department_id, row.relation_role) for row in relations} == {
            (responsible_id, "responsible"),
            (beneficiary_id, "beneficiary"),
        }
