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
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.ai.harness.document import Block, DocumentModel
from app.ai.harness.pipeline import _find_quote, RETRIEVAL_TERMS, field_types, strict_value
from app.ai.harness.source_signals import collect_source_signals
from app.documents.intelligence.hybrid import route_summary, visual_candidate_pages
from app.ai.service import AIService
from app.ai.schema import normalize_constrained_schema
from app.core.config import Settings
from app.models.contract import Contract
from app.models.enums import ExtractionStatus, ReviewFlag, ValidationStatus
from app.models.evidence import BoundingBox, SourceEvidence
from app.models.values import Money


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


class VisualPageReading(BaseModel):
    page: int
    visible_text: list[str] = Field(default_factory=list)
    layout_relations: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


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
    return max(1, int(len(text.encode("utf-8")) / 3 * 1.15))


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
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", value or "")
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


def _normalize_date_payload(value: Any) -> Any:
    if isinstance(value, str):
        iso = _date_signal_iso(value)
        if iso:
            return {"date": iso, "condition": None, "requires_review": False}
        return value
    if isinstance(value, dict):
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
            r"(?P<value>\d+)\s*(?P<unit>Jahr(?:e|en)?|Monat(?:e|en)?|Woche(?:n)?|Tag(?:e|en)?|Stunde(?:n)?)",
            value,
            re.IGNORECASE,
        )
        if not match:
            return value
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
    if isinstance(value, dict):
        # Model sometimes emits {"years": 4} / {"months": N} etc.
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


def _normalize_equipment_item(item: Any) -> Optional[dict]:
    """Normalisiert ein einzelnes Equipment-Proposal deterministisch.

    Nimmt Strings (reines Geräte-/Systemmodell) wie Dicts an und gibt ein
    Equipment-taugliches Dict nur mit bekannten Feldern zurueck. Fehlende
    Seriennummern werden NICHT erfunden; sie bleiben einfach weg (None).
    """
    if isinstance(item, str):
        name = item.strip()
        return {"device_name": name} if name else None
    if not isinstance(item, dict):
        return None
    cleaned: dict[str, Any] = {}
    for raw_key, val in item.items():
        key = _EQUIPMENT_ALIASES.get(raw_key, raw_key)
        if key not in _EQUIPMENT_KEEP or val is None:
            continue
        if isinstance(val, str):
            stripped = val.strip()
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
                amount_obj = row["amount"]
                if not isinstance(amount_obj, dict):
                    amount_obj = {}
                if "currency" not in amount_obj and item.get("currency"):
                    amount_obj["currency"] = item["currency"]
                if "unit" not in row and item.get("unit"):
                    row["unit"] = item["unit"]
                row["amount"] = _normalize_money_payload(amount_obj)
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
                amount_obj = row["amount"]
                if not isinstance(amount_obj, dict):
                    amount_obj = {}
                if "currency" not in amount_obj and item.get("currency"):
                    amount_obj["currency"] = item["currency"]
                row["amount"] = _normalize_money_payload(amount_obj)
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


def _steady_annual_amount(rows: list[dict]) -> float | None:
    """Return the steady yearly amount when staged rows stay constant from a
    later year onward (e.g. 1.Jahr=0, 2.-4.Jahr=8000).  Deterministic, no model."""
    by_index: dict[int, dict] = {
        row["period_index"]: row
        for row in rows
        if isinstance(row.get("period_index"), int) and row.get("amount")
    }
    if not by_index:
        return None
    idxs = sorted(by_index)
    if len(idxs) < 2 or (idxs[0] == 1 and len(idxs) < 3):
        return None
    if idxs[0] == 1 and len(idxs) >= 3:
        amounts = {by_index[i]["amount"]["amount"] for i in idxs[1:]}
    else:
        amounts = {by_index[i]["amount"]["amount"] for i in idxs}
    values = [x for x in amounts if x != 0]
    if len(values) == 1 and len(amounts) <= 2:
        return next(iter(values))
    return None


