"""Kalenderbewusste Datum-Arithmetik (STEP 9).

Regeln:
- MONATE: additive/subtraktive Monatsverschiebung mit dokumentierter
  End-of-Monat-Regel. 31. Januar + 1 Monat → **28. Februar** (bzw. 29. im
  Schaltjahr), NICHT 3. März. Genauer: Tag wird geklemmt auf das letzte
  gültige Datum des Zielmonats; das Verhältnis „Tag >= ursprünglicher Tag"
  wird bewahrt (kein stummer Überlauf).
- JAHRE: y-months = years*12 (Schaltjahre werden über die Tagesgrenzen
  automatisch korrekt behandelt).
- Kein „1 Monat = 30 Tage", kein „1 Jahr = 365 Tage".
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Optional

from app.contracts.calculation.models import CalcDuration


def month_add(base: date, months: int) -> date:
    """Addiert `months` kalenderbewusst auf `base` (End-of-Monat-Klemmung).

    Dokumentierte Regel:
    1. Zielmonat = base.month + months (Jahr entsprechend überlaufen).
    2. Zieltages = min(base.day, last_day_of_target_month).
    Beispiele: 2024-01-31 + 1 = 2024-02-29 (Schaltjahr);
               2023-01-31 + 1 = 2023-02-28;
               2024-01-31 + 2 = 2024-03-31.
    """
    if months == 0:
        return base
    month_index = base.month - 1 + months  # 0-basiert
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(base.day, last_day)
    return date(year, month, day)


def month_sub(base: date, months: int) -> date:
    """Subtrahiert `months` kalenderbewusst (`months` >= 0)."""
    if months < 0:
        raise ValueError("month_sub erwartet months >= 0; verwende month_add fuer negative")
    return month_add(base, -months)


def add_duration(base: date, d: CalcDuration) -> date:
    """Addiert eine zusammengesetzte Dauer (Jahre, Monate, Wochen, Tage).

    Reihenfolge (deterministisch): Monate (Jahre*12 + Monate) zuerst, dann
    Tage/Wochen. Wochen und Tage sind exakte Kalendertage.
    """
    out = month_add(base, d.years * 12 + d.months)
    if d.weeks:
        out = out + timedelta(weeks=d.weeks)
    if d.days:
        out = out + timedelta(days=d.days)
    return out


def subtract_duration(base: date, d: CalcDuration) -> date:
    """Subtrahiert eine Dauer (für Fristen: „3 Monate zum Vertragsende")."""
    out = month_add(base, -(d.years * 12 + d.months))
    if d.weeks:
        out = out - timedelta(weeks=d.weeks)
    if d.days:
        out = out - timedelta(days=d.days)
    return out


def days_between(earlier: date, later: date) -> int:
    """Kalendertage zwischen zwei Daten ((later - earlier).days)."""
    return (later - earlier).days
