"""Deterministische Normalisierung + Quell-Grounding (STEP 8B-Semantik).

Reine Code-Logik (keine KI): normalisiert strukturierte Werte, verwirft klar
fehlklassifizierte Identifikatoren und groundet kritische Identitäts-/Leistungsfelder
nur bei starken, direkt aus dem Quelldokument ableitbaren Signalen.
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
    "servicevereinbarung": ContractType.SERVICE,
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
    r"\b(?:gmbh|gmrh|ag|kg|mbh|krankenhaus|klinikum|klinik|hospital|stiftung|"
    r"universitätsklinikum|universitaetsklinikum|medical|medizintechnik)\b",
    re.IGNORECASE,
)
_CONTRACT_NUMBER_LABEL_RE = re.compile(
    r"\b(?:vertragsnummer|vertrags[- ]?nr\.?|vertrag[- ]?nr\.?|contract\s*(?:number|no\.?))\b",
    re.IGNORECASE,
)
_OFFER_NUMBER_LABEL_RE = re.compile(
    r"\b(?:angebotsnummer|angebots[- ]?nr\.?|angebot[- ]?nr\.?)\b",
    re.IGNORECASE,
)
_ORDER_NUMBER_LABEL_RE = re.compile(
    r"\b(?:bestellung|bestellnummer|bestell[- ]?nr\.?|purchase\s*order|po\s*(?:number|no\.?))\b",
    re.IGNORECASE,
)
_CONTRACT_TITLE_RE = re.compile(
    r"\b(?:servicevereinbarung|servicevertrag|wartungsvertrag|wartungs- und servicevertrag|"
    r"service- und wartungsvertrag|mietvertrag|leasingvertrag|vertrag)\b",
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


def _strip_party_qualifiers(value: str) -> str:
    cleaned = " ".join(str(value or "").split())
    cleaned = re.sub(r"\s*\([^()]{2,120}\)\s*$", "", cleaned).strip()
    return cleaned


def _split_org_candidates(text: str) -> list[str]:
    raw_parts = re.split(r"[\n|;/]+", text)
    candidates: list[str] = []
    for raw in raw_parts:
        part = _strip_party_qualifiers(raw.strip())
        if not (4 <= len(part) <= 100):
            continue
        if not _ORG_HINT_RE.search(part):
            continue
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
    if re.search(r"\bgmrh\b", value, re.IGNORECASE):
        penalty += 0.18
    return ratio - penalty


def _table_role_anchor(texts: list[str], role: str) -> Optional[str]:
    aliases = {
        "customer": ("auftraggeber", "kunde"),
        "supplier": ("auftragnehmer", "lieferant", "dienstleister"),
    }
    wanted = aliases.get(role, ())
    if not wanted:
        return None

    for text in texts:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for idx, line in enumerate(lines):
            if "|" not in line:
                continue
            headers = [cell.strip().lower() for cell in line.split("|")]
            positions = [i for i, header in enumerate(headers) if any(alias in header for alias in wanted)]
            if len(positions) != 1:
                continue
            col = positions[0]
            pipe_rows_seen = 0
            for row in lines[idx + 1:]:
                if "|" not in row:
                    continue
                pipe_rows_seen += 1
                if pipe_rows_seen > 6:
                    break
                cells = [cell.strip() for cell in row.split("|")]
                if col >= len(cells):
                    continue
                value = _strip_party_qualifiers(cells[col])
                if value and not any(alias in value.lower() for alias in wanted):
                    return value
    return None


def _canonicalize_party_name(
    value: Optional[str],
    texts: list[str],
    *,
    role_anchor: Optional[str] = None,
) -> tuple[Optional[str], bool]:
    if not value and not role_anchor:
        return value, False

    current = _strip_party_qualifiers(value or role_anchor or "")
    anchor = _strip_party_qualifiers(role_anchor or current)
    anchor_norm = _fuzzy_norm(anchor)
    anchor_quality = _name_quality(anchor)

    model_segments = [
        _strip_party_qualifiers(p)
        for p in re.split(r"[;\n|]+", value or current)
        if p.strip()
    ]
    source_candidates: list[str] = []
    for text in texts:
        source_candidates.extend(_split_org_candidates(text))
    source_candidates.extend(model_segments)

    best = current
    best_score = -1.0
    for candidate in source_candidates:
        candidate = _strip_party_qualifiers(candidate)
        score = SequenceMatcher(None, anchor_norm, _fuzzy_norm(candidate)).ratio()
        quality = _name_quality(candidate)
        if score < 0.72:
            continue
        if quality + 0.02 < anchor_quality:
            continue
        weighted = score + max(0.0, min(0.2, quality - anchor_quality))
        if weighted > best_score:
            best = candidate
            best_score = weighted

    if best_score < 0:
        return value, False
    return best, best != " ".join((value or "").split())


def _source_contract_title(texts: list[str]) -> Optional[str]:
    for text in texts[:12]:
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            if not (6 <= len(line) <= 180):
                continue
            if _CONTRACT_TITLE_RE.search(line):
                return line
    return None


def _contract_type_from_title(title: Optional[str]) -> Optional[ContractType]:
    low = _norm(title or "")
    if not low:
        return None
    if "servicevereinbarung" in low or "servicevertrag" in low or "service- und wartungsvertrag" in low or "wartungs- und servicevertrag" in low:
        return ContractType.SERVICE
    if "wartungsvertrag" in low:
        return ContractType.MAINTENANCE
    if "leasingvertrag" in low or "leasing" in low:
        return ContractType.LEASE
    if "mietvertrag" in low:
        return ContractType.RENTAL
    return None


def _source_contains(texts: list[str], *needles: str) -> bool:
    haystack = "\n".join(texts).casefold()
    return any(needle.casefold() in haystack for needle in needles)


def _included_contains(contract: Contract, *needles: str) -> bool:
    joined = "\n".join(contract.services.included_services).casefold()
    return any(needle.casefold() in joined for needle in needles)


def _ground_source_services_from_texts(contract: Contract, texts: list[str]) -> list[str]:
    issues: list[str] = []
    rules = (
        ("maintenance", ("wartung",), ("wartung",)),
        ("repair", ("reparatur", "reparaturen"), ("reparatur", "reparaturen")),
        ("software_updates", ("software-update", "software update"), ("software-update", "software update")),
    )
    for field_name, included_needles, source_needles in rules:
        if getattr(contract.services, field_name) is not None:
            continue
        if _included_contains(contract, *included_needles) and _source_contains(texts, *source_needles):
            setattr(contract.services, field_name, True)
            issues.append(f"services.{field_name}: aus belegter included_services-Zeile groundet")
    return issues


def ground_source_identity(contract: Contract, units: Iterable[object]) -> list[str]:
    """Evidence-first post-processing for critical identity and service facts."""
    texts = _iter_source_texts(units)
    issues = _ground_contract_number(contract, texts)

    title = (contract.identity.contract_title or "").strip()
    source_title = _source_contract_title(texts)
    if source_title and title != source_title:
        contract.identity.contract_title = source_title
        title = source_title
        issues.append("identity.contract_title: explizite Vertragsüberschrift aus Quelle priorisiert")

    current_type = contract.identity.contract_type
    grounded_type = _contract_type_from_title(source_title or title)
    if grounded_type is not None and current_type != grounded_type:
        contract.identity.contract_type = grounded_type
        issues.append("identity.contract_type: aus expliziter Vertragsüberschrift abgeleitet")

    customer_anchor = _table_role_anchor(texts, "customer")
    supplier_anchor = _table_role_anchor(texts, "supplier")

    for field_name, anchor in (
        ("customer", customer_anchor),
        ("supplier", supplier_anchor),
        ("contractor", None),
    ):
        old = getattr(contract.identity, field_name, None)
        new, changed = _canonicalize_party_name(old, texts, role_anchor=anchor)
        if changed:
            setattr(contract.identity, field_name, new)
            issues.append(f"identity.{field_name}: Rollenbeleg/OCR-Schreibweise aus Quelle kanonisiert")
        elif not old and anchor:
            setattr(contract.identity, field_name, _strip_party_qualifiers(anchor))
            issues.append(f"identity.{field_name}: explizite Tabellenrolle aus Quelle übernommen")

    issues.extend(_ground_source_services_from_texts(contract, texts))
    return issues


def ground_source_services(contract: Contract, units: Iterable[object]) -> list[str]:
    """Public focused helper used by tests and future pipeline stages."""
    return _ground_source_services_from_texts(contract, _iter_source_texts(units))


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
