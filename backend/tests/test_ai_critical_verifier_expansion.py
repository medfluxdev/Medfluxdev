"""DB-free regression coverage for the expanded critical-claim verifier."""

from datetime import date

import json

import pytest

from app.ai.groups.critical_policy import current_verifier_fields
from app.ai.groups.verifier import (
    SENSITIVE_FIELDS,
    _collect_sensitive_values,
    _is_sensitive_relevant,
    run_verifier,
)
from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.models.contract import Contract
from app.models.values import FlexibleDate, Money, TimeValue
from app.models.enums import TimeUnit


def _unit(text: str, index: int = 1) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.PARAGRAPH, index=index, text=text)


def _by_field(contract: Contract, units: list[ExtractionUnit]):
    return {item.field: item for item in _collect_sensitive_values(contract, units=units)}


def test_sensitive_fields_are_owned_by_central_policy():
    assert tuple(SENSITIVE_FIELDS) == current_verifier_fields()


def test_party_role_evidence_requires_role_and_name_in_same_unit():
    contract = Contract()
    contract.identity.customer = "Krankenhaus Nordwest GmbH"
    contract.identity.supplier = "MEDTRON AG"
    units = [
        _unit("Auftraggeber: Krankenhaus Nordwest GmbH", 1),
        _unit("Auftragnehmer: MEDTRON AG", 2),
    ]

    values = _by_field(contract, units)
    assert values["identity.customer"].evidence_scope == "field"
    assert "Auftraggeber" in values["identity.customer"].evidence
    assert values["identity.supplier"].evidence_scope == "field"
    assert "Auftragnehmer" in values["identity.supplier"].evidence


def test_party_name_without_role_does_not_borrow_section_evidence_when_units_exist():
    contract = Contract()
    contract.identity.customer = "Krankenhaus Nordwest GmbH"
    units = [_unit("Krankenhaus Nordwest GmbH, Frankfurt am Main")]

    value = _by_field(contract, units)["identity.customer"]
    assert value.evidence is None
    assert value.evidence_scope is None


def test_service_true_requires_positive_evidence_and_false_requires_explicit_negation():
    contract = Contract()
    contract.services.repair = True
    positive = _by_field(contract, [_unit("Kostenlose Reparaturen sind enthalten.")])["services.repair"]
    assert positive.evidence_scope == "field"

    contract.services.repair = False
    silent = _by_field(contract, [_unit("Wartung ist enthalten.")])["services.repair"]
    assert silent.evidence is None

    negative = _by_field(contract, [_unit("Reparaturen sind nicht enthalten.")])["services.repair"]
    assert negative.evidence_scope == "field"


def test_sla_response_time_is_field_scoped_by_label_and_value():
    contract = Contract()
    contract.sla.response_time = TimeValue(value=4, unit=TimeUnit.HOURS, original_text="Reaktionszeit 4 Stunden")
    values = _by_field(contract, [_unit("Service Level: Reaktionszeit 4 Stunden ab Störungsmeldung.")])
    response = values["sla.response_time"]
    assert response.evidence_scope == "field"
    assert "Reaktionszeit" in response.evidence


def test_financial_expansion_routes_period_specific_amounts():
    contract = Contract()
    contract.costs.quarterly_cost = Money(amount=1200, currency="EUR", period="quarterly")
    contract.payment.advance_payment = Money(amount=500, currency="EUR", period="once")
    units = [
        _unit("Quartalsweise Gebühr: 1.200 EUR", 1),
        _unit("Vorauszahlung: 500 EUR bei Auftragserteilung", 2),
    ]
    values = _by_field(contract, units)
    assert values["costs.quarterly_cost"].evidence_scope == "field"
    assert values["payment.advance_payment"].evidence_scope == "field"


def test_empty_structured_wrappers_are_not_verifier_claims():
    contract = Contract()
    values = _by_field(contract, [])
    assert _is_sensitive_relevant(values["sla.response_time"]) is False
    assert _is_sensitive_relevant(values["payment.advance_payment"]) is False


class _FakeAI:
    def __init__(self, payload: dict):
        self.payload = payload

    async def generate_structured(self, *args, **kwargs):
        return json.dumps(self.payload)


@pytest.mark.asyncio
async def test_duplicate_verifier_decisions_fail_closed_to_empty_result():
    contract = Contract()
    contract.identity.contract_number = "V-123"
    units = [_unit("Vertragsnummer: V-123")]
    ai = _FakeAI(
        {
            "decisions": [
                {"field": "identity.contract_number", "supported": True},
                {"field": "identity.contract_number", "supported": True},
            ]
        }
    )
    result, calls = await run_verifier(ai, contract, "Vertragsnummer: V-123", units=units)
    assert calls == 1
    assert result.decisions == []


@pytest.mark.asyncio
async def test_unexpected_verifier_field_fails_closed_to_empty_result():
    contract = Contract()
    contract.identity.contract_number = "V-123"
    units = [_unit("Vertragsnummer: V-123")]
    ai = _FakeAI(
        {"decisions": [{"field": "identity.supplier", "supported": True}]}
    )
    result, calls = await run_verifier(ai, contract, "Vertragsnummer: V-123", units=units)
    assert calls == 1
    assert result.decisions == []


class _MustNotRunAI:
    async def generate_structured(self, *args, **kwargs):
        raise AssertionError("AI must not be called for evidence-less critical claims")


@pytest.mark.asyncio
async def test_context_cannot_rescue_evidence_less_critical_claim():
    contract = Contract()
    contract.identity.contract_number = "V-999"

    result, calls = await run_verifier(
        _MustNotRunAI(),
        contract,
        "Vertragsnummer: V-999",
        units=[_unit("Bestellnummer V-999")],
    )

    assert calls == 0
    assert len(result.decisions) == 1
    assert result.decisions[0].field == "identity.contract_number"
    assert result.decisions[0].supported is False
    assert "Kein feldspezifischer Quellenbeleg" in (result.decisions[0].reason or "")


def test_money_field_evidence_rejects_currency_mismatch():
    contract = Contract()
    contract.costs.annual_cost = Money(amount=1200, currency="EUR", period="annual")
    values = _by_field(
        contract,
        [_unit("Jährliche Gebühr: 1.200 USD")],
    )
    assert values["costs.annual_cost"].evidence is None


def test_numeric_matching_does_not_accept_prefix_collision():
    contract = Contract()
    contract.costs.annual_cost = Money(amount=12, currency="EUR", period="annual")
    values = _by_field(
        contract,
        [_unit("Jährliche Gebühr: 1.200 EUR")],
    )
    assert values["costs.annual_cost"].evidence is None


def test_start_date_accepts_german_calendar_format():
    contract = Contract()
    contract.dates.start_date = FlexibleDate(date=date(2026, 2, 1))
    values = _by_field(
        contract,
        [_unit("Vertragsbeginn: 01.02.2026")],
    )
    assert values["dates.start_date"].evidence_scope == "field"
