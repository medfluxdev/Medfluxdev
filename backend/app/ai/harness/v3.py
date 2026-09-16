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

from pydantic import BaseModel, Field

from app.ai.harness.document import Block, DocumentModel
from app.ai.harness.pipeline import _find_quote, field_types, strict_value
from app.ai.harness.source_signals import collect_source_signals
from app.ai.service import AIService
from app.core.config import Settings
from app.models.contract import Contract
from app.models.enums import ExtractionStatus, ReviewFlag, ValidationStatus
from app.models.evidence import BoundingBox, SourceEvidence


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
    unresolved: list[str] = Field(default_factory=list)


PACKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("core", ("identity.", "dates.", "termination.")),
    ("commercial", ("costs.", "payment.")),
    ("operations", ("equipment", "services.", "sla.")),
)

SYSTEM = """You are the semantic contract reader inside MedFlux.
Read the supplied contract source and return only facts actually supported by it.
Do not invent values. Do not infer missing business facts. Distinguish binding
terms from alternatives, superseded text and optional offers.
For each fact:
- choose only a field from the supplied field catalog;
- return the typed value expected by that field;
- ALWAYS provide page and an exact source quote for every non-ambiguous fact;
- the quote must be copied verbatim from CONTRACT SOURCE, never paraphrased and never contain ellipses;
- for every literal date, duration and money signal, decide its contractual role instead of silently omitting it;
- use the exact typed shape shown by the field catalog whenever possible;
- never output MedFlux block ids.
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


def _page_source(canonical) -> str:
    rows: list[str] = []
    if canonical.pages:
        for page in canonical.pages:
            text = (page.text or "").strip()
            if text:
                rows.append(f"[PAGE {page.page_number}]\n{text}")
    else:
        for unit in canonical.logical_units:
            text = (unit.text or "").strip()
            if text:
                rows.append(f"[{unit.source_type.upper()} {unit.index}]\n{text}")
    return "\n\n".join(rows)


def _field_catalog(types: dict[str, Any], prefixes: tuple[str, ...]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for field, annotation in types.items():
        if any(field == prefix or field.startswith(prefix) for prefix in prefixes):
            selected[field] = (
                str(annotation)
                .replace("typing.", "")
                .replace("app.models.values.", "")
                .replace("app.models.contract.", "")
                .replace("app.models.enums.", "")
            )
    return selected


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


def _normalize_date_payload(value: Any) -> Any:
    if isinstance(value, str):
        iso = _date_signal_iso(value)
        if iso:
            return {"date": iso, "condition": None, "requires_review": False}
        return value
    if isinstance(value, dict):
        cleaned = {
            key: value.get(key)
            for key in ("date", "condition", "requires_review")
            if key in value
        }
        raw_date = cleaned.get("date")
        if isinstance(raw_date, str):
            cleaned["date"] = _date_signal_iso(raw_date) or raw_date
        cleaned.setdefault("requires_review", False)
        return cleaned
    return value


def _normalize_duration_payload(value: Any) -> Any:
    if isinstance(value, str):
        match = re.search(
            r"(?P<value>\\d+)\\s*(?P<unit>Jahr(?:e|en)?|Monat(?:e|en)?|Woche(?:n)?|Tag(?:e|en)?|Stunde(?:n)?)",
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
    if isinstance(value, dict):
        return {
            key: value.get(key)
            for key in ("amount", "currency", "period")
            if key in value
        }
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
        return _normalize_money_payload(value)
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
                row["amount"] = _normalize_money_payload(row["amount"])
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
                row["amount"] = _normalize_money_payload(row["amount"])
            normalized.append(row)
        return normalized
    if field in {
        "sla.response_time",
        "sla.resolution_time",
        "sla.service_hours",
        "sla.emergency_availability",
    } and isinstance(value, dict):
        return {
            key: value.get(key)
            for key in ("value", "unit", "original_text")
            if key in value
        }
    if isinstance(value, str):
        return value.strip()
    return value


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
        return bool(number and number.group(0) in payload)

    if field == "termination.automatic_renewal" and kind == "renewal_negation":
        return value is False

    if field.startswith("costs.") or field.startswith("payment."):
        if kind != "money":
            return False
        amount = _money_amount(raw)
        if amount is None:
            return False
        if isinstance(value, dict):
            direct = value.get("amount")
            if isinstance(direct, (int, float)) and abs(float(direct) - amount) < 0.001:
                return True
            return any(
                isinstance(item, dict)
                and isinstance(item.get("amount"), dict)
                and isinstance(item["amount"].get("amount"), (int, float))
                and abs(float(item["amount"]["amount"]) - amount) < 0.001
                for item in value.values()
                if isinstance(value, dict)
            )
        return str(int(amount)) in _normalize_digits(payload)

    return False


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
                schema = schema_type.model_json_schema()
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
                            next_output, decision = _retry_output_plan(
                                purpose,
                                prompt_tokens,
                                capacity,
                                base_output,
                                1024 * len(images or []),
                            )
                            metric["retry_decision"] = decision
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

            # Vision is a fallback perception channel, not a mandatory reasoning stage.
            sparse_pages = [
                page.page_number
                for page in canonical.pages
                if len((page.text or "").strip()) < 60
            ]
            if sparse_pages and descriptor.capabilities.vision is True and page_image_loader is not None:
                max_visual = min(
                    len(sparse_pages),
                    int(getattr(self.settings, "harness_vision_max_calls", 4)),
                )
                for page_number in sparse_pages[:max_visual]:
                    image = page_image_loader(page_number)
                    reading = await call(
                        f"vision:{page_number}",
                        "Transcribe only clearly visible contract text from this page. "
                        "Preserve dates, numbers, currency, punctuation and negation exactly. "
                        "Put uncertain material in unresolved. "
                        f"Return page={page_number}.",
                        VisualPageReading,
                        images=[image],
                        stage="vision",
                    )
                    visual_readings[page_number] = reading

            base_source = _page_source(canonical)
            if visual_readings:
                base_source += "\n\n[VISION TRANSCRIPTIONS]\n" + json.dumps(
                    {
                        page: reading.visible_text
                        for page, reading in visual_readings.items()
                    },
                    ensure_ascii=False,
                )

            if not base_source.strip():
                raise ValueError("No readable source text or vision transcription")

            proposals: list[ProposedFact] = []
            for pack_name, prefixes in PACKS:
                catalog = _field_catalog(types, prefixes)
                pack_signals = [
                    signal
                    for signal in source_signals
                    if signal.get("kind")
                    in {
                        "date",
                        "money",
                        "duration",
                        "labelled_contract_number",
                        "renewal_negation",
                    }
                ]
                prompt = (
                    f"Extract the {pack_name} contract facts from the source below. "
                    "Use Qwen semantic understanding to decide what each literal value means. "
                    "The literal source signals are observations, not final facts. "
                    "Inspect every relevant signal and decide its contractual role. "
                    "For every accepted fact page and exact quote are mandatory; copy the quote verbatim, without ellipses. "
                    "Do not output fields outside this catalog. Omit facts that are not actually present.\n\n"
                    "FIELD CATALOG:\n"
                    + json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
                    + "\n\nLITERAL SOURCE SIGNALS:\n"
                    + json.dumps(pack_signals, ensure_ascii=False, separators=(",", ":"))
                    + "\n\nCONTRACT SOURCE:\n"
                    + base_source
                )
                batch = await call(
                    f"semantic:{pack_name}",
                    prompt,
                    ProposedFactBatch,
                    stage="semantic",
                )
                proposals.extend(batch.facts)

            def locate(fact: ProposedFact):
                quote = (fact.quote or "").strip()
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

                # Missing page/quote should not kill an otherwise precise semantic
                # fact. For literal string values (supplier, title, payment terms,
                # etc.) locate a unique exact/case-insensitive source occurrence.
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

                if fact.page is not None and fact.page in visual_readings and quote:
                    for fragment in visual_readings[fact.page].visible_text:
                        found = _find_quote(fragment, quote)
                        if found is not None:
                            return (None, found[0]), True
                return None

            contract = Contract()
            supported_count = 0
            normalizations: list[dict] = []

            for fact in proposals:
                original_value = fact.value
                fact.value = _normalize_fact_value(fact.field, fact.value)
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
