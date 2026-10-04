"""Central policy inventory for safety-critical extracted contract claims.

The policy is deliberately data-only. A claim listed here is never considered
verified merely because it passed schema validation; it must be enforced by the
semantic scalar verifier or a specialized deterministic verifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Criticality(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"


class EvidenceStrategy(str, Enum):
    FIELD = "field"
    PARTY_ROLE = "party_role"
    EQUIPMENT = "equipment"
    SECTION = "section"


@dataclass(frozen=True)
class CriticalClaimPolicy:
    field: str
    criticality: Criticality
    evidence_strategy: EvidenceStrategy
    semantic_verifier_required: bool = True
    unknown_values: tuple[object, ...] = ()


CURRENT_VERIFIER_CLAIMS: tuple[CriticalClaimPolicy, ...] = (
    CriticalClaimPolicy("identity.contract_number", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("identity.supplier", Criticality.CRITICAL, EvidenceStrategy.PARTY_ROLE),
    CriticalClaimPolicy("identity.customer", Criticality.CRITICAL, EvidenceStrategy.PARTY_ROLE),
    CriticalClaimPolicy("identity.contractor", Criticality.HIGH, EvidenceStrategy.PARTY_ROLE),
    CriticalClaimPolicy("dates.start_date", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("dates.end_date", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("dates.duration", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("dates.minimum_duration", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("termination.cancellation_period", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("termination.automatic_renewal", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("termination.renewal_period", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.annual_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.monthly_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.quarterly_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.semi_annual_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.one_time_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.maintenance_fee", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.hourly_rate", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.additional_costs", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.total_contract_value", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.price_adjustment_clause", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.tax_basis", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.tax_rate_percent", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("payment.payment_deadline_days", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("payment.advance_payment", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy(
        "payment.billing_interval",
        Criticality.HIGH,
        EvidenceStrategy.FIELD,
        unknown_values=("other",),
    ),
    CriticalClaimPolicy("services.maintenance", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("services.repair", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("services.software_updates", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("services.spare_parts_included", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("services.emergency_service", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("sla.response_time", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("sla.resolution_time", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("sla.emergency_availability", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("sla.availability_24_7", Criticality.CRITICAL, EvidenceStrategy.FIELD),
)

# List/dynamic claims are enforced by specialized deterministic gates because a
# scalar `section.field` verifier cannot safely address individual list members.
SPECIALIZED_CRITICAL_CLAIMS: tuple[CriticalClaimPolicy, ...] = (
    CriticalClaimPolicy("equipment[].device_name", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].manufacturer", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].system_name", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].equipment_category", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].equipment_type", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].location", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].department", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].model", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].serial_number", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].inventory_number", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].coverage_start", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].coverage_end", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].service_scope", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].included_services", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].excluded_services", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("equipment[].sla_notes", Criticality.HIGH, EvidenceStrategy.EQUIPMENT, semantic_verifier_required=False),
    CriticalClaimPolicy("services.included_services", Criticality.CRITICAL, EvidenceStrategy.SECTION, semantic_verifier_required=False),
    CriticalClaimPolicy("services.excluded_services", Criticality.CRITICAL, EvidenceStrategy.SECTION, semantic_verifier_required=False),
    CriticalClaimPolicy("dates.start_condition", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("dates.end_condition", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("termination.cancellation_condition", Criticality.CRITICAL, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("termination.cancellation_to_contract_end", Criticality.CRITICAL, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("termination.extraordinary_termination", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("costs.default_currency", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("costs.setup_installation_cost", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("costs.travel_cost", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("costs.material_cost", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("costs.spare_parts_cost", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("costs.scheduled_prices", Criticality.CRITICAL, EvidenceStrategy.SECTION, semantic_verifier_required=False),
    CriticalClaimPolicy("costs.variable_charges", Criticality.CRITICAL, EvidenceStrategy.SECTION, semantic_verifier_required=False),
    CriticalClaimPolicy("costs.discounts", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("costs.price_indexation", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("payment.payment_terms", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("services.inspection", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("services.calibration", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("services.remote_support", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("services.technical_support", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("services.consumables_included", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("sla.service_hours", Criticality.CRITICAL, EvidenceStrategy.FIELD, semantic_verifier_required=False),
    CriticalClaimPolicy("sla.sla_notes", Criticality.HIGH, EvidenceStrategy.FIELD, semantic_verifier_required=False),
)

# Reserved for claims discovered by future schema expansion that are not yet
# enforced. Keeping this explicit prevents silent policy debt.
PENDING_CRITICAL_CLAIMS: tuple[CriticalClaimPolicy, ...] = ()


def current_verifier_fields() -> tuple[str, ...]:
    return tuple(policy.field for policy in CURRENT_VERIFIER_CLAIMS)


def policy_for(field: str) -> CriticalClaimPolicy | None:
    for policy in CURRENT_VERIFIER_CLAIMS + SPECIALIZED_CRITICAL_CLAIMS + PENDING_CRITICAL_CLAIMS:
        if policy.field == field:
            return policy
    return None
