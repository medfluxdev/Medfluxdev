# Equipment occurrence identity: persistence correction plan (source review, 2026-09-30)

Status: DESIGN / NOT IMPLEMENTED / TESTS NOT EXECUTED. Do not interpret this as release acceptance.

## Verified source-level failure

`v3.py` preserves distinct equipment facts when their complete serialized rows differ, including distinct evidence. `DocumentProcessingService._build_extraction` persists per-item evidence refs `identity_equipment.evidence.<index>`. However, `database/services.py::_equipment_fingerprint` hashes contract ID and a limited identity tuple; `add_equipment` returns the first matching row in the same extraction. `contract_equipment` also has `uq_contract_equipment_contract_extraction_fingerprint`. Consequently two separately evidenced physical units with the same name/model and no unique identifier collapse. Existing STRICT XFAIL: `test_distinct_same_name_units_without_identifiers_remain_separate`.

## Constraints

1. Preserve a stable *semantic* fingerprint for cross-reanalysis work-item lineage where the identity is genuinely known. Do not blindly add `equipment_index`: row order can change.
2. Represent a separate *occurrence* of each extracted device/coverage row within one extraction. An occurrence must retain its own `field_ref`, `equipment_index`, evidence, scope and review state.
3. Identical repeated extraction facts must be deduplicated before persistence only when the full item including evidence and scope is identical; two rows with the same name/model but different verified source or scope must not be merged automatically.
4. Missing/ambiguous unique IDs require manual review; never infer that two same-name rows are the same physical unit, nor that different quotes guarantee distinct physical units without review.
5. Historical extraction rows stay immutable and remain excluded from *current* catalog links. Preserve organization scoping and existing unique-serial master resolution policy.

## Implementation sequence (requires schema design and owner-approved DB validation)

- Introduce a dedicated nullable `occurrence_fingerprint` for each `contract_equipment` row. Backfill historical rows with a deterministic unique value per existing row without rewriting their existing `logical_fingerprint`. Plan a staged migration with rollback and index creation.
- Replace the current uniqueness constraint on `(contract_id, extraction_id, logical_fingerprint)` with a uniqueness rule for `(contract_id, extraction_id, occurrence_fingerprint)` after backfill. Preserve logical fingerprint for compatible legacy readers.
- Compute occurrence identity from canonical row data plus normalized, source-verified evidence identity when present. For ambiguous same-content rows with distinct source locations, keep distinct occurrences and flag review. When no stable source identity exists, avoid promising stable cross-reanalysis identity; use per-extraction occurrence identity and explicit review.
- Update `add_equipment` idempotency to compare occurrence identity rather than logical fingerprint. Keep the existing master identity lookup separate; never merge anonymous devices by name/model.
- Update equipment work-item derivation so distinct unresolved occurrences do not collide under the old shared `_fp_source` while known, stable identifiers continue to reconcile across reanalysis. Define how a reviewed work item is carried forward when source order changes, and when to create a new review item instead.
- Check all catalog/detail, reanalysis replacement, source-navigation, and archival paths for assumptions of one logical fingerprint per extraction.

## Required acceptance cases

- Two separately evidenced same-name/model units without serials: two persisted rows, distinct evidence refs, distinct review tasks; no invented unique IDs.
- Exact repeated fact with identical evidence/scope: one persisted occurrence after harness deduplication.
- One identified physical unit in two accepted coverage scopes: two coverage links, one canonical master, one distinct contract count.
- Reanalysis with reordered evidence: correct current links and review lineage; old rows remain auditable and invisible in current catalog.
- Cross-org serial collision cannot expose or merge other organizations' equipment.
- Run migration on representative PostgreSQL snapshot, then real multi-page PDF/DOCX, API and UI navigation, and final consolidated owner-approved acceptance.

No schema change is included in this document.
## Additional verified blocker: same identified unit, distinct service scopes

A separate source review found that `_equipment_fingerprint` also omits `service_scope`, coverage dates, included/excluded services and evidence. Two separately sourced coverage rows with the SAME device name and serial but different service scopes collapse under `add_equipment` before they reach the catalog. The earlier distinct-contract count regression intentionally used two different device names, so it does not cover this case. Added STRICT XFAIL `test_same_identified_device_keeps_two_distinct_coverage_scopes` (`547527c`), source-only and not executed. The occurrence migration must preserve *both* rows linked to the same canonical master while counting their contract once; do not solve the anonymous-unit collision by making serial-only rows unconditionally idempotent.
