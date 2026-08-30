"""Tests für das Medflux-Vertragsdatenmodell (Schritt 3)."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.models.contract import Contract
from app.models.enums import (
    BillingInterval,
    ContractStatus,
    ContractType,
    ExtractionMethod,
    ExtractionStatus,
    ReviewStatus,
    TimeUnit,
    ValidationStatus,
)
from app.models.evidence import SourceEvidence
from app.models.values import Duration, FlexibleDate, Money, TimeValue


def test_valid_full_contract():
    contract = Contract(
        id="C-001",
        status=ContractStatus.ACTIVE,
        identity={
            "contract_title": "Wartungsvertrag CT",
            "contract_number": "WM-2024-001",
            "contract_type": ContractType.MAINTENANCE,
            "supplier": "Siemens Healthineers",
            "customer": "Klinikum Mitte",
            "department": "Radiologie",
        },
        equipment=[
            {
                "device_name": "CT-Scanner",
                "manufacturer": "Siemens",
                "model": "Somatom go.Top",
                "serial_number": "SN-12345",
                "system_name": "Radiologie-CT",
            }
        ],
        dates={
            "start_date": {"date": date(2024, 1, 1)},
            "end_date": {"date": date(2026, 12, 31)},
            "duration": {"value": 36, "unit": TimeUnit.MONTHS},
        },
        termination={
            "cancellation_period": {"value": 6, "unit": TimeUnit.MONTHS},
            "automatic_renewal": True,
            "renewal_period": {"value": 12, "unit": TimeUnit.MONTHS},
        },
        costs={
            "default_currency": "EUR",
            "annual_cost": {"amount": 24500.00, "currency": "EUR", "period": "annual"},
            "monthly_cost": {"amount": 2000.00, "currency": "EUR", "period": "monthly"},
        },
        payment={
            "payment_terms": "30 Tage netto",
            "payment_deadline_days": 30,
            "billing_interval": BillingInterval.ANNUAL,
        },
        services={
            "included_services": ["Wartung", "Reparatur"],
            "excluded_services": ["Verschleißteile"],
            "maintenance": True,
            "repair": True,
        },
        sla={
            "response_time": {
                "value": 4,
                "unit": TimeUnit.HOURS,
                "original_text": "Reaktionszeit 4 Stunden",
            },
            "availability_24_7": True,
        },
        review={
            "review_status": ReviewStatus.REVIEWED,
            "requires_manual_review": False,
        },
        analysis={
            "model_name": "qwen3:8b-q4",
            "extraction_status": ExtractionStatus.SUCCESS,
            "validation_status": ValidationStatus.VALID,
        },
    )
    assert contract.identity.contract_title == "Wartungsvertrag CT"
    assert contract.equipment[0].serial_number == "SN-12345"
    assert contract.dates.start_date.date == date(2024, 1, 1)
    assert contract.termination.cancellation_period.value == 6
    assert contract.costs.annual_cost.amount == 24500.00
    assert contract.costs.annual_cost.currency == "EUR"


def test_minimal_contract():
    contract = Contract()
    assert contract.status == ContractStatus.UNKNOWN
    assert contract.equipment == []
    assert contract.services.included_services == []
    assert contract.dates.start_date is None
    assert contract.review.requires_manual_review is False
    # Es dürfen keine Berechnungsfelder existieren
    assert "latest_cancellation_date" not in contract.model_dump()
    assert "warning_level" not in contract.model_dump()


def test_event_based_start_date():
    contract = Contract(
        dates={
            "start_date": {
                "date": None,
                "condition": "Übergabedatum",
                "requires_review": True,
            }
        }
    )
    fdate = contract.dates.start_date
    assert fdate.date is None
    assert fdate.condition == "Übergabedatum"
    assert fdate.requires_review is True


def test_unknown_start_date_is_null_not_string():
    contract = Contract(dates={"start_date": None})
    assert contract.dates.start_date is None
    data = contract.model_dump()
    assert data["dates"]["start_date"] is None


def test_monetary_values_structured():
    costs = Contract(costs={"annual_cost": {"amount": 12000.0, "currency": "EUR"}})
    money = costs.costs.annual_cost
    assert isinstance(money, Money)
    assert money.amount == 12000.0
    assert money.currency == "EUR"
    # Währung wird normalisiert
    assert Money(currency="eur").currency == "EUR"
    # Ein leerer/unbekannter Betrag ist None, kein String
    assert Money().amount is None


def test_source_evidence_linked():
    contract = Contract(
        identity={
            "contract_number": "WM-2024-001",
            "evidence": {
                "page": 3,
                "source_text": "Vertrags-Nr.: WM-2024-001",
                "confidence": 0.98,
                "extraction_method": ExtractionMethod.AI,
                "requires_review": False,
            },
        }
    )
    ev = contract.identity.evidence
    assert isinstance(ev, SourceEvidence)
    assert ev.page == 3
    assert ev.confidence == 0.98
    assert ev.extraction_method == ExtractionMethod.AI


def test_invalid_confidence_above_one():
    with pytest.raises(ValidationError):
        SourceEvidence(confidence=1.5)


def test_invalid_confidence_below_zero():
    with pytest.raises(ValidationError):
        SourceEvidence(confidence=-0.1)


def test_invalid_negative_time_period():
    with pytest.raises(ValidationError):
        Duration(value=-5, unit=TimeUnit.MONTHS)


def test_invalid_negative_money():
    with pytest.raises(ValidationError):
        Money(amount=-100.0)


def test_non_positive_page_rejected():
    with pytest.raises(ValidationError):
        SourceEvidence(page=0)


def test_time_value_with_original_text():
    tv = TimeValue(value=8, unit=TimeUnit.HOURS, original_text="8 Stunden")
    assert tv.value == 8
    assert tv.unit == TimeUnit.HOURS
    assert tv.original_text == "8 Stunden"


def test_flexible_date_explicit():
    fd = FlexibleDate(date=date(2025, 6, 1))
    assert fd.date == date(2025, 6, 1)
    assert fd.condition is None
