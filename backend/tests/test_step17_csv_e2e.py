"""DB-backed authenticated CSV export coverage for STEP 17.

The pytest session is isolated by ``backend/conftest.py``.  These tests exercise
the real FastAPI auth middleware and PostgreSQL-backed current-state export.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.core.config import settings
from app.database.models.auth import User
from app.database.services import create_contract, create_organization
from app.database.session import create_session
from app.main import app


@pytest.fixture()
def csv_fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(
        settings,
        "app_secret_key",
        "medflux-step17-test-only-secret-8fbf0c61a54a44ec9eab1b73c46b8b63",
    )
    monkeypatch.setattr(settings, "auth_cookie_secure", False)

    suffix = uuid.uuid4().hex[:10]
    org_slug = f"csv-e2e-{suffix}"
    other_org_slug = f"csv-e2e-other-{suffix}"
    password = "Correct-Horse-Battery-42"

    session = create_session()
    try:
        org = create_organization(session, name="CSV Hospital", slug=org_slug)
        other_org = create_organization(
            session, name="Other CSV Hospital", slug=other_org_slug
        )
        user = User(
            organization_id=org.id,
            username="admin",
            display_name="CSV Admin",
            password_hash=hash_password(password),
            role="admin",
            active=True,
        )
        session.add(user)
        session.flush()

        active = create_contract(
            session,
            organization_id=org.id,
            supplier="Alpha MedTech",
            contract_number="CSV-ACTIVE-1",
            status="active",
            risk_level="medium",
        )
        archived = create_contract(
            session,
            organization_id=org.id,
            supplier="Beta Service",
            contract_number="CSV-ARCHIVED-1",
            status="active",
            risk_level="low",
        )
        archived.is_archived = True

        other = create_contract(
            session,
            organization_id=other_org.id,
            supplier="Secret Other Org",
            contract_number="CSV-OTHER-1",
            status="active",
            risk_level="critical",
        )
        assert active.id and archived.id and other.id
        session.commit()
    finally:
        session.close()

    return {
        "org_slug": org_slug,
        "other_org_slug": other_org_slug,
        "password": password,
    }


def _login(client: TestClient, fixture: dict[str, str]) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "organization_slug": fixture["org_slug"],
            "username": "admin",
            "password": fixture["password"],
        },
    )
    assert response.status_code == 200


def test_authenticated_csv_is_org_scoped_and_safe(csv_fixture: dict[str, str]) -> None:
    with TestClient(app) as client:
        _login(client, csv_fixture)
        response = client.get(
            "/api/operations/contracts.csv",
            params={"organization_slug": csv_fixture["org_slug"]},
        )

    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "attachment;" in response.headers["content-disposition"]

    text = response.content.decode("utf-8-sig")
    lines = text.splitlines()
    assert lines[0].startswith("contract_id;supplier;contract_number;")
    assert "Alpha MedTech" in text
    assert "CSV-ACTIVE-1" in text
    assert "Beta Service" in text
    assert "CSV-ARCHIVED-1" in text
    assert "Secret Other Org" not in text
    assert "CSV-OTHER-1" not in text


def test_csv_include_archived_false_filters_archived(csv_fixture: dict[str, str]) -> None:
    with TestClient(app) as client:
        _login(client, csv_fixture)
        response = client.get(
            "/api/operations/contracts.csv",
            params={
                "organization_slug": csv_fixture["org_slug"],
                "include_archived": "false",
            },
        )

    assert response.status_code == 200
    text = response.content.decode("utf-8-sig")
    assert "CSV-ACTIVE-1" in text
    assert "CSV-ARCHIVED-1" not in text
    assert "CSV-OTHER-1" not in text


def test_csv_cross_org_slug_is_hidden(csv_fixture: dict[str, str]) -> None:
    with TestClient(app) as client:
        _login(client, csv_fixture)
        response = client.get(
            "/api/operations/contracts.csv",
            params={"organization_slug": csv_fixture["other_org_slug"]},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Ressource nicht gefunden."
