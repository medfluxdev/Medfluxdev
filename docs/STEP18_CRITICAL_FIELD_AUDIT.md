# STEP 18 Critical Field Audit

This audit is intentionally fail-closed. A field being present in the Pydantic schema does not mean it is safe to trust operationally.

## Current verifier coverage

The semantic verifier currently covers:

- identity.contract_number
- dates.start_date / end_date / duration / minimum_duration
- termination.cancellation_period / automatic_renewal / renewal_period
- costs.annual_cost / monthly_cost / total_contract_value
- payment.billing_interval (except `other`, which is an unknown/default and not a claim)

Field-scoped evidence routing exists for those fields. Missing verifier decisions and unsupported decisions are review conditions.

## Critical claims not yet semantically verified

These remain **runtime/architecture work**, not trusted claims merely because extraction succeeded:

### Parties
- identity.supplier
- identity.customer
- identity.contractor

Party names have deterministic source grounding/canonicalization, but they are not in `SENSITIVE_FIELDS`. Role mistakes are legally/operationally important and require a dedicated party-role verifier rather than generic fuzzy matching alone.

### Equipment coverage
- equipment[].device_name / model / manufacturer
- serial_number / inventory_number
- service_scope
- coverage_start / coverage_end
- included_services / excluded_services

Each Equipment object has its own `SourceEvidence`, but the current GroupPipeline section evidence loop only verifies section-level evidence and does not iterate `contract.equipment`. This is a concrete coverage gap. Until fixed and runtime-tested, equipment coverage must not be treated as fully evidence-verified.

### Services
- services.included_services / excluded_services
- maintenance / inspection / repair / calibration / software_updates
- remote_support / technical_support
- spare_parts_included / consumables_included / emergency_service

Tri-state bool prompting and deterministic grounding reduce hallucination risk, but these claims are not currently in the semantic verifier set.

### SLA
- response_time / resolution_time / service_hours / emergency_availability
- availability_24_7

These can affect hospital operations and must eventually receive field-scoped evidence verification. `availability_24_7` must preserve tri-state semantics: absence is null, never false.

### Financial fields beyond current verifier
- quarterly_cost / semi_annual_cost / one_time_cost
- setup_installation_cost / maintenance_fee / hourly_rate
- travel_cost / material_cost / spare_parts_cost / additional_costs
- scheduled_prices / variable_charges / discounts
- price_adjustment_clause / price_indexation
- tax_basis / tax_rate_percent
- payment_terms / payment_deadline_days / advance_payment

No derived aggregation is allowed at extraction time. Conditional/variable charges must remain separate.

## Required implementation order

1. Verify per-equipment evidence objects deterministically in GroupPipeline.
2. Add dedicated critical-claim inventory/policy rather than growing one ad-hoc tuple indefinitely.
3. Add party-role semantic verification with field-scoped role evidence.
4. Add equipment identity/coverage verification.
5. Add services/SLA verification with tri-state bool rules.
6. Expand financial verification without deriving values.
7. Ensure every critical present claim is either VERIFIED/GROUNDED or forces NEEDS_REVIEW.
8. Add adversarial tests for conflicting parties, devices, service inclusion/exclusion, SLA and money.
9. Run DB-free targeted safety gate.
10. Run one real Accutron benchmark and then the full backend regression.

## Closure invariant

A critical extracted value must never become operationally trusted solely because the LLM emitted valid JSON. It needs source grounding/evidence plus the applicable deterministic/semantic verification policy. Missing, contradictory, unsupported, or unverifiable evidence must fail closed to human review.
