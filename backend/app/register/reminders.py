"""Erinnerungen vor Kündigungstermin bzw. Vertragsende.

Erste Erinnerung: `contract.reminder_lead_months` (leer = Standard DEFAULT_REMINDER_LEAD_MONTHS).
Weitere Erinnerungen: `contract.reminder_extra_leads` (Liste aus Wert + Einheit), jede genau einmal.
Rein: keine DB, kein `now()`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from app.contracts.calculation.calendar_ import month_add

DEFAULT_REMINDER_LEAD_MONTHS = 4
UNITS: dict[str, tuple[str, str, int]] = {
    # Einheit: (Singular, Plural, Höchstwert)
    "days": ("Tag", "Tage", 365),
    "weeks": ("Woche", "Wochen", 104),
    "months": ("Monat", "Monate", 60),
}
MAX_EXTRA = 10


def normalize_leads(raw: Any) -> list[dict[str, Any]]:
    """Weitere Erinnerungen prüfen: [{"value": 1, "unit": "months"}, …], ohne Doppelte, früheste zuerst."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("Weitere Erinnerungen: Liste erwartet.")
    if len(raw) > MAX_EXTRA:
        raise ValueError(f"Höchstens {MAX_EXTRA} weitere Erinnerungen.")
    seen: set[tuple[int, str]] = set()
    result = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Weitere Erinnerungen: ungültiger Eintrag.")
        unit = item.get("unit")
        if unit not in UNITS:
            raise ValueError("Weitere Erinnerungen: Einheit Tage, Wochen oder Monate.")
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= UNITS[unit][2]:
            raise ValueError(f"Weitere Erinnerungen: 1 bis {UNITS[unit][2]} {UNITS[unit][1]}.")
        if (value, unit) in seen:
            continue
        seen.add((value, unit))
        result.append({"value": value, "unit": unit})
    # Weiteste Vorlaufzeit zuerst (z. B. 2 Monate, 2 Wochen, 3 Tage).
    reference = date(2000, 1, 1)
    return sorted(result, key=lambda lead: lead_date(reference, lead))


def lead_date(anchor: date, lead: dict[str, Any]) -> date:
    value, unit = lead["value"], lead["unit"]
    if unit == "months":
        return month_add(anchor, -value)
    return anchor - timedelta(days=value * (7 if unit == "weeks" else 1))


def lead_label(lead: dict[str, Any]) -> str:
    singular, plural, _ = UNITS[lead["unit"]]
    return f"{lead['value']} {singular if lead['value'] == 1 else plural}"


def first_reminder(anchor: Optional[date], lead_months: Optional[int]) -> Optional[date]:
    if anchor is None:
        return None
    lead = DEFAULT_REMINDER_LEAD_MONTHS if lead_months is None else lead_months
    if lead < 0:
        return None
    return min(anchor, month_add(anchor, -lead))


def extra_reminders(anchor: Optional[date], leads: Any, first: Optional[date]) -> list[date]:
    """Weitere Erinnerungstermine (aufsteigend), nur nach der ersten und nicht nach dem Stichtag."""
    if anchor is None:
        return []
    dates = {lead_date(anchor, lead) for lead in normalize_leads(leads or [])}
    return sorted(day for day in dates if day <= anchor and (first is None or day > first))
