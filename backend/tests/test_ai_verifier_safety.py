"""Regression tests for verifier evidence routing and null-safe collection."""

from app.ai.groups.verifier import _collect_sensitive_values, _is_sensitive_relevant
from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.models.contract import Contract
from app.models.evidence import SourceEvidence
from app.models.enums import BillingInterval, TimeUnit
from app.models.values import Duration


def _unit(source_type: SourceType, index: int, text: str) -> ExtractionUnit:
    return ExtractionUnit(source_type=source_type, index=index, text=text)


def test_collect_sensitive_values_no_crash_when_source_text_none():
    contract = Contract()
    for section in (
        contract.identity,
        contract.dates,
        contract.termination,
        contract.costs,
        contract.payment,
    ):
        section.evidence = SourceEvidence()

    values = _collect_sensitive_values(contract)
    assert values, "sensible Felder wurden gesammelt"
    for sv in values:
        assert sv.evidence is None
        assert sv.evidence_scope is None


def test_collect_sensitive_values_still_captures_source_text():
    contract = Contract()
    contract.payment.evidence = SourceEvidence(source_text="jaehrliche Zahlung")
    contract.payment.billing_interval = None

    values = _collect_sensitive_values(contract)
    by_field = {sv.field: sv for sv in values}
    assert by_field["payment.billing_interval"].evidence == "jaehrliche Zahlung"
    assert by_field["payment.billing_interval"].evidence_scope == "section"


def test_collect_sensitive_values_truncates_long_source_text():
    contract = Contract()
    contract.identity.evidence = SourceEvidence(source_text="x" * 300)

    values = _collect_sensitive_values(contract)
    by_field = {sv.field: sv for sv in values}
    ev = by_field["identity.contract_number"].evidence
    assert ev is not None
    assert len(ev) <= 120


def test_minimum_duration_uses_field_evidence_over_wrong_section_evidence():
    contract = Contract()
    contract.dates.minimum_duration = Duration(value=2, unit=TimeUnit.YEARS)
    contract.dates.evidence = SourceEvidence(source_text="Vertragsbeginn nach Übergabe")
    contract.termination.evidence = SourceEvidence(source_text="Mindestvertragslaufzeit (2 Jahre)")
    units = [
        _unit(SourceType.TABLE, 2, "Mindestvertragslaufzeit (2 Jahre) | X"),
        _unit(SourceType.PARAGRAPH, 3, "Vertragsbeginn nach Übergabe"),
    ]

    values = _collect_sensitive_values(contract, units=units)
    by_field = {sv.field: sv for sv in values}
    minimum = by_field["dates.minimum_duration"]

    assert minimum.value == {"value": 2, "unit": "years"}
    assert minimum.evidence == "Mindestvertragslaufzeit (2 Jahre) | X"
    assert minimum.evidence_scope == "field"


def test_minimum_duration_does_not_borrow_unrelated_dates_evidence_when_field_match_exists():
    contract = Contract()
    contract.dates.minimum_duration = Duration(value=2, unit=TimeUnit.YEARS)
    contract.dates.evidence = SourceEvidence(source_text="Kündigungsfrist sechs Monate")
    units = [_unit(SourceType.TABLE, 2, "Mindestvertragslaufzeit (2 Jahre)")]

    values = _collect_sensitive_values(contract, units=units)
    by_field = {sv.field: sv for sv in values}

    assert by_field["dates.minimum_duration"].evidence == "Mindestvertragslaufzeit (2 Jahre)"
    assert by_field["dates.minimum_duration"].evidence_scope == "field"


def test_default_billing_interval_other_is_not_a_verifiable_claim():
    contract = Contract()
    contract.payment.billing_interval = BillingInterval.OTHER

    values = _collect_sensitive_values(contract)
    billing = next(v for v in values if v.field == "payment.billing_interval")

    assert billing.value == "other"
    assert _is_sensitive_relevant(billing) is False


def test_explicit_annual_billing_interval_remains_verifiable():
    contract = Contract()
    contract.payment.billing_interval = BillingInterval.ANNUAL
    units = [_unit(SourceType.PARAGRAPH, 4, "Die Abrechnung erfolgt jährlich.")]

    values = _collect_sensitive_values(contract, units=units)
    billing = next(v for v in values if v.field == "payment.billing_interval")

    assert billing.value == "annual"
    assert billing.evidence == "Die Abrechnung erfolgt jährlich."
    assert billing.evidence_scope == "field"
    assert _is_sensitive_relevant(billing) is True
