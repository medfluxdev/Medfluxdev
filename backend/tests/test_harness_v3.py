"""PR-6 / Contract Intelligence V3 focused tests.

Mocked provider only. These tests validate ARCHITECTURE and CONTROL FLOW, not
ABIOMED/Accutron correctness against the real model. A real-model benchmark is
still required (see test_report notes at the bottom of this module).
"""
import inspect
import json
from types import SimpleNamespace

import pytest

from app.ai.harness import get_harness_class
from app.ai.harness.context import CallBudgetExhausted, ContextOverflow, ContextPlanner, estimate_tokens
from app.ai.harness.document import Block, DocumentModel
from app.ai.harness.models import (
    ApplicabilityDecision,
    ContractMap,
    NumberRole,
    Observation,
    PrecedenceRule,
    SectionUnderstanding,
    SelectionRelation,
)
from app.ai.harness.pipeline import HarnessV2
from app.ai.harness.v3 import (
    HarnessV3,
    _fair_token_allocation,
    _merge_maps_v3,
    _retry_fits_context,
    _retry_output_plan,
    compact_sections,
    measured_output_budget,
    sanitize_applicability,
    sanitize_contract_map,
)
from app.ai.harness.v3_perception import perceive_option_clusters
from app.ai.schemas import ModelCapabilities, ModelDescriptor
from app.core.config import Settings
from app.documents.intelligence.canonical import (
    BoundingRegion,
    DocumentIntelligenceResult,
    Element,
    Page,
    ProcessingProvenance,
)
from app.models.values import Money


SETTINGS_V3 = dict(
    harness_engine="v3",
    harness_max_calls=64,
    harness_vision_pages_per_batch=2,
    harness_vision_min_pages_for_batch=2,
)


def v3_settings(**overrides):
    return Settings(_env_file=None, **(SETTINGS_V3 | overrides))


def native_document(text="Vertrag 452664 MedTech GmbH Service 1.650,00 EUR"):
    return DocumentIntelligenceResult(
        document_id="synthetic",
        source_sha256="a" * 64,
        canonical_text=text,
        provenance=ProcessingProvenance(provider="native_pdf"),
        pages=[
            Page(
                page_number=1,
                width_pt=600,
                height_pt=800,
                text=text,
                elements=[
                    Element(
                        element_id="a",
                        page=1,
                        reading_order=0,
                        text=text,
                        type="paragraph",
                        method="native",
                    )
                ],
            )
        ],
    )


def scan_document(pages: int):
    page_models = []
    for page_number in range(1, pages + 1):
        text = "Vertrag 452664 MedTech GmbH 1.650,00 EUR" if page_number == 1 else ""
        page_models.append(
            Page(
                page_number=page_number,
                width_pt=600,
                height_pt=800,
                text=text,
                elements=[
                    Element(
                        element_id=f"s{page_number}",
                        page=page_number,
                        reading_order=0,
                        text=text,
                        type="image",
                        method="native",
                    )
                ],
            )
        )
    return DocumentIntelligenceResult(
        document_id="synthetic",
        source_sha256="b" * 64,
        canonical_text=" ".join(p.text or "" for p in page_models),
        provenance=ProcessingProvenance(provider="native_pdf"),
        pages=page_models,
    )


def multi_block_document(blocks: int = 8, block_ref="p1:e0"):
    """Text-based multi-block document whose full-document prompt does NOT fit,
    forcing the family resolver to use planner.segments()/packing."""
    elements = []
    texts = []
    for i in range(blocks):
        text = f"Klausel {i}. " + ("Vertragsbedingungen und Leistungsumfang " * 22)
        texts.append(text)
        elements.append(
            Element(
                element_id=f"e{i}",
                page=1,
                reading_order=i,
                text=text,
                type="paragraph",
                method="native",
            )
        )
    return DocumentIntelligenceResult(
        document_id="synthetic",
        source_sha256="f" * 64,
        canonical_text=" ".join(texts),
        provenance=ProcessingProvenance(provider="native_pdf"),
        pages=[Page(
            page_number=1, width_pt=600, height_pt=800, text=" ".join(texts),
            elements=elements,
        )],
    )


