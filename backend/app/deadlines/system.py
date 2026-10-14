"""Systemtermine aus den Register-Fristen (deterministisch).

Aus den berechneten Fristen eines Vertrags entstehen Termine im Postfach:
- `cancel_by`: Kuendigungsfrist (kuendbare/sich verlaengernde Vertraege),
- `contract_end`: Vertragsende bei fester Laufzeit,
- `set_ended`: nach wirksamer Kuendigung den Vertrag auf "Beendet" setzen,
- `payment_due`: naechste Zahlung aus Finanzeintraegen mit Zahlungserinnerung
  (nur mit gepflegtem Zahlungszeitpunkt; vorschuessig = Periodenbeginn,
  nachschuessig = Periodenende),
- `maintenance_due`: naechste Wartung (gepflegtes Datum, Folgetermine im Intervall).

Ist eine Frist erledigt, entsteht automatisch die naechste, sobald sich die
berechnete Frist weiterbewegt (z. B. naechste Verlaengerungsperiode).
Erledigte Termine mit gleichem Faelligkeitsdatum werden nie neu angelegt.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.calculation.calendar_ import month_add
from app.database.models import Contract
from app.database.models.deadlines import ContractDeadline
from app.database.models.finance import ContractFinanceEntry
from app.register.service import log_system_activity, retention_info, term_inputs
from app.register.reminders import DEFAULT_REMINDER_LEAD_MONTHS as DEFAULT_LEAD_MONTHS, extra_reminders
from app.register.terms import TermResult, compute_terms

ACTIVE_STATUSES = frozenset({"in_arbeit", "gueltig"})
ADJUSTING_KINDS = frozenset({"percent", "index", "negotiation"})
# Zahlungen/Wartungen laufen bis zum Vertragsende weiter, auch nach einer Kuendigung.
SCHEDULE_STATUSES = frozenset({"in_arbeit", "gueltig", "gekuendigt"})
INTERVAL_MONTHS = {"monthly": 1, "quarterly": 3, "semi_annual": 6, "annual": 12}
PAYMENT_LEAD_DAYS = 14
MAX_PERIODS = 1200
TERM_BASIS_FIELDS = (
    "term_model", "term_start_date", "term_fixed_end_date", "initial_term_value", "minimum_term_value",
    "notice_period_value", "notice_period_unit", "notice_to", "renewal_period_value",
)


@dataclass(frozen=True)
class SystemDeadlineSpec:
    system_key: str
    kind: str
    title: str
    due_date: date
    remind_on: date
    todo_text: str
    assignee_account_id: Optional[uuid.UUID]
    escalation_account_id: Optional[uuid.UUID]
    # Weitere Erinnerungstage (nur Kündigungsfrist/Vertragsende), ISO-Daten aufsteigend.
    extra_remind_on: Optional[list] = None


def _extra(due: date, contract: Contract) -> Optional[list]:
    extra = extra_reminders(due, contract.reminder_extra_leads or [], _remind_on(due, contract.reminder_lead_months))
    return [day.isoformat() for day in extra] or None


def _remind_on(due: date, lead_months: Optional[int]) -> date:
    lead = DEFAULT_LEAD_MONTHS if lead_months is None else lead_months
    return min(due, month_add(due, -lead))


@dataclass(frozen=True)
class PaymentSchedule:
    label: str
    amount: Decimal
    currency: str
    interval: str
    valid_from: date
    valid_to: Optional[date]
    timing: str  # in_advance | in_arrears


def payment_schedules(entries: Iterable[ContractFinanceEntry]) -> list[PaymentSchedule]:
    """Nur Ausgaben mit eingeschalteter Erinnerung UND gepflegtem Zahlungszeitpunkt (nie geraten)."""
    return [
        PaymentSchedule(row.label, row.amount, row.currency, row.interval, row.valid_from, row.valid_to, row.payment_timing)
        for row in entries
        if row.direction == "expense" and row.payment_reminder and row.payment_timing in ("in_advance", "in_arrears")
    ]


def _payment_dates(schedule: PaymentSchedule, end: Optional[date]) -> Iterable[date]:
    """Faelligkeiten je Periode in aufsteigender Reihenfolge (bis Gueltig-bis bzw. Vertragsende)."""
    last = min((value for value in (schedule.valid_to, end) if value is not None), default=None)
    if schedule.interval == "once":
        due = schedule.valid_from if schedule.timing == "in_advance" else (schedule.valid_to or schedule.valid_from)
        if last is None or schedule.valid_from <= last:
            yield due
        return
    months = INTERVAL_MONTHS.get(schedule.interval)
    if months is None:
        return
    for index in range(MAX_PERIODS):
        start = month_add(schedule.valid_from, index * months)
        if last is not None and start > last:
            return
        if schedule.timing == "in_advance":
            yield start
        else:
            period_end = month_add(schedule.valid_from, (index + 1) * months) - timedelta(days=1)
            yield min(period_end, last) if last is not None else period_end


def _money(amount: Decimal, currency: str) -> str:
    text = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} {'€' if currency == 'EUR' else currency}"


def next_payment(
    schedules: Iterable[PaymentSchedule], as_of: date, end: Optional[date], done: frozenset[date] = frozenset()
) -> Optional[tuple[date, list[PaymentSchedule]]]:
    """Naechste noch nicht erledigte Zahlung ab heute; mehrere Eintraege am selben Tag werden zusammengefasst."""
    found: dict[date, list[PaymentSchedule]] = {}
    for schedule in schedules:
        for due in _payment_dates(schedule, end):
            if due >= as_of and due not in done:
                found.setdefault(due, []).append(schedule)
                break
    if not found:
        return None
    due = min(found)
    return due, sorted(found[due], key=lambda item: item.label)


def next_maintenance(
    anchor: Optional[date], interval_months: Optional[int], as_of: date, end: Optional[date],
    done: frozenset[date] = frozenset(),
) -> Optional[date]:
    """Gepflegtes Datum zuerst (auch wenn schon vorbei: dann ueberfaellig), danach Folgetermine im Intervall."""
    if anchor is None:
        return None
    if anchor not in done and (anchor >= as_of or not interval_months):
        return anchor if end is None or anchor <= end else None
    if not interval_months:
        return None
    for index in range(1, MAX_PERIODS):
        due = month_add(anchor, index * interval_months)
        if end is not None and due > end:
            return None
        if due >= as_of and due not in done:
            return due
    return None


def plan_system_deadlines(
    contract: Contract,
    terms: TermResult,
    deletion_from: Optional[date] = None,
    *,
    payments: Iterable[PaymentSchedule] = (),
    as_of: Optional[date] = None,
    done: Optional[dict[str, frozenset[date]]] = None,
) -> list[SystemDeadlineSpec]:
    if contract.lifecycle_state != "active" or contract.is_archived:
        return []
    assignee = contract.reminder_recipient_account_id or contract.responsible_account_id
    escalation = contract.escalation_recipient_account_id
    specs: list[SystemDeadlineSpec] = []
    if contract.business_status in ACTIVE_STATUSES:
        if terms.cancel_by is not None:
            specs.append(SystemDeadlineSpec(
                system_key="cancel_by",
                kind="kuendigungsfrist",
                title="Kündigungsfrist",
                due_date=terms.cancel_by,
                remind_on=_remind_on(terms.cancel_by, contract.reminder_lead_months),
                extra_remind_on=_extra(terms.cancel_by, contract),
                todo_text=contract.reminder_todo or "Verlängerung prüfen oder Vertrag fristgerecht kündigen.",
                assignee_account_id=assignee,
                escalation_account_id=escalation,
            ))
        elif contract.term_model == "fixed_term" and terms.possible_end is not None:
            specs.append(SystemDeadlineSpec(
                system_key="contract_end",
                kind="vertragsende",
                title="Vertragsende (feste Laufzeit)",
                due_date=terms.possible_end,
                remind_on=_remind_on(terms.possible_end, contract.reminder_lead_months),
                extra_remind_on=_extra(terms.possible_end, contract),
                todo_text=contract.reminder_todo or "Folgevertrag oder Verlängerung klären.",
                assignee_account_id=assignee,
                escalation_account_id=escalation,
            ))
        adjustment_date = contract.price_adjustment_next_date
        if contract.price_adjustment_kind in ADJUSTING_KINDS and adjustment_date is not None:
            specs.append(SystemDeadlineSpec(
                system_key="price_adjustment",
                kind="preisanpassung",
                title="Preisanpassung prüfen",
                due_date=adjustment_date,
                remind_on=_remind_on(adjustment_date, 1),
                todo_text="Angekündigte Preisanpassung mit dem Vertrag abgleichen und Finanzdaten aktualisieren.",
                assignee_account_id=assignee,
                escalation_account_id=escalation,
            ))
    if contract.business_status in SCHEDULE_STATUSES and as_of is not None:
        done = done or {}
        # Nur ein feststehendes Ende begrenzt die Serie (Kuendigung wirksam oder feste Laufzeit);
        # bei kuendbaren/sich verlaengernden Vertraegen ist possible_end nur das fruehestmoegliche Ende.
        end = terms.actual_end or (terms.possible_end if contract.term_model == "fixed_term" else None)
        payment = next_payment(payments, as_of, end, done.get("payment_due", frozenset()))
        if payment is not None:
            due, items = payment
            first = items[0]
            more = f" (+{len(items) - 1} weitere)" if len(items) > 1 else ""
            specs.append(SystemDeadlineSpec(
                system_key="payment_due",
                kind="zahlung",
                title=f"Zahlung fällig: {first.label} – {_money(first.amount, first.currency)}{more}"[:255],
                due_date=due,
                remind_on=min(due, due - timedelta(days=PAYMENT_LEAD_DAYS)),
                todo_text="Rechnung mit dem Vertrag abgleichen und Zahlung freigeben.",
                assignee_account_id=assignee,
                escalation_account_id=escalation,
            ))
        maintenance = next_maintenance(
            contract.maintenance_next_date, contract.maintenance_interval_months, as_of, end,
            done.get("maintenance_due", frozenset()),
        )
        if maintenance is not None:
            specs.append(SystemDeadlineSpec(
                system_key="maintenance_due",
                kind="wartung",
                title="Wartung fällig",
                due_date=maintenance,
                remind_on=_remind_on(maintenance, 1),
                todo_text="Wartungstermin mit dem Vertragspartner abstimmen und nach Durchführung erledigen.",
                assignee_account_id=assignee,
                escalation_account_id=escalation,
            ))
    # Sobald das Vertragsende feststeht (auch bei fester Laufzeit im laufenden Vertrag), steht der Löschtermin fest.
    # Ändert sich das Ende, ersetzt der Abgleich den alten Termin durch den neuen.
    if contract.business_status != "geloescht" and deletion_from is not None:
        specs.append(SystemDeadlineSpec(
            system_key="retention_review",
            kind="loeschpruefung",
            title="Löschprüfung (Aufbewahrungsfrist abgelaufen)",
            due_date=deletion_from,
            remind_on=deletion_from,
            todo_text="Prüfen, ob Vertrag und Dokumente gelöscht werden können; Löschung über den Löschablauf beantragen.",
            assignee_account_id=assignee,
            escalation_account_id=escalation,
        ))
    if contract.business_status == "gekuendigt" and terms.actual_end is not None:
        specs.append(SystemDeadlineSpec(
            system_key="set_ended",
            kind="statuswechsel",
            title="Vertrag auf „Beendet“ setzen",
            due_date=terms.actual_end,
            remind_on=terms.actual_end,
            todo_text="Nach Vertragsende den Status auf „Beendet“ setzen.",
            assignee_account_id=assignee,
            escalation_account_id=escalation,
        ))
    return specs


SYSTEM_NAME = "System (Fristenabgleich)"


def _plain(value):
    return value.isoformat() if isinstance(value, date) else (str(value) if value is not None else None)


def sync_system_deadlines(session: Session, contract: Contract, as_of: date) -> dict[str, int]:
    """Gleicht die offenen Systemtermine mit den aktuellen Fristen ab (idempotent)."""
    terms = compute_terms(term_inputs(contract), as_of)
    deletion_from = retention_info(session, contract, terms)["deletion_from"]
    rows = session.scalars(
        select(ContractDeadline).where(
            ContractDeadline.contract_id == contract.id, ContractDeadline.source == "system"
        )
    ).all()
    open_rows = {row.system_key: row for row in rows if row.status == "open"}
    closed = {(row.system_key, row.due_date) for row in rows if row.status != "open"}
    done: dict[str, frozenset[date]] = {}
    for key, due in closed:
        done[key] = done.get(key, frozenset()) | {due}
    entries = session.scalars(
        select(ContractFinanceEntry).where(ContractFinanceEntry.contract_id == contract.id)
    ).all()
    specs = {
        spec.system_key: spec
        for spec in plan_system_deadlines(
            contract, terms, date.fromisoformat(deletion_from) if deletion_from else None,
            payments=payment_schedules(entries), as_of=as_of, done=done,
        )
    }
    counts = {"created": 0, "updated": 0, "cancelled": 0}

    for key, row in open_rows.items():
        if key not in specs:
            row.status = "cancelled"
            row.note = "Automatisch entfernt: Die Grundlage der Frist hat sich geändert."
            counts["cancelled"] += 1
            log_system_activity(session, contract, "deadline.system_cancelled", {
                "deadline_id": str(row.id), "title": row.title, "due_date": row.due_date.isoformat(),
            }, display_name=SYSTEM_NAME)
    for key, spec in specs.items():
        row = open_rows.get(key)
        if row is None:
            if (key, spec.due_date) in closed:
                continue
            session.add(ContractDeadline(
                organization_id=contract.organization_id,
                contract_id=contract.id,
                source="system",
                system_key=key,
                kind=spec.kind,
                title=spec.title,
                due_date=spec.due_date,
                remind_on=spec.remind_on,
                extra_remind_on=spec.extra_remind_on,
                todo_text=spec.todo_text,
                assignee_account_id=spec.assignee_account_id,
                escalation_account_id=spec.escalation_account_id,
                status="open",
                created_by_name="System",
            ))
            counts["created"] += 1
            log_system_activity(session, contract, "deadline.system_created", {
                "title": spec.title, "due_date": spec.due_date.isoformat(), "system_key": key,
            }, display_name=SYSTEM_NAME)
            continue
        if row.due_date < as_of and spec.due_date != row.due_date:
            # Verpasste Frist bleibt offen (ueberfaellig/Eskalation), bis sie
            # erledigt wird; erst danach entsteht die naechste Periode.
            continue
        diffs = {}
        for attr in ("kind", "title", "due_date", "remind_on", "extra_remind_on", "todo_text", "assignee_account_id", "escalation_account_id"):
            value = getattr(spec, attr)
            if getattr(row, attr) != value:
                diffs[attr] = {"before": _plain(getattr(row, attr)), "after": _plain(value)}
                setattr(row, attr, value)
        if diffs:
            counts["updated"] += 1
            log_system_activity(session, contract, "deadline.system_updated", {
                "deadline_id": str(row.id), "title": row.title, "fields": diffs,
            }, display_name=SYSTEM_NAME)
    session.flush()
    return counts
