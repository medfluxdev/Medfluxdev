"""Finanzdaten eines Vertrags (H4): Pflege, Zusammenfassung, KI-Vorschlaege,
Kostenstellen-Aufteilung."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.contracts.calculation.calendar_ import month_add
from app.database.models import Contract, CostCenter
from app.database.models.finance import (
    AMOUNT_BASIS_ALLOWED,
    FINANCE_DIRECTION_ALLOWED,
    FINANCE_INTERVAL_ALLOWED,
    ContractCostAllocation,
    ContractFinanceEntry,
    ContractServiceItem,
    ContractSuggestionDismissal,
)
from app.finance.ai import finance_suggestions, service_suggestions
from app.finance.calc import EntryInput, PriceAdjustment, allocate, summarize
from app.register.service import RegisterActor, load_extracted, log_activity, term_inputs
from app.register.terms import compute_terms

ENTRY_FIELDS = (
    "direction", "label", "cost_type_code", "amount", "amount_basis", "vat_rate", "currency", "interval",
    "valid_from", "valid_to", "apply_price_adjustment", "note",
)
SERVICE_FIELDS = ("label", "service_kind", "amount", "unit", "plus_vat", "currency", "valid_from", "valid_to", "note")


class FinanceError(ValueError):
    def __init__(self, status_code: int, detail_de: str):
        super().__init__(detail_de)
        self.status_code = status_code
        self.detail_de = detail_de


# --------------------------------------------------------------------------- validation


def _decimal(value: Any, label: str, *, low: Decimal, high: Decimal) -> Decimal:
    if isinstance(value, bool) or value is None or (isinstance(value, str) and not value.strip()):
        raise FinanceError(422, f"{label}: Zahl erwartet.")
    try:
        number = Decimal(str(value).strip().replace(",", "."))
    except InvalidOperation:
        raise FinanceError(422, f"{label}: Zahl erwartet.")
    if not number.is_finite() or not low <= number <= high:
        raise FinanceError(422, f"{label}: Wert zwischen {low} und {high} erwartet.")
    return number.quantize(Decimal("0.01"))


def _date(value: Any, label: str, *, required: bool) -> Optional[date]:
    if value in (None, ""):
        if required:
            raise FinanceError(422, f"{label} ist erforderlich.")
        return None
    try:
        return value if isinstance(value, date) else date.fromisoformat(str(value))
    except ValueError:
        raise FinanceError(422, f"{label}: Datum im Format JJJJ-MM-TT erwartet.")


def _text(value: Any, label: str, max_length: int, *, required: bool = False) -> Optional[str]:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise FinanceError(422, f"{label} ist erforderlich.")
        return None
    if not isinstance(value, str):
        raise FinanceError(422, f"{label}: Text erwartet.")
    if len(value.strip()) > max_length:
        raise FinanceError(422, f"{label}: höchstens {max_length} Zeichen.")
    return value.strip()


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise FinanceError(422, f"{label}: Ja/Nein erwartet.")
    return value


def _currency(value: Any) -> str:
    text = _text(value, "Währung", 3) or "EUR"
    if len(text) != 3 or not text.isalpha():
        raise FinanceError(422, "Währung: dreistelliger Code erwartet (z. B. EUR).")
    return text.upper()


def clean_entry(values: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    unknown = [key for key in values if key not in ENTRY_FIELDS]
    if unknown:
        raise FinanceError(422, f"Unbekannte Felder: {', '.join(unknown)}.")
    out: dict[str, Any] = {}
    for key, value in values.items():
        if key == "direction":
            if value not in FINANCE_DIRECTION_ALLOWED:
                raise FinanceError(422, "Typ: Ausgaben oder Einnahmen erwartet.")
            out[key] = value
        elif key == "label":
            out[key] = _text(value, "Bezeichnung", 255, required=True)
        elif key == "cost_type_code":
            out[key] = _text(value, "Kostenart", 64)
        elif key == "amount":
            out[key] = _decimal(value, "Betrag", low=Decimal("0"), high=Decimal("999999999999"))
        elif key == "amount_basis":
            if value not in AMOUNT_BASIS_ALLOWED:
                raise FinanceError(422, "Betrag: netto oder brutto erwartet.")
            out[key] = value
        elif key == "vat_rate":
            out[key] = _decimal(value, "Steuersatz", low=Decimal("0"), high=Decimal("100"))
        elif key == "currency":
            out[key] = _currency(value)
        elif key == "interval":
            if value not in FINANCE_INTERVAL_ALLOWED:
                raise FinanceError(422, "Ungültiges Zahlungsintervall.")
            out[key] = value
        elif key == "valid_from":
            out[key] = _date(value, "Gültig ab", required=True)
        elif key == "valid_to":
            out[key] = _date(value, "Gültig bis", required=False)
        elif key == "apply_price_adjustment":
            out[key] = _bool(value, "Preisanpassung anwenden")
        elif key == "note":
            out[key] = _text(value, "Bemerkung", 5000)
    if not partial:
        for key, label in (("label", "Bezeichnung"), ("amount", "Betrag"), ("valid_from", "Gültig ab")):
            if out.get(key) is None:
                raise FinanceError(422, f"{label} ist erforderlich.")
    return out


def clean_service(values: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    unknown = [key for key in values if key not in SERVICE_FIELDS]
    if unknown:
        raise FinanceError(422, f"Unbekannte Felder: {', '.join(unknown)}.")
    out: dict[str, Any] = {}
    for key, value in values.items():
        if key == "label":
            out[key] = _text(value, "Leistung", 255, required=True)
        elif key == "service_kind":
            out[key] = _text(value, "Leistungsart", 64)
        elif key == "amount":
            out[key] = None if value in (None, "") else _decimal(value, "Betrag", low=Decimal("0"), high=Decimal("999999999999"))
        elif key == "unit":
            out[key] = _text(value, "Einheit", 64)
        elif key == "plus_vat":
            out[key] = _bool(value, "zzgl. USt.")
        elif key == "currency":
            out[key] = _currency(value)
        elif key in ("valid_from", "valid_to"):
            out[key] = _date(value, "Gültig ab" if key == "valid_from" else "Gültig bis", required=False)
        elif key == "note":
            out[key] = _text(value, "Bemerkung", 5000)
    if not partial and out.get("label") is None:
        raise FinanceError(422, "Leistung ist erforderlich.")
    return out


def _check_period(valid_from: Optional[date], valid_to: Optional[date]) -> None:
    if valid_from and valid_to and valid_to < valid_from:
        raise FinanceError(422, "„Gültig bis“ liegt vor „Gültig ab“.")


# --------------------------------------------------------------------------- read model


def _entry_payload(row: ContractFinanceEntry) -> dict:
    return {
        "id": str(row.id), "direction": row.direction, "label": row.label, "cost_type_code": row.cost_type_code,
        "amount": str(row.amount), "amount_basis": row.amount_basis, "vat_rate": str(row.vat_rate), "currency": row.currency,
        "interval": row.interval, "valid_from": row.valid_from.isoformat(),
        "valid_to": row.valid_to.isoformat() if row.valid_to else None,
        "apply_price_adjustment": row.apply_price_adjustment, "note": row.note, "origin": row.origin,
        "source_key": row.source_key, "created_by_name": row.created_by_name,
    }


def _service_payload(row: ContractServiceItem) -> dict:
    return {
        "id": str(row.id), "label": row.label, "service_kind": row.service_kind,
        "amount": str(row.amount) if row.amount is not None else None, "unit": row.unit, "plus_vat": row.plus_vat,
        "currency": row.currency, "valid_from": row.valid_from.isoformat() if row.valid_from else None,
        "valid_to": row.valid_to.isoformat() if row.valid_to else None, "note": row.note, "origin": row.origin,
        "source_key": row.source_key,
    }


def contract_end(contract: Contract, as_of: date) -> Optional[date]:
    terms = compute_terms(term_inputs(contract), as_of)
    return terms.actual_end or terms.possible_end


def price_adjustment(contract: Contract, as_of: date) -> tuple[PriceAdjustment, list[str]]:
    notes: list[str] = []
    next_date = contract.price_adjustment_next_date
    interval = contract.price_adjustment_interval_months or 12
    if contract.price_adjustment_kind == "percent" and next_date is None and contract.term_start_date:
        anniversary = contract.term_start_date
        while anniversary <= as_of:
            anniversary = month_add(anniversary, interval)
        next_date = anniversary
        notes.append(f"Anpassungsdatum angenommen: {next_date.strftime('%d.%m.%Y')} (Vertragsjahrestag) – bitte in den Stammdaten bestätigen.")
    return PriceAdjustment(
        kind=contract.price_adjustment_kind,
        percent=contract.price_adjustment_percent,
        next_date=next_date,
        interval_months=interval,
    ), notes


def _entries(session: Session, contract_id: uuid.UUID) -> list[ContractFinanceEntry]:
    return list(session.scalars(
        select(ContractFinanceEntry)
        .where(ContractFinanceEntry.contract_id == contract_id)
        .order_by(ContractFinanceEntry.direction, ContractFinanceEntry.valid_from, ContractFinanceEntry.created_at)
    ).all())


def entry_inputs(rows: list[ContractFinanceEntry]) -> list[EntryInput]:
    return [
        EntryInput(
            direction=row.direction, amount=row.amount, amount_basis=row.amount_basis, vat_rate=row.vat_rate,
            interval=row.interval, valid_from=row.valid_from, valid_to=row.valid_to, currency=row.currency,
            apply_price_adjustment=row.apply_price_adjustment, ref=str(row.id),
        )
        for row in rows
    ]


def finance_summary(session: Session, contract: Contract, as_of: date) -> list[dict]:
    rows = _entries(session, contract.id)
    if not rows:
        return []
    adjustment, notes = price_adjustment(contract, as_of)
    summaries = summarize(entry_inputs(rows), as_of=as_of, contract_end=contract_end(contract, as_of), adjustment=adjustment)
    out = []
    for summary in summaries:
        data = summary.as_dict()
        data["notes"] = notes + data["notes"]
        out.append(data)
    return out


def annual_run_rate(session: Session, contract: Contract, as_of: date) -> Optional[dict]:
    """Jaehrliche Kosten aus gepflegten Finanzdaten (Hauptwaehrung), sonst None."""
    rows = [row for row in _entries(session, contract.id) if row.direction == "expense"]
    if not rows:
        return None
    adjustment, _ = price_adjustment(contract, as_of)
    summaries = summarize(entry_inputs(rows), as_of=as_of, contract_end=contract_end(contract, as_of), adjustment=adjustment)
    main = max(summaries, key=lambda item: item.expense.annual_run_rate.net)
    rate = main.expense.annual_run_rate.as_dict()
    return {"currency": main.currency, "net": rate["net"], "gross": rate["gross"]}


def refresh_maintained_cost(session: Session, contract: Contract, as_of: Optional[date] = None) -> None:
    """Aktualisiert den Zwischenspeicher der gepflegten Jahreskosten am Vertrag."""
    as_of = as_of or date.today()
    rate = annual_run_rate(session, contract, as_of)
    contract.maintained_annual_cost = Decimal(rate["net"]) if rate else None
    contract.maintained_annual_currency = rate["currency"] if rate else None
    contract.maintained_cost_as_of = as_of if rate else None
    session.flush()


def refresh_all_maintained_costs(session: Session, as_of: date, organization_id: Optional[uuid.UUID] = None) -> int:
    stmt = select(Contract).where(
        or_(
            Contract.id.in_(select(ContractFinanceEntry.contract_id)),
            Contract.maintained_annual_cost.is_not(None),
        )
    )
    if organization_id is not None:
        stmt = stmt.where(Contract.organization_id == organization_id)
    count = 0
    for contract in session.scalars(stmt).all():
        refresh_maintained_cost(session, contract, as_of)
        count += 1
    return count


def _allocations(session: Session, contract: Contract, summaries: list[dict]) -> list[dict]:
    rows = session.execute(
        select(ContractCostAllocation, CostCenter)
        .join(CostCenter, CostCenter.id == ContractCostAllocation.cost_center_id)
        .where(ContractCostAllocation.contract_id == contract.id)
        .order_by(ContractCostAllocation.share_percent.desc())
    ).all()
    shares = [(str(row.cost_center_id), row.share_percent) for row, _ in rows]
    main = next((item for item in summaries if item["currency"] == "EUR"), summaries[0] if summaries else None)
    yearly = {key: value for key, value in allocate(Decimal(main["expense"]["annual_run_rate"]["net"]), shares)} if main else {}
    return [
        {
            "cost_center_id": str(row.cost_center_id), "code": center.code, "name": center.name,
            "share_percent": str(row.share_percent), "recharge_mode": row.recharge_mode,
            "annual_net": str(yearly[str(row.cost_center_id)]) if str(row.cost_center_id) in yearly else None,
        }
        for row, center in rows
    ]


def _dismissed(session: Session, contract_id: uuid.UUID) -> set[tuple[str, str]]:
    return set(session.execute(
        select(ContractSuggestionDismissal.scope, ContractSuggestionDismissal.suggestion_key)
        .where(ContractSuggestionDismissal.contract_id == contract_id)
    ).all())


def accepted_extraction(session: Session, contract: Contract):
    if contract.accepted_extraction_id is None:
        return None
    return load_extracted(session, contract.accepted_extraction_id)


def suggestions(session: Session, contract: Contract) -> dict[str, list[dict]]:
    extracted = accepted_extraction(session, contract)
    if extracted is None:
        return {"entries": [], "services": []}
    start = contract.term_start_date or getattr(extracted.dates.start_date, "date", None) or date.today().replace(day=1)
    dismissed = _dismissed(session, contract.id)
    used_entries = {row.source_key for row in _entries(session, contract.id) if row.source_key}
    used_services = set(session.scalars(
        select(ContractServiceItem.source_key).where(
            ContractServiceItem.contract_id == contract.id, ContractServiceItem.source_key.is_not(None)
        )
    ).all())
    return {
        "entries": [
            item for item in finance_suggestions(extracted, start=start)
            if item["key"] not in used_entries and ("finance", item["key"]) not in dismissed
        ],
        "services": [
            item for item in service_suggestions(extracted)
            if item["key"] not in used_services and ("service", item["key"]) not in dismissed
        ],
    }


def finance_payload(session: Session, contract: Contract, as_of: Optional[date] = None) -> dict:
    as_of = as_of or date.today()
    summaries = finance_summary(session, contract, as_of)
    services = session.scalars(
        select(ContractServiceItem).where(ContractServiceItem.contract_id == contract.id)
        .order_by(ContractServiceItem.valid_from.nullsfirst(), ContractServiceItem.label)
    ).all()
    return {
        "contract_id": str(contract.id),
        "as_of": as_of.isoformat(),
        "entries": [_entry_payload(row) for row in _entries(session, contract.id)],
        "summaries": summaries,
        "services": [_service_payload(row) for row in services],
        "allocations": _allocations(session, contract, summaries),
        "primary_cost_center_id": str(contract.cost_center_id) if contract.cost_center_id else None,
        "price_adjustment": {
            "kind": contract.price_adjustment_kind,
            "percent": str(contract.price_adjustment_percent) if contract.price_adjustment_percent is not None else None,
            "index_name": contract.price_adjustment_index_name,
            "next_date": contract.price_adjustment_next_date.isoformat() if contract.price_adjustment_next_date else None,
            "interval_months": contract.price_adjustment_interval_months,
        },
        "suggestions": suggestions(session, contract),
    }


# --------------------------------------------------------------------------- write


def create_entry(session: Session, *, contract: Contract, actor: RegisterActor, values: dict[str, Any],
                 origin: str = "manual", source_key: Optional[str] = None) -> ContractFinanceEntry:
    clean = clean_entry(values, partial=False)
    _check_period(clean.get("valid_from"), clean.get("valid_to"))
    clean.setdefault("direction", "expense")
    clean.setdefault("amount_basis", "net")
    clean.setdefault("vat_rate", Decimal("19.00"))
    clean.setdefault("interval", "monthly")
    row = ContractFinanceEntry(
        organization_id=contract.organization_id, contract_id=contract.id, origin=origin, source_key=source_key,
        extraction_id=contract.accepted_extraction_id if source_key else None, created_by_name=actor.display_name, **clean,
    )
    session.add(row)
    session.flush()
    refresh_maintained_cost(session, contract)
    log_activity(session, actor, contract.id, "finance.entry_created", {
        "entry_id": str(row.id), "label": row.label, "amount": str(row.amount), "direction": row.direction, "origin": origin,
    })
    return row


def _own(session: Session, model, contract: Contract, row_id: uuid.UUID):
    row = session.get(model, row_id)
    if row is None or row.contract_id != contract.id:
        raise FinanceError(404, "Eintrag nicht gefunden.")
    return row


def update_entry(session: Session, *, contract: Contract, actor: RegisterActor, entry_id: uuid.UUID, values: dict[str, Any]) -> None:
    row = _own(session, ContractFinanceEntry, contract, entry_id)
    clean = clean_entry(values, partial=True)
    _check_period(clean.get("valid_from", row.valid_from), clean.get("valid_to", row.valid_to))
    diffs = {}
    for key, value in clean.items():
        if getattr(row, key) != value:
            diffs[key] = {"before": str(getattr(row, key)), "after": str(value)}
            setattr(row, key, value)
    if diffs:
        log_activity(session, actor, contract.id, "finance.entry_updated", {"entry_id": str(row.id), "fields": diffs})
    session.flush()
    refresh_maintained_cost(session, contract)


def delete_entry(session: Session, *, contract: Contract, actor: RegisterActor, entry_id: uuid.UUID) -> None:
    row = _own(session, ContractFinanceEntry, contract, entry_id)
    log_activity(session, actor, contract.id, "finance.entry_deleted", {"entry": {k: str(v) for k, v in _entry_payload(row).items()}})
    session.delete(row)
    session.flush()


def create_service(session: Session, *, contract: Contract, actor: RegisterActor, values: dict[str, Any],
                   origin: str = "manual", source_key: Optional[str] = None) -> ContractServiceItem:
    clean = clean_service(values, partial=False)
    _check_period(clean.get("valid_from"), clean.get("valid_to"))
    row = ContractServiceItem(
        organization_id=contract.organization_id, contract_id=contract.id, origin=origin, source_key=source_key,
        extraction_id=contract.accepted_extraction_id if source_key else None, **clean,
    )
    session.add(row)
    session.flush()
    log_activity(session, actor, contract.id, "finance.service_created", {"service_id": str(row.id), "label": row.label, "origin": origin})
    return row


def update_service(session: Session, *, contract: Contract, actor: RegisterActor, service_id: uuid.UUID, values: dict[str, Any]) -> None:
    row = _own(session, ContractServiceItem, contract, service_id)
    clean = clean_service(values, partial=True)
    _check_period(clean.get("valid_from", row.valid_from), clean.get("valid_to", row.valid_to))
    for key, value in clean.items():
        setattr(row, key, value)
    log_activity(session, actor, contract.id, "finance.service_updated", {"service_id": str(row.id), "fields": sorted(clean)})
    session.flush()


def delete_service(session: Session, *, contract: Contract, actor: RegisterActor, service_id: uuid.UUID) -> None:
    row = _own(session, ContractServiceItem, contract, service_id)
    log_activity(session, actor, contract.id, "finance.service_deleted", {"service_id": str(row.id), "label": row.label})
    session.delete(row)
    session.flush()
    refresh_maintained_cost(session, contract)


def accept_suggestion(session: Session, *, contract: Contract, actor: RegisterActor, scope: str, key: str,
                      overrides: Optional[dict[str, Any]] = None) -> None:
    available = suggestions(session, contract)
    pool = available["entries"] if scope == "finance" else available["services"] if scope == "service" else None
    if pool is None:
        raise FinanceError(404, "Unbekannter Bereich.")
    match = next((item for item in pool if item["key"] == key), None)
    if match is None:
        raise FinanceError(404, "Vorschlag nicht (mehr) verfügbar.")
    values = {**match["values"], **(overrides or {})}
    if scope == "finance":
        create_entry(session, contract=contract, actor=actor, values=values, origin="ai_confirmed", source_key=key)
    else:
        create_service(session, contract=contract, actor=actor, values=values, origin="ai_confirmed", source_key=key)


def dismiss_suggestion(session: Session, *, contract: Contract, actor: RegisterActor, scope: str, key: str) -> None:
    if scope not in ("finance", "service"):
        raise FinanceError(404, "Unbekannter Bereich.")
    exists = session.scalar(select(ContractSuggestionDismissal.id).where(
        ContractSuggestionDismissal.contract_id == contract.id,
        ContractSuggestionDismissal.scope == scope,
        ContractSuggestionDismissal.suggestion_key == key,
    ))
    if exists is None:
        session.add(ContractSuggestionDismissal(
            organization_id=contract.organization_id, contract_id=contract.id, scope=scope,
            suggestion_key=key, dismissed_by_name=actor.display_name,
        ))
        log_activity(session, actor, contract.id, "finance.suggestion_dismissed", {"scope": scope, "key": key})
    session.flush()


def set_allocations(session: Session, *, contract: Contract, actor: RegisterActor, items: list[dict[str, Any]]) -> None:
    """Ersetzt die Aufteilung; Summe muss 100 % ergeben (oder leer sein)."""
    clean: dict[uuid.UUID, tuple[Decimal, Optional[str]]] = {}
    for item in items:
        try:
            center_id = uuid.UUID(str(item.get("cost_center_id")))
        except ValueError:
            raise FinanceError(422, "Ungültige Kostenstelle.")
        center = session.get(CostCenter, center_id)
        if center is None or center.organization_id != contract.organization_id or not center.is_active:
            raise FinanceError(422, "Kostenstelle nicht verfügbar.")
        if contract.hospital_id is not None and center.hospital_id != contract.hospital_id:
            raise FinanceError(422, "Kostenstelle gehört zu einem anderen Krankenhaus.")
        if center_id in clean:
            raise FinanceError(422, "Jede Kostenstelle nur einmal angeben.")
        share = _decimal(item.get("share_percent"), "Anteil", low=Decimal("0.01"), high=Decimal("100"))
        clean[center_id] = (share, _text(item.get("recharge_mode"), "Weiterbelastung", 64))
    if clean and sum(share for share, _ in clean.values()) != Decimal("100.00"):
        raise FinanceError(422, "Die Anteile müssen zusammen 100 % ergeben.")
    existing = {
        row.cost_center_id: row for row in session.scalars(
            select(ContractCostAllocation).where(ContractCostAllocation.contract_id == contract.id)
        ).all()
    }
    before = {str(key): str(row.share_percent) for key, row in existing.items()}
    for center_id, row in existing.items():
        if center_id not in clean:
            session.delete(row)
    session.flush()
    for center_id, (share, mode) in clean.items():
        row = existing.get(center_id)
        if row is None:
            row = ContractCostAllocation(organization_id=contract.organization_id, contract_id=contract.id, cost_center_id=center_id)
            session.add(row)
        row.share_percent = share
        row.recharge_mode = mode
    if clean:
        contract.cost_center_id = max(clean.items(), key=lambda item: item[1][0])[0]
    log_activity(session, actor, contract.id, "finance.allocations_updated", {
        "before": before, "after": {str(key): str(value[0]) for key, value in clean.items()},
    })
    session.flush()


def export_csv(session: Session, contract: Contract, directions: set[str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Vertragsnr.", "Typ", "Bezeichnung", "Kostenart", "Betrag", "Basis", "Steuer %", "Währung",
                     "Intervall", "Gültig ab", "Gültig bis", "Herkunft", "Bemerkung"])
    for row in _entries(session, contract.id):
        if row.direction not in directions:
            continue
        writer.writerow([
            contract.register_number or "", "Ausgaben" if row.direction == "expense" else "Einnahmen", row.label,
            row.cost_type_code or "", str(row.amount).replace(".", ","), "netto" if row.amount_basis == "net" else "brutto",
            str(row.vat_rate).replace(".", ","), row.currency, row.interval, row.valid_from.strftime("%d.%m.%Y"),
            row.valid_to.strftime("%d.%m.%Y") if row.valid_to else "", row.origin, (row.note or "").replace("\n", " "),
        ])
    return buffer.getvalue()
