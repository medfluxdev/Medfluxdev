"""Verifier completeness regressions for sensitive contract claims."""

from app.ai.groups.extractor import GroupPipeline
from app.ai.groups.verifier import SensitiveVerificationResult, VerificationDecision
from app.core.config import Settings
from app.models.contract import Contract
from app.models.enums import BillingInterval, TimeUnit
from app.models.values import Duration


settings = Settings(_env_file=None)


def _pipeline() -> GroupPipeline:
    return GroupPipeline(None, settings)  # type: ignore[arg-type]


def test_expected_verifier_fields_include_present_sensitive_claims_only():
    contract = Contract()
    contract.identity.contract_number = "V-123"
    contract.dates.minimum_duration = Duration(value=2, unit=TimeUnit.YEARS)
    contract.payment.billing_interval = BillingInterval.OTHER

    expected = _pipeline()._expected_verifier_fields(contract)

    assert "identity.contract_number" in expected
    assert "dates.minimum_duration" in expected
    assert "payment.billing_interval" not in expected
    assert "costs.annual_cost" not in expected


def test_partial_verifier_reply_leaves_detectable_missing_sensitive_fields():
    contract = Contract()
    contract.identity.contract_number = "V-123"
    contract.dates.minimum_duration = Duration(value=2, unit=TimeUnit.YEARS)

    result = SensitiveVerificationResult(
        decisions=[
            VerificationDecision(
                field="identity.contract_number",
                supported=True,
                reason="belegt",
            )
        ]
    )

    pipeline = _pipeline()
    expected = pipeline._expected_verifier_fields(contract)
    returned = {decision.field for decision in result.decisions}
    missing = expected - returned

    assert missing == {"dates.minimum_duration"}


def test_explicit_billing_interval_requires_verifier_decision():
    contract = Contract()
    contract.payment.billing_interval = BillingInterval.ANNUAL

    assert "payment.billing_interval" in _pipeline()._expected_verifier_fields(contract)
