"""Schritt 13a: Entscheidungsvorlage vor Kuendigungsfristen (nur Beratung).

Fakten, Fristen und Betraege berechnet der Code aus Stammdaten und Finanzdaten.
Die Hinweise sind regelbasiert und begruendet; entschieden wird ausschliesslich
durch Menschen (Lifecycle-Entscheidung). Nichts wird automatisch gekuendigt.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Account, Contract
from app.database.models.contract import ContractDocument
from app.database.models.deadlines import ContractDeadline
from app.database.models.lifecycle import ContractLifecycleDecision
from app.database.models.register import ContractPartner
from app.finance.calc import month_index, monthly_values
from app.finance.service import _entries, entry_inputs, price_adjustment
from app.register.service import review_pending, term_inputs
from app.register.terms import TERM_MODEL_LABELS, compute_terms
from app.reports.grid import GridRow

RUNNING = ("in_arbeit", "gueltig")
DECISION_LABELS = {"renew": "Verlängern", "renegotiate": "Neu verhandeln", "terminate": "Kündigen", "monitor": "Beobachten"}
OPEN_DECISION_STATUS = ("planned", "in_progress", "completed")


def _de(day: Optional[date]) -> str:
    return day.strftime("%d.%m.%Y") if day else "–"


def _euro(amount: Decimal) -> str:
    text = f"{amount.quantize(Decimal('0.01')):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{text} €"


def urgency(cancel_by: Optional[date], as_of: date) -> str:
    if cancel_by is None:
        return "unknown"
    days = (cancel_by - as_of).days
    if days < 0:
        return "missed"
    if days <= 30:
        return "critical"
    if days <= 90:
        return "soon"
    return "planned"


def _cost_between(session: Session, contract: Contract, start: date, end: date, as_of: date) -> Optional[Decimal]:
    rows = [row for row in _entries(session, contract.id) if row.direction == "expense" and (row.currency or "EUR") == "EUR"]
    if not rows:
        return None
    adjustment, _ = price_adjustment(contract, as_of)
    total = Decimal("0")
    first, last = month_index(start), month_index(end)
    for entry in entry_inputs(rows):
        for net, _gross in monthly_values(entry, first, last, adjustment).values():
            total += net
    return total.quantize(Decimal("0.01"))


def _latest_decision(session: Session, contract_id: uuid.UUID) -> Optional[ContractLifecycleDecision]:
    return session.scalars(
        select(ContractLifecycleDecision)
        .where(ContractLifecycleDecision.contract_id == contract_id, ContractLifecycleDecision.status.in_(OPEN_DECISION_STATUS))
        .order_by(ContractLifecycleDecision.created_at.desc())
    ).first()


def renewal_brief(session: Session, contract: Contract, as_of: date, visible: Optional[set[uuid.UUID]] = None) -> dict:
    inputs = term_inputs(contract)
    terms = compute_terms(inputs, as_of)
    cancel_by = terms.cancel_by
    current_end = terms.actual_end or terms.possible_end
    days_left = (cancel_by - as_of).days if cancel_by else None

    # Was passiert ohne Kuendigung: Fristen am Tag nach der Kuendigungsfrist.
    next_end: Optional[date] = None
    next_cancel_by: Optional[date] = None
    if cancel_by is not None and contract.business_status in RUNNING:
        after = compute_terms(replace(inputs), cancel_by + timedelta(days=1))
        next_end = after.possible_end
        next_cancel_by = after.cancel_by

    if contract.business_status == "gekuendigt":
        if_no_action = f"Der Vertrag ist gekündigt und endet am {_de(terms.actual_end or contract.terminated_effective)}."
    elif contract.term_model == "fixed_term" and current_end is not None:
        if_no_action = f"Der Vertrag endet am {_de(current_end)} ohne Kündigung. Für eine Weiterführung ist ein Anschlussvertrag nötig."
    elif cancel_by is None:
        if_no_action = "Kündigungsfrist nicht berechenbar – Laufzeitangaben in den Stammdaten vervollständigen."
    elif contract.term_model == "auto_renewal":
        if_no_action = (
            f"Ohne Kündigung bis {_de(cancel_by)} verlängert sich der Vertrag "
            f"um {inputs.renewal_period.label() if inputs.renewal_period else 'die vereinbarte Periode'} bis {_de(next_end)}."
        )
    else:
        if_no_action = (
            f"Ohne Kündigung bis {_de(cancel_by)} läuft der Vertrag weiter; "
            f"nächste Kündigungsmöglichkeit bis {_de(next_cancel_by)} zum {_de(next_end)}."
        )

    renewal_cost = None
    if current_end and next_end and next_end > current_end and contract.term_model != "fixed_term":
        renewal_cost = _cost_between(session, contract, current_end + timedelta(days=1), next_end, as_of)

    adjustment, adjustment_notes = price_adjustment(contract, as_of)

    partner_name = None
    partner_contracts: list[dict] = []
    if contract.partner_id:
        partner_name = session.scalar(select(ContractPartner.short_name).where(ContractPartner.id == contract.partner_id))
        stmt = select(Contract.id, Contract.register_number, Contract.short_description).where(
            Contract.organization_id == contract.organization_id,
            Contract.partner_id == contract.partner_id,
            Contract.id != contract.id,
            Contract.business_status.in_(RUNNING + ("gekuendigt",)),
            Contract.lifecycle_state == "active",
        )
        if visible is not None:
            stmt = stmt.where(Contract.id.in_(visible))
        partner_contracts = [
            {"contract_id": str(cid), "register_number": number, "short_description": title}
            for cid, number, title in session.execute(stmt.order_by(Contract.register_number)).all()
        ]

    names = dict(session.execute(
        select(Account.id, Account.display_name).where(Account.id.in_([
            value for value in (contract.responsible_account_id, contract.reminder_recipient_account_id) if value
        ]))
    ).all()) if (contract.responsible_account_id or contract.reminder_recipient_account_id) else {}
    documents = session.scalar(select(func.count()).select_from(ContractDocument).where(ContractDocument.contract_id == contract.id)) or 0
    open_deadlines = session.scalars(
        select(ContractDeadline).where(ContractDeadline.contract_id == contract.id, ContractDeadline.status == "open")
        .order_by(ContractDeadline.due_date).limit(5)
    ).all()
    decision = _latest_decision(session, contract.id)
    unreviewed = review_pending(session, contract)

    annual = None
    rows = [row for row in _entries(session, contract.id) if row.direction == "expense"]
    if rows:
        annual = _cost_between(session, contract, date(as_of.year, as_of.month, 1), date(as_of.year, as_of.month, 1), as_of)
        annual = (annual * 12).quantize(Decimal("0.01")) if annual is not None else None

    hints: list[dict] = []

    def hint(kind: str, text: str, reason: str) -> None:
        hints.append({"kind": kind, "text": text, "reason": reason})

    fixed = contract.term_model == "fixed_term" and cancel_by is None
    level = urgency(cancel_by, as_of) if contract.business_status in RUNNING and not fixed else "none"
    if level == "missed" and decision is None:
        hint("action", "Die Kündigungsfrist ist verstrichen. Prüfen, ob der Vertrag sich verlängert hat, und die Folgefrist vormerken.",
             f"Kündbar bis {_de(cancel_by)} liegt vor dem Stichtag {_de(as_of)}.")
    elif level in ("critical", "soon") and decision is None:
        hint("action", f"Bis {_de(cancel_by)} entscheiden: verlängern, neu verhandeln oder kündigen.",
             f"Noch {days_left} Tage bis zum Ende der Kündigungsfrist; es ist keine Entscheidung erfasst.")
    if unreviewed:
        hint("check", "Die KI-Werte des Vertrags sind noch nicht vollständig geprüft. Laufzeit und Kündigungsfrist vor der Entscheidung bestätigen.",
             "Die Fristen beruhen auf Stammdaten, die teilweise aus der KI-Analyse stammen.")
    if renewal_cost is not None and renewal_cost > 0:
        hint("info", f"Bei Verlängerung entstehen bis {_de(next_end)} voraussichtlich {_euro(renewal_cost)} (netto).",
             "Hochrechnung aus den gepflegten Finanzposten über den Verlängerungszeitraum.")
    elif annual is None and contract.business_status in RUNNING:
        hint("check", "Keine Kosten gepflegt – ein Kostenvergleich für die Entscheidung ist nicht möglich.",
             "Im Reiter Finanzen sind keine Ausgaben erfasst.")
    if adjustment.kind == "percent" and adjustment.percent:
        hint("info", f"Vereinbarte Preisanpassung: +{str(adjustment.percent).rstrip('0').rstrip('.').replace('.', ',')} % ab {_de(adjustment.next_date)}. Verhandlungsspielraum prüfen.",
             "Aus den Stammdaten (Preisanpassung).")
    elif adjustment.kind in ("index", "negotiation"):
        hint("info", "Die Preisanpassung ist an einen Index bzw. eine Verhandlung gebunden – aktuelles Angebot vor der Entscheidung anfordern.",
             "Künftige Beträge sind nicht vorausberechenbar.")
    if len(partner_contracts) >= 1 and partner_name:
        hint("info", f"Mit {partner_name} bestehen {len(partner_contracts)} weitere laufende Verträge – gemeinsame Verhandlung prüfen.",
             "Aus dem Vertragsregister (gleicher Vertragspartner).")
    if contract.term_model == "auto_renewal" and inputs.renewal_period and inputs.renewal_period.unit in ("years",) and (inputs.renewal_period.value or 0) >= 2:
        hint("info", f"Die automatische Verlängerung bindet jeweils für {inputs.renewal_period.label()}. Eine kürzere Verlängerungsperiode kann verhandelt werden.",
             "Aus den Laufzeitangaben.")
    if not contract.reminder_recipient_account_id and contract.business_status in RUNNING:
        hint("check", "Keinen Erinnerungsempfänger hinterlegt – Erinnerung an die Frist geht nur an die verantwortliche Person.",
             "Feld „Erinnerung an“ ist leer.")
    if documents == 0:
        hint("check", "Kein Vertragsdokument hinterlegt – Kündigungsregelung im Original prüfen.", "Keine Dokumente am Vertrag.")

    return {
        "contract_id": str(contract.id),
        "register_number": contract.register_number,
        "short_description": contract.short_description or contract.supplier,
        "business_status": contract.business_status,
        "term_model": TERM_MODEL_LABELS.get(contract.term_model) if contract.term_model else None,
        "as_of": as_of.isoformat(),
        "urgency": level,
        "days_left": days_left,
        "cancel_by": cancel_by.isoformat() if cancel_by else None,
        "current_end": current_end.isoformat() if current_end else None,
        "next_end_if_no_action": next_end.isoformat() if next_end else None,
        "if_no_action": if_no_action,
        "annual_cost": str(annual) if annual is not None else None,
        "renewal_cost": str(renewal_cost) if renewal_cost is not None else None,
        "price_adjustment_notes": adjustment_notes,
        "partner": partner_name or contract.supplier,
        "partner_contracts": partner_contracts,
        "responsible": names.get(contract.responsible_account_id),
        "reminder_recipient": names.get(contract.reminder_recipient_account_id),
        "documents": documents,
        "review_pending": unreviewed,
        "open_deadlines": [{"due_date": item.due_date.isoformat(), "title": item.title} for item in open_deadlines],
        "decision": {
            "id": str(decision.id), "decision": decision.decision, "label": DECISION_LABELS.get(decision.decision, decision.decision),
            "status": decision.status, "note": decision.note, "by": decision.actor_display_name,
            "at": decision.created_at.isoformat() if decision.created_at else None,
        } if decision else None,
        "hints": hints,
        "explanation": terms.explanation,
    }


def upcoming_renewals(rows: list[GridRow], as_of: date, days: int) -> list[GridRow]:
    until = as_of + timedelta(days=days)
    out = [
        row for row in rows
        if row.values["business_status"] in RUNNING and row.values["cancel_by"] is not None
        and as_of - timedelta(days=30) <= row.values["cancel_by"] <= until
    ]
    return sorted(out, key=lambda row: row.values["cancel_by"])


def decision_summary(session: Session, contract_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    if not contract_ids:
        return {}
    out: dict[uuid.UUID, dict] = {}
    for row in session.scalars(
        select(ContractLifecycleDecision)
        .where(ContractLifecycleDecision.contract_id.in_(contract_ids), ContractLifecycleDecision.status.in_(OPEN_DECISION_STATUS))
        .order_by(ContractLifecycleDecision.created_at.desc())
    ).all():
        out.setdefault(row.contract_id, {"decision": row.decision, "label": DECISION_LABELS.get(row.decision, row.decision), "status": row.status})
    return out
