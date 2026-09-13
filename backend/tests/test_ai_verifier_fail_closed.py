"""Fail-closed regression coverage for semantic verifier decisions.

Sensitive fields rejected by the verifier must always force manual review,
including when there is no section-level SourceEvidence object. This protects
field-scoped evidence routing from becoming a silent verification failure.
"""

from __future__ import annotations

import httpx
import pytest

from app.ai.contract_extractor import StructuredContractExtractor
from app.ai.groups.extractor import GroupPipeline
from app.ai.groups.verifier import SensitiveVerificationResult, VerificationDecision
from app.ai.service import AIService
from app.core.config import Settings
from app.documents.extraction.schemas import ExtractionUnit, SourceType, UnitMethod
from app.models.contract import Contract
from app.models.enums import ExtractionStatus, ReviewStatus
from app.models.evidence import SourceEvidence

from tests.helpers_group import build_handler


settings = Settings(_env_file=None)


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
    assert result.verifier_issues == 1
    assert result.contract is not None
    assert "identity.contract_number" in (result.contract.review.risk_notes or "")
