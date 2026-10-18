"""Zahlungs-/Wartungserinnerungen, Zahlungszeitpunkt und Prüfmodus der Organisation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select

from app.contracts.review import service as review_service
from app.contracts.review.events import ReviewEvents
from app.deadlines.system import PaymentSchedule, next_maintenance, next_payment, payment_schedules
from app.finance.ai import payment_timing


def _schedule(**overrides) -> PaymentSchedule:
    values = dict(label="Pauschale", amount=Decimal("1200.00"), currency="EUR", interval="quarterly",
                  valid_from=date(2026, 1, 1), valid_to=None, timing="in_advance")
    values.update(overrides)
    return PaymentSchedule(**values)


# --------------------------------------------------------------------------- Zahlungstermine (rein)


def test_payment_in_advance_is_due_at_period_start():
    due, items = next_payment([_schedule()], date(2026, 10, 10), None)
    assert due == date(2027, 1, 1) and items[0].label == "Pauschale"
    assert next_payment([_schedule()], date(2026, 10, 1), None)[0] == date(2026, 10, 1)


def test_payment_in_arrears_is_due_at_period_end():
    due, _ = next_payment([_schedule(timing="in_arrears")], date(2026, 10, 10), None)
    assert due == date(2026, 12, 31)


def test_payment_skips_done_dates_and_stops_at_validity_or_contract_end():
    assert next_payment([_schedule()], date(2026, 10, 1), None, frozenset({date(2026, 10, 1)}))[0] == date(2027, 1, 1)
    assert next_payment([_schedule(valid_to=date(2026, 12, 31))], date(2026, 10, 2), None) is None
    assert next_payment([_schedule()], date(2026, 10, 2), date(2026, 12, 31)) is None
    # Nachschuessig endet die letzte Periode am Vertragsende.
    assert next_payment([_schedule(timing="in_arrears")], date(2026, 10, 2), date(2026, 11, 15))[0] == date(2026, 11, 15)


def test_payments_on_the_same_day_are_combined_and_once_is_supported():
    due, items = next_payment([_schedule(label="B"), _schedule(label="A")], date(2026, 9, 1), None)
    assert due == date(2026, 10, 1) and [item.label for item in items] == ["A", "B"]
    once = _schedule(interval="once", valid_from=date(2026, 11, 1), valid_to=date(2026, 11, 30), timing="in_arrears")
    assert next_payment([once], date(2026, 10, 10), None)[0] == date(2026, 11, 30)
    assert next_payment([once], date(2026, 12, 1), None) is None


def test_only_expenses_with_reminder_and_known_timing_become_schedules():
    def row(**overrides):
        values = dict(direction="expense", payment_reminder=True, payment_timing="in_advance", label="X",
                      amount=Decimal("1"), currency="EUR", interval="monthly", valid_from=date(2026, 1, 1), valid_to=None)
        values.update(overrides)
        return SimpleNamespace(**values)

    rows = [row(), row(payment_reminder=False), row(payment_timing=None), row(direction="income")]
    assert len(payment_schedules(rows)) == 1


# --------------------------------------------------------------------------- Wartung (rein)


def test_maintenance_uses_maintained_date_then_interval():
    as_of = date(2026, 10, 10)
    assert next_maintenance(date(2026, 11, 1), 6, as_of, None) == date(2026, 11, 1)
    # Vergangenes Datum ohne Intervall bleibt stehen (ueberfaellig) ...
    assert next_maintenance(date(2026, 9, 1), None, as_of, None) == date(2026, 9, 1)
    # ... mit Intervall folgt der naechste Termin ab heute.
    assert next_maintenance(date(2026, 3, 1), 6, as_of, None) == date(2027, 3, 1)
    assert next_maintenance(date(2026, 11, 1), 6, as_of, None, frozenset({date(2026, 11, 1)})) == date(2027, 5, 1)
    assert next_maintenance(date(2026, 11, 1), None, as_of, None, frozenset({date(2026, 11, 1)})) is None
    assert next_maintenance(date(2026, 11, 1), 6, as_of, date(2026, 10, 31)) is None
    assert next_maintenance(None, 6, as_of, None) is None


# --------------------------------------------------------------------------- Zahlungszeitpunkt aus dem Wortlaut


def _extracted(terms):
    return SimpleNamespace(payment=SimpleNamespace(payment_terms=terms, payment_notes=None))


def test_payment_timing_is_read_only_from_unambiguous_wording():
    assert payment_timing(_extracted("Die Vergütung ist quartalsweise im Voraus zu zahlen.")) == "in_advance"
    assert payment_timing(_extracted("Zahlung vierteljährlich nachschüssig")) == "in_arrears"
    assert payment_timing(_extracted("Abrechnung nachträglich nach Leistungserbringung")) == "in_arrears"
    assert payment_timing(_extracted("im Voraus oder nachträglich nach Wahl")) is None
    assert payment_timing(_extracted("Zahlbar innerhalb von 30 Tagen")) is None
    assert payment_timing(_extracted(None)) is None


# --------------------------------------------------------------------------- Prüfmodus (Lesezustand)


_REVIEW_DATA = {
    "identity": {"supplier": "Abiomed"},
    "costs": {"annual_recurring": {"amount": 1200}, "tax_breakdown": {"rate_percent": 19}},
    "evidence": [
        {"field_ref": "identity.supplier", "evidence_id": "e1", "page": 1, "snippet": "Abiomed"},
        {"field_ref": "costs.annual", "evidence_id": "e2", "page": 2, "snippet": "1.200 EUR jährlich"},
        {"field_ref": "costs.vat_rate", "evidence_id": "e3", "page": 2, "snippet": "19 %", "requires_review": True},
    ],
}


def _states(monkeypatch, mode):
    monkeypatch.setattr(review_service, "_latest_fact_reviews", lambda session, contract_id: {})
    monkeypatch.setattr(review_service, "load_events", lambda session, contract_id: ReviewEvents())
    monkeypatch.setattr(review_service, "auto_accept_allowed", lambda session, organization_id, contract_id: mode == "auto_noncritical")
    states = review_service.build_fact_review_states(None, organization_id=None, contract_id=None, data=_REVIEW_DATA)
    return {state["fact_key"]: state for state in states}


def test_manual_mode_auto_accepts_nothing(monkeypatch):
    states = _states(monkeypatch, "manual")
    assert states["costs.annual"]["state"] == "unreviewed"
    assert all(state["state"] != "auto_accepted" for state in states.values())


def test_auto_mode_accepts_only_noncritical_facts_with_clean_evidence(monkeypatch):
    states = _states(monkeypatch, "auto_noncritical")
    assert states["costs.annual"]["state"] == "auto_accepted"
    assert states["costs.annual"]["state_label_de"] == "Automatisch übernommen"
    # Kritisch bleibt manuell, zu pruefender Beleg bleibt "Zu prüfen".
    assert states["identity.supplier"]["state"] == "unreviewed"
    assert states["costs.vat_rate"]["state"] == "needs_review"
    summary = review_service.build_review_summary(list(states.values()))
    # „Jährliche Kosten“ ist ein Rechenwert: er zählt nicht als Angabe, die eine Entscheidung braucht.
    assert summary["relevant_count"] == 2 and summary["reviewed_count"] == 0
    assert summary["critical_unreviewed_count"] == 2


# --------------------------------------------------------------------------- Datenbank: Sync + API


def test_finance_entry_with_reminder_creates_payment_deadline(monkeypatch):
    from app.database.models import Contract
    from app.database.models.deadlines import ContractDeadline
    from app.database.session import create_session
    from tests.test_register_gaps import _client, _seed

    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids)
    cid = client.post("/api/contracts", params=query, json={"values": {
        "short_description": "Wartung", "term_model": "terminable", "term_start_date": "2026-01-01",
        "notice_period_value": 3, "notice_period_unit": "months", "notice_to": "month_end",
    }}).json()["contract_id"]
    entry = {"label": "Pauschale", "amount": "300", "vat_rate": "19", "interval": "annual", "valid_from": "2020-01-01"}
    response = client.post(f"/api/contracts/{cid}/finance/entries", params=query, json={"values": entry})
    assert response.status_code == 200, response.text
    entry_id = response.json()["entries"][0]["id"]
    assert response.json()["entries"][0]["payment_timing"] is None

    def payment_rows():
        session = create_session()
        try:
            return session.scalars(select(ContractDeadline).where(
                ContractDeadline.contract_id == UUID(cid), ContractDeadline.system_key == "payment_due",
                ContractDeadline.status == "open",
            )).all()
        finally:
            session.close()

    # Ohne Zahlungszeitpunkt keine Erinnerung (nie geraten).
    client.patch(f"/api/contracts/{cid}/finance/entries/{entry_id}", params=query, json={"values": {"payment_reminder": True}})
    assert payment_rows() == []
    bad = client.patch(f"/api/contracts/{cid}/finance/entries/{entry_id}", params=query, json={"values": {"payment_timing": "sometimes"}})
    assert bad.status_code == 422
    client.patch(f"/api/contracts/{cid}/finance/entries/{entry_id}", params=query, json={"values": {"payment_timing": "in_advance"}})
    rows = payment_rows()
    assert len(rows) == 1 and rows[0].kind == "zahlung" and rows[0].due_date.month == 1 and rows[0].due_date.day == 1
    assert "300,00 €" in rows[0].title

    # Wartung ueber die Registerfelder.
    response = client.patch(f"/api/contracts/{cid}/register", params=query, json={"changes": {
        "maintenance_next_date": "2030-05-01", "maintenance_interval_months": 12,
    }})
    assert response.status_code == 200, response.text
    session = create_session()
    try:
        maintenance = session.scalars(select(ContractDeadline).where(
            ContractDeadline.contract_id == UUID(cid), ContractDeadline.system_key == "maintenance_due",
        )).all()
        assert [(row.due_date, row.status) for row in maintenance] == [(date(2030, 5, 1), "open")]
        assert session.get(Contract, UUID(cid)).maintenance_interval_months == 12
    finally:
        session.close()
    too_long = client.patch(f"/api/contracts/{cid}/register", params=query, json={"changes": {"maintenance_interval_months": 500}})
    assert too_long.status_code == 422

    # Erinnerung aus -> offener Termin wird entfernt.
    client.patch(f"/api/contracts/{cid}/finance/entries/{entry_id}", params=query, json={"values": {"payment_reminder": False}})
    assert payment_rows() == []


def test_review_settings_api_requires_admin_and_is_logged(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes import review_settings
    from app.database.models import ActivityLog
    from app.database.models.organization import Organization
    from app.database.session import create_session
    from tests.test_register_gaps import _seed

    slug, ids = _seed()
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role="admin", is_developer=False, display_name="Admin")
    monkeypatch.setattr(review_settings, "current_actor", lambda request, organization_slug: actor)
    app = FastAPI()
    app.include_router(review_settings.router)
    client = TestClient(app)
    query = {"organization_slug": slug}

    current = client.get("/api/review-settings", params=query).json()
    assert current["review_mode"] == "manual" and current["can_edit"] is True
    assert {option["value"] for option in current["options"]} == {"manual", "auto_noncritical"}
    assert client.put("/api/review-settings", params=query, json={"review_mode": "everything"}).status_code == 422
    updated = client.put("/api/review-settings", params=query, json={"review_mode": "auto_noncritical"}).json()
    assert updated["review_mode"] == "auto_noncritical"

    session = create_session()
    try:
        assert session.get(Organization, ids["org"]).review_mode == "auto_noncritical"
        assert review_service.review_mode(session, ids["org"]) == "auto_noncritical"
        logs = session.scalars(select(ActivityLog).where(
            ActivityLog.organization_id == ids["org"], ActivityLog.event_name == "organization.review_mode_changed",
        )).all()
        assert [log.context_data for log in logs] == [{"before": "manual", "after": "auto_noncritical"}]
    finally:
        session.close()

    actor.role = "contract_manager"
    assert client.get("/api/review-settings", params=query).json()["can_edit"] is False
    assert client.put("/api/review-settings", params=query, json={"review_mode": "manual"}).status_code == 403
