"""Bisherige Entscheidungen: nachtraeglich aendern und loeschen, beides protokolliert."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import contract_register, lifecycle
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models.activity_log import ActivityLog
from app.database.models.deadlines import ContractDeadline
from app.database.models.lifecycle import ContractLifecycleDecision
from app.database.session import create_session
from tests.test_renewal_brief import _setup


def _client(monkeypatch, ids, slug, role="admin"):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role=role, is_developer=False, display_name="Admin")
    monkeypatch.setattr(contract_register, "current_actor", lambda request, organization_slug: actor)
    monkeypatch.setattr(contract_register, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(lifecycle, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    monkeypatch.setattr(lifecycle.settings, "auth_enabled", True)
    app = FastAPI()

    @app.middleware("http")
    async def _actor(request, call_next):
        request.state.actor = actor
        return await call_next(request)

    app.include_router(contract_register.router)
    app.include_router(lifecycle.router)
    return TestClient(app)


def _events(contract_id: str) -> list[ActivityLog]:
    session = create_session()
    try:
        return list(session.scalars(select(ActivityLog).where(ActivityLog.object_id == UUID(contract_id)).order_by(ActivityLog.created_at)))
    finally:
        session.close()


def test_decision_can_be_changed_and_deleted_with_audit(monkeypatch):
    slug, ids, _ = _setup(monkeypatch)
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, slug)
    cid = client.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung CT"}}).json()["contract_id"]
    created = client.post(f"/api/lifecycle/contracts/{cid}", params=query, json={"decision": "monitor", "effective_date": "2026-12-31", "note": "erst beobachten"}).json()

    changed = client.patch(f"/api/lifecycle/contracts/{cid}/{created['id']}", params=query, json={
        "decision": "terminate", "status": "planned", "effective_date": "2027-03-31", "note": "doch kündigen",
    })
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert (body["decision"], body["effective_date"], body["note"]) == ("terminate", "2027-03-31", "doch kündigen")
    updated = [e for e in _events(cid) if e.event_name == "contract.lifecycle_decision_updated"]
    assert updated and updated[0].context_data["previous_decision"] == "monitor" and set(updated[0].context_data["changed"]) == {"decision", "effective_date", "note"}

    assert client.patch(f"/api/lifecycle/contracts/{cid}/{created['id']}", params=query, json={"decision": "unsinn", "status": "planned"}).status_code == 422

    deleted = client.delete(f"/api/lifecycle/contracts/{cid}/{created['id']}", params=query)
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"/api/lifecycle/contracts/{cid}", params=query).json()["items"] == []
    gone = [e for e in _events(cid) if e.event_name == "contract.lifecycle_decision_deleted"]
    assert gone and gone[0].context_data["decision"] == "terminate"
    assert client.delete(f"/api/lifecycle/contracts/{cid}/{created['id']}", params=query).status_code == 404


def test_viewer_may_not_delete(monkeypatch):
    slug, ids, _ = _setup(monkeypatch)
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, slug)
    cid = client.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung MRT"}}).json()["contract_id"]
    created = client.post(f"/api/lifecycle/contracts/{cid}", params=query, json={"decision": "renew"}).json()
    viewer = _client(monkeypatch, ids, slug, role="viewer")
    assert viewer.delete(f"/api/lifecycle/contracts/{cid}/{created['id']}", params=query).status_code == 403
    session = create_session()
    try:
        assert session.get(ContractLifecycleDecision, UUID(created["id"])) is not None
    finally:
        session.close()


def test_reminder_is_created_changed_and_cancelled_with_the_decision(monkeypatch):
    slug, ids, _ = _setup(monkeypatch)
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, slug)
    cid = client.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung Labor"}}).json()["contract_id"]
    created = client.post(f"/api/lifecycle/contracts/{cid}", params=query, json={
        "decision": "renew", "effective_date": "2027-03-31",
        "reminder": {"title": "Verlängerung umsetzen", "due_date": "2027-01-15", "kind": "pruefung"},
    })
    assert created.status_code == 200, created.text
    reminder = created.json()["reminder"]
    assert reminder["title"] == "Verlängerung umsetzen" and reminder["due_date"] == "2027-01-15" and reminder["status"] == "open"

    changed = client.patch(f"/api/lifecycle/contracts/{cid}/{created.json()['id']}", params=query, json={
        "decision": "terminate", "status": "planned", "effective_date": "2027-03-31",
        "reminder": {"title": "Kündigung versenden", "due_date": "2026-12-01"},
    }).json()
    assert changed["reminder"]["id"] == reminder["id"]
    assert (changed["reminder"]["title"], changed["reminder"]["due_date"]) == ("Kündigung versenden", "2026-12-01")
    session = create_session()
    try:
        deadline = session.get(ContractDeadline, UUID(reminder["id"]))
        assert deadline.remind_on.isoformat() == "2026-12-01"
    finally:
        session.close()

    listed = client.get(f"/api/lifecycle/contracts/{cid}", params=query).json()["items"]
    assert listed[0]["reminder"]["title"] == "Kündigung versenden"

    assert client.delete(f"/api/lifecycle/contracts/{cid}/{created.json()['id']}", params=query).status_code == 200
    session = create_session()
    try:
        assert session.get(ContractDeadline, UUID(reminder["id"])).status == "cancelled"
    finally:
        session.close()


def test_reminder_can_be_removed_or_added_later(monkeypatch):
    slug, ids, _ = _setup(monkeypatch)
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, slug)
    cid = client.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung OP"}}).json()["contract_id"]
    created = client.post(f"/api/lifecycle/contracts/{cid}", params=query, json={"decision": "monitor"}).json()
    assert created["reminder"] is None
    added = client.patch(f"/api/lifecycle/contracts/{cid}/{created['id']}", params=query, json={
        "status": "planned", "reminder": {"title": "Erneut prüfen", "due_date": "2027-02-01"},
    }).json()
    assert added["reminder"]["status"] == "open"
    removed = client.patch(f"/api/lifecycle/contracts/{cid}/{created['id']}", params=query, json={"status": "planned", "remove_reminder": True}).json()
    assert removed["reminder"] is None
    session = create_session()
    try:
        assert session.get(ContractDeadline, UUID(added["reminder"]["id"])).status == "cancelled"
    finally:
        session.close()


def test_same_reminder_is_not_created_twice(monkeypatch):
    slug, ids, _ = _setup(monkeypatch)
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, slug)
    cid = client.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung Röntgen"}}).json()["contract_id"]
    reminder = {"title": "Entscheidung erneut prüfen", "due_date": "2027-02-01"}
    first = client.post(f"/api/lifecycle/contracts/{cid}", params=query, json={"decision": "monitor", "reminder": reminder}).json()
    second = client.post(f"/api/lifecycle/contracts/{cid}", params=query, json={"decision": "monitor", "reminder": reminder}).json()
    assert first["reminder"]["id"] == second["reminder"]["id"]
    # Geteilte Erinnerung bleibt, solange eine andere Entscheidung sie nutzt.
    client.delete(f"/api/lifecycle/contracts/{cid}/{first['id']}", params=query)
    session = create_session()
    try:
        assert session.get(ContractDeadline, UUID(second["reminder"]["id"])).status == "open"
    finally:
        session.close()
