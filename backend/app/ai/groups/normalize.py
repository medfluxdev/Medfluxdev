"""Deterministische Normalisierung + Quell-Grounding (STEP 8B-Semantik).

Reine Code-Logik (keine KI): normalisiert strukturierte Werte, verwirft klar
fehlklassifizierte Identifikatoren und bevorzugt bei OCR-beschädigten
Parteinamen eine sauber belegte Schreibweise aus demselben Dokument.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, Optional

from app.models.contract import Contract
from app.models.enums import BillingInterval, ContractType, TimeUnit


_CONTRACT_TYPE_SYNONYMS = {
    "wartungsvertrag": ContractType.MAINTENANCE,
    "wartung": ContractType.MAINTENANCE,
    "maintenance": ContractType.MAINTENANCE,
    "servicevertrag": ContractType.SERVICE,
    "service": ContractType.SERVICE,
    "full service": ContractType.SERVICE,
    "wartungs- und servicevertrag": ContractType.SERVICE,
    "service- und wartungsvertrag": ContractType.SERVICE,
    "lease": ContractType.LEASE,
    "leasing": ContractType.LEASE,
    "miete": ContractType.RENTAL,
    "rental": ContractType.RENTAL,
    "mietvertrag": ContractType.RENTAL,
    "other": ContractType.OTHER,
    "unknown": ContractType.UNKNOWN,
}

_BILLING_SYNONYMS = {
    "monthly": BillingInterval.MONTHLY,
    "monatlich": BillingInterval.MONTHLY,
    "pro monat": BillingInterval.MONTHLY,
    "je monat": BillingInterval.MONTHLY,
    "quarterly": BillingInterval.QUARTERLY,
    "vierteljährlich": BillingInterval.QUARTERLY,
    "quartalsweise": BillingInterval.QUARTERLY,
    "halbjährlich": BillingInterval.SEMI_ANNUAL,
    "semi_annual": BillingInterval.SEMI_ANNUAL,
    "annual": BillingInterval.ANNUAL,
    "jährlich": BillingInterval.ANNUAL,
    "pro jahr": BillingInterval.ANNUAL,
    "je jahr": BillingInterval.ANNUAL,
    "im jahr": BillingInterval.ANNUAL,
    "once": BillingInterval.ONCE,
    "einmalig": BillingInterval.ONCE,
    "einmal": BillingInterval.ONCE,
}

_TIMEUNIT_DE = {
    "tag": TimeUnit.DAYS, "tage": TimeUnit.DAYS, "tagen": TimeUnit.DAYS,
    "woche": TimeUnit.WEEKS, "wochen": TimeUnit.WEEKS,
    "monat": TimeUnit.MONTHS, "monate": TimeUnit.MONTHS, "monaten": TimeUnit.MONTHS,
    "jahr": TimeUnit.YEARS, "jahre": TimeUnit.YEARS, "jahren": TimeUnit.YEARS,
    "stunde": TimeUnit.HOURS, "stunden": TimeUnit.HOURS,
}

_ORG_HINT_RE = re.compile(
    r"\b(?:gmbh|ag|kg|mbh|krankenhaus|klinikum|klinik|hospital|stiftung|"
    r"universitätsklinikum|universitaetsklinikum|medical|medizintechnik)\b",
    re.IGNORECASE,
)
_CONTRACT_NUMBER_LABEL_RE = re.compile(
    r"\b(?:vertrags?(?:nummer|[- ]?nr\.? )?|contract\s*(?:number|no\.?))\b",
    re.IGNORECASE,
)
_OFFER_NUMBER_LABEL_RE = re.compile(
    r"\b(?:angebots?(?:nummer|[- ]?nr\.?))\b",
    re.IGNORECASE,
)
_ORDER_NUMBER_LABEL_RE = re.compile(
    r"\b(?:bestellung|bestell(?:nummer|[- ]?nr\.?)|purchase\s*order|po\s*(?:number|no\.?))\b",
    re.IGNORECASE,
)


def _norm(v: str) -> str:
    return " ".join(str(v).strip().lower().split())


def _fuzzy_norm(v: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in str(v)).split())


def normalize_contract_type(value) -> ContractType:
    if value is None or value == "":
        return ContractType.UNKNOWN
    if isinstance(value, ContractType):
        return value
    return _CONTRACT_TYPE_SYNONYMS.get(_norm(value), ContractType.UNKNOWN)


def normalize_billing_interval(value) -> BillingInterval:
    if value is None or value == "":
        return BillingInterval.OTHER
    if isinstance(value, BillingInterval):
        return value
    return _BILLING_SYNONYMS.get(_norm(value), BillingInterval.OTHER)


def normalize_duration_unit(text: str) -> Optional[TimeUnit]:
    return _TIMEUNIT_DE.get(_norm(text))


def _iter_source_texts(units: Iterable[object]) -> list[str]:
    out: list[str] = []
    for unit in units:
        text = str(getattr(unit, "text", "") or "").strip()
        if text:
            out.append(text)
    return out


def _window_around(text: str, needle: str, radius: int = 90) -> list[str]:
    windows: list[str] = []
    low_text = text.lower()
    low_needle = needle.lower()
    start = 0
    while True:
        idx = low_text.find(low_needle, start)
        if idx < 0:
            break
        windows.append(text[max(0, idx - radius): min(len(text), idx + len(needle) + radius)])
        start = idx + max(1, len(needle))
    return windows


def _ground_contract_number(contract: Contract, texts: list[str]) -> list[str]:
    """Verwirft eine Bestellnummer, wenn sie fälschlich als Vertragsnummer kam.

    Ein Wert bleibt erhalten, sobald derselbe Wert irgendwo im Dokument nahe einer
    expliziten Vertrags-/Angebotsnummer-Markierung steht. Nur wenn alle belegten
    Vorkommen ausschließlich Bestellkontext sind, wird auf None zurückgesetzt.
    """
    value = (contract.identity.contract_number or "").strip()
    if not value:
        return []

    windows: list[str] = []
    for text in texts:
        windows.extend(_window_around(text, value))
    if not windows:
        return []

    if any(_CONTRACT_NUMBER_LABEL_RE.search(w) or _OFFER_NUMBER_LABEL_RE.search(w) for w in windows):
        return []
    if any(_ORDER_NUMBER_LABEL_RE.search(w) for w in windows):
        contract.identity.contract_number = None
        return ["identity.contract_number: Bestellnummer als Vertragsnummer verworfen"]
    return []


def _split_org_candidates(text: str) -> list[str]:
    # DOCX-Tabellen und Signaturen verwenden typischerweise Zeilen, Pipes oder
    # Slash-Trenner. Kurze Segmente halten den Vergleich robust und vermeiden,
    # dass eine komplette Signatur als Firmenname übernommen wird.
    raw_parts = re.split(r"[\n|;/]+", text)
    candidates: list[str] = []
    for raw in raw_parts:
        part = " ".join(raw.strip().split())
        if not (4 <= len(part) <= 100):
            continue
        if not _ORG_HINT_RE.search(part):
            continue
        # Adress-/E-Mail-Zeilen sind keine canonical organization names.
        low = part.lower()
        if "@" in part or re.search(r"\b\d{4,5}\b", part) or low.startswith(("email", "tel", "fax")):
            continue
        candidates.append(part)
    return candidates


def _name_quality(value: str) -> float:
    if not value:
        return 0.0
    letters = sum(ch.isalpha() or ch.isspace() for ch in value)
    ratio = letters / max(1, len(value))
    penalty = 0.0
    if any(ch.isdigit() for ch in value):
        penalty += 0.15
    if any(ch in ";{}[]" for ch in value):
        penalty += 0.12
    # Häufige OCR-Verwechslung bei deutscher Gesellschaftsform.
    if re.search(r"\bgmrh\b", value, re.IGNORECASE):
        penalty += 0.18
    return ratio - penalty


def _canonicalize_party_name(value: Optional[str], texts: list[str]) -> tuple[Optional[str], bool]:
    if not value:
        return value, False

    current = " ".join(value.split())
    current_norm = _fuzzy_norm(current)
    current_quality = _name_quality(current)
    best = current
    best_score = 0.0

    for text in texts:
        for candidate in _split_org_candidates(text):
            if candidate.casefold() == current.casefold():
                continue
            score = SequenceMatcher(None, current_norm, _fuzzy_norm(candidate)).ratio()
            quality = _name_quality(candidate)
            # Fuzzy-Match korrigiert nur offensichtliche OCR-Schreibweisen. Die
            # hohe Schwelle + Qualitätsverbesserung verhindert einen Wechsel zu
            # einer anderen Firma, nur weil beide z.B. "GmbH" enthalten.
            if score < 0.72 or quality < current_quality + 0.08:
                continue
            weighted = score + min(0.2, quality - current_quality)
            if weighted > best_score:
                best = candidate
                best_score = weighted

    return (best, best != current)


def ground_source_identity(contract: Contract, units: Iterable[object]) -> list[str]:
    """Evidence-first Nachbearbeitung für Identitätsfelder.

    Die Funktion ist absichtlich lieferantenunabhängig: sie nutzt ausschließlich
    die im Dokument vorhandenen Texteinheiten und generische Rollen-/Nummerregeln.
    """
    texts = _iter_source_texts(units)
    issues = _ground_contract_number(contract, texts)

    for field_name in ("customer", "supplier", "contractor"):
        old = getattr(contract.identity, field_name, None)
        new, changed = _canonicalize_party_name(old, texts)
        if changed:
            setattr(contract.identity, field_name, new)
            issues.append(f"identity.{field_name}: OCR-Schreibweise aus sauberem Quellbeleg kanonisiert")
    return issues


CONTRADICTION_REVIEW = "logical contradiction"


def check_contradictions(contract: Contract) -> list[str]:
    issues: list[str] = []
    dates = contract.dates
    if dates.start_date is not None and dates.start_date.date is not None:
        if dates.end_date is not None and dates.end_date.date is not None:
            if dates.end_date.date < dates.start_date.date:
                issues.append("dates: end_date liegt VOR start_date – bitte prüfen")

    term = contract.termination
    if term.automatic_renewal is False and term.renewal_period is not None:
        issues.append("termination: automatic_renewal=false, aber renewal_period gesetzt – bitte prüfen")
    if term.cancellation_period is not None and term.renewal_period is not None:
        if (
            term.cancellation_period.unit == term.renewal_period.unit
            and term.cancellation_period.value is not None
            and term.renewal_period.value is not None
            and term.renewal_period.value < term.cancellation_period.value
        ):
            issues.append("termination: renewal_period KLEINER als cancellation_period – bitte prüfen")

    costs = contract.costs
    if costs.monthly_cost is not None and costs.monthly_cost.amount is not None and costs.monthly_cost.amount > 0:
        if costs.annual_cost is not None and costs.annual_cost.amount is not None and costs.annual_cost.amount > 0:
            if costs.annual_cost.amount < costs.monthly_cost.amount:
                issues.append("costs: annual_cost kleiner als monthly_cost – bitte prüfen")
    return issues


def run_normalization(contract: Contract) -> list[str]:
    issues: list[str] = []
    ct = contract.identity.contract_type
    if not isinstance(ct, ContractType) or ct not in (
        ContractType.MAINTENANCE, ContractType.SERVICE, ContractType.LEASE,
        ContractType.RENTAL, ContractType.OTHER,
    ):
        contract.identity.contract_type = normalize_contract_type(ct)
    issues.extend(check_contradictions(contract))
    return issues
