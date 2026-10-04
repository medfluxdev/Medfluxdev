# HYDMedia hospital contract-workflow reference

> **Status:** source-of-truth reference for MedFlux workflow/product decisions.
>
> **Evidence reviewed:** 107 screenshots supplied from the hospital's current HYDMedia Business Workflow environment (14 Sep and 1 Oct 2026). This document records what is visible in those screenshots. It must not be treated as a claim about screens or behavior that were not captured.

## Why this reference exists

The screenshots show the real contract-management workflow MedFlux is intended to assist. The current environment is HYDMedia Business Workflow / contract management. Staff work from large contract tables and open modal/detail forms to enter, select, review, and maintain structured contract data. MedFlux should therefore optimize for **extract -> verify -> map -> hand off structured values**, rather than producing only a prose contract summary.

## Observed workflow

1. **Contract overview / selection**
   - Central `Verträge` list with status indicators and contract numbers.
   - Large configurable data grids with many columns.
   - Filtering/grouping/search and report/export-oriented UI are visible.
   - Views include grouping/selection by organisational/company context.

2. **Contract master/detail form**
   - A selected contract opens a dense `Vertrag bearbeiten` form.
   - Visible master-data concepts include contract number, company/entity, department, contract type/category, description/subject, responsible/assigned context and status-related fields.
   - Multiple values are selected from lookup dialogs rather than inferred automatically.

3. **Contract subject / object**
   - Dedicated `Vertragsgegenstand` / subject area is visible.
   - Free-text/description fields are used alongside coded/lookup values.

4. **Financial data**
   - Dedicated `Finanzdaten` area.
   - Financial rows can be created/edited/deleted and exported.
   - The UI distinguishes recurring/current-year style values and displays net/gross/VAT-related amounts.
   - Separate entry dialogs contain amount/period/value fields.
   - This is a major MedFlux target: extracted financial facts must retain evidence and units/periodicity instead of being collapsed into one generic “cost” value.

5. **Dates / deadlines**
   - Dedicated `Termine` area with an entry dialog.
   - Captured date/deadline information is structured, not merely narrative.
   - MedFlux should preserve explicit date literals, semantic date type, conditions and evidence.

6. **Services / performance**
   - A dedicated `Leistung` entry flow is visible.
   - MedFlux should preserve individual service/performance items where the contract contains them instead of flattening all content into a generic subject.

7. **Remarks**
   - Dedicated `Bemerkung`/remarks entry exists.
   - Free text remains part of the workflow even where structured fields exist.

8. **Documents**
   - A document tab/area is present in the contract detail workflow.
   - The workflow therefore combines structured metadata with the underlying contract/document record.

9. **History / audit trail**
   - Dedicated `Historie` view shows dated/user-associated changes.
   - MedFlux must preserve provenance: extracted value, evidence location, confidence/review state, and subsequent human corrections.

10. **Framework/linked contracts**
    - `Rahmen Verknüpfung` / framework linkage is visible through a contract-selection dialog.
    - Contract relationships are first-class workflow data and should not be represented only as free text.

11. **Status**
    - Contract list contains visually distinct status values.
    - Status is a structured operational property and should remain separate from extraction confidence/review status in MedFlux.

12. **Administration**
    - Screens show administration for categories/types, organisational/master-data lists and other lookup/configuration data.
    - These values are often chosen from controlled lists.
    - MedFlux should map extracted text to controlled HYDMedia-like target values only when mapping is supported; otherwise retain the literal and flag for review.

13. **Roles and workflow users**
    - Screens show roles/workflow-role configuration and user/application assignments.
    - This confirms the hospital process is role-aware. MedFlux should not assume every reviewer/approver is interchangeable.

## Product implications for MedFlux

### Core principle

**The target is not “AI reads a PDF.” The target is “AI removes as much manual HYDMedia data entry as safely possible.”**

### Required extraction model

MedFlux should model at least these target families:

| Target family | Required MedFlux behavior |
|---|---|
| Contract identity | contract number, title/short description, contract type/category |
| Parties / organisations | supplier/contract partner, internal company/entity/department where evidenced |
| Contract subject | structured subject plus literal description/evidence |
| Equipment / products | preserve explicit equipment/device names as individual items |
| Duration | explicit duration literal + normalized duration where safe |
| Dates / deadlines | date literal + semantic type + condition + evidence |
| Financial data | amount + currency + net/gross/VAT + periodicity/period + evidence |
| Services | individual service/performance items |
| Status | business status separate from AI validation state |
| Relationships | framework/parent/linked-contract references |
| Documents | source-document identity and page/evidence references |
| Remarks | human/free-text notes kept separate from extracted facts |
| Audit | who/what/when for AI extraction, review and corrections |

### Human-in-the-loop rule

When a target value cannot be supported by contract evidence or a deterministic mapping, MedFlux should **not invent a HYDMedia value**. Keep the source literal, show the evidence, and request human confirmation.

### UI direction

The hospital screenshots favor dense operational data entry over conversational output. MedFlux's review UI should therefore provide:
- a compact contract overview;
- target-field mapping;
- evidence beside each extracted value;
- explicit missing/ambiguous states;
- fast keyboard-friendly correction;
- clear distinction between source literal and normalized value;
- grouped financial/date/service/equipment items;
- audit history of accepted/rejected/corrected values.

## Screenshot-set coverage

The reviewed set contains **107 PNG screenshots**. Named captures include:
- contract overview/status/company views (`vertrage 1-6`, `vertrage nach gesllellschaft`);
- contract detail captures (`vertrage 7 details` through `vertrage 11 details`);
- `vertraggegenstand`;
- `Rahmen verknupfung`;
- `finanzdaten 1-4`;
- `Termine 1`;
- `leistung1`;
- `bemrkung`;
- `historie 1`;
- `doku 1`;
- roles/workflow-user captures;
- administration captures `admin 1-14`;
- additional timestamped screenshots showing the same operational areas and lookup tables.

## Important limitation

This reference describes the captured hospital screens. It does **not** establish database schemas, API availability, mandatory-field rules, hidden validation rules, or every possible HYDMedia workflow. Those require direct system/configuration/API evidence.

## External product context (secondary, not screenshot evidence)

Dedalus' public HYDMedia material describes contract management as a BPM/workflow use case involving import, review/approval, deadline management, contract lifecycle, master data, contract partners and cost centres. This is consistent with the broad workflow visible in the hospital screenshots, but product documentation must remain secondary to the hospital evidence when MedFlux behavior is designed.

## Decision rule for future MedFlux work

When changing extraction fields, validation, review UX or export/mapping behavior, check this reference first. Prefer compatibility with the observed hospital workflow. Do not remove or merge target concepts merely because a test contract does not contain them.

---
Source package supplied by Jamal from hospital screenshots, reviewed 2026-10-01.
