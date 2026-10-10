"""Stichtag "heute" in der Zeitzone der Organisation.

Berechnungen bekommen ihr Datum immer explizit uebergeben; nur Einstiegspunkte
(Routen, Tageslauf) fragen hier nach dem heutigen Kalendertag. So haengt das
Ergebnis nicht von der Zeitzone des Servers ab (z. B. kurz nach Mitternacht).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.config import settings


def today_local(now: Optional[datetime] = None) -> date:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(ZoneInfo(settings.org_timezone)).date()
