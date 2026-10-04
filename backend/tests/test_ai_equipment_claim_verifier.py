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


def test_same_serial_with_conflicting_models_is_never_silently_accepted():
    contract = Contract(
        equipment=[
            Equipment(
                device_name="Scanner",
                model="Model A",
                serial_number="SN-77",
                evidence=SourceEvidence(source_text="Scanner Model A Seriennummer SN-77"),
            ),
            Equipment(
                device_name="Scanner",
                model="Model B",
                serial_number="SN-77",
                evidence=SourceEvidence(source_text="Scanner Model B Seriennummer SN-77"),
            ),
        ]
    )
    units = [
        _unit("Scanner Model A Seriennummer SN-77", 1),
        _unit("Scanner Model B Seriennummer SN-77", 2),
    ]
    issues = verify_equipment_claims(contract, units)
    assert any("gleiche Geräteidentität" in issue and "model" in issue for issue in issues)
    assert contract.equipment[0].evidence.requires_review is True
    assert contract.equipment[1].evidence.requires_review is True


def test_two_same_named_devices_with_distinct_serials_are_not_false_conflict():
    contract = Contract(
        equipment=[
            Equipment(device_name="Pump", model="X", serial_number="SN-1"),
            Equipment(device_name="Pump", model="X", serial_number="SN-2"),
        ]
    )
    units = [
        _unit("Pump X Seriennummer SN-1", 1),
        _unit("Pump X Seriennummer SN-2", 2),
    ]
    issues = verify_equipment_claims(contract, units)
    assert not any("gleiche Geräteidentität" in issue for issue in issues)


def test_equipment_location_is_operationally_grounded():
    contract = Contract(
        equipment=[
            Equipment(
                device_name="Pump X",
                location="OP 3",
                evidence=SourceEvidence(source_text="Pump X"),
            )
        ]
    )
    issues = verify_equipment_claims(contract, [_unit("Pump X befindet sich im OP 2")])
    assert any(".location" in issue for issue in issues)


def test_equipment_included_service_rejects_explicit_exclusion():
    contract = Contract(
        equipment=[
            Equipment(
                device_name="Pump X",
                included_services=["Kalibrierung"],
                evidence=SourceEvidence(source_text="Pump X"),
            )
        ]
    )
    issues = verify_equipment_claims(
        contract, [_unit("Pump X: Kalibrierung ist nicht enthalten")]
    )
    assert any("included_services" in issue for issue in issues)


def test_equipment_excluded_service_requires_negative_semantics():
    contract = Contract(
        equipment=[
            Equipment(
                device_name="Pump X",
                excluded_services=["Kalibrierung"],
                evidence=SourceEvidence(source_text="Pump X"),
            )
        ]
    )
    positive = verify_equipment_claims(
        contract, [_unit("Pump X: Kalibrierung ist enthalten")]
    )
    assert any("excluded_services" in issue for issue in positive)

    negative = verify_equipment_claims(
        contract, [_unit("Pump X: Kalibrierung ist nicht enthalten")]
    )
    assert not any("excluded_services" in issue for issue in negative)
