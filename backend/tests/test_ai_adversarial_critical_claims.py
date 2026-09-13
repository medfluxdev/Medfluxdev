"""Adversarial DB-free tests for critical contract claim grounding.

These cases intentionally place a correct-looking value next to the wrong field
semantics. The verifier must prefer false negatives/manual review over accepting
a semantically wrong critical claim.
"""

from app.ai.groups.verifier import _collect_sensitive_values
from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.models.contract import Contract
from app.models.enums import BillingInterval, TimeUnit
from app.models.values import Duration, Money, TimeValue


def _unit(text: str, index: int = 1) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.PARAGRAPH, index=index, text=text)


def _field(contract: Contract, units: list[ExtractionUnit], field: str):
    values = {v.field: v for v in _collect_sensitive_values(contract, units=units)}
    return values[field]


def test_purchase_order_number_is_not_contract_number_evidence():
    contract = Contract()
    contract.identity.contract_number = "452664"
    claim = _field(
        contract,
        [_unit("Bestellnummer 452664")],
        "identity.contract_number",
    )
    assert claim.evidence is None


def test_same_party_name_without_customer_role_is_not_customer_evidence():
    contract = Contract()
    contract.identity.customer = "Hospital GmbH"
    claim = _field(
        contract,
        [_unit("Rechnung an Hospital GmbH")],
        "identity.customer",
    )
    assert claim.evidence is None


def test_two_year_cancellation_text_cannot_support_minimum_duration():
    contract = Contract()
    contract.dates.minimum_duration = Duration(value=2, unit=TimeUnit.YEARS)
    claim = _field(
        contract,
        [_unit("Kündigungsfrist: 2 Jahre")],
        "dates.minimum_duration",
    )
    assert claim.evidence is None


def test_monthly_amount_cannot_support_annual_cost_even_when_amount_matches():
    contract = Contract()
    contract.costs.annual_cost = Money(amount=1200, currency="EUR", period="annual")
    claim = _field(
        contract,
        [_unit("Monatliche Gebühr: 1.200 EUR")],
        "costs.annual_cost",
    )
    assert claim.evidence is None


def test_annual_amount_cannot_support_monthly_cost_even_when_amount_matches():
    contract = Contract()
    contract.costs.monthly_cost = Money(amount=500, currency="EUR", period="monthly")
    claim = _field(
        contract,
        [_unit("Jährliche Gebühr: 500 EUR")],
        "costs.monthly_cost",
    )
    assert claim.evidence is None


def test_sla_resolution_time_cannot_be_proved_by_response_time_label():
    contract = Contract()
    contract.sla.resolution_time = TimeValue(value=4, unit=TimeUnit.HOURS)
    claim = _field(
        contract,
        [_unit("Reaktionszeit: 4 Stunden")],
        "sla.resolution_time",
    )
    assert claim.evidence is None


def test_24_7_false_requires_explicit_negation_not_silence():
    contract = Contract()
    contract.sla.availability_24_7 = False
    silent = _field(
        contract,
        [_unit("Servicezeiten Montag bis Freitag 08:00–17:00")],
        "sla.availability_24_7",
    )
    assert silent.evidence is None

    explicit = _field(
        contract,
        [_unit("24/7-Service ist nicht enthalten")],
        "sla.availability_24_7",
    )
    assert explicit.evidence_scope == "field"


def test_service_false_requires_explicit_exclusion_not_missing_word():
    contract = Contract()
    contract.services.repair = False
    claim = _field(
        contract,
        [_unit("Wartung und Software-Updates sind enthalten")],
        "services.repair",
    )
    assert claim.evidence is None


def test_billing_other_is_not_upgraded_by_unrelated_payment_text():
    contract = Contract()
    contract.payment.billing_interval = BillingInterval.OTHER
    claim = _field(
        contract,
        [_unit("Zahlung innerhalb von 30 Tagen")],
        "payment.billing_interval",
    )
    assert claim.evidence is None


def test_table_with_both_party_names_does_not_support_swapped_roles():
    contract = Contract()
    contract.identity.customer = "MEDTRON AG"
    contract.identity.supplier = "Krankenhaus Nordwest GmbH"
    table = ExtractionUnit(
        source_type=SourceType.TABLE,
        index=1,
        text=(
            "Auftraggeber | Auftragnehmer\n"
            "Krankenhaus Nordwest GmbH\n"
            "Frankfurt am Main | MEDTRON AG\n"
            "Saarbrücken"
        ),
    )

    values = {v.field: v for v in _collect_sensitive_values(contract, units=[table])}
    assert values["identity.customer"].evidence is None
    assert values["identity.supplier"].evidence is None
