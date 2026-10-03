"""Tests für den FastAPI-Einstiegspunkt von Medflux."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "Medflux"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    payload = r.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "Medflux"
    assert payload["version"]


def test_ready():
    r = client.get("/ready")
    assert r.status_code == 200
    payload = r.json()
    assert payload["status"] == "ready"
    assert payload["database"] == "ok"


def test_cors_allows_credentialed_frontend_requests_when_auth_is_disabled():
    r = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert r.headers["access-control-allow-credentials"] == "true"