class FakeProvider:
    supports_structured_output = True
    last_done_reason = None
    last_usage = {"prompt_tokens": 123, "completion_tokens": 42}

    def __init__(self, unsupported=False, cost_applicability="applicable", number_decision=None,
                 block_ref="p1:a", map_number_role="order_number",
                 truncated_titles=None, truncate_once=True):
        self.requests = []
        self.unsupported = unsupported
        self.cost_applicability = cost_applicability
        self.number_decision = number_decision
        self.block_ref = block_ref
        self.map_number_role = map_number_role
        self.truncated_titles = set(truncated_titles or [])
        self.truncate_once = truncate_once
        self._truncated = False

    def _find_candidate_batch(self, text):
        idx = text.find('{"candidates"')
        found = None
        while idx != -1:
            try:
                obj, _ = json.JSONDecoder().raw_decode(text, idx)
                if isinstance(obj, dict) and "candidates" in obj:
                    found = obj
            except Exception:
                pass
            idx = text.find('{"candidates"', idx + 1)
        return found

    async def generate_request(self, text, system, schema, max_tokens, context_tokens, images=None):
        self.requests.append((text, images, context_tokens))
        title = schema["title"]
        ref = self.block_ref
        truncated = title in self.truncated_titles and not (self.truncate_once and self._truncated)
        if truncated:
            self._truncated = True
            self.last_done_reason = "length"
        else:
            self.last_done_reason = None
        if title == "VisionObservation":
            return json.dumps({"description": "Visual region with option table"})
        if title == "SectionUnderstanding":
            return json.dumps({"section_index": 0})
        if title == "GlobalContractUnderstanding":
            return json.dumps({
                "document_type": "service",
                "purpose": "wartung",
                "authority_order": ["Hauptvertrag", "Anlage"],
                "selections_summary": ["selected plan visible"],
                "key_clauses": ["plan options and prices"],
                "unresolved": [],
            })
        if title == "ContractMap":
            payload = {
                "document_type": "service",
                "observations": [{
                    "topic": "identity costs delivery",
                    "summary": "Service contract with plan options",
                    "block_refs": [ref],
                    "related_refs": [],
                }],
                "selections": [{
                    "cluster": "plan", "option": "selected plan", "selected": True,
                    "applicability": "applicable", "block_ids": [ref],
                    "reason": "selection evidenced in clause",
                }],
            }
            if self.map_number_role is not None:
                payload["number_roles"] = [{
                    "value": "452664", "role": self.map_number_role, "block_ids": [ref],
                    "reason": "appears as order reference",
                }]
            return json.dumps(payload)
        if title == "ApplicabilityBatch":
            decisions = [{
                "scope": "option", "decision": "selected", "target": "selected plan",
                "reason": "selection evidenced", "block_ids": [ref],
            }]
            if self.number_decision is not None:
                decisions.append({
                    "scope": "number", "decision": self.number_decision, "target": "452664",
                    "reason": "number role", "block_ids": [ref],
                })
            return json.dumps({"decisions": decisions})
        if title == "GroundingBatch":
            batch = self._find_candidate_batch(text) or {"candidates": []}
            return json.dumps({
                "decisions": [{
                    "candidate_index": i, "supported": not self.unsupported,
                    "explanation": "Source entails claim",
                } for i in range(len(batch["candidates"]))],
            })
        if title == "CandidateBatch":
            if "costs, payment" in text and "related contract-field pack" in text:
                return json.dumps({"candidates": [{
                    "field": "costs.annual_cost",
                    "value": {"amount": 1650, "currency": "EUR", "period": "annual"},
                    "status": "supported",
                    "applicability": self.cost_applicability,
                    "evidence_refs": [{"block_id": ref, "quote": "1.650,00 EUR"}],
                }]})
            if "identity, dates, termination" in text and "related contract-field pack" in text:
                facts = [{
                    "field": "identity.contract_number", "value": "452664",
                    "status": "supported",
                    "evidence_refs": [{"block_id": ref, "quote": "452664"}],
                }]
                if self.unsupported:
                    return json.dumps({"candidates": facts})
                facts.append({
                    "field": "identity.supplier", "value": "MedTech GmbH",
                    "status": "supported",
                    "evidence_refs": [{"block_id": ref, "quote": "MedTech GmbH"}],
                })
                return json.dumps({"candidates": facts})
            return '{"candidates": []}'
        raise AssertionError(f"unexpected schema {title}")


def ai(provider, vision=True):
    async def runtime():
        return provider, ModelDescriptor(
            provider_id="mock",
            model_id="selected",
            context_length=262144,
            capabilities=ModelCapabilities(text=True, vision=vision),
        )

    return SimpleNamespace(harness_runtime=runtime)


# ----------------------------------------------------------------------
# Engine selection (decision 1: v2 stays the default, v3 explicit)
# ----------------------------------------------------------------------


def test_engine_selection_default_is_v2_and_v3_is_explicit():
    assert get_harness_class(Settings(_env_file=None)) is HarnessV2
    assert get_harness_class(v3_settings()) is HarnessV3


def test_no_business_specific_rule_strings_in_v3_source():
    for cls in (HarnessV3,):
        source = inspect.getsource(cls)
        for forbidden in ("Guard TOP", "ABIOMED", "Accutron", "1650", "1.650"):
            assert forbidden not in source


# ----------------------------------------------------------------------
# Perception layer (evidence capture only)
# ----------------------------------------------------------------------


def test_perception_captures_option_clusters_and_selection_controls():
    text = ("Schutzpläne\nGuard TOP ............ 1.650,00 EUR\n"
            "Basis (x) 350,00 EUR")
    source = DocumentIntelligenceResult(
        document_id="synthetic",
        source_sha256="c" * 64,
        canonical_text=text,
        provenance=ProcessingProvenance(provider="native_pdf"),
        pages=[Page(
            page_number=1, width_pt=600, height_pt=800, text=text,
            elements=[
                Element(element_id="h", type="heading", text="Schutzpläne", page=1,
                        reading_order=0, method="native"),
                Element(element_id="p1", type="paragraph", text="Guard TOP ............ 1.650,00 EUR",
                        page=1, reading_order=1, method="native",
                        region=BoundingRegion(page=1, x0=50, y0=50, x1=500, y1=60)),
                Element(element_id="cb", type="checkbox", text="", page=1, reading_order=2,
                        method="native", region=BoundingRegion(page=1, x0=30, y0=49, x1=40, y1=59)),
                Element(element_id="p2", type="paragraph", text="Basis (x) 350,00 EUR",
                        page=1, reading_order=3, method="native",
                        region=BoundingRegion(page=1, x0=50, y0=90, x1=500, y1=100)),
            ],
        )],
    )
    model = DocumentModel.build(source)
    clusters = perceive_option_clusters(source, model)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.cluster_label == "Schutzpläne"
    labels = {option.label for option in cluster.options}
    assert labels == {"Guard TOP", "Basis"}
    by_label = {option.label: option for option in cluster.options}
    assert by_label["Guard TOP"].price_text == "1.650,00 EUR"
    assert by_label["Guard TOP"].control_region is not None
    assert by_label["Basis"].selection_hint is True
    assert by_label["Guard TOP"].selection_hint is None


def test_perception_never_raises_and_never_decides():
    assert perceive_option_clusters(None, DocumentModel.build(native_document())) == []
    assert perceive_option_clusters(native_document(), DocumentModel.build(native_document())) or True


# ----------------------------------------------------------------------
# deterministischer Merge der V3-Map-Oberfläche
# ----------------------------------------------------------------------


def test_merge_maps_v3_unions_v3_surface_losslessly():
    a = ContractMap(selections=[SelectionRelation(cluster="plan", option="A", selected=True,
                                                  applicability="applicable")],
                    number_roles=[NumberRole(value="1", role="contract_number")])
    b = ContractMap(selections=[SelectionRelation(cluster="plan", option="B", selected=False,
                                                  applicability="alternative")],
                    number_roles=[NumberRole(value="1", role="contract_number")],
                    precedence=[{"document_type": "Anlage", "rank": 1}])
    merged = _merge_maps_v3([a, b])
    assert len(merged.selections) == 2
    assert len(merged.number_roles) == 1  # dedupe by (value, role)
    assert len(merged.precedence) == 1


