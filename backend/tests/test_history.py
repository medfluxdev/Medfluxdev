"""H6.2 Historie: Vertragshistorie, organisationsweites Protokoll, Filter, Export, Sichtbarkeit."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import contract_register, history as history_routes
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import Account, AccountMembership
from app.database.models.organization import Organization
from app.database.session import create_session
from app.history.service import event_category, event_label, history_csv


def test_labels_and_categories():
    assert event_label("contract.status_changed") == "Status geändert"
    assert event_label("custom.thing_done") == "custom: thing done"
    assert event_category("finance.entry_created") == "finance"
    assert event_category("hospital.updated") == "organisation"
    assert event_category("whatever.x") == "other"


def test_csv_is_excel_safe():
    csv = history_csv([{
        "at": "2026-10-04T10:00:00+00:00", "actor": "=HYPERLINK(\"x\")", "role": "admin", "category": "contract",
        "label": "Stammdaten geändert", "contract_number": "000001", "contract_title": "MRT",
        "details": {"fields": {"short_description": {"before": "a", "after": "b"}}},
    }])
    assert csv.startswith("﻿Zeitpunkt;Benutzer")
    assert "'=HYPERLINK" in csv
    assert "short_description: before: a; after: b" in csv


def _seed():
    ids = {key: uuid4() for key in ("org", "admin", "manager", "other", "viewer")}
    slug = f"hist-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Historie Test", slug=slug))
        for key in ("admin", "manager", "other", "viewer"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@x.invalid", display_name=key.title(), credential_digest="t"))
        session.flush()
        for key, role in (("admin", "admin"), ("manager", "contract_manager"), ("other", "contract_manager"), ("viewer", "viewer")):
            session.add(AccountMembership(organization_id=ids["org"], account_id=ids[key], role=role))
        session.commit()
    finally:
        session.close()
    return slug, ids


def _as(monkeypatch, ids, key, role):
    actor = SimpleNamespace(
        organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title(),
    )
    for module in (contract_register, history_routes):
        monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
        monkeypatch.setattr(module, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    app.include_router(contract_register.router)
    app.include_router(history_routes.router)
    return TestClient(app)


def test_contract_history_and_organization_log(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    manager = _as(monkeypatch, ids, "manager", "contract_manager")
    cid = manager.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung CT"}}).json()["contract_id"]
    manager.patch(f"/api/contracts/{cid}/register", params=query, json={"changes": {"internal_number": "INT-1"}})
    manager.post(f"/api/contracts/{cid}/remarks", params=query, json={"body": "Angebot angefragt"})

    history = manager.get(f"/api/contracts/{cid}/history", params=query)
    assert history.status_code == 200, history.text
    labels = [item["label"] for item in history.json()["items"]]
    assert labels[:3] == ["Notiz hinzugefügt", "Stammdaten geändert", "Vertrag angelegt"]
    assert history.json()["items"][1]["actor"] == "Manager"

    admin = _as(monkeypatch, ids, "admin", "admin")
    admin.put(f"/api/contracts/{cid}/confidentiality", params=query, json={"is_confidential": True})

    log = admin.get("/api/history", params={**query, "category": "contract"}).json()
    contract_events = [item["event"] for item in admin.get(f"/api/contracts/{cid}/history", params=query).json()["items"]]
    assert log["total"] == len(contract_events)
    assert log["items"][0]["label"] == "Vertraulichkeit geändert"
    assert log["items"][0]["contract_number"] is not None
    assert {actor["display_name"] for actor in log["actors"]} == {"Admin", "Manager"}

    by_user = admin.get("/api/history", params={**query, "account_id": str(ids["admin"])}).json()
    assert by_user["total"] == 1
    assert admin.get("/api/history", params={**query, "date_from": "2000-01-01", "date_to": "2000-01-02"}).json()["total"] == 0
    assert admin.get("/api/history", params={**query, "category": "nope"}).status_code == 422

    exported = admin.get("/api/history/export", params={**query, "contract_id": cid})
    assert exported.status_code == 200
    assert exported.text.count("\r\n") == len(contract_events) + 1
    assert admin.get("/api/history", params={**query, "category": "other"}).json()["items"][0]["event"] == "history.exported"

    other = _as(monkeypatch, ids, "other", "contract_manager")
    assert other.get(f"/api/contracts/{cid}/history", params=query).status_code == 404
    assert other.get("/api/history", params={**query, "category": "contract"}).json()["total"] == 0

    viewer = _as(monkeypatch, ids, "viewer", "viewer")
    assert viewer.get("/api/history", params=query).status_code == 403
    assert viewer.get(f"/api/contracts/{cid}/history", params=query).status_code == 403
