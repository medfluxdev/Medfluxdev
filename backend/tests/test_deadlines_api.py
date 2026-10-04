"""H5 deadlines, daily job, notifications, deputies and inbox on PostgreSQL."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import contract_register, deadlines as deadline_routes
from app.core.scope_context import ScopeContext
from app.database.models import Account, AccountMembership
from app.database.models.deadlines import AccountDeputy, ContractDeadline, Notification, NotificationOutbox
from app.database.models.organization import Organization
from app.database.session import create_session
from app.deadlines.notify import run_daily


class FakeTransport:
    sent: list = []

    def send(self, message):
        FakeTransport.sent.append(message)


class FailingTransport:
    def send(self, message):
        raise ConnectionRefusedError("smtp down")


def _seed():
    ids = {key: uuid4() for key in ("org", "manager", "boss", "deputy", "viewer")}
    slug = f"deadlines-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Fristen Test", slug=slug))
        for key in ("manager", "boss", "deputy", "viewer"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@klinik.invalid", display_name=key.title(), credential_digest="test-only"))
        session.flush()
        for key, role in (("manager", "contract_manager"), ("boss", "admin"), ("deputy", "contract_manager"), ("viewer", "viewer")):
            session.add(AccountMembership(organization_id=ids["org"], account_id=ids[key], role=role))
        session.commit()
    finally:
        session.close()
    return slug, ids


def _client(monkeypatch, ids, key, role):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())
    for module in (contract_register, deadline_routes):
        monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
        monkeypatch.setattr(module, "current_scope_context", lambda: ScopeContext())
    app = FastAPI()
    app.include_router(contract_register.router)
    app.include_router(deadline_routes.router)
    return TestClient(app)


def _contract(client, slug, ids, **extra):
    values = {
        "short_description": "Wartung MRT",
        "term_model": "terminable",
        "term_start_date": "2027-04-01",
        "notice_period_value": 3,
        "notice_period_unit": "months",
        "notice_to": "quarter_end",
        "escalation_recipient_account_id": str(ids["boss"]),
        **extra,
    }
    response = client.post("/api/contracts", params={"organization_slug": slug}, json={"values": values})
    assert response.status_code == 200, response.text
    return response.json()["contract_id"]


def test_system_deadline_follows_register_and_daily_run_notifies(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, "manager", "contract_manager")
    contract_id = _contract(client, slug, ids)

    [deadline] = client.get(f"/api/contracts/{contract_id}/deadlines", params=query).json()["items"]
    assert deadline["source"] == "system" and deadline["system_key"] == "cancel_by"
    assert (deadline["due_date"], deadline["remind_on"]) == ("2027-06-30", "2027-03-30")
    assert deadline["assignee_name"] == "Manager" and deadline["escalation_name"] == "Boss"
    assert deadline["basis_unconfirmed"] is False

    client.patch(f"/api/contracts/{contract_id}/register", params=query, json={"changes": {"notice_period_value": 6}})
    [updated] = client.get(f"/api/contracts/{contract_id}/deadlines", params=query).json()["items"]
    assert updated["id"] == deadline["id"] and (updated["due_date"], updated["remind_on"]) == ("2027-06-30", "2027-03-30")

    assert client.patch(f"/api/deadlines/{updated['id']}", params=query, json={"values": {"due_date": "2027-01-01"}}).status_code == 422
    assert client.post(f"/api/deadlines/{updated['id']}/cancel", params=query, json={}).status_code == 409
    toggled = client.patch(f"/api/deadlines/{updated['id']}", params=query, json={"values": {"send_ics": True}})
    assert toggled.status_code == 200 and toggled.json()["items"][0]["send_ics"] is True

    session = create_session()
    try:
        session.add(AccountDeputy(
            organization_id=ids["org"], account_id=ids["manager"], deputy_account_id=ids["deputy"],
            valid_from=date(2027, 3, 1), valid_to=date(2027, 4, 30),
        ))
        session.commit()
    finally:
        session.close()

    FakeTransport.sent = []
    reminder_day = date(2027, 3, 30)
    first = run_daily(as_of=reminder_day, trigger="test", transport_factory=FakeTransport, organization_id=ids["org"])
    assert first.counts["deadline_reminder"] == 2
    second = run_daily(as_of=reminder_day, trigger="test", transport_factory=FakeTransport, organization_id=ids["org"])
    assert second.counts.get("deadline_reminder", 0) == 0
    recipients = sorted(message["To"] for message in FakeTransport.sent)
    assert recipients == sorted([f"manager-{slug}@klinik.invalid", f"deputy-{slug}@klinik.invalid"])
    deputy_mail = next(m for m in FakeTransport.sent if m["To"].startswith("deputy"))
    assert "Vertretung für Manager" in deputy_mail["Subject"]
    assert any(part.get_content_type() == "text/calendar" for part in deputy_mail.iter_attachments())

    overdue = run_daily(as_of=date(2027, 7, 2), trigger="test", transport_factory=FakeTransport, organization_id=ids["org"])
    assert overdue.counts["deadline_overdue"] == 1
    assert overdue.counts["deadline_escalation"] == 1

    session = create_session()
    try:
        kinds = {
            (row.kind, row.on_behalf_of_name)
            for row in session.scalars(select(Notification).where(Notification.contract_id == UUID(contract_id))).all()
        }
        assert ("deadline_escalation", None) in kinds and ("deadline_reminder", "Manager") in kinds
        missed = session.get(ContractDeadline, UUID(updated["id"]))
        assert missed.status == "open" and missed.due_date == date(2027, 6, 30)
    finally:
        session.close()

    inbox = client.get("/api/inbox", params=query).json()
    assert inbox["unread_count"] >= 2
    assert inbox["deadlines"][0]["contract_label"].startswith("000001")
    note_id = inbox["notifications"][0]["id"]
    assert client.post(f"/api/inbox/{note_id}/read", params=query).json()["marked"] == 1
    assert client.post("/api/inbox/read-all", params=query).json()["marked"] >= 1
    assert client.get("/api/inbox", params=query).json()["unread_count"] == 0

    done = client.post(f"/api/deadlines/{updated['id']}/done", params=query, json={"note": "Verlängerung beschlossen"})
    assert done.status_code == 200
    states = {(item["system_key"], item["status"]) for item in done.json()["items"]}
    assert ("cancel_by", "done") in states


def test_failed_mail_is_retried_and_reported(monkeypatch):
    slug, ids = _seed()
    client = _client(monkeypatch, ids, "manager", "contract_manager")
    _contract(client, slug, ids, reminder_lead_months=0, term_start_date="2026-01-01", notice_to="month_end", notice_period_value=1)
    as_of = date.today() + timedelta(days=40)
    result = run_daily(as_of=as_of, trigger="test", transport_factory=FailingTransport, organization_id=ids["org"])
    assert result.counts.get("emails_failed", 0) >= 1
    session = create_session()
    try:
        row = session.scalars(select(NotificationOutbox).where(NotificationOutbox.organization_id == ids["org"])).first()
        assert row.status == "pending" and row.attempts == 1 and "smtp down" in row.last_error
    finally:
        session.close()
    FakeTransport.sent = []
    retry = run_daily(as_of=as_of, trigger="test", transport_factory=FakeTransport, organization_id=ids["org"])
    assert retry.counts.get("emails_sent", 0) >= 1


def test_manual_deadlines_preferences_deputies_and_job_status(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, "manager", "contract_manager")
    contract_id = _contract(client, slug, ids, term_model="perpetual")

    bad = client.post(f"/api/contracts/{contract_id}/deadlines", params=query,
                      json={"values": {"title": "Prüfung", "due_date": "2026-11-01", "remind_on": "2026-12-01"}})
    assert bad.status_code == 422
    created = client.post(
        f"/api/contracts/{contract_id}/deadlines", params=query,
        json={"values": {"title": "Wartungsprotokoll anfordern", "due_date": "2026-11-15", "assignee_account_id": str(ids["deputy"]), "send_ics": True}},
    )
    assert created.status_code == 200, created.text
    [manual] = [item for item in created.json()["items"] if item["source"] == "manual"]
    assert manual["assignee_name"] == "Deputy" and manual["remind_on"] == "2026-11-15"

    session = create_session()
    try:
        assigned = session.scalars(select(Notification).where(
            Notification.account_id == ids["deputy"], Notification.kind == "deadline_assigned"
        )).all()
        assert len(assigned) == 1
    finally:
        session.close()

    assert client.post(f"/api/deadlines/{manual['id']}/cancel", params=query, json={}).status_code == 200
    reopened = client.post(f"/api/deadlines/{manual['id']}/reopen", params=query, json={})
    assert reopened.json()["items"][0]["status"] == "open"
    listing = client.get("/api/deadlines", params={**query, "due_before": "2026-12-31"}).json()["items"]
    assert [item["id"] for item in listing] == [manual["id"]]

    prefs = client.put("/api/me/notification-settings", params=query,
                       json={"values": {"receives_reminders": False, "default_deputy_account_id": str(ids["deputy"])}})
    assert prefs.status_code == 200
    assert prefs.json()["receives_reminders"] is False and prefs.json()["default_deputy_name"] == "Deputy"
    assert client.put("/api/me/notification-settings", params=query,
                      json={"values": {"default_deputy_account_id": str(ids["manager"])}}).status_code == 422

    own = client.post("/api/deputies", params=query, json={
        "deputy_account_id": str(ids["deputy"]), "valid_from": "2026-12-20", "valid_to": "2027-01-06",
    })
    assert own.status_code == 200 and own.json()["items"][0]["deputy_name"] == "Deputy"
    assert client.post("/api/deputies", params=query, json={
        "account_id": str(ids["boss"]), "deputy_account_id": str(ids["deputy"]), "valid_from": "2026-12-20", "valid_to": "2027-01-06",
    }).status_code == 403
    assert client.post("/api/deputies", params=query, json={
        "deputy_account_id": str(ids["deputy"]), "valid_from": "2027-01-06", "valid_to": "2026-12-20",
    }).status_code == 422
    assert client.get("/api/jobs/daily", params=query).status_code == 403

    viewer = _client(monkeypatch, ids, "viewer", "viewer")
    assert viewer.post(f"/api/contracts/{contract_id}/deadlines", params=query, json={"values": {"title": "x", "due_date": "2026-11-01"}}).status_code == 403

    admin = _client(monkeypatch, ids, "boss", "admin")
    run = admin.post("/api/jobs/daily/run", params=query)
    assert run.status_code == 200, run.text
    status = admin.get("/api/jobs/daily", params=query).json()
    assert status["runs"][0]["scope"] == "organization" and status["runs"][0]["status"] == "succeeded"
    assert status["smtp_configured"] is False
    assert "emails_waiting_for_smtp" in status["runs"][0]["counts"]

    session = create_session()
    try:
        assert session.scalars(select(ContractDeadline).where(ContractDeadline.contract_id == UUID(contract_id))).first() is not None
    finally:
        session.close()
