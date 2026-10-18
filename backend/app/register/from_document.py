"""Angabe aus einer markierten Stelle des Vertragsdokuments uebernehmen
(Plan ERNEUT_ERFASSEN_PLAN_20261011, Phase 4).

Die Person markiert Text auf einer Seite, so wie MedFlux sie gelesen hat (auch OCR).
Der Code prueft, dass die Stelle wirklich auf dieser Seite steht, liest den Wert
deterministisch (Datum, Dauer, Zahl, Prozent, Kuendigungstermin, Text) und speichert
ihn als von Hand gepflegten Wert mit Fundstelle. Kein Modell, nichts geraten:
mehrdeutige oder unlesbare Markierungen werden abgelehnt.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.detail.recovery import fix_text, load_canonical_pages
from app.database.models import Contract
from app.database.models.contract import ContractDocument
from app.register.ai_mapping import notice_target_from_text
from app.register.fields import FIELDS

PERIOD_BASES = ("initial_term", "minimum_term", "notice_period", "renewal_period")
MAX_QUOTE = 1000

_MONTHS = {
    "januar": 1, "jan": 1, "februar": 2, "feb": 2, "maerz": 3, "märz": 3, "mrz": 3, "mär": 3, "april": 4, "apr": 4,
    "mai": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "november": 11, "nov": 11, "dezember": 12, "dez": 12,
}
_WORDS = {
    "ein": 1, "eine": 1, "einen": 1, "einem": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10, "elf": 11, "zwölf": 12, "zwoelf": 12,
    "achtzehn": 18, "vierundzwanzig": 24, "sechsunddreißig": 36, "sechsunddreissig": 36, "achtundvierzig": 48,
    "sechzig": 60,
}
_UNITS = (
    (re.compile(r"^tag(e|en|es)?$"), "days"),
    (re.compile(r"^woche(n)?$"), "weeks"),
    (re.compile(r"^monat(e|en|s)?$"), "months"),
    (re.compile(r"^jahr(e|en|es)?$"), "years"),
)

_NUMERIC_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})(?!\d)")
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_WORD_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*\.?\s*([A-Za-zÄÖÜäöüß]{3,9})\.?\s+(\d{4})(?!\d)")
_NUMBER = re.compile(r"(?<![\d,.])(\d{1,6}(?:[.,]\d{1,4})?)(?![\d])")


class CaptureError(ValueError):
    def __init__(self, detail_de: str) -> None:
        super().__init__(detail_de)
        self.detail_de = detail_de


def normalize(text: str) -> str:
    """Vergleichsform: gleiche Bindestriche/Anfuehrungszeichen, Leerraum zusammengefasst."""
    text = fix_text(text or "")
    for src, dst in (("­", ""), ("‐", "-"), ("‑", "-"), ("‒", "-"), ("–", "-"), ("—", "-"),
                     ("„", '"'), ("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'"), (" ", " ")):
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def _valid_date(day: int, month: int, year: int) -> Optional[date]:
    try:
        return date(year, month, day) if 1900 <= year <= 2200 else None
    except ValueError:
        return None


def parse_date(text: str) -> date:
    found: set[date] = set()
    for match in _NUMERIC_DATE.finditer(text):
        value = _valid_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if value:
            found.add(value)
    for match in _ISO_DATE.finditer(text):
        value = _valid_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        if value:
            found.add(value)
    for match in _WORD_DATE.finditer(text):
        month = _MONTHS.get(match.group(2).casefold().rstrip("."))
        if month:
            value = _valid_date(int(match.group(1)), month, int(match.group(3)))
            if value:
                found.add(value)
    if not found:
        raise CaptureError("In der markierten Stelle steht kein Datum.")
    if len(found) > 1:
        raise CaptureError("Die markierte Stelle enthält mehrere Daten. Bitte nur das gemeinte Datum markieren.")
    return found.pop()


def _unit(word: str) -> Optional[str]:
    lowered = word.casefold()
    for pattern, unit in _UNITS:
        if pattern.match(lowered):
            return unit
    return None


def parse_duration(text: str) -> tuple[int, str]:
    # Wortweise: eine Einheit zaehlt mit der Zahl direkt davor ("3 Monate", "drei Monaten",
    # "zwölf (12) Monate" – dann gilt die Ziffer in Klammern).
    tokens = re.findall(r"\(\s*\d{1,3}\s*\)|\d{1,3}|[A-Za-zÄÖÜäöüß]+", text)
    found: set[tuple[int, str]] = set()
    for index, token in enumerate(tokens):
        unit = _unit(token)
        if unit is None or index == 0:
            continue
        before = tokens[index - 1]
        number: Optional[int] = None
        if before.startswith("("):
            number = int(before.strip("() "))
        elif before.isdigit():
            number = int(before)
        else:
            number = _WORDS.get(before.casefold())
        if number is not None:
            found.add((number, unit))
    if not found:
        raise CaptureError("In der markierten Stelle steht keine Dauer (z. B. „3 Monate“).")
    if len(found) > 1:
        raise CaptureError("Die markierte Stelle enthält mehrere Fristen. Bitte nur die gemeinte markieren.")
    return found.pop()


def _numbers(text: str) -> list[Decimal]:
    out: list[Decimal] = []
    for raw in _NUMBER.findall(text):
        try:
            out.append(Decimal(raw.replace(".", "").replace(",", ".") if "," in raw else raw))
        except InvalidOperation:
            continue
    return out


def parse_int(text: str) -> int:
    values = {int(value) for value in _numbers(text) if value == int(value)}
    if not values:
        raise CaptureError("In der markierten Stelle steht keine Zahl.")
    if len(values) > 1:
        raise CaptureError("Die markierte Stelle enthält mehrere Zahlen. Bitte nur die gemeinte markieren.")
    return values.pop()


def parse_percent(text: str) -> Decimal:
    hits = re.findall(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:%|Prozent|v\.\s?H\.)", text, flags=re.IGNORECASE)
    values = {Decimal(item.replace(",", ".")) for item in hits}
    if not values:
        raise CaptureError("In der markierten Stelle steht kein Prozentsatz.")
    if len(values) > 1:
        raise CaptureError("Die markierte Stelle enthält mehrere Prozentsätze. Bitte nur den gemeinten markieren.")
    return values.pop()


def capturable(key: str) -> bool:
    return any(key == item for item, _label in CAPTURE_FIELDS)


def values_from_quote(key: str, quote: str) -> dict[str, Any]:
    """Feldwerte aus der markierten Stelle; CaptureError, wenn nicht eindeutig lesbar."""
    if key in PERIOD_BASES:
        number, unit = parse_duration(quote)
        return {f"{key}_value": number, f"{key}_unit": unit}
    if key == "notice_to":
        target = notice_target_from_text(quote)
        if target is None:
            raise CaptureError("Aus der markierten Stelle geht kein eindeutiger Kündigungstermin hervor (z. B. „zum Quartalsende“).")
        return {"notice_to": target}
    spec = FIELDS.get(key)
    if spec is None or not capturable(key):
        raise CaptureError("Dieses Feld kann nicht aus dem Dokument übernommen werden.")
    if spec.kind == "date":
        return {key: parse_date(quote)}
    if spec.kind == "int":
        if key.endswith("_months"):
            # "alle 12 Monate" oder "jährlich" als Dauer lesen, sonst eine einzelne Zahl.
            try:
                number, unit = parse_duration(quote)
                if unit in {"months", "years"}:
                    return {key: number * (12 if unit == "years" else 1)}
            except CaptureError:
                pass
        return {key: parse_int(quote)}
    if spec.kind == "decimal":
        return {key: parse_percent(quote)}
    return {key: normalize(quote)}


# Felder, die aus einer markierten Stelle uebernommen werden koennen (Reihenfolge = Auswahlliste).
CAPTURE_FIELDS: tuple[tuple[str, str], ...] = (
    ("contract_title", "Vertragstitel"),
    ("short_description", "Kurzbeschreibung"),
    ("subject_text", "Vertragsgegenstand"),
    ("internal_number", "Interne Nummer"),
    ("term_start_date", "Vertragsbeginn"),
    ("term_fixed_end_date", "Festes Vertragsende"),
    ("initial_term", "Laufzeit"),
    ("minimum_term", "Mindestlaufzeit"),
    ("notice_period", "Kündigungsfrist"),
    ("notice_to", "Kündigung zum"),
    ("renewal_period", "Verlängerung um"),
    ("terminated_on", "Gekündigt am"),
    ("terminated_effective", "Gekündigt zum"),
    ("price_adjustment_percent", "Preisanpassung (% je Anpassung)"),
    ("price_adjustment_index_name", "Preisindex"),
    ("price_adjustment_next_date", "Nächste Preisanpassung"),
    ("price_adjustment_interval_months", "Anpassung alle (Monate)"),
    ("maintenance_next_date", "Nächste Wartung"),
    ("maintenance_interval_months", "Wartung alle (Monate)"),
)
_UNIT_DE = {"days": ("Tag", "Tage"), "weeks": ("Woche", "Wochen"), "months": ("Monat", "Monate"), "years": ("Jahr", "Jahre")}
_NOTICE_DE = {"contract_end": "zum Vertragsende", "month_end": "zum Monatsende", "quarter_end": "zum Quartalsende",
              "half_year_end": "zum Halbjahresende", "year_end": "zum Jahresende", "anytime": "jederzeit"}


def preview(key: str, changes: dict[str, Any]) -> str:
    """So wird der gelesene Wert gespeichert (deutsche Anzeige fuer die Vorschau)."""
    if key in PERIOD_BASES:
        number, unit = changes[f"{key}_value"], changes[f"{key}_unit"]
        singular, plural = _UNIT_DE[unit]
        return f"{number} {singular if number == 1 else plural}"
    value = changes[key]
    if key == "notice_to":
        return _NOTICE_DE.get(value, value)
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, Decimal):
        return f"{value.normalize():f}".replace(".", ",") + " %"
    if key.endswith("_months"):
        return f"alle {value} Monate"
    return str(value)


@dataclass
class Capture:
    changes: dict[str, Any]
    document_version_id: uuid.UUID
    page: int
    quote: str


def prepare_capture(
    session: Session, *, contract: Contract, field_key: str, document_version_id: uuid.UUID, page: int, quote: str,
) -> Capture:
    """Prueft Dokument, Seite und Fundstelle und liest den Wert."""
    cleaned = normalize(quote)
    if not cleaned:
        raise CaptureError("Bitte eine Stelle im Text markieren.")
    if len(cleaned) > MAX_QUOTE:
        raise CaptureError(f"Die markierte Stelle ist zu lang (höchstens {MAX_QUOTE} Zeichen).")
    if not capturable(field_key):
        raise CaptureError("Dieses Feld kann nicht aus dem Dokument übernommen werden.")
    linked = session.scalars(select(ContractDocument.id).where(
        ContractDocument.organization_id == contract.organization_id,
        ContractDocument.contract_id == contract.id,
        ContractDocument.document_version_id == document_version_id,
    )).first()
    if linked is None:
        raise CaptureError("Dieses Dokument gehört nicht zu diesem Vertrag.")
    pages = {row["page"]: row["text"] for row in load_canonical_pages(
        session, organization_id=contract.organization_id, document_version_id=document_version_id,
    )}
    if page not in pages:
        raise CaptureError("Für diese Seite liegt kein gelesener Text vor.")
    if cleaned not in normalize(pages[page]):
        raise CaptureError("Die markierte Stelle wurde auf dieser Seite nicht gefunden.")
    return Capture(values_from_quote(field_key, cleaned), document_version_id, page, cleaned)


def page_text(session: Session, *, contract: Contract, document_version_id: uuid.UUID, page: int) -> Optional[dict]:
    linked = session.scalars(select(ContractDocument.id).where(
        ContractDocument.organization_id == contract.organization_id,
        ContractDocument.contract_id == contract.id,
        ContractDocument.document_version_id == document_version_id,
    )).first()
    if linked is None:
        return None
    pages = load_canonical_pages(session, organization_id=contract.organization_id, document_version_id=document_version_id)
    numbers = sorted(row["page"] for row in pages)
    text = next((fix_text(row["text"]) for row in pages if row["page"] == page), None)
    return {"page": page, "pages": numbers, "text": text,
            "fields": [{"key": key, "label": label} for key, label in CAPTURE_FIELDS]}
