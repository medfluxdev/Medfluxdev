"""Restructure Phase C: Glocke zählt, was sie öffnet; "Nur meine" = Postfach-Definition."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from app.api.routes import notifications as notification_routes
from app.core.scope_context import ScopeContext
from app.database.models import Contract
from app.database.models.deadlines import ContractDeadline, Notification
from app.database.session import create_session
from tests.test_deadlines_api import _client, _contract, _seed


def _notify(ids, contract_id, count, read=0):
    session = create_session()
    try:
        for index in range(count):
            note = Notification(
                organization_id=ids["org"], account_id=ids["manager"], kind="deadline_reminder",
                title=f"Erinnerung {index}", contract_id=UUID(contract_id), dedupe_key=f"test-{contract_id}-{index}",
            )
            session.add(note)
            session.flush()
            if index < read:
                from datetime import datetime, timezone
                note.read_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()


def test_bell_summary_matches_lists_and_read_all(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, "manager", "contract_manager")
    monkeypatch.setattr(notification_routes, "current_scope_context", lambda: ScopeContext())
    contract_id = _contract(client, slug, ids)
    _notify(ids, contract_id, 3, read=1)

    summary = client.get("/api/inbox/summary", params=query).json()
    inbox = client.get("/api/inbox", params={**query, "unread_only": True}).json()
    assert summary["unread_for_me"] == 2 == inbox["unread_count"] == inbox["total"] == len(inbox["notifications"])
    assert isinstance(summary["work_queue_open"], int)

    paged = client.get("/api/inbox", params={**query, "limit": 1, "offset": 1}).json()
    assert paged["total"] == 3 and len(paged["notifications"]) == 1 and paged["offset"] == 1

    assert client.post("/api/inbox/read-all", params=query).json()["marked"] == 2
    assert client.get("/api/inbox/summary", params=query).json()["unread_for_me"] == 0


def test_mine_filter_matches_inbox_definition(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, "manager", "contract_manager")
    contract_id = _contract(client, slug, ids)
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id))
        contract.responsible_account_id = ids["manager"]
        session.add(ContractDeadline(
            organization_id=ids["org"], contract_id=contract.id, source="manual", kind="follow_up", title="Ohne Zuweisung",
            due_date=date.today() - timedelta(days=2), remind_on=date.today() - timedelta(days=9), status="open",
            assignee_account_id=None,
        ))
        session.commit()
    finally:
        session.close()

    mine = {item["title"] for item in client.get("/api/deadlines", params={**query, "mine": True}).json()["items"]}
    inbox = {item["title"] for item in client.get("/api/inbox", params=query).json()["deadlines"]}
    assert "Ohne Zuweisung" in mine
    assert mine == inbox

    other = _client(monkeypatch, ids, "deputy", "contract_manager")
    assert "Ohne Zuweisung" not in {item["title"] for item in other.get("/api/deadlines", params={**query, "mine": True}).json()["items"]}