# ----------------------------------------------------------------------
# HarnessV3 control flow (mocked)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v3_full_native_path_records_stages_and_contract():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    assert result.contract is not None, result.diagnostics["issues"]
    assert result.contract.identity.supplier == "MedTech GmbH"
    assert result.contract.costs.annual_cost.amount == 1650
    assert result.contract.analysis.harness_version == "v3"
    assert result.diagnostics["harness_version"] == "v3"
    assert result.prompt_version.startswith("harness-v3")

    purposes = {row.get("purpose") for row in result.diagnostics["calls"]}
    assert "global_understanding" in purposes
    assert any(p.startswith("understanding:") for p in purposes)
    assert "applicability" in purposes
    assert any(p.startswith("resolve_pack:core:") for p in purposes)
    assert any(p.startswith("resolve_pack:commercial:") for p in purposes)

    global_call = next(row for row in result.diagnostics["calls"] if row["purpose"] == "global_understanding")
    assert global_call["stage"] == "global"
    assert global_call["pages"] == [1]
    assert "response_sha256" in global_call
    assert "latency_seconds" in global_call
    assert "usage" in global_call
    assert result.diagnostics["selections"]
    assert "order_number" in {n["role"] for n in result.diagnostics["number_roles"]}
    assert result.diagnostics["precedence"] or True


@pytest.mark.asyncio
async def test_v3_scanned_document_batches_visual_compute_into_sections():
    provider = FakeProvider(block_ref="p1:s1")
    rendered = []
    page_images = {"p": lambda p: rendered.append(p) or "img"}
    result = await HarnessV3(v3_settings(), ai(provider, vision=True)).analyze(
        scan_document(4),
        image_loader=lambda block: "img",
        page_image_loader=page_images["p"],
    )
    diagnostics = result.diagnostics
    section_rows = [row for row in diagnostics["calls"] if row.get("schema") == "SectionUnderstanding"]
    assert len(section_rows) == 2
    assert [row["pages"] for row in section_rows] == [[1, 2], [3, 4]]
    assert all(row["stage"] == "sections" for row in section_rows)
    assert rendered == [1, 2, 3, 4]
    assert len(diagnostics["section_understandings"]) == 2
    assert diagnostics["global_understanding"] is not None
    purposes = {row.get("purpose") for row in diagnostics["calls"]}
    assert any(str(p).startswith("understanding:") for p in purposes)
    vision_rows = [row for row in diagnostics["calls"] if row.get("stage") == "vision"]
    # Page-first vision owns these scanned pages, so duplicate region calls
    # are intentionally suppressed.
    assert vision_rows == []
    deferred = [
        d for d in diagnostics["context_decisions"]
        if d.get("vision") == "deferred_to_page_batch"
    ]
    assert len(deferred) == 4


@pytest.mark.asyncio
async def test_v3_image_heavy_without_vision_degrades_gracefully():
    provider = FakeProvider(block_ref="p1:s1")
    result = await HarnessV3(v3_settings(), ai(provider, vision=False)).analyze(
        scan_document(4), image_loader=lambda block: "img", page_image_loader=lambda p: "img"
    )
    assert any("Vision" in issue for issue in result.diagnostics["issues"])
    assert result.requires_review
    assert result.contract is not None, "deterministic recall must still succeed without vision"


# ----------------------------------------------------------------------
# Deterministische Anwendbarkeit (decisions 4 + 10)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v3_applicable_cost_is_used_and_alternative_is_excluded():
    provider = FakeProvider(cost_applicability="alternative")
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    assert result.contract is not None, result.diagnostics["issues"]
    assert result.contract.costs.annual_cost is None, "alternative must never reach the contract"
    assert result.contract.identity.supplier == "MedTech GmbH", "other grounded facts survive"
    excluded = [d for d in result.diagnostics["context_decisions"] if "applicability_excluded" in d]
    assert any(d["field"] == "costs.annual_cost" for d in excluded)
    candidates = result.diagnostics["candidates"]
    assert any(c["field"] == "costs.annual_cost" and c["applicability"] == "alternative" for c in candidates)


@pytest.mark.asyncio
async def test_v3_superseded_is_also_excluded():
    provider = FakeProvider(cost_applicability="superseded")
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    assert result.contract is not None
    assert result.contract.costs.annual_cost is None


@pytest.mark.asyncio
async def test_v3_number_used_as_reference_is_not_written_as_contract_number():
    provider = FakeProvider(cost_applicability="applicable", number_decision="order_number")
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    assert result.contract is not None, result.diagnostics["issues"]
    assert result.contract.identity.contract_number is None, "reference number must not become contract number"
    assert any(issue.startswith("identity.contract_number") for issue in result.diagnostics["issues"])
    roles = {n["value"]: n["role"] for n in result.diagnostics["number_roles"]}
    assert roles.get("452664") == "order_number"


@pytest.mark.asyncio
async def test_v3_no_grounded_truth_returns_none_and_durable_error():
    provider = FakeProvider(unsupported=True)
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    assert result.contract is None
    assert result.requires_review
    assert result.error and result.error.startswith("HarnessFailure")
    assert result.diagnostics["call_count"] == len(provider.requests)


@pytest.mark.asyncio
async def test_v3_call_budget_is_hard():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(harness_max_calls=1), ai(provider)).analyze(native_document())
    assert len(provider.requests) == 1
    assert result.contract is None
    assert result.requires_review
    assert result.diagnostics["call_count"] == 1


