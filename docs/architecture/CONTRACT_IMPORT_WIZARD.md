# Contract Import Wizard — user-selected ownership and approval path

**Status (2026-10-10):** implemented on `feature/developer-hub-import-wizard` – wizard step „Erfassung“, server-side mode validation, `contract.intake_mode`, manual capture with stored original, batch confirmation, failed-imports list. Deviation: no separate import-intent endpoint; the existing import route validates destination and mode atomically (allowed by this spec). Duplicate protection is the existing SHA-256 dedupe per organisation. The per-field AI/manual/both display and evidence review reuse the existing Prüfung and provenance. Original text: Owner requirement on 2026-09-26. Work on isolated architecture branch; reconcile against currently uncommitted local Visual-First experiment prior to code edits.

## Product decision
**The import screen must ask these questions BEFORE creating an import/processing run:**
1. Which authorized organization/hospital/department (and optional cost center) owns this contract? Default to the user's single authorized department when unambiguous, but show it explicitly for confirmation; do not allow unauthorized department selection.
2. Which ingestion/approval workflow?
   - `ai_direct` — AI proposes, independent deterministic source verification runs; only verified fields within hospital's explicit auto-approval policy become accepted. Any low-confidence, ambiguous, conflicting or high-impact money/date/termination claims require review and stay pending. Never silently commit all generated fields.
   - `manual` — save immutable original, open structured data entry form, attach original-page evidence for critical facts, validate user permissions, persist reviewed manual snapshot and audit identity.
   - `ai_human_review` — AI extraction + independent evidence validation, then editable side-by-side source and fields. User accepts/rejects/edits each critical fact. Persist confirmed final snapshot with per-field provenance, identity and decisions. **Recommended default** until auto-approval has passed real-contract evaluation.
3. Confirmation summary: selected owner, cost center allocation or unallocated, mode, permitted destination, any automatic acceptance limitations. Explicit user confirmation triggers import.

## UX flow
`Select source PDF/DOCX -> Select authorized destination -> Choose mode -> Review settings/confirm -> Upload -> (AI or manual) -> Evidence review where applicable -> Accept snapshot -> Event-based calculations/notifications`.

Batch uploads must not implicitly assign one contract's department to unrelated documents: show an explicit per-document destination/mode override or confirm all belong to the same department, otherwise require individual import.

Suggested visible German labels:
- `Wohin soll der Vertrag zugeordnet werden?` Institution / Krankenhaus / Abteilung / Kostenstelle (optional).
- `Wie möchten Sie die Vertragsdaten erfassen?`
- `KI-gestützt (automatische Übernahme nur verifizierter Angaben)`
- `Manuelle Eingabe`
- `KI-gestützt mit manueller Prüfung`
- `Unklare oder widersprüchliche Angaben werden nicht automatisch bestätigt.`

## Trust and persistence
Separate dimensions: **extraction method** AI / manual / AI+manual, **verification** source-correlated/needs review/rejected, **approval** authorized auto-policy/manual approved/pending; do not merge these into one boolean. Preserve original AI candidate and reviewer correction, independent citation, revision, actor and timestamp for every critical field. `MANUAL` means operator-entered, not automatically verified correct. `AI_DIRECT` is a policy-governed workflow, NOT an exemption from review of uncertain/high-risk clauses.

Owner assignment and allocation are different: a contract may have a primary responsible department and share costs across cost centers; do not book full amount to every linked department. A later owner correction is audited and does not rewrite immutable original or previous accepted snapshot.

Backend preflight must enforce allowed hospital/department and optional cost center, role permission for chosen mode (especially direct acceptance), allowed MIME/size and duplicate/revision policy. Never trust client-supplied `organization_slug` or `department_id` for authorization. A `scope context` derived from authenticated server principal is mandatory.

Suggested boundary: `POST /api/documents/import-intents` takes destination IDs/mode and creates a server-validated, short-lived, user-bound intent; existing document import references it on upload; service persists mode/destination before processing and launches the correct workflow. Alternatively atomically validate posted config in existing import route; never make separate unauthenticated configuration storage. Use explicit idempotency key to prevent duplicate imports or processing after retry.

Failure/interrupt policy: uploads preserve immutable original and explicit pending state; manual drafts can resume; AI outages cannot magically switch workflow mode without consent; erroneous automatic assumptions remain review-required. Only an accepted version triggers authoritative financial forecasts and notifications.

## Repo integration map from direct source inspection
Current `frontend/app/import/page.tsx` imports files using `importDocuments(selected,effectiveOrgSlug)` and does not visibly gather the desired mode/destination in the inspected 1–135 lines. Existing `backend/app/api/routes/documents.py` has an authoritative `DocumentProcessingService`, bounded upload and scoped validation. `backend/app/api/routes/organization_structure.py` exposes scope-filtered institutions/departments. Inspect entire files and current experimental branch before adding wizard; reuse the existing processing path and avoid a second ungoverned import route.

## Acceptance tests (release gate)
- [ ] No upload proceeds before mode and scope confirmation.
- [ ] Scoped non-admin cannot select a foreign hospital or department by altered HTTP payload; no metadata leakage.
- [ ] Department assignment and cost center allocation remain separate and visible, including shared contracts.
- [ ] Manual path can submit/pause/resume/correct and audit source/evidence.
- [ ] AI+human path cannot mark pending claims as confirmed before authorized user review.
- [ ] AI-direct path respects explicit policy, does NOT accept unproven money/date/renewal or visual page guesses; policy disabled by default until acceptance.
- [ ] Per-field AI / manual / both, approval state and exact page evidence are displayed after import.
- [ ] Failed retries preserve original selected workflow and do not send duplicate reminders.
- [ ] Safe batch imports require explicit same-destination confirmation or per-file configuration.
- [ ] Clean-up inventory and repeat targeted + existing full regression suite, source provenance and end-to-end on isolated branch before any integration.
