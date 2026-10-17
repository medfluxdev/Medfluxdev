"""H5 pure logic: system deadline planning, ICS, mail message, scheduler timing, self-service paths."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.auth.middleware import _self_service_mutation
from app.deadlines.mail import build_ics, build_message
from app.deadlines.system import plan_system_deadlines
from app.jobs.daily import due_now
from app.register.terms import TermResult


def _contract(**overrides):
    values = dict(
        lifecycle_state="active", is_archived=False, business_status="gueltig", term_model="terminable",
        reminder_recipient_account_id=None, responsible_account_id=uuid4(), escalation_recipient_account_id=uuid4(),
        reminder_lead_months=None, reminder_extra_leads=None, reminder_todo=None, escalation_days_before=None, price_adjustment_kind=None, price_adjustment_next_date=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


TERMS = TermResult(status="complete", cancel_by=date(2027, 6, 30), possible_end=date(2027, 9, 30))


def test_cancel_by_deadline_with_default_lead():
    contract = _contract()
    [spec] = plan_system_deadlines(contract, TERMS)
    assert spec.system_key == "cancel_by"
    assert spec.due_date == date(2027, 6, 30)
    assert spec.remind_on == date(2027, 2, 28)  # Standard: 4 Monate vorher
    assert spec.extra_remind_on is None
    assert spec.assignee_account_id == contract.responsible_account_id
    assert spec.escalation_account_id == contract.escalation_recipient_account_id


def test_reminder_recipient_and_lead_override():
    recipient = uuid4()
    [spec] = plan_system_deadlines(
        _contract(reminder_recipient_account_id=recipient, reminder_lead_months=0, reminder_todo="Angebot einholen"), TERMS
    )
    assert spec.assignee_account_id == recipient
    assert spec.remind_on == spec.due_date
    # Was zu tun ist, gehört seit 2026-10-15 zum Termin (overrides), nicht mehr zum Vertrag.
    assert spec.todo_text == "Verlängerung prüfen oder Vertrag fristgerecht kündigen."


def test_fixed_term_creates_contract_end_deadline():
    [spec] = plan_system_deadlines(
        _contract(term_model="fixed_term"), TermResult(status="complete", possible_end=date(2027, 7, 28))
    )
    assert spec.system_key == "contract_end"
    assert spec.due_date == date(2027, 7, 28)


def test_terminated_contract_gets_set_ended_task():
    [spec] = plan_system_deadlines(
        _contract(business_status="gekuendigt"),
        TermResult(status="complete", possible_end=date(2026, 12, 31), actual_end=date(2026, 12, 31)),
    )
    assert spec.system_key == "set_ended"
    assert spec.remind_on == spec.due_date == date(2026, 12, 31)


@pytest.mark.parametrize("status", ["gueltig", "gekuendigt", "beendet"])
def test_retention_review_as_soon_as_end_is_known(status):
    specs = plan_system_deadlines(
        _contract(business_status=status, term_model="fixed_term"),
        TermResult(status="complete", possible_end=date(2029, 3, 31)),
        deletion_from=date(2040, 1, 1),
    )
    [review] = [spec for spec in specs if spec.system_key == "retention_review"]
    assert review.due_date == review.remind_on == date(2040, 1, 1)


def test_no_retention_review_for_cancelled_contract():
    specs = plan_system_deadlines(_contract(business_status="geloescht"), TERMS, deletion_from=date(2040, 1, 1))
    assert all(spec.system_key != "retention_review" for spec in specs)


@pytest.mark.parametrize(
    "overrides",
    [
        {"business_status": "beendet"},
        {"business_status": "geloescht"},
        {"is_archived": True},
        {"lifecycle_state": "pending_deletion"},
    ],
)
def test_no_deadlines_for_closed_contracts(overrides):
    assert plan_system_deadlines(_contract(**overrides), TERMS) == []


def test_ics_is_valid_and_escaped():
    ics = build_ics(
        uid="abc@medflux", due=date(2027, 6, 30), summary="Kündigungsfrist; Vertrag 000001",
        description="Zeile 1\nZeile 2, mit Komma " + "x" * 80, now=datetime(2026, 10, 4, tzinfo=timezone.utc),
    )
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert "DTSTART;VALUE=DATE:20270630" in ics and "DTEND;VALUE=DATE:20270701" in ics
    assert "SUMMARY:Kündigungsfrist\\; Vertrag 000001" in ics
    assert "Zeile 1\\nZeile 2\\, mit Komma" in ics
    assert all(len(line.encode("utf-8")) <= 75 for line in ics.split("\r\n"))
    assert "TRIGGER:-P1D" in ics


def test_mail_message_with_calendar_attachment(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "smtp_from", "medflux@klinik.invalid")
    message = build_message(recipient="a@klinik.invalid", subject="Erinnerung", body="Text", ics="BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
    assert message["To"] == "a@klinik.invalid" and message["From"] == "medflux@klinik.invalid"
    attachments = list(message.iter_attachments())
    assert len(attachments) == 1 and attachments[0].get_content_type() == "text/calendar"


@pytest.mark.parametrize(
    "hour,ran,expected",
    [(4, False, False), (5, False, True), (23, False, True), (6, True, False)],
)
def test_scheduler_due(hour, ran, expected):
    assert due_now(datetime(2026, 10, 4, hour, 0), 5, ran) is expected


@pytest.mark.parametrize(
    "path,allowed",
    [
        ("/api/inbox/read-all", True),
        ("/api/inbox/01a106c2-c280-7c98-9f84-bc9bb3b50afc/read", True),
        ("/api/me/notification-settings", True),
        ("/api/inbox/../contracts/read", False),
        ("/api/deadlines/01a106c2-c280-7c98-9f84-bc9bb3b50afc/done", False),
        ("/api/me/notification-settings/extra", False),
    ],
)
def test_self_service_paths(path, allowed):
    assert _self_service_mutation(path) is allowed


def test_price_adjustment_creates_review_deadline():
    specs = plan_system_deadlines(
        _contract(price_adjustment_kind="percent", price_adjustment_next_date=date(2027, 1, 1)), TERMS
    )
    adjustment = next(spec for spec in specs if spec.system_key == "price_adjustment")
    assert (adjustment.due_date, adjustment.remind_on) == (date(2027, 1, 1), date(2026, 12, 1))
    assert plan_system_deadlines(_contract(price_adjustment_kind="fixed", price_adjustment_next_date=date(2027, 1, 1)), TERMS)[-1].system_key == "cancel_by"


def test_extra_reminders_after_the_first_each_listed_once():
    contract = _contract(reminder_lead_months=3, reminder_extra_leads=[{"value": 2, "unit": "weeks"}, {"value": 1, "unit": "months"}, {"value": 6, "unit": "months"}])
    [spec] = plan_system_deadlines(contract, TERMS)
    # Jede Erinnerung zählt; die früheste (6 Monate) ist die erste, der Rest aufsteigend.
    assert spec.remind_on == date(2026, 12, 30)
    assert spec.extra_remind_on == ["2027-03-30", "2027-05-30", "2027-06-16"]


def test_reminder_leads_validation_and_labels():
    import pytest

    from app.register.reminders import first_reminder, lead_label, normalize_leads

    assert normalize_leads([{"value": 3, "unit": "days"}, {"value": 1, "unit": "months"}, {"value": 1, "unit": "months"}]) == [
        {"value": 1, "unit": "months"}, {"value": 3, "unit": "days"},
    ]
    assert lead_label({"value": 1, "unit": "weeks"}) == "1 Woche" and lead_label({"value": 2, "unit": "months"}) == "2 Monate"
    assert first_reminder(date(2029, 3, 31), None) == date(2028, 11, 30)
    assert first_reminder(date(2029, 3, 31), 0) == date(2029, 3, 31)
    for bad in ([{"value": 0, "unit": "days"}], [{"value": 1, "unit": "years"}], [{"value": "1", "unit": "days"}], "x"):
        with pytest.raises(ValueError):
            normalize_leads(bad)