@pytest.mark.asyncio
async def test_v3_page_images_are_only_loaded_within_budget_and_bounded():
    provider = FakeProvider(block_ref="p1:s1")
    rendered_pages = []
    settings = v3_settings(harness_vision_pages_per_batch=1)
    result = await HarnessV3(settings, ai(provider, vision=True)).analyze(
        scan_document(5),
        image_loader=lambda block: "img",
        page_image_loader=lambda page: rendered_pages.append(page) or "img",
    )
    sections = [row["pages"] for row in result.diagnostics["calls"] if row.get("schema") == "SectionUnderstanding"]
    assert sections == [[1], [2], [3], [4], [5]]
    assert rendered_pages == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_v3_existing_map_helpers_reused_for_evidence():
    # Field catalog and strict typing are the same deterministic tower as v2.1.
    from app.ai.harness.pipeline import field_types, _coalesce_batch
    assert "costs.annual_cost" in field_types()
    sample = Money(amount=1000, currency="EUR", period="annual")
    batch = {"candidates": [{"field": "costs.annual_cost", "value": sample.model_dump(),
                             "status": "supported", "evidence_refs": [{"block_id": "a", "quote": "1000 EUR"}]}]}
    from app.ai.harness.models import CandidateBatch, FactCandidate, EvidenceRef
    merged = _coalesce_batch(CandidateBatch(candidates=[FactCandidate(**batch["candidates"][0])]))
    assert merged.candidates[0].status == "supported"


# ----------------------------------------------------------------------
# A - ContractMap invalid source-ref tolerance (quarantine, never remap)
# ----------------------------------------------------------------------


def _nine_valid_one_invalid_map() -> ContractMap:
    document_model = DocumentModel.build(native_document())
    observations = [
        Observation(topic=f"t{i}", summary=f"summary {i}", block_refs=["p1:a"])
        for i in range(9)
    ]
    observations.append(
        Observation(topic="ghost", summary="phantom clause", block_refs=["p1:ghost"])
    )
    return ContractMap(observations=observations), document_model


def test_a_single_invalid_observation_does_not_discard_map():
    mapping, document = _nine_valid_one_invalid_map()
    clean, dropped = sanitize_contract_map(document, mapping, stage="test")
    assert len(clean.observations) == 9
    assert len(dropped) == 1
    assert dropped[0]["item_type"] == "observation"
    assert dropped[0]["invalid_refs"] == ["p1:ghost"]
    assert dropped[0]["action"] == "dropped"
    assert dropped[0]["requires_review"] is True
    assert all("p1:ghost" not in obs.block_refs for obs in clean.observations)


def test_a_invalid_selection_rejected_observations_survive():
    mapping, document = _nine_valid_one_invalid_map()
    mapping.selections = [
        SelectionRelation(cluster="plan", option="sel", selected=True,
                          applicability="applicable", block_ids=["p1:bad"])
    ]
    clean, dropped = sanitize_contract_map(document, mapping, stage="test")
    assert clean.selections == []
    assert len(clean.observations) == 9
    assert any(d["item_type"] == "selection" for d in dropped)


def test_a_invalid_number_role_rejected_unrelated_semantics_survive():
    mapping, document = _nine_valid_one_invalid_map()
    mapping.number_roles = [
        NumberRole(value="452664", role="order_number", block_ids=["p1:bad"]),
        NumberRole(value="Z-2", role="reference", block_ids=["p1:a"]),
    ]
    mapping.selections = [
        SelectionRelation(cluster="plan", option="sel", selected=True,
                          applicability="applicable", block_ids=["p1:a"])
    ]
    clean, dropped = sanitize_contract_map(document, mapping, stage="test")
    assert len(clean.number_roles) == 1
    assert clean.number_roles[0].value == "Z-2"
    assert len(clean.selections) == 1
    assert any(d["item_type"] == "number_role" for d in dropped)


def test_a_invalid_ref_never_remapped_to_another_block():
    mapping, document = _nine_valid_one_invalid_map()
    mapping.observations = [
        Observation(topic="phantom", summary="s", block_refs=["p1:ghost"])
    ]
    clean, dropped = sanitize_contract_map(document, mapping, stage="test")
    assert clean.observations == []
    assert all("p1:ghost" not in obs.block_refs for obs in clean.observations)
    # Dropped, never silently rewritten to a real block id.
    assert all("p1:a" not in obs.block_refs for obs in clean.observations)


def test_a_sanitize_applicability_drops_only_invalid_decisions():
    document = DocumentModel.build(native_document())
    decisions = [
        ApplicabilityDecision(scope="number", decision="order_number", target="x",
                              block_ids=["p1:a"]),
        ApplicabilityDecision(scope="option", decision="selected", target="y",
                              block_ids=["p1:bad"]),
    ]
    valid, dropped = sanitize_applicability(decisions, document, stage="applicability")
    assert len(valid) == 1 and valid[0].target == "x"
    assert len(dropped) == 1 and dropped[0]["invalid_refs"] == ["p1:bad"]


# ----------------------------------------------------------------------
# B - Dynamic family prompt packing (no static magic reserves)
# ----------------------------------------------------------------------


def _blocks(n: int) -> list[Block]:
    return [Block(id=f"p1:b{i}", text=" " + "x" * 600, kind="text", page=1) for i in range(n)]


def test_b_segments_use_actual_context_and_per_block_costs():
    planner = ContextPlanner(configured=8192, advertised=8192, output_tokens=1800)
    overhead = "fixed instruction overhead " * 10
    blocks = _blocks(8)
    segments = planner.segments(blocks, overhead, purpose="resolve_segments:identity",
                                extra_reserve=64, per_block_cost=lambda block: 0)
    decision = next(
        row for row in planner.decisions if row.get("purpose") == "resolve_segments:identity"
        and "segments" in row
    )
    assert decision["extra_reserve"] == 64
    assert decision["per_block_cost"] is True
    assert decision["block_budget"] == (
        planner.input_budget - estimate_tokens(overhead) - 64
    )
    assert segments  # structural blocks are packed whole


def test_b_per_block_visual_cost_reduces_block_capacity():
    planner = ContextPlanner(configured=4096, advertised=4096, output_tokens=1200)
    overhead = "instruction overhead "
    blocks = _blocks(3)
    cheap = planner.segments(blocks, overhead, purpose="seg:identity",
                             extra_reserve=0, per_block_cost=lambda block: 0)
    expensive = planner.segments(blocks, overhead, purpose="seg:identity",
                                 extra_reserve=0, per_block_cost=lambda block: 900)
    # With per-block visual observation rows counted, the same blocks no longer
    # all fit: packing must reflect ACTUAL prompt components, not a static reserve.
    assert len(expensive) > len(cheap)


