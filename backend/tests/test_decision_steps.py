"""Umsetzung einer Entscheidung: Schritte je Entscheidung, automatisch erkannt oder abgehakt."""

from __future__ import annotations

from datetime import date

from app.reports.decision_steps import StepFacts, decision_steps, next_step
from tests.test_lifecycle_decision_edit import _client, _events
from tests.test_renewal_brief import _setup


def facts(**overrides) -> StepFacts:
    values = dict(
        decision="renew", decided_on=date(2026, 8, 15), baseline_end=date(2026, 12, 31), term_model="fixed_term",
        business_status="gueltig", cancel_by=date(2026, 9, 30), current_end=date(2026, 12, 31), partner="MEDTEC",
    )
    values.update(overrides)
    return StepFacts(**values)


def keys(steps):
    return [(step["key"], step["done"]) for step in steps]


def test_renew_steps_are_detected_from_maintained_data():
    steps = decision_steps(facts())
    assert keys(steps) == [("agree", False), ("term", False), ("prices", False), ("document", False)]
    assert steps[0]["title"] == "Verlängerung mit MEDTEC vereinbaren" and steps[0]["due"] == "2026-09-30"
    assert steps[1]["target"] == {"tab": "register", "section": "term"}
    done = decision_steps(facts(current_end=date(2027, 12, 31), priced_after_baseline=True, documents_since=("nachtrag",)))
    assert all(step["done"] and step["done_how"] == "auto" for step in done)
    assert next_step(done) is None


def test_auto_renewal_needs_no_termination_and_no_document():
    steps = decision_steps(facts(term_model="auto_renewal"))
    assert [step["key"] for step in steps] == ["no_termination", "term", "prices"]


def test_terminate_steps_and_manual_ticks():
    steps = decision_steps(facts(decision="terminate", manual={"followup": {"by": "Ahmad", "at": "2026-08-20T10:00:00+00:00"}}))
    assert keys(steps) == [("send", False), ("status", False), ("confirmation", False), ("followup", True)]
    assert steps[3]["done_how"] == "manual" and steps[3]["done_by"] == "Ahmad"
    assert next_step(steps)["key"] == "send"
    after = decision_steps(facts(decision="terminate", business_status="gekuendigt", documents_since=("kuendigungsbestaetigung",)))
    assert keys(after)[:3] == [("send", True), ("status", True), ("confirmation", True)]


def test_monitor_and_renegotiate_point_back_to_the_decision():
    monitor = decision_steps(facts(decision="monitor"))
    assert monitor[0]["target"] == {"action": "change_decision"} and not monitor[0]["done"]
    assert decision_steps(facts(decision="monitor", reminder_due=date(2026, 11, 1)))[0]["done"] is True
    renegotiate = decision_steps(facts(decision="renegotiate", entries_changed_since=True))
    assert keys(renegotiate) == [("talk", True), ("terms", True), ("document", False), ("result", False)]
    assert renegotiate[0]["due"] == "2026-08-31"


def test_steps_api_ticks_audits_and_sets_in_progress(monkeypatch):
    slug, ids, _ = _setup(monkeypatch)
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, slug)
    cid = client.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung CT"}}).json()["contract_id"]
    created = client.post(f"/api/lifecycle/contracts/{cid}", params=query, json={"decision": "terminate"}).json()
    assert [step["key"] for step in created["steps"]] == ["send", "status", "confirmation", "followup"]

    ticked = client.post(f"/api/lifecycle/contracts/{cid}/{created['id']}/steps/send", params=query, json={"done": True})
    assert ticked.status_code == 200, ticked.text
    body = ticked.json()
    assert body["status"] == "in_progress"
    send = next(step for step in body["steps"] if step["key"] == "send")
    assert send["done"] and send["done_how"] == "manual" and send["done_by"] == "Admin"
    listed = client.get(f"/api/lifecycle/contracts/{cid}", params=query).json()["items"][0]
    assert next(step for step in listed["steps"] if step["key"] == "send")["done"] is True

    undone = client.post(f"/api/lifecycle/contracts/{cid}/{created['id']}/steps/send", params=query, json={"done": False}).json()
    assert next(step for step in undone["steps"] if step["key"] == "send")["done"] is False
    assert client.post(f"/api/lifecycle/contracts/{cid}/{created['id']}/steps/agree", params=query, json={"done": True}).status_code == 404
    names = [event.event_name for event in _events(cid)]
    assert "contract.lifecycle_step_done" in names and "contract.lifecycle_step_undone" in names

    client.patch(f"/api/lifecycle/contracts/{cid}/{created['id']}", params=query, json={"status": "completed"})
    assert client.post(f"/api/lifecycle/contracts/{cid}/{created['id']}/steps/send", params=query, json={"done": True}).status_code == 409


def test_viewer_may_not_tick_steps(monkeypatch):
    slug, ids, _ = _setup(monkeypatch)
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, slug)
    cid = client.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung MRT"}}).json()["contract_id"]
    created = client.post(f"/api/lifecycle/contracts/{cid}", params=query, json={"decision": "renew"}).json()
    viewer = _client(monkeypatch, ids, slug, role="viewer")
    assert viewer.post(f"/api/lifecycle/contracts/{cid}/{created['id']}/steps/agree", params=query, json={"done": True}).status_code == 403


def _add_entry(cid: str, org_id, valid_from: str, valid_to: str | None) -> None:
    from datetime import date as _date
    from decimal import Decimal
    from uuid import UUID

    from app.database.models.finance import ContractFinanceEntry
    from app.database.session import create_session

    session = create_session()
    try:
        session.add(ContractFinanceEntry(
            organization_id=org_id, contract_id=UUID(cid), direction="expense", label="Wartung", amount=Decimal("8000"),
            amount_basis="net", vat_rate=Decimal("19"), currency="EUR", interval="annual",
            valid_from=_date.fromisoformat(valid_from), valid_to=_date.fromisoformat(valid_to) if valid_to else None, origin="manual",
        ))
        session.commit()
    finally:
        session.close()


def test_old_entries_do_not_tick_prices_only_new_ones_do(monkeypatch):
    slug, ids, _ = _setup(monkeypatch)
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids, slug)
    cid = client.post("/api/contracts", params=query, json={"values": {
        "short_description": "Wartung CT", "term_model": "fixed_term", "term_start_date": "2025-01-01", "term_fixed_end_date": "2026-12-31",
    }}).json()["contract_id"]
    # Alte Preisstaffel reicht schon über das Vertragsende hinaus – das ist keine neue Bepreisung.
    _add_entry(cid, ids["org"], "2027-01-01", "2029-12-31")
    created = client.post(f"/api/lifecycle/contracts/{cid}", params=query, json={"decision": "renew"}).json()
    prices = next(step for step in created["steps"] if step["key"] == "prices")
    assert prices["done"] is False

    _add_entry(cid, ids["org"], "2027-01-01", "2027-12-31")
    listed = client.get(f"/api/lifecycle/contracts/{cid}", params=query).json()["items"][0]
    prices = next(step for step in listed["steps"] if step["key"] == "prices")
    assert prices["done"] is True and prices["done_how"] == "auto"
