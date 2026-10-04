"""U5: Einrichtungs-Checkliste fuer Administratoren."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import admin_setup
from app.database.models import Account, AccountMembership
from app.database.models.organization import Organization
from app.database.models.organization_structure import Department, Hospital
from app.database.session import create_session


def test_setup_status_lists_open_and_done_items(monkeypatch):
    org, admin = uuid4(), uuid4()
    session = create_session()
    try:
        session.add(Organization(id=org, name="Setup", slug=f"setup-{org.hex[:8]}"))
        session.add(Account(id=admin, login_name=f"a-{org.hex[:6]}@x.invalid", display_name="Admin", credential_digest="t"))
        session.flush()
        session.add(AccountMembership(organization_id=org, account_id=admin, role="admin"))
        hospital = Hospital(organization_id=org, name="Nord", code="N")
        session.add(hospital)
        session.flush()
        session.add(Department(organization_id=org, hospital_id=hospital.id, name="Radiologie", code="RAD"))
        session.commit()
    finally:
        session.close()

    actor = SimpleNamespace(organization_id=org, account_id=admin, role="admin", is_developer=False, display_name="Admin")
    monkeypatch.setattr(admin_setup, "current_actor", lambda request, organization_slug: actor)
    app = FastAPI()
    app.include_router(admin_setup.router)
    client = TestClient(app)
    data = client.get("/api/admin/setup-status", params={"organization_slug": "x"}).json()
    by_key = {item["key"]: item for item in data["items"]}
    assert by_key["organization"]["status"] == "ok"
    assert by_key["users"]["status"] == "todo"
    assert by_key["mail"]["status"] == "optional"
    assert by_key["daily_job"]["detail"] == "noch nie gelaufen"
    assert data["required_open"] >= 1

    viewer = SimpleNamespace(organization_id=org, account_id=admin, role="viewer", is_developer=False, display_name="V")
    monkeypatch.setattr(admin_setup, "current_actor", lambda request, organization_slug: viewer)
    assert client.get("/api/admin/setup-status", params={"organization_slug": "x"}).status_code == 403