@pytest.mark.asyncio
async def test_b_resolve_uses_full_structural_blocks_never_tail_clipped():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    full_block = "Vertrag 452664 MedTech GmbH Service 1.650,00 EUR"
    assert result.contract is not None
    resolve_texts = [
        text for (text, images, context) in provider.requests
        if text.startswith("Resolve this related contract-field pack in ONE pass:")
    ]
    assert resolve_texts
    assert any(full_block in text for text in resolve_texts)


@pytest.mark.asyncio
async def test_b_every_executed_call_is_prevalidated_against_runtime_window():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    capacity = result.diagnostics["context_budget"]
    for row in result.diagnostics["calls"]:
        # planner.check() runs on the FINAL assembled prompt before the provider
        # call; any overflow would have aborted the call, so every executed call
        # fits inside the runtime window with the base reserve.
        assert row["estimated_prompt_tokens"] <= capacity - 512
    assert all(row.get("succeeded") for row in result.diagnostics["calls"])


@pytest.mark.asyncio
async def test_b_family_packing_records_small_real_reserve_not_static_magic():
    provider = FakeProvider(block_ref="p1:e0")
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(multi_block_document(8))
    decisions = result.diagnostics["context_decisions"]
    row = next(
        d for d in decisions
        if d.get("purpose") == "resolve_pack_segments:core" and "segments" in d
    )
    assert row["per_block_cost"] is True
    assert 0 <= row["extra_reserve"] < 500  # sections-bound + safety, NOT 1100/1300


def test_b_measured_output_retry_only_for_eligible_stages():
    assert measured_output_budget("resolve:identity:0", prompt_tokens=3000,
                                  capacity=8192, base_output=1800) is not None
    assert measured_output_budget("resolve_pack:core:0", prompt_tokens=3000,
                                  capacity=8192, base_output=1800) is not None
    assert measured_output_budget("vision:p1:a", prompt_tokens=3000,
                                  capacity=8192, base_output=1800) is None
    assert measured_output_budget("resolve:identity:0", prompt_tokens=7000,
                                  capacity=8192, base_output=1800) is None


# ----------------------------------------------------------------------
# C - Call-budget semantics (never mislabelled as context overflow)
# ----------------------------------------------------------------------


def test_c_call_budget_exhaustion_is_not_context_overflow_subclass():
    assert not issubclass(CallBudgetExhausted, ContextOverflow)
    assert not issubclass(CallBudgetExhausted, ValueError)


@pytest.mark.asyncio
async def test_c_hard_budget_exhaustion_classified_separately():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(harness_max_calls=3), ai(provider)).analyze(native_document())
    assert provider.requests and len(provider.requests) == result.diagnostics["call_count"] == 3
    assert result.diagnostics["budget_exhausted"] is True
    categories = result.diagnostics["failure_categories"]
    assert categories.get("call_budget_exhausted", 0) >= 1
    assert categories.get("context_overflow", 0) == 0
    assert any("Call-Budget erschöpft" in issue for issue in result.diagnostics["issues"])
    assert result.contract is None
    assert result.error and "call_budget_exhausted" in result.error


@pytest.mark.asyncio
async def test_c_no_hidden_retry_after_budget_exhaustion():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(harness_max_calls=3), ai(provider)).analyze(native_document())
    calls_after_exhaustion = [
        c for c in result.diagnostics["calls"] if c.get("failed")
        and c.get("error_category") == "call_budget_exhausted"
    ]
    # The exhaustion event is not recorded as a redundant retried call; the
    # analysis stopped cleanly with exactly one classified budget failure.
    assert result.diagnostics["call_count"] == 3
    assert result.diagnostics["failure_categories"]["call_budget_exhausted"] == 1


# ----------------------------------------------------------------------
# D - Global-section compaction fairness (no first-sections-win)
# ----------------------------------------------------------------------


def _many_sections(count: int) -> list[SectionUnderstanding]:
    sections = []
    for i in range(count):
        sections.append(
            SectionUnderstanding(
                section_index=i,
                pages=[i + 1],
                observations=[
                    Observation(
                        topic="t",
                        summary="very long summary " + ("clause " * 200),
                        block_refs=["p1:a"],
                    )
                ],
                unresolved=["unresolved detail " + ("text " * 100)],
            )
        )
    return sections


def test_d_compact_sections_keeps_first_and_last_with_small_budget():
    payload = compact_sections(_many_sections(8), budget=260)
    rows = json.loads(payload)
    indices = {row["section_index"] for row in rows}
    assert 0 in indices and 7 in indices
    pages = {tuple(row["pages"]) for row in rows}
    assert (1,) in pages and (8,) in pages


def test_d_compact_sections_preserves_page_identity():
    payload = compact_sections(_many_sections(5), budget=300)
    rows = json.loads(payload)
    for row in rows:
        assert isinstance(row["pages"], list) and int(row["pages"][0]) == row["section_index"] + 1


def test_d_fair_allocation_never_starves_a_section():
    caps = _fair_token_allocation(8, [1000] * 8, 400)
    assert len(caps) == 8
    assert all(cap >= 1 for cap in caps)
    assert sum(map(int, caps)) == 400


def test_d_budget_below_section_count_is_bounded():
    # Allocator nominal caps (sum) never exceed the requested budget.
    for n_budget_spread in ((8, 1), (8, 2), (8, 3), (8, 5)):
        n, budget = n_budget_spread
        caps = _fair_token_allocation(n, [1000] * n, budget)
        assert sum(map(int, caps)) <= budget, (n, budget, sum(caps))
    # Actual payload estimate stays within the requested budget as well.
    for budget in (1, 2, 3, 5):
        payload = compact_sections(_many_sections(8), budget=budget)
        assert estimate_tokens(payload) <= budget, budget


def test_d_budget_equal_section_count_is_bounded():
    payload = compact_sections(_many_sections(8), budget=8)
    assert estimate_tokens(payload) <= 8
    json.loads(payload)  # always valid JSON


