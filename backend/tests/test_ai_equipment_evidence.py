"""Regression tests for equipment-scoped source evidence in GroupPipeline."""

from app.ai.groups.extractor import GroupPipeline
from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.models.contract import Contract, Equipment
from app.models.evidence import SourceEvidence


def _pipeline() -> GroupPipeline:
    return GroupPipeline.__new__(GroupPipeline)


def _unit(text: str, index: int = 1) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.PARAGRAPH, index=index, text=text)


def test_equipment_identity_without_item_evidence_fails_closed():
    contract = Contract(equipment=[Equipment(device_name="Accutron MR")])
    issues = _pipeline()._verify_evidence_on_contract(
        contract, [_unit("Servicevereinbarung für Accutron MR")]
    )
    assert any("Equipment[0]" in issue and "ohne eigenen Nachweis" in issue for issue in issues)


def test_equipment_item_evidence_is_verified_against_source_unit():
    contract = Contract(
        equipment=[
            Equipment(
                device_name="Accutron MR",
                evidence=SourceEvidence(
                    source_type="paragraph",
                    paragraph_index=1,
                    source_text="Servicevereinbarung für Accutron MR",
                ),
            )
        ]
    )
    issues = _pipeline()._verify_evidence_on_contract(
        contract, [_unit("Servicevereinbarung für Accutron MR")]
    )
    assert not issues
    assert contract.equipment[0].evidence is not None
    assert contract.equipment[0].evidence.requires_review is False


def test_equipment_item_evidence_wrong_excerpt_is_review_required():
    contract = Contract(
        equipment=[
            Equipment(
                serial_number="SN-123",
                evidence=SourceEvidence(
                    source_type="paragraph",
                    paragraph_index=1,
                    source_text="Seriennummer SN-999",
                ),
            )
        ]
    )
    issues = _pipeline()._verify_evidence_on_contract(
        contract, [_unit("Seriennummer SN-123")]
    )
    assert any("source_text nicht" in issue for issue in issues)
    assert contract.equipment[0].evidence is not None
    assert contract.equipment[0].evidence.requires_review is True


def test_equipment_review_scan_includes_item_evidence():
    contract = Contract(
        equipment=[
            Equipment(
                device_name="Accutron MR",
                evidence=SourceEvidence(source_text="Accutron MR", requires_review=True),
            )
        ]
    )
    issues = _pipeline()._scan_evidence_review(contract)
    assert any(issue.startswith("Equipment[0]") for issue in issues)
