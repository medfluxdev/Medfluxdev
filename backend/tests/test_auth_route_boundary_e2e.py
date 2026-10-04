"""DB-backed cross-route tenant-boundary regression coverage.

These tests verify the central signed-identity organization binding before route
logic executes. They intentionally run only in the normal PostgreSQL-isolated
suite, not the DB-free STEP 18 gate.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.security import hash_password
from app.core.config import settings
from app.database.models.auth import User
from app.database.services import create_organization
from app.database.session import create_session
from app.main import app


@pytest.fixture()
def tenant_boundary_fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(
        settings,
        "app_secret_key",
        "medflux-tenant-boundary-test-secret-2026",
    )
    monkeypatch.setattr(settings, "auth_cookie_secure", False)

    suffix = uuid.uuid4().hex[:10]
    own_slug = f"tenant-own-{suffix}"
    other_slug = f"tenant-other-{suffix}"
    password = "Correct-Horse-Battery-42"

    session = create_session()
    try:
        own = create_organization(session, name="Own Hospital", slug=own_slug)
        create_organization(session, name="Other Hospital", slug=other_slug)
        session.add(
            User(
                organization_id=own.id,
                username="reviewer",
                display_name="Tenant Reviewer",
                password_hash=hash_password(password),
                role="reviewer",
                active=True,
            )
        )
        session.commit()
    finally:
        session.close()

    return {"own": own_slug, "other": other_slug, "password": password}


def _login(client: TestClient, fixture: dict[str, str]) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "organization_slug": fixture["own"],
            "username": "reviewer",
            "password": fixture["password"],
        },
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/contracts",
        "/api/dashboard/overview",
        "/api/equipment",
        "/api/work-queue",
        "/api/intelligence/events",
        "/api/operations/contracts.csv",
    ],
)
def test_cross_org_slug_is_hidden_for_every_resource_family(
    tenant_boundary_fixture: dict[str, str], path: str
) -> None:
    with TestClient(app) as client:
        _login(client, tenant_boundary_fixture)
        response = client.get(
            path,
            params={"organization_slug": tenant_boundary_fixture["other"]},
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Ressource nicht gefunden."


def test_cross_org_opaque_document_endpoint_is_hidden_before_lookup(
    tenant_boundary_fixture: dict[str, str],
) -> None:
    fake_version = uuid.uuid4()
    with TestClient(app) as client:
        _login(client, tenant_boundary_fixture)
        response = client.get(
            f"/api/documents/{fake_version}/source-region",
            params={
                "organization_slug": tenant_boundary_fixture["other"],
                "snippet": "Vertragsnummer",
            },
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Ressource nicht gefunden."


def test_cross_org_write_is_hidden_not_authorized_by_query_slug(
    tenant_boundary_fixture: dict[str, str],
) -> None:
    fake_contract = uuid.uuid4()
    with TestClient(app) as client:
        _login(client, tenant_boundary_fixture)
        response = client.post(
            f"/api/contracts/{fake_contract}/archive",
            params={"organization_slug": tenant_boundary_fixture["other"]},
        )
    assert response.status_code == 404
    assert response.json()["detail"] == "Ressource nicht gefunden."