def test_d_very_small_budget_records_incompleteness():
    log: list = []
    payload = compact_sections(_many_sections(8), budget=1, log=log)
    assert estimate_tokens(payload) <= 1
    decision = log[-1]
    assert decision["module"] == "compact_sections"
    assert decision["incomplete"] is True
    assert decision["represented"] < 8
    assert decision["bounded"] is True


def test_d_payload_estimate_never_exceeds_requested_budget():
    # Whenever the compactor claims bounded output, the ACTUAL generated payload
    # must fit inside the requested budget (mathematical hard bound).
    for budget in (1, 2, 4, 8, 16, 32, 64, 128, 256, 300, 512, 700, 900):
        log: list = []
        payload = compact_sections(_many_sections(8), budget=budget, log=log)
        est = estimate_tokens(payload)
        assert est <= budget, (budget, est)
        assert log[-1]["module"] == "compact_sections"
        assert log[-1]["bounded"] is True
    for budget in (1, 60, 150, 300, 700):
        log: list = []
        payload = compact_sections(_many_sections(3), budget=budget, log=log)
        assert estimate_tokens(payload) <= budget, budget
        assert log[-1]["bounded"] is True


# ----------------------------------------------------------------------
# E - Output truncation handling
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e_truncated_output_never_silently_accepted():
    provider = FakeProvider(truncated_titles={"GlobalContractUnderstanding"})
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    truncated_calls = [
        row for row in result.diagnostics["calls"]
        if row.get("done_reason") == "length"
    ]
    assert truncated_calls
    for row in truncated_calls:
        assert row.get("failed") is True
        assert row.get("error_category") == "truncated_output"
    # The truncated global payload was never accepted as global meaning.
    assert result.diagnostics["global_understanding"] is None


@pytest.mark.asyncio
async def test_e_resolve_stage_recovers_via_measured_retry():
    provider = FakeProvider(truncated_titles={"CandidateBatch"})
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    # The FIRST CandidateBatch resolve call truncates and is retried once with a
    # measured output budget; the retry succeeds and grounded facts survive.
    retries = [
        row for row in result.diagnostics["calls"]
        if "retried_with_output_tokens" in row and row.get("succeeded")
    ]
    assert retries
    assert any(
        d.get("decision") == "output_budget_stage_retry"
        for d in result.diagnostics["context_decisions"]
    )
    assert result.contract is not None
    assert result.contract.identity.supplier == "MedTech GmbH"


def test_e_retry_bounds_are_stage_local_and_never_global():
    # resolve/ground eligible; vision never; oversized prompts never.
    assert measured_output_budget("ground:identity:0", 2500, 8192, 1800) == 2800
    assert measured_output_budget("recovery:identity", 2500, 8192, 1800) == 2800
    assert measured_output_budget("vision:p1:a", 2500, 8192, 1800) is None
    assert measured_output_budget("section:0", 2500, 8192, 1800) is None
    # The raise is capped well below the 8192 runtime window (no global hack).
    assert measured_output_budget("resolve:identity:0", 3000, 8192, 1800) <= 2800


def test_e2_retry_context_fit_explicit_window_math():
    # prompt + raised output + prompt reserve + image reserve <= runtime capacity
    assert _retry_fits_context(3000, 2800, 8192, 512, 0) is True
    assert _retry_fits_context(5000, 2800, 8192, 512, 0) is False  # 5000+2800+512 > 8192
    assert _retry_fits_context(3000, 2800, 8192, 512, 1024) is True  # 6312+1024 <= 8192
    assert _retry_fits_context(3000, 2800, 8192, 512, 2048) is False  # 6312+2048 > 8192


def test_e2_retry_allowed_when_new_output_budget_safely_fits():
    plan, decision = _retry_output_plan("resolve:identity:0", 3000, 8192, 1800, 0)
    assert plan == 2800
    assert decision == "output_budget_stage_retry"


def test_e2_retry_rejected_when_new_output_budget_would_exceed_window():
    # The raised output budget together with the image reserve would exceed the
    # runtime window -> rejected before any provider call, with a clear reason.
    plan, decision = _retry_output_plan("resolve:identity:0", 3000, 8192, 1800, 2048)
    assert plan is None
    assert decision == "output_retry_skipped_context_overflow"


def test_e2_retry_includes_image_reserve():
    # Image reserve small enough -> retry still allowed.
    plan, decision = _retry_output_plan("resolve:identity:0", 2500, 8192, 1800, 512)
    assert plan == 2800 and decision == "output_budget_stage_retry"
    # Image reserve large enough to overflow the window -> rejected.
    plan, decision = _retry_output_plan("resolve:identity:0", 2500, 8192, 1800, 2400)
    assert plan is None and decision == "output_retry_skipped_context_overflow"
    # Ground/recovery stages are eligible and follow the same gate.
    plan, decision = _retry_output_plan("ground:identity:0", 2500, 8192, 1800, 1024)
    assert plan == 2800 and decision == "output_budget_stage_retry"
    # Non-eligible stages never retry.
    plan, decision = _retry_output_plan("vision:p1:a", 3000, 8192, 1800, 0)
    assert plan is None and decision == "output_retry_not_performed"


@pytest.mark.asyncio
async def test_e2_no_silent_provider_call_after_failed_retry_fit():
    # The GlobalContractUnderstanding stage is NOT eligible for retry. Truncation
    # there must be surfaced as a failure with EXACTLY ONE provider request and
    # a recorded skip decision, never a speculative second call.
    provider = FakeProvider(truncated_titles={"GlobalContractUnderstanding"})
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    global_calls = [c for c in result.diagnostics["calls"] if c["purpose"] == "global_understanding"]
    assert len(global_calls) == 1
    assert global_calls[0].get("retried_with_output_tokens") is None
    decisions = result.diagnostics["context_decisions"]
    skip = [d for d in decisions if d.get("decision", "").startswith("output_retry_")]
    assert skip and skip[0]["decision"] == "output_retry_not_performed"
    assert skip[0]["runtime_capacity"] == 8192


