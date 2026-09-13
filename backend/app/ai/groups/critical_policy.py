"""Central policy inventory for safety-critical extracted contract claims.

The policy is deliberately data-only: extraction/verifier code can consume it
without duplicating severity/default/evidence semantics.  A claim listed here is
not automatically VERIFIED; callers must enforce the configured strategy.
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


# Current semantic-verifier claims. Keep this inventory as the single target for
# migration away from verifier.py's historical SENSITIVE_FIELDS tuple.
CURRENT_VERIFIER_CLAIMS: tuple[CriticalClaimPolicy, ...] = (
    CriticalClaimPolicy("identity.contract_number", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("dates.start_date", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("dates.end_date", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("dates.duration", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("dates.minimum_duration", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("termination.cancellation_period", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("termination.automatic_renewal", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("termination.renewal_period", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.annual_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.monthly_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.total_contract_value", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy(
        "payment.billing_interval",
        Criticality.HIGH,
        EvidenceStrategy.FIELD,
        unknown_values=("other",),
    ),
)

# Claims that must join the enforced verifier/evidence path before STEP 18 can be
# considered broadly safe for hospital contract operations.
PENDING_CRITICAL_CLAIMS: tuple[CriticalClaimPolicy, ...] = (
    CriticalClaimPolicy("identity.supplier", Criticality.CRITICAL, EvidenceStrategy.PARTY_ROLE),
    CriticalClaimPolicy("identity.customer", Criticality.CRITICAL, EvidenceStrategy.PARTY_ROLE),
    CriticalClaimPolicy("identity.contractor", Criticality.HIGH, EvidenceStrategy.PARTY_ROLE),
    CriticalClaimPolicy("equipment[].device_name", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT),
    CriticalClaimPolicy("equipment[].model", Criticality.HIGH, EvidenceStrategy.EQUIPMENT),
    CriticalClaimPolicy("equipment[].serial_number", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT),
    CriticalClaimPolicy("equipment[].inventory_number", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT),
    CriticalClaimPolicy("equipment[].coverage_start", Criticality.HIGH, EvidenceStrategy.EQUIPMENT),
    CriticalClaimPolicy("equipment[].coverage_end", Criticality.HIGH, EvidenceStrategy.EQUIPMENT),
    CriticalClaimPolicy("equipment[].service_scope", Criticality.CRITICAL, EvidenceStrategy.EQUIPMENT),
    CriticalClaimPolicy("services.included_services", Criticality.CRITICAL, EvidenceStrategy.SECTION),
    CriticalClaimPolicy("services.excluded_services", Criticality.CRITICAL, EvidenceStrategy.SECTION),
    CriticalClaimPolicy("services.maintenance", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("services.repair", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("services.software_updates", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("services.spare_parts_included", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("services.emergency_service", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("sla.response_time", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("sla.resolution_time", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("sla.emergency_availability", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("sla.availability_24_7", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.quarterly_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.semi_annual_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.one_time_cost", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.maintenance_fee", Criticality.CRITICAL, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.hourly_rate", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.additional_costs", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.price_adjustment_clause", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.tax_basis", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("costs.tax_rate_percent", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("payment.payment_deadline_days", Criticality.HIGH, EvidenceStrategy.FIELD),
    CriticalClaimPolicy("payment.advance_payment", Criticality.CRITICAL, EvidenceStrategy.FIELD),
)


def current_verifier_fields() -> tuple[str, ...]:
    return tuple(policy.field for policy in CURRENT_VERIFIER_CLAIMS)


def policy_for(field: str) -> CriticalClaimPolicy | None:
    for policy in CURRENT_VERIFIER_CLAIMS + PENDING_CRITICAL_CLAIMS:
        if policy.field == field:
            return policy
    return None
