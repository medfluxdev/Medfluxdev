"""KI-Vorschlaege fuer Finanzeintraege und Leistungskatalog (deterministisch
aus der akzeptierten Extraktion).

Nur Betraege, die die Extraktion explizit liefert, werden vorgeschlagen.
Fehlt die Steuerbasis oder der Steuersatz, wird netto/19 % nur als
gekennzeichnete Annahme vorgeschlagen – der Mensch bestaetigt oder korrigiert.
Nichts wird ohne Bestaetigung uebernommen.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from app.contracts.calculation.calendar_ import month_add
from app.models.contract import Contract as ExtractedContract
from app.models.values import Money

_PERIOD_TO_INTERVAL = {
    "monthly": "monthly", "month": "monthly", "monatlich": "monthly",
    "quarterly": "quarterly", "quartal": "quarterly", "quartalsweise": "quarterly",
    "semi_annual": "semi_annual", "halbjaehrlich": "semi_annual", "halbjährlich": "semi_annual",
    "annual": "annual", "yearly": "annual", "jaehrlich": "annual", "jährlich": "annual",
    "once": "once", "one_time": "once", "einmalig": "once",
}
_RECURRING_FIELDS = (
    ("monthly_cost", "monthly", "Wiederkehrende Kosten (monatlich)"),
    ("quarterly_cost", "quarterly", "Wiederkehrende Kosten (quartalsweise)"),
    ("semi_annual_cost", "semi_annual", "Wiederkehrende Kosten (halbjährlich)"),
    ("annual_cost", "annual", "Wiederkehrende Kosten (jährlich)"),
)
_ONCE_FIELDS = (
    ("one_time_cost", "Einmalige Kosten"),
    ("setup_installation_cost", "Einrichtung / Installation"),
)
_SERVICE_FIELDS = (
    ("hourly_rate", "Stundensatz", "stundensatz", "pro Stunde"),
    ("travel_cost", "Reisekosten", "reisekosten", None),
    ("material_cost", "Material", "material", None),
    ("spare_parts_cost", "Ersatzteile", "material", None),
)


def _decimal(money: Optional[Money]) -> Optional[Decimal]:
    if money is None or money.amount is None:
        return None
    return Decimal(str(money.amount)).quantize(Decimal("0.01"))


def _interval(money: Money, default: str) -> str:
    period = (money.period or "").strip().lower()
    return _PERIOD_TO_INTERVAL.get(period, default)


def _tax(extracted: ExtractedContract) -> tuple[str, Decimal, list[str]]:
    assumptions: list[str] = []
    basis = (extracted.costs.tax_basis or "").strip().lower()
    if basis not in ("net", "gross"):
        basis = "net"
        assumptions.append("Netto angenommen (Steuerbasis im Vertrag nicht eindeutig)")
    rate = extracted.costs.tax_rate_percent
    if rate is None:
        assumptions.append("19 % MwSt. angenommen")
        return basis, Decimal("19.00"), assumptions
    return basis, Decimal(str(rate)).quantize(Decimal("0.01")), assumptions


def _currency(money: Money, extracted: ExtractedContract) -> str:
    return (money.currency or extracted.costs.default_currency or "EUR").upper()[:3]


def finance_suggestions(extracted: ExtractedContract, *, start: date) -> list[dict[str, Any]]:
    costs = extracted.costs
    basis, vat_rate, assumptions = _tax(extracted)
    out: list[dict[str, Any]] = []

    def add(key: str, label: str, money: Money, interval: str, valid_from: date, valid_to: Optional[date], adjust: bool) -> None:
        amount = _decimal(money)
        if amount is None:
            return
        out.append({
            "key": key,
            "values": {
                "direction": "expense",
                "label": label,
                "amount": str(amount),
                "amount_basis": basis,
                "vat_rate": str(vat_rate),
                "currency": _currency(money, extracted),
                "interval": interval,
                "valid_from": valid_from.isoformat(),
                "valid_to": valid_to.isoformat() if valid_to else None,
                "apply_price_adjustment": adjust,
            },
            "assumptions": list(assumptions),
            "source_field": key,
        })

    scheduled = [item for item in costs.scheduled_prices if item.amount.amount is not None and item.period_index]
    if scheduled:
        for item in sorted(scheduled, key=lambda row: row.period_index):
            year_start = month_add(start, 12 * (item.period_index - 1))
            year_end = month_add(start, 12 * item.period_index) - timedelta(days=1)
            label = item.period_label or f"{item.period_index}. Vertragsjahr"
            add(f"costs.scheduled_prices.{item.period_index}", f"Preisstufe {label}", item.amount,
                _interval(item.amount, "annual"), year_start, year_end, False)
    else:
        for field, default_interval, label in _RECURRING_FIELDS:
            money = getattr(costs, field)
            if money is not None and money.amount is not None:
                add(f"costs.{field}", label, money, _interval(money, default_interval), start, None, True)
                break
        else:
            fee = costs.maintenance_fee
            if fee is not None and fee.amount is not None and fee.period:
                add("costs.maintenance_fee", "Wartungspauschale", fee, _interval(fee, "annual"), start, None, True)
    for field, label in _ONCE_FIELDS:
        money = getattr(costs, field)
        if money is not None and money.amount is not None:
            add(f"costs.{field}", label, money, "once", start, None, False)
    return out


def service_suggestions(extracted: ExtractedContract) -> list[dict[str, Any]]:
    costs = extracted.costs
    out: list[dict[str, Any]] = []
    for index, charge in enumerate(costs.variable_charges):
        amount = _decimal(charge.amount)
        if amount is None:
            continue
        out.append({
            "key": f"costs.variable_charges.{index}",
            "values": {
                "label": (charge.label or "Leistung")[:255],
                "service_kind": "kosten",
                "amount": str(amount),
                "unit": charge.unit,
                "plus_vat": (costs.tax_basis or "net") != "gross",
                "currency": _currency(charge.amount, extracted),
                "note": charge.condition,
            },
            "source_field": f"costs.variable_charges.{index}",
        })
    for field, label, kind, unit in _SERVICE_FIELDS:
        money = getattr(costs, field)
        amount = _decimal(money)
        if amount is None:
            continue
        out.append({
            "key": f"costs.{field}",
            "values": {
                "label": label, "service_kind": kind, "amount": str(amount), "unit": unit,
                "plus_vat": (costs.tax_basis or "net") != "gross", "currency": _currency(money, extracted), "note": None,
            },
            "source_field": f"costs.{field}",
        })
    return out


_PERCENT = re.compile(r"(\d{1,2}(?:[.,]\d{1,3})?)\s*(?:%|prozent)", re.IGNORECASE)
_YEARLY = re.compile(r"(jährlich|jaehrlich|pro jahr|p\.\s?a\.|je vertragsjahr|jedes jahr)", re.IGNORECASE)
_INDEX = re.compile(r"(verbraucherpreisindex|vpi|preisindex|lohnindex|tariflohn|index)", re.IGNORECASE)
_FIXED = re.compile(r"(festpreis|preisbindung|keine preisanpassung|preise sind fest|fest für die laufzeit)", re.IGNORECASE)
_NEGOTIATION = re.compile(r"(nach vereinbarung|neu verhandelt|verhandlung)", re.IGNORECASE)


def price_adjustment_from_text(text: Optional[str]) -> Optional[dict[str, Any]]:
    """Eindeutige Preisanpassungsart aus dem Klauseltext; bei Mehrdeutigkeit None."""
    if not text or not text.strip():
        return None
    percent = _PERCENT.search(text)
    candidates = []
    if percent and _YEARLY.search(text):
        candidates.append({"kind": "percent", "percent": Decimal(percent.group(1).replace(",", ".")), "interval_months": 12})
    index = _INDEX.search(text)
    if index:
        candidates.append({"kind": "index", "index_name": index.group(1)})
    if _FIXED.search(text):
        candidates.append({"kind": "fixed"})
    if _NEGOTIATION.search(text) and not candidates:
        candidates.append({"kind": "negotiation"})
    return candidates[0] if len(candidates) == 1 else None
