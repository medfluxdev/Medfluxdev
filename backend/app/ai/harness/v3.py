"""Contract Intelligence Harness V3.

V3 evolves the existing ``app.ai.harness`` package: the same provider-neutral
verb, the same bounded ContextPlanner, the same grounded-evidence guarantees.
It adds explicit per-stage reasoning with Qwen as the semantic authority:

    Perception (deterministic evidence capture, never semantic decisions)
      -> Vision (selective, bounded regions)
      -> SectionUnderstanding (VISUAL COMPUTE only, provisional)
      -> GlobalContractUnderstanding (the ONLY contract-global authority)
      -> ContractMap (segment union + synthesis)
      -> Cross-Clause / Applicability (selections, alternatives, number roles,
         precedence, table-column applicability)
      -> Fact Resolution per family (applicability-labelled candidates)
      -> Evidence Binding + deterministic handoff (excludes alternative/
         superseded facts from the Contract model and downstream calculation)

Deterministic code never decides semantic applicability; it validates grounded
evidence, enforces schema/integrity, excludes Qwen-classified alternatives, and
performs arithmetic/date/currency/lifecycle work.

Architecture notes (per audit and approved decisions):
* ``harness_engine="v3"`` is explicit and configurable; ``v2`` (v2.1) remains
  the production default until real ABIOMED/Accutron benchmarks validate V3.
* No Guard-TOP-specific or provider-specific business rules exist here.
* Section understanding batches VISUAL COMPUTE (bounded page renders), never
  semantic truth; only the global stage establishes contract-global meaning.
* OCR/atomic geometry is irrelevant to this module: canonical visual evidence
  and Qwen vision proceed regardless of OCR success (perception is optional).
* Per-stage diagnostics record purpose, pages, provider, model, token estimates,
  latency, response hash and failure reason (bounded; never raw source text).
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

from app.ai.exceptions import AIProviderError
from app.ai.harness.context import (
    CallBudgetExhausted,
    ContextOverflow,
    ContextPlanner,
    assemble,
    estimate_tokens,
)
from app.ai.harness.document import Block, DocumentModel
from app.ai.harness.models import (
    ApplicabilityBatch,
    ApplicabilityDecision,
    CandidateBatch,
    ContractMap,
    FactCandidate,
    GlobalContractUnderstanding,
    GroundingBatch,
    NumberRole,
    Observation,
    OptionCluster,
    PrecedenceRule,
    SectionUnderstanding,
    SelectionRelation,
    VisionObservation,
)
from app.ai.harness.pipeline import (
    SYSTEM,
    TOPICS,
    RETRIEVAL_TERMS,
    _find_quote,
    _coalesce_batch,
    field_types,
    strict_value,
)
from app.ai.harness.v3_perception import perceive_option_clusters
from app.ai.service import AIService
from app.core.config import Settings
from app.models.contract import Contract
from app.models.enums import ExtractionStatus, ReviewFlag, ValidationStatus
from app.models.evidence import BoundingBox, SourceEvidence


_ALTERNATIVE_LABELS = {"alternative", "superseded"}

# Output-truncation retry is stage-local, measurable and bounded: only resolve,
# ground and recovery stages may retry once with a modest, prompt-measured
# output budget raise that still fits the runtime context window. It is never a
# global 8192-output hack and never runs on 65536-token experiments (that
# crashed Ollama on the target 8 GB hardware).
_OUTPUT_RETRY_PREFIXES = ("resolve:", "ground:", "recover:", "recovery:")
_OUTPUT_RETRY_MAX = 2800
_OUTPUT_RETRY_MIN_GAIN = 128
_OUTPUT_RETRY_RESERVE = 512

# Bounded worst-case token cap of compact_sections(..., budget=300) used as
# per-segment section-context allowance during family packing. It is the
# guarantee of the compactor (missing rows are never fabricated), not a magic
# reserve: the final assembled prompt is additionally validated before every
# provider call.
_SECTION_CONTEXT_BOUND = 400
_PACK_SAFETY_MARGIN = 64


class _OutputTruncated(Exception):
    """Internal marker: the provider returned before the structured output was
    complete (done_reason=length/max_tokens). The raw payload is never accepted."""


def measured_output_budget(purpose: str, prompt_tokens: int, capacity: int,
                           base_output: int) -> int | None:
    """Return a single modest output raise for truncation retries, or None.

    The raise is only granted when the measured prompt leaves margin inside the
    runtime window AND the increase meaningfully exceeds the base output budget.
    """
    if not purpose.startswith(_OUTPUT_RETRY_PREFIXES):
        return None
    margin = int(capacity) - int(prompt_tokens) - _OUTPUT_RETRY_RESERVE
    if margin <= 0:
        return None
    candidate = min(_OUTPUT_RETRY_MAX, margin)
    if candidate <= int(base_output) + _OUTPUT_RETRY_MIN_GAIN:
        return None
    return candidate


def _retry_fits_context(prompt_tokens, output_tokens, capacity, prompt_reserve,
                        image_reserve: int = 0) -> bool:
    """Explicit runtime-window proof for a truncation retry schedule:

    prompt tokens + raised output budget + prompt reserve + image reserve
    must fit inside the runtime capacity (e.g. the observed 8192 window).
    """
    return (
        int(prompt_tokens) + int(output_tokens) + int(prompt_reserve) + int(image_reserve)
        <= int(capacity)
    )


def _retry_output_plan(purpose, prompt_tokens, capacity, base_output,
                       image_reserve: int = 0) -> tuple[int | None, str]:
    """Decide whether a truncation retry is granted.

    Returns ``(output_tokens, decision)``. At most ONE stage-local retry; the
    raised output budget must demonstrably fit the runtime window together with
    the measured prompt and every reserve (prompt + image). A skipped retry
    always carries a clear diagnostic decision. Never mutates any settings here.
    """
    candidate = measured_output_budget(purpose, prompt_tokens, capacity, base_output)
    if candidate is None:
        return None, "output_retry_not_performed"
    if not _retry_fits_context(
        prompt_tokens, candidate, capacity, _OUTPUT_RETRY_RESERVE, image_reserve
    ):
        return None, "output_retry_skipped_context_overflow"
    return candidate, "output_budget_stage_retry"


def _drop_entry(stage: str, item_type: str, invalid_refs: list[str]) -> dict:
    """Diagnostic record for a quarantined semantic item. Never contains source
    content, only the stage, the item type and the offending reference ids."""
    return {
        "stage": stage,
        "item_type": item_type,
        "invalid_refs": sorted({str(ref) for ref in invalid_refs}),
        "action": "dropped",
        "requires_review": True,
    }


def _tally_failure_categories(calls: list[dict], budget_exhausted: bool) -> dict:
    counted: dict[str, int] = {}
    for call_row in calls:
        category = call_row.get("error_category") or "ok"
        counted[category] = counted.get(category, 0) + 1
    counted["call_budget_exhausted"] = counted.get("call_budget_exhausted", 0) + (
        1 if budget_exhausted else 0
    )
    return counted


def _refs_of(item) -> list[str]:
    if isinstance(item, Observation):
        return list(item.block_refs or []) + list(item.related_refs or [])
    if isinstance(item, (SelectionRelation, NumberRole, PrecedenceRule, ApplicabilityDecision)):
        return list(item.block_ids or [])
    return []


def sanitize_contract_map(document, mapping: ContractMap, *, stage: str = "map") -> tuple[ContractMap, list[dict]]:
    """Drop (quarantine) only those semantic map items whose source refs do not
    exist in ``document.index``; never remap, guess, fuzzy-match or repair.

    Every valid observation and semantic item is preserved verbatim. Dropped
    items are returned as diagnostics records (stage, item type, invalid refs)
    so review can be required without exposing raw contract content.
    """
    dropped: list[dict] = []

    def keep(items, item_type):
        valid = []
        for item in items:
            bad = sorted({ref for ref in _refs_of(item) if ref not in document.index})
            if bad:
                dropped.append(_drop_entry(stage, item_type, bad))
                continue
            valid.append(item)
        return valid

    clean = ContractMap(
        document_type=mapping.document_type,
        purpose=mapping.purpose,
        observations=keep(mapping.observations, "observation"),
        missing_material=list(mapping.missing_material or []),
        selections=keep(mapping.selections, "selection"),
        number_roles=keep(mapping.number_roles, "number_role"),
        precedence=keep(mapping.precedence, "precedence"),
        unresolved_references=list(mapping.unresolved_references or []),
    )
    return clean, dropped


def sanitize_applicability(decisions, document, *, stage: str) -> tuple[list, list[dict]]:
    valid = []
    dropped = []
    for decision in decisions:
        bad = sorted({ref for ref in (decision.block_ids or []) if ref not in document.index})
        if bad:
            dropped.append(_drop_entry(stage, "applicability_decision", bad))
            continue
        valid.append(decision)
    return valid, dropped


def _truncate_strings(value, limit: int):
    if isinstance(value, dict):
        return {key: _truncate_strings(val, limit) for key, val in value.items()}
    if isinstance(value, list):
        return [_truncate_strings(val, limit) for val in value]
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + "…"
    return value


def compact_items(items, budget: int, str_limit: int = 180) -> list:
    """Deterministic, order-preserving compaction of JSON-able items.

    Long string fields are truncated and items are kept while the cumulated
    estimated token size stays within `budget`. Sensible lossy clipping only;
    the first item is always kept so the semantic state never vanishes.
    """
    kept: list[dict] = []
    used = 0
    for item in items:
        data = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
        data = _truncate_strings(data, str_limit)
        est = estimate_tokens(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        if used + est > budget and kept:
            break
        kept.append(data)
        used += est
    return kept


def _section_row(section, str_limit: int) -> dict:
    return {
        "section_index": section.section_index,
        "pages": list(section.pages or []),
        "observations": compact_items(section.observations, budget=200, str_limit=str_limit),
        "option_clusters": compact_items(section.option_clusters, budget=200, str_limit=str_limit),
        "numbers": [n.model_dump(mode="json") for n in (section.numbers or [])],
        "unresolved": list(section.unresolved or []),
    }


def _fit_row_to_tokens(row: dict, cap: int) -> str:
    limit = 160  # matches the per-section str_limit used to build the row
    while True:
        trimmed = _truncate_strings(row, limit)
        payload = json.dumps(trimmed, ensure_ascii=False, separators=(",", ":"))
        est = estimate_tokens(payload)
        if est <= cap or limit <= 8:
            return payload
        limit = max(8, int(limit * 0.7))


def _fair_spread(n: int, k: int) -> list[int]:
    """Evenly spread ``k`` distinct section indices across ``n`` reading positions.

    Deterministic and order-equitable: when fewer sections than positions can be
    represented the chosen indices are spread across the whole range (never a
    fixed first-wins prefix). Both extreme positions are included whenever at
    least two slots are available.
    """
    if k <= 0 or n <= 0:
        return []
    if k >= n:
        return list(range(n))
    if k == 1:
        return [n // 2]
    chosen = sorted(
        {min(n - 1, max(0, round(i * (n - 1) / (k - 1)))) for i in range(k)}
    )
    for idx in range(n):
        if len(chosen) >= k:
            break
        if idx not in chosen:
            chosen.append(idx)
            chosen.sort()
    return chosen[:k]


def _fair_token_allocation(n: int, full_costs: list[int], budget: int) -> list[int]:
    """Token caps per section with the hard invariant ``sum(caps) <= budget``.

    Every represented section receives at least one unit; when the budget cannot
    cover all sections only an evenly spread subset is attempted (never a
    first-wins prefix). The caps are NOMINAL, not a promise: ``compact_sections``
    additionally hard-verifies the actual fitted payload against the budget.
    No semantic interpretation is added.
    """
    if n == 0 or budget <= 0:
        return [0] * n
    attempt = min(n, int(budget))
    positions = _fair_spread(n, attempt)
    share, remainder = divmod(int(budget), attempt)
    caps = [0] * n
    for position in positions:
        caps[position] = share
    index = 0
    while remainder > 0:
        changed = False
        for offset in range(attempt):
            current = positions[(index + offset) % attempt]
            if caps[current] < full_costs[current]:
                caps[current] += 1
                remainder -= 1
                changed = True
                if remainder == 0:
                    break
        if not changed:
            break
        index += 1
    return caps


def _section_priority(n: int) -> list[int]:
    """Deterministic representation priority: reading extremes first, then
    stepping inward. Used ONLY for the final hard-bound drop decision; a
    structural preference (first/last pages) with no semantic interpretation.
    """
    order: list[int] = []
    for step in range(n):
        front, back = step, n - 1 - step
        if front > back:
            break
        order.append(front)
        if front != back:
            order.append(back)
    return order


def compact_sections(sections, budget: int = 700, str_limit: int = 160,
                     log: list | None = None) -> str:
    """Compact ALL section readings to a HARD token bound.

    The returned JSON array satisfies ``estimate_tokens(payload) <= budget`` for
    every budget >= the empty-array floor. Per-section micro-summaries are
    deterministic string clipping only - never semantic abstraction - and pages/
    section identity are always preserved for every represented row. If the
    budget structurally cannot represent every section, representations are
    dropped (extremes longest) and the incompleteness is recorded in ``log``.
    """
    budget = int(budget)
    if budget < 1:
        if log is not None:
            log.append({
                "module": "compact_sections",
                "budget": budget,
                "sections": len(sections),
                "represented": 0,
                "incomplete": True,
                "bounded": False,
                "reason": "budget_below_minimum_token_floor",
            })
        return "[]"
    if not sections:
        return "[]"
    rows = [_section_row(section, str_limit) for section in sections]
    payloads = [
        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        for row in rows
    ]
    costs = [estimate_tokens(payload) for payload in payloads]
    if sum(costs) <= budget:
        return "[" + ",".join(payloads) + "]"
    caps = _fair_token_allocation(len(sections), costs, budget)
    fitted: dict[int, tuple[str, int]] = {}
    for index, row in enumerate(rows):
        if caps[index] <= 0:
            continue
        payload = _fit_row_to_tokens(row, caps[index])
        fitted[index] = (payload, estimate_tokens(payload))
    estimate = sum(cost for _, cost in fitted.values())
    drop_order = list(_section_priority(len(sections)))
    while estimate > budget and drop_order:
        dropped = drop_order.pop()
        if dropped in fitted:
            estimate -= fitted[dropped][1]
            del fitted[dropped]
    if log is not None:
        log.append({
            "module": "compact_sections",
            "budget": budget,
            "sections": len(sections),
            "represented": len(fitted),
            "represented_sections": sorted(fitted),
            "dropped_sections": sorted(set(range(len(sections))) - set(fitted)),
            "estimate_tokens": estimate if fitted else estimate_tokens("[]"),
            "incomplete": len(fitted) < len(sections),
            "bounded": (estimate if fitted else estimate_tokens("[]")) <= budget,
        })
    if not fitted:
        return "[]"
    return "[" + ",".join(fitted[i][0] for i in sorted(fitted)) + "]"


def _merge_maps_v3(maps: list[ContractMap]) -> ContractMap:
    """Lossless deterministic union of maps including the V3 semantic surface."""
    merged = ContractMap()
    observations: list[Observation] = []
    seen: set[tuple] = set()
    for mapping in maps:
        for obs in mapping.observations:
            key = (
                obs.topic,
                obs.summary,
                tuple(obs.block_refs),
                tuple(obs.related_refs),
                obs.ambiguity,
            )
            if key not in seen:
                seen.add(key)
                observations.append(obs)
        for item in mapping.missing_material:
            if item not in merged.missing_material:
                merged.missing_material.append(item)
        for item in mapping.unresolved_references:
            if item not in merged.unresolved_references:
                merged.unresolved_references.append(item)

    def merge_distinct(existing: list, additions: list, key_of):
        for item in additions:
            key = key_of(item)
            if key not in {key_of(entry) for entry in existing}:
                existing.append(item)

    for mapping in maps:
        merge_distinct(merged.selections, mapping.selections, lambda s: (s.cluster, s.option, s.applicability))
        merge_distinct(merged.number_roles, mapping.number_roles, lambda n: (n.value, n.role))
        merge_distinct(merged.precedence, mapping.precedence, lambda p: (p.document_type,))
    merged.document_type = next((m.document_type for m in maps if m.document_type), None)
    merged.purpose = next((m.purpose for m in maps if m.purpose), None)
    merged.observations = observations
    return merged


class HarnessV3:
    """Perception -> sections (visual compute) -> global -> map -> applicability
    -> grounded facts -> deterministic handoff."""

    def __init__(self, settings: Settings, ai: AIService | None = None):
        self.settings = settings
        self.ai = ai or AIService(settings)

    async def analyze(self, canonical, image_loader=None, page_image_loader=None):
        from app.ai.contract_extractor import ContractAnalysisResult

        started = time.monotonic()
        calls: list[dict] = []
        issues: list[str] = []
        maps: list[ContractMap] = []
        candidates: list[FactCandidate] = []
        evidence_rows: list[dict] = []
        dropped_refs: list[dict] = []
        budget_exhausted = False
        contract = Contract()
        planner = ContextPlanner(
            self.settings.harness_context_tokens,
            None,
            self.settings.harness_output_tokens,
        )
        provider_id = model_id = None
        document = DocumentModel.build(canonical)
        types = field_types()
        visual_observations: dict[str, VisionObservation] = {}
        section_understandings: list[SectionUnderstanding] = []
        applicability_entries: list[ApplicabilityDecision] = []
        selections: list[SelectionRelation] = []
        number_roles: list[NumberRole] = []
        precedence_rules: list[PrecedenceRule] = []
        global_understanding: GlobalContractUnderstanding | None = None
        clusters: list[OptionCluster] = []
        provider = None

        def failure_category(exc: Exception) -> str:
            done_reason = getattr(provider, "last_done_reason", None)
            if done_reason in {"length", "max_tokens"}:
                return "truncated_output"
            if isinstance(exc, CallBudgetExhausted):
                return "call_budget_exhausted"
            name = type(exc).__name__.lower()
            if "validation" in name or "json" in name:
                return "schema_error"
            if "timeout" in name:
                return "provider_timeout"
            if isinstance(exc, AIProviderError):
                return "provider_error"
            if isinstance(exc, ContextOverflow):
                return "context_overflow"
            return "runtime_error"

        async def call(purpose, text, schema_type, images=None, *, pages=None, stage=None):
            if len(calls) >= self.settings.harness_max_calls:
                raise CallBudgetExhausted(
                    f"Model call budget exhausted (max={self.settings.harness_max_calls})"
                )
            schema = schema_type.model_json_schema()
            instruction = SYSTEM + "\nOutput schema: " + json.dumps(schema, separators=(",", ":"))
            image_reserve = 1024 * len(images) if images else 0
            tokens = planner.check(instruction + text, purpose, extra_reserve=image_reserve)
            metric = {
                "purpose": purpose,
                "stage": stage,
                "schema": schema_type.__name__,
                "provider": provider_id,
                "model": model_id,
                "estimated_prompt_tokens": tokens,
                "recovery": purpose.startswith("recovery"),
                "failed": False,
            }
            if pages:
                metric["pages"] = [int(page) for page in pages]
            calls.append(metric)
            begin = time.monotonic()
            original_output = planner.output_tokens
            try:
                for _attempt in range(2):
                    try:
                        raw = await provider.generate_request(
                            text,
                            instruction,
                            schema,
                            planner.output_tokens,
                            planner.capacity,
                            images,
                        )
                        metric["done_reason"] = getattr(provider, "last_done_reason", None)
                        metric["response_chars"] = len(raw)
                        metric["response_sha256"] = (
                            getattr(provider, "last_response_sha256", None)
                            or hashlib.sha256(raw.encode("utf-8")).hexdigest()
                        )
                        if metric["done_reason"] in {"length", "max_tokens"}:
                            raise _OutputTruncated()
                        parsed = schema_type.model_validate_json(raw)
                        metric["succeeded"] = True
                        return parsed
                    except _OutputTruncated:
                        next_output, retry_decision = _retry_output_plan(
                            purpose, tokens, planner.capacity, original_output, image_reserve
                        )
                        if "retried_with_output_tokens" in metric or next_output is None:
                            metric["truncated"] = True
                            metric["failed"] = True
                            metric["succeeded"] = False
                            metric["error_type"] = "_OutputTruncated"
                            metric["error_category"] = "truncated_output"
                            metric["error_summary"] = "Model output exceeded budget"
                            if "retried_with_output_tokens" not in metric:
                                planner.decisions.append({
                                    "purpose": purpose,
                                    "stage": stage,
                                    "decision": retry_decision,
                                    "measured_prompt_tokens": tokens,
                                    "prompt_reserve": _OUTPUT_RETRY_RESERVE,
                                    "image_reserve": image_reserve,
                                    "runtime_capacity": planner.capacity,
                                    "candidate_output_tokens": next_output,
                                })
                            raise ValueError("Model output exceeded budget")
                        planner.output_tokens = next_output
                        metric["retried_with_output_tokens"] = next_output
                        planner.decisions.append({
                            "purpose": purpose,
                            "stage": stage,
                            "decision": retry_decision,
                            "from_output_tokens": original_output,
                            "to_output_tokens": next_output,
                            "measured_prompt_tokens": tokens,
                            "prompt_reserve": _OUTPUT_RETRY_RESERVE,
                            "image_reserve": image_reserve,
                            "runtime_capacity": planner.capacity,
                        })
                        continue
                    except Exception as exc:
                        metric["failed"] = True
                        metric["succeeded"] = False
                        metric["error_type"] = type(exc).__name__
                        metric["error_category"] = failure_category(exc)
                        metric["done_reason"] = getattr(provider, "last_done_reason", None)
                        metric["error_summary"] = str(exc).splitlines()[0][:180]
                        raise
                raise AssertionError("unreachable: output retry loop exhausted")
            finally:
                metric["latency_seconds"] = round(time.monotonic() - begin, 3)
                metric["usage"] = dict(getattr(provider, "last_usage", {}))
                planner.output_tokens = original_output

        def canonicalize_evidence(candidate: FactCandidate) -> bool:
            if not candidate.evidence_refs:
                return False
            for ref in candidate.evidence_refs:
                block = document.index.get(ref.block_id)
                if block is None:
                    return False
                resolved = _find_quote(block.text, ref.quote)
                if resolved is None:
                    return False
                ref.quote = resolved[0]
            return True

        async def verify(batch: CandidateBatch, context: str, purpose: str):
            """Evidence-first verification with semantic escalation only when needed.

            Exact canonical quote resolution is deterministic and authoritative for
            source binding. A second Qwen grounding call is reserved for candidates
            whose meaning cannot be safely accepted from exact evidence alone
            (ambiguity/conflict/dependency/unknown applicability or semantic-role
            sensitive fields). This avoids paying a model call for every already
            well-grounded fact while preserving Qwen authority where interpretation
            is actually required.
            """
            if not batch.candidates:
                return batch

            semantic_sensitive_prefixes = (
                "identity.contract_number",
                "dates.",
                "termination.",
                "costs.",
                "payment.",
                "sla.",
            )
            escalate_indices: list[int] = []
            for index, candidate in enumerate(batch.candidates):
                if candidate.status != "supported":
                    continue
                if not canonicalize_evidence(candidate):
                    candidate.status = "unsupported"
                    continue
                needs_semantic_verifier = bool(
                    candidate.ambiguity
                    or candidate.conflicts
                    or candidate.missing_dependencies
                    or candidate.applicability == "unknown"
                    or candidate.field.startswith(semantic_sensitive_prefixes)
                )
                if needs_semantic_verifier:
                    escalate_indices.append(index)

            if not escalate_indices:
                planner.decisions.append({
                    "purpose": purpose,
                    "decision": "deterministic_evidence_binding_sufficient",
                    "candidate_count": len(batch.candidates),
                })
                return batch

            semantic_candidates = [batch.candidates[index] for index in escalate_indices]
            decisions = await call(
                purpose,
                "Check whether the quoted sources ENTAIL every part of each candidate, including negation, "
                "units, recurrence, roles, scope, exceptions, and cross-clause precedence. Keyword overlap is "
                "insufficient. Reject unsupported normalized values. Return exactly one decision per candidate "
                "index in THIS SUBSET. Be concise.\n"
                + CandidateBatch(candidates=semantic_candidates).model_dump_json()
                + "\n"
                + context,
                GroundingBatch,
                stage="ground",
            )
            for subset_index, original_index in enumerate(escalate_indices):
                candidate = batch.candidates[original_index]
                verdicts = [
                    decision
                    for decision in decisions.decisions
                    if decision.candidate_index == subset_index
                ]
                if len(verdicts) != 1 or not verdicts[0].supported:
                    candidate.status = "unsupported"
            planner.decisions.append({
                "purpose": purpose,
                "decision": "semantic_grounding_escalation",
                "candidate_count": len(batch.candidates),
                "escalated_count": len(escalate_indices),
            })
            return batch

        def map_refs_for_family(family: str) -> tuple[set[str], list[dict]]:
            words = set(TOPICS[family].split()) | {family}
            refs: set[str] = set()
            selected: list[dict] = []
            for mapping in maps:
                for obs in mapping.observations:
                    topic_words = set(obs.topic.lower().replace("_", " ").split())
                    if words.intersection(topic_words):
                        selected.append(obs.model_dump())
                        refs.update(obs.block_refs)
                        refs.update(obs.related_refs)
            changed = True
            while changed:
                before = len(refs)
                for mapping in maps:
                    for obs in mapping.observations:
                        obs_refs = set(obs.block_refs)
                        related = set(obs.related_refs)
                        if refs.intersection(obs_refs | related):
                            refs.update(obs_refs | related)
                changed = len(refs) != before
            return refs, selected

        def ranked_blocks(family: str) -> tuple[list[Block], list[dict]]:
            refs, observations = map_refs_for_family(family)
            terms = RETRIEVAL_TERMS[family]
            scored: list[tuple[int, int, Block]] = []
            order = {block.id: index for index, block in enumerate(document.blocks)}
            for block in document.blocks:
                score = 0
                if block.id in refs:
                    score += 100
                haystack = block.searchable_text.lower()
                score += min(30, 3 * sum(1 for term in terms if term in haystack))
                if score and block.kind in {"table", "heading", "title"}:
                    score += 4
                scored.append((score, order[block.id], block))

            if any(score > 0 for score, _, _ in scored):
                ranked = [block for score, _, block in sorted(scored, key=lambda row: (-row[0], row[1])) if score > 0]
                relevant_ids = {block.id for block in ranked}
                for _, index, block in scored:
                    if block.id not in relevant_ids:
                        continue
                    for neighbor_index in (index - 1, index + 1):
                        if 0 <= neighbor_index < len(document.blocks):
                            neighbor = document.blocks[neighbor_index]
                            if neighbor.id not in relevant_ids:
                                ranked.append(neighbor)
                                relevant_ids.add(neighbor.id)
            else:
                ranked = list(document.blocks)
            planner.decisions.append(
                {
                    "purpose": family,
                    "retrieval_ranked_blocks": [block.id for block in ranked],
                    "semantic_ref_count": len(refs),
                }
            )
            return ranked, observations

        def vision_context(blocks: list[Block]) -> str:
            rows = []
            for block in blocks:
                observation = visual_observations.get(block.id)
                if observation is not None:
                    rows.append({"block_id": block.id, **observation.model_dump()})
            return json.dumps(rows, ensure_ascii=False, separators=(",", ":")) if rows else "[]"

        def sections_context() -> str:
            if not section_understandings:
                return "{}"
            rows = [section.model_dump() for section in section_understandings]
            return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))

        def sections_context_pages(page_numbers) -> str:
            if not section_understandings or not page_numbers:
                return "{}"
            wanted = set(page_numbers)
            related = [
                section for section in section_understandings
                if any(page in wanted for page in section.pages or [])
            ]
            return compact_sections(related, budget=300, log=planner.decisions)

        def sections_bound_tokens() -> int:
            """Bounded token allowance for the per-segment provisional section
            context, derived from the actual compactor guarantee instead of a
            static magic reserve."""
            if not section_understandings:
                return 0
            return estimate_tokens(compact_sections(section_understandings, budget=300, log=planner.decisions))

        def block_vision_cost(block: Block) -> int:
            """Deterministic per-block context cost: the token size of this
            block's visual observation row that will be assembled for its family
            segment. Used by the planner so packing reflects the actual prompt."""
            observation = visual_observations.get(block.id)
            if observation is None:
                return 0
            row = json.dumps(
                {"block_id": block.id, **observation.model_dump()},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            return estimate_tokens(row)

        def vision_summary() -> str:
            return (
                "\nVisual observations (auxiliary, not quotable textual evidence): "
                + json.dumps(
                    [{"block_id": key, **value.model_dump()} for key, value in visual_observations.items()],
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

        def visual_signature(block: Block):
            if block.page is None or block.element is None or block.element.region is None:
                return None
            page = canonical.page(block.page)
            if page is None or not page.width_pt or not page.height_pt:
                return None
            region = block.element.region
            return (
                block.kind,
                round(region.x0 / page.width_pt, 2),
                round(region.y0 / page.height_pt, 2),
                round(region.x1 / page.width_pt, 2),
                round(region.y1 / page.height_pt, 2),
                bool((block.text or "").strip()),
            )

        def visual_relevance_score(block: Block) -> int:
            parts = [block.searchable_text or ""]
            if block.page is not None:
                page = canonical.page(block.page)
                if page is not None and page.text:
                    parts.append(page.text)
            haystack = " ".join(parts).lower()
            score = 0
            score += 5 * sum(1 for term in RETRIEVAL_TERMS["costs"] if term in haystack)
            score += 3 * sum(1 for term in RETRIEVAL_TERMS["dates"] if term in haystack)
            score += 2 * sum(1 for term in RETRIEVAL_TERMS["identity"] if term in haystack)
            score += 2 * sum(1 for term in RETRIEVAL_TERMS["equipment"] if term in haystack)
            if block.kind in {"table", "image_page"}:
                score += 3
            return score

        def select_visual_blocks(blocks: list[Block]) -> tuple[list[Block], list[Block]]:
            signatures: dict[tuple, int] = {}
            for block in blocks:
                sig = visual_signature(block)
                if sig is not None:
                    signatures[sig] = signatures.get(sig, 0) + 1
            selected: list[Block] = []
            skipped: list[Block] = []
            high_value_kinds = {"checkbox", "signature", "stamp", "form", "image_page"}
            for block in blocks:
                sig = visual_signature(block)
                repeated_empty_decoration = (
                    block.kind in {"image", "figure"}
                    and not (block.text or "").strip()
                    and sig is not None
                    and signatures.get(sig, 0) > 1
                )
                if repeated_empty_decoration and block.kind not in high_value_kinds:
                    skipped.append(block)
                    continue
                selected.append(block)
            selected.sort(
                key=lambda block: (
                    -visual_relevance_score(block),
                    0 if block.kind in high_value_kinds else 1,
                    0 if (block.text or "").strip() else 1,
                    document.blocks.index(block),
                )
            )
            return selected, skipped

        def evidence_geometry(block: Block, quote: str):
            if block.page is None:
                return None, None
            page = canonical.page(block.page)
            if page is None:
                return None, None
            page_match = _find_quote(page.text, quote)
            if page_match is not None:
                _, start, end = page_match
                atoms = [
                    atom
                    for atom in page.atomic_units
                    if atom.aligned
                    and atom.canonical_offset is not None
                    and atom.canonical_length is not None
                    and atom.precision.value in {"word", "line", "table_cell"}
                    and atom.canonical_offset < end
                    and atom.canonical_offset + atom.canonical_length > start
                ]
                if atoms:
                    box = BoundingBox(
                        x0=min(atom.bbox.x0 for atom in atoms),
                        y0=min(atom.bbox.y0 for atom in atoms),
                        x1=max(atom.bbox.x1 for atom in atoms),
                        y1=max(atom.bbox.y1 for atom in atoms),
                    )
                    confidences = [atom.confidence for atom in atoms if atom.confidence is not None]
                    return box, (sum(confidences) / len(confidences) if confidences else None)
                words = [
                    word
                    for element in page.elements
                    for word in element.word_regions
                    if word.offset < end and word.offset + word.length > start
                ]
                if words:
                    box = BoundingBox(
                        x0=min(word.region.x0 for word in words),
                        y0=min(word.region.y0 for word in words),
                        x1=max(word.region.x1 for word in words),
                        y1=max(word.region.y1 for word in words),
                    )
                    return box, None
            for table in page.tables:
                for cell in table.cells:
                    if cell.region is None:
                        continue
                    if _find_quote(cell.text, quote) is not None:
                        return (
                            BoundingBox(
                                x0=cell.region.x0,
                                y0=cell.region.y0,
                                x1=cell.region.x1,
                                y1=cell.region.y1,
                            ),
                            cell.confidence,
                        )
            return None, None

        def role_for_number(value_text: str) -> str | None:
            key = str(value_text).strip()
            roles = {n.role for n in number_roles if str(n.value).strip() == key}
            return roles.pop() if roles else None

        try:
            provider, descriptor = await self.ai.harness_runtime()
            provider_id, model_id = descriptor.provider_id, descriptor.model_id
            planner.advertised = descriptor.context_length
            if descriptor.capabilities.text is not True or not provider.supports_structured_output:
                raise ValueError("Selected model/provider lacks verified text/structured-output capability")
            if not document.blocks:
                raise ValueError("Canonical document contains no analyzable source blocks")
            all_pages = sorted({block.page for block in document.blocks if block.page is not None})

            # ---- PERCEPTION (deterministic evidence capture; never decides) ----
            clusters = perceive_option_clusters(canonical, document)

            # ---- VISION (selective, bounded regions) ----
            visual_blocks = [block for block in document.blocks if block.needs_vision]
            visual_candidates, skipped_visuals = select_visual_blocks(visual_blocks)

            # Page-first vision policy: when a visual page is already scheduled for
            # full-page SectionUnderstanding, do not also spend region-level model
            # calls on every visual block from that page. Region vision remains a
            # targeted fallback for pages that are not covered by page-batch reading.
            batch_eligible_pages = set(document.visual_pages)
            if (
                descriptor.capabilities.vision is True
                and page_image_loader is not None
                and len(batch_eligible_pages) >= self.settings.harness_vision_min_pages_for_batch
            ):
                deferred_to_page_batch = [
                    block for block in visual_candidates if block.page in batch_eligible_pages
                ]
                visual_candidates = [
                    block for block in visual_candidates if block.page not in batch_eligible_pages
                ]
                for block in deferred_to_page_batch:
                    planner.decisions.append({
                        "block": block.id,
                        "vision": "deferred_to_page_batch",
                    })
            for block in skipped_visuals:
                planner.decisions.append({"block": block.id, "vision": "skipped_repeated_empty_decoration"})
            # Vision region calls are independently bounded (harness_vision_max_calls)
            # and do NOT grow linearly when the semantic call budget is raised.
            visual_budget = min(
                len(visual_candidates),
                max(0, self.settings.harness_vision_max_calls),
            )
            for block in visual_candidates[:visual_budget]:
                if budget_exhausted:
                    break
                if descriptor.capabilities.vision is True and image_loader is not None:
                    try:
                        image = image_loader(block)
                        observation = await call(
                            "vision:" + block.id,
                            "Describe only contract-relevant visual evidence in region " + block.id +
                            ". Distinguish visible text from inference, mark uncertainty, and do not invent text. "
                            "Be concise. Native/OCR context: " + block.text,
                            VisionObservation,
                            [image],
                            pages=[block.page] if block.page is not None else None,
                            stage="vision",
                        )
                        visual_observations[block.id] = observation
                    except CallBudgetExhausted:
                        budget_exhausted = True
                        break
                    except (ValueError, RuntimeError, AIProviderError, ContextOverflow) as exc:
                        issues.append("Visuelle Quelle nicht auflösbar: " + block.id)
                        planner.decisions.append({"block": block.id, "vision": "failed", "error_type": type(exc).__name__})
                else:
                    issues.append("Visuelle Quelle ohne verfügbare Vision: " + block.id)
            for block in visual_candidates[visual_budget:]:
                planner.decisions.append({"block": block.id, "vision": "deferred_by_visual_call_budget"})

            # ---- SECTION understanding (VISUAL COMPUTE only, provisional) ----
            visual_pages = document.visual_pages or [b.page for b in document.blocks if b.needs_vision]
            needs_batches = (
                all_pages
                and not budget_exhausted
                and len(visual_pages) >= self.settings.harness_vision_min_pages_for_batch
                and descriptor.capabilities.vision is True
                and page_image_loader is not None
                and len(calls) + max(1, len(all_pages) // self.settings.harness_vision_pages_per_batch)
                < self.settings.harness_max_calls - 6
            )
            if needs_batches:
                batch_size = max(1, self.settings.harness_vision_pages_per_batch)
                page_batches = [all_pages[i:i + batch_size] for i in range(0, len(all_pages), batch_size)]
                section_ordinal = [0]

                async def probe_section_batch(batch, index) -> bool:
                    texts = []
                    for page_number in batch:
                        page = canonical.page(page_number)
                        if page is not None and (page.text or "").strip():
                            texts.append(f"[Seite {page_number}]\n{page.text[:1800]}")
                    block_ids = [block.id for block in document.blocks if block.page in batch]
                    try:
                        images = [page_image_loader(page_number) for page_number in batch]
                        section = await call(
                            "section:" + str(section_ordinal[0]),
                            "Read ONLY this page batch. Produce a PROVISIONAL SectionUnderstanding: "
                            "observations as factual reading (do NOT assert contract-global meaning, selections, "
                            "applicability or precedence here), visible option/price clusters, candidate number "
                            "strings listed factually without roles, and unresolved items.\n"
                            "Page texts (auxiliary):\n" + "\n".join(texts)
                            + "\nBlock ids in this batch:\n" + json.dumps(block_ids, separators=(",", ":")),
                            SectionUnderstanding,
                            images,
                            pages=batch,
                            stage="sections",
                        )
                    except ContextOverflow:
                        return False
                    except ValueError as exc:
                        if getattr(provider, "last_done_reason", None) in {"length", "max_tokens"}:
                            planner.decisions.append({
                                "purpose": "section:" + str(index),
                                "decision": "section_batch_shrink_output_truncated",
                                "error_type": "truncated_output",
                            })
                            return False
                        issues.append(
                            f"Section {index}: {type(exc).__name__}; manuelle Prüfung erforderlich"
                        )
                        planner.decisions.append({
                            "purpose": "section:" + str(index),
                            "decision": "section_failed_continue",
                            "error_type": type(exc).__name__,
                        })
                        return True
                    except (RuntimeError, AIProviderError) as exc:
                        issues.append(
                            f"Section {index}: {type(exc).__name__}; manuelle Prüfung erforderlich"
                        )
                        planner.decisions.append({
                            "purpose": "section:" + str(index),
                            "decision": "section_failed_continue",
                            "error_type": type(exc).__name__,
                        })
                        return True
                    section_ordinal[0] += 1
                    section_understandings.append(
                        SectionUnderstanding(
                            section_index=section_ordinal[0] - 1,
                            pages=batch,
                            observations=section.observations,
                            option_clusters=section.option_clusters,
                            numbers=section.numbers,
                            unresolved=section.unresolved,
                            block_ids=block_ids,
                        )
                    )
                    return True

                for index, batch in enumerate(page_batches):
                    if budget_exhausted:
                        break
                    pending = [batch]
                    while pending:
                        if budget_exhausted:
                            break
                        current = pending.pop(0)
                        try:
                            ok = await probe_section_batch(current, index)
                        except CallBudgetExhausted:
                            budget_exhausted = True
                            planner.decisions.append({
                                "purpose": "section:" + str(index),
                                "decision": "call_budget_exhausted",
                            })
                            break
                        if ok:
                            continue
                        planner.decisions.append({
                            "purpose": "section:" + str(index),
                            "decision": "section_batch_shrink",
                            "pages": current,
                        })
                        if len(current) <= 1:
                            issues.append(
                                f"Section {index}: ContextOverflow; manuelle Prüfung erforderlich"
                            )
                            planner.decisions.append({
                                "purpose": "section:" + str(index),
                                "decision": "section_failed_continue",
                                "error_type": "ContextOverflow",
                            })
                            continue
                        mid = max(1, len(current) // 2)
                        pending[:0] = [current[:mid], current[mid:]]
            elif len(visual_pages) >= self.settings.harness_vision_min_pages_for_batch:
                if not all_pages or page_image_loader is None:
                    issues.append("Bildbasierte Seiten ohne verfügbares Page-Rendering; manuelle Prüfung erforderlich")
                elif not descriptor.capabilities.vision:
                    issues.append("Bildbasierte Seiten ohne verfügbare Vision; manuelle Prüfung erforderlich")

            # ---- GLOBAL understanding (the ONLY contract-global authority) ----
            section_summary = (
                compact_sections(section_understandings, budget=900, log=planner.decisions)
                if section_understandings
                else ""
            )
            gcu_instruction = (
                "Establish the contract-global understanding of the WHOLE document: document type, purpose, "
                "party roles, authority/precedence order of documents/attachments/emails, what is selected vs "
                "unselected (plan/option selections with reason), and key clauses. You are the ONLY stage that "
                "may assert contract-global meaning. Abstain where the material is insufficient. Be concise.\n"
            )
            if not budget_exhausted:
                if section_summary:
                    gcu_material = section_summary
                else:
                    full = assemble(document.blocks)
                    if planner.fits(SYSTEM + gcu_instruction + json.dumps(GlobalContractUnderstanding.model_json_schema()) + full):
                        gcu_material = full
                    else:
                        ranked_all = planner.pack_ranked(
                            document.blocks,
                            SYSTEM + gcu_instruction + json.dumps(GlobalContractUnderstanding.model_json_schema()),
                            purpose="global_context",
                        )
                        gcu_material = assemble(ranked_all)
                        issues.append("Globales Verständnis nutzt begrenzten Kontext; Vollständigkeit manuell prüfen")
                try:
                    global_understanding = await call(
                        "global_understanding",
                        gcu_instruction + vision_summary() + gcu_material,
                        GlobalContractUnderstanding,
                        pages=all_pages or None,
                        stage="global",
                    )
                except CallBudgetExhausted:
                    budget_exhausted = True
                    planner.decisions.append({
                        "purpose": "global_understanding",
                        "decision": "call_budget_exhausted",
                    })
                except (ContextOverflow, ValueError, RuntimeError, AIProviderError) as exc:
                    issues.append("Globales Verständnis: " + type(exc).__name__ + "; manuelle Prüfung erforderlich")
                    planner.decisions.append({
                        "purpose": "global_understanding",
                        "decision": "failed_continue",
                        "error_type": type(exc).__name__,
                    })

            # ---- CONTRACT MAP (segment union + synthesis) ----
            understanding_instruction = (
                "Build a ContractMap before database-field extraction. Map EVERY material clause and its role: "
                "parties/roles, contract identity and purpose, definitions, dates/term/renewal/termination, "
                "financial terms and price tables including free periods and additional one-time calls, payment, "
                "services/obligations/exclusions, SLA, equipment/coverage, annexes, amendments/precedence, "
                "cross-clause dependencies, contradictions, unresolved references, and missing material. "
                "Also express: which plan/option is selected vs unselected (selections, with applicable/alternative/"
                "superseded labelling), observed number strings and their roles (contract_number vs order_number/"
                "reference/customer_number), and document/attachment authority order (precedence). "
                "Use only source block IDs that are supplied. related_refs must connect definitions, exceptions, "
                "annexes, amendments and competing clauses. Topic names should use identity, equipment, dates, "
                "termination, costs, payment, services or sla when applicable.\n"
                "Keep each observation summary concise; one observation per materially distinct clause.\n"
            )
            map_overhead = SYSTEM + understanding_instruction + vision_summary() + json.dumps(ContractMap.model_json_schema())
            if section_summary:
                try:
                    planner.check(map_overhead + section_summary, "global_map")
                    mapping = await call(
                        "global_map",
                        understanding_instruction + vision_summary() + section_summary,
                        ContractMap,
                        pages=all_pages or None,
                        stage="global",
                    )
                    clean, dropped = sanitize_contract_map(document, mapping, stage="global_map")
                    dropped_refs.extend(dropped)
                    if dropped:
                        issues.append("ContractMap: Einträge mit ungültigen Quellverweisen verworfen; manuelle Prüfung erforderlich")
                        planner.decisions.append({
                            "purpose": "global_map",
                            "decision": "invalid_refs_quarantined",
                            "dropped": len(dropped),
                        })
                    maps.append(clean)
                except CallBudgetExhausted:
                    budget_exhausted = True
                    planner.decisions.append({
                        "purpose": "global_map",
                        "decision": "call_budget_exhausted",
                    })
                except (ContextOverflow, ValueError, RuntimeError, AIProviderError) as exc:
                    issues.append(f"ContractMap: {type(exc).__name__}; manuelle Prüfung erforderlich")
                    planner.decisions.append({
                        "purpose": "global_map",
                        "decision": "map_failed_continue",
                        "error_type": type(exc).__name__,
                    })
            else:
                try:
                    base_segments = planner.segments(document.blocks, map_overhead, purpose="global_understanding")
                except ContextOverflow as exc:
                    issues.append("ContractMap segmentation: ContextOverflow; manuelle Prüfung erforderlich")
                    planner.decisions.append({
                        "purpose": "global_understanding",
                        "decision": "segmentation_failed_continue_with_lexical_recall",
                        "error_type": type(exc).__name__,
                    })
                    base_segments = []
                segments: list[list[Block]] = []
                max_map_blocks = 28
                for segment in base_segments:
                    for start_index in range(0, len(segment), max_map_blocks):
                        segments.append(segment[start_index:start_index + max_map_blocks])
                if len(segments) != len(base_segments):
                    planner.decisions.append({
                        "purpose": "global_understanding",
                        "decision": "output_aware_map_refinement",
                        "segment_sizes": [len(segment) for segment in segments],
                    })
                for index, segment in enumerate(segments):
                    if budget_exhausted:
                        break
                    try:
                        mapping = await call(
                            "understanding:" + str(index),
                            understanding_instruction + vision_summary() + assemble(segment),
                            ContractMap,
                            pages=all_pages or None,
                            stage="global",
                        )
                        clean, dropped = sanitize_contract_map(document, mapping, stage="understanding:" + str(index))
                        dropped_refs.extend(dropped)
                        if dropped:
                            issues.append(
                                f"ContractMap segment {index}: Einträge mit ungültigen Quellverweisen verworfen; "
                                "manuelle Prüfung erforderlich"
                            )
                            planner.decisions.append({
                                "purpose": "understanding:" + str(index),
                                "decision": "invalid_refs_quarantined",
                                "dropped": len(dropped),
                            })
                        maps.append(clean)
                    except CallBudgetExhausted:
                        budget_exhausted = True
                        planner.decisions.append({
                            "purpose": "understanding:" + str(index),
                            "decision": "call_budget_exhausted",
                        })
                    except (ContextOverflow, ValueError, RuntimeError, AIProviderError) as exc:
                        issues.append(f"ContractMap segment {index}: {type(exc).__name__}; manuelle Prüfung erforderlich")
                        planner.decisions.append({
                            "purpose": "understanding:" + str(index),
                            "decision": "segment_failed_continue",
                            "error_type": type(exc).__name__,
                        })
                if len(maps) > 1 and not budget_exhausted:
                    union_map = _merge_maps_v3(maps)
                    maps.append(union_map)
                    synthesis = (
                        "Reconcile the section maps into one global ContractMap. Preserve every material fact, "
                        "conflict, dependency, selection and source reference; do not resolve ambiguity without "
                        "authority. Be concise.\n" + union_map.model_dump_json()
                    )
                    try:
                        synthesized = await call("global_map", synthesis, ContractMap, pages=all_pages or None, stage="global")
                        clean, dropped = sanitize_contract_map(document, synthesized, stage="global_map")
                        dropped_refs.extend(dropped)
                        if dropped:
                            issues.append("Synthesized ContractMap: Einträge mit ungültigen Quellverweisen verworfen; "
                                          "manuelle Prüfung erforderlich")
                        maps.append(clean)
                    except CallBudgetExhausted:
                        budget_exhausted = True
                        planner.decisions.append({
                            "purpose": "global_map",
                            "decision": "call_budget_exhausted",
                        })
                    except (ContextOverflow, ValueError, RuntimeError, AIProviderError) as exc:
                        planner.decisions.append({
                            "purpose": "global_map",
                            "decision": "deterministic_global_map_retained",
                            "error_type": type(exc).__name__,
                        })

            final_map = maps[-1] if maps else ContractMap()
            selections = list(final_map.selections)
            number_roles = list(final_map.number_roles)
            precedence_rules = list(final_map.precedence)
            for reference in final_map.unresolved_references:
                issues.append("Unaufgelöste Referenz: " + reference)

            # ---- CROSS-CLAUSE / APPLICABILITY (Qwen decides; deterministic applies) ----
            applicability_observations = []
            for family in ("costs", "identity", "termination"):
                _, observations = map_refs_for_family(family)
                applicability_observations.extend(observations)
            applicability_map = (
                json.dumps(
                    {
                        "observations": compact_items(applicability_observations, budget=900),
                        "selections": [s.model_dump() for s in selections],
                        "number_roles": [n.model_dump() for n in number_roles],
                        "precedence": [p.model_dump() for p in precedence_rules],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                if maps
                else "{}"
            )
            applicability_instruction = (
                "Decide the cross-clause applicability semantics with source grounding:\n"
                "- which plan/option is SELECTED and therefore APPLICABLE vs which are ALTERNATIVES or "
                "SUPERSEDED (e.g. a marked/selected protection plan vs unselected price options);\n"
                "- which amount is the applicable fixed/plan price when multiple amounts are visible; "
                "do NOT treat alternatives as part of the applicable total;\n"
                "- table-column applicability: which retrieved table column binds the facts used;\n"
                "- for each observed number string: is it the CONTRACT_NUMBER, ORDER_NUMBER, a REFERENCE, a "
                "CUSTOMER_NUMBER or OTHER?\n"
                "- document/attachment/email authority and precedence (AUTHORITATIVE vs SECONDARY).\n"
                "Only use supplied source block IDs. A selection must be evidenced by a clause, a marked control "
                "or an explicit statement; never infer a selection from price alone. Ground every decision.\n"
            )
            applicability_families = ["costs", "identity", "termination"]
            applicability_source_ids = set()
            for family in applicability_families:
                ranked, _ = ranked_blocks(family)
                applicability_source_ids.update(block.id for block in ranked)
            applicability_blocks = [
                block for block in document.blocks
                if block.id in applicability_source_ids
            ] or list(document.blocks)
            if not budget_exhausted:
                clusters_json = json.dumps(
                    compact_items(clusters, budget=600), ensure_ascii=False, separators=(",", ":")
                )
                vision_json = vision_summary()
                applicability_overhead = (
                    SYSTEM
                    + applicability_instruction
                    + json.dumps(ApplicabilityBatch.model_json_schema())
                    + applicability_map
                    + clusters_json
                    + vision_json
                )
                try:
                    applicability_pack = planner.pack_ranked(
                        applicability_blocks,
                        applicability_overhead,
                        purpose="applicability_context",
                        extra_reserve=_PACK_SAFETY_MARGIN,
                        per_block_cost=block_vision_cost,
                    )
                    applicability_input = (
                        applicability_instruction
                        + "\nContractMap: " + applicability_map
                        + "\nOption clusters (perception evidence): " + clusters_json
                        + vision_json
                        + "\nSources:\n" + assemble(sorted(applicability_pack, key=lambda b: document.blocks.index(b)))
                    )
                    batch = await call(
                        "applicability",
                        applicability_input,
                        ApplicabilityBatch,
                        pages=all_pages or None,
                        stage="applicability",
                    )
                    valid_decisions, dropped = sanitize_applicability(
                        batch.decisions, document, stage="applicability"
                    )
                    dropped_refs.extend(dropped)
                    if dropped:
                        issues.append(
                            "Applicability: Entscheidungen mit ungültigen Quellverweisen verworfen; "
                            "manuelle Prüfung erforderlich"
                        )
                        planner.decisions.append({
                            "purpose": "applicability",
                            "decision": "invalid_refs_quarantined",
                            "dropped": len(dropped),
                        })
                    applicability_entries.extend(valid_decisions)
                    selections.extend(
                        SelectionRelation(
                            cluster=decision.scope,
                            option=decision.target,
                            selected=(decision.decision == "selected"),
                            applicability={
                                "selected": "applicable",
                                "applicable": "applicable",
                                "alternative": "alternative",
                                "superseded": "superseded",
                                "not_selected": "alternative",
                                "secondary": "alternative",
                            }.get(decision.decision, "unknown"),
                            block_ids=list(decision.block_ids),
                            reason=decision.reason,
                        )
                        for decision in valid_decisions
                        if decision.scope in {"option", "price", "table_column"}
                        and decision.decision in {"selected", "not_selected", "applicable", "alternative", "superseded", "secondary"}
                    )
                    for decision in valid_decisions:
                        if decision.scope != "number" or decision.decision not in {
                            "contract_number", "order_number", "reference", "customer_number", "other",
                        }:
                            continue
                        if any(n.value == decision.target for n in number_roles):
                            continue
                        number_roles.append(
                            NumberRole(
                                value=decision.target,
                                role=decision.decision,
                                block_ids=list(decision.block_ids),
                                reason=decision.reason,
                            )
                        )
                    for decision in valid_decisions:
                        if decision.scope != "document" or decision.decision not in {"authoritative", "secondary"}:
                            continue
                        if any(p.document_type == decision.target for p in precedence_rules):
                            continue
                        precedence_rules.append(
                            PrecedenceRule(
                                document_type=decision.target,
                                rank=1 if decision.decision == "authoritative" else 2,
                                block_ids=list(decision.block_ids),
                                reason=decision.reason,
                            )
                        )
                except CallBudgetExhausted:
                    budget_exhausted = True
                    planner.decisions.append({
                        "purpose": "applicability",
                        "decision": "call_budget_exhausted",
                    })
                except (ContextOverflow, ValueError, RuntimeError, AIProviderError) as exc:
                    issues.append("Applicability: " + type(exc).__name__ + "; manuelle Prüfung erforderlich")
                    planner.decisions.append({
                        "purpose": "applicability",
                        "decision": "failed_continue_with_map",
                        "error_type": type(exc).__name__,
                    })

            # ---- FACT RESOLUTION per family ----
            topic_names = list(TOPICS)
            for family_index, family in enumerate(topic_names):
                if budget_exhausted:
                    planner.decisions.append({
                        "purpose": family,
                        "decision": "family_skipped_call_budget_exhausted",
                    })
                    issues.append("Modell-Call-Budget erschöpft; Analyse abgebrochen – manuelle Prüfung erforderlich")
                    break
                family_types = {key: val for key, val in types.items() if key == family or key.startswith(family + ".")}
                expected = set(family_types)
                ranked, observations = ranked_blocks(family)
                catalog = {
                    key: str(value)
                    .replace("typing.", "")
                    .replace("app.models.values.", "")
                    .replace("app.models.contract.", "")
                    .replace("app.models.enums.", "")
                    for key, value in family_types.items()
                }
                ranked_ids = {block.id for block in ranked}
                family_words = set(TOPICS[family].split()) | {family}

                def relevant_to_family(dumpable) -> bool:
                    text = " ".join(
                        str(getattr(dumpable, key, "") or "")
                        for key in (
                            "target", "scope", "cluster", "option", "value",
                            "reason", "decision", "document_type",
                        )
                    ).lower()
                    return (
                        any(word in text for word in family_words)
                        or any(
                            block_id in ranked_ids
                            for block_id in (getattr(dumpable, "block_ids", None) or [])
                        )
                    )

                option_clusters_here = (
                    clusters
                    if family == "costs"
                    else [
                        c for c in clusters
                        if any(opt.block_id in ranked_ids for opt in c.options)
                    ]
                )
                semantic_state = {
                    "observations": compact_items(observations, budget=500),
                    "selections": [
                        s.model_dump() for s in selections if relevant_to_family(s)
                    ],
                    "number_roles": [
                        n.model_dump() for n in number_roles if relevant_to_family(n)
                    ],
                    "precedence": [
                        p.model_dump() for p in precedence_rules if relevant_to_family(p)
                    ],
                    "applicability_decisions": [
                        d.model_dump() for d in applicability_entries if relevant_to_family(d)
                    ],
                    "option_clusters": compact_items(option_clusters_here, budget=400),
                }
                prompt = (
                    "Resolve " + family + " across the supplied sources, the ContractMap dependencies and the "
                    "compact cross-clause applicability context. Compare competing clauses, definitions, annexes and "
                    "amendment authority. Classify each returned candidate's applicability: 'applicable' = binding "
                    "for this contract now; 'alternative' = an explicitly visible but NOT selected/gated option "
                    "(e.g. unselected plans or add-on options); 'superseded' = replaced by a later authoritative "
                    "clause/annex/email. Deterministic calculation EXCLUDES alternative and superseded facts. "
                    "Be concise. "
                    "For cost/price fields resolve ONLY the applicable binding price of the selected option; never "
                    "aggregate gated options into annual totals. Do not use a number as the contract number if the "
                    "applicability context classifies it as order_number/reference/customer_number. Keep unresolved "
                    "alternatives as conflicting/ambiguous; abstain instead of guessing. Return candidates only for "
                    "requested fields. evidence_refs must quote exact text from the referenced source block. Do not "
                    "put generated evidence inside normalized values. Do not compute annualized costs or derived "
                    "dates. Money={amount:number,currency:string,period:monthly|quarterly|semi_annual|annual|once}; "
                    "For costs.scheduled_prices preserve every explicit staged price separately as "
                    "{period_index:1-based integer,period_label:verbatim period label,amount:Money,condition:null|string}; "
                    "use this for year-by-year/phase-by-phase fixed prices and include zero-price periods. "
                    "For costs.variable_charges preserve usage/event prices separately as "
                    "{label:string,amount:Money,unit:per_call|per_hour|per_device|verbatim unit,condition:null|string}; "
                    "never fold variable charges into scheduled prices or a total. "
                    "For identity roles: supplier/contractor is the external service provider/vendor and customer "
                    "is the hospital/client; do not swap party roles. "
                    "Duration={value:integer,unit:days|weeks|months|years}; "
                    "FlexibleDate={date:YYYY-MM-DD|null,condition:string|null}; "
                    "TimeValue={value:number,unit:hours|days,original_text:string}; "
                    "Equipment objects: device_name,manufacturer,model,serial_number,inventory_number,system_name,"
                    "service_scope,included_services:list,excluded_services:list. Candidate field types: "
                    + json.dumps(catalog, separators=(",", ":"))
                    + "\nCompact semantic state: "
                    + json.dumps(semantic_state, ensure_ascii=False, separators=(",", ":"))
                    + "\n"
                )

                family_overhead = SYSTEM + prompt + json.dumps(CandidateBatch.model_json_schema())
                # Dynamic packing: the block budget is derived from the ACTUAL
                # prompt components (instruction/schema overhead plus the bounded
                # per-segment provisional-section context) plus per-block visual
                # observation costs. No static magic reserve like 1100/1300.
                sections_bound = (
                    sections_bound_tokens() + 32
                    if section_understandings
                    else 0
                )
                full_document_prompt = family_overhead + assemble(document.blocks)
                if planner.fits(full_document_prompt):
                    ordered_blocks = list(document.blocks)
                    planner.decisions.append({
                        "purpose": family,
                        "decision": "full_contract_family_context",
                        "block_count": len(ordered_blocks),
                    })
                else:
                    ordered_ids = {block.id for block in ranked}
                    ordered_blocks = [block for block in document.blocks if block.id in ordered_ids]
                    if not ordered_blocks:
                        ordered_blocks = list(document.blocks)
                segment_batches: list[CandidateBatch] = []
                try:
                    family_segments = planner.segments(
                        ordered_blocks,
                        family_overhead,
                        purpose="resolve_segments:" + family,
                        extra_reserve=sections_bound + _PACK_SAFETY_MARGIN,
                        per_block_cost=block_vision_cost,
                    )
                except CallBudgetExhausted:
                    budget_exhausted = True
                    planner.decisions.append({
                        "purpose": "resolve_segments:" + family,
                        "decision": "call_budget_exhausted",
                    })
                    family_segments = []
                except (ContextOverflow, ValueError, RuntimeError, AIProviderError) as exc:
                    issues.append(f"{family}: {type(exc).__name__}; manuelle Prüfung erforderlich")
                    planner.decisions.append({
                        "purpose": "resolve_segments:" + family,
                        "decision": "family_segmentation_failed",
                        "error_type": type(exc).__name__,
                    })
                    family_segments = []

                for segment_index, segment in enumerate(family_segments):
                    if budget_exhausted:
                        break
                    context = assemble(segment)
                    visual = vision_context(segment)
                    segment_pages = sorted(
                        {block.page for block in segment if block.page is not None}
                    )
                    local_prompt = (
                        prompt
                        + "Visual observations for these blocks: " + visual + "\n"
                        + "Relevant provisional section readings for these blocks: "
                        + sections_context_pages(segment_pages) + "\n"
                    )
                    try:
                        resolved = await call(
                            f"resolve:{family}:{segment_index}",
                            local_prompt + context,
                            CandidateBatch,
                            pages=segment_pages or None,
                            stage="resolve",
                        )
                        resolved = await verify(resolved, context, f"ground:{family}:{segment_index}")
                        segment_batches.append(resolved)
                    except CallBudgetExhausted:
                        budget_exhausted = True
                        planner.decisions.append({
                            "purpose": f"resolve:{family}:{segment_index}",
                            "decision": "call_budget_exhausted",
                        })
                        break
                    except (ContextOverflow, ValueError, RuntimeError, AIProviderError) as exc:
                        issues.append(
                            f"{family} segment {segment_index}: {type(exc).__name__}; "
                            "manuelle Prüfung erforderlich"
                        )
                        planner.decisions.append({
                            "purpose": f"resolve:{family}:{segment_index}",
                            "decision": "segment_failed_continue",
                            "error_type": type(exc).__name__,
                        })

                if segment_batches:
                    batch = _coalesce_batch(
                        CandidateBatch(
                            candidates=[
                                candidate
                                for item in segment_batches
                                for candidate in item.candidates
                            ]
                        ),
                        expected,
                    )
                else:
                    batch = CandidateBatch(
                        candidates=[
                            FactCandidate(field=field, status="missing")
                            for field in family_types
                        ]
                    )

                for candidate in batch.candidates:
                    if candidate.field not in family_types:
                        candidate.status = "unsupported"
                    elif candidate.status == "supported":
                        try:
                            strict_value(
                                family_types[candidate.field],
                                candidate.normalized_value
                                if candidate.normalized_value is not None
                                else candidate.value,
                            )
                        except (ValueError, TypeError):
                            candidate.status = "unsupported"

                failed = [
                    candidate
                    for candidate in batch.candidates
                    if candidate.status != "supported"
                    or candidate.conflicts
                    or candidate.missing_dependencies
                    or candidate.ambiguity
                ]
                if failed:
                    remaining_families = len(topic_names) - family_index - 1
                    reserve_for_core = remaining_families * 2
                    calls_left = self.settings.harness_max_calls - len(calls)
                    if calls_left <= reserve_for_core + 2:
                        planner.decisions.append({
                            "purpose": family,
                            "decision": "recovery_deferred_to_preserve_core_call_budget",
                            "calls_left": calls_left,
                            "reserved_core_calls": reserve_for_core,
                        })
                    else:
                        unresolved_fields = {candidate.field for candidate in failed}
                        evidence_ids = {
                            ref.block_id
                            for candidate in failed
                            for ref in candidate.evidence_refs
                            if ref.block_id in document.index
                        }
                        recovery_ranked = [
                            document.index[block_id] for block_id in evidence_ids
                        ]
                        recovery_ranked.extend(
                            block for block in ranked if block.id not in evidence_ids
                        )
                        recovery_prefix = (
                            prompt
                            + "\nRecover ONLY these unresolved fields. Keep successful fields untouched. "
                            "Re-evaluate precedence and applicability; abstain when the source does not "
                            "establish a value.\n"
                            + CandidateBatch(candidates=failed).model_dump_json()
                            + "\n"
                        )
                        try:
                            recovery_blocks = planner.pack_ranked(
                                recovery_ranked,
                                SYSTEM
                                + recovery_prefix
                                + json.dumps(CandidateBatch.model_json_schema()),
                                purpose="recovery_context:" + family,
                                extra_reserve=sections_bound + _PACK_SAFETY_MARGIN,
                                per_block_cost=block_vision_cost,
                            )
                            if recovery_blocks:
                                recovery_pages = sorted(
                                    {block.page for block in recovery_blocks if block.page is not None}
                                )
                                recovery_context = (
                                    assemble(
                                        sorted(
                                            recovery_blocks,
                                            key=lambda b: document.blocks.index(b),
                                        )
                                    )
                                    + "\nVisual observations for recovery blocks: "
                                    + vision_context(recovery_blocks)
                                    + "\nRelevant provisional section readings for recovery blocks: "
                                    + sections_context_pages(recovery_pages)
                                )
                                recovery = await call(
                                    "recovery:" + family,
                                    recovery_prefix + recovery_context,
                                    CandidateBatch,
                                    pages=recovery_pages or None,
                                    stage="recover",
                                )
                                recovery = await verify(recovery, recovery_context, "recovery_ground:" + family)
                                recovery = _coalesce_batch(recovery)
                                recovered = {
                                    candidate.field: candidate
                                    for candidate in recovery.candidates
                                    if candidate.field in unresolved_fields
                                    and candidate.status == "supported"
                                }
                                batch.candidates = [
                                    recovered.get(candidate.field, candidate)
                                    for candidate in batch.candidates
                                ]
                                planner.decisions.append({
                                    "purpose": family,
                                    "recovered_fields": sorted(recovered),
                                    "unresolved_fields": sorted(unresolved_fields - set(recovered)),
                                })
                        except CallBudgetExhausted:
                            budget_exhausted = True
                            planner.decisions.append({
                                "purpose": "recovery:" + family,
                                "decision": "call_budget_exhausted",
                            })
                        except (ContextOverflow, ValueError, RuntimeError, AIProviderError) as exc:
                            issues.append(f"{family} recovery: {type(exc).__name__}; manuelle Prüfung erforderlich")
                            planner.decisions.append({
                                "purpose": "recovery:" + family,
                                "decision": "recovery_failed_keep_core",
                                "error_type": type(exc).__name__,
                            })

                candidates.extend(batch.candidates)

            issues.extend(reason for mapping in maps for reason in mapping.missing_material)
            supported_count = 0
            excluded_count = 0
            for candidate in candidates:
                if candidate.status != "supported" or candidate.conflicts or candidate.missing_dependencies or candidate.ambiguity:
                    issues.append(candidate.field + ": " + candidate.status)
                    continue
                if candidate.applicability in _ALTERNATIVE_LABELS:
                    excluded_count += 1
                    planner.decisions.append({
                        "field": candidate.field,
                        "applicability_excluded": candidate.applicability,
                    })
                    continue
                if candidate.field == "identity.contract_number":
                    # G / Qwen-authority invariant: the number role below comes
                    # ONLY from the Qwen number-role/applicability result. This
                    # guard never infers a role from the string itself; it merely
                    # prevents a Qwen-classified order/reference/customer number
                    # from being written as the contract number.
                    raw = candidate.normalized_value if candidate.normalized_value is not None else candidate.value
                    if raw is not None:
                        key = str(raw).strip()
                        role = role_for_number(key)
                        has_contract_role = "contract_number" in {
                            n.role for n in number_roles if str(n.value).strip() == key
                        }
                        if role in {"order_number", "reference", "customer_number", "other"} and not has_contract_role:
                            issues.append(
                                "identity.contract_number: Nummer als "
                                + role.replace("_", " ")
                                + " klassifiziert; Vertragsnummer nicht bestätigt – manuelle Prüfung"
                            )
                            continue
                try:
                    if not canonicalize_evidence(candidate) or candidate.field not in types:
                        raise ValueError("Ungrounded or unknown field")
                    value = strict_value(
                        types[candidate.field],
                        candidate.normalized_value if candidate.normalized_value is not None else candidate.value,
                    )
                    if candidate.field == "equipment":
                        contract.equipment = value or []
                    else:
                        group, field = candidate.field.split(".", 1)
                        setattr(getattr(contract, group), field, value)
                    supported_count += 1

                    for ref in candidate.evidence_refs:
                        block = document.index[ref.block_id]
                        source = SourceEvidence(
                            document_id=canonical.document_id,
                            page=block.page,
                            source_type=block.source_type,
                            source_text=ref.quote,
                            paragraph_index=block.source_index if block.source_type == "paragraph" else None,
                            table_index=block.source_index if block.source_type == "table" else None,
                        )
                        box, confidence = evidence_geometry(block, ref.quote)
                        if box is not None:
                            source.bounding_box = box
                            source.ocr_confidence = confidence
                        evidence_rows.append(
                            {"field": candidate.field, "block_id": block.id, "source": source.model_dump(mode="json")}
                        )
                        if candidate.field == "equipment":
                            for equipment in contract.equipment:
                                if equipment.evidence is None:
                                    equipment.evidence = source
                        else:
                            holder = getattr(contract, candidate.field.split(".")[0])
                            if holder.evidence is None:
                                holder.evidence = source
                except (ValueError, TypeError):
                    candidate.status = "unsupported"
                    issues.append(candidate.field + ": unsupported")

            if excluded_count:
                planner.decisions.append({
                    "applicability_exclusions": excluded_count,
                })
            if supported_count == 0:
                issues.append("Keine belastbar belegte Vertragsinformation extrahiert")

        except CallBudgetExhausted as exc:
            budget_exhausted = True
            issues.append("Modell-Call-Budget erschöpft; Analyse abgebrochen – manuelle Prüfung erforderlich")
            planner.decisions.append({
                "purpose": "harness",
                "decision": "call_budget_exhausted",
                "error_type": type(exc).__name__,
            })
        except Exception as exc:
            issues.append("Harness: " + type(exc).__name__ + "; manuelle Prüfung erforderlich")
            if "supported_count" not in locals():
                supported_count = 0
            planner.decisions.append({
                "purpose": "harness",
                "decision": "unexpected_exception",
                "error_type": type(exc).__name__,
            })

        contract.review.requires_manual_review = bool(issues)
        contract.review.review_reasons = [ReviewFlag.OTHER] if issues else []
        contract.review.risk_notes = "; ".join(dict.fromkeys(issues)) or None
        contract.analysis.harness_version = "v3"
        contract.analysis.model_name = model_id
        contract.analysis.analysis_version = "harness-v3"
        contract.analysis.analysis_timestamp = datetime.now(timezone.utc).isoformat()
        diagnostics = {
            "harness_version": "v3",
            "provider": provider_id,
            "model": model_id,
            "source_sha256": canonical.source_sha256,
            "advertised_context": planner.advertised,
            "context_budget": planner.capacity,
            "context_decisions": planner.decisions,
            "budget_exhausted": budget_exhausted,
            "failure_categories": _tally_failure_categories(calls, budget_exhausted),
            "dropped_refs": dropped_refs,
            "perception": {
                "option_clusters": [c.model_dump() for c in clusters],
            },
            "section_understandings": [s.model_dump() for s in section_understandings],
            "global_understanding": (
                global_understanding.model_dump() if global_understanding is not None else None
            ),
            "contract_maps": [mapping.model_dump() for mapping in maps],
            "applicability": [decision.model_dump() for decision in applicability_entries],
            "selections": [s.model_dump() for s in selections],
            "number_roles": [n.model_dump() for n in number_roles],
            "precedence": [p.model_dump() for p in precedence_rules],
            "visual_observations": {
                key: value.model_dump() for key, value in visual_observations.items()
            },
            "candidates": [candidate.model_dump() for candidate in candidates],
            "evidence_count": len(evidence_rows),
            "calls": calls,
            "call_count": len(calls),
            "failure_count": sum(bool(call_row.get("failed")) for call_row in calls),
            "recovery_count": sum(bool(call_row.get("recovery")) for call_row in calls),
            "issues": list(dict.fromkeys(issues)),
        }
        contract.analysis.harness = {
            **diagnostics,
            "document_intelligence": canonical.provenance.model_dump(mode="json"),
            "token_estimator": "utf8_byte_estimate_div3_safety1.35",
            "evidence": evidence_rows,
        }

        status = ExtractionStatus.PARTIAL if issues else ExtractionStatus.SUCCESS
        contract.analysis.extraction_status = status
        has_grounded_truth = bool(locals().get("supported_count", 0))
        validation_status = (
            ValidationStatus.VALID if has_grounded_truth else ValidationStatus.UNKNOWN
        )
        contract.analysis.validation_status = validation_status

        failed_calls = [row for row in calls if row.get("failed")]
        last_failure = failed_calls[-1] if failed_calls else None
        technical_error = None
        if not has_grounded_truth:
            if budget_exhausted:
                technical_error = "HarnessFailure purpose=harness category=call_budget_exhausted"
            elif last_failure is not None:
                technical_error = (
                    "HarnessFailure"
                    f" purpose={last_failure.get('purpose')}"
                    f" category={last_failure.get('error_category') or 'unknown'}"
                    f" type={last_failure.get('error_type') or 'unknown'}"
                    f" done_reason={last_failure.get('done_reason') or 'none'}"
                    f" response_sha256={last_failure.get('response_sha256') or 'none'}"
                )
            else:
                technical_error = "HarnessFailure purpose=unknown category=no_grounded_facts"

        result = ContractAnalysisResult(
            document_id=canonical.document_id or "",
            contract=contract if has_grounded_truth else None,
            status=status,
            validation_status=validation_status,
            requires_review=bool(issues) or not has_grounded_truth,
            model=model_id,
            prompt_version="harness-v3",
            ai_call_count=len(calls),
            groups_processed=sum(
                1 for family in TOPICS
                if any(call_row.get("purpose", "").startswith("resolve:" + family + ":") for call_row in calls)
            ),
            processing_duration=time.monotonic() - started,
            message="Analyse benötigt manuelle Prüfung." if issues else "Analyse abgeschlossen.",
            error=technical_error,
            diagnostics=diagnostics,
        )
        return result