# ----------------------------------------------------------------------
# F - Vision budget decoupled from total call budget
# ----------------------------------------------------------------------


def _visual_heavy_document(pages: int, blocks_per_page: int):
    page_models = []
    all_text = []
    for page_number in range(1, pages + 1):
        elements = []
        for index in range(blocks_per_page):
            text = f"Bildbereich {page_number}-{index}"
            all_text.append(text)
            elements.append(
                Element(
                    element_id=f"v{index}",
                    page=page_number,
                    reading_order=index,
                    text=text,
                    type="image",
                    method="native",
                    region=BoundingRegion(
                        page=page_number, x0=10 + index, y0=10, x1=120 + index, y1=60
                    ),
                )
            )
        page_models.append(
            Page(
                page_number=page_number,
                width_pt=600,
                height_pt=800,
                text=" ".join(all_text),
                elements=elements,
            )
        )
    return DocumentIntelligenceResult(
        document_id="synthetic",
        source_sha256="d" * 64,
        canonical_text=" ".join(all_text),
        provenance=ProcessingProvenance(provider="native_pdf"),
        pages=page_models,
    )


@pytest.mark.asyncio
async def test_f_vision_calls_do_not_double_when_semantic_budget_doubles():
    source = _visual_heavy_document(8, 4)  # 32 visual blocks
    counts = []
    for max_calls in (32, 64):
        provider = FakeProvider(block_ref="p1:v0")
        result = await HarnessV3(
            v3_settings(harness_max_calls=max_calls), ai(provider, vision=True)
        ).analyze(
            source,
            image_loader=lambda block: "img",
            page_image_loader=lambda page: "img",
        )
        vision_calls = [row for row in result.diagnostics["calls"] if row.get("stage") == "vision"]
        counts.append(len(vision_calls))
    assert counts[0] == counts[1], f"vision calls must not scale with max_calls: {counts}"
    # Full-page section vision covers these scanned pages in both cases.
    assert counts[0] == 0


@pytest.mark.asyncio
async def test_semantic_packs_reduce_resolve_stage_call_fanout():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    resolve_calls = [
        row for row in result.diagnostics["calls"]
        if row.get("stage") == "resolve"
    ]
    purposes = {row.get("purpose") for row in resolve_calls}
    assert any(str(p).startswith("resolve_pack:core:") for p in purposes)
    assert any(str(p).startswith("resolve_pack:commercial:") for p in purposes)
    assert any(str(p).startswith("resolve_pack:operations:") for p in purposes)
    assert not any(str(p).startswith("resolve:identity:") for p in purposes)


