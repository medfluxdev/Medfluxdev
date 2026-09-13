# STEP 18 Autopilot Plan

Status snapshot after Big Pickle quota exhaustion. Static/GitHub work continues; runtime claims remain unverified until the local gate is executed.

## Completed statically on JAMAL

- [x] Make unsupported semantic-verifier decisions fail closed even when section-level evidence is absent.
- [x] Count actual verifier problems instead of counting every verifier decision as an issue.
- [x] Surface multi-chunk extraction conflicts instead of silently keeping the first value.
- [x] Fail closed when the verifier returns no usable decisions.
- [x] Require a verifier decision for every present sensitive claim; missing decisions force review.
- [x] Treat `payment.billing_interval=other` as an unknown/default, not a factual claim.
- [x] Require concrete `source_text` for evidence; a page/paragraph/table pointer alone is not proof.
- [x] Add targeted regression tests for verifier fail-closed behavior, completeness, merge conflicts, and evidence source text.
- [x] Add a DB-free PowerShell safety gate: `scripts/step18_safety_gate.ps1`.
- [x] Inventory all contract-model critical fields and document verifier/evidence coverage in `docs/STEP18_CRITICAL_FIELD_AUDIT.md`.
- [x] Confirm central auth middleware binds requested `organization_slug` to the signed identity when auth is enabled; mismatches fail as 404 and viewers cannot mutate domain data.

## Static implementation backlog

- [ ] Verify each `equipment[].evidence` object in GroupPipeline; current section evidence loop covers identity/dates/termination/costs/payment/services/SLA but not per-equipment evidence.
- [ ] Replace the ad-hoc `SENSITIVE_FIELDS` tuple with a centralized critical-claim policy describing severity, unknown/default semantics, evidence strategy and verifier requirement.
- [ ] Add party-role verification for supplier/customer/contractor.
- [ ] Add equipment identity/coverage verification for device/model/serial/inventory/coverage/service scope.
- [ ] Add services/SLA verification with strict tri-state boolean semantics.
- [ ] Expand financial verification to the remaining extracted money/payment fields without deriving or aggregating values.
- [ ] Add adversarial tests for conflicting parties, devices, inclusion/exclusion, SLA and money.
- [ ] Review all contract/document/equipment/intelligence routes for tenant binding and direct-object authorization.
- [ ] Review Contract 360 and Human Review UI so unverified/unsupported claims cannot look verified.

## Runtime gate when local model quota is available

- [ ] Run `scripts/step18_safety_gate.ps1` with `MEDFLUX_UNIT_ONLY=1`.
- [ ] Run one production Accutron extraction at temperature 0.
- [ ] Assert canonical 27/27 benchmark fields.
- [ ] Verify `dates.minimum_duration` is supported from field-scoped evidence containing `Mindestvertragslaufzeit (2 Jahre)`.
- [ ] Verify `payment.billing_interval=other` is excluded from semantic verification.
- [ ] Verify no invented contract number / dates / costs / cancellation / renewal facts.
- [ ] Verify unsupported or missing sensitive verifier decisions always produce PARTIAL / NEEDS_REVIEW.
- [ ] Verify multi-chunk contradictory critical values produce review instead of silent first-value acceptance.
- [ ] If targeted gate passes, run the full backend regression suite once.

## Closure rule

STEP 18 is not closed by static review alone and not closed by the Accutron benchmark alone. Closure requires the targeted safety gate, the real benchmark gate, and a final full backend regression with no newly introduced failures.
