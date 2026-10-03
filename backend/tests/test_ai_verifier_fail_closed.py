"""Fail-closed regression coverage for semantic verifier decisions.

Sensitive fields rejected by the verifier must always force manual review,
including when there is no section-level SourceEvidence object. This protects
field-scoped evidence routing from becoming a silent verification failure.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.ai.contract_extractor import StructuredContractExtractor
from app.ai.groups.extractor import GroupPipeline
from app.ai.groups.verifier import (
    VERIFIER_SYSTEM_PROMPT,
    SensitiveVerificationResult,
    VerificationDecision,
)
from app.ai.service import AIService
from app.core.config import Settings
from app.database.ai_selection import set_ai_selection, set_setting
from app.documents.extraction.schemas import ExtractionUnit, SourceType, UnitMethod
from app.models.contract import Contract
from app.models.enums import ExtractionStatus, ReviewStatus
from app.models.evidence import SourceEvidence

from tests.helpers_group import build_handler, chat_reply


settings = Settings(_env_file=None)


@pytest.fixture(autouse=True)
def _explicit_model_selection_for_mocked_ai():
    set_ai_selection("ollama", "qwen3:8b-test")
    yield
    for key in ("ai_provider", "ai_model", "ai_provider_endpoint"):
        set_setting(key, None)


def _pipeline() -> GroupPipeline:
    # _apply_verifier/_finalize are deterministic and do not call the AI service.
    return GroupPipeline(None, settings)  # type: ignore[arg-type]


def test_unsupported_field_without_section_evidence_forces_manual_review():
    contract = Contract()
    contract.identity.contract_number = "WM-123"
    assert contract.identity.evidence is None

    result = SensitiveVerificationResult(
        decisions=[
            VerificationDecision(
                field="identity.contract_number",
                supported=False,
                reason="Nummer ist im Beleg nicht als Vertragsnummer ausgewiesen",
            )
        ]
    )

    pipeline = _pipeline()
    issues = pipeline._apply_verifier(contract, result)

    assert len(issues) == 1
    assert "identity.contract_number" in issues[0]
    assert "nicht gestützt" in issues[0]

    pipeline._finalize(contract, issues)
    assert contract.review.requires_manual_review is True
    assert contract.review.review_status == ReviewStatus.NEEDS_REVIEW
    assert "identity.contract_number" in (contract.review.risk_notes or "")


def test_unsupported_field_downgrades_existing_section_evidence():
    contract = Contract()
    contract.dates.evidence = SourceEvidence(
        source_text="Mindestvertragslaufzeit 2 Jahre",
        confidence=0.95,
        requires_review=False,
    )
    result = SensitiveVerificationResult(
        decisions=[
            VerificationDecision(
                field="dates.minimum_duration",
                supported=False,
                reason="Wert nicht eindeutig belegt",
            )
        ]
    )

    issues = _pipeline()._apply_verifier(contract, result)

    assert len(issues) == 1
    assert contract.dates.evidence.requires_review is True
    assert contract.dates.evidence.confidence == 0.5


@pytest.mark.asyncio
async def test_extraction_counts_only_unsupported_verifier_decisions_as_issues():
    contract_payload = {
        "identity": {
            "contract_title": "Wartungsvertrag",
            "contract_number": "WM-123",
        },
        "equipment": [],
        "dates": {},
        "termination": {},
        "costs": {},
        "payment": {},
        "services": {},
        "sla": {},
    }
    decisions = [
        {
            "field": "identity.contract_number",
            "supported": False,
            "reason": "nicht als Vertragsnummer belegt",
        }
    ]
    handler = build_handler(contract_payload, verifier_decisions=decisions)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ai = AIService(settings, client=client)
    extractor = StructuredContractExtractor(ai, settings, max_retries=0)

    unit = ExtractionUnit(
        source_type=SourceType.PAGE,
        index=1,
        text="Wartungsvertrag Bestellnummer WM-123",
        method=UnitMethod.TEXT,
    )
    result = await extractor.extract([unit])
    await client.aclose()

    assert result.status == ExtractionStatus.PARTIAL
    assert result.requires_review is True
    # Source grounding rejects the Bestellnummer before semantic verification,
    # so the result is fail-closed through normalization rather than an LLM
    # verifier decision.
    assert result.verifier_issues == 0
    assert result.normalization_issues >= 1
    assert result.contract is not None
    assert "identity.contract_number" in (result.contract.review.risk_notes or "")


@pytest.mark.asyncio
async def test_verifier_invalid_response_fails_closed_instead_of_success():
    contract_payload = {
        "identity": {
            "contract_title": "Wartungsvertrag",
            "contract_number": "WM-123",
        },
        "equipment": [],
        "dates": {},
        "termination": {},
        "costs": {},
        "payment": {},
        "services": {},
        "sla": {},
    }
    base_handler = build_handler(contract_payload)

    def handler(req: httpx.Request) -> httpx.Response:
        payload = json.loads(req.content)
        system = payload["messages"][0]["content"]
        if VERIFIER_SYSTEM_PROMPT.strip()[:60] in system:
            return chat_reply(req, "this-is-not-json")
        return base_handler(req)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ai = AIService(settings, client=client)
    extractor = StructuredContractExtractor(ai, settings, max_retries=0)
    unit = ExtractionUnit(
        source_type=SourceType.PAGE,
        index=1,
        text="Vertragsnummer WM-123",
        method=UnitMethod.TEXT,
    )

    result = await extractor.extract([unit])
    await client.aclose()

    assert result.status == ExtractionStatus.PARTIAL
    assert result.requires_review is True
    assert result.verifier_issues == 1
    assert result.contract is not None
    assert "keine verwertbare Entscheidung" in (result.contract.review.risk_notes or "")


def test_multi_chunk_group_merge_exposes_conflicts_instead_of_hiding_them():
    pipeline = _pipeline()
    spec = pipeline._specs["identity_equipment"]
    first = spec.model.model_validate(
        {"identity": {"supplier": "Supplier A"}, "equipment": []}
    )
    second = spec.model.model_validate(
        {"identity": {"supplier": "Supplier B"}, "equipment": []}
    )

    merged, conflicts = pipeline._merge_models(spec.model, [first, second])

    assert merged.identity.supplier == "Supplier A"
    assert conflicts
    assert any("supplier" in conflict for conflict in conflicts)
