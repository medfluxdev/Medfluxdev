"""Systemtermine aus den Register-Fristen (deterministisch).

Aus den berechneten Fristen eines Vertrags entstehen Termine im Postfach:
- `cancel_by`: Kuendigungsfrist (kuendbare/sich verlaengernde Vertraege),
- `contract_end`: Vertragsende bei fester Laufzeit,
- `set_ended`: nach wirksamer Kuendigung den Vertrag auf "Beendet" setzen.

Ist eine Frist erledigt, entsteht automatisch die naechste, sobald sich die
berechnete Frist weiterbewegt (z. B. naechste Verlaengerungsperiode).
Erledigte Termine mit gleichem Faelligkeitsdatum werden nie neu angelegt.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.calculation.calendar_ import month_add
from app.database.models import Contract
from app.database.models.deadlines import ContractDeadline
from app.register.service import retention_info, term_inputs
from app.register.terms import TermResult, compute_terms

DEFAULT_LEAD_MONTHS = 3
ACTIVE_STATUSES = frozenset({"in_arbeit", "gueltig"})
ADJUSTING_KINDS = frozenset({"percent", "index", "negotiation"})
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


def _remind_on(due: date, lead_months: Optional[int]) -> date:
    lead = DEFAULT_LEAD_MONTHS if lead_months is None else lead_months
    return min(due, month_add(due, -lead))


def plan_system_deadlines(
    contract: Contract, terms: TermResult, deletion_from: Optional[date] = None
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
    if contract.business_status in ("beendet", "gekuendigt") and deletion_from is not None:
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


def sync_system_deadlines(session: Session, contract: Contract, as_of: date) -> dict[str, int]:
    """Gleicht die offenen Systemtermine mit den aktuellen Fristen ab (idempotent)."""
    terms = compute_terms(term_inputs(contract), as_of)
    deletion_from = retention_info(session, contract, terms)["deletion_from"]
    specs = {
        spec.system_key: spec
        for spec in plan_system_deadlines(contract, terms, date.fromisoformat(deletion_from) if deletion_from else None)
    }
    rows = session.scalars(
        select(ContractDeadline).where(
            ContractDeadline.contract_id == contract.id, ContractDeadline.source == "system"
        )
    ).all()
    open_rows = {row.system_key: row for row in rows if row.status == "open"}
    closed = {(row.system_key, row.due_date) for row in rows if row.status != "open"}
    counts = {"created": 0, "updated": 0, "cancelled": 0}

    for key, row in open_rows.items():
        if key not in specs:
            row.status = "cancelled"
            row.note = "Automatisch entfernt: Die Grundlage der Frist hat sich geändert."
            counts["cancelled"] += 1
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
                todo_text=spec.todo_text,
                assignee_account_id=spec.assignee_account_id,
                escalation_account_id=spec.escalation_account_id,
                status="open",
                created_by_name="System",
            ))
            counts["created"] += 1
            continue
        if row.due_date < as_of and spec.due_date != row.due_date:
            # Verpasste Frist bleibt offen (ueberfaellig/Eskalation), bis sie
            # erledigt wird; erst danach entsteht die naechste Periode.
            continue
        changed = False
        for attr in ("kind", "title", "due_date", "remind_on", "todo_text", "assignee_account_id", "escalation_account_id"):
            value = getattr(spec, attr)
            if getattr(row, attr) != value:
                setattr(row, attr, value)
                changed = True
        if changed:
            counts["updated"] += 1
    session.flush()
    return counts