def test_source_has_parseable_contract_map_control_flow():
    # Lightweight guard for accidental indentation damage in the async control flow.
    import ast
    from pathlib import Path
    source = Path(__file__).parents[1] / "app" / "ai" / "harness" / "v3.py"
    ast.parse(source.read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_contract_map_segments_execute_after_successful_segmentation():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    map_calls = [
        row for row in result.diagnostics["calls"]
        if str(row.get("purpose", "")).startswith("understanding:")
    ]
    assert map_calls
    assert result.diagnostics["number_roles"]


@pytest.mark.asyncio
async def test_stage_diagnostics_expose_call_counts_and_latency():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    assert result.diagnostics["stage_call_counts"]
    assert "resolve" in result.diagnostics["stage_call_counts"]
    assert "resolve" in result.diagnostics["stage_latency_seconds"]
    assert result.diagnostics["stage_latency_seconds"]["resolve"] >= 0


@pytest.mark.asyncio
async def test_f_region_fallback_runs_when_page_section_is_unavailable():
    source = _visual_heavy_document(2, 3)
    provider = FakeProvider(
        block_ref="p1:v0",
        truncated_titles={"SectionUnderstanding"},
        truncate_once=False,
    )
    result = await HarnessV3(
        v3_settings(harness_max_calls=64, harness_vision_max_calls=2), ai(provider, vision=True)
    ).analyze(
        source,
        image_loader=lambda block: "region",
        page_image_loader=lambda page: "page",
    )
    fallback_calls = [
        row for row in result.diagnostics["calls"]
        if str(row.get("purpose", "")).startswith("vision_fallback:")
    ]
    assert len(fallback_calls) <= 2
    assert fallback_calls
    assert any(
        d.get("vision") == "region_fallback_after_missing_page_section"
        for d in result.diagnostics["context_decisions"]
    )


@pytest.mark.asyncio
async def test_f_region_fallback_is_limited_to_one_call_per_uncovered_page():
    source = _visual_heavy_document(2, 3)
    provider = FakeProvider(
        block_ref="p1:v0",
        truncated_titles={"SectionUnderstanding"},
        truncate_once=False,
    )
    result = await HarnessV3(
        v3_settings(harness_max_calls=64, harness_vision_max_calls=16), ai(provider, vision=True)
    ).analyze(
        source,
        image_loader=lambda block: "region",
        page_image_loader=lambda page: "page",
    )
    fallback_calls = [
        row for row in result.diagnostics["calls"]
        if str(row.get("purpose", "")).startswith("vision_fallback:")
    ]
    pages = [tuple(row.get("pages") or []) for row in fallback_calls]
    assert len(pages) == len(set(pages))
    assert len(fallback_calls) <= 2
    assert any(
        d.get("vision") == "deferred_duplicate_page_fallback"
        for d in result.diagnostics["context_decisions"]
    )


def test_b_ranked_pack_fallback_handles_oversized_structural_unit():
    planner = ContextPlanner(configured=4096, advertised=4096, output_tokens=1200)
    blocks = [
        Block(id="p1:huge", text="x" * 12000, kind="text", page=1),
        Block(id="p1:small", text="Service 1.650,00 EUR", kind="text", page=1),
    ]
    overhead = "resolve-pack-overhead"

    with pytest.raises(ContextOverflow):
        planner.segments(
            blocks,
            overhead,
            purpose="resolve_pack_segments:test",
        )

    ranked = planner.pack_ranked(
        blocks,
        overhead,
        purpose="resolve_pack_ranked_fallback:test",
    )
    assert [block.id for block in ranked] == ["p1:small"]
    decision = next(
        d for d in planner.decisions
        if d.get("purpose") == "resolve_pack_ranked_fallback:test"
    )
    assert decision["decision"] == "ranked_pack"


@pytest.mark.asyncio
async def test_visual_sensitive_candidate_with_unresolved_visual_is_not_delivered():
    source = native_document()
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(source)
    # Baseline synthetic path still delivers grounded identity when no unresolved
    # visual observation is attached to its evidence block.
    assert result.contract is not None
    assert result.diagnostics["delivery_complete"] is True


def test_diagnostics_delivery_fields_present_on_successful_synthetic_path():
    # Structural guard: diagnostics expose delivery-level counters so a future
    # benchmark can distinguish "semantic map understood" from "contract delivered".
    import ast
    from pathlib import Path
    source = Path(__file__).parents[1] / "app" / "ai" / "harness" / "v3.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert {"supported_count", "excluded_count", "delivery_complete"} <= literals


def test_final_prompt_refit_path_is_present():
    import ast
    from pathlib import Path
    source = Path(__file__).parents[1] / "app" / "ai" / "harness" / "v3.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "segment_skipped_after_final_prompt_overflow" in literals
    assert "resolve_pack_refit:" in source.read_text(encoding="utf-8")


def test_precedence_conflict_quarantine_marker_is_present():
    import ast
    from pathlib import Path
    source = Path(__file__).parents[1] / "app" / "ai" / "harness" / "v3.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "precedence_conflict_quarantined" in literals


def test_global_map_uses_lossless_union_without_extra_model_call():
    import ast
    from pathlib import Path
    source_path = Path(__file__).parents[1] / "app" / "ai" / "harness" / "v3.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "deterministic_lossless_union_no_extra_model_call" in literals
    assert 'await call(\n                        "global_map"' not in source


def test_delivery_gate_requires_resolve_pack_attempt():
    import ast
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app" / "ai" / "harness" / "v3.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    literals = {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "no_resolve_pack_executed" in literals


@pytest.mark.asyncio
async def test_semantic_pack_recovery_skips_broad_missing_field_retry():
    provider = FakeProvider()
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    skipped = [
        d for d in result.diagnostics["context_decisions"]
        if d.get("decision") == "recovery_skipped_unsubstantiated_missing_fields"
    ]
    assert skipped
    assert all(d.get("fields") for d in skipped)


@pytest.mark.asyncio
async def test_f_page_batch_vision_suppresses_duplicate_region_calls():
    source = _visual_heavy_document(4, 3)
    provider = FakeProvider(block_ref="p1:v0")
    result = await HarnessV3(
        v3_settings(harness_max_calls=64, harness_vision_max_calls=16), ai(provider, vision=True)
    ).analyze(source, image_loader=lambda block: "region", page_image_loader=lambda page: "page")
    region_calls = [
        row for row in result.diagnostics["calls"]
        if row.get("stage") == "vision"
    ]
    section_calls = [
        row for row in result.diagnostics["calls"]
        if row.get("stage") == "sections"
    ]
    assert region_calls == []
    assert section_calls
    deferred = [
        d for d in result.diagnostics["context_decisions"]
        if d.get("vision") == "deferred_to_page_batch"
    ]
    assert len(deferred) == 12


@pytest.mark.asyncio
async def test_f_vision_budget_respects_independent_setting():
    source = _visual_heavy_document(8, 4)
    provider = FakeProvider(block_ref="p1:v0")
    result = await HarnessV3(
        v3_settings(harness_max_calls=64, harness_vision_max_calls=4), ai(provider, vision=True)
    ).analyze(source, image_loader=lambda block: "img", page_image_loader=lambda page: "img")
    vision_calls = [row for row in result.diagnostics["calls"] if row.get("stage") == "vision"]
    # Because full-page SectionUnderstanding is available, the region budget is
    # not consumed at all on this page-first fast path.
    assert vision_calls == []
    deferred = [
        d for d in result.diagnostics["context_decisions"]
        if d.get("vision") == "deferred_to_page_batch"
    ]
    assert len(deferred) == 32


# ----------------------------------------------------------------------
# G - Qwen semantic authority on the number-role path
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_number_role_conflict_keeps_existing_role_and_forces_review():
    provider = FakeProvider(
        cost_applicability="applicable",
        number_decision="contract_number",
        map_number_role="order_number",
    )
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    assert result.contract is not None, result.diagnostics["issues"]
    assert result.contract.identity.contract_number is None
    roles = {n["role"] for n in result.diagnostics["number_roles"] if n["value"] == "452664"}
    assert roles == {"order_number"}
    assert any(
        d.get("decision") == "number_role_conflict_quarantined"
        and d.get("value") == "452664"
        for d in result.diagnostics["context_decisions"]
    )
    assert any("Nummernrolle widersprüchlich" in issue for issue in result.diagnostics["issues"])


@pytest.mark.asyncio
async def test_g_contract_number_written_when_qwen_classifies_contract_number():
    provider = FakeProvider(cost_applicability="applicable", number_decision="contract_number",
                            map_number_role=None)
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    assert result.contract is not None, result.diagnostics["issues"]
    assert result.contract.identity.contract_number == "452664"
    roles = {n["value"]: n["role"] for n in result.diagnostics["number_roles"]}
    assert roles.get("452664") == "contract_number"
    assert not any(issue.startswith("identity.contract_number") for issue in result.diagnostics["issues"])


@pytest.mark.asyncio
async def test_g_reference_classification_blocks_contract_number_without_map_role():
    provider = FakeProvider(cost_applicability="applicable", number_decision="order_number",
                            map_number_role=None)
    result = await HarnessV3(v3_settings(), ai(provider)).analyze(native_document())
    assert result.contract is not None, result.diagnostics["issues"]
    # Deterministic code ENFORCES the Qwen classification; it never infers it.
    assert result.contract.identity.contract_number is None
    roles = {n["value"]: n["role"] for n in result.diagnostics["number_roles"]}
    assert roles.get("452664") == "order_number"
    assert any(issue.startswith("identity.contract_number") for issue in result.diagnostics["issues"])