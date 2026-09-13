"""Deterministic safety gate for critical claims not suited to scalar AI verification.

The gate never derives replacement values. A populated claim must have a source
unit that proves its value *and* its field semantics; otherwise it is surfaced
for human review. This closes gaps for list-valued prices/services and remaining
termination/payment/SLA fields without expanding trust in model output.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from app.models.contract import Contract


_NEGATION_RE = re.compile(r"\b(?:nicht|kein(?:e|en|er)?|ohne|ausgeschlossen|nicht\s+enthalten)\b", re.I)

_SERVICE_TERMS = {
    "inspection": ("inspektion", "sichtprüfung", "sichtpruefung"),
    "calibration": ("kalibrier", "justier"),
    "remote_support": ("fernwartung", "ferndiagnose", "remote support"),
    "technical_support": ("technischer support", "hotline", "helpdesk", "anwendersupport"),
    "consumables_included": ("verbrauchsmaterial", "verbrauchsteil", "consumables"),
}

_MONEY_LABELS = {
    "setup_installation_cost": re.compile(r"installation|inbetriebnahme|aufbau|setup", re.I),
    "travel_cost": re.compile(r"fahrtkosten|reisekosten|anfahr|travel", re.I),
    "material_cost": re.compile(r"materialkosten|material", re.I),
    "spare_parts_cost": re.compile(r"ersatzteil|verschleißteil|verschleissteil|spare\s+part", re.I),
    "discounts": re.compile(r"rabatt|nachlass|discount", re.I),
}

_SERVICE_HOURS_RE = re.compile(r"servicezeit|servicezeiten|geschäftszeit|geschaeftszeit|erreichbar|supportzeiten", re.I)

_CURRENCY_MARKERS = {
    "EUR": ("eur", "€", "euro"),
    "USD": ("usd", "$", "us-dollar", "us dollar"),
    "CHF": ("chf", "fr.", "franken"),
    "GBP": ("gbp", "£", "pound"),
}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _texts(units: Iterable[object]) -> list[str]:
    return [
        text
        for unit in units
        if (text := str(getattr(unit, "text", "") or "").strip())
    ]


def _exactish(text: str, value: Any) -> bool:
    needle = _norm(value)
    return bool(needle) and needle in _norm(text)


def _amount(value: Any) -> float | None:
    if value is None:
        return None
    amount = getattr(value, "amount", None)
    if isinstance(value, dict):
        amount = value.get("amount")
    try:
        return float(amount) if amount is not None else None
    except (TypeError, ValueError):
        return None


def _contains_number(text: str, number: float | int) -> bool:
    variants = {str(number).replace(".", ","), str(number)}
    if float(number).is_integer():
        i = int(number)
        variants.update({str(i), f"{i:,}".replace(",", "."), f"{i:,}".replace(",", " ")})
    compact = text.replace(" ", "")
    return any(v.replace(" ", "") in compact for v in variants)


def _money_supported(texts: list[str], value: Any, label: re.Pattern[str]) -> bool:
    amount = _amount(value)
    if amount is None:
        return False
    return any(label.search(text) and _contains_number(text, amount) for text in texts)


def _bool_supported(texts: list[str], terms: tuple[str, ...], expected: bool) -> bool:
    for text in texts:
        low = text.casefold()
        positions = [low.find(t.casefold()) for t in terms if low.find(t.casefold()) >= 0]
        if not positions:
            continue
        idx = min(positions)
        window = text[max(0, idx - 90): min(len(text), idx + 160)]
        negative = bool(_NEGATION_RE.search(window))
        if expected and not negative:
            return True
        if not expected and negative:
            return True
    return False


def _time_supported(texts: list[str], value: Any, label: re.Pattern[str]) -> bool:
    original = str(getattr(value, "original_text", None) or "").strip()
    number = getattr(value, "value", None)
    unit = getattr(getattr(value, "unit", None), "value", getattr(value, "unit", None))
    unit_words = {
        "hours": ("stunde", "stunden", "hour", "hours"),
        "days": ("tag", "tage", "days"),
        "weeks": ("woche", "wochen", "weeks"),
        "months": ("monat", "monate", "months"),
    }.get(str(unit), (str(unit),) if unit else ())
    for text in texts:
        if not label.search(text):
            continue
        if original and _exactish(text, original):
            return True
        if number is not None and _contains_number(text, number) and any(w.casefold() in text.casefold() for w in unit_words):
            return True
    return False


def _currency_supported(texts: list[str], currency: Any) -> bool:
    code = str(currency or "").strip().upper()
    if not code:
        return True
    markers = _CURRENCY_MARKERS.get(code, (code.casefold(),))
    for text in texts:
        low = text.casefold()
        if any(marker.casefold() in low for marker in markers):
            return True
    return False


def _mark_section(section: Any) -> None:
    ev = getattr(section, "evidence", None)
    if ev is not None:
        ev.requires_review = True
        if ev.confidence is None or ev.confidence > 0.5:
            ev.confidence = 0.5


def _check_exact(issues: list[str], texts: list[str], field: str, value: Any, section: Any) -> None:
    if value in (None, ""):
        return
    if any(_exactish(text, value) for text in texts):
        return
    _mark_section(section)
    issues.append(f"{field}: Wert nicht wörtlich in der Quelle gestützt")


def verify_residual_critical_claims(contract: Contract, units: Iterable[object]) -> list[str]:
    texts = _texts(units)
    issues: list[str] = []

    if contract.costs.default_currency:
        if not _currency_supported(texts, contract.costs.default_currency):
            _mark_section(contract.costs)
            issues.append(
                "costs.default_currency: Währung nicht in der Quelle gestützt"
            )

    # Event/termination/payment clauses: exact text is safer than fuzzy semantic
    # inference. If normalization changed the wording enough to lose the source,
    # human review is preferred.
    for field, value in (
        ("dates.start_condition", contract.dates.start_condition),
        ("dates.end_condition", contract.dates.end_condition),
        ("termination.cancellation_condition", contract.termination.cancellation_condition),
        ("termination.cancellation_to_contract_end", contract.termination.cancellation_to_contract_end),
        ("termination.extraordinary_termination", contract.termination.extraordinary_termination),
    ):
        section = contract.dates if field.startswith("dates.") else contract.termination
        _check_exact(issues, texts, field, value, section)

    for field, value in (
        ("costs.price_indexation", contract.costs.price_indexation),
        ("payment.payment_terms", contract.payment.payment_terms),
    ):
        section = contract.costs if field.startswith("costs.") else contract.payment
        _check_exact(issues, texts, field, value, section)

    for field, label in _MONEY_LABELS.items():
        value = getattr(contract.costs, field)
        if value is None or _amount(value) is None:
            continue
        if not _money_supported(texts, value, label):
            _mark_section(contract.costs)
            issues.append(f"costs.{field}: Betrag nicht feldspezifisch in der Quelle gestützt")

    for field, terms in _SERVICE_TERMS.items():
        value = getattr(contract.services, field)
        if value is None:
            continue
        if not _bool_supported(texts, terms, bool(value)):
            _mark_section(contract.services)
            issues.append(f"services.{field}: Bool-Wert nicht explizit in der Quelle gestützt")

    if contract.sla.service_hours is not None and getattr(contract.sla.service_hours, "value", None) is not None:
        if not _time_supported(texts, contract.sla.service_hours, _SERVICE_HOURS_RE):
            _mark_section(contract.sla)
            issues.append("sla.service_hours: Zeitwert nicht feldspezifisch in der Quelle gestützt")

    _check_exact(issues, texts, "sla.sla_notes", contract.sla.sla_notes, contract.sla)

    # Scheduled prices: each explicit amount must be tied to its period label in
    # at least one source unit. A bare repeated amount is not enough.
    for index, price in enumerate(contract.costs.scheduled_prices):
        amount = _amount(price.amount)
        if amount is None:
            continue
        label = str(price.period_label or "").strip()
        supported = any(
            _contains_number(text, amount)
            and (not label or _exactish(text, label))
            for text in texts
        )
        if not supported:
            _mark_section(contract.costs)
            issues.append(
                f"costs.scheduled_prices[{index}]: Preisstufe nicht mit Zeitraum in der Quelle gestützt"
            )

    # Variable charges need both the amount and the semantic label/unit; this
    # prevents a fixed fee elsewhere from being mistaken for a per-call charge.
    for index, charge in enumerate(contract.costs.variable_charges):
        amount = _amount(charge.amount)
        if amount is None:
            continue
        label = str(charge.label or "").strip()
        unit = str(charge.unit or "").strip()
        supported = any(
            _contains_number(text, amount)
            and (not label or _exactish(text, label))
            and (not unit or _exactish(text, unit))
            for text in texts
        )
        if not supported:
            _mark_section(contract.costs)
            issues.append(
                f"costs.variable_charges[{index}]: variable Position nicht feldspezifisch gestützt"
            )

    return issues
