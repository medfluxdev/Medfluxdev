"""Direct Contract Intelligence Harness.

This module intentionally replaces the previous multi-stage Harness V3.
The old pipeline forced one fact through many semantic gates
(section/global/map/applicability/candidate/grounding/binding), which made a
correct Qwen reading easy to lose before Contract360.

The replacement has a much smaller responsibility graph:

    canonical OCR/layout + optional vision transcription
        -> literal source signals (deterministic observations)
        -> Qwen semantic fact proposals (no internal block ids)
        -> deterministic evidence resolver
        -> schema validation
        -> Contract + evidence

Qwen owns contractual meaning. Code owns source integrity, type validation and
persistence safety. The model never has to know MedFlux block identifiers.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from app.ai.harness.document import Block, DocumentModel
from app.ai.harness.pipeline import (
    _find_quote,
    _find_quote_tolerant,
    RETRIEVAL_TERMS,
    field_types,
    strict_value,
    equipment_identity_in_quote,
)
from app.ai.harness.source_signals import collect_source_signals
from app.documents.intelligence.hybrid import route_summary, visual_candidate_pages
from app.ai.service import AIService
from app.core.config import Settings
from app.models.contract import Contract
from app.models.contract import Equipment as EquipmentModel
from app.models.contract import VariableCharge
from app.models.enums import (
    ExtractionMethod,
    ExtractionStatus,
    ReviewFlag,
    ValidationStatus,
)
from app.models.evidence import BoundingBox, SourceEvidence
from app.models.values import Duration, Money, TimeUnit


class ProposedFact(BaseModel):
    field: str
    value: Any
    page: int | None = None
    quote: str = ""
    applicability: Literal["applicable", "alternative", "superseded", "unknown"] = "applicable"
    ambiguity: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ProposedFactBatch(BaseModel):
    facts: list[ProposedFact] = Field(default_factory=list)


# A visual reading is *complementary* to the canonical OCR text layer, never a
# second full-page transcription. Unbounded transcription of a dense scanned
# contract page cannot fit the vision output budget: the model hits the token
# limit mid-JSON and the structured response is lost. The bounds below keep every
# vision call inside `harness_vision_output_tokens`.
_VISION_MAX_FRAGMENTS = 12
_VISION_FRAGMENT_MAX_CHARS = 160

_VisionFragment = Annotated[str, Field(max_length=_VISION_FRAGMENT_MAX_CHARS)]


class VisualPageReading(BaseModel):
    page: int
    visible_text: list[_VisionFragment] = Field(
        default_factory=list, max_length=_VISION_MAX_FRAGMENTS
    )
    layout_relations: list[_VisionFragment] = Field(
        default_factory=list, max_length=_VISION_MAX_FRAGMENTS
    )
    unresolved: list[_VisionFragment] = Field(
        default_factory=list, max_length=_VISION_MAX_FRAGMENTS
    )


# Each pack: (name, field selectors, retrieval topics, keyword expansion)
# Field selectors match the full dotted field name or a dotted prefix (trailing dot).
# Retrieval topics drive deterministic per-pack source page selection and keyword hits.
# Keyword expansion is disabled for packs whose facts are fully anchored by money
# signals: those packs must only see pages that actually carry amounts, so the model
# maps the given literals instead of inventing numbers from unrelated scope clauses.
PACKS: tuple[tuple[str, tuple[str, ...], tuple[str, ...], bool], ...] = (
    ("core", ("identity.", "dates.", "termination."), ("identity", "dates", "termination"), True),
    ("commercial", ("costs.",), ("costs", "payment"), False),
    ("payment", ("payment.", "costs.tax_basis", "costs.tax_rate_percent",
                 "costs.price_adjustment_clause", "costs.price_indexation",
                 "costs.discounts"), ("payment", "costs"), True),
    ("operations", ("equipment", "services.", "sla."), ("equipment", "services", "sla"), True),
)

# Deterministic guidance for literal money values per pack.  The model interprets
# contractual meaning; the harness only supplies stable terminology to prevent the
# same literal from being sprayed across several cost fields.
_PACK_GUIDANCE = {
    "core": (
        "IDENTITY: supplier/customer is the legal company name only, without street, "
        "postcode or city; keep the company form verbatim (e.g. GmbH, AG) and never "
        "translate or shorten it. contract_title is the document title, not the parties. "
        "If the contract states a service contact, extract the email into service_email "
        "and the phone number into service_phone exactly as written; never guess them. "
        "DATES/TERMINATION: always decide termination.automatic_renewal (true/false) from the renewal "
        "wording; the literal signal 'nicht automatisch verlängert' means false."
    ),
    "commercial": (
        "MONEY MAPPING: assign each money literal exactly once, by its contractual role: "
        "a steady yearly recurring fee (e.g. per contract year, yearly base amount) -> costs.annual_cost with period=annual; "
        "year-staged amounts such as '1.Jahr', '2.Jahr' -> costs.scheduled_prices with 1-based period_index; "
        "a per-usage/per-call price (e.g. 'per call') -> costs.variable_charges with unit per_call. "
        "When year-staged amounts are identical from a certain year onward, that steady yearly amount is also "
        "the annual recurring fee -> set costs.annual_cost to it with period=annual. "
        "amount must be written as a JSON object: {\"amount\": <number or string>, \"currency\": \"EUR\", ...}. "
        "EVERY output amount must be verbatim equal to one of the money source signals; never invent totals or derive "
        "one amount from another, never repeat one literal amount in several cost fields, never return empty list items, "
        "and never map an amount to a page that does not contain it."
    ),
    "operations": (
        "OPERATIONS: equipment is a list of typed objects "
        "{device_name,manufacturer,model,serial_number,inventory_number,system_name,"
        "service_scope,included_services:list,excluded_services:list}. "
        "Copy the exact device/system name verbatim from the source; set serial_number only when the "
        "document states it, otherwise omit the field (never invent a serial). "
        "services.included_services and services.excluded_services are verbatim clause items "
        "(one entry per service), never paraphrases. Also set the boolean service facts "
        "(maintenance, inspection, repair, calibration, software_updates, remote_support, "
        "technical_support, spare_parts_included, consumables_included, emergency_service) "
        "to true exactly when the contract page states that service is included, and mirror "
        "those services in services.included_services. "
        "sla.availability_24_7 must be false whenever the contract states an explicit service window "
        "such as 'Montag bis Freitag 09:00-17:00' (no weekend/holiday coverage). "
        "sla.service_hours captures that window text verbatim as original_text."
    ),
}

SYSTEM = """You are the semantic contract reader inside MedFlux.
Read the supplied contract source pages and return only facts actually supported by them.
Do not invent values. Do not infer missing business facts. Distinguish binding
terms from alternatives, superseded text and optional offers.
For each returned fact:
- choose only a field from the supplied field catalog;
- return the typed value expected by that field;
- ALWAYS provide page and an exact source quote;
- the quote must be copied verbatim from CONTRACT SOURCE, never paraphrased and never contain ellipses;
- DECIDE each literal date, duration and money signal's contractual role; a signal with no contracting meaning must be omitted, not force-filled;
- never map one literal value to several fields; when two roles are possible, keep only the best-supported one;
- use the exact typed shape shown by the field catalog whenever possible;
- for enum fields output only a plain enum string value, never a Python repr such as <Enum.NAME>;
- never output MedFlux block ids.
Omit every field the source does not explicitly support; an omitted fact is better than a guessed one.
The deterministic evidence resolver will locate your quote in the original
canonical source. If wording is uncertain, set ambiguity instead of guessing.
"""


def measured_output_budget(
    purpose: str, prompt_tokens: int, capacity: int, base_output: int
) -> int | None:
    """Compatibility helper retained for callers/tests; the new harness uses one
    bounded retry only when the provider reports output truncation.
    """
    if not purpose.startswith(("semantic:", "vision:")):
        return None
    margin = int(capacity) - int(prompt_tokens) - 512
    candidate = min(3200, margin)
    return candidate if candidate >= int(base_output) + 128 else None


def _retry_fits_context(
    prompt_tokens: int,
    output_tokens: int,
    capacity: int,
    prompt_reserve: int,
    image_reserve: int = 0,
) -> bool:
    return (
        int(prompt_tokens)
        + int(output_tokens)
        + int(prompt_reserve)
        + int(image_reserve)
        <= int(capacity)
    )


def _retry_output_plan(
    purpose: str,
    prompt_tokens: int,
    capacity: int,
    base_output: int,
    image_reserve: int = 0,
) -> tuple[int | None, str]:
    candidate = measured_output_budget(purpose, prompt_tokens, capacity, base_output)
    if candidate is None:
        return None, "output_retry_not_performed"
    if not _retry_fits_context(
        prompt_tokens, candidate, capacity, 512, image_reserve
    ):
        return None, "output_retry_skipped_context_overflow"
    return candidate, "output_budget_stage_retry"


def _estimate_tokens(text: str) -> int:
    """Conservative pre-call token estimate for one prompt.

    Calibrated against measured Ollama `prompt_eval_count` values for German
    contract prompts (core pack: ~3.2 UTF-8 bytes per token). The factor stays
    slightly pessimistic so a budget computed from it can never understate the
    real prompt size.
    """
    return max(1, int(len(text.encode("utf-8")) / 3.1))


_CONTEXT_RESERVE = 512
_MIN_OUTPUT_TOKENS = 256
_PACK_SPLIT_MAX_DEPTH = 6


def _effective_context(
    prompt_tokens: int,
    output_tokens: int,
    requested_context: int,
    model_capacity: int | None,
    image_reserve: int = 0,
    reserve: int = _CONTEXT_RESERVE,
    allow_growth: bool = False,
) -> int:
    """Effective num_ctx for one provider call.

    The operator-configured context is a *memory* budget: on a local, VRAM-limited
    device a larger KV cache is paid for with partial CPU offload, which collapses
    generation speed and can make the model ramble until the output cap. The
    harness therefore never grows num_ctx beyond that budget; it only shrinks it
    when a single call provably cannot fit. Growing stays available for operators
    who deliberately configure a larger context via `harness_allow_context_growth`.
    """
    allowed = int(requested_context)
    if model_capacity is not None:
        allowed = min(allowed, int(model_capacity))
    needed = int(prompt_tokens) + int(output_tokens) + int(image_reserve) + int(reserve)
    if needed <= allowed:
        return allowed
    if not allow_growth or model_capacity is None:
        return allowed
    return min(int(model_capacity), needed)


def _fits_output_budget(
    prompt_tokens: int,
    output_tokens: int,
    context: int,
    image_reserve: int = 0,
    reserve: int = _CONTEXT_RESERVE,
) -> bool:
    return (
        int(prompt_tokens) + int(output_tokens) + int(image_reserve) + int(reserve)
        <= int(context)
    )


def _shrunk_output_budget(
    prompt_tokens: int,
    context: int,
    image_reserve: int = 0,
    reserve: int = _CONTEXT_RESERVE,
) -> int:
    """Largest output budget that still fits, never below the generation floor."""
    room = int(context) - int(prompt_tokens) - int(image_reserve) - int(reserve)
    return max(_MIN_OUTPUT_TOKENS, room)


def _field_catalog(types: dict[str, Any], selectors: tuple[str, ...]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for field, annotation in types.items():
        if any(field == select or field.startswith(select) for select in selectors):
            selected[field] = (
                str(annotation)
                .replace("typing.", "")
                .replace("app.models.values.", "")
                .replace("app.models.contract.", "")
                .replace("app.models.enums.", "")
            )
    return selected


# Kind eines literalen Quellsignals -> betroffene Retrieval-Topics.  Damit werden
# Seiten, die konkrete Signale tragen, deterministic fuer das jeweilige Pack
# ausgewaehlt (z. B. Geld-Seiten nur fuer commercial/payment).
_SIGNAL_TOPICS = {
    "identity": {"labelled_contract_number"},
    "dates": {"date", "duration"},
    "termination": {"date", "duration", "renewal_negation"},
    "costs": {"money"},
    "payment": {"money"},
}

# Obergrenze fuer die pro Pack gelieferten Quellseiten.  Signal-Seiten haben
# Vorrang; Keyword-Seiten werden nur bis zu dieser Grenze ergaenzt, damit der
# Prompt klein genug bleibt, damit Qwen die volle Output-Budget-Erwartung
# (Struktur statt Abkuerzungen) einhalten kann.
_PACK_MAX_PAGES = 5


def _pack_pages(
    topics: tuple[str, ...],
    canonical,
    source_signals,
    expand_keywords: bool = True,
) -> list[int]:
    """Deterministic per-pack source page selection.

    A pack sees pages that carry a literal signal relevant to its topics and the
    first page (identity context).  With keyword expansion enabled it additionally
    sees pages with a DENSE keyword profile (at least two distinct terms; generic
    single hits are noise) up to a cap.  If nothing matches, all pages are kept
    (fail-safe: analysis never silently runs on a misleading subset).

    Packs that are fully anchored by money signals disable keyword expansion so
    they only ever see pages that really carry amounts.
    """
    signal_kinds = {
        kind
        for topic in topics
        for kind in _SIGNAL_TOPICS.get(topic, ())
    }
    wanted: set[int] = set()
    for signal in source_signals:
        kind = signal.get("kind")
        page = signal.get("page")
        if kind in signal_kinds and page is not None:
            wanted.add(int(page))

    if "identity" in topics and canonical.pages:
        wanted.add(canonical.pages[0].page_number)

    if expand_keywords:
        keywords = [kw for topic in topics for kw in RETRIEVAL_TERMS.get(topic, ())]
        # The page cap applies only to packs that already have signal anchors.
        # Packs without literals (e.g. services) keep full keyword recall so their
        # annex pages are never dropped.
        limit = _PACK_MAX_PAGES if wanted else None
        if keywords:
            for page in canonical.pages:
                page_number = page.page_number
                if page_number in wanted:
                    continue
                lowered = (page.text or "").casefold()
                hits = {kw for kw in keywords if kw in lowered}
                if len(hits) >= 2 and (limit is None or len(wanted) < limit):
                    wanted.add(page_number)

    if not wanted:
        return sorted(page.page_number for page in canonical.pages)
    return sorted(wanted)


def _pack_source(canonical, page_numbers, visual_readings) -> str:
    rows: list[str] = []
    for page in canonical.pages:
        if page.page_number not in page_numbers:
            continue
        text = (page.text or "").strip()
        if text:
            rows.append(f"[PAGE {page.page_number}]\n{text}")
    if visual_readings:
        rows.append("[VISION TRANSCRIPTIONS]\n" + json.dumps(
            {
                page: {
                    "visible_text": reading.visible_text,
                    "layout_relations": reading.layout_relations,
                }
                for page, reading in visual_readings.items()
                if page in page_numbers
            },
            ensure_ascii=False,
        ))
    return "\n\n".join(rows)


def _bbox(block: Block) -> BoundingBox | None:
    region = getattr(getattr(block, "element", None), "region", None)
    if region is None:
        return None
    try:
        return BoundingBox(
            x0=float(region.x0),
            y0=float(region.y0),
            x1=float(region.x1),
            y1=float(region.y1),
        )
    except (TypeError, ValueError):
        return None


def _normalize_digits(value: str) -> str:
    return re.sub(r"[^0-9]", "", value or "")


def _date_signal_iso(value: str) -> str | None:
    text = value or ""
    # ISO zuerst: "2029-06-03" darf nicht als dd-mm-yyyy (3.6.2029) gelesen werden.
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        year, month, day = iso.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", text)
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _money_amount(value: str) -> float | None:
    match = re.search(r"(\d[\d.\s]*)(?:,(\d{2}))?", value or "")
    if not match:
        return None
    whole = re.sub(r"[.\s]", "", match.group(1))
    decimals = match.group(2) or "00"
    try:
        return float(f"{whole}.{decimals}")
    except ValueError:
        return None


_DURATION_UNIT_BY_STEM = {
    "jahr": "years",
    "monat": "months",
    "woche": "weeks",
    "tag": "days",
    "stund": "hours",
    "quarter": "quarters",
}


def _duration_unit_from_text(text: str) -> str | None:
    cleaned = re.sub(r"[^a-zäöüß]", "", (text or "").casefold())
    for stem, unit in _DURATION_UNIT_BY_STEM.items():
        if stem in cleaned:
            return unit
    return None


def _duration_candidates(value: Any) -> list[dict]:
    def walk(node: Any, rows: list[dict]) -> None:
        if isinstance(node, dict):
            if "value" in node and isinstance(node.get("value"), (int, float)):
                unit = _duration_unit_from_text(str(node.get("unit") or ""))
                rows.append({"value": int(node["value"]), "unit": unit})
            for key in ("value", "unit", "years", "months", "weeks", "days", "hours"):
                if key in node:
                    walk(node[key], rows)
        elif isinstance(node, list):
            for item in node:
                walk(item, rows)

    rows: list[dict] = []
    walk(value, rows)
    return rows


_PY_REPR_RE = re.compile(r"^(?P<cls>[A-Z][A-Za-z0-9_]*)\((?P<body>.*)\)$", re.DOTALL)
_REPR_INVALID = object()


def _split_top_level(body: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote = ""
    for char in body:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
            current.append(char)
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def _coerce_repr_scalar(raw: str) -> Any:
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "none":
        return None
    nested = _parse_python_repr(text)
    if nested is not None:
        return nested
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    # Unbekannter Skalarwert als Rohtext behalten (z. B.
    # `FlexibleDate(YYYY-MM-DD=2029-06-03)`), statt die Form zu verwerfen.
    return text


def _parse_python_repr(text: str) -> Optional[dict[str, Any]]:
    """Parse a `Model(field=value, ...)` repr into plain data.

    MiniCPM sometimes emits the Python *repr* of a nested model instead of its
    JSON object (`Duration(days=30)`, `FlexibleDate(YYYY-MM-DD=2029-06-03)`).
    Those carry a real fact but fail object validation, so every date/duration
    would silently be dropped. Parsing them here is deterministic; a repr that
    cannot be parsed is returned unchanged and rejected by the normal gates.
    """
    match = _PY_REPR_RE.match(text.strip())
    if match is None:
        return None
    fields: dict[str, Any] = {}
    for part in _split_top_level(match.group("body")):
        if "=" not in part:
            return None
        key, _, raw = part.partition("=")
        key = key.strip()
        if not key:
            return None
        parsed = _coerce_repr_scalar(raw)
        if parsed is _REPR_INVALID:
            return None
        fields[key] = parsed
    return fields


def _normalize_date_payload(value: Any) -> Any:
    if isinstance(value, str):
        iso = _date_signal_iso(value)
        if iso:
            return {"date": iso, "condition": None, "requires_review": False}
        parsed = _parse_python_repr(value)
        if parsed is not None:
            return _normalize_date_payload(parsed)
        return value
    if isinstance(value, dict):
        # `FlexibleDate(YYYY-MM-DD=2029-06-03)` parst zu
        # {"YYYY-MM-DD": "2029-06-03"}; das Feld ist ein Datum, kein Datum.
        if not value.get("date") and not value.get("literal_value"):
            for raw_key, raw_value in value.items():
                key = str(raw_key).strip().casefold()
                if key in {"date", "datum", "yyyy-mm-dd", "iso", "iso_date"}:
                    iso = _date_signal_iso(str(raw_value))
                    if iso:
                        return {
                            "date": iso,
                            "condition": None,
                            "requires_review": False,
                        }
        # Qwen semantic nutzt {"date_type": "start"|"end", "literal_value":
        # "04.06.2025"} - gleiche Form wie bei Dauer-Fakten.  Ohne Umbau leeren
        # wir den Date-Wert zu {"requires_review": false} und verlieren das
        # belegte Datum.  Uebernehme das Literal deterministisch.
        if value.get("literal_value") or value.get("date_type"):
            literal = value.get("literal_value")
            if isinstance(literal, str):
                iso = _date_signal_iso(literal)
                if iso:
                    return {
                        "date": iso,
                        "condition": None,
                        "requires_review": False,
                    }
        # Qwen sometimes emits {"year": Y, "month": M, "day": D} instead of the
        # FlexibleDate shape.  Normalize that deterministically before validation.
        if "year" in value or "month" in value or "day" in value:
            year = value.get("year") or (value.get("years") or 0)
            month = value.get("month") or (value.get("months") or 0)
            day = value.get("day") or (value.get("days") or 0)
            try:
                iso = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                return {"date": iso, "condition": None, "requires_review": False}
            except (TypeError, ValueError):
                pass
        cleaned = {
            key: value.get(key)
            for key in ("date", "condition", "requires_review")
            if key in value
        }
        if not cleaned:
            # Kein erkennbares Datumsfeld (z. B. eine unvollstaendige
            # `FlexibleDate(YYYY-MM-DD=1983)`-Form): zurueckgeben, damit die
            # strenge Validierung das Fact ablehnt, statt still ein leeres Datum
            # zu uebernehmen.
            return value
        raw_date = cleaned.get("date")
        if isinstance(raw_date, str):
            cleaned["date"] = _date_signal_iso(raw_date) or raw_date
        elif isinstance(raw_date, dict) and (
            "year" in raw_date or "month" in raw_date or "day" in raw_date
        ):
            nested = _normalize_date_payload(raw_date)
            if isinstance(nested, dict) and nested.get("date"):
                cleaned["date"] = nested["date"]
        cleaned.setdefault("requires_review", False)
        return cleaned
    return value


def _normalize_duration_payload(value: Any) -> Any:
    if isinstance(value, str):
        match = re.search(
            r"(?P<value>\d+)\s*(?P<unit>Jahr(?:e|en)?|Monat(?:e|en)?|Woche(?:n)?|Tag(?:e|en)?|Stunde(?:n)?"
            r"|years?|months?|weeks?|days?|hours?|minutes?)",
            value,
            re.IGNORECASE,
        )
        if not match:
            parsed = _parse_python_repr(value)
            if parsed is not None:
                return _normalize_duration_payload(parsed)
            return value
        unit_raw = match.group("unit").lower()
        if unit_raw.startswith("jahr") or unit_raw.startswith("year"):
            unit = "years"
        elif unit_raw.startswith("monat") or unit_raw.startswith("month"):
            unit = "months"
        elif unit_raw.startswith("woch") or unit_raw.startswith("week"):
            unit = "weeks"
        elif unit_raw.startswith("tag") or unit_raw.startswith("day"):
            unit = "days"
        elif unit_raw.startswith("minut"):
            unit = "minutes"
        else:
            unit = "hours"
        return {"value": int(match.group("value")), "unit": unit}
    if isinstance(value, dict):
        # Model sometimes emits {"years": 4} / {"months": N} / {"value": N,
        # "unit": ...} / {"duration_type": "months", "literal_value": "48
        # Monaten"} (semantic-extraction flavour).  Unify them deterministically.
        if value.get("literal_value") or value.get("duration_type"):
            literal = value.get("literal_value")
            if isinstance(literal, str):
                match = re.search(
                    r"(?P<value>\d+)\s*(?P<unit>Jahr(?:e|en)?|Monat(?:e|en)?|Woche(?:n)?|Tag(?:e|en)?|Stunde(?:n)?)",
                    literal,
                    re.IGNORECASE,
                )
                if match:
                    unit_raw = match.group("unit").lower()
                    if unit_raw.startswith("jahr"):
                        unit = "years"
                    elif unit_raw.startswith("monat"):
                        unit = "months"
                    elif unit_raw.startswith("woche"):
                        unit = "weeks"
                    elif unit_raw.startswith("tag"):
                        unit = "days"
                    else:
                        unit = "hours"
                    return {"value": int(match.group("value")), "unit": unit}
            amount = value.get("amount") or value.get("value")
            type_raw = (value.get("duration_type") or "").lower()
            if amount is not None and type_raw:
                return {
                    "value": int(float(amount)),
                    "unit": _duration_unit_from_text(type_raw),
                }
        unit = None
        for key in ("unit", "years", "year", "months", "month", "weeks", "week",
                    "days", "day", "hours", "hour", "quarters", "quarter"):
            if key in value and value.get(key) is not None:
                last = key
                break
        else:
            last = None
        if last is not None and last != "unit":
            if last.startswith("year"):
                unit = "years"
            elif last.startswith("month"):
                unit = "months"
            elif last.startswith("week"):
                unit = "weeks"
            elif last.startswith("day"):
                unit = "days"
            elif last.startswith("hour"):
                unit = "hours"
            elif last.startswith("quarter"):
                unit = "quarters"
            return {
                "value": int(value[last]),
                "unit": unit,
            }
        return {
            key: value.get(key)
            for key in ("value", "unit")
            if key in value
        }
    return value


def _normalize_money_payload(value: Any) -> Any:
    if isinstance(value, str):
        amount = _money_amount(value)
        if amount is None:
            return value
        currency = "EUR" if ("EUR" in value.upper() or "€" in value) else None
        return {"amount": amount, "currency": currency, "period": None}
    if isinstance(value, (int, float)):
        return {"amount": float(value), "currency": None, "period": None}
    if isinstance(value, dict):
        amount = value.get("amount")
        currency = value.get("currency") or value.get("currency_code")
        if amount is None and "value_str" in value:
            amount = value.get("value_str")
        if amount is None and any(key in value for key in ("cents", "value")):
            amount = value.get("cents", value.get("value"))
        if isinstance(amount, str):
            parsed = _money_amount(amount)
            if parsed is not None:
                amount = parsed
        elif isinstance(amount, dict):
            nested = _normalize_money_payload(amount)
            if isinstance(nested, dict):
                amount = nested.get("amount")
                currency = currency or nested.get("currency")
        cleaned = {}
        if amount is not None:
            cleaned["amount"] = amount
            cleaned["currency"] = currency
            cleaned["period"] = value.get("period")
        return cleaned
    return value


def _literal_evidence(
    literals: list[str],
    blocks: list[Block],
    document: DocumentModel | None = None,
) -> dict[tuple[str, str], tuple[Block, str]]:
    """Unique evidence spans for literal strings within ``blocks``.

    Case-exact match preferred, casefold fallback allowed.  The caller
    scopes ``blocks`` (fact page first, all pages as fallback), so an
    OCR-identical address that repeats on a later page does not shadow
    the same fact on its asserted page.
    """
    found: dict[tuple[str, str], tuple[Block, str]] = {}
    for literal in literals:
        if literal.upper() in {"EUR", "USD", "GBP"}:
            continue
        for block in blocks:
            resolved = _find_quote(block.text or "", literal)
            exact = resolved[0] if resolved is not None else _find_casefold(
                block.text or "", literal
            )
            if exact is not None:
                found.setdefault((block.id, exact), (block, exact))
    return found


def _money_field(field: str) -> bool:
    """True for fields that carry a monetary amount.

    Nur echte Geld-Felder (Einzelwerte + Zeilen mit Betrag, z. B.
    scheduled_prices / variable_charges) unterliegen dem strikten
    Geld-Locator.  Nicht-Geld-Felder unter `costs.`/`payment.` (z. B.
    tax_basis, payment_deadline_days) duerfen weiterhin ueber ihren
    Quelltext-Quote belegt werden.
    """
    if field in _MONEY_FIELDS:
        return True
    return field in {"costs.scheduled_prices", "costs.variable_charges"}


def _normalize_row_amount(amount_value: Any, row_currency: Any) -> Any:
    """Normalise pro-Zeile Betraege (scheduled_prices / variable_charges).

    Der Betrag kann als Money-Objekt, flacher String ("9.500,00 EUR", "9500")
    oder Zahl kommen.  Flache Strings wurden frueher zu {} geleert (Betrag
    verschwand unbegruendet); diese Deterministik erhaelt amount+currency,
    wenn ein Betrag erkennbar ist.  Keine Betraege werden erfunden.
    """
    if isinstance(amount_value, dict):
        merged = dict(amount_value)
        if "currency" not in merged and row_currency:
            merged["currency"] = row_currency
        return _normalize_money_payload(merged)
    if isinstance(amount_value, (str, int, float)):
        money = _normalize_money_payload(amount_value)
        if isinstance(money, dict):
            if money.get("currency") is None and row_currency:
                money["currency"] = row_currency
            return money
    return amount_value


_MONEY_FIELDS = {
    "costs.total_contract_value",
    "costs.annual_cost",
    "costs.monthly_cost",
    "costs.quarterly_cost",
    "costs.semi_annual_cost",
    "costs.one_time_cost",
    "costs.setup_installation_cost",
    "costs.maintenance_fee",
    "costs.hourly_rate",
    "costs.travel_cost",
    "costs.material_cost",
    "costs.spare_parts_cost",
    "costs.additional_costs",
    "costs.discounts",
    "payment.advance_payment",
}

_MONEY_PERIOD_BY_FIELD = {
    "costs.annual_cost": "annual",
    "costs.monthly_cost": "monthly",
    "costs.quarterly_cost": "quarterly",
    "costs.semi_annual_cost": "semi_annual",
    "costs.one_time_cost": "once",
}


# Zulaessige Felder eines Equipment-Objekts (vgl. app.models.contract.Equipment).
# Alles andere (v. a. 'evidence') wird verworfen – die Evidenz bindet der Harness
# deterministisch aus der gefundenen Quelle.
_EQUIPMENT_KEEP = {
    "device_name",
    "manufacturer",
    "model",
    "serial_number",
    "inventory_number",
    "system_name",
    "equipment_category",
    "equipment_type",
    "location",
    "department",
    "service_scope",
    "included_services",
    "excluded_services",
    "coverage_start",
    "coverage_end",
    "sla_notes",
}

_EQUIPMENT_ALIASES = {
    "deviceName": "device_name",
    "serialNumber": "serial_number",
    "seriennr": "serial_number",
    "seriennummer": "serial_number",
    "inventarnr": "inventory_number",
    "systemName": "system_name",
    "equipmentCategory": "equipment_category",
    "equipmentType": "equipment_type",
}

_EQUIPMENT_SCOPE_LIST_KEYS = {"included_services", "excluded_services"}


def _clean_device_name(name: str) -> str:
    """Reduce an OCR/model device name to the device name itself.

    Contract price tables repeat the device in a row like
    `OPTIS(TM) Mobile Next Imaging System | 1014932 | SN: 12`. The trailing
    article/serial columns are not part of the device name, so only the first
    meaningful cell is kept. Nothing is invented: empty or purely numeric
    fragments are dropped, never filled in.
    """
    text = " ".join((name or "").split())
    if "|" in text:
        candidates = [
            segment.strip()
            for segment in text.split("|")
            if segment.strip() and re.search(r"[A-Za-z\u00c4-\u00dc\u00e4-\u00fc]", segment)
        ]
        if candidates:
            text = candidates[0]
    text = re.sub(r"\bSN:?\s*$", "", text).strip()
    return text


def _normalize_equipment_item(item: Any) -> Optional[dict]:
    """Normalisiert ein einzelnes Equipment-Proposal deterministisch.

    Nimmt Strings (reines Geräte-/Systemmodell) wie Dicts an und gibt ein
    Equipment-taugliches Dict nur mit bekannten Feldern zurueck. Fehlende
    Seriennummern werden NICHT erfunden; sie bleiben einfach weg (None).
    """
    if isinstance(item, str):
        name = _clean_device_name(item)
        return {"device_name": name} if name else None
    if not isinstance(item, dict):
        return None
    cleaned: dict[str, Any] = {}
    for raw_key, val in item.items():
        key = _EQUIPMENT_ALIASES.get(raw_key, raw_key)
        if key not in _EQUIPMENT_KEEP or val is None:
            continue
        if isinstance(val, str):
            stripped = _clean_device_name(val) if key == "device_name" else val.strip()
            if stripped:
                cleaned[key] = (
                    [stripped] if key in _EQUIPMENT_SCOPE_LIST_KEYS else stripped
                )
        elif isinstance(val, list):
            if key in _EQUIPMENT_SCOPE_LIST_KEYS:
                items = _normalize_scope_list(val)
            else:
                items = [str(x).strip() for x in val if str(x).strip()]
            if items:
                cleaned[key] = items
        else:
            cleaned[key] = val
    return cleaned or None


def _normalize_equipment_payload(value: Any) -> Any:
    """Bringt Equipment-Proposals in das Schema `list[Equipment]`-taugliche Format.

    Behebt den UAT-Defekt „Geräte fehlen": Qwen lieferte frueher
    `["Impella\u00aeAIC System"]` – ein List-of-Strings – das bei der strikten
    Schema-Validierung als `schema_validation_failed` verworfen wurde.
    """
    if isinstance(value, str):
        normalized = _normalize_equipment_item(value)
        return [normalized] if normalized else []
    if isinstance(value, list):
        out: list[dict] = []
        for item in value:
            normalized = _normalize_equipment_item(item)
            if normalized is not None:
                out.append(normalized)
        return out
    if isinstance(value, dict):
        normalized = _normalize_equipment_item(value)
        return [normalized] if normalized else []
    return value


_SLA_TIMEVALUE_FIELDS = {
    "sla.response_time",
    "sla.resolution_time",
    "sla.service_hours",
    "sla.emergency_availability",
}


def _normalize_timevalue_payload(value: Any) -> Any:
    """Normalisiert SLA-TimeValue-Proposals (value/unit/original_text).

    Behandelt die Window-Semantik von `sla.service_hours`: Qwen liefert oft
    `{"start_time": "09:00", "end_time": "17:00", "days": ...}`. Diese Keys werden
    deterministisch zu einem `original_text` zusammengesetzt statt verworfen –
    die bisherige Key-Filterung liess sie zu `{}` kollabieren und der Fakt wurde
    als „Supported fact has no value" verworfen (UAT-Defekt Service Hours).
    """
    if isinstance(value, str):
        text = value.strip()
        return (
            {"value": None, "unit": None, "original_text": text} if text else None
        )
    if isinstance(value, (int, float)):
        return {"value": float(value), "unit": None, "original_text": None}
    if not isinstance(value, dict):
        return value
    cleaned: dict[str, Any] = {
        key: value.get(key)
        for key in ("value", "unit", "original_text")
        if value.get(key) is not None
    }
    original = cleaned.get("original_text")
    if original is None:
        start = value.get("start_time") or value.get("start")
        end = value.get("end_time") or value.get("end")
        days = value.get("days") or value.get("weekdays")
        if start or end or days:
            parts: list[str] = []
            if days:
                if isinstance(days, str):
                    parts.append(days.strip())
                else:
                    joined = ", ".join(str(d) for d in days if d)
                    if joined:
                        parts.append(joined)
            if start and end:
                parts.append(f"{start}-{end}")
            elif start:
                parts.append(f"ab {start}")
            elif end:
                parts.append(f"bis {end}")
            if parts:
                original = " ".join(p for p in parts if p)
    if original:
        cleaned["original_text"] = str(original)
    return cleaned or None


def _normalize_fact_value(field: str, value: Any) -> Any:
    if field in {"dates.start_date", "dates.end_date"}:
        return _normalize_date_payload(value)
    if field in {
        "dates.duration",
        "dates.minimum_duration",
        "termination.cancellation_period",
        "termination.renewal_period",
    }:
        return _normalize_duration_payload(value)
    if field in _MONEY_FIELDS:
        normalized = _normalize_money_payload(value)
        if isinstance(normalized, dict) and not normalized.get("period"):
            period = _MONEY_PERIOD_BY_FIELD.get(field)
            if period:
                normalized["period"] = period
        return normalized
    if field == "costs.default_currency" and isinstance(value, str):
        return value.strip().upper()
    if field == "costs.variable_charges" and isinstance(value, list):
        normalized = []
        for item in value:
            if not isinstance(item, dict):
                continue
            row = {
                key: item.get(key)
                for key in ("label", "amount", "unit", "condition")
                if key in item
            }
            if "amount" in row:
                row["amount"] = _normalize_row_amount(row["amount"], item.get("currency"))
            if "unit" not in row and item.get("unit"):
                row["unit"] = item["unit"]
            normalized.append(row)
        return normalized
    if field == "costs.scheduled_prices" and isinstance(value, list):
        normalized = []
        for item in value:
            if not isinstance(item, dict):
                continue
            row = {
                key: item.get(key)
                for key in ("period_index", "period_label", "amount", "condition")
                if key in item
            }
            if "amount" in row:
                row["amount"] = _normalize_row_amount(row["amount"], item.get("currency"))
            if "period_index" in row and isinstance(row["period_index"], str):
                try:
                    row["period_index"] = int(row["period_index"])
                except (ValueError, TypeError):
                    pass
            normalized.append(row)
        return normalized
    if field == "equipment":
        return _normalize_equipment_payload(value)
    if field in _SLA_TIMEVALUE_FIELDS:
        return _normalize_timevalue_payload(value)
    if field in {"services.included_services", "services.excluded_services"}:
        return _normalize_scope_list(value)
    if isinstance(value, str):
        return value.strip()
    return value


_SCOPE_LIST_ITEM_KEYS = ("name", "label", "description", "text", "value")


def _normalize_scope_list(value: Any) -> list[str]:
    """Normalisiert Leistungs-Listen deterministisch auf `list[str]`.

    Die strikte Schema-Validierung verwarf bisher jede Proposal-Form ausser
    `list[str]` (list-of-dicts, einzelner String, Leereintraege). Diese
    Normalisierung ist konservativ: ein dict traegt nur den ersten belegten
    Text-Key (name/label/description/text/value), Strings werden gestrippt,
    Leereintraege verworfen und Duplikate (Reihenfolge-erhaltend) entfernt.
    Es wird nie ein Leistungs-Item erfunden.
    """
    rows: list[str] = []
    if isinstance(value, str):
        item = value.strip()
        if item:
            rows.append(item)
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, str):
                item = entry.strip()
            elif isinstance(entry, dict):
                item = None
                for key in _SCOPE_LIST_ITEM_KEYS:
                    candidate = entry.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        item = candidate.strip()
                        break
            else:
                item = None
            if item:
                rows.append(item)
    return list(dict.fromkeys(rows))


# Deterministische, generische (nicht vertragsspezifische) Zuordnung eines
# evidengestuetzten Bool-Leistungsfakts zu seinem kanonischen deutschen
# Leistungs-Begriff. Reine Faelle: Reihenfolge ist fest, kein ABIOMED-Bezug.
_SERVICE_FACT_KEYS = (
    "maintenance", "inspection", "repair", "calibration", "software_updates",
    "remote_support", "technical_support", "spare_parts_included",
    "consumables_included", "emergency_service",
)

_SERVICE_FACT_LABELS_DE = {
    "maintenance": "Wartung",
    "inspection": "Sichtprüfung / Inspektion",
    "repair": "Reparatur",
    "calibration": "Kalibrierung",
    "software_updates": "Softwareupdates",
    "remote_support": "Fernwartung / Remote-Support",
    "technical_support": "Technischer Support",
    "spare_parts_included": "Ersatzteile",
    "consumables_included": "Verbrauchsmaterial",
    "emergency_service": "Notdienst",
}


_RUNTIME_DURATION_STRONG = (
    "vertragslaufzeit",
    "vertragsdauer",
    "laufzeit",
    "mietlaufzeit",
)

_RUNTIME_DURATION_WEAK = ("vertragszeitraum",)


def _build_page_evidence(
    page: int | None,
    quote: str,
    document: Any,
    canonical: Any,
    *,
    extraction_method: ExtractionMethod = ExtractionMethod.PROGRAMMATIC,
) -> Optional[SourceEvidence]:
    source = SourceEvidence(
        page=page,
        source_type="page",
        source_text=quote,
        extraction_method=extraction_method,
        requires_review=False,
    )
    if page is None:
        return source
    block = next(
        (
            candidate
            for candidate in document.pages_blocks.get(page, [])
            if _find_quote(candidate.text or "", quote) is not None
        ),
        None,
    )
    if block is not None:
        source.source_type = getattr(block, "source_type", "page")
        source.paragraph_index = (
            getattr(block, "source_index", None)
            if source.source_type == "paragraph"
            else None
        )
        source.table_index = (
            getattr(block, "source_index", None)
            if source.source_type == "table"
            else None
        )
        box = _bbox(block)
        if box is not None:
            source.bounding_box = box
        return source
    page_text = next(
        (
            candidate.text
            for candidate in canonical.pages
            if candidate.page_number == page and (candidate.text or "").strip()
        ),
        None,
    )
    if page_text is not None and _find_quote(page_text, quote) is not None:
        source.source_text = _clean_quote(page_text)
    return source


_TITLE_EXCLUSIONS = (
    "allgemeine geschäftsbedingungen",
    "allgemeine geschaeftsbedingungen",
    "datenschutzvereinbarung",
    "data processing agreement",
    "privacy policy",
)
_TITLE_MARKERS = ("servicevertrag", "rahmenvertrag", "wartungsvertrag", "kaufvertrag", "vertrag")


def _primary_contract_title(canonical, document) -> Optional[tuple[str, SourceEvidence]]:
    """Select a short, source-backed contract heading from the opening pages.

    Generic legal appendices often repeat a title-like heading near the end of a
    document. Restricting candidate search to the opening pages and excluding
    standard legal boilerplate keeps those headings from replacing the principal
    contract identity without relying on any vendor or product name.
    """
    for page in sorted(canonical.pages, key=lambda item: item.page_number)[:3]:
        candidates: list[tuple[int, str, str]] = []
        for block in sorted(
            document.pages_blocks.get(page.page_number, []),
            key=lambda item: getattr(item, "reading_order", 0),
        ):
            for raw_line in (block.text or "").splitlines():
                line = re.sub(r"\s+", " ", raw_line).strip(" \t\r\n:;|-")
                lowered = line.casefold()
                if not line or len(line) > 140 or any(term in lowered for term in _TITLE_EXCLUSIONS):
                    continue
                if not any(term in lowered for term in _TITLE_MARKERS):
                    continue
                if re.search(r"\b(?:paragraf|paragraph|artikel|article|seite|page)\s+\d", lowered):
                    continue
                priority = 0 if lowered.startswith(("servicevertrag", "rahmenvertrag", "wartungsvertrag")) else 1
                candidates.append((priority, line, line))
        if candidates:
            _priority, title, quote = min(candidates, key=lambda row: (row[0], len(row[1])))
            evidence = _build_page_evidence(page.page_number, quote, document, canonical)
            if evidence is not None:
                return title, evidence
    return None


def _duration_from_runtime_signal(
    contract: Any, signals, document: Any, canonical: Any
) -> Optional[tuple[Any, SourceEvidence]]:
    """Derive the contract duration from a literal "Laufzeit von X" sentence.

    This is a labelled literal in the source ("Der Vertrag hat eine Laufzeit von
    48 Monaten"), so code can read it deterministically instead of asking the
    model and hoping it picks the right sentence. Only used while
    `dates.duration` is still empty. Several sentences may repeat the same term
    ("Laufzeit von 48 Monaten" and "Verbrauchsmaterial fuer den Vertragszeitraum
    von 48 Monaten"); that agreement is accepted and the strongest sentence is
    used as evidence. Genuinely *different* durations stay unresolved.
    """
    candidates: list[tuple[int, Any, SourceEvidence]] = []
    for signal in signals:
        if _signal_field(signal, "kind") != "duration":
            continue
        page = _signal_field(signal, "page")
        if page is None:
            continue
        signal_value = _signal_field(signal, "value")
        quote = (_signal_field(signal, "quote") or "").strip()
        lowered = quote.casefold()
        if any(marker in lowered for marker in _RUNTIME_DURATION_STRONG):
            rank = 2
        elif any(marker in lowered for marker in _RUNTIME_DURATION_WEAK):
            rank = 1
        else:
            continue
        window = _temporal_candidates(signal_value)
        if not window:
            window = _temporal_candidates(quote)
        if len(window) != 1:
            continue
        value = _duration_unit_from_text(str(signal_value or "")) or window[0]["unit"]
        if value != window[0]["unit"]:
            continue
        evidence = _build_page_evidence(page, quote, document, canonical)
        if evidence is None:
            continue
        duration = _make_duration(window[0]["value"], value)
        if duration is None:
            continue
        candidates.append((rank, duration, evidence))
    if not candidates:
        return None
    distinct = {(row[1].value, getattr(row[1].unit, "value", row[1].unit)) for row in candidates}
    if len(distinct) > 1:
        # Mehrere unterschiedliche Laufzeiten: nicht raten.
        return None
    best_rank = max(row[0] for row in candidates)
    for rank, duration, evidence in candidates:
        if rank == best_rank:
            return duration, evidence
    return None


def _make_duration(number: int, unit: str) -> Optional[Any]:
    try:
        return Duration(value=number, unit=TimeUnit(unit))
    except (ValueError, TypeError):
        return None


# ------------------------------------------- Deterministische Preis-/Kostenableitung

_PRICE_TABLE_SECTION_MARKERS = (
    "einzelkomponenten",
    "verbrauchsmaterial",
    "mengenabweichung",
    "ausgleichszahlung",
)

# Aggregate rows repeat a total that is already carried by the item rows.
_AGGREGATE_LABEL_MARKERS = ("kosten ", "summe", "gesamt", "total")

_INSTALL_LABEL_MARKERS = (
    "install-kit",
    "install kit",
    "installationskosten",
    "inbetriebnahme",
    "installier",
)

_ONE_TIME_LABEL_MARKERS = (
    "anteilige zahlung",
    "einmalig",
    "pauschale",
)

_CONDITION_CLAUSE_MARKERS = (
    "nicht erreicht",
    "zielmengenverfehlung",
    "nichterreichung",
    "wahlrecht",
)

_EURO_HINT_RE = re.compile(r"(?:€|\bEUR\b)", re.IGNORECASE)


def _currency_from_text(text: str) -> Optional[str]:
    return "EUR" if _EURO_HINT_RE.search(text or "") else None


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in (line or "").split("|")]


def _price_row_candidates(page_text: str) -> list[dict]:
    """Every pipe-table row of a page that carries exactly one price per cell."""
    rows: list[dict] = []
    lines = (page_text or "").splitlines()
    for index, line in enumerate(lines):
        if "|" not in line:
            continue
        cells = _table_cells(line)
        if len(cells) < 2:
            continue
        label = next((cell for cell in cells if cell), "")
        for cell in cells:
            amounts = [
                (_money_amount(match.group(0)), match.group(0))
                for match in _MONEY_LITERAL_RE.finditer(cell)
            ]
            amounts = [(value, literal) for value, literal in amounts if value is not None]
            if not amounts or label == cell:
                # Die Label-Zelle selbst traegt den Betrag (z. B.
                # "Anteilige Zahlung: | | EUR 12.000,00") - weiter unten.
                continue
            for value, literal in amounts:
                rows.append(
                    {
                        "label": _clean_quote(label),
                        "amount": value,
                        "currency": _currency_from_text(cell) or _currency_from_text(line),
                        "literal": literal,
                        "line_index": index,
                        "row_text": " ".join(line.split()),
                        "context": " ".join(" ".join(part.split()) for part in lines[max(0, index - 15):index]),
                    }
                )
    return rows


def _money_from_literal(literal: str, period: Optional[str]) -> Optional[Money]:
    value = _money_amount(literal)
    if value is None:
        return None
    return Money(amount=value, currency="EUR", period=period)


def _derive_costs_from_price_tables(
    contract: Any, canonical: Any, document: Any
) -> list[dict]:
    """Read literal price-table rows into cost fields, without inferring periods.

    Purchase contracts carry their money in pipe tables ("Bezeichnung | Preis pro
    Stueck | Kaufpreis"). The model frequently returns those rows without page or
    quote, so the evidence gate drops them. Reading them here is deterministic: the
    amount must appear verbatim in its own row, and every row keeps its own page
    and row text as evidence. Recurring budgets (annual/monthly) are never touched
    here - those stay the AI's job behind the financial classification gate.
    """
    derived: list[dict] = []
    for page in canonical.pages:
        page_number = page.page_number
        page_text = page.text or ""
        if not page_text:
            continue
        variable_rows: list[dict] = []
        for row in _price_row_candidates(page_text):
            label = row["label"]
            if not label or re.match(r"^(bezeichnung|produkt|modell|menge)", label, re.IGNORECASE):
                continue
            if any(label.casefold().startswith(marker) for marker in _AGGREGATE_LABEL_MARKERS):
                continue
            context = row["context"].casefold()
            conditional = any(marker in context for marker in _CONDITION_CLAUSE_MARKERS) or any(
                marker in page_text.casefold() for marker in ("ausgleichszahlung", "zielmengenverfehlung")
            )

            if any(marker in label.casefold() for marker in _ONE_TIME_LABEL_MARKERS):
                if contract.costs.one_time_cost is None:
                    money = _money_from_literal(row["literal"], "once")
                    if money is not None:
                        contract.costs.one_time_cost = money
                        evidence = _build_page_evidence(
                            page_number, row["row_text"], document, canonical
                        )
                        if evidence is not None:
                            contract.costs.evidence = evidence
                        derived.append(
                            {
                                "field": "costs.one_time_cost",
                                "derivation": "literal_price_table_row",
                                "page": page_number,
                                "label": label,
                                "amount": money.amount,
                                "evidence": (
                                    evidence.model_dump(mode="json") if evidence else None
                                ),
                            }
                        )
                continue

            if any(marker in label.casefold() for marker in _INSTALL_LABEL_MARKERS):
                if contract.costs.setup_installation_cost is None:
                    money = _money_from_literal(row["literal"], "once")
                    if money is not None:
                        contract.costs.setup_installation_cost = money
                        evidence = _build_page_evidence(
                            page_number, row["row_text"], document, canonical
                        )
                        derived.append(
                            {
                                "field": "costs.setup_installation_cost",
                                "derivation": "literal_price_table_row",
                                "page": page_number,
                                "label": label,
                                "amount": money.amount,
                                "evidence": (
                                    evidence.model_dump(mode="json") if evidence else None
                                ),
                            }
                        )
                continue

            if conditional:
                variable_rows.append(row)

        condition_clause = _condition_clause(page_text)
        if variable_rows and condition_clause:
            row_evidence = _build_page_evidence(
                page_number, condition_clause, document, canonical
            )
        for row in variable_rows:
            money = _money_from_literal(row["literal"], None)
            if money is None:
                continue
            if any(
                existing.label == row["label"]
                and existing.amount.amount == money.amount
                for existing in contract.costs.variable_charges
            ):
                continue
            contract.costs.variable_charges.append(
                VariableCharge(
                    label=row["label"],
                    amount=money,
                    unit="per_piece",
                    condition=condition_clause,
                )
            )
            derived.append(
                {
                    "field": "costs.variable_charges",
                    "derivation": "literal_price_table_row",
                    "page": page_number,
                    "label": row["label"],
                    "amount": money.amount,
                    "condition": condition_clause,
                    "evidence": (
                        row_evidence.model_dump(mode="json") if row_evidence else None
                    ),
                }
            )

    return derived


def _condition_clause(page_text: str) -> Optional[str]:
    for line in (page_text or "").splitlines():
        if any(marker in line.casefold() for marker in _CONDITION_CLAUSE_MARKERS):
            cleaned = _clean_quote(" ".join(line.split()))
            if 20 <= len(cleaned) <= 400:
                return cleaned
    return None


# ---------------------------------------------- Startbedingung / Lieferantenbeleg

_START_CONDITION_RE = re.compile(
    r"[^.\n]{0,60}\b(?:startet|beginnt|gilt\s+ab)\b[^.\n]{0,160}", re.IGNORECASE
)

_START_CONDITION_TRIGGERS = (
    "installation",
    "inbetriebnahme",
    "übergabe",
    "uebergabe",
    "lieferung",
    "vertragsbeginn",
    "vertragsschluss",
)


def _derive_start_condition(
    contract: Any, canonical: Any
) -> Optional[tuple[str, Any]]:
    """Read the event the term starts on, e.g. "an dem Tag der Installation".

    The contract deliberately has no calendar start date, only a trigger. That is
    a literal clause, so it is read from the source instead of being inferred.
    """
    if contract.dates.start_condition:
        return None
    found: list[tuple[int, str]] = []
    for page in canonical.pages:
        page_text = page.text or ""
        if not page_text:
            continue
        for match in _START_CONDITION_RE.finditer(page_text):
            clause = _clean_quote(" ".join(match.group(0).split()))
            lowered = clause.casefold()
            if not any(trigger in lowered for trigger in _START_CONDITION_TRIGGERS):
                continue
            if len(clause) < 15 or len(clause) > 220:
                continue
            found.append((page.page_number, clause))
    distinct = {clause for _, clause in found}
    if len(distinct) != 1:
        # Abweichende Klauseln bleiben ungeklaert statt geraten.
        return None
    page_number, clause = found[0]
    return page_number, clause


_LEGAL_FORM_RE = re.compile(
    r"\b(?:GmbH|mbH|AG|KG|OHG|UG|SE|Ltd\.?|Inc\.?|B\.V\.|S\.A\.|N\.V\.|S\.r\.l\.)\b"
)

_ADDRESS_HINT_RE = re.compile(
    r"(?:\b\d{5}\b|stra(?:ss|ß)e|allee|weg\b|platz\b|betriebsstätte|betricbsstätte|anschrift)",
    re.IGNORECASE,
)


_ORG_NAME_RE = re.compile(
    r"\b((?:[A-ZÄÖÜ][\w&.\-]*\s+){0,5}?"
    r"(?:GmbH(?:\s*&\s*Co\.?\s*KG)?|mbH|AG|KG|OHG|UG|gGmbH|SE|KGaA|"
    r"Ltd\.?|Ltd|LLC|Inc\.?|Incorporated|Corporation|Corp\.?|PLC|"
    r"B\.V\.|S\.A\.|N\.V\.|S\.r\.l\.|S\.p\.A\.|A\.G\.|AB|AS|Oy|SAS|S\.à\s*r\.l\.))"
)

_PARTIES_SPLIT_RE = re.compile(r"\s+und\s+", re.IGNORECASE)

# Organisation names that appear in boilerplate but never denote the vendor.
_KNOWN_NON_PARTIES = frozenset(
    {
        "abbott medical gmbh betriebsstaette wetzlar schanzenfeldstr",
        "kliniken",
        "klinikum",
    }
)


def _org_key(name: str) -> str:
    """Comparable form of an organisation name (case, punctuation, spacing)."""
    cleaned = re.sub(r"[^\w\s]", " ", (name or "").casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


def _parties_clause(line: str, supplier: str) -> Optional[str]:
    """Trim an OCR run-together line down to the "zwischen A und B" clause.

    Scanned cover pages concatenate letterhead, footer and body text into one
    line. The contracting-parties sentence inside it is the strongest supplier
    citation, so the noisy surroundings are cut away.
    """
    # NOTE: never take an index from a case-folded copy - casefold can change the
    # string length ("ß" -> "ss") and would cut the clause at the wrong offset.
    start = re.search(r"zwischen", line, re.IGNORECASE)
    if start is None:
        return None
    supplier_pattern = r"\s+".join(re.escape(piece) for piece in supplier.split())
    match = re.search(supplier_pattern, line[start.start():], re.IGNORECASE)
    if match is None:
        return None
    clause = _clean_quote(line[start.start():])
    if not (10 <= len(clause) <= 400) or "und" not in clause.casefold():
        return None
    return clause


def _derive_supplier(contract: Any, canonical: Any, document: Any) -> Optional[Any]:
    """Read the supplier party deterministically from an explicit legal-form mention.

    The evidence gate correctly drops the model's supplier fact whenever it omits
    page/quote, which left the party empty even though the contract names it in
    plain sight. The name is therefore read from the text itself:

    1. the contracting-parties sentence ``zwischen A und B`` -> A is the vendor;
    2. otherwise the letterhead line carrying a legal form.

    Only a name that literally carries a legal form is accepted, the hospital
    customer is excluded, and an already accepted AI supplier is never replaced.
    """
    identity = getattr(contract, "identity", None)
    if identity is None:
        return None
    existing = (getattr(identity, "supplier", None) or "").strip()
    if existing:
        return None
    customer = (getattr(identity, "customer", None) or "").strip()
    customer_key = _org_key(customer)

    best: Optional[tuple[int, int, int, str, str]] = None
    for page in canonical.pages:
        page_number = page.page_number
        for line in (page.text or "").splitlines():
            candidate = " ".join(line.split())
            if not candidate or "|" in candidate or len(candidate) > 2000:
                continue
            for name, rank in _supplier_candidates(candidate):
                if customer_key and _org_key(name) == customer_key:
                    continue
                if _org_key(name) in _KNOWN_NON_PARTIES:
                    continue
                key = (rank, page_number, len(name), name, candidate)
                if best is None or key[:3] < best[:3]:
                    best = key
    if best is None:
        return None
    _rank, page_number, _length, name, source_line = best
    clause = _parties_clause(source_line, name)
    quote = clause or _clean_quote(source_line)
    if len(quote) > 400:
        quote = name
    evidence = _build_page_evidence(page_number, quote, document, canonical)
    if evidence is None:
        return None
    evidence.source_text = quote
    evidence.extraction_method = ExtractionMethod.PROGRAMMATIC
    identity.supplier = name
    return evidence


def _supplier_candidates(line: str) -> list[tuple[str, int]]:
    """Yield (organisation name, rank) pairs found in one canonical line.

    rank 0 - named as the first party of a "zwischen A und B" sentence;
    rank 1 - letterhead style mention with an address hint;
    rank 2 - any other legal-form mention.
    """
    found: list[tuple[str, int]] = []
    start = re.search(r"zwischen", line, re.IGNORECASE)
    if start is not None:
        head = line[start.start():]
        split = _PARTIES_SPLIT_RE.search(head)
        if split is not None:
            first_party = head[: split.start()]
            for match in _ORG_NAME_RE.finditer(first_party):
                name = _clean_quote(match.group(1))
                if _LEGAL_FORM_RE.search(name):
                    found.append((name, 0))
    has_address = bool(_ADDRESS_HINT_RE.search(line))
    for match in _ORG_NAME_RE.finditer(line):
        name = _clean_quote(match.group(1))
        if not _LEGAL_FORM_RE.search(name):
            continue
        found.append((name, 1 if has_address else 2))
    return found


def _bind_supplier_evidence(contract: Any, canonical: Any, document: Any) -> Optional[Any]:
    """Point the identity evidence at an explicit supplier letterhead line.

    The supplier name is often read off the contract title, which proves nothing
    about the party. A line that names the supplier together with its legal form
    (and preferably an address) is an actual mention of the supplier, so it is
    preferred as the group's evidence.
    """
    supplier = (getattr(getattr(contract, "identity", None), "supplier", None) or "").strip()
    if not supplier:
        return None
    current = getattr(getattr(contract, "identity", None), "evidence", None)
    if current is not None and supplier.casefold() in (getattr(current, "source_text", "") or "").casefold():
        return None

    supplier_pattern = r"\s+".join(re.escape(piece) for piece in supplier.split())
    best: Optional[tuple[int, int, int, str]] = None
    for page in canonical.pages:
        page_number = page.page_number
        for line in (page.text or "").splitlines():
            candidate = " ".join(line.split())
            if not candidate or "|" in candidate or len(candidate) > 2000:
                continue
            if not re.search(supplier_pattern, candidate, re.IGNORECASE):
                continue
            if not _LEGAL_FORM_RE.search(candidate):
                continue
            quote = _parties_clause(candidate, supplier) or candidate
            if "zwischen" in quote.casefold():
                rank = 0
            elif _ADDRESS_HINT_RE.search(candidate):
                rank = 1
            else:
                rank = 2
            key = (rank, page_number, len(quote), quote)
            if best is None or key[:3] < best[:3]:
                best = key
    if best is None:
        return None
    _rank, page_number, _length, candidate = best
    evidence = _build_page_evidence(page_number, candidate, document, canonical)
    if evidence is None:
        return None
    evidence.source_text = candidate
    evidence.extraction_method = ExtractionMethod.PROGRAMMATIC
    return evidence


def _equipment_from_title_evidence(
    contract: Any, title_evidence: Optional[SourceEvidence] = None
) -> Optional[Any]:
    """Derive one device deterministically from an evidence-bound contract title.

    Framing contracts are titled `Rahmenvertrag Nr. X - <Geraet>` and the device
    often never gets its own grounded fact (the model then omits page/quote and
    the evidence gate drops it). The title's own source quote is already bound to
    a real location, so the device name is read from that text instead of being
    invented. Only used when no equipment fact was accepted at all, and only when
    the candidate occurs verbatim in the bound title source.
    """
    title = getattr(getattr(contract, "identity", None), "contract_title", None)
    if title_evidence is None:
        title_evidence = getattr(getattr(contract, "identity", None), "evidence", None)
    if not title or title_evidence is None:
        return None
    source_text = getattr(title_evidence, "source_text", "") or ""
    normalized_source = " ".join(source_text.split()).casefold()
    candidate = ""
    for separator in (" - ", " – ", " — ", " –", " -"):
        if separator in title:
            tail = title.rsplit(separator, 1)[1].strip()
            if len(tail) >= 3:
                candidate = tail
            break
    if not candidate:
        return None
    if candidate.casefold() not in normalized_source:
        return None
    if not re.search(r"[A-Za-z\u00c4-\u00dc\u00e4-\u00fc]", candidate):
        return None
    if re.search(r"\bvertrag\b|\bRahmenvertrag\b", candidate, re.IGNORECASE):
        return None
    item = EquipmentModel(device_name=candidate)
    item.evidence = title_evidence
    return item


def _merge_service_scope_facts(services: Any) -> None:
    """Projiziert evidengestuetzte Bool-Leistungsfakten deterministisch in
    `services.included_services`.

    Die KI entscheidet sowohl die Bool-Fakten als auch (manchmal) die Liste
    ; sobald ein Bool-Fakt mit Quellen-Beleg TRUE ist, darf der zugehoerige
    Leistungs-Begriff nicht verloren gehen, nur weil die Proposal-Form der
    Liste von Lauf zu Lauf wechselt. Es werden NUR accepted Fakten (True)
    uebernommen – False/None bleiben aussen (fail-closed), Duplikate bleiben
    einmalig und die vorherige Listen-Reihenfolge bleibt erhalten.
    """
    if services is None:
        return
    included = list(getattr(services, "included_services") or [])
    for key in _SERVICE_FACT_KEYS:
        if getattr(services, key, None) is not True:
            continue
        label = _SERVICE_FACT_LABELS_DE.get(key)
        if label and label not in included:
            included.append(label)
    services.included_services = included


def _clean_quote(quote: str) -> str:
    cleaned = quote.strip()
    for marker in ("…", "..."):
        while cleaned.startswith(marker):
            cleaned = cleaned[len(marker):].lstrip()
        while cleaned.endswith(marker):
            cleaned = cleaned[:-len(marker)].rstrip()
    cleaned = cleaned.strip(" \t\r\n\"'")
    return cleaned


def _literal_strings(value: Any) -> list[str]:
    rows: list[str] = []
    if isinstance(value, str):
        text = value.strip()
        if len(text) >= 4:
            rows.append(text)
    elif isinstance(value, dict):
        for item in value.values():
            rows.extend(_literal_strings(item))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_literal_strings(item))
    return list(dict.fromkeys(rows))


def _find_casefold(source: str, needle: str) -> str | None:
    if not source or not needle:
        return None
    index = source.casefold().find(needle.casefold())
    if index < 0:
        return None
    return source[index:index + len(needle)]


def _signal_matches(field: str, value: Any, signal: dict) -> bool:
    kind = signal.get("kind")
    raw = str(signal.get("value") or "")
    payload = json.dumps(value, ensure_ascii=False, default=str)

    if field == "identity.contract_number" and kind == "labelled_contract_number":
        target = value if isinstance(value, str) else payload
        return _normalize_digits(str(target)) == _normalize_digits(raw)

    if field.startswith("dates.") and kind == "date":
        iso = _date_signal_iso(raw)
        return bool(iso and iso in payload)

    if field.startswith("dates.") and kind == "duration":
        number = re.search(r"\d+", raw)
        if not number:
            return False
        signal_amount = int(number.group(0))
        signal_unit = _duration_unit_from_text(raw)
        candidates = _duration_candidates(value)
        if not candidates:
            return False
        return any(
            candidate["value"] == signal_amount
            and (
                signal_unit is None
                or candidate.get("unit") is None
                or candidate["unit"] == signal_unit
            )
            for candidate in candidates
        )

    if field == "termination.automatic_renewal" and kind == "renewal_negation":
        return value is False

    if field.startswith("costs.") or field.startswith("payment."):
        if kind != "money":
            return False
        amount = _money_amount(raw)
        if amount is None:
            return False
        candidates: list[float] = []
        if isinstance(value, dict):
            direct = value.get("amount")
            if isinstance(direct, (int, float)):
                candidates.append(float(direct))
            elif isinstance(direct, dict) and isinstance(direct.get("amount"), (int, float)):
                candidates.append(float(direct["amount"]))
        elif isinstance(value, (int, float)):
            candidates.append(float(value))
        elif isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                money = item.get("amount")
                if isinstance(money, (int, float)):
                    candidates.append(float(money))
                elif isinstance(money, dict) and isinstance(money.get("amount"), (int, float)):
                    candidates.append(float(money["amount"]))
        return any(abs(candidate - amount) < 0.001 for candidate in candidates)

    return False


_STAGED_YEAR_RE = re.compile(
    r"\b(?:im\s+)?(\d{1,2})\s*\.?\s*Jahr\b(?P<label>[^|\n]{0,150}?)(?:\s*\|\s*|\s+)(?P<amount>\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d+)\s*(?:EUR|€)",
    re.IGNORECASE,
)
_PER_CALL_RE = re.compile(
    r"\bper\s+calls?\b\s*[:]?\s*(?P<amount>\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})?|\d+)\s*(?:EUR|€)",
    re.IGNORECASE,
)

# Deterministic pricing-annex reader.  Qwen still decides the contractual role
# (which money literals are scheduled/staged vs per-call vs recurring); this
# reader then re-reads those literals verbatim from the source page so the
# transcribed numbers can never drift (8.000,00 -> 8.0) or turn into invented
# totals.  It is generic German contract language, not a per-contract fixture.
def _staged_price_rows(text: str) -> list[tuple[dict, str]]:
    rows: list[tuple[dict, str]] = []
    for match in _STAGED_YEAR_RE.finditer(text or ""):
        amount = _money_amount(match.group("amount"))
        if amount is None:
            continue
        rows.append(
            (
                {
                    "period_index": int(match.group(1)),
                    "period_label": (match.group("label") or "").strip() or None,
                    "amount": {"amount": amount, "currency": "EUR", "period": None},
                    "condition": None,
                },
                match.group(0),
            )
        )
    return rows


def _per_call_rows(text: str) -> list[tuple[dict, str]]:
    rows: list[tuple[dict, str]] = []
    for match in _PER_CALL_RE.finditer(text or ""):
        amount = _money_amount(match.group("amount"))
        if amount is None:
            continue
        rows.append(
            (
                {
                    "label": (match.group(0) or "").strip(),
                    "amount": {"amount": amount, "currency": "EUR", "period": None},
                    "unit": "per_call",
                    "condition": None,
                },
                match.group(0),
            )
        )
    return rows


# Money literal matcher for staged label+amount verification.  German scans
# write "€ 12.000,00" as well as "12.000,00 EUR" and table OCR interleaves
# pipes/spacing; both currency positions are accepted, a bare number is never
# treated as money.
_MONEY_LITERAL_RE = re.compile(
    r"(?<!\w)(?:€|EUR)\s*(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d{2})?\s*(?:€|EUR)?(?!\w)"
    r"|(?<!\w)(?:€|EUR)?\s*(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d{2})?\s*(?:€|EUR)(?!\w)",
    re.IGNORECASE,
)

_MONEY_STOPWORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "eines", "einer",
    "und", "oder", "für", "fur", "in", "im", "auf", "an", "ab", "von", "mit",
    "zum", "zur", "am", "bei", "aus", "je", "pro", "netto",
}


def _money_amounts_from_value(value: Any) -> list[float]:
    """Recursively collect every monetary amount contained in a fact value."""
    amounts: list[float] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"amount", "value"} and isinstance(item, (int, float)):
                amounts.append(float(item))
            elif key == "amount" and isinstance(item, str):
                parsed = _money_amount(item)
                if parsed is not None:
                    amounts.append(parsed)
            else:
                amounts.extend(_money_amounts_from_value(item))
    elif isinstance(value, list):
        for item in value:
            amounts.extend(_money_amounts_from_value(item))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        amounts.append(float(value))
    elif isinstance(value, str):
        parsed = _money_amount(value)
        if parsed is not None:
            amounts.append(parsed)
    return list(dict.fromkeys(round(a, 2) for a in amounts if a is not None))


def _money_label_phrase(quote: str) -> str:
    """Label phrase from a money quote with the amount literal removed.

    Pipes and other table separators are reduced to spaces so the phrase can be
    located with the same tolerant matcher as a normal quote.
    """
    cleaned = _MONEY_LITERAL_RE.sub(" ", quote or "")
    words = [
        word
        for word in re.findall(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9\-/]*", cleaned)
        if word.casefold() not in _MONEY_STOPWORDS and len(word) >= 2
    ]
    return " ".join(words)


def _locate_money_staged(
    document: DocumentModel,
    page_blocks: list[Block],
    quote: str,
    amounts: list[float],
) -> tuple[Block, str] | None:
    """OCR-tolerant label+amount evidence binding for money facts.

    Anchors the exact amount literal on the fact's page and requires the label
    to co-occur near it (tolerant to pipes, line breaks, whitespace and small
    OCR typos).  The caller already restricts ``page_blocks`` to the fact's page,
    so an amount that only exists on another page can never bind here.  A money
    figure is never accepted by the number alone: without a matching label
    phrase only a *unique* amount occurrence counts, and any ambiguity or
    non-uniqueness resolves to None (fail-closed).
    """
    if not amounts or not page_blocks:
        return None
    label_phrase = _money_label_phrase(quote)
    candidates: set[tuple[str, int, str]] = set()
    for block in page_blocks:
        text = block.text or ""
        for match in _MONEY_LITERAL_RE.finditer(text):
            amount = _money_amount(match.group(0))
            if amount is None or not any(
                abs(round(amount, 2) - expected) < 0.001 for expected in amounts
            ):
                continue
            start = max(0, match.start() - 120)
            end = min(len(text), match.end() + 120)
            window = text[start:end]
            if label_phrase and _find_quote_tolerant(window, label_phrase) is None:
                continue
            candidates.add((block.id, match.start(), match.group(0)))
    if len(candidates) != 1:
        return None
    block_id, start, literal = next(iter(candidates))
    block = document.index.get(block_id)
    if block is None:
        return None
    return block, literal.strip()


def _steady_annual_amount(rows: list[dict], *, expected_years: int | None = None) -> float | None:
    """Infer a steady rate ONLY from a contiguous, complete year-price schedule.

    This is a calculation, not a newly observed contract fact.  A missing period,
    duplicate year, inconsistent currency or incomplete expected duration means
    the yearly price cannot safely be inferred.
    """
    if not rows or (expected_years is not None and expected_years < 3):
        return None
    by_index: dict[int, dict] = {}
    currencies: set[str] = set()
    for row in rows:
        idx = row.get("period_index")
        money = row.get("amount")
        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 1:
            return None
        if idx in by_index or not isinstance(money, dict) or money.get("amount") is None:
            return None
        by_index[idx] = money
        if money.get("currency"):
            currencies.add(str(money["currency"]).upper())
    if len(currencies) > 1:
        return None
    indices = sorted(by_index)
    if indices[0] != 1 or indices != list(range(1, indices[-1] + 1)):
        return None
    if expected_years is not None and indices[-1] != expected_years:
        return None
    if len(indices) < 3:
        return None
    later = [by_index[i]["amount"] for i in indices[1:]]
    if not later or any(amount != later[0] for amount in later):
        return None
    if not isinstance(later[0], (int, float)) or isinstance(later[0], bool) or later[0] <= 0:
        return None
    return float(later[0])


def _complete_scheduled_total(rows: list[dict], *, expected_years: int | None) -> float | None:
    """Sum a complete, contiguous staged schedule without treating it as a quote."""
    if not rows or expected_years is None or expected_years < 1:
        return None
    amounts: dict[int, float] = {}
    currencies: set[str] = set()
    for row in rows:
        index = row.get("period_index")
        money = row.get("amount")
        amount = money.get("amount") if isinstance(money, dict) else None
        currency = money.get("currency") if isinstance(money, dict) else None
        if (
            not isinstance(index, int) or isinstance(index, bool) or index < 1
            or index in amounts
            or not isinstance(amount, (int, float)) or isinstance(amount, bool)
            or amount < 0
            or not currency
        ):
            return None
        amounts[index] = float(amount)
        currencies.add(str(currency).upper())
    if len(currencies) != 1 or sorted(amounts) != list(range(1, expected_years + 1)):
        return None
    return round(sum(amounts.values()), 2)


# Deterministische Finanzklassifikations-Logik (GATE 1 - EUR 12.000):
# Ein Betrag, dessen WAEHRUNGS-MEANING (annual/semi_annual/quarterly/monthly/
# maintenance) nicht belegt ist, darf nie als wiederkehrende Verpflichtung in
# die autoritativen Kostenfelder (und damit in Kalkulation/Forecast) einfliessen.
# Beleg ist NUR deterministisch und bindet PERIODE + BETRAG an DIESELBE Evidenz:
#   (a) das lokalisierte Fakt-Zitat traegt den Perioden-Anker UND genau den
#       vorgeschlagenen Geldbetrag, ODER
#   (b) eine korroborierte visuelle Zeile (genau diese Seite) matcht den Betrag
#       UND bezeugt die Periodizitaet selbst (Label/Quote mit Anker), ODER
#   (c) Legacy-/Hybrid-Pfad ohne Visual-First-Zeilen (bestehende Locator-Evidenz).
# Ein Periodenwort irgendwo auf der Seite oder in einer unpassenden Zeile ist
# KEIN Klassifikationsbeweis fuer den vorgeschlagenen Betrag.
_PERIOD_FIELDS: dict[str, re.Pattern[str]] = {
    "costs.annual_cost": re.compile(
        r"j[äa]hrlich|jaehrlich|pro\s+jahr|jahres(?:preis|geb[\u00fc]hr|gebuehr)|(?<!semi[- ])\bannual\b", re.I),
    "costs.semi_annual_cost": re.compile(
        r"halbj[äa]hrlich|halbjaehrlich|semi\s*-?\s*annual|halbes\s+jahr", re.I),
    "costs.quarterly_cost": re.compile(
        r"quartals\w*|quarterly|viertelj[äa]hrlich|je\s+quartal", re.I),
    "costs.monthly_cost": re.compile(
        r"monatl(?:ich)?|monthly|pro\s+monat", re.I),
    "costs.maintenance_fee": re.compile(
        r"wartung|maintenance|service(?:geb[\u00fc]hr|gebuehr)|(?:service\s+)?fee\b", re.I),
}


_TEMPORAL_FIELDS = {
    "dates.start_date",
    "dates.end_date",
    "dates.duration",
    "dates.minimum_duration",
}

_TEMPORAL_DATE_FIELDS = {"dates.start_date", "dates.end_date"}

_TEMPORAL_UNIT_BY_FIELD_UNIT = {
    "year": "years",
    "years": "years",
    "month": "months",
    "months": "months",
    "week": "weeks",
    "weeks": "weeks",
    "day": "days",
    "days": "days",
    "hour": "hours",
    "hours": "hours",
}


def _canonical_temporal_unit(unit: Any) -> Optional[str]:
    return _TEMPORAL_UNIT_BY_FIELD_UNIT.get(str(unit or "").strip().casefold())


def _temporal_date_candidates(value: Any) -> list[str]:
    """ISO dates carried by a proposed date value or a signal literal."""
    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for raw_key, raw_value in node.items():
                key = str(raw_key).strip().casefold()
                if key in {"date", "literal_value", "iso", "iso_date", "yyyy-mm-dd"}:
                    iso = _date_signal_iso(str(raw_value))
                    if iso:
                        found.append(iso)
                else:
                    walk(raw_value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            iso = _date_signal_iso(node)
            if iso:
                found.append(iso)

    walk(value)
    return found


def _temporal_candidates(value: Any) -> list[dict]:
    """Extract comparable (number, unit) pairs from a proposed date/duration."""
    rows: list[dict] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            unit = None
            number = None
            for key, expected in (
                ("years", "years"),
                ("months", "months"),
                ("weeks", "weeks"),
                ("days", "days"),
                ("hours", "hours"),
                ("year", "years"),
                ("month", "months"),
                ("week", "weeks"),
                ("day", "days"),
                ("hour", "hours"),
            ):
                if node.get(key) is not None:
                    unit = expected
                    number = node.get(key)
                    break
            if unit is None and node.get("value") is not None and node.get("unit"):
                unit = _canonical_temporal_unit(node.get("unit"))
                number = node.get("value")
            if unit is not None and number is not None:
                try:
                    rows.append({"value": int(float(number)), "unit": unit})
                except (TypeError, ValueError, OverflowError):
                    pass
            for nested in node.values():
                walk(nested)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            for match in re.finditer(
                r"(\d+)\s*(Jahr(?:e|en)?|Monat(?:e|en)?|Woche(?:n)?|Tag(?:e|en)?|Stunde(?:n)?"
                r"|years?|months?|weeks?|days?|hours?)",
                node,
                re.IGNORECASE,
            ):
                stem = match.group(2).casefold()
                for prefix, unit in (
                    ("jahr", "years"),
                    ("year", "years"),
                    ("monat", "months"),
                    ("month", "months"),
                    ("woch", "weeks"),
                    ("week", "weeks"),
                    ("tag", "days"),
                    ("day", "days"),
                    ("stund", "hours"),
                    ("hour", "hours"),
                ):
                    if stem.startswith(prefix):
                        rows.append({"value": int(match.group(1)), "unit": unit})
                        break

    walk(value)
    return rows


def _signal_field(signal: Any, name: str) -> Any:
    """Read a source-signal field from either the dataclass or its dict form."""
    if isinstance(signal, dict):
        return signal.get(name)
    return getattr(signal, name, None)


def _temporal_signal_supported(fact, signals) -> bool:
    """A proposed date/duration must be corroborated by a signal on its page.

    The model happily maps an unrelated sentence onto a date field (e.g. reading
    "Dauer i.d.R. 2 - 3 Wochen" - an installation lead time - as the contract
    duration). A temporal fact is only accepted when a `date`/`duration` source
    signal on the evidence page carries the very same number *and* unit. This is
    the deterministic counterpart to the financial classification gate.
    """
    value = getattr(fact, "value", None)
    page = getattr(fact, "page", None)
    same_page = [
        signal
        for signal in signals
        if page is None or _signal_field(signal, "page") == page
    ]

    if fact.field in _TEMPORAL_DATE_FIELDS:
        proposed_dates = set(_temporal_date_candidates(value))
        if not proposed_dates:
            return False
        signal_dates: set[str] = set()
        for signal in same_page:
            if _signal_field(signal, "kind") != "date":
                continue
            signal_dates.update(_temporal_date_candidates(_signal_field(signal, "value")))
            signal_dates.update(_temporal_date_candidates(_signal_field(signal, "quote")))
        return bool(proposed_dates & signal_dates)

    proposed = _temporal_candidates(value)
    if not proposed:
        return False
    signal_rows: list[dict] = []
    for signal in same_page:
        if _signal_field(signal, "kind") != "duration":
            continue
        signal_rows.extend(_temporal_candidates(_signal_field(signal, "value")))
        signal_rows.extend(_temporal_candidates(_signal_field(signal, "quote")))
    for expected in proposed:
        for row in signal_rows:
            if row["value"] == expected["value"] and row["unit"] == expected["unit"]:
                return True
    return False


def _financial_classification_verified(
    fact, visual_first_rows, *, resolved_page=None,
) -> bool:
    """Recurring-cost classification requires period AND amount to share evidence.

    A period word anywhere on the page - or in a different quote / corroborated
    row - is never accepted as proof for the proposed amount. The amount must
    co-occur with the periodicity in the located fact quote or in a corroborated
    visual row whose value matches the amount and whose label/quote carries the
    anchor. The legacy/hybrid path without visual-first rows is unchanged.
    """
    anchor = _PERIOD_FIELDS.get(fact.field)
    if anchor is None:
        # Nicht-disretionäre Felder (identity, dates, termination, SLA-Liste,
        # scheduled_prices/variable_charges) unterliegen ihres eigenen Schemas.
        return True
    if not visual_first_rows:
        # Legacy-/Hybrid-Pfad ohne Visual-First: unveraendert (Money-OCR-Tests).
        return True

    expected = _money_amounts_from_value(getattr(fact, "value", None))
    if len(expected) != 1:
        # Null oder mehrere Betraege sind keine eindeutige Einzel-Referenz fuer
        # eine Periodenkategorie; solche Fakten bleiben klassifikations-offen.
        return False
    amount = expected[0]

    def exactly_proposed_amount(text: str) -> bool:
        literals = [
            parsed
            for match in _MONEY_LITERAL_RE.finditer(text or "")
            for parsed in [_money_amount(match.group(0))]
            if parsed is not None
        ]
        return len(literals) == 1 and round(literals[0], 2) == round(amount, 2)

    # (a) Das lokalisierte Zitat traegt den Anker UND genau den vorgeschlagenen
    # Betrag. Ein Mehrfachbetrag-Klausel ("... 5.000 EUR; einmalig 12.000 EUR")
    # bleibt ambig: ein Periodenwort darf nie auf eine andere Quantitaet im
    # selben Zitat verweisen.
    if fact.quote and anchor.search(fact.quote) and exactly_proposed_amount(fact.quote):
        return True

    # (b) Korrobierte Zeile: beweist Label+Wert-Paar auf dieser Seite; der Wert
    # muss dem vorgeschlagenen Betrag entsprechen UND die Zeile selbst die
    # Periodizitaet bezeugen (Label oder eigenes Zitat).
    page = resolved_page if resolved_page is not None else fact.page
    for row in visual_first_rows:
        if row.page != page or row.status != "corroborated":
            continue
        if _money_amount(row.value) != amount:
            continue
        for observation in row.observations:
            if anchor.search(observation.label or ""):
                return True
            if anchor.search(observation.quote or "") and exactly_proposed_amount(
                observation.quote
            ):
                return True
    return False


def _warmup_image_base64() -> str:
    """Kleines Graustufen-PNG (dep-frei via zlib/struct) fuer den Vision-Warmup."""
    import base64
    import struct
    import zlib

    width = height = 96
    row = b"\x00" + b"\x80" * width
    raw = row * height

    def chunk(tag: bytes, data: bytes) -> bytes:
        block = tag + data
        return struct.pack(">I", len(data)) + block + struct.pack(">I", zlib.crc32(block))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode("ascii")


async def _warm_up_vision(provider, context: int) -> None:
    """Eine begrenzte multimodale Call-Instruktion als deterministischer Warmup.

    Nach einem Modell-Load kann die erste Vision-Inferenz pathologisch lang sein
    (kein Token fuer Minuten). Dieser Warmup traegt diese Kosten einmalig und
    frueh; danach lesen die echten Seiten nur noch warm. Scheitert er, faellt
    die Analyse bestimmt und frueh statt mitten in den Seitenlesungen.
    """
    schema = VisualPageReading.model_json_schema()
    await provider.generate_request(
        "You receive a blank placeholder image. Read nothing. "
        "Return an empty reading for page 1.",
        "Return exactly the JSON schema output.",
        schema,
        64,
        min(int(context), 4096),
        [_warmup_image_base64()],
    )

class DirectContractHarness:
    """Small orchestration layer: semantic extraction once, deterministic proof once."""

    def __init__(self, settings: Settings, ai: AIService | None = None):
        self.settings = settings
        self.ai = ai or AIService(settings)

    async def analyze(self, canonical, image_loader=None, page_image_loader=None,
                      original_page_loader=None):
        from app.ai.contract_extractor import ContractAnalysisResult

        started = time.monotonic()
        original_page_loader = original_page_loader or page_image_loader
        document = DocumentModel.build(canonical)
        types = field_types()
        source_signals = collect_source_signals(document)
        calls: list[dict] = []
        analysis_id = str(uuid.uuid4())
        rejected: list[dict] = []
        evidence_rows: list[dict] = []
        accepted: list[dict] = []
        accepted_evidence_by_field: dict[str, SourceEvidence] = {}
        visual_readings: dict[int, VisualPageReading] = {}
        issues: list[str] = []
        provider_id = model_id = None

        try:
            provider, descriptor = await self.ai.harness_runtime()
            provider_id = descriptor.provider_id
            model_id = descriptor.model_id
            for row in calls:
                row["provider"] = provider_id
                row["model"] = model_id
            if descriptor.capabilities.text is not True:
                raise ValueError("Selected model does not support text analysis")
            if not provider.supports_structured_output:
                raise ValueError("Selected provider lacks structured output")
            if not document.blocks:
                raise ValueError("Canonical document has no analyzable source")

            capacity = int(
                min(
                    getattr(self.settings, "harness_context_tokens", 8192),
                    descriptor.context_length or getattr(self.settings, "harness_context_tokens", 8192),
                )
            )
            base_output = int(getattr(self.settings, "harness_output_tokens", 1800))
            vision_output = min(
                base_output,
                int(getattr(self.settings, "harness_vision_output_tokens", base_output)),
            )
            semantic_schema = ProposedFactBatch.model_json_schema()
            system_prefix = SYSTEM + "\nOutput JSON schema: " + json.dumps(
                semantic_schema, separators=(",", ":")
            )

            async def call(purpose: str, prompt: str, schema_type, *, images=None, stage="semantic", output_budget=None):
                schema = schema_type.model_json_schema()
                system = SYSTEM + "\nOutput JSON schema: " + json.dumps(
                    schema, separators=(",", ":")
                )
                prompt_tokens = _estimate_tokens(system + prompt)
                metric = {
                    "analysis_id": analysis_id,
                    "provider": provider_id or getattr(self.ai, "provider_id", None),
                    "model": model_id or getattr(self.ai, "model_id", None),
                    "purpose": purpose,
                    "stage": stage,
                    "schema": schema_type.__name__,
                    "estimated_prompt_tokens": prompt_tokens,
                    "requested_context": capacity,
                    "output_reserve": _CONTEXT_RESERVE,
                    "failed": False,
                }
                calls.append(metric)

                def safe_error_category(exc: Exception) -> str:
                    category = getattr(exc, "category", None)
                    if category:
                        return str(category)
                    if type(exc).__name__ == "ValidationError":
                        return "schema_validation"
                    if isinstance(exc, (ValueError, TypeError)):
                        return "schema_validation"
                    return "unknown"

                output_tokens = base_output if output_budget is None else int(output_budget)
                attempt = 0
                allow_growth = bool(
                    getattr(self.settings, "harness_allow_context_growth", False)
                )
                while True:
                    image_reserve = 1024 * len(images or [])
                    effective_context = _effective_context(
                        prompt_tokens,
                        output_tokens,
                        capacity,
                        descriptor.context_length,
                        image_reserve,
                        allow_growth=allow_growth,
                    )
                    if not _fits_output_budget(
                        prompt_tokens, output_tokens, effective_context, image_reserve
                    ):
                        shrunk = _shrunk_output_budget(
                            prompt_tokens, effective_context, image_reserve
                        )
                        if shrunk < output_tokens:
                            output_tokens = shrunk
                            metric["output_budget_shrunk_to"] = shrunk
                    if attempt == 0:
                        metric["effective_context"] = effective_context
                    metric["retry_count"] = attempt
                    begin = time.monotonic()
                    try:
                        raw = await provider.generate_request(
                            prompt,
                            system,
                            schema,
                            output_tokens,
                            effective_context,
                            images,
                        )
                        metric["latency_seconds"] = round(time.monotonic() - begin, 3)
                        metric["done_reason"] = getattr(provider, "last_done_reason", None)
                        metric["response_chars"] = len(raw)
                        metric["response_sha256"] = (
                            getattr(provider, "last_response_sha256", None)
                            or hashlib.sha256(raw.encode("utf-8")).hexdigest()
                        )
                        usage = getattr(provider, "last_usage", None) or {}
                        actual_prompt_tokens = usage.get("prompt_tokens")
                        if actual_prompt_tokens:
                            metric["actual_prompt_tokens"] = int(actual_prompt_tokens)
                            prompt_tokens = int(actual_prompt_tokens)
                        if metric["done_reason"] in {"length", "max_tokens"}:
                            raise RuntimeError("output_truncated")
                        parsed = schema_type.model_validate_json(raw)
                        metric["succeeded"] = True
                        return parsed
                    except Exception as exc:
                        if str(exc) == "output_truncated" and attempt == 0:
                            metric["truncation_count"] = 1
                            next_output, decision = _retry_output_plan(
                                purpose,
                                prompt_tokens,
                                effective_context,
                                base_output,
                                1024 * len(images or []),
                            )
                            metric["retry_decision"] = decision
                            metric["retry_prompt_tokens"] = prompt_tokens
                            metric["retry_effective_context"] = effective_context
                            if next_output is not None:
                                output_tokens = next_output
                                metric["retried_with_output_tokens"] = next_output
                                attempt += 1
                                continue
                            metric["retry_not_performed"] = True
                        metric["failed"] = True
                        metric["succeeded"] = False
                        metric["error_type"] = type(exc).__name__
                        metric["error_category"] = (
                            "truncated_output"
                            if str(exc) == "output_truncated"
                            else safe_error_category(exc)
                        )
                        raise

            visual_first_data = None
            visual_first_rows = []
            if getattr(self.settings, "visual_first_experiment_enabled", False):
                if descriptor.capabilities.vision is not True:
                    raise ValueError("Visual-First requires the selected vision model")
                from app.ai.harness.visual_first_bridge import prepare_visual_first
                if getattr(self.settings, "harness_vision_warmup_enabled", True):
                    try:
                        await _warm_up_vision(provider, capacity)
                    except Exception as warmup_exc:
                        raise ValueError(
                            "Vision warm-up failed (%s): cold-start inference is "
                            "unstable; aborting deterministically"
                            % type(warmup_exc).__name__
                        ) from warmup_exc
                visual_readings, visual_first_rows, visual_first_data = await prepare_visual_first(
                    canonical=canonical,
                    source_signals=source_signals,
                    page_image_loader=original_page_loader,
                    provider=provider,
                    context=capacity,
                    output_tokens=vision_output,
                    max_pages=self.settings.visual_first_max_pages,
                    max_reviews=self.settings.visual_first_max_reviews,
                )
                calls.extend(
                    {"purpose": "visual-first:%s:%s" % (item["stage"], item["page"]),
                     "stage": item["stage"], "failed": False, "succeeded": True}
                    for item in visual_first_data["calls"]
                )
                if any(item.get("rejected_page_mismatch")
                       for item in visual_first_data["calls"]):
                    issues.append("Visual-First page mismatch requires manual review")
                if any(item.get("provenance_ambiguous_multipage") or
                       item.get("provenance_ambiguous_on_other_page") or
                       item.get("provenance_unverified_by_ocr")
                       for item in visual_first_data["calls"]):
                    issues.append("Visual-First ambiguous provenance requires manual review")
                if any(item.get("rejected_invalid_region") or
                       item.get("rejected_malformed_claim")
                       for item in visual_first_data["calls"]):
                    issues.append("Visual-First invalid source claim requires manual review")
                if any(item.get("rejected_page_error") or item.get("rejected_review_error")
                       for item in visual_first_data["calls"]):
                    issues.append("Visual-First unreadable page requires manual review")
                for row in visual_first_rows:
                    if row.status != "corroborated":
                        issues.append("Visual-First evidence requires human review")
                        break

            # JAMAL v1: deterministic hybrid routing. Vision is used for image-only
            # and structurally ambiguous scanned/OCR pages, while clean native-text
            # pages remain text-only. Routing decides compute only, never meaning.
            candidate_pages = visual_candidate_pages(canonical)
            page_routes = route_summary(canonical)
            calls.append({
                "purpose": "routing:hybrid-pages",
                "stage": "routing",
                "routes": page_routes,
                "vision_candidates": candidate_pages,
                "failed": False,
                "succeeded": True,
            })
            if (not getattr(self.settings, "visual_first_experiment_enabled", False)
                    and candidate_pages and descriptor.capabilities.vision is True
                    and page_image_loader is not None):
                max_visual = min(
                    len(candidate_pages),
                    int(getattr(self.settings, "harness_vision_max_calls", 4)),
                )
                for page_number in candidate_pages[:max_visual]:
                    image = page_image_loader(page_number)
                    reading = await call(
                        f"vision:{page_number}",
                        f"Read contract page {page_number} visually. The canonical OCR text layer "
                        f"already covers this page. Return at most {_VISION_MAX_FRAGMENTS} short "
                        f"fragments per list, each at most {_VISION_FRAGMENT_MAX_CHARS} characters. "
                        "visible_text: only fragments that are missing from or clearly wrong in the "
                        "OCR layer (dates, amounts, negated clauses), copied verbatim without ellipses. "
                        "layout_relations: only explicit visual relationships such as 'this column "
                        "header applies to that row', 'this checkbox is marked', 'signature block at "
                        "the bottom of the page'. Do not repeat the full page text, do not summarize, "
                        "and do not infer contractual meaning. Put anything uncertain in unresolved. "
                        f"Return page={page_number}.",
                        VisualPageReading,
                        images=[image],
                        stage="vision",
                        output_budget=vision_output,
                    )
                    visual_readings[page_number] = reading

            if not any((page.text or "").strip() for page in canonical.pages) and not visual_readings:
                raise ValueError("No readable source text or vision transcription")

            proposals: list[ProposedFact] = []
            for pack_name, selectors, topics, expand_keywords in PACKS:
                catalog = _field_catalog(types, selectors)
                pack_pages = _pack_pages(topics, canonical, source_signals, expand_keywords)
                pack_signals = [
                    signal
                    for signal in source_signals
                    if (signal.get("page") is None or signal.get("page") in pack_pages)
                    and signal.get("kind")
                    in {
                        "date",
                        "money",
                        "duration",
                        "labelled_contract_number",
                        "renewal_negation",
                    }
                ]
                guidance = _PACK_GUIDANCE.get(pack_name, "")
                catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))

                def build_pack_prompt(pages: list[int], chunk_signals: list[dict]) -> str:
                    return (
                        f"Extract the {pack_name} contract facts from the source below. "
                        "Use Qwen semantic understanding to decide what each literal value means. "
                        "The literal source signals are observations, not final facts. "
                        "Inspect every relevant signal and decide its contractual role. "
                        "For every accepted fact page and exact quote are mandatory; copy the quote verbatim, without ellipses. "
                        "Do not output fields outside this catalog. Omit facts that are not actually present."
                        + (" " + guidance if guidance else "")
                        + "\n\nFIELD CATALOG:\n"
                        + catalog_json
                        + "\n\nLITERAL SOURCE SIGNALS (pages "
                        + str(pages)
                        + "):\n"
                        + json.dumps(chunk_signals, ensure_ascii=False, separators=(",", ":"))
                        + "\n\nCONTRACT SOURCE (pages "
                        + str(pages)
                        + "):\n"
                        + _pack_source(canonical, pages, visual_readings)
                    )

                # A single call must fit the operator's context budget together with
                # its output budget. A too-large pack is therefore split into page
                # chunks instead of being truncated mid-answer or silently dropped.
                def chunk_signals_for(pages: list[int]) -> list[dict]:
                    return [
                        signal
                        for signal in pack_signals
                        if signal.get("page") is None or signal.get("page") in pages
                    ]

                def prompt_fits(pages: list[int]) -> bool:
                    candidate = build_pack_prompt(pages, chunk_signals_for(pages))
                    return _fits_output_budget(
                        _estimate_tokens(system_prefix + candidate),
                        base_output,
                        capacity,
                    )

                def split_pages(pages: list[int], depth: int = 0) -> list[list[int]]:
                    if prompt_fits(pages) or depth >= _PACK_SPLIT_MAX_DEPTH:
                        return [pages]
                    midpoint = max(1, len(pages) // 2)
                    left, right = pages[:midpoint], pages[midpoint:]
                    if not left or not right:
                        return [pages]
                    return split_pages(left, depth + 1) + split_pages(right, depth + 1)

                for chunk_index, chunk_pages in enumerate(split_pages(pack_pages)):
                    chunk_prompt = build_pack_prompt(chunk_pages, chunk_signals_for(chunk_pages))
                    batch = await call(
                        f"semantic:{pack_name}"
                        + (f":chunk{chunk_index + 1}" if len(pack_pages) != len(chunk_pages) else ""),
                        chunk_prompt,
                        ProposedFactBatch,
                        stage="semantic",
                    )
                    proposals.extend(batch.facts)

                def locate(fact: ProposedFact):
                    quote = _clean_quote(fact.quote or "")
                    page_blocks = (
                        document.pages_blocks.get(fact.page, [])
                        if fact.page is not None
                        else document.blocks
                    )
                    money_field = _money_field(fact.field)
                    money_amounts = _money_amounts_from_value(fact.value) if money_field else []
                    # A generic quote match may only bind money facts when the quote
                    # itself carries a money literal matching the proposed amount.
                    # Otherwise the number field could be accepted by irrelevant
                    # tables ("120 Stueck") and hallucinated amounts pass through.
                    money_quote_ok = False
                    if money_field and money_amounts:
                        for m in _MONEY_LITERAL_RE.finditer(quote):
                            if _money_amount(m.group(0)) is not None and any(
                                abs(round(_money_amount(m.group(0)), 2) - expected) < 0.001
                                for expected in money_amounts
                            ):
                                money_quote_ok = True
                                break
                    if quote and (not money_field or money_quote_ok):
                        matches: list[tuple[Block, str]] = []
                        for block in page_blocks:
                            found = _find_quote(block.text or "", quote)
                            if found is not None:
                                matches.append((block, found[0]))
                        if not matches and fact.page is not None:
                            for block in document.blocks:
                                found = _find_quote(block.text or "", quote)
                                if found is not None:
                                    matches.append((block, found[0]))
                        if len(matches) == 1:
                            return matches[0], False
                        if not matches and fact.page is not None:
                            source_page = next(
                                (page for page in canonical.pages
                                 if page.page_number == fact.page),
                                None,
                            )
                            if source_page is not None:
                                found = _find_quote(
                                    (source_page.text or "").strip(), quote
                                )
                                if found is not None:
                                    return (None, found[0]), False

                        # OCR-tolerant fallback: table cells separate label and amount
                        # with pipes/whitespace that the model quote may not reproduce
                        # verbatim, and OCR can add a single typo.  Keeps page scope,
                        # requires a unique match and flags review.
                        tolerant: list[tuple[Block, str]] = []
                        for block in page_blocks:
                            found = _find_quote_tolerant(block.text or "", quote)
                            if found is not None:
                                tolerant.append((block, found[0]))
                        if not tolerant and fact.page is not None:
                            for block in document.blocks:
                                found = _find_quote_tolerant(block.text or "", quote)
                                if found is not None:
                                    tolerant.append((block, found[0]))
                        if len(tolerant) == 1:
                            return tolerant[0], True
                        if not tolerant and fact.page is not None:
                            source_page = next(
                                (page for page in canonical.pages
                                 if page.page_number == fact.page),
                                None,
                            )
                            if source_page is not None:
                                found = _find_quote_tolerant(
                                    (source_page.text or "").strip(), quote
                                )
                                if found is not None:
                                    return (None, found[0]), True

                    # Staged label+amount money locator: money must never bind by the
                    # number alone.  Anchors the amount literal on the fact's page and
                    # requires its label to co-occur (OCR/pipe-tolerant); ambiguity or
                    # a wrong page leaves the fact unresolved.
                    if _money_field(fact.field):
                        staged = _locate_money_staged(
                            document,
                            page_blocks,
                            quote,
                            _money_amounts_from_value(fact.value),
                        )
                        if staged is not None:
                            block, literal = staged
                            return (block, literal), False

                    signal_matches = [
                        signal
                        for signal in source_signals
                        if (fact.page is None or signal.get("page") == fact.page)
                        and _signal_matches(fact.field, fact.value, signal)
                        and not (
                            signal.get("kind") == "money"
                            and _money_field(fact.field)
                        )
                    ]
                    if len(signal_matches) == 1:
                        signal = signal_matches[0]
                        block = document.index.get(signal.get("block_id"))
                        if block is not None:
                            found = _find_quote(block.text or "", signal.get("quote") or "")
                            if found is not None:
                                return (block, found[0]), False

                    if fact.page is not None and fact.page in visual_readings and quote and (not money_field or money_quote_ok):
                        for fragment in visual_readings[fact.page].visible_text:
                            found = _find_quote(fragment, quote)
                            if found is not None:
                                return (None, found[0]), True

                    # Missing page/quote should not kill an otherwise precise semantic
                    # fact, but facts the model itself did not mark as applicable must
                    # not be retroactively saved by a loose literal match (junk
                    # acceptance).  For applicable literal string values (supplier,
                    # title, payment terms, etc.) locate a unique exact/case-insensitive
                    # source occurrence.
                    if fact.applicability != "applicable":
                        return None
                    literals = _literal_strings(fact.value)
                    if not literals:
                        return None
                    # Page-scoped first: the same literal (e.g. a printer address
                    # header) can legally repeat on later pages; its unique evidence
                    # on the asserted page remains valid.
                    if fact.page is not None:
                        page_evidence = _literal_evidence(
                            literals, document.pages_blocks.get(fact.page, [])
                        )
                        if len(page_evidence) == 1:
                            return next(iter(page_evidence.values())), False
                    unique_literal = _literal_evidence(literals, document.blocks)
                    if len(unique_literal) == 1:
                        return next(iter(unique_literal.values())), False
                    return None

            contract = Contract()
            supported_count = 0
            normalizations: list[dict] = []

            for fact in proposals:
                original_value = fact.value
                fact.value = _normalize_fact_value(fact.field, fact.value)
                if fact.field in {"costs.scheduled_prices", "costs.variable_charges"} and fact.page is not None:
                    page_text = "\n".join(
                        (block.text or "")
                        for block in document.pages_blocks.get(fact.page, [])
                    )
                    if fact.field == "costs.scheduled_prices":
                        parsed = _staged_price_rows(page_text)
                    else:
                        parsed = _per_call_rows(page_text)
                    if parsed:
                        fact.value = [row for row, _ in parsed]
                        fact.applicability = "applicable"
                        fact.quote = parsed[0][1]
                if fact.value != original_value:
                    normalizations.append({
                        "field": fact.field,
                        "from": original_value,
                        "to": fact.value,
                    })
                if fact.field not in types:
                    rejected.append({"field": fact.field, "reason": "unknown_field"})
                    continue
                if fact.applicability in {"alternative", "superseded"}:
                    rejected.append(
                        {
                            "field": fact.field,
                            "reason": f"applicability:{fact.applicability}",
                        }
                    )
                    continue
                if fact.ambiguity:
                    rejected.append(
                        {
                            "field": fact.field,
                            "reason": "model_marked_ambiguous",
                            "detail": fact.ambiguity[:240],
                        }
                    )
                    continue

                if (visual_first_rows and fact.field.startswith("costs.")
                    and any(row.page == fact.page and row.status == "disputed"
                            for row in visual_first_rows)):
                    rejected.append({"field": fact.field, "page": fact.page,
                                     "reason": "visual_first_cost_dispute_manual_review"})
                    continue

                located = locate(fact)
                if located is None:
                    rejected.append(
                        {
                            "field": fact.field,
                            "reason": "evidence_not_located",
                            "page": fact.page,
                            "quote": fact.quote[:240],
                        }
                    )
                    continue

                (block, resolved_quote), visual_only = located
                page = fact.page if block is None else block.page

                if fact.field in _TEMPORAL_FIELDS and not _temporal_signal_supported(
                    fact, source_signals
                ):
                    rejected.append({
                        "field": fact.field, "page": page,
                        "reason": "temporal_value_not_corroborated_by_signal",
                        "quote": (fact.quote or "")[:240],
                    })
                    continue

                if not _financial_classification_verified(
                    fact, visual_first_rows, resolved_page=page,
                ):
                    # GATE 1: ein nicht periodenbelegter Betrag darf weder als
                    # annual_cost noch als eine andere wiederkehrende Kostenart in
                    # kalkulatorische Verantwortung uebergehen (Kalkulation,
                    # Forecast, Suche, Analytics). Nur manuelle Freigabe war.
                    rejected.append({
                        "field": fact.field, "page": page,
                        "reason": "financial_classification_unverified",
                        "quote": (fact.quote or "")[:240],
                    })
                    issues.append(
                        "Financial classification requires manual review: %s"
                        % fact.field
                    )
                    continue

                try:
                    value = strict_value(types[fact.field], fact.value)
                except (ValueError, TypeError) as exc:
                    rejected.append(
                        {
                            "field": fact.field,
                            "reason": "schema_validation_failed",
                            "detail": str(exc)[:240],
                        }
                    )
                    continue
                source = SourceEvidence(
                    document_id=canonical.document_id,
                    page=page,
                    source_type=(block.source_type if block is not None else "page"),
                    source_text=resolved_quote,
                    confidence=fact.confidence,
                    requires_review=bool(visual_only),
                )
                if block is not None:
                    box = _bbox(block)
                    if box is not None:
                        source.bounding_box = box
                if visual_only and not any(
                    i.startswith("Evidence requires manual review") for i in issues
                ):
                    # Fail-closed provenance: a fact whose only located evidence
                    # is an unverified image reading (or an OCR-tolerant literal
                    # match) must force the WHOLE analysis into review. The
                    # per-row flag alone is not enough - status, review reasons
                    # and requires_review aggregate from `issues`.
                    issues.append(
                        "Evidence requires manual review: %s" % fact.field
                    )

                if fact.field == "equipment":
                    # A contract can contain separately grounded equipment
                    # facts from different pages/annexes. Never discard devices
                    # already accepted from an earlier fact.
                    new_equipment = value or []
                    unattributed = 0
                    for item in new_equipment:
                        if equipment_identity_in_quote(item, resolved_quote):
                            item.evidence = source
                        else:
                            unattributed += 1
                    # Remove only exact repeated rows from overlapping facts.
                    # Names/models/serials alone are not safe deduplication keys:
                    # two physical units can share those values. Preserve any
                    # distinct source, scope or equipment attribute.
                    seen_equipment = {
                        json.dumps(item.model_dump(mode="json"), sort_keys=True)
                        for item in contract.equipment
                    }
                    for item in new_equipment:
                        fingerprint = json.dumps(
                            item.model_dump(mode="json"), sort_keys=True
                        )
                        if fingerprint not in seen_equipment:
                            contract.equipment.append(item)
                            seen_equipment.add(fingerprint)
                    if unattributed:
                        issues.append(
                            "Equipment source attribution incomplete: "
                            f"{unattributed} item(s) require manual evidence review"
                        )
                else:
                    group, field = fact.field.split(".", 1)
                    holder = getattr(contract, group)
                    # Mehrere Fakten fuer eine Zeilen-Liste (z. B. zwei
                    # variable_charges-Kosten pro Seite) duerfen sich nicht
                    # gegenseitig ueberschreiben; die Betraege werden aneinander-
                    # gehaengt statt still verloren zu gehen.
                    if (
                        fact.field
                        in {"costs.variable_charges", "costs.scheduled_prices"}
                        and isinstance(getattr(holder, field, None), list)
                    ):
                        value = [*getattr(holder, field), *value]
                    setattr(holder, field, value)
                    if getattr(holder, "evidence", None) is None:
                        holder.evidence = source

                evidence_rows.append(
                    {
                        "field": fact.field,
                        "source": source.model_dump(mode="json"),
                    }
                )
                accepted.append(
                    {
                        "field": fact.field,
                        "page": page,
                        "quote": resolved_quote,
                        "confidence": fact.confidence,
                    }
                )
                # Per-field evidence is kept so later derivations can still be
                # grounded in the fact's OWN source. The identity group's single
                # evidence slot may be re-pointed to a stronger citation (e.g. an
                # explicit supplier letterhead) and must not invalidate it.
                accepted_evidence_by_field.setdefault(fact.field, source)
                supported_count += 1

            _merge_service_scope_facts(getattr(contract, "services", None))

            primary_title_derivation = None
            primary_title = _primary_contract_title(canonical, document)
            if primary_title is not None:
                title_text, title_evidence = primary_title
                accepted_title_evidence = accepted_evidence_by_field.get(
                    "identity.contract_title"
                )
                if (
                    not accepted_title_evidence
                    or (accepted_title_evidence.page or 10**9) > (title_evidence.page or 10**9)
                ):
                    contract.identity.contract_title = title_text
                    accepted_evidence_by_field["identity.contract_title"] = title_evidence
                    evidence_rows = [
                        row for row in evidence_rows
                        if row.get("field") != "identity.contract_title"
                    ]
                    evidence_rows.append({
                        "field": "identity.contract_title",
                        "source": title_evidence.model_dump(mode="json"),
                    })
                    accepted = [
                        row for row in accepted
                        if row.get("field") != "identity.contract_title"
                    ]
                    accepted.append({
                        "field": "identity.contract_title",
                        "page": title_evidence.page,
                        "quote": title_evidence.source_text,
                        "confidence": None,
                    })
                    if accepted_title_evidence is None:
                        supported_count += 1
                    primary_title_derivation = {
                        "field": "identity.contract_title",
                        "derivation": "opening_page_contract_heading",
                        "page": title_evidence.page,
                    }

            scheduled_rows = [
                {
                    "period_index": row.period_index,
                    "amount": {
                        "amount": row.amount.amount if row.amount else None,
                        "currency": row.amount.currency if row.amount else None,
                    },
                }
                for row in contract.costs.scheduled_prices
                if row.period_index is not None and row.amount and row.amount.amount is not None
            ]
            # An inferred ongoing rate is not a newly source-verified contract
            # fact. Only derive it from a COMPLETE staged schedule whose duration
            # and currency can be proven; never inflate supported_count or forge
            # a quotation/evidence row for it.
            derived_facts: list[dict] = []
            if primary_title_derivation is not None:
                derived_facts.append(primary_title_derivation)
            cost_derived = _derive_costs_from_price_tables(contract, canonical, document)
            derived_facts.extend(cost_derived)
            start_condition = _derive_start_condition(contract, canonical)
            if start_condition is not None:
                condition_page, condition_clause = start_condition
                contract.dates.start_condition = condition_clause
                contract.dates.evidence = _build_page_evidence(
                    condition_page, condition_clause, document, canonical
                )
                derived_facts.append(
                    {
                        "field": "dates.start_condition",
                        "derivation": "literal_start_trigger_clause",
                        "page": condition_page,
                        "start_condition": condition_clause,
                    }
                )
            supplier_evidence = _bind_supplier_evidence(contract, canonical, document)
            if supplier_evidence is not None:
                contract.identity.evidence = supplier_evidence
                derived_facts.append(
                    {
                        "field": "identity.supplier",
                        "derivation": "explicit_supplier_letterhead_mention",
                        "page": supplier_evidence.page,
                    }
                )
            elif not (contract.identity.supplier or "").strip():
                # The evidence gate rejected the model's supplier fact (missing
                # page/quote). The party is still named verbatim in the document,
                # so it is read from the text rather than left empty.
                derived_supplier_evidence = _derive_supplier(contract, canonical, document)
                if derived_supplier_evidence is not None:
                    contract.identity.evidence = derived_supplier_evidence
                    derived_facts.append(
                        {
                            "field": "identity.supplier",
                            "derivation": "legal_form_party_mention",
                            "page": derived_supplier_evidence.page,
                            "supplier": contract.identity.supplier,
                        }
                    )
            if not contract.equipment:
                derived_equipment = _equipment_from_title_evidence(
                    contract,
                    accepted_evidence_by_field.get("identity.contract_title"),
                )
                if derived_equipment is not None:
                    contract.equipment.append(derived_equipment)
                    derived_facts.append(
                        {
                            "field": "equipment",
                            "derivation": "device_name_from_bound_contract_title",
                            "device_name": derived_equipment.device_name,
                        }
                    )
            duration = contract.dates.duration
            if contract.dates.duration is None:
                derived_duration = _duration_from_runtime_signal(
                    contract, source_signals, document, canonical
                )
                if derived_duration is not None:
                    contract.dates.duration = derived_duration[0]
                    contract.dates.evidence = derived_duration[1]
                    derived_facts.append(
                        {
                            "field": "dates.duration",
                            "derivation": "literal_runtime_duration_signal",
                            "duration": derived_duration[0].model_dump(mode="json"),
                        }
                    )
            unit = getattr(getattr(duration, "unit", None), "value", getattr(duration, "unit", None))
            expected_years = None
            normalized_unit = str(unit).lower() if unit is not None else ""
            if duration is not None and normalized_unit in {"year", "years", "month", "months"}:
                try:
                    number = float(duration.value)
                    if number.is_integer() and number > 0:
                        if normalized_unit in {"year", "years"}:
                            expected_years = int(number)
                        elif int(number) % 12 == 0:
                            expected_years = int(number) // 12
                except (TypeError, ValueError, OverflowError):
                    pass
            schedule_currencies = {
                str(row["amount"]["currency"]).upper()
                for row in scheduled_rows if row["amount"].get("currency")
            }
            complete_currency = (
                len(schedule_currencies) == 1
                and all(row["amount"].get("currency") for row in scheduled_rows)
            )
            steady_annual = (
                _steady_annual_amount(scheduled_rows, expected_years=expected_years)
                if expected_years is not None and complete_currency else None
            )
            if steady_annual is not None and contract.costs.annual_cost is None:
                contract.costs.annual_cost = Money(
                    amount=steady_annual,
                    currency=next(iter(schedule_currencies)),
                    period="annual",
                )
                derived_facts.append(
                    {
                        "field": "costs.annual_cost",
                        "derivation": "complete_staged_yearly_price_schedule",
                        "source_fields": ["costs.scheduled_prices", "dates.duration"],
                        "period_indexes": sorted(row["period_index"] for row in scheduled_rows),
                        "source_verified_as_independent_fact": False,
                    }
                )
            if contract.costs.total_contract_value is None:
                scheduled_total = _complete_scheduled_total(
                    scheduled_rows, expected_years=expected_years
                )
                if scheduled_total is not None and complete_currency:
                    total_currency = next(iter(schedule_currencies))
                    contract.costs.total_contract_value = Money(
                        amount=scheduled_total,
                        currency=total_currency,
                        period="contract_total",
                    )
                    derived_facts.append({
                        "field": "costs.total_contract_value",
                        "derivation": "sum_complete_staged_yearly_price_schedule",
                        "source_fields": ["costs.scheduled_prices", "dates.duration"],
                        "period_indexes": sorted(row["period_index"] for row in scheduled_rows),
                        "period_amounts": [
                            {"period_index": row["period_index"], **row["amount"]}
                            for row in sorted(scheduled_rows, key=lambda item: item["period_index"])
                        ],
                        "source_verified_as_independent_fact": False,
                    })
            if supported_count == 0:
                issues.append("No source-grounded contract facts were delivered")
            if rejected:
                issues.append(f"{len(rejected)} proposed facts were not accepted")

            contract.review.requires_manual_review = bool(issues)
            contract.review.review_reasons = [ReviewFlag.OTHER] if issues else []
            contract.review.risk_notes = "; ".join(issues) or None
            status = ExtractionStatus.PARTIAL if issues else ExtractionStatus.SUCCESS
            validation_status = (
                ValidationStatus.VALID if supported_count else ValidationStatus.UNKNOWN
            )
            contract.analysis.extraction_status = status
            contract.analysis.validation_status = validation_status
            contract.analysis.harness_version = "direct-v1"
            contract.analysis.analysis_version = "direct-contract-intelligence-v1"
            contract.analysis.model_name = model_id
            contract.analysis.analysis_timestamp = datetime.now(timezone.utc).isoformat()

            diagnostics = {
                "harness_version": "direct-v1",
                "analysis_id": analysis_id,
                "provider": provider_id,
                "model": model_id,
                "processing_stage": "complete",
                "source_sha256": canonical.source_sha256,
                "source_signals": source_signals,
                "visual_first": visual_first_data,
                "visual_first_evidence_statuses": [
                    {"page": row.page, "label": row.label, "status": row.status,
                     "reasons": row.reasons} for row in visual_first_rows
                ],
                "semantic_proposals": [fact.model_dump() for fact in proposals],
                "normalizations": normalizations,
                "accepted_facts": accepted,
                "derived_facts": derived_facts,
                "rejected_facts": rejected,
                "evidence_count": len(evidence_rows),
                "supported_count": supported_count,
                "delivery_complete": bool(supported_count),
                "visual_readings": {
                    page: reading.model_dump()
                    for page, reading in visual_readings.items()
                },
                "calls": calls,
                "call_count": len(calls),
                "failure_count": sum(1 for row in calls if row.get("failed")),
                "stage_call_counts": {
                    stage: sum(1 for row in calls if row.get("stage") == stage)
                    for stage in {"vision", "semantic"}
                },
                "issues": issues,
            }
            for row in calls:
                row["analysis_id"] = analysis_id
            contract.analysis.harness = {
                **diagnostics,
                "document_intelligence": canonical.provenance.model_dump(mode="json"),
                "evidence": evidence_rows,
            }

            error = None
            if not supported_count:
                error = (
                    "HarnessFailure purpose=delivery category=no_grounded_facts "
                    f"proposals={len(proposals)} rejected={len(rejected)} "
                    f"evidence_failures={sum(1 for row in rejected if row.get('reason') == 'evidence_not_located')}"
                )

            return ContractAnalysisResult(
                document_id=canonical.document_id or "",
                contract=contract if supported_count else None,
                status=status,
                validation_status=validation_status,
                requires_review=bool(issues) or not supported_count,
                model=model_id,
                prompt_version="direct-contract-intelligence-v1",
                ai_call_count=len(calls),
                groups_processed=len(PACKS),
                processing_duration=time.monotonic() - started,
                message=(
                    "Analyse abgeschlossen."
                    if not issues
                    else "Analyse benötigt manuelle Prüfung."
                ),
                error=error,
                diagnostics=diagnostics,
            )

        except Exception as exc:
            category = getattr(exc, "category", None) or ""
            status_code = getattr(exc, "status_code", None)
            failed_calls = [row for row in calls if row.get("failed")]
            last_failure = failed_calls[-1] if failed_calls else {}
            failure_category = (
                last_failure.get("error_category")
                or category
                or ("timeout" if type(exc).__name__ == "AITimeoutError" else "unknown")
            )
            processing_stage = last_failure.get("stage") or "setup"
            for row in calls:
                row["provider"] = provider_id or getattr(self.ai, "active_provider_id", lambda: None)()
                row["model"] = model_id or getattr(self.ai, "active_model_id", lambda: None)()
                row["analysis_id"] = analysis_id
            diagnostics = {
                "harness_version": "direct-v1",
                "analysis_id": analysis_id,
                "provider": provider_id,
                "model": model_id,
                "processing_stage": processing_stage,
                "safe_error_category": failure_category,
                "request_id": analysis_id,
                "source_sha256": canonical.source_sha256,
                "source_signals": source_signals,
                "calls": calls,
                "call_count": len(calls),
                "failure_count": sum(1 for row in calls if row.get("failed")),
                "issues": [failure_category],
            }
            return ContractAnalysisResult(
                document_id=canonical.document_id or "",
                contract=None,
                status=ExtractionStatus.FAILED,
                validation_status=ValidationStatus.UNKNOWN,
                requires_review=True,
                model=model_id,
                prompt_version="direct-contract-intelligence-v1",
                ai_call_count=len(calls),
                groups_processed=0,
                processing_duration=time.monotonic() - started,
                message="Analyse fehlgeschlagen.",
                error=(
                    f"HarnessFailure purpose={last_failure.get('purpose', 'setup')} "
                    f"category={failure_category}"
                    + (f" http_status={status_code}" if status_code else "")
                ),
                diagnostics=diagnostics,
            )


# Integration compatibility: production detects the class by the historical HarnessV3 name.
# This class contains only the new direct implementation inherited above.
class HarnessV3(DirectContractHarness):
    pass
