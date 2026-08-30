r"""OCR-Token-Sicherheit: verdaechtige Muster vs. unmissverstaendliche Werte.

Grundsatz (STEP 8B, Observed discrepancy): Dokumentscans erzeugen verdaectige
Werte wie `150,480,00` (OCR-Typo aus 150.480,00), `5.916.67` oder
`792,000,00`. Medflux darf solche Muster NUR als "verdaechtig, manueller
Review erforderlich" markieren und NIE heimlich "reparieren".

Nur UNAMBIVALENTE Muster werden deterministisch normalisiert:
- Deutsche Preise `\d{1,3}(\.\d{3})+,\d{2}`  -> exakter Dezimalwert (z. B.
  792.000,00 -> 792000.00)
- `\d{1,3}(\.\d{3})+,-` (Strichform)       -> exakter Eurobetrag
- Euro-Prae- bzw. Suffix `EUR`/`€` werden optional getoleriert.

Alles andere, das eine Tausend-/Dezimaltrennungs-Varianz zeigt, wird als
`Trust=Low` gemeldet. Prozent-, Datums- und Seriennummer-Tokens erhalten
eine eigene verdaechtige/korrekte Klassifikation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Literal, Optional

from app.documents.intelligence.dates import find_dates

_TRUST = Literal["safe", "suspicious"]


@dataclass(frozen=True)
class ParsedMoney:
    ok: bool
    amount: Optional[Decimal] = None
    reason: str = ""


_MONEY_SEARCH_RE = re.compile(
    r"(?<!\w)(?:\s*(?:eur|€)\s*)?"
    r"(?P<num>\d{1,3}(?:\.\d{3})+,\d{2}|\d{1,3}(?:\.\d{3})+,-)"
    r"(?:\s*(?:eur|€))?(?!\d)",
    re.IGNORECASE,
)
_SUSPICIOUS_SEP_RE = re.compile(
    r"(?<!\w)\d{1,3}(?:[.,]\d{1,3}){2,}(?:[.,]\d{1,2})?\b"
)
_DIRTY_DD_RE = re.compile(r"(?<!\w)\d{1,3}\.\d{1,3}\.\d{2}\b")
_DIRTY_CC_RE = re.compile(r"(?<!\w)\d{1,3},\d{3},\d{2}\b")


def _as_decimal(num_group: str) -> Optional[Decimal]:
    """Baut aus der Zahlen-Gruppe einen exakten Dezimalwert (kein Runden)."""
    try:
        token = re.sub(r"[^\d,.-]", "", num_group)
        if token.endswith("-"):
            token = token.rstrip("-").replace(".", "").replace(",", "")
            token = f"{token}.00"
        else:
            token = token.replace(".", "").replace(",", ".")
        return Decimal(token)
    except InvalidOperation:
        return None


def safe_normalize_money(text: str) -> ParsedMoney:
    """Normalisiert einen Betrag, wenn er EINDEUTIG deutsch ist.

    Returns:
        ParsedMoney(ok=True, amount=...) bei eindeutigem Betrag;
        ParsedMoney(ok=False, reason=...) sonst (KEIN Erfinden).
    """
    m = _MONEY_SEARCH_RE.search(text.strip())
    if not m:
        return ParsedMoney(ok=False, reason="no_exact_german_pattern")
    amount = _as_decimal(m.group("num"))
    if amount is None:
        return ParsedMoney(ok=False, reason="inexact_decimal")
    return ParsedMoney(ok=True, amount=amount)


def classify_number_token(raw: str) -> tuple[_TRUST, str]:
    """Klassifiziert ein Text-Token nach numerischer Verdaechtigkeit.

    Returns:
        (status, reason) – status 'suspicious' erfordert manuellen Review.
    """
    token = raw.strip()
    if not token:
        return "safe", "empty"
    if _DIRTY_CC_RE.search(token) or _DIRTY_DD_RE.search(token):
        return "suspicious", "duplicate_thousand_separator"
    m = safe_normalize_money(token)
    if m.ok:
        return "safe", "german_money"
    if _SUSPICIOUS_SEP_RE.search(token):
        return "suspicious", "mixed_thousand_decimal_separator"
    return "safe", "non_money_number"


def classify_percent_token(raw: str) -> tuple[_TRUST, str]:
    token = raw.strip()
    m = re.fullmatch(r"(?P<pct>\d+(?:[.,]\d+)?)\s*%", token)
    if not m:
        return "safe", "non_percent"
    # "1.234 %" zeigt Tausendertrennung UND nicht-deutsche Prozent-Form
    if re.search(r"\.", m.group("pct").rstrip(".")):
        return "suspicious", "percent_with_dot"
    return "safe", "percent"


def classify_date_token(raw: str) -> tuple[_TRUST, str]:
    """Datumstoken: korrekt, wenn ein gueltiges Kalenderdatum erkannt wurde."""
    hits = find_dates(raw)
    valid = [h for h in hits if h.to_date() is not None]
    if valid:
        return "safe", "german_date"
    return "suspicious", "unparsed_date_maybe_event_based"


def classify_serial_repetition(variants: list[str]) -> tuple[_TRUST, str]:
    """Seriennummern-Varianten (z. B. "21115" vs "24445"): Diskrepanz = review."""
    clean = {v.strip() for v in variants if v.strip()}
    if len(clean) <= 1:
        return "safe", "one_unique_variant"
    return "suspicious", f"{len(clean)}_varianten"


def token_normal_form(raw: str) -> str:
    """Deterministische Rohform (fuer Gruppierung, kennt keine Sprache)."""
    return " ".join(raw.strip().lower().split())


@dataclass
class SuspiciousReport:
    """Diagnose-Report aller verdaechtigen Tokens eines Texts."""

    total_review_tokens: int = 0
    suspicious: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def scan_suspicious_numbers(text: str) -> list[tuple[str, str]]:
    """Durchsucht Freitext nach verdaechtigen numerischen Tokens."""
    found: list[tuple[str, str]] = []
    for m in _SUSPICIOUS_SEP_RE.finditer(text):
        token = m.group(0)
        status, reason = classify_number_token(token)
        if status == "suspicious":
            found.append((token, reason))
    # Zusaetzlich Deich nach "X.XXX,YY" irregulaeren Datums-Kombinationen
    for m in re.finditer(r"\d{1,3}\.\d{1,3}\.\d{2}(?!\d)", text):
        token = m.group(0)
        found.append((token, classify_number_token(token)[1]))
    return found


def de_duplicate_suspicious(items: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for it in items:
        if it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out