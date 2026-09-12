"""PR-6 focused tests. No real model calls or imported contracts."""
import json
from types import SimpleNamespace

import pytest

from app.ai.harness.context import ContextOverflow, ContextPlanner, assemble
from app.ai.harness.document import DocumentModel
from app.ai.harness.models import CandidateBatch, ContractMap, EvidenceRef, FactCandidate
from app.ai.harness.pipeline import (
    HarnessV2, field_types, _coalesce_batch, candidate_schema, strict_value, TOPICS,
)
from app.ai.schemas import ModelCapabilities, ModelDescriptor
from app.core.config import Settings
from app.documents.intelligence.canonical import (
    DocumentIntelligenceResult, Element, LogicalUnit, Page, ProcessingProvenance,
)


def document(text="Vertrag Nr. TEST-42", visual=False):
    return DocumentIntelligenceResult(document_id="synthetic", source_sha256="a" * 64,
        canonical_text=text, provenance=ProcessingProvenance(provider="native_pdf"),
        pages=[Page(page_number=1, width_pt=600, height_pt=800, text=text, elements=[
            Element(element_id="a", page=1, reading_order=0, text=text,
                    type="checkbox" if visual else "paragraph", method="native")])])


class FakeProvider:
    supports_structured_output = True
    last_done_reason = None
    last_usage = {"prompt_tokens": 123, "completion_tokens": 42}

    def __init__(self, conflicting=False, unsupported=False):
        self.requests = []
        self.conflicting = conflicting
        self.unsupported = unsupported

    async def generate_request(self, text, system, schema, max_tokens, context_tokens, images=None):
        self.requests.append((text, images, context_tokens))
        title = schema["title"]
        if title == "ContractMap":
            return json.dumps({"document_type": "service", "observations": [
                {"topic": "identity dates costs termination equipment payment services sla",
                 "summary": "Service contract", "block_refs": ["p1:a"]}]})
        if title == "VisionObservation":
            return json.dumps({"description": "Checkbox region"})
        if title == "GroundingBatch":
            # The candidate batch is on its own line after the instructions.
            batch = json.loads(text.split("\n", 1)[1].split("\n[p1:a", 1)[0])
            return json.dumps({"decisions": [{"candidate_index": i, "supported": not self.unsupported,
                                              "explanation": "Source entails claim"}
                                             for i in range(len(batch["candidates"]))]})
        if title == "CandidateBatch":
            if "Resolve identity " in text:
                facts = [{"field": "identity.contract_number", "value": "TEST-42", "status": "supported",
                          "evidence_refs": [{"block_id": "p1:a", "quote": "TEST-42"}]}]
                if self.conflicting:
                    facts.append({**facts[0], "value": "OTHER"})
                return json.dumps({"candidates": facts})
            return '{"candidates": []}'
        raise AssertionError(title)


def ai(provider, vision=False):
    async def runtime():
        return provider, ModelDescriptor(provider_id="mock", model_id="selected", context_length=262144,
            capabilities=ModelCapabilities(text=True, vision=vision))
    return SimpleNamespace(harness_runtime=runtime)


def test_document_preserves_provenance_and_docx_addresses():
    source = document()
    model = DocumentModel.build(source)
    assert model.canonical is source
    assert model.blocks[0].element is source.pages[0].elements[0]
    source.pages = []
    source.logical_units = [LogicalUnit(source_type="paragraph", index=3, text="Clause")]
    model = DocumentModel.build(source)
    assert model.blocks[0].page is None
    assert model.blocks[0].id == "paragraph:3"


def test_budget_never_uses_advertised_capacity_as_safe_budget():
    planner = ContextPlanner(8192, 262144, 1800)
    assert planner.capacity == 8192
    blocks = DocumentModel.build(document("x" * 14000)).blocks
    with pytest.raises(ContextOverflow):
        planner.segments(blocks)
    assert planner.decisions[-1]["decision"] == "oversized_structural_unit"


def test_structure_segmentation_has_no_loss():
    from app.ai.harness.document import Block
    blocks = [Block(str(i), "clause " * 40, "paragraph", heading="Terms") for i in range(6)]
    segments = ContextPlanner(1500, None, 200).segments(blocks)
    assert len(segments) > 1
    assert [b.id for s in segments for b in s] == [b.id for b in blocks]
    assert all("heading=Terms" in assemble(s) for s in segments)


def test_map_and_candidate_schema():
    with pytest.raises(ValueError):
        ContractMap.model_validate({"invented_property": True})
    with pytest.raises(ValueError):
        FactCandidate(field="x", status="certain")


@pytest.mark.asyncio
async def test_pipeline_evidence_version_accounting_and_no_native_vision():
    provider = FakeProvider()
    result = await HarnessV2(Settings(_env_file=None), ai(provider)).analyze(document())
    assert result.contract.identity.contract_number == "TEST-42", result.contract.analysis.harness["issues"]
    meta = result.contract.analysis.harness
    assert result.contract.analysis.harness_version == "v2.1"
    assert meta["provider"] == "mock" and meta["model"] == "selected"
    assert meta["context_budget"] == 8192
    assert meta["call_count"] == len(provider.requests)
    assert all(images is None for _, images, _ in provider.requests)
    assert meta["evidence"][0]["source"]["page"] == 1
    assert meta["evidence"][0]["source"]["bounding_box"] is None
    assert len([c for c in meta["calls"] if c["purpose"] == "recovery:identity"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("conflicting,unsupported", [(True, False), (False, True)])
async def test_conflict_and_unsupported_abstain(conflicting, unsupported):
    provider = FakeProvider(conflicting, unsupported)
    result = await HarnessV2(Settings(_env_file=None), ai(provider)).analyze(document())
    assert result.contract is None
    assert result.requires_review
    assert result.validation_status.value == "unknown"




class FailingContractMapProvider(FakeProvider):
    """First understanding call fails as if Ollama truncated structured output."""

    async def generate_request(self, text, system, schema, max_tokens, context_tokens, images=None):
        if schema["title"] == "ContractMap":
            self.requests.append((text, images, context_tokens))
            self.last_done_reason = "length"
            self.last_usage = {"prompt_tokens": 500, "completion_tokens": max_tokens}
            raise ValueError("Model output exceeded budget")
        self.last_done_reason = None
        return await super().generate_request(
            text, system, schema, max_tokens, context_tokens, images
        )


@pytest.mark.asyncio
async def test_contract_map_failure_is_local_and_diagnostics_survive():
    provider = FailingContractMapProvider()
    result = await HarnessV2(Settings(_env_file=None), ai(provider)).analyze(document())

    # Global-map failure must not prevent deterministic lexical recall from
    # extracting a later evidence-grounded fact.
    assert result.contract is not None
    assert result.contract.identity.contract_number == "TEST-42"
    assert result.requires_review

    failed = [row for row in result.diagnostics["calls"] if row.get("failed")]
    assert failed
    assert failed[0]["purpose"] == "understanding:0"
    assert failed[0]["error_category"] == "truncated_output"
    assert failed[0]["done_reason"] == "length"


@pytest.mark.asyncio
async def test_no_grounded_truth_returns_unknown_with_durable_error_summary():
    provider = FakeProvider(unsupported=True)
    result = await HarnessV2(Settings(_env_file=None), ai(provider)).analyze(document())

    assert result.contract is None
    assert result.validation_status.value == "unknown"
    assert result.error.startswith("HarnessFailure")
    assert result.diagnostics["call_count"] == len(provider.requests)
    assert result.diagnostics["issues"]


@pytest.mark.asyncio
@pytest.mark.parametrize("capable", [True, False])
async def test_selective_vision_and_review(capable):
    provider = FakeProvider()
    result = await HarnessV2(Settings(_env_file=None), ai(provider, capable)).analyze(
        document(visual=True), image_loader=lambda _: "image")
    assert any(images for _, images, _ in provider.requests) is capable
    assert result.requires_review


@pytest.mark.asyncio
async def test_call_budget_is_hard_and_overflow_is_honest():
    provider = FakeProvider()
    result = await HarnessV2(Settings(_env_file=None, harness_max_calls=1), ai(provider)).analyze(document())
    assert len(provider.requests) == 1
    assert result.requires_review
    assert result.contract is None
    assert result.diagnostics["call_count"] == 1


def test_cost_schema_exposes_staged_and_variable_pricing():
    fields = field_types()
    assert "costs.scheduled_prices" in fields
    assert "costs.variable_charges" in fields


def test_staged_price_candidates_merge_across_segments_without_false_conflict():
    batch = CandidateBatch(candidates=[
        FactCandidate(
            field="costs.scheduled_prices", status="supported",
            normalized_value=[{"period_index": 1, "period_label": "1.Jahr", "amount": {"amount": 0, "currency": "EUR", "period": "annual"}, "condition": None}],
            evidence_refs=[EvidenceRef(block_id="p8:a", quote="1.Jahr 0 EUR")],
        ),
        FactCandidate(
            field="costs.scheduled_prices", status="supported",
            normalized_value=[{"period_index": 2, "period_label": "2.Jahr", "amount": {"amount": 8000, "currency": "EUR", "period": "annual"}, "condition": None}],
            evidence_refs=[EvidenceRef(block_id="p8:b", quote="2.Jahr 8.000,00 EUR")],
        ),
    ])
    merged = _coalesce_batch(batch)
    assert len(merged.candidates) == 1
    candidate = merged.candidates[0]
    assert candidate.status == "supported"
    assert [item["period_index"] for item in candidate.normalized_value] == [1, 2]
    assert len(candidate.evidence_refs) == 2


def test_same_schedule_period_with_different_amount_is_real_conflict():
    batch = CandidateBatch(candidates=[
        FactCandidate(
            field="costs.scheduled_prices", status="supported",
            normalized_value=[{"period_index": 2, "period_label": "2.Jahr", "amount": {"amount": 8000, "currency": "EUR", "period": "annual"}, "condition": None}],
            evidence_refs=[EvidenceRef(block_id="a", quote="8.000 EUR")],
        ),
        FactCandidate(
            field="costs.scheduled_prices", status="supported",
            normalized_value=[{"period_index": 2, "period_label": "2.Jahr", "amount": {"amount": 9000, "currency": "EUR", "period": "annual"}, "condition": None}],
            evidence_refs=[EvidenceRef(block_id="b", quote="9.000 EUR")],
        ),
    ])
    merged = _coalesce_batch(batch)
    assert merged.candidates[0].status == "conflicting"


@pytest.mark.parametrize("value", [None, "", "  ", [], {}, {"date": None, "condition": None}])
def test_supported_empty_values_are_rejected(value):
    with pytest.raises(ValueError, match="no value"):
        strict_value(str | None, value)
    batch = _coalesce_batch(CandidateBatch(candidates=[
        FactCandidate(field="identity.contract_number", status="supported", value=value),
    ]))
    assert batch.candidates[0].status == "unsupported"


def test_false_and_zero_are_valid_facts():
    assert strict_value(bool | None, False) is False
    assert strict_value(int | None, 0) == 0


def test_empty_candidate_does_not_conflict_with_supported_value():
    batch = _coalesce_batch(CandidateBatch(candidates=[
        FactCandidate(field="identity.contract_number", status="supported"),
        FactCandidate(field="identity.contract_number", status="supported", value="TEST-42"),
    ]))
    assert len(batch.candidates) == 1
    assert batch.candidates[0].status == "supported"
    assert batch.candidates[0].value == "TEST-42"


def test_native_schema_defines_json_values_and_requires_fact_payload():
    schema = candidate_schema()
    assert schema["$defs"]["JsonValue"]["anyOf"]
    assert {"value", "normalized_value", "evidence_refs"} <= set(
        schema["$defs"]["FactCandidate"]["required"]
    )


class EmptyValueProvider(FakeProvider):
    async def generate_request(self, text, system, schema, max_tokens, context_tokens, images=None):
        raw = await super().generate_request(text, system, schema, max_tokens, context_tokens, images)
        if schema["title"] == "CandidateBatch":
            payload = json.loads(raw)
            for candidate in payload["candidates"]:
                candidate.pop("value", None)
            return json.dumps(payload)
        return raw


@pytest.mark.asyncio
async def test_empty_supported_candidates_never_create_accepted_truth():
    result = await HarnessV2(Settings(_env_file=None), ai(EmptyValueProvider())).analyze(document())
    assert result.contract is None
    assert result.validation_status.value == "unknown"
    assert result.requires_review


class BudgetProvider(FakeProvider):
    async def generate_request(self, text, system, schema, max_tokens, context_tokens, images=None):
        self.requests.append((text, images, context_tokens))
        if schema["title"] == "ContractMap":
            return json.dumps({"observations": []})
        if schema["title"] == "GroundingBatch":
            batch, _ = json.JSONDecoder().raw_decode(text.split("\n", 1)[1])
            return json.dumps({"decisions": [
                {"candidate_index": index, "supported": True, "explanation": "Explicit source"}
                for index in range(len(batch["candidates"]))
            ]})
        return json.dumps({"candidates": [{
            "field": "identity.contract_number", "value": "TEST-42", "status": "supported",
            "evidence_refs": [{"block_id": "p1:a", "quote": "TEST-42"}],
        }]})


@pytest.mark.asyncio
async def test_long_document_reserves_calls_for_every_family():
    source = document()
    for page_number in range(2, 55):
        content = "Wartung Vertrag Beginn Ende Preis EUR Zahlung Leistung Reaktionszeit. " * 15
        source.pages.append(Page(
            page_number=page_number, width_pt=600, height_pt=800, text=content,
            elements=[Element(element_id=f"clause-{page_number}", page=page_number,
                              reading_order=0, text=content, type="paragraph", method="native")],
        ))
    provider = BudgetProvider()
    result = await HarnessV2(
        Settings(_env_file=None, harness_max_calls=20), ai(provider),
    ).analyze(source)
    purposes = [call["purpose"] for call in result.diagnostics["calls"]]
    assert len(provider.requests) <= 20
    for family in TOPICS:
        assert any(purpose.startswith(f"resolve:{family}:") for purpose in purposes), family
    assert any("CallBudgetExhausted" in issue for issue in result.diagnostics["issues"])
    assert not any("ContextOverflow" in issue for issue in result.diagnostics["issues"])
