# Ahmed requirements reference — supplied 2026-10-01

Source materials supplied directly by Jamal:
1. `هيكل التنظمي للمؤسسة (1).docx` — organizational structure, 16 numbered sections.
2. `first-doc 26.09.2026(1).docx` — phase-one contract intelligence, review, reminders and cost analysis.

**This file is a requirements digest, not a byte-identical archive of the original DOCX attachments.** Preserve the original attachments separately; do not treat this digest as a replacement for their exact text, examples and formatting. No original DOCX or contract PDF was committed.

## Organizational structure (source document)

- Einrichtung → one or multiple Krankenhäuser → unlimited-depth natural organizational tree. Examples of nodes: Klinik, Abteilung, Bereich, Station, Funktionsbereich, Einheit. No fixed depth or universal hospital hierarchy.
- Medizintechnik, IT, Radiologie, Kardiologie, Einkauf etc. stay in their real tree locations. Do NOT nest a beneficiary department under a responsible department just because of one contract.
- Import and contract editing must display an obvious `Organisation` section with:
  - `Krankenhaus` (filter subsequent unit options to the selected hospital).
  - `Verantwortlicher Bereich`: **one** department responsible for managing the contract.
  - `Nutzender Bereich`: **one or multiple** beneficiaries, with `+ Weiteren nutzenden Bereich hinzufügen`.
  - `Kostenstelle`: cost center, preferably suggested from the chosen department; a department may have multiple cost centers.
- Display full unit ancestry in pickers to disambiguate repeated names (e.g. Medizinische Klinik › Kardiologie › Herzkatheter).
- Search by cost-center number and show associated unit/hospital.
- `Einstellungen → Organisationsstruktur`: tree view and authorized create/edit/activate/deactivate of units/subunits and cost centers.
- Saved contract details must display hospital, responsible department, beneficiary departments and cost center, editable later.
- Keep normal import UI simple; organizational hierarchy and contract-specific roles must remain separate.
- Example PACS contract: responsible IT, beneficiaries Radiologie/Kardiologie/Notaufnahme; other examples include Medizintechnik responsible for radiology device service.

## First-phase contract processing (source document)
- Extract vendor, start/end dates, price, duration, cancellation notice, automatic renewal, payment frequency (monthly/yearly), prepaid status, tax-inclusive/exclusive amounts and ideally both normalized amounts, annual escalation versus fixed pricing.
- After extraction, request user confirmation before accepting/persisting verified contract facts; offer an explicit option to bypass manual confirmation with automatic acceptance. Each fact should indicate manual extraction, AI extraction, or agreement between both.
- Calculate and notify on approaching expiry, cancellation deadline, auto-renewal, next payment/maintenance. Notify the responsible person in the responsible department, optionally other users/head of department, with configurable in-app/email channels.
- Analytics: active/expired/expiring counts; annual per-contract cost; total costs; cost distribution by department, contract type and vendor; most expensive contracts; pending renewal decisions; navigation Einrichtung → department → contract; frontend charts and dedicated analytics area.

## Acceptance checklist — import UI
1. Select hospital within current Einrichtung; do not silently assign an arbitrary default.
2. Select one responsible department within that hospital.
3. Add/remove multiple beneficiaries within that hospital, displaying full tree paths.
4. Select relevant cost center; expose linked centers and number search.
5. Review organization selection before upload; persist roles and verify them in saved contract details and subsequent editing.
6. Server-side validation and authorization must reject cross-hospital/organization IDs and invalid role combinations.
7. Preserve the existing isolated trial and immutable stable reference; implement changes on a separate reviewed branch.

## Observed gap 2026-10-01
Jamal's import screenshot shows a target-region summary and PDF/DOCX dropzone, but not the expected hospital/responsible/beneficiary/cost-center input workflow. Backend already has contract-department role models/tests, but end-to-end UI parity with the source requirements is NOT verified. This is an implementation gap to investigate, not a request to redesign the approved requirements.
