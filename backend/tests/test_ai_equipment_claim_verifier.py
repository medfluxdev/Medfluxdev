"""DB-free tests for deterministic equipment field verification."""

from datetime import date

from app.ai.groups.equipment_verifier import verify_equipment_claims
from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.models.contract import Contract, Equipment
from app.models.evidence import SourceEvidence
from app.models.values import FlexibleDate


def _unit(text: str, index: int = 1) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.PARAGRAPH, index=index, text=text)


def test_serial_number_requires_serial_label_not_bare_number():
    contract = Contract(
        equipment=[
            Equipment(
                device_name="Accutron MR",
                serial_number="SN-123",
                evidence=SourceEvidence(source_text="Accutron MR SN-123"),
            )
        ]
    )
    issues = verify_equipment_claims(contract, [_unit("Accutron MR SN-123")])
    assert any("serial_number" in issue for issue in issues)
    assert contract.equipment[0].evidence.requires_review is True


def test_serial_number_with_label_is_supported():
    contract = Contract(
        equipment=[
            Equipment(
                device_name="Accutron MR",
                serial_number="SN-123",
                evidence=SourceEvidence(source_text="Accutron MR Seriennummer SN-123"),
            )
        ]
    )
    issues = verify_equipment_claims(
        contract, [_unit("Gerät Accutron MR, Seriennummer SN-123")]
    )
    assert issues == []


def test_inventory_number_cannot_be_mistaken_for_serial_number():
    contract = Contract(
        equipment=[
            Equipment(
                inventory_number="INV-9",
                evidence=SourceEvidence(source_text="Seriennummer INV-9"),
            )
        ]
    )
    issues = verify_equipment_claims(contract, [_unit("Seriennummer INV-9")])
    assert any("inventory_number" in issue for issue in issues)


def test_coverage_date_requires_coverage_semantics():
    contract = Contract(
        equipment=[
            Equipment(
                device_name="Accutron MR",
                coverage_start=FlexibleDate(date=date(2026, 1, 1)),
                evidence=SourceEvidence(source_text="Accutron MR 01.01.2026"),
            )
        ]
    )
    issues = verify_equipment_claims(
        contract, [_unit("Accutron MR gefertigt am 01.01.2026")]
    )
    assert any("coverage_start" in issue for issue in issues)

    issues = verify_equipment_claims(
        contract, [_unit("Accutron MR Abdeckung ab 01.01.2026")]
    )
    assert not any("coverage_start" in issue for issue in issues)
