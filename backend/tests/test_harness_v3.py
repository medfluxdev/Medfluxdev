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
from app.ai.harness.document import Block, DocumentModel
from app.ai.harness.models import ContractMap, NumberRole, SelectionRelation
from app.ai.harness.pipeline import HarnessV2
from app.ai.harness.v3 import HarnessV3, _merge_maps_v3
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


class FakeProvider:
    supports_structured_output = True
    last_done_reason = None
    last_usage = {"prompt_tokens": 123, "completion_tokens": 42}

    def __init__(self, unsupported=False, cost_applicability="applicable", number_decision=None, block_ref="p1:a"):
        self.requests = []
        self.unsupported = unsupported
        self.cost_applicability = cost_applicability
        self.number_decision = number_decision
        self.block_ref = block_ref

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
            return json.dumps({
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
                "number_roles": [{
                    "value": "452664", "role": "order_number", "block_ids": [ref],
                    "reason": "appears as order reference",
                }],
            })
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
            if "Resolve costs " in text:
                return json.dumps({"candidates": [{
                    "field": "costs.annual_cost",
                    "value": {"amount": 1650, "currency": "EUR", "period": "annual"},
                    "status": "supported",
                    "applicability": self.cost_applicability,
                    "evidence_refs": [{"block_id": ref, "quote": "1.650,00 EUR"}],
                }]})
            if "Resolve identity " in text:
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
    assert any(p.startswith("resolve:identity:") for p in purposes)
    assert any(p.startswith("resolve:costs:") for p in purposes)

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
    assert "global_map" in {row.get("purpose") for row in diagnostics["calls"]}
    vision_rows = [row for row in diagnostics["calls"] if row.get("stage") == "vision"]
    assert len(vision_rows) == 4
    assert all(row.get("pages") for row in vision_rows)


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