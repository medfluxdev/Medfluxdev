from app.ai.groups.critical_policy import (
    CURRENT_VERIFIER_CLAIMS,
    PENDING_CRITICAL_CLAIMS,
    Criticality,
    current_verifier_fields,
    policy_for,
)
from app.ai.groups.verifier import SENSITIVE_FIELDS


def test_current_policy_matches_enforced_verifier_fields() -> None:
    """Policy migration must not silently drift from actual verifier coverage."""
    assert current_verifier_fields() == SENSITIVE_FIELDS


def test_critical_policy_has_no_duplicate_fields() -> None:
    fields = [p.field for p in CURRENT_VERIFIER_CLAIMS + PENDING_CRITICAL_CLAIMS]
    assert len(fields) == len(set(fields))


def test_hospital_critical_pending_claims_are_explicitly_inventoried() -> None:
    required = {
        "identity.supplier",
        "identity.customer",
        "equipment[].device_name",
        "equipment[].serial_number",
        "services.included_services",
        "services.excluded_services",
        "services.maintenance",
        "services.repair",
        "sla.response_time",
        "sla.availability_24_7",
        "payment.advance_payment",
    }
    assert required <= {p.field for p in PENDING_CRITICAL_CLAIMS}
    assert all(policy_for(field) is not None for field in required)


def test_contract_number_and_termination_are_critical() -> None:
    assert policy_for("identity.contract_number").criticality is Criticality.CRITICAL
    assert policy_for("termination.cancellation_period").criticality is Criticality.CRITICAL
    assert policy_for("termination.automatic_renewal").criticality is Criticality.CRITICAL
