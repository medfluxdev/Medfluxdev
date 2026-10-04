"""WP1.2 / WP1.3 API coverage in the pytest-isolated schema (same pattern as test_contract_department_roles_api)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import cost_center_routes, organization_structure
from app.database.models import Account, AccountMembership
from app.database.models.organization import Organization
from app.database.models.organization_structure import CostCenter, Department, Hospital
from app.database.session import create_session


def _seed():
    organization_id, hospital_a, hospital_b = uuid4(), uuid4(), uuid4()
    radio_id, ct_id, foreign_id, account_id, center_id = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    slug = f"wp1-api-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=organization_id, name="WP1 Test Organization", slug=slug))
        session.add_all([
            Hospital(id=hospital_a, organization_id=organization_id, name="Krankenhaus Heidelberg", code="HD"),
            Hospital(id=hospital_b, organization_id=organization_id, name="Krankenhaus B", code="B"),
        ])
        session.flush()
        session.add_all([
            Department(id=radio_id, organization_id=organization_id, hospital_id=hospital_a, name="Radiologie", code="RAD", unit_type="abteilung"),
            Department(id=ct_id, organization_id=organization_id, hospital_id=hospital_a, parent_id=radio_id, name="CT", code="CT"),
            Department(id=foreign_id, organization_id=organization_id, hospital_id=hospital_b, name="Fremd", code="FRM"),
        ])
        session.flush()
        session.add(CostCenter(id=center_id, organization_id=organization_id, hospital_id=hospital_a, department_id=radio_id, code="471100", name="Radiologie"))
        session.add(Account(id=account_id, login_name=f"{slug}@example.invalid", display_name="WP1 Admin", credential_digest="test-only-digest"))
        session.flush()
        session.add(AccountMembership(organization_id=organization_id, account_id=account_id, hospital_id=hospital_a, department_id=radio_id, role="admin"))
        session.commit()
    finally:
        session.close()
    actor = SimpleNamespace(organization_id=organization_id, account_id=account_id, role="admin", is_developer=False, display_name="WP1 Admin")
    return slug, actor, dict(hospital_a=hospital_a, radio=radio_id, ct=ct_id, foreign=foreign_id, center=center_id)


def _client(actor, monkeypatch):
    monkeypatch.setattr(cost_center_routes, "current_actor", lambda request, organization_slug: actor)
    monkeypatch.setattr(organization_structure, "current_actor", lambda request, organization_slug: actor)
    app = FastAPI()
    app.include_router(cost_center_routes.router)
    app.include_router(organization_structure.router)
    return TestClient(app)


def test_cost_center_patch_edit_reassign_reject_foreign_and_deactivate(monkeypatch):
    slug, actor, ids = _seed()
    client = _client(actor, monkeypatch)
    query = {"organization_slug": slug}
    base = f"/api/cost-centers/{ids['center']}"

    edited = client.patch(base, params=query, json={"name": "Radiologie (gesamt)", "department_id": str(ids["ct"])})
    assert edited.status_code == 200, edited.text
    assert edited.json()["name"] == "Radiologie (gesamt)" and edited.json()["department_id"] == str(ids["ct"])

    foreign = client.patch(base, params=query, json={"department_id": str(ids["foreign"])})
    assert foreign.status_code == 422

    blank = client.patch(base, params=query, json={"name": "   "})
    assert blank.status_code == 422

    off = client.patch(base, params=query, json={"is_active": False})
    assert off.status_code == 200 and off.json()["is_active"] is False

    missing = client.patch(f"/api/cost-centers/{uuid4()}", params=query, json={"name": "x"})
    assert missing.status_code == 404

    session = create_session()
    try:
        row = session.get(CostCenter, ids["center"])
        assert row.is_active is False and row.department_id == ids["ct"]
    finally:
        session.close()


def test_structure_search_by_cost_center_number_and_unit_type_roundtrip(monkeypatch):
    slug, actor, ids = _seed()
    client = _client(actor, monkeypatch)
    query = {"organization_slug": slug}

    found = client.get("/api/organization-structure/search", params={**query, "q": "471100"})
    assert found.status_code == 200, found.text
    items = found.json()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "cost_center"
    assert items[0]["hospital_name"] == "Krankenhaus Heidelberg"
    assert items[0]["path_label"] == "Radiologie"

    nested = client.get("/api/organization-structure/search", params={**query, "q": "ct"})
    dept = next(i for i in nested.json()["items"] if i["kind"] == "department" and i["code"] == "CT")
    assert dept["path_label"] == "Radiologie › CT"

    structure = client.get("/api/organization-structure", params=query).json()
    radio = next(d for d in structure["departments"] if d["id"] == str(ids["radio"]))
    assert radio["unit_type"] == "abteilung"
    assert "klinik" in structure["unit_types"]

    updated = client.patch(f"/api/organization-structure/departments/{ids['ct']}", params=query, json={"unit_type": "Funktionsbereich"})
    assert updated.status_code == 200 and updated.json()["unit_type"] == "funktionsbereich"

    invalid = client.patch(f"/api/organization-structure/departments/{ids['ct']}", params=query, json={"unit_type": "kiosk"})
    assert invalid.status_code == 422

    created = client.post("/api/organization-structure/departments", params=query,
                          json={"hospital_id": str(ids["hospital_a"]), "parent_id": str(ids["radio"]), "name": "MRT", "code": "MRT", "unit_type": "einheit"})
    assert created.status_code == 200 and created.json()["unit_type"] == "einheit"
