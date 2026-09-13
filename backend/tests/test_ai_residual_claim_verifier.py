"""DB-free regression tests for residual critical-claim verification."""

from app.ai.groups.residual_claim_verifier import verify_residual_critical_claims
from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.models.contract import Contract, ScheduledPrice, VariableCharge
from app.models.values import Money, TimeValue
from app.models.enums import TimeUnit


def _unit(text: str, index: int = 1) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.PARAGRAPH, index=index, text=text)


def test_payment_terms_require_exact_source_text():
    contract = Contract()
    contract.payment.payment_terms = "Zahlbar innerhalb von 30 Tagen"

    issues = verify_residual_critical_claims(
        contract, [_unit("Zahlung innerhalb von 14 Tagen")]
    )

    assert any("payment.payment_terms" in issue for issue in issues)


def test_false_optional_service_requires_explicit_negation():
    contract = Contract()
    contract.services.remote_support = False

    silent = verify_residual_critical_claims(
        contract, [_unit("Wartung und Reparatur sind enthalten")]
    )
    assert any("services.remote_support" in issue for issue in silent)

    explicit = verify_residual_critical_claims(
        contract, [_unit("Fernwartung ist nicht enthalten")]
    )
    assert not any("services.remote_support" in issue for issue in explicit)


def test_service_hours_need_service_hour_semantics():
    contract = Contract()
    contract.sla.service_hours = TimeValue(value=8, unit=TimeUnit.HOURS)

    issues = verify_residual_critical_claims(
        contract, [_unit("Reaktionszeit innerhalb von 8 Stunden")]
    )

    assert any("sla.service_hours" in issue for issue in issues)


def test_scheduled_price_requires_amount_and_period_label_together():
    contract = Contract()
    contract.costs.scheduled_prices = [
        ScheduledPrice(
            period_index=1,
            period_label="Vertragsjahr 1",
            amount=Money(amount=1200, currency="EUR", period="annual"),
        )
    ]

    wrong = verify_residual_critical_claims(
        contract,
        [
            _unit("Vertragsjahr 1 beginnt am 01.01.2026", 1),
            _unit("Servicepreis 1.200 EUR", 2),
        ],
    )
    assert any("scheduled_prices[0]" in issue for issue in wrong)

    supported = verify_residual_critical_claims(
        contract, [_unit("Vertragsjahr 1: Servicepreis 1.200 EUR")]
    )
    assert not any("scheduled_prices[0]" in issue for issue in supported)


def test_variable_charge_requires_amount_and_semantic_unit_together():
    contract = Contract()
    contract.costs.variable_charges = [
        VariableCharge(
            label="Störungsbearbeitung",
            amount=Money(amount=250, currency="EUR"),
            unit="per_call",
        )
    ]

    wrong = verify_residual_critical_claims(
        contract,
        [
            _unit("Störungsbearbeitung nach Aufwand", 1),
            _unit("Pauschale 250 EUR", 2),
        ],
    )
    assert any("variable_charges[0]" in issue for issue in wrong)

    supported = verify_residual_critical_claims(
        contract, [_unit("Störungsbearbeitung 250 EUR per_call")]
    )
    assert not any("variable_charges[0]" in issue for issue in supported)


def test_sla_notes_must_be_traceable_to_source():
    contract = Contract()
    contract.sla.sla_notes = "Priorität 1 nur werktags"

    issues = verify_residual_critical_claims(
        contract, [_unit("Priorität 1 rund um die Uhr")]
    )

    assert any("sla.sla_notes" in issue for issue in issues)
