from app.ai.groups.critical_policy import (
    CURRENT_VERIFIER_CLAIMS,
    PENDING_CRITICAL_CLAIMS,
    SPECIALIZED_CRITICAL_CLAIMS,
    Criticality,
    current_verifier_fields,
    policy_for,
)
from app.ai.groups.verifier import SENSITIVE_FIELDS


def test_current_policy_matches_enforced_verifier_fields() -> None:
    assert current_verifier_fields() == SENSITIVE_FIELDS


def test_critical_policy_has_no_duplicate_fields() -> None:
    fields = [
        p.field
        for p in (
            CURRENT_VERIFIER_CLAIMS
            + SPECIALIZED_CRITICAL_CLAIMS
            + PENDING_CRITICAL_CLAIMS
        )
    ]
    assert len(fields) == len(set(fields))


def test_newly_enforced_hospital_claims_are_current():
    enforced = {
        "identity.supplier",
        "identity.customer",
        "services.maintenance",
        "services.repair",
        "sla.response_time",
        "sla.availability_24_7",
        "payment.advance_payment",
    }
    current = {p.field for p in CURRENT_VERIFIER_CLAIMS}
    assert enforced <= current


def test_dynamic_and_list_claims_are_owned_by_specialized_gates():
    required = {
        "equipment[].device_name",
        "equipment[].serial_number",
        "services.included_services",
        "services.excluded_services",
    }
    specialized = {p.field for p in SPECIALIZED_CRITICAL_CLAIMS}
    assert required <= specialized
    assert all(policy_for(field) is not None for field in required)
    assert all(policy_for(field).semantic_verifier_required is False for field in required)


def test_no_known_critical_claim_is_left_unowned():
    assert PENDING_CRITICAL_CLAIMS == ()


def test_contract_number_and_termination_are_critical() -> None:
    assert policy_for("identity.contract_number").criticality is Criticality.CRITICAL
    assert policy_for("termination.cancellation_period").criticality is Criticality.CRITICAL
    assert policy_for("termination.automatic_renewal").criticality is Criticality.CRITICAL


def test_operational_equipment_and_residual_claims_are_in_policy():
    required = {
        "equipment[].device_name",
        "equipment[].manufacturer",
        "equipment[].model",
        "equipment[].serial_number",
        "equipment[].inventory_number",
        "equipment[].system_name",
        "equipment[].equipment_category",
        "equipment[].equipment_type",
        "equipment[].location",
        "equipment[].department",
        "equipment[].coverage_start",
        "equipment[].coverage_end",
        "equipment[].service_scope",
        "equipment[].included_services",
        "equipment[].excluded_services",
        "equipment[].sla_notes",
        "costs.default_currency",
        "costs.scheduled_prices",
        "costs.variable_charges",
        "payment.payment_terms",
        "services.inspection",
        "services.calibration",
        "services.remote_support",
        "services.technical_support",
        "services.consumables_included",
        "sla.service_hours",
        "sla.sla_notes",
    }
    owned = {
        p.field
        for p in (
            CURRENT_VERIFIER_CLAIMS
            + SPECIALIZED_CRITICAL_CLAIMS
            + PENDING_CRITICAL_CLAIMS
        )
    }
    assert required <= owned
