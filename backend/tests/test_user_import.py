"""Massenimport von Benutzern mit Erstpasswort durch den Administrator."""

from __future__ import annotations

import secrets
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import users
from app.auth.credential_store import verify_password as verify_account_password
from app.auth.service import Actor
from app.database.models import Account, AccountMembership
from app.database.models.activity_log import ActivityLog
from app.database.models.organization import Organization
from app.database.models.organization_structure import Department, Hospital
from app.database.session import create_session


def _pw() -> str:
    return secrets.token_urlsafe(12)


def _setup(monkeypatch, role: str = "admin"):
    org, admin = uuid4(), uuid4()
    session = create_session()
    try:
        session.add(Organization(id=org, name="Import", slug=f"imp-{org.hex[:8]}"))
        session.add(Account(id=admin, login_name=f"admin-{org.hex[:6]}@x.invalid", display_name="Admin", credential_digest="t"))
        session.flush()
        session.add(AccountMembership(organization_id=org, account_id=admin, role=role))
        north = Hospital(organization_id=org, name="Klinikum Nord", code="KN")
        south = Hospital(organization_id=org, name="Klinikum Süd", code="KS")
        session.add_all([north, south])
        session.flush()
        session.add(Department(organization_id=org, hospital_id=north.id, name="Radiologie", code="RAD"))
        session.commit()
    finally:
        session.close()
    actor = Actor(account_id=admin, login_name="admin", display_name="Admin", organization_id=org, organization_slug="imp", role=role)
    monkeypatch.setattr(users, "current_actor", lambda request, organization_slug: actor)
    app = FastAPI()
    app.include_router(users.router)
    return TestClient(app), org


def _post(client, rows, dry_run):
    return client.post("/api/users/import", params={"organization_slug": "imp"}, json={"rows": rows, "dry_run": dry_run})


def test_preview_then_import_with_admin_given_passwords(monkeypatch):
    client, org = _setup(monkeypatch)
    tag = org.hex[:6]
    first, second = _pw(), _pw()
    rows = [
        {"email": f"Anna.{tag}@Klinik.invalid", "display_name": "Anna Berg", "role": "Vertragsmanager", "hospital": "kn", "department": "Radiologie", "password": first},
        {"email": f"ben.{tag}@klinik.invalid", "display_name": "Ben Kurz", "role": "", "hospital": "Klinikum Süd", "department": "", "password": second},
    ]

    preview = _post(client, rows, True).json()
    assert preview["valid"] is True and preview["created"] == 0
    assert preview["rows"][0] == {"line": 1, "email": f"anna.{tag}@klinik.invalid", "display_name": "Anna Berg", "role": "contract_manager",
                                  "hospital": "Klinikum Nord", "department": "Radiologie", "errors": []}
    assert preview["rows"][1]["role"] == "viewer"
    assert first not in str(preview) and second not in str(preview)

    session = create_session()
    try:
        assert session.scalar(select(Account).where(Account.login_name == f"anna.{tag}@klinik.invalid")) is None
    finally:
        session.close()

    result = _post(client, rows, False).json()
    assert result["valid"] is True and result["created"] == 2
    session = create_session()
    try:
        anna = session.scalar(select(Account).where(Account.login_name == f"anna.{tag}@klinik.invalid"))
        assert verify_account_password(first, anna.credential_digest)
        membership = session.scalar(select(AccountMembership).where(AccountMembership.account_id == anna.id))
        assert membership.organization_id == org and membership.role == "contract_manager" and membership.department_id is not None
        events = list(session.scalars(select(ActivityLog.event_name).where(ActivityLog.organization_id == org)))
        assert events.count("account.created") == 2 and "account.bulk_imported" in events
        contexts = " ".join(str(item) for item in session.scalars(select(ActivityLog.context_data).where(ActivityLog.organization_id == org)))
        assert first not in contexts and second not in contexts
    finally:
        session.close()


def test_any_error_blocks_the_whole_import(monkeypatch):
    client, org = _setup(monkeypatch)
    tag = org.hex[:6]
    good = _pw()
    rows = [
        {"email": f"ok.{tag}@x.invalid", "display_name": "Ok", "role": "Leser", "hospital": "KN", "password": good},
        {"email": f"ok.{tag}@x.invalid", "display_name": "Doppelt", "role": "Leser", "hospital": "KN", "password": _pw()},
        {"email": f"kurz.{tag}@x.invalid", "display_name": "Kurz", "role": "Chef", "hospital": "Klinikum West", "department": "Labor", "password": "kurz"},
        {"email": f"nohosp.{tag}@x.invalid", "display_name": "Ohne", "role": "Prüfer", "password": _pw()},
        {"email": "", "display_name": "", "role": "admin", "department": "Radiologie", "password": ""},
    ]
    result = _post(client, rows, False).json()
    assert result["valid"] is False and result["created"] == 0
    errors = {item["line"]: " ".join(item["errors"]) for item in result["rows"]}
    assert errors[1] == ""
    assert "Doppelt in der Liste (auch Zeile 1)" in errors[2]
    assert "Unbekannte Rolle „Chef“" in errors[3] and "Klinikum West" in errors[3] and "kürzer als 10" in errors[3]
    assert "Krankenhaus fehlt" in errors[4]
    assert "E-Mail" in errors[5] and "Name fehlt" in errors[5] and "Ein Bereich braucht ein Krankenhaus" in errors[5] and "Erstpasswort fehlt" in errors[5]
    session = create_session()
    try:
        assert session.scalar(select(Account).where(Account.login_name == f"ok.{tag}@x.invalid")) is None
    finally:
        session.close()


def test_existing_account_and_non_admin_are_rejected(monkeypatch):
    client, org = _setup(monkeypatch)
    tag = org.hex[:6]
    rows = [{"email": f"admin-{tag}@x.invalid", "display_name": "Schon da", "role": "admin", "password": _pw()}]
    result = _post(client, rows, True).json()
    assert "bereits einen Benutzer" in result["rows"][0]["errors"][0]
    assert _post(client, [], True).json()["errors"] == ["Die Liste enthält keine Benutzer."]

    client, _ = _setup(monkeypatch, role="contract_manager")
    assert _post(client, rows, True).status_code == 403
