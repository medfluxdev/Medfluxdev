import json
from types import SimpleNamespace

import pytest

from app.ai.harness import get_harness_class
from app.ai.harness.document import DocumentModel
from app.ai.harness.source_signals import collect_source_signals
from app.ai.harness.v3 import DirectContractHarness, HarnessV3
from app.ai.schemas import ModelCapabilities, ModelDescriptor
from app.core.config import Settings
from app.documents.intelligence.canonical import (
    DocumentIntelligenceResult,
    Element,
    Page,
    ProcessingProvenance,
)


def settings(**overrides):
    base = {
        "harness_engine": "v3",
        "harness_max_calls": 16,
        "harness_output_tokens": 1800,
        "harness_context_tokens": 8192,
        "harness_vision_max_calls": 2,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def document():
    pages = [
        Page(
            page_number=1,
            width_pt=600,
            height_pt=800,
            text="ABIOMED Europe GmbH Vertr.-Nr.: 40015645",
            elements=[
                Element(
                    element_id="p1",
                    page=1,
                    reading_order=0,
                    text="ABIOMED Europe GmbH Vertr.-Nr.: 40015645",
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
        Page(
            page_number=5,
            width_pt=600,
            height_pt=800,
            text=(
                "Der Vertrag beginnt am 01.04.2025 und endet am 31.03.2029. "
                "Die Laufzeit beträgt 4 Jahren. Der Vertrag wird nicht automatisch verlängert."
            ),
            elements=[
                Element(
                    element_id="p5",
                    page=5,
                    reading_order=0,
                    text=(
                        "Der Vertrag beginnt am 01.04.2025 und endet am 31.03.2029. "
                        "Die Laufzeit beträgt 4 Jahren. Der Vertrag wird nicht automatisch verlängert."
                    ),
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
        Page(
            page_number=8,
            width_pt=600,
            height_pt=800,
            text="Fixed per call: 2.226,00 EUR. 2.Jahr 8.000,00 EUR.",
            elements=[
                Element(
                    element_id="p8",
                    page=8,
                    reading_order=0,
                    text="Fixed per call: 2.226,00 EUR. 2.Jahr 8.000,00 EUR.",
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
    ]
    return DocumentIntelligenceResult(
        document_id="abiomed-test",
        source_sha256="a" * 64,
        canonical_text="\n".join(page.text for page in pages),
        provenance=ProcessingProvenance(provider="docling"),
        pages=pages,
    )


class FakeProvider:
    supports_structured_output = True
    last_done_reason = None
    last_response_sha256 = None

    async def generate_request(
        self, text, system, schema, max_tokens, context_tokens, images=None
    ):
        title = schema["title"]
        if title == "ProposedFactBatch":
            if "semantic:core" in text:
                raise AssertionError("purpose must not leak into prompt")
            if "identity.contract_number" in text:
                return json.dumps(
                    {
                        "facts": [
                            {
                                "field": "identity.supplier",
                                "value": "ABIOMED Europe GmbH",
                                "page": 1,
                                "quote": "ABIOMED Europe GmbH",
                                "applicability": "applicable",
                            },
                            {
                                "field": "identity.contract_number",
                                "value": "40015645",
                                "page": 1,
                                "quote": "Vertr.-Nr.: 40015645",
                                "applicability": "applicable",
                            },
                            {
                                "field": "dates.start_date",
                                "value": {
                                    "date": "2025-04-01",
                                    "condition": None,
                                    "requires_review": False,
                                },
                                "page": 5,
                                "quote": "beginnt am 01.04.2025",
                                "applicability": "applicable",
                            },
                            {
                                "field": "dates.end_date",
                                "value": {
                                    "date": "2029-03-31",
                                    "condition": None,
                                    "requires_review": False,
                                },
                                "page": 5,
                                "quote": "endet am 31.03.2029",
                                "applicability": "applicable",
                            },
                            {
                                "field": "dates.duration",
                                "value": {"value": 4, "unit": "years"},
                                "page": 5,
                                "quote": "Laufzeit beträgt 4 Jahren",
                                "applicability": "applicable",
                            },
                            {
                                "field": "termination.automatic_renewal",
                                "value": False,
                                "page": 5,
                                "quote": "nicht automatisch verlängert",
                                "applicability": "applicable",
                            },
                        ]
                    }
                )
            if "costs.annual_cost" in text:
                return json.dumps(
                    {
                        "facts": [
                            {
                                "field": "costs.annual_cost",
                                "value": {
                                    "amount": 8000,
                                    "currency": "EUR",
                                    "period": "annual",
                                },
                                "page": 8,
                                "quote": "8.000,00 EUR",
                                "applicability": "applicable",
                            },
                            {
                                "field": "costs.variable_charges",
                                "value": [
                                    {
                                        "label": "Fixed per call",
                                        "amount": {
                                            "amount": 2226,
                                            "currency": "EUR",
                                            "period": None,
                                        },
                                        "unit": "per_call",
                                        "condition": None,
                                    }
                                ],
                                "page": 8,
                                "quote": "Fixed per call: 2.226,00 EUR",
                                "applicability": "applicable",
                            },
                        ]
                    }
                )
            return '{"facts":[]}'
        if title == "VisualPageReading":
            return json.dumps({"page": 1, "visible_text": [], "unresolved": []})
        raise AssertionError(title)


def ai(provider=None):
    provider = provider or FakeProvider()

    async def runtime():
        return provider, ModelDescriptor(
            provider_id="mock",
            model_id="qwen3-vl:8b-instruct",
            context_length=8192,
            capabilities=ModelCapabilities(text=True, vision=True),
        )

    return SimpleNamespace(harness_runtime=runtime)


def test_engine_selection_uses_replacement_harness():
    assert get_harness_class(settings()) is HarnessV3
    assert issubclass(HarnessV3, DirectContractHarness)


def test_production_constructor_accepts_settings_only():
    harness = HarnessV3(settings())
    assert isinstance(harness, DirectContractHarness)
    assert harness.ai is not None


def test_source_signals_find_reference_values():
    rows = collect_source_signals(DocumentModel.build(document()))
    values = {row["value"] for row in rows}
    assert "40015645" in values
    assert "01.04.2025" in values
    assert "31.03.2029" in values
    assert "4 Jahren" in values
    assert "2.226,00 EUR" in values
    assert "8.000,00 EUR" in values


@pytest.mark.asyncio
async def test_direct_harness_delivers_grounded_contract_without_block_ids():
    result = await DirectContractHarness(settings(), ai()).analyze(document())

    assert result.contract is not None, result.error
    contract = result.contract
    assert contract.identity.supplier == "ABIOMED Europe GmbH"
    assert contract.identity.contract_number == "40015645"
    assert str(contract.dates.start_date.date) == "2025-04-01"
    assert str(contract.dates.end_date.date) == "2029-03-31"
    assert contract.dates.duration.value == 4
    assert contract.termination.automatic_renewal is False
    assert contract.costs.annual_cost.amount == 8000
    assert contract.costs.variable_charges[0].amount.amount == 2226
    assert result.diagnostics["supported_count"] >= 8
    assert result.diagnostics["evidence_count"] >= 8
    assert result.diagnostics["stage_call_counts"]["semantic"] == 3


@pytest.mark.asyncio
async def test_alternative_fact_never_projects():
    class AlternativeProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch" and "costs.annual_cost" in text:
                payload = json.loads(raw)
                for fact in payload["facts"]:
                    if fact["field"] == "costs.annual_cost":
                        fact["applicability"] = "alternative"
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(settings(), ai(AlternativeProvider())).analyze(
        document()
    )
    assert result.contract is not None
    assert result.contract.costs.annual_cost is None
    assert any(
        row["field"] == "costs.annual_cost"
        and row["reason"] == "applicability:alternative"
        for row in result.diagnostics["rejected_facts"]
    )


@pytest.mark.asyncio
async def test_quote_can_bind_by_literal_source_signal_when_model_quote_is_bad():
    class BadQuoteProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch" and "identity.contract_number" in text:
                payload = json.loads(raw)
                for fact in payload["facts"]:
                    if fact["field"] == "identity.contract_number":
                        fact["quote"] = "contract number 40015645"
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(settings(), ai(BadQuoteProvider())).analyze(
        document()
    )
    assert result.contract is not None
    assert result.contract.identity.contract_number == "40015645"
    accepted = {
        row["field"]: row for row in result.diagnostics["accepted_facts"]
    }
    assert accepted["identity.contract_number"]["page"] == 1


@pytest.mark.asyncio
async def test_missing_page_and_quote_are_auto_anchored_and_dates_normalized():
    class SparseEvidenceProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] != "ProposedFactBatch":
                return raw
            payload = json.loads(raw)
            for fact in payload["facts"]:
                if fact["field"] == "identity.supplier":
                    fact["page"] = None
                    fact["quote"] = ""
                if fact["field"] == "dates.start_date":
                    fact["value"] = "01.04.2025"
                    fact["page"] = None
                    fact["quote"] = ""
                if fact["field"] == "dates.end_date":
                    fact["value"] = "31.03.2029"
                    fact["page"] = None
                    fact["quote"] = ""
                if fact["field"] == "dates.duration":
                    fact["value"] = "4 Jahren"
                    fact["page"] = None
                    fact["quote"] = ""
                if fact["field"] == "costs.annual_cost":
                    fact["value"] = "8.000,00 EUR"
                    fact["page"] = None
                    fact["quote"] = ""
            return json.dumps(payload)

    result = await DirectContractHarness(
        settings(), ai(SparseEvidenceProvider())
    ).analyze(document())

    assert result.contract is not None, result.error
    assert result.contract.identity.supplier == "ABIOMED Europe GmbH"
    assert str(result.contract.dates.start_date.date) == "2025-04-01"
    assert str(result.contract.dates.end_date.date) == "2029-03-31"
    assert result.contract.dates.duration.value == 4
    assert result.contract.costs.annual_cost.amount == 8000
    normalized_fields = {
        row["field"] for row in result.diagnostics["normalizations"]
    }
    assert "dates.start_date" in normalized_fields
    assert "dates.end_date" in normalized_fields
    assert "dates.duration" in normalized_fields
    assert "costs.annual_cost" in normalized_fields
    accepted = {
        row["field"]: row for row in result.diagnostics["accepted_facts"]
    }
    assert accepted["identity.supplier"]["page"] == 1
    assert accepted["dates.start_date"]["page"] == 5
    assert accepted["dates.end_date"]["page"] == 5
    assert accepted["costs.annual_cost"]["page"] == 8


@pytest.mark.asyncio
async def test_known_time_value_drops_unknown_model_properties_before_validation():
    class ExtraSlaPropertyProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch" and "sla.service_hours" in text:
                payload = json.loads(raw)
                payload["facts"].append(
                    {
                        "field": "sla.service_hours",
                        "value": {
                            "value": 8,
                            "unit": "hours",
                            "original_text": "8 Stunden",
                            "unexpected": "discard me",
                        },
                        "page": None,
                        "quote": "",
                        "applicability": "applicable",
                    }
                )
                return json.dumps(payload)
            return raw

    # No source evidence for this synthetic SLA value, so it must still be
    # rejected by evidence rather than by schema shape.
    result = await DirectContractHarness(
        settings(), ai(ExtraSlaPropertyProvider())
    ).analyze(document())
    rows = [
        row for row in result.diagnostics["rejected_facts"]
        if row["field"] == "sla.service_hours"
    ]
    assert rows
    assert rows[0]["reason"] == "evidence_not_located"
