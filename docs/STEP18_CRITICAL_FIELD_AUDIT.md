# STEP 18 Critical Field Audit

Status: **static implementation complete / runtime validation pending**.

This audit is fail-closed. A value being present in the Pydantic contract schema never makes it operationally trusted by itself.

## Enforced scalar semantic verifier

The central policy in `backend/app/ai/groups/critical_policy.py` owns the scalar critical claims. The semantic verifier now covers:

- contract number;
- supplier, customer and contractor with role-aware evidence;
- start/end dates, total duration and minimum duration;
- cancellation period, automatic renewal and renewal period;
- recurring/one-time/maintenance/hourly/additional/total money claims currently assigned to the scalar verifier;
- price-adjustment clause, tax basis and tax rate;
- payment deadline, advance payment and billing interval (except `other`, which remains unknown/default);
- critical service booleans such as maintenance, repair, software updates, spare parts and emergency service;
- SLA response time, resolution time, emergency availability and 24/7 availability.

Production verification with extraction units is field-evidence-first. Missing field evidence is not replaced with unrelated section evidence. Duplicate, incomplete or unexpected verifier decisions fail closed into manual review.

## Specialized deterministic critical gates

Claims that cannot be safely represented as one scalar `section.field` are owned by specialized gates:

- each equipment item is independently evidence-verified;
- serial and inventory numbers require the correct identifier semantics;
- equipment coverage dates require coverage semantics;
- conflicting duplicate device identities are surfaced instead of silently merged;
- included/excluded service-list members are checked individually;
- excluded services require explicit negative semantics;
- residual termination/payment clauses are traceable to source text;
- remaining service tri-state booleans require explicit positive/negative support;
- service hours and SLA notes are source-grounded;
- setup/travel/material/spare-parts/discount money claims require matching semantic labels;
- scheduled prices require amount + period context;
- variable charges require amount + label/unit context.

The policy inventory explicitly owns these specialized claims and `PENDING_CRITICAL_CLAIMS` is empty. Runtime tests are still required before STEP 18 is closed.

## Human-review invariant

A contract may not be marked reviewed while any **critical** material fact is still unreviewed. Blanket acknowledgement is allowed only for remaining non-critical items and still requires an explicit note.

The Contract 360 review UI mirrors this rule: critical open facts disable review completion and are shown as a blocking condition.

## Evidence/UI invariant

- Evidence without concrete `source_text` is not proof.
- Review-required evidence is displayed as **Unbestätigt · Menschliche Prüfung erforderlich**.
- The review list no longer claims all active contracts were human-reviewed merely because no open review rows were returned.
- Authenticated reviewer identity is server-bound; development/manual identity remains explicitly unverified.

## Static regression coverage

The targeted safety gate includes regression tests for:

- critical-policy ownership/parity;
- evidence fail-closed behavior;
- semantic verifier completeness and outage handling;
- party-role, service/SLA, money and adversarial field routing;
- per-equipment evidence and equipment claim conflicts;
- service list and residual critical claims;
- multi-chunk conflicts;
- auth reviewer provenance;
- critical-review completion;
- CSV formula-injection protection;
- production security configuration.

## Runtime closure still required

1. Run `scripts/step18_safety_gate.ps1` with `MEDFLUX_UNIT_ONLY=1`.
2. Run the real Accutron production extraction at temperature 0.
3. Assert the canonical 27/27 benchmark and no invented critical facts.
4. Verify minimum-duration field evidence and `billing_interval=other` exclusion in the real pipeline.
5. Run DB-backed auth/tenant isolation gates.
6. Run frontend TypeScript/lint/build.
7. Run the full backend regression suite once targeted gates pass.

## Closure invariant

No critical extracted value is operationally trusted solely because an LLM emitted schema-valid JSON. Missing, contradictory, unsupported or unverifiable evidence fails closed to human review.
