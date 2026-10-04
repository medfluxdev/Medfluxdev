import json
from types import SimpleNamespace

import pytest

from app.ai.schemas import ModelCapabilities, ModelDescriptor
from app.core.config import Settings
from app.documents.intelligence.canonical import (
    DocumentIntelligenceResult,
    Element,
    Page,
    ProcessingProvenance,
)

# A literal that exists ONLY in the vision transcription - never in the OCR
# document text. The semantic model echoes this unverified image reading back
# as a contract fact.
VISION_ONLY_LITERAL = "Vierfachteil Sonder-Wartungspaket"


def settings(**overrides):
    base = {
        "harness_engine": "v3",
        "harness_max_calls": 16,
        "harness_output_tokens": 1800,
        "harness_context_tokens": 8192,
        "harness_vision_max_calls": 2,
        "visual_first_experiment_enabled": True,
        "visual_first_max_pages": 9,
        "visual_first_max_reviews": 0,
        "harness_vision_warmup_enabled": False,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def document(page3_text: str):
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
            page_number=2,
            width_pt=600,
            height_pt=800,
            text="Allgemeine Bedingungen und Servicezeiten.",
            elements=[
                Element(
                    element_id="p2",
                    page=2,
                    reading_order=0,
                    text="Allgemeine Bedingungen und Servicezeiten.",
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
        Page(
            page_number=3,
            width_pt=600,
            height_pt=800,
            text=page3_text,
            elements=[
                Element(
                    element_id="p3",
                    page=3,
                    reading_order=0,
                    text=page3_text,
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
    ]
    return DocumentIntelligenceResult(
        document_id="vision-fail-closed",
        source_sha256="c" * 64,
        canonical_text="\n".join(page.text for page in pages),
        provenance=ProcessingProvenance(provider="docling"),
        pages=pages,
    )


class EchoVisionProvider:
    """The vision model reads a literal that OCR never sees; the semantic model
    then echoes that unverified image text back as a confident contract fact."""

    supports_structured_output = True
    last_done_reason = None
    last_usage = {}

    async def generate_request(
        self, text, system, schema, max_tokens, context_tokens, images=None
    ):
        title = schema["title"]
        if title == "VisionClaims":
            if "Page=3." in text:
                return json.dumps(
                    {
                        "claims": [
                            {
                                "page": 3,
                                "label": "Leistung",
                                "value": VISION_ONLY_LITERAL,
                                "quote": VISION_ONLY_LITERAL,
                                "region": [10, 10, 20, 20],
                                "uncertain": False,
                            }
                        ]
                    }
                )
            return json.dumps({"claims": []})
        if title == "ProposedFactBatch":
            if "services.included_services" in text:
                return json.dumps(
                    {
                        "facts": [
                            {
                                "field": "services.included_services",
                                "value": [VISION_ONLY_LITERAL],
                                "page": 3,
                                "quote": VISION_ONLY_LITERAL,
                                "applicability": "applicable",
                                "confidence": 0.98,
                            }
                        ]
                    }
                )
            return json.dumps({"facts": []})
        raise AssertionError(f"Unexpected schema title {title}")


def ai(provider):
    async def runtime():
        return provider, ModelDescriptor(
            provider_id="mock",
            model_id="qwen3-vl:8b-instruct",
            context_length=8192,
            capabilities=ModelCapabilities(text=True, vision=True),
        )

    return SimpleNamespace(harness_runtime=runtime)


@pytest.mark.asyncio
async def test_unverified_vision_echo_cannot_become_trusted_contract_evidence():
    from app.ai.harness.v3 import HarnessV3

    # Page 3 OCR text contains NO trace of the literal; only the vision
    # transcription carries it (unverified image reading).
    result = await HarnessV3(settings(), ai=ai(EchoVisionProvider())).analyze(
        document("Allgemeine Bedingungen ohne Sonderleistungen."),
        original_page_loader=lambda p: "iVBORw0KGgo=",
    )
    assert result.contract is not None, result.error
    # The echo IS recorded (so the scenario is real) - but its evidence must be
    # permanently review-pinned, never trusted.
    accepted = [
        f for f in result.diagnostics["accepted_facts"]
        if f.get("field") == "services.included_services"
    ]
    assert accepted, result.diagnostics["accepted_facts"]
    harness = result.contract.analysis.harness
    evidence = [
        row for row in harness["evidence"]
        if row.get("field") == "services.included_services"
    ]
    assert evidence, "expected a recorded evidence row for the vision-echo fact"
    assert all(row["source"]["requires_review"] is True for row in evidence)
    assert all(row["source"]["page"] == 3 for row in evidence)
    # Fail-closed at ANALYSIS level: an unverified image reading fed back into
    # the semantic model must force the whole result into manual review.
    assert result.requires_review is True
    assert any(
        "Evidence requires manual review" in i
        for i in result.diagnostics["issues"]
    ), result.diagnostics["issues"]
    assert result.contract.review.review_reasons
    from app.models.enums import ExtractionStatus
    assert result.contract.analysis.extraction_status == ExtractionStatus.PARTIAL