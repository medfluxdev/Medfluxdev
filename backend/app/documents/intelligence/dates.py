"""Deterministische deutsche Datumserkennung/-normalisierung (STEP 8B).

Unterstützte Formen (best-effort, deterministisch, OHNE Erfindung):
- "27. Januar 2018", "16. April 2025"
- Monatsnamen/übliche Abkuerzungen: Januar/Jan./Jan, Februar/Feb./Feb,
  März/Mrz/März, April/Apr./Apr, Mai, Juni/Jun./Jun, Juli/Jul./Jul.,
  August/Aug./Aug, September/Sep./Sept./Sep, Oktober/Okt./Okt,
  November/Nov./Nov, Dezember/Dez./Dez
- numerisch "13.06.2017" bzw. "13.6.2017"

WICHTIG (STEP 8B): Ereignisbasierte Daten ("ab Übergabedatum", "... bis
Unterschrift") werden NICHT in explizite Kalenderdaten umgewandelt –
sie entsprechen keiner erkennbaren Tage-/Monats-Grammatik und liefern None.

Ungültige Kalenderdaten (z. B. "32. Januar") liefern None statt Erfindung.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

_MONTH_NAMES: dict[str, int] = {}
for _month_no, _names in enumerate(
    [
        ("januar", "jan", "ja"),
        ("februar", "feb"),
        ("märz", "maerz", "mrz"),
        ("april", "apr"),
        ("mai",),
        ("juni", "jun"),
        ("juli", "jul"),
        ("august", "aug"),
        ("september", "sept", "sep"),
        ("oktober", "okt"),
        ("november", "nov"),
        ("dezember", "dez"),
    ],
    start=1,
):
    for _n in _names:
        _MONTH_NAMES[_n] = _month_no

_MONTH_TOKEN_RE = "|".join(sorted(_MONTH_NAMES, key=len, reverse=True))
_SINGLE_RE = re.compile(
    r"(?<!\d)(\d{1,2})\.\s*(" + _MONTH_TOKEN_RE + r")\.?\s*(\d{2,4})(?!\d)",
    re.IGNORECASE,
)
_NUMERIC_RE = re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{2,4})(?!\d)")


class ParsedDate:
    """Ergebnis des Parsens: Datum + erkannte Textspanne."""

    __slots__ = ("day", "month", "year", "text")

    def __init__(self, day: int, month: int, year: int, text: str) -> None:
        self.day = day
        self.month = month
        self.year = year
        self.text = text

    def to_date(self) -> Optional[date]:
        try:
            return date(self.year, self.month, self.day)
        except ValueError:
            return None

    @property
    def iso(self) -> Optional[str]:
        d = self.to_date()
        return d.isoformat() if d else None


def _expand_year(year: int) -> int:
    if year < 100:
        return 2000 + year if year <= 69 else 1900 + year
    return year


def find_dates(text: str) -> list[ParsedDate]:
    """Findet alle Treffer (einschliesslich mehrdeutiger/korumpe) im Text.

    Liefert fuer jeden Treffer auch die Original-Textspanne; enthaelt eine
    Spanne mehrere Kandidaten, werden alle zurueckgegeben (unverlustig).
    """
    hits: list[ParsedDate] = []
    for m in _SINGLE_RE.finditer(text):
        day = int(m.group(1))
        month = _MONTH_NAMES.get(m.group(2).lower())
        year = _expand_year(int(m.group(3)))
        if month is None:
            continue
        hits.append(ParsedDate(day, month, year, m.group(0)))
    for m in _NUMERIC_RE.finditer(text):
        hits.append(
            ParsedDate(
                int(m.group(1)),
                int(m.group(2)),
                _expand_year(int(m.group(3))),
                m.group(0),
            )
        )
    return hits


def parse_german_date(text: str) -> Optional[date]:
    """Parst den ERSTEN gueltigen deutschen Datumsterm (oder None).

    Args:
        text: Rohtext, der einen Datums-Term enthalten kann.
    Returns:
        Kalenderdatum oder None (kein Datum, mehrdeutig oder ungültig –
        insbesondere ereignisbasierte Formulierungen).
    """
    for hit in find_dates(text):
        d = hit.to_date()
        if d is not None:
            return d
    return None


def find_report_dates(text: str) -> list[dict]:
    """Diagnose-Ausgabe: alle Treffer ISOLIERT davon, ob sie gueltig sind."""
    return [
        {"text": h.text, "date": h.iso, "valid": h.to_date() is not None}
        for h in find_dates(text)
    ]