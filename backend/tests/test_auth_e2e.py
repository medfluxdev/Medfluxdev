"""DB-backed end-to-end coverage for STEP 16 local auth boundaries.

These tests deliberately exercise the real FastAPI middleware/routes against the
pytest-isolated PostgreSQL schema from ``backend/conftest.py``. They must never
run with ``MEDFLUX_UNIT_ONLY=1`` because persistence is part of the contract
being verified here.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.auth.service import record_audit_event
from app.core.config import settings
from app.database.models.auth import User
from app.database.models.organization import Organization
from app.database.session import create_session
from app.main import app


@pytest.fixture()
def auth_fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Create two organizations and representative roles in the isolated DB."""

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(
        settings,
        "app_secret_key",
        "medflux-test-only-secret-9d914a9a4d8e4a1ca0bdb3cf2b99a4ae",
    )
    monkeypatch.setattr(settings, "auth_cookie_secure", False)

    suffix = uuid.uuid4().hex[:10]
    org_slug = f"auth-e2e-{suffix}"
    other_org_slug = f"auth-e2e-other-{suffix}"
    password = "Correct-Horse-Battery-42"

    session = create_session()
    try:
        org = Organization(name="Auth E2E Hospital", slug=org_slug)
        other_org = Organization(name="Other Auth E2E Hospital", slug=other_org_slug)
        session.add_all([org, other_org])
        session.flush()

        reviewer = User(
            organization_id=org.id,
            username="reviewer",
            display_name="Review Person",
            password_hash=hash_password(password),
            role="reviewer",
            active=True,
        )
        viewer = User(
            organization_id=org.id,
            username="viewer",
            display_name="View Person",
            password_hash=hash_password(password),
            role="viewer",
            active=True,
        )
        admin = User(
            organization_id=org.id,
            username="admin",
            display_name="Admin Person",
            password_hash=hash_password(password),
            role="admin",
            active=True,
        )
        other_admin = User(
            organization_id=other_org.id,
            username="other-admin",
            display_name="Other Admin",
            password_hash=hash_password(password),
            role="admin",
            active=True,
        )
        session.add_all([reviewer, viewer, admin, other_admin])
        session.flush()

        record_audit_event(
            session,
            organization_id=other_org.id,
            user_id=other_admin.id,
            action="other-org.private-event",
            entity_type="organization",
            entity_id=str(other_org.id),
        )
        session.commit()
    finally:
        session.close()

    return {
        "org_slug": org_slug,
        "other_org_slug": other_org_slug,
        "password": password,
    }


def _login(client: TestClient, *, org_slug: str, username: str, password: str):
    return client.post(
        "/api/auth/login",
        json={
            "organization_slug": org_slug,
            "username": username,
            "password": password,
        },
    )


def test_login_me_audit_logout_roundtrip(auth_fixture: dict[str, str]) -> None:
    with TestClient(app) as client:
        unauthenticated = client.get("/api/auth/me")
        assert unauthenticated.status_code == 401

        login = _login(
            client,
            org_slug=auth_fixture["org_slug"],
            username="reviewer",
            password=auth_fixture["password"],
        )
        assert login.status_code == 200
        assert login.json() == {"ok": True}
        assert settings.auth_cookie_name in client.cookies

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        body = me.json()
        assert body["email"] == "reviewer"
        assert body["display_name"] == "Review Person"
        assert body["is_active"] is True
        assert body["memberships"][0]["organization_slug"] == auth_fixture["org_slug"]
        assert body["memberships"][0]["role"] == "reviewer"

        audit = client.get("/api/audit")
        assert audit.status_code == 200
        actions = [event["action"] for event in audit.json()]
        assert "auth.login" in actions
        assert "other-org.private-event" not in actions

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        assert logout.json() == {"ok": True}

        after_logout = client.get("/api/auth/me")
        assert after_logout.status_code == 401


def test_cross_org_query_is_hidden(auth_fixture: dict[str, str]) -> None:
    with TestClient(app) as client:
        login = _login(
            client,
            org_slug=auth_fixture["org_slug"],
            username="reviewer",
            password=auth_fixture["password"],
        )
        assert login.status_code == 200

        response = client.get(
            "/api/operations/contracts.csv",
            params={"organization_slug": auth_fixture["other_org_slug"]},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Ressource nicht gefunden."


def test_write_permissions_follow_integrated_role_policy(auth_fixture: dict[str, str]) -> None:
    with TestClient(app) as viewer_client:
        login = _login(
            viewer_client,
            org_slug=auth_fixture["org_slug"],
            username="viewer",
            password=auth_fixture["password"],
        )
        assert login.status_code == 200
        blocked = viewer_client.post(
            "/api/documents/import",
            params={"organization_slug": auth_fixture["org_slug"]},
        )
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == "Keine Berechtigung fuer diese Aktion."

    with TestClient(app) as reviewer_client:
        login = _login(
            reviewer_client,
            org_slug=auth_fixture["org_slug"],
            username="reviewer",
            password=auth_fixture["password"],
        )
        assert login.status_code == 200
        blocked = reviewer_client.post(
            "/api/documents/import",
            params={"organization_slug": auth_fixture["org_slug"]},
        )
        assert blocked.status_code == 403
        assert "Berechtigung" in blocked.json()["detail"]

    with TestClient(app) as admin_client:
        login = _login(
            admin_client,
            org_slug=auth_fixture["org_slug"],
            username="admin",
            password=auth_fixture["password"],
        )
        assert login.status_code == 200
        allowed = admin_client.post(
            "/api/documents/import",
            params={"organization_slug": auth_fixture["org_slug"]},
        )
        assert allowed.status_code == 200
        payload = allowed.json()
        assert payload["total"] == 0
        assert payload["successful"] == 0
        assert payload["failed"] == 0