class DirectContractHarness:
    """Small orchestration layer: semantic extraction once, deterministic proof once."""

    def __init__(self, settings: Settings, ai: AIService | None = None):
        self.settings = settings
        self.ai = ai or AIService(settings)

    async def analyze(self, canonical, image_loader=None, page_image_loader=None):
        from app.ai.contract_extractor import ContractAnalysisResult

        started = time.monotonic()
        document = DocumentModel.build(canonical)
        types = field_types()
        source_signals = collect_source_signals(document)
        calls: list[dict] = []
        rejected: list[dict] = []
        evidence_rows: list[dict] = []
        accepted: list[dict] = []
        visual_readings: dict[int, VisualPageReading] = {}
        issues: list[str] = []
        provider_id = model_id = None

        try:
            provider, descriptor = await self.ai.harness_runtime()
            provider_id = descriptor.provider_id
            model_id = descriptor.model_id
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

            async def call(purpose: str, prompt: str, schema_type, *, images=None, stage="semantic"):
                schema = normalize_constrained_schema(schema_type.model_json_schema())
                system = SYSTEM + "\nOutput JSON schema: " + json.dumps(
                    schema, separators=(",", ":")
                )
                prompt_tokens = _estimate_tokens(system + prompt)
                metric = {
                    "purpose": purpose,
                    "stage": stage,
                    "schema": schema_type.__name__,
                    "estimated_prompt_tokens": prompt_tokens,
                    "failed": False,
                }
                calls.append(metric)
                output_tokens = base_output
                for attempt in range(2):
                    begin = time.monotonic()
                    try:
                        raw = await provider.generate_request(
                            prompt,
                            system,
                            schema,
                            output_tokens,
                            capacity,
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
                        if metric["done_reason"] in {"length", "max_tokens"}:
                            raise RuntimeError("output_truncated")
                        parsed = schema_type.model_validate_json(raw)
                        metric["succeeded"] = True
                        return parsed
                    except Exception as exc:
                        if (
                            str(exc) == "output_truncated"
                            and attempt == 0
                        ):
                            retry_tokens = (
                                int(metric["actual_prompt_tokens"])
                                if metric.get("actual_prompt_tokens")
                                else prompt_tokens
                            )
                            next_output, decision = _retry_output_plan(
                                purpose,
                                retry_tokens,
                                capacity,
                                base_output,
                                1024 * len(images or []),
                            )
                            metric["retry_decision"] = decision
                            metric["retry_prompt_tokens"] = retry_tokens
                            if next_output is not None:
                                output_tokens = next_output
                                metric["retried_with_output_tokens"] = next_output
                                continue
                        metric["failed"] = True
                        metric["succeeded"] = False
                        metric["error_type"] = type(exc).__name__
                        metric["error_category"] = (
                            "truncated_output"
                            if str(exc) == "output_truncated"
                            else "provider_or_schema_error"
                        )
                        raise

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
            if candidate_pages and descriptor.capabilities.vision is True and page_image_loader is not None:
                max_visual = min(
                    len(candidate_pages),
                    int(getattr(self.settings, "harness_vision_max_calls", 4)),
                )
                for page_number in candidate_pages[:max_visual]:
                    image = page_image_loader(page_number)
                    try:
                        reading = await call(
                            f"vision:{page_number}",
                            "Read this contract page visually. Transcribe only clearly visible text exactly, "
                            "preserving dates, numbers, currency, punctuation and negation. "
                            "Also record only explicit visual/layout relationships needed to interpret tables, "
                            "rows, columns, labels, selected controls, service windows or signatures; do not infer "
                            "contractual meaning. Put uncertain material in unresolved. "
                            f"Return page={page_number}.",
                            VisualPageReading,
                            images=[image],
                            stage="vision",
                        )
                    except ValidationError:
                        # OCR text remains a usable source when an optional visual
                        # reading is malformed. Keep the failed call in diagnostics,
                        # require human review, and continue semantic extraction.
                        issues.append(
                            f"Visual reading for page {page_number} failed schema validation"
                        )
                        continue
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
                prompt = (
                    f"Extract the {pack_name} contract facts from the source below. "
                    "Use Qwen semantic understanding to decide what each literal value means. "
                    "The literal source signals are observations, not final facts. "
                    "Inspect every relevant signal and decide its contractual role. "
                    "For every accepted fact page and exact quote are mandatory; copy the quote verbatim, without ellipses. "
                    "Do not output fields outside this catalog. Omit facts that are not actually present."
                    + (" " + guidance if guidance else "")
                    + "\n\nFIELD CATALOG:\n"
                    + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
                    + "\n\nLITERAL SOURCE SIGNALS (pages "
                    + str(pack_pages)
                    + "):\n"
                    + json.dumps(pack_signals, ensure_ascii=False, separators=(",", ":"))
                    + "\n\nCONTRACT SOURCE (pages "
                    + str(pack_pages)
                    + "):\n"
                    + _pack_source(canonical, pack_pages, visual_readings)
                )
                batch = await call(
                    f"semantic:{pack_name}",
                    prompt,
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
                if quote:
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

                signal_matches = [
                    signal
                    for signal in source_signals
                    if (fact.page is None or signal.get("page") == fact.page)
                    and _signal_matches(fact.field, fact.value, signal)
                ]
                if len(signal_matches) == 1:
                    signal = signal_matches[0]
                    block = document.index.get(signal.get("block_id"))
                    if block is not None:
                        found = _find_quote(block.text or "", signal.get("quote") or "")
                        if found is not None:
                            return (block, found[0]), False

                if fact.page is not None and fact.page in visual_readings and quote:
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
                literal_matches: list[tuple[Block, str]] = []
                for literal in _literal_strings(fact.value):
                    if literal.upper() in {"EUR", "USD", "GBP"}:
                        continue
                    for block in document.blocks:
                        resolved = _find_quote(block.text or "", literal)
                        exact = resolved[0] if resolved is not None else _find_casefold(
                            block.text or "", literal
                        )
                        if exact is not None:
                            literal_matches.append((block, exact))
                unique_literal = {
                    (block.id, text): (block, text)
                    for block, text in literal_matches
                }
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

                (block, resolved_quote), visual_only = located
                page = fact.page if block is None else block.page
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

                if fact.field == "equipment":
                    contract.equipment = value or []
                    for item in contract.equipment:
                        if item.evidence is None:
                            item.evidence = source
                else:
                    group, field = fact.field.split(".", 1)
                    holder = getattr(contract, group)
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
                supported_count += 1

            _merge_service_scope_facts(getattr(contract, "services", None))

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
            steady_annual = _steady_annual_amount(scheduled_rows)
            if steady_annual is not None and contract.costs.annual_cost is None:
                contract.costs.annual_cost = Money(
                    amount=steady_annual,
                    currency=(
                        scheduled_rows[0]["amount"]["currency"]
                        if scheduled_rows and scheduled_rows[0]["amount"].get("currency")
                        else "EUR"
                    ),
                    period="annual",
                )
                accepted.append(
                    {
                        "field": "costs.annual_cost",
                        "page": None,
                        "quote": "abgeleitet aus gestaffelten Jahrespreisen",
                        "confidence": None,
                    }
                )
                if contract.costs.evidence is not None:
                    evidence_rows.append(
                        {
                            "field": "costs.annual_cost",
                            "source": contract.costs.evidence.model_dump(mode="json"),
                        }
                    )
                supported_count += 1

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
                "provider": provider_id,
                "model": model_id,
                "source_sha256": canonical.source_sha256,
                "source_signals": source_signals,
                "semantic_proposals": [fact.model_dump() for fact in proposals],
                "normalizations": normalizations,
                "accepted_facts": accepted,
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
            diagnostics = {
                "harness_version": "direct-v1",
                "provider": provider_id,
                "model": model_id,
                "source_sha256": canonical.source_sha256,
                "source_signals": source_signals,
                "calls": calls,
                "call_count": len(calls),
                "failure_count": sum(1 for row in calls if row.get("failed")),
                "issues": [type(exc).__name__],
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
                error=f"HarnessFailure purpose=direct category={type(exc).__name__}",
                diagnostics=diagnostics,
            )


# Integration compatibility: production detects the class by the historical HarnessV3 name.
# This class contains only the new direct implementation inherited above.
class HarnessV3(DirectContractHarness):
    pass
