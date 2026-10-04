"""WP1.7: a department linked to live contracts cannot be deactivated."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import organization_structure
from app.database.models.contract import Contract
from app.database.models.organization import Organization
from app.database.models.organization_structure import ContractDepartment, Department, Hospital
from app.database.session import create_session


def _seed(*, archived: bool = False):
    org_id, hospital_id, linked_id, free_id, contract_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    slug = f"wp17-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=org_id, name="WP1.7 Org", slug=slug))
        session.add(Hospital(id=hospital_id, organization_id=org_id, name="Krankenhaus", code="KH"))
        session.flush()
        session.add_all([
            Department(id=linked_id, organization_id=org_id, hospital_id=hospital_id, name="Radiologie", code="RAD"),
            Department(id=free_id, organization_id=org_id, hospital_id=hospital_id, name="Leer", code="LEER"),
        ])
        session.flush()
        session.add(Contract(id=contract_id, organization_id=org_id, hospital_id=hospital_id,
                             scope_type="hospital", contract_number="WP17-1", supplier="Synthetic",
                             is_archived=archived))
        session.flush()
        session.add(ContractDepartment(organization_id=org_id, contract_id=contract_id,
                                       department_id=linked_id, relation_role="responsible"))
        session.commit()
    finally:
        session.close()
    actor = SimpleNamespace(organization_id=org_id, account_id=uuid4(), role="admin",
                            is_developer=False, display_name="Admin")
    return slug, actor, linked_id, free_id


def _client(actor, monkeypatch):
    monkeypatch.setattr(organization_structure, "current_actor", lambda request, organization_slug: actor)
    monkeypatch.setattr(organization_structure, "_record_activity", lambda *a, **k: None)
    app = FastAPI()
    app.include_router(organization_structure.router)
    return TestClient(app)


def test_department_with_live_contract_cannot_be_deactivated(monkeypatch):
    slug, actor, linked_id, free_id = _seed()
    client = _client(actor, monkeypatch)
    query = {"organization_slug": slug}

    blocked = client.patch(f"/api/organization-structure/departments/{linked_id}", params=query, json={"is_active": False})
    assert blocked.status_code == 409, blocked.text
    assert "1 aktiven" in blocked.json()["detail"]

    renamed = client.patch(f"/api/organization-structure/departments/{linked_id}", params=query, json={"name": "Radiologie II"})
    assert renamed.status_code == 200 and renamed.json()["is_active"] is True

    free = client.patch(f"/api/organization-structure/departments/{free_id}", params=query, json={"is_active": False})
    assert free.status_code == 200 and free.json()["is_active"] is False

    session = create_session()
    try:
        assert session.get(Department, linked_id).is_active is True
    finally:
        session.close()


def test_archived_contract_does_not_block_deactivation(monkeypatch):
    slug, actor, linked_id, _ = _seed(archived=True)
    client = _client(actor, monkeypatch)
    response = client.patch(f"/api/organization-structure/departments/{linked_id}",
                            params={"organization_slug": slug}, json={"is_active": False})
    assert response.status_code == 200 and response.json()["is_active"] is False
