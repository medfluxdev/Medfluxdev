# MedFlux as a Complete AI Contract Manager: Gap Analysis against a Real Legacy System (HYDMedia) and Step-by-Step Plan

**Date:** 2026-10-04 (rev. 2: product direction confirmed)

> **Product direction (decided 2026-10-04 by the product owner).** MedFlux **replaces** classic contract-management software such as HYDMedia. HYDMedia is used here only as a **real-world reference** for the basic functions every hospital contract manager must have. MedFlux keeps these basics and adds its own advantage on top: **local AI** that analyses contracts, fills in data, checks it and advises, without contract content ever leaving the hospital.
>
> MedFlux = **(1) a complete, modern contract manager that works fully without AI** + **(2) a local AI layer on every function**.
>
> HYDMedia is **not** copied 1:1, and MedFlux is **not** an add-on to it. We adopt the functions and the domain knowledge (fields, catalogues, status workflow, deadline rules, reminders, finance logic). We do not adopt its desktop UI, its weaknesses or its data-quality problems.
**Source of evidence:** `design-reference/hospital-workflow/ahmed-hospital-current-workflow-2026-09-14.zip`. The zip has 107 PNGs, of which 56 are unique; the rest are duplicates. They were captured on 14.09.2026 and 01.10.2026 from the hospital's production system, **HYDMedia Business Workflow – Contracts module**.
**Compared against:** MedFlux `main` at `f46238e`. That includes the code inventory, `docs/architecture/WORKPLAN_ORGSTRUKTUR_PHASE1_20261003.md`, `CONTRACT_IMPORT_WIZARD.md`, `COST_CENTER_INTELLIGENCE.md` and `docs/BRANCH_UNIFICATION_20261004.md` §4.
**Related:** `docs/references/HYDMEDIA_HOSPITAL_WORKFLOW_REFERENCE.md` gives the high-level observations. This document goes field-by-field and turns the result into an executable plan.

> Privacy note: this document contains no personal names, emails, personnel numbers or vendor-identifying data from the screenshots. The screenshots themselves stay outside git.

---

## Implementation status

| Phase | Status | Date | Commits / notes |
|---|---|---|---|
| H0 | done (privacy fix; screenshots still to request) | 2026-10-04 | `87ccbee` |
| H1.1–H1.5 register core, term engine, status workflow, numbering, manual creation | done | 2026-10-04 | `cac5d0e`, `86958e9`, `1014c60`, `b587775` |
| H2.1–H2.5 partners, types/categories, lookups, multi-hospital, admin UI | done | 2026-10-04 | as above |
| H6.1 remarks journal, H6.2 contract history tab + organisation-wide history with filters and CSV export | done | 2026-10-04 | as above, `6e6518c` |
| H5.1–H5.4 deadlines, daily job, e-mail/ICS, deputies, inbox | done (D5: in-process opt-in or Task Scheduler; D6: SMTP optional) | 2026-10-04 | `2695467`, `68ed23f` |
| H3.1–H3.3 documents, amendment proposals, framework links, import destination | done | 2026-10-04 | `db16dd7`, `6145003`, `50501e6` |
| H4.1–H4.3 finance entries, service catalogue, cost-centre split, price adjustment, AI suggestions | done | 2026-10-04 | `c53082e`, `d9fd4fb`, `c1f1cf5` |
| H8.1–H8.2 permission matrix, confidential contracts with grants, „Rollen & Rechte“ page | done | 2026-10-04 | `e948586`, `662771c` |
| H9 retention per type/contract, „Löschen ab“, retention review deadline, AI data-protection flag | done | 2026-10-04 | `e948586`, `662771c` |
| H7.1–H7.5 register grid (columns, filters, grouping, sums), saved views, tree, Excel export, portfolio report, analytics, cover-sheet PDF | done | 2026-10-04 | `da4e646` |
| 13a renewal briefs (advice only) and renewals overview | done | 2026-10-04 | `ec29d83`, `c8d5582` |
| Open from §4A | semantic search across contract contents; AI narrative for briefs; dark theme for charts (app has no dark theme) | – | – |
| H10 | on hold (no replacement agreement yet) | – | – |

## 0. Executive summary

**What HYDMedia is.** HYDMedia is a **manual contract register on top of a DMS**. It has:
- about 2,540 contracts and about 1,281 contract partners;
- 24 contract types and 68 categories;
- a 5-state status workflow;
- notice-deadline calculation from term data;
- reminders sent by a nightly e-mail job, with escalation and deputies;
- finance entries (income and expenses, net/gross/VAT, validity periods) with current-year, to-date and to-end aggregation;
- a service price list, typed attachments, framework-contract linkage, an append-only remarks journal, an audit history;
- configurable lookup catalogues, number ranges, saved workspaces, grid grouping, filtering and export, and report templates.

**There is no AI, no source evidence and no data validation.** Device and serial numbers are buried in free text, the catalogues contain duplicates, and every value is typed by hand.

**What MedFlux is.** MedFlux is an **AI-first analysis system**. It has local extraction with evidence, deterministic deadline and cost calculation, warnings, a work queue, an org tree with responsible and beneficiary departments, an equipment registry, and fact review.

**But MedFlux is not yet a contract register.** A contract only exists if a document was uploaded and analysed. Most business fields live only inside an extraction JSON snapshot. They cannot be created or edited freely, and there are no partner or type catalogues, no reminders that are actually sent, no remarks, no attachments to existing contracts, and no framework hierarchy.

**The strategic conclusion.** To replace HYDMedia in daily use, MedFlux needs two layers:
- **Layer 1 (Basis):** every basic function of a classic contract manager, as first-class, editable and audited data that works even with the AI switched off.
- **Layer 2 (AI):** for every basic function, the local AI removes manual work. It pre-fills fields with evidence, matches partners, classifies contracts, turns amendments into change proposals, proposes deadlines and finance entries, checks consistency and answers questions. The AI is a **source of proposals**, never the only source of truth.

§4 contains the step-by-step plan for Layer 1. §4A explains for each module what Layer 2 adds.

**The plan has 11 phases (H0–H10).** They are ordered so that each phase is shippable on its own, migrations stay additive, and the core invariants hold:
- AI proposes, code computes, humans decide.
- `DocumentProcessingService` remains the single processing path.
- Contract content stays local.

---

## 1. What the real program does (consolidated feature inventory)

Screenshot IDs refer to the capture time, e.g. `152449` = `Screenshot 2026-10-01 152449.png`. `admin N` is the user's file label.

### 1.1 Shell and navigation
- **Layout.** A desktop client with three areas: **Contracts**, **Rollen/Workflows** and **Administration** (all screens).
- **Navigation panel.**
  - "Favoriten" holds saved searches, e.g. "Vorauswahl".
  - The "Suchstruktur" tree has the nodes "Verträge", "Verträge nach Gesellschaft" (company → department) and "Abteilungen" (151907, 153659).
- **Main tabs.** "Dokumente" (contract list), "Postfach (n)" (an inbox with a pending count) and "Administration".
- **Status bar.** Shows the user, the **active role**, the layout ("Standard"), the date and the record count.
- **Menus** (3–7.png, Screenshot_2):
  - Bearbeiten: select all, invert selection, copy cell, search in tree.
  - Ansicht: "Feldauswahl" (column chooser), "Vorschau" (F12), expand/collapse groups.
  - Extras: "Suchen", "Suche vertiefen", "Export Datengitter…" (F8), "Rolle wechseln", "Vertreter", "Arbeitsbereiche konfigurieren…".
  - Berichte: "Bericht erzeugen…".
  - ?: help, keyboard shortcuts, remote support.

### 1.2 Contract list (grid)
- **Search and filtering.**
  - Quick search across Status, Vertragsnr., Kurzbeschreibung, Vertragspartner and more.
  - Every column has a filter offering "(Alle)", "(Benutzerdefiniert…)", "(Leer)", "(Nicht leer)" and its distinct values (152401).
- **Grid controls.**
  - "Gruppierungsfläche": drag a column there to group, multi-level.
  - Sort on any column, a column chooser, a clear-filters button and coloured status badges.
- **About 50 available columns** (151907, 152054, 152153, 152242, 152318):
  - Status, Vertragsnr., Kurzbeschreibung, Erstelldatum, Ersteller, Vertragspartner, Vertragstyp, Kategorie, Vertragsart.
  - Dates and deadlines: **früh./festes Vertragsende**, **kündbar bis**, **gekündigt am**, **mögl./tatsächl. Vertragsende**, **Erinnerung (am)**, **Gekündigt zu**, Vertragsbeginn.
  - Organisation and storage: Abteilung, Standort (paper storage), **Anhang** (attachment count), Gesellschaft, Mandanten, Int. Nr., Kontonummer, Bereich.
  - People: Verantwortlich, **Erinnerung an**, **Eskalation an**.
  - Money: **Kosten laufendes Jahr**, **Kosten Laufzeit**, **Einnahmen laufendes Jahr / Laufzeit**, and net/gross expense columns, including custom computed fields (`CUSTOM_AUSGABEN_MOEGL_VERTNDE_N`, `CUSTOM_AUSGABENBISENDE_BRUTTO`).
  - Flags and retention: **Rahmenvertrag** (☐), **Löschen ab Ende**, **Manuelle Abrechnung** (☐).
- **Status transitions.** A "Statuswechsel" bar above the list offers only the transitions allowed for the selected row and role (152153, 152242).

### 1.3 Contract master record ("Vertrag bearbeiten", 152449–152755, 152921)
**Header fields:**

| Field | Type | Required |
|---|---|---|
| Vertragsnummer | auto, 6-digit, read-only | system |
| Int. Nr. | text | – |
| Rahmenvertrag | checkbox | – |
| Mandant › Gesellschaft | lookup, **multi-select** | – |
| Mandant › Abteilung | lookup, **multi-select** | – |
| Lagerort | lookup (where the paper original is kept) | – |
| Manuelle Abrechnung | checkbox | – |
| Verantwortlich | user lookup | **yes** |
| Vertragspartner | partner lookup, with "Vertrags-P. anlegen/anzeigen" | **yes** |
| Bereich | lookup, with "Bereich anlegen" | – |
| Kurzbeschreibung | text | **yes** |

**Tab "Vertragsdaten":**

| Field | Type | Required |
|---|---|---|
| Vertragstyp | lookup | **yes** |
| Kategorie | lookup, filtered by type | **yes** |
| Laufzeit (= Vertragsart) | Feste Laufzeit / Kündbarer Vertrag / Kündbarer Vertrag mit Mindestlaufzeit / Automatische Verlängerung / Ewige Laufzeit | **yes** |
| Vertragsbeginn | date | **yes** |
| Kündigungszeit | number + unit (Monat(e) …) | **yes** |
| Kündigung zum | e.g. **Quartalsende** (Monatsende/Jahresende inferred) | **yes** |
| → mögl. Vertragsende / bei Kündigung bis | **computed**, read-only | – |
| Erinnerung am | date (example: notice deadline − 3 months) | – |
| Erinnerungsneuberechnung | interval ("monatlich") + n Monat(e) lead time | – |
| ToDo | template text, from the ERINNERUNGSTODO catalogue | – |
| ToDo erledigt | button: acknowledge, then recalculate | – |
| Erinnerung an / Eskalation an | user lookup | **yes** |
| Gekündigt am / Gekündigt zum | dates | – |
| Löschen ab Ende | integer (retention, in years after end) | – |
| Kontonummer, Kostenstelle | text | – |

**Other tabs:**
- **Finanzdaten** (152921–153054):
  - Entries have Typ (Einnahmen/Ausgaben), Bezeichnung, Gültig ab (month/year), Gültig bis (optional), Betrag with a Netto/Brutto basis, Steuer %, and a remark.
  - Aggregates are calculated **on whole months** for laufendes Jahr, bisher, bis Vertragsende and Gesamt-Laufzeit, each as net and gross, separately for income and expenses.
  - Buttons: "Finanzdaten aktualisieren" and an export of income and/or expenses.
- **Termine** (153135):
  - Several deadlines per contract, each with Zuständig, date, Art (catalogue), Termin-Typ, ToDo and remark.
  - Options: "Erinnerungs Mail" and "ICS-Datei senden".
  - "Termin erledigt" marks a deadline done; each has an open/done status.
- **Gegenstand** (153202): a single free-text field.
- **Leistungskatalog** (153227): service rows with Leistung, Leistungsart, Betrag, "zzgl. USt" (flag), Gültig ab/bis and a remark.
- **Dokumente** (153259):
  - Several documents, each with Pos., **Hauptdokument**, **Gültig**, date/time and Bezeichnung.
  - Actions: create, add, show, edit metadata, delete, "als Hauptdokument festlegen".
  - Typical set: the contract, an internal routing slip ("Laufzettel"), a vendor self-declaration.
- **Bemerkungen** (153404): an **append-only** journal ("Neue Bemerkung" plus a read-only history).
- **gehört zu Verträgen** (153431):
  - Link the contract to a framework contract; the picker shows only contracts flagged as framework.
  - Unlink, and save the link as a favourite.
- **Historie** (153503): Seq., date/time, user role, user name. Events only, no field diffs.
- **Form usability:** previous/next record without closing, "Beim Speichern nicht schließen", and the required fields highlighted.

### 1.4 Status lifecycle (152401, 152153, 152242)
`In Arbeit` → `Gültig` → `Gekündigt` | `Beendet`; `Beendet` → `Gelöscht` (soft delete) | `Gültig` (reactivate). Transitions depend on the current state and the user's role.

### 1.5 Administration catalogues (admin 1–14)
| Catalogue | Content |
|---|---|
| Arbeitsbereiche | saved views: "meine Wiedervorlage", "zum Löschen vorgesehen", "gelöschte Verträge", "Verträge ab 2017" |
| Monitoring | heartbeat of the nightly batch job ("Verarbeitungslauf") |
| Vertragstypen (24) | Wartung, Lizenz, Miete, Leasing, Kauf, Dienstleistung, Dienstvertrag, Werkvertrag, Versicherung, Versorgung, Kooperation, Mitgliedschaft, Darlehen, Kredite, Erbbaurecht, Nutzung, Leihe, Sponsoring, Drittmittel, Med. Versorgung, Auftragsverarbeitung, Sonstige Dokumente, **vertraulich** … |
| Kategorien (68) | n:m mapped to types (Software, Medizingerät, Röntgengerät, Laborgeräte, Haustechnik, Hardware, IT, Energie, Kfz, Gebäude, §116b, Studie, …); contains duplicates |
| Vertragspartner (1,281) | Kurzname, Name1/2, Anzeigename, address, Postfach, phone, fax, web, Branche, Typ, Klasse |
| Bereiche | sub-areas or contact areas per partner |
| Mandanten / Gesellschaft | the group's legal entities (hospitals, specialist medical centre, senior homes, care company, foundation) |
| Nummernkreise | contract number sequence, each number free / in use / reserved, plus the user who drew it |
| Nachschlagefelder (114) | generic lookups: ANLAGENTYP (26 attachment types: Nachtrag, Kündigung, Kündigungsbestätigung, AVV, Angebot, Rechnung, Addendum, Vergütungsvereinbarung, …), LAGERORT, ART (follow-up types), **ERINNERUNGSTODO** (Verlängerung prüfen, Vertrag kündigen?, Gekündigt → Kündigung dokumentieren, Beendet → Vertrag auf beendet setzen, …), WAEHRUNG, KOSTENSTELLE, **WEITERBELASTUNG** (teilweise/vollständig), BRANCHE, ADRESSART, ANREDE, FUNKTION, ABTEILUNG |
| Berichte | report templates per table, e.g. "Deckblatt" (cover sheet) |
| Historie (219k) | global audit of user **and system** actions, e.g. "Erinnerungsmail gesendet, Empfänger …" |
| Dokumentenarten | document class → workflow, accepted file mask (*.pdf) |
| Vertreter | deputy per user with Von/Bis and an active flag |

### 1.6 Users, roles and workflow (153738–153915)
- **User fields:** login, Langname, Funktion, E-Mail, Telefon, **Vorgaberolle** (default role), Locked by System/Admin, Domain (AD), "Erhält Benachrichtigungen", "Erhält Erinnerungen", Gesellschaft, **Standardvertreter** (default deputy), Userlizenz.
- **Roles:** "ADMIN" and "ABTEILUNGS-VERTRAGSBEARBEITER". Permissions are granted per area: Administration, Suchstruktur, Pool, Persönlicher Arbeitsbereich, Postfach, Globale Layouts. The department role appears to see only its own department's contracts.
- **Workflow:** a single definition, "CONTRACTS – Workflow für Verträge"; the Postfach receives the workflow tasks.

### 1.7 Weaknesses of the real program (MedFlux opportunities)
- Everything is manual: no extraction, no evidence, no confidence.
- Reminder dates are partly maintained by hand. The lead time exists, but a wrong start date or notice value goes unnoticed.
- Device, serial and inventory numbers live in the Kurzbeschreibung text ("… SN 12345 (HG1411)").
- Catalogue duplicates, sparse partner records, near-duplicate vendors, raw `CUSTOM_*` field names visible in the UI, and pickers that show raw IDs or personnel numbers instead of names.
- History has no field-level old/new values.
- No dashboard, no risk view, no cost-centre allocation.

---

## 2. Gap matrix (HYDMedia capability vs MedFlux today)

Status: ✅ present · 🟡 partial · ❌ missing · ➕ MedFlux is ahead.

| # | Capability | HYDMedia | MedFlux today | Gap | Phase |
|---|---|---|---|---|---|
| 1 | Contract exists without a document / manual creation | ✔ | ❌ (only created by upload + analysis) | **critical** | H1 |
| 2 | Editable master fields (Kurzbeschreibung, type, category, term model, dates, notice …) | ✔ | 🟡 (fact review of about 20 fields + 4 override keys; values in extraction JSONB) | **critical** | H1 |
| 3 | System contract number (number range) + Int. Nr. | ✔ | ❌ (only the extracted `contract_number`) | high | H1 |
| 4 | Business status workflow (In Arbeit/Gültig/Gekündigt/Beendet/Gelöscht), role-gated | ✔ | 🟡 (computed status + lifecycle_state + decisions; no user-set business status) | high | H1 |
| 5 | Term model (5 Vertragsarten) incl. "Kündigung zum Quartalsende", "Ewige Laufzeit" | ✔ | 🟡 (renewal and cancellation relative to contract end; no "anytime to period end", no perpetual) | high | H1 |
| 6 | Termination record (gekündigt am / zum) | ✔ | 🟡 (lifecycle decision "terminate" + effective date) | medium | H1 |
| 7 | Vertragspartner master (address, Branche …) + inline create | ✔ | ❌ (`supplier` is plain text) | **critical** | H2 |
| 8 | Vertragstyp / Kategorie catalogues (n:m) | ✔ | ❌ (enum maintenance/service/lease/rental/other) | high | H2 |
| 9 | Generic lookup catalogues (Lagerort, Anlagentyp, Art, ToDo templates, Weiterbelastung …) | ✔ | ❌ | high | H2 |
| 10 | Several Gesellschaften per contract (group contracts) | ✔ | ❌ (one hospital) | medium | H2 |
| 11 | Several documents per contract, attach to existing, document type, Hauptdokument/Gültig | ✔ | 🟡 (`contract_document` roles exist, but no UI/API to attach) | **critical** | H3 |
| 12 | Framework ↔ individual contract link | ✔ | 🟡 (`contract_relation` table, nothing writes to it) | high | H3 |
| 13 | Finance entries (income/expenses, validity period, net/gross/VAT) | ✔ | 🟡 (extracted costs + calculation; no user-managed entries, no income) | high | H4 |
| 14 | Aggregates: current year / to date / to end / whole term, net and gross | ✔ | 🟡 (annualised cost; not stored, no current-year/to-date/to-end) | high | H4 |
| 15 | Leistungskatalog (service price list with validity) | ✔ | 🟡 (scheduled_prices / variable_charges in the extraction, not editable) | medium | H4 |
| 16 | Several cost centres + recharging (Weiterbelastung), Kontonummer, Manuelle Abrechnung | 🟡 (one Kostenstelle text field) | 🟡 (one cost_center_id) | medium | H4 |
| 17 | Termine (several, owner, type, ToDo, done) | ✔ | 🟡 (work items auto-derived; no user-created deadlines) | high | H5 |
| 18 | E-mail reminders, ICS invites, nightly job, escalation recipient | ✔ | ❌ (`remind_at` is stored but never sent) | **critical** | H5 |
| 19 | Deputies (Von/Bis) + per-user notification opt-in | ✔ | ❌ | high | H5 |
| 20 | Postfach (personal inbox with count) | ✔ | 🟡 (bell built from work items; no read state) | medium | H5 |
| 21 | Job monitoring (last run) | ✔ | ❌ | medium | H5 |
| 22 | Bemerkungen journal (append-only) | ✔ | ❌ (comments only on work items) | high | H6 |
| 23 | Contract history | ✔ (events) | ✅➕ (activity_log + fact reviews + overrides; per-contract UI) | low (global view missing) | H6 |
| 24 | Grid: column chooser, group-by, per-column filter, server-side saved views (Arbeitsbereiche/Favoriten) | ✔ | 🟡 (good filters; views only in localStorage; no grouping or column chooser) | high | H7 |
| 25 | Browse by Gesellschaft → Abteilung tree | ✔ | 🟡 (scope picker) | medium | H7 |
| 26 | Export of any grid (Excel), report templates (cover sheet PDF) | ✔ | 🟡 (one CSV, 10 columns) | high | H7 |
| 27 | Analytics / charts | ❌ | 🟡 (dashboard KPIs ➕; /analysen minimal) | medium | H7 |
| 28 | Permission matrix, role switch, confidential contracts | ✔ (simple) | 🟡 (4 roles, scope, inline checks) | medium | H8 |
| 29 | User profile (Funktion, phone, AD domain, lock) | ✔ | 🟡 | low | H8 |
| 30 | Retention "Löschen ab Ende" + Lagerort of original | ✔ | ❌ (soft delete exists) | medium | H9 |
| 31 | Import of the existing HYDMedia data | – | ❌ | **deferred** until a replacement agreement with the hospital | H10 (on hold) |
| 32 | AI extraction with source/page/confidence | ❌ | ➕ | – | keep |
| 33 | Deterministic deadlines + warning levels + dashboard | 🟡 | ➕ | – | keep |
| 34 | Equipment registry (serial/inventory numbers) | ❌ (free text) | ➕ | – | keep |
| 35 | Responsible vs beneficiary departments, org tree | 🟡 (flat departments) | ➕ | – | keep |

---

## 3. Design principles for the integration

0. **MedFlux must work without AI.** If the model is off or a document is not readable, users can still create, maintain, search, monitor and report on contracts fully by hand. The AI makes everything faster and safer, but it is never a precondition.
1. **Register first, AI on top.** Every basic field (taking HYDMedia as the reference) becomes a **contract field** with a stored current value that a user can edit. AI extraction becomes a **proposal source** for those fields, not the only source.
2. **Value provenance on every field.** Each field stores its origin and confirmation:
   - origin: `manual`, `ai`, `ai_confirmed`, `ai_corrected`, `imported_legacy`;
   - for AI values, `evidence_id` (page and region);
   - `confirmed_by` / `confirmed_at`.
   This implements WP3 (`review_mode`, `confirmed_both`) in one generic place.
3. **Code computes.** The possible end, the notice deadline, the reminder date, finance aggregates and status suggestions all come from `app/contracts/calculation`, never from the model. A computed value can be overridden manually only through the override mechanism, with an audit entry.
4. **Additive migrations only.** New tables and columns, backfilled from the accepted extraction. The extraction JSONB stays as the evidence snapshot.
5. **The business status is separate from the computed status and the review status.**
   - `business_status` is set by the user through the workflow (HYDMedia states).
   - `computed_status` (expiring, expired …) is derived by code.
   - `review_status` reflects the fact review.
6. **Catalogues are configurable per organisation**, have unique keys and an active flag, and ship with a **cleaned German hospital default set**. The HYDMedia lists serve as the domain reference for this set, with duplicates and misuse removed (e.g. "LOI" filed as a contract type).
7. **Single processing path.** Attaching a document to an existing contract still runs through `DocumentProcessingService`. The result is a **proposal diff** against the current register values, never a silent overwrite.
8. **A modern web UX, not a desktop clone.** Adopt the *functions*, not the layout: no 50-column grids or modal stacks as the default. Show names, not personnel numbers. Use smart defaults: category filtered by type, cost centre suggested by department, reminder date computed. Support keyboard navigation and previous/next record. Use dense power-user tables only where they help (lists, export).
9. **Avoid the legacy weaknesses on purpose.** Enforce uniqueness in catalogues, warn about duplicate partners, store structured device data instead of serial numbers in free text, keep field-level history, never show raw IDs or `CUSTOM_*` names, and check reminders and deadlines automatically instead of maintaining them by hand.

---

## 4. Step-by-step plan

Each step lists **Goal, Evidence, Backend, Frontend, AI integration, Tests and DoD**. DoD follows `CONTRIBUTING.md`: model + migration, API, scope, `lib/domain-api` consumer, UI states, audit event, backend and frontend tests, documentation, CI green. Sizes are S ≤ 2 days, M ≤ 1 week, L ≤ 2–3 weeks.

**Mapping to existing work packages:**
- H1.4 and the provenance part of H1.2 implement **WP3**.
- H4 implements **WP2**.
- H5 implements **WP4**.
- H7 implements **WP5**.
- H8 implements **WP6**.
- H1, H3 and H10 implement **CONTRACT_IMPORT_WIZARD**.

`docs/PROJECT_PROGRESS.md` must be updated after each step.

---

### Phase H0 – Preparation and decisions (S)

**H0.1 Product decisions.** Record the answers in this document, §6:
- **Replace or coexist?** **Decided: MedFlux replaces the legacy system.** Consequences:
  - MedFlux is the single master for all contract data. There is no synchronisation with HYDMedia and no export in HYDMedia format.
  - **Data migration is out of scope for now.** It will only be planned after an agreement with the hospital to replace its system (H10 is on hold).
  - Every basic function in §1 must work in MedFlux before the old system is switched off.
- **Business status set.** Adopt the HYDMedia states 1:1, or add a state such as "In Prüfung"?
- **Group contracts.** Does one contract belong to several Gesellschaften (HYDMedia multi-select), or is it duplicated per hospital?
- **Contract scope.** Are all contract types in scope (memberships, insurance, leases, approvals), or only maintenance and service contracts? HYDMedia holds all of them.

**H0.2 Missing evidence.** Ask the hospital for screenshots or exports of:
- the dropdown lists for "Kündigung zum", "Erinnerungsneuberechnung", "Termin-Typ" and "Leistungsart";
- the Postfach contents;
- the Rollen/Workflows definition;
- the "Berichte" outputs;
- an example reminder e-mail;
- the Vertragspartner detail form.

Do **not** request data exports for now. Migration is on hold until a replacement agreement exists.

**H0.3 Data protection.** Remove the real-contract PDF folder (`عقود حقيقية لتدريب النموذج/`) from git tracking. Keep these screenshots out of git (they contain personal data).

**DoD:** the decisions are recorded in §6, the evidence request is sent, and the privacy issue is resolved.

---

### Phase H1 – Contract register core (L), the foundation for everything else

**H1.1 Contract master fields as stored columns**
- **Goal.** All HYDMedia header and "Vertragsdaten" fields exist as editable, stored values.
- **Backend.**
  - Add a migration with new `contract` columns:
    - identity: `register_number` (unique per org), `internal_number`, `short_description` (Kurzbeschreibung), `subject_text` (Gegenstand);
    - flags: `is_framework`, `manual_billing`;
    - responsibility: `storage_location_id` (FK in H2), `responsible_account_id` (exists), `reminder_recipient_account_id`, `escalation_recipient_account_id`;
    - classification: `contract_type_id` and `contract_category_id` (FKs in H2; until then `contract_type_code` text);
    - term data: `term_model` (enum: `fixed_term`, `terminable`, `terminable_min_term`, `auto_renewal`, `perpetual`), `start_date` (exists), `minimum_term` (n + unit), `fixed_end_date`, `notice_period_value`, `notice_period_unit`, `notice_to` (enum: `contract_end`, `month_end`, `quarter_end`, `half_year_end`, `year_end`, `anytime`), `renewal_period` (n + unit);
    - termination and retention: `terminated_on`, `terminated_effective`, `retention_years_after_end`, `account_number`.
  - Add `contract_field_provenance` with (contract_id, field_key, origin, extraction_id, evidence_id, confirmed_by, confirmed_at, updated_by, updated_at).
  - **Backfill** the new fields from the accepted extraction with origin `ai` (or `ai_confirmed` where a confirmed `fact_review` exists).
  - Add `PATCH /api/contracts/{id}` with a field allow-list. It must:
    - validate types and the scope check;
    - write an `activity_log` entry with **old and new values** (field-level diff, better than HYDMedia);
    - set provenance to `manual` / `ai_corrected`;
    - trigger recalculation and the warnings re-run (H1.3).
- **Frontend.**
  - A new **"Stammdaten" edit form** on the contract detail, grouped by topic (Identität & Partner, Organisation & Verantwortung, Laufzeit & Kündigung, Erinnerung). The HYDMedia fields are the checklist for completeness, not the layout template.
  - Required-field highlighting.
  - A provenance badge per field (AI with evidence link, Manuell, Bestätigt), reusing `ValueOriginBadge`.
  - Previous/next contract navigation, and "Nach dem Speichern geöffnet lassen".
- **AI integration.**
  - Map the extraction to `term_model`:
    - `automatic_renewal` → `auto_renewal`;
    - minimum duration plus cancellable → `terminable_min_term`;
    - explicit end and no renewal → `fixed_term`.
  - Map `notice_to` from `cancellation_to_contract_end` or `cancellation_condition` ("zum Quartalsende" → `quarter_end`) **only with evidence**. Otherwise leave it empty and flag it for review.
- **Tests.**
  - Migration up and down on the 55432 cluster, and a backfill test.
  - PATCH tests: allow-list, scope, viewer forbidden, audit diff, provenance.
  - Frontend form tests, including a11y.

**H1.2 Manual contract creation (no document)**
- **Goal.** HYDMedia lets users create contracts with no PDF (memberships, approvals). MedFlux must too.
- **Backend.** Add `POST /api/contracts`, with required fields per the HYDMedia rules: Kurzbeschreibung, Vertragspartner, Verantwortlich, Vertragstyp, Kategorie, term model, Vertragsbeginn, and the notice period when the term model needs one. It assigns `register_number` (H1.5), creates the contract with `business_status = in_arbeit`, and runs the calculation and warnings.
- **Frontend.** A "Vertrag anlegen" button that opens the same form as H1.1. This is the "manual" mode of `CONTRACT_IMPORT_WIZARD.md`.
- **Tests.** Required-field validation, numbering, scope (hospital and department of the creator), audit entry.

**H1.3 Deterministic term engine extension**
- **Goal.** Cover all five HYDMedia term models and "Kündigung zum <period end>".
- **Backend** (`app/contracts/calculation/dates.py`):
  - `terminable` + `notice_to = quarter_end` gives:
    - next possible end = the first quarter end that is at least the notice period after today;
    - "kündbar bis" = that end minus the notice period.
  - The same logic applies to `month_end`, `half_year_end` and `year_end`.
  - `terminable_min_term` uses the same logic, but never earlier than start + minimum term.
  - `perpetual` with no notice yields no end and no warnings, except reminders.
  - `fixed_term`: end = the fixed end or start + duration; no cancellation needed. The warning type is "Verlängerung prüfen".
  - `auto_renewal` keeps the existing renewal logic.
  - Outputs, named after HYDMedia: `earliest_end` (früh./festes Vertragsende), `cancel_by` (kündbar bis), `possible_end` (mögl. Vertragsende), and `actual_end` (= `terminated_effective` if terminated).
  - Bump `CALC_VERSION`.
- **Tests.** A table-driven test for every term model × `notice_to`, built from the HYDMedia examples. For example: start 01.04.2027, notice 3 months, quarter end → possible end 30.09.2027, cancel by 30.06.2027 (screenshot 152449). Also cover leap years and month-end rollover.

**H1.4 Business status workflow**
- **Goal.** Statuses In Arbeit → Gültig → Gekündigt / Beendet → Gelöscht, plus reactivation, gated by role.
- **Backend.**
  - Add `business_status` and a transition table in code (`contracts/status/workflow.py`).
  - Add `POST /api/contracts/{id}/status-transitions` with `{to, note, effective_date}`.
  - Rules:
    - "Gekündigt" requires `terminated_on` and `terminated_effective`.
    - "Beendet" sets `actual_end`.
    - "Gelöscht" reuses the existing soft-delete queue.
    - "Gültig" requires the critical facts to be reviewed (reuse the review gate) unless an admin overrides.
  - Each transition writes an audit entry and closes or opens the related work items.
  - **Suggestions:** code proposes a transition but never performs it. For example: `possible_end` passed and still "Gültig" → work item "Vertrag auf beendet setzen" (the HYDMedia ERINNERUNGSTODO "Beendet").
- **Frontend.**
  - A status badge in the HYDMedia colours (Gültig green, In Arbeit amber, Gekündigt/Beendet red, Gelöscht grey).
  - A "Statuswechsel" button group that shows only the allowed transitions.
- **Tests.** The transition matrix × role, guards, audit, and the work-item side effects.

**H1.5 Number ranges (Nummernkreise)**
- **Backend.** Add a `number_range` table (org, purpose = `contract`, prefix, padding = 6, next_value) and a `number_allocation` table (value, state free/used/reserved, account, timestamp).
  - Allocate inside a transaction with `SELECT … FOR UPDATE`.
  - An admin can reserve numbers.
  - Design the sequence so a future import can keep existing numbers (set `next_value` past the highest imported number). This needs no extra work now.
- **Frontend.** Admin page "Nummernkreise" (H2 admin area).
- **Tests.** Concurrency: two parallel creates must not get the same number. Also test reserved numbers and the import offset.

**Phase H1 DoD.** A contract can be created and fully edited without AI. Every field shows its origin. The HYDMedia deadline example computes identically. The status workflow works for all roles. `PROJECT_PROGRESS.md` is updated.

---

### Phase H2 – Master data and catalogues (M–L)

**H2.1 Vertragspartner (contract partners)**
- **Backend.**
  - Add a `contract_partner` table (org, short_name (unique per org), name1, name2, display_name, street, postal_code, city, country, po_box, po_box_postal_code, phone, fax, website, email, industry_id, partner_type, partner_class, address_type, active) and `partner_contact` (Bereich/contact areas: name, role, phone, email).
  - Add a `contract.partner_id` FK and keep `supplier` as the literal extracted text.
  - **Migration:** group the existing `supplier` strings by normalised name (case, legal form, umlauts) into partner candidates. Merging requires admin confirmation in a UI, not an automatic merge.
  - Add CRUD `/api/partners` and a fuzzy search endpoint.
- **AI.** After extraction, match `supplier`, its address and its email to an existing partner with a score:
  - a high score proposes "Partner X" (the user confirms);
  - a low score proposes "Neuen Partner anlegen", pre-filled from the extracted contractor block.
  - The model never creates a partner on its own.
- **Frontend.**
  - A partner picker that shows the display name plus city, never the raw ID.
  - "Partner anlegen" and "Partner anzeigen" inline, as in HYDMedia.
  - A partner list page with **duplicate warnings**, which fixes a HYDMedia weakness.
  - A partner detail page listing all of the partner's contracts and the total cost.

**H2.2 Vertragstypen and Kategorien**
- **Backend.**
  - Add `contract_type` (org, code, label, description, is_confidential, active), `contract_category` (org, code, label, description, active) and the n:m table `contract_type_category`.
  - Seed a cleaned default set derived from the 24 HYDMedia types and 68 categories. Duplicates are merged and misused entries removed; the merges are listed for confirmation.
  - Map the existing `contract_type` enum: maintenance → Wartungsvertrag, service → Dienstleistungsvertrag, lease → Leasingvertrag, rental → Mietvertrag.
- **AI.** Classify the type and category from the extraction (title, subject, equipment). Only offer values that exist in the catalogue, with evidence and a confidence. If uncertain, leave the field empty and send it to manual review.
- **Frontend.** The category dropdown is filtered by the chosen type.

**H2.3 Generic lookup catalogues ("Nachschlagefelder")**
- **Backend.**
  - Add a `lookup_value` table (org, field_key, code, label, description, sort, active, unique(org, field_key, code)).
  - Field keys: `storage_location` (Lagerort), `attachment_type` (Anlagentyp), `deadline_kind` (Art), `deadline_type` (Termin-Typ), `todo_template` (ERINNERUNGSTODO, with an instruction text), `recharge_mode` (Weiterbelastung), `industry` (Branche), `address_type`, `salutation`, `job_function` (Funktion), `service_kind` (Leistungsart).
  - Seed with a cleaned default set (HYDMedia values as the reference).
- **Frontend.** One generic admin page, "Einstellungen → Auswahllisten": a list per field key with create/edit/deactivate, a uniqueness check and drag-sorting.

**H2.4 Group companies (Gesellschaften)**
- `hospital` already models a legal entity.
- If decision H0.1 says contracts can belong to several companies, add a `contract_hospital` n:m table (`is_primary`), with scope logic: a contract is visible to members of any linked hospital.
- Otherwise keep one hospital per contract.

**H2.5 Administration area UI**
- **Frontend.** `/settings` gains the sections Vertragspartner, Vertragstypen & Kategorien, Auswahllisten, Nummernkreise and Organisationsstruktur (exists).

**H2 Tests and DoD.**
- Uniqueness and deactivation guards (a value still in use cannot be deleted, only deactivated, like the WP1.7 HTTP 409).
- Seed idempotency.
- Partner-matching tests with mocked AI.
- Contract forms use only catalogue values.

---

### Phase H3 – Documents, amendments and framework linkage (M–L)

**H3.1 Several documents per contract**
- **Backend.**
  - Add `POST /api/contracts/{id}/documents` (upload with `attachment_type` from the catalogue, a title, and `is_main` / `is_valid`), plus PATCH for metadata, "set as main" and "mark invalid".
  - Deletion follows the existing soft-delete rules.
  - Upload uses the existing storage and SHA-256 dedup. `contract_document.role` maps from `attachment_type`.
- **Processing.**
  - If the type is analysable (Vertrag, Nachtrag, Addendum, Vergütungsvereinbarung, Kündigung, Kündigungsbestätigung, Leistungskatalog, AVV), run `DocumentProcessingService` **in "amendment" mode**.
  - The result is a **proposal diff** against the current register values. For example: "Nachtrag: monthly price 3.500 → 3.700 EUR from 01.01.2027, evidence p. 2". The user accepts each proposal individually, which writes provenance `ai_confirmed`.
  - Non-analysable types (Laufzettel, Rechnung, Korrespondenz, Fotos) are only stored.
- **Special cases.**
  - An uploaded **Kündigung** or **Kündigungsbestätigung** proposes `terminated_on` / `terminated_effective` and the status transition to "Gekündigt".
  - An uploaded **Rechnung** links to the existing invoice check (`ContractBillingPanel`).
- **Frontend.**
  - A "Dokumente" tab: list with Pos., Typ, Hauptdokument ★, Gültig ☑, date, uploader.
  - Actions: hinzufügen, anzeigen (PdfViewer), Metadaten bearbeiten, als Hauptdokument, ungültig setzen.
  - The contract list gets an "Anhänge" count column.
- **Tests.** Upload to an existing contract, scope checks, the diff-proposal flow, and a guarantee that no silent overwrite happens.

**H3.2 Framework ↔ individual contract linkage**
- **Backend.**
  - Add a writer for `contract_relation` (`governs` / `belongs_to_framework`): `POST/DELETE /api/contracts/{id}/relations`.
  - The framework picker only lists contracts with `is_framework = true`.
  - Several parents are allowed ("gehört zu Verträgen").
  - The aggregate view shows the framework with all its individual contracts, their total cost and their next deadlines.
- **AI.** If the text references a framework contract ("auf Grundlage des Rahmenvertrags Nr. …"), propose the link when a matching register number or partner exists. The user confirms.
- **Frontend.**
  - A "Verknüpfungen" tab: link/unlink, and a list showing number, category and Kurzbeschreibung.
  - The framework's detail page shows a "Einzelverträge" section.

**H3.3 Import wizard modes** (`CONTRACT_IMPORT_WIZARD.md`)
- Modes: `ai_direct`, `ai_human_review` (default) and `manual`.
- Per file, choose the destination: "neuer Vertrag" or "zu bestehendem Vertrag (als Typ …)".

---

### Phase H4 – Finance (WP2 extended) (L)

**H4.1 Finance entries ("Finanzdaten")**
- **Backend.** Add a `contract_finance_entry` table with:
  - `direction` (expense/income) and `label`;
  - `cost_type_id` (optional; Kostenart catalogue);
  - `amount`, `amount_basis` (net/gross), `vat_rate`, `currency`;
  - `interval` (monthly/quarterly/semi_annual/annual/once);
  - `valid_from` (month) and `valid_to` (month, nullable);
  - `cost_center_allocation` (see H4.3), `note`;
  - `origin` + `evidence_id`, `created_by`, `created_at`.
  Add CRUD under `/api/contracts/{id}/finance-entries`.
- **AI.** After extraction, **propose** finance entries from `costs.*`, `scheduled_prices[]` and `variable_charges[]`, keeping their period and evidence. The existing strict finance gate (`_financial_source_rejection`) still applies. The user accepts the proposals into entries.
- **Calculation** (`contracts/calculation/finance.py`, deterministic): compute aggregates **on whole months, as HYDMedia does**:
  - net and gross for `current_year`, `to_date` and `to_contract_end` (until `possible_end` / `actual_end`);
  - `total_term`;
  - all of these separately for expenses and income;
  - plus the normalised `annualized_cost_net/gross` (WP2.3).
  Store the results in a new calculation-result section so lists can sort and filter by them.
- **Frontend.**
  - A "Finanzdaten" tab: a summary matrix (rows Ausgaben / Einnahmen / Gesamt; columns laufendes Jahr / bisher / bis Vertragsende / Laufzeit; net and gross), the entry list, an entry dialog and an export.
  - Show "Berechnung auf Basis ganzer Monate" as an explanation.
- **Tests.** Golden numbers from the screenshots (3.500,00 net × 19 % = 4.165,00 gross), validity-period edge cases, open-ended entries, income vs expense.

**H4.2 Leistungskatalog (service price list)**
- **Backend.** Add `contract_service_item` (label, `service_kind` from the catalogue, amount, `plus_vat` flag, valid_from, valid_to, note, origin + evidence). Equipment-linked services can optionally reference `contract_equipment`.
- **AI.** Propose items from `services.included`, `variable_charges` (hourly rate, travel cost, spare parts) and price tables, with evidence.
- **Frontend.** A "Leistungen" tab with a list and an editor.

**H4.3 Cost centres, cost types and recharging**
- **Backend.**
  - Add a `contract_cost_allocation` table (contract or finance entry → cost_center_id, share_percent, recharge_mode from the Weiterbelastung catalogue). Shares must sum to 100 %.
  - Keep `contract.cost_center_id` as the primary.
  - Add a `cost_type` catalogue (Kostenart, linked to the H2.3 lookups).
  - Add `contract.account_number` (from H1.1) and `manual_billing`.
- **Frontend.** An allocation editor in the Organisation section. The cost-centre filter becomes visible in the contract list (today it is backend only).
- **Price adjustment (WP2.1).** Add a structured `price_adjustment` with:
  - `kind`: fixed / index (with index name) / percentage per year / by negotiation;
  - the value, the next adjustment date, evidence.
  A deterministic projection feeds `to_contract_end`.

---

### Phase H5 – Deadlines, reminders and notifications (WP4) (L)

**H5.1 Deadlines ("Termine")**
- **Backend.** Add a `contract_deadline` table with:
  - `kind` (lookup `deadline_kind`), `deadline_type` (lookup), `due_date`;
  - `assignee_account_id`, `escalation_account_id`;
  - `todo_template_id` + `todo_text`, `note`;
  - `status` (open/done/cancelled), `done_by`, `done_at`;
  - `send_email` and `send_ics` flags;
  - `source`: `manual`, or `system` with a `calc_ref`.
- **System deadlines.** Generated deterministically from the calculation:
  - reminder date = `cancel_by` − lead time;
  - `possible_end` with the ToDo "Verlängerung prüfen" or "Vertrag kündigen?";
  - payment due dates from the finance entries (WP4.1);
  - maintenance due dates from `contract_equipment` / service intervals.
- **Recalculation rule** ("Erinnerungsneuberechnung"): a per-contract `reminder_lead` (n months) plus a `recalc_interval`.
  - When a system deadline is marked done and the contract is still active, the next one is generated, e.g. the next renewal period.
  - When contract data changes, open system deadlines are regenerated. Manual deadlines are never touched.
- **Relation to existing pieces.**
  - The warnings engine stays as it is; it drives the severity of the dashboard and the work queue.
  - Each deadline creates or links a `work_item`, so the Postfach and the work queue stay in one place.
  - The existing `remind_at` field on work items is replaced by deadlines (migration).
- **Frontend.**
  - A "Termine" tab on the contract: list, create, edit, done, delete.
  - The Vertragsdaten section shows "Erinnerung am / an", "Eskalation an" and ToDo, plus a "ToDo erledigt" button, as in HYDMedia.

**H5.2 Notification delivery**
- **Backend.**
  - Add `notification` (recipient, kind, contract, deadline, created_at, read_at) and `notification_outbox` (channel email, payload, status, attempts, last_error, sent_at).
  - **SMTP** settings live in the organisation settings (host, port, TLS, sender). The password is not stored in the database; it goes in an env or secret file.
  - Mail content is **minimal**: contract number, Kurzbeschreibung, deadline, ToDo, and a link into MedFlux. No contract contents beyond that, for data-protection reasons.
  - **ICS:** generate an `.ics` attachment (VEVENT + VALARM) when `send_ics` is set.
- **Scheduler.**
  - An in-process APScheduler job, or a Windows Task Scheduler job calling `python -m app.jobs.daily`.
  - Daily it: evaluates due deadlines (lead and due dates), escalates overdue ones to `escalation_account`, re-runs warnings for all active contracts, and sends the outbox.
  - It must be **idempotent**: a unique key (deadline, kind, date) prevents double mails.
- **Monitoring.**
  - Add a `job_run` table (job, host, started, finished, status, counts, error).
  - Admin page "Monitoring" shows the last run, the next run and failures; the dashboard warns if the last successful run is older than 26 h.
  - Every sent mail is logged in the history ("Erinnerungsmail gesendet an …"), as in HYDMedia.

**H5.3 Deputies and user preferences**
- **Backend.**
  - Add `account_deputy` (account, deputy, valid_from, valid_to, active) and `account.default_deputy_id`.
  - Add `account.receives_notifications` and `account.receives_reminders`.
  - Delivery resolves the active deputy for the date: the mail goes to the deputy and a copy to the original assignee.
- **Frontend.**
  - Profile: "Vertretung", "Benachrichtigungen".
  - Admin: a deputies list.

**H5.4 Postfach (inbox)**
- **Frontend.** The bell becomes an **inbox** page with read/unread state, filters (Fristen, Prüfungen, Statuswechsel), a count badge, and "meine Wiedervorlage" as a default view.

**H5 Tests.**
- Deterministic deadline generation per term model.
- Recalculation after done.
- Scheduler idempotency, using a frozen clock.
- The outbox retry path.
- Deputy resolution.
- ICS validity.
- **No real SMTP in tests**: a fake transport.

---

### Phase H6 – Remarks and history (S–M)

**H6.1 Bemerkungen (remarks journal)**
- **Backend.** Add `contract_remark` (contract, author, created_at, text, optional `finance_entry_id` / `deadline_id`). It is append-only, with no edit or delete; a correction is a new entry.
- **Frontend.** A "Bemerkungen" tab with a new-remark box and a chronological history showing author and time.

**H6.2 History**
- MedFlux already logs more than HYDMedia does. The work here:
  - Make sure every H1–H5 mutation logs a field-level diff, the system actor (scheduler) and the role.
  - Add a **global history page** (`/audit` for admins), with filters by user, action, contract and date, and an export.
  - Add a "Historie" tab on the contract that merges activity_log, fact reviews, overrides, status transitions, documents and sent mails.

---

### Phase H7 – Lists, views, export, reporting (WP5) (L)

**H7.1 Contract grid upgrade**
- **Column chooser.** All register fields are available as columns, including the H1/H4/H5 values (früh. Ende, kündbar bis, gekündigt am, mögl. Ende, Erinnerung am/an, Eskalation an, Kosten laufendes Jahr/Laufzeit, Einnahmen, Rahmenvertrag, Anhänge, Gesellschaft, Abteilung, Kostenstelle, Lagerort, Löschen ab Ende).
- **Per-column filters** with the operators empty, not empty, value list and range.
- **Group by** one or two columns, with group counts and sums.
- **Backend.** Extend `contracts/search/service.py` with column projection, group-by aggregates and the new filters, keeping the scope filter.
- **Performance.** Paginated, with indexes on the new columns; avoid N+1 queries.

**H7.2 Saved views ("Arbeitsbereiche" / "Favoriten")**
- **Backend.** Add `saved_view` (owner or org-global, name, filters, columns, sort, grouping). Only admins create global views; this matches HYDMedia's "Globale Layouts".
- **Defaults to seed:** "Meine Verträge", "Meine Wiedervorlage", "Kündigungsfrist < 90 Tage", "In Arbeit", "Zum Löschen vorgesehen", "Gelöschte Verträge".
- **Frontend.** The current localStorage views migrate to the server.

**H7.3 Navigation tree.** A left-side tree "Verträge nach Gesellschaft → Abteilung", built from the org tree with counts, as an alternative to the scope picker.

**H7.4 Export and reports**
- **Exports.**
  - Excel (`.xlsx`, via `openpyxl`) of the current grid view, with its columns and filters.
  - A per-contract finance export (income and/or expenses).
  - Each export is logged in the audit (it exists for CSV).
- **Reports.**
  - A **"Deckblatt"** PDF per contract: master data, deadlines, finance summary, documents, responsible people.
  - Portfolio reports: cost by Gesellschaft, Abteilung, Kostenstelle, Vertragstyp and Partner; upcoming deadlines over the next 6 months; contracts by status.
  - Rendered server-side and locally (HTML → PDF with a local engine; no cloud).

**H7.5 Analytics (`/analysen`, WP5).** Charts for cost over time, cost by department, type and partner, the deadline heatmap, top-N partners, and income vs expenses. Use one chart library, following the dataviz rules, with drill-down into the grid.

---

### Phase H8 – Roles, permissions and users (WP6) (M)

**H8.1 Permission matrix**
- Centralise the inline checks into `auth/permissions.py`: a matrix of role × action (contract.create/edit/status.<transition>/delete, document.attach, finance.edit, deadline.edit, catalogue.admin, partner.admin, export, audit.view, views.global).
- Map the HYDMedia roles:
  - "ADMIN" → `admin`;
  - "ABTEILUNGS-VERTRAGSBEARBEITER" → `contract_manager` with department scope (this exists: membership `department_id`).
- Optionally add role switching ("Rolle wechseln") for users with several memberships. The scope picker partly covers it already.

**H8.2 Confidential contracts.** Contracts whose type has `is_confidential = true` (HYDMedia "vertraulich") are visible only to an explicit allow-list (management). Enforce this in `scoped_contract_ids`, in exports and in the AI assistant (fail-closed).

**H8.3 User profile.** Add `job_function` (lookup), `phone`, the notification preferences and the default deputy (H5.3), and a lock state (the admin lock exists via deactivation). AD/SSO is a later, separate security review (Step 16 rule).

---

### Phase H9 – Retention and physical originals (S)
- `retention_years_after_end` gives a `deletion_due_year`, which appears in the grid and in the view "Zum Löschen vorgesehen".
- The daily job creates "Löschprüfung" work items. Deletion itself always goes through the existing soft-delete confirmation, never automatically.
- The `storage_location` lookup records where the paper original is kept (e.g. Archiv Original/Kopie, a department), together with the Lagerort.

---

### Phase H10 – Legacy data migration (ON HOLD)

> **Status: on hold (decided 2026-10-04).** Data migration will not be planned or built until the hospital agrees to replace its current system. The notes below are kept only as a sketch for that later point. No work, data requests or scripts until then.

MedFlux replaces the old system, so this is a **one-time takeover**, not a synchronisation. The importer is generic: a **legacy import** with a mapping profile. HYDMedia is the first profile, so other hospitals with other legacy tools (Excel lists, other CLM software) can use the same path.

**H10.1 Import pipeline.** A script and admin UI, `scripts/import_legacy_contracts.py`, with a mapping profile `hydmedia.yaml` and a dry-run report. It reads a **legacy export (CSV/XLSX)** for contracts and partners, and later the document files with their metadata. Steps:
1. **Map columns** through a reviewed mapping file: Status → business_status, Vertragsnr. → register_number, Vertragstyp/Kategorie → catalogues, Vertragsart → term_model, Kündigung zum → notice_to, Gesellschaft/Abteilung → org, Verantwortlich, Erinnerung an and Eskalation an → accounts (via a personnel-number → account mapping table), money columns → finance entries.
2. **Partners** are imported first, with a duplicate review.
3. **Provenance** of every imported value is `imported_legacy` (with the profile name).
4. **Recompute** MedFlux's own deadlines and **compare** them with HYDMedia's "kündbar bis" and "mögl. Vertragsende". Differences become review work items. This is a data-quality win: it finds wrongly maintained HYDMedia data.
5. **Extract structured equipment data.** Parse serial and inventory numbers out of the Kurzbeschreibung (pattern `SN <serial> (<NW|HG>####)`) into `contract_equipment` proposals for review.
6. **Documents.** Attach the PDFs from the legacy DMS as documents (H3.1). Then run the **local AI as a quality audit** of the old data: the AI extracts the facts, MedFlux compares them with the imported values, and every disagreement (end date, notice period, price, partner) becomes a review item with evidence. This is the first visible benefit of the switch: on day one the hospital sees where its old data was wrong or incomplete.

**H10.2 Go-live procedure.**
1. Dry run on a copy, review the report, fix the mapping.
2. Final import on a freeze date; the legacy system becomes read-only.
3. Run the AI quality audit in the background, prioritised by the nearest deadlines first.
4. Parallel check for a few weeks: compare reminders sent by MedFlux with the old system's deadline list.
5. Switch off the legacy system and archive its export (for the retention period).

**H10 Tests.** A fixture with a synthetic legacy export (no real data), idempotent re-import, and mapping-error reports.

---

## 4A. The AI layer: what MedFlux adds on top of each basic function

This is what makes MedFlux more than a modern HYDMedia. Each row is a **Layer 2** feature. It is built in the same phase as its basic function, or directly after it, and it always follows the rules: local model only, evidence for every value, code computes, the human confirms, "nicht gefunden" instead of guessing.

| Basic function (Layer 1) | In a classic system (HYDMedia) | What MedFlux AI adds (Layer 2) | Status today | Phase |
|---|---|---|---|---|
| **Create a contract** | Type about 25 fields by hand | Upload the PDF → all master fields pre-filled with page/region evidence and confidence; the user only confirms or corrects | ✅ extraction exists; needs mapping into the register fields | H1 |
| **Contract term & notice** | User enters the term model; reminder dates partly maintained by hand | AI reads the term clauses (Laufzeit, Mindestlaufzeit, Kündigungsfrist, "zum Quartalsende", Verlängerung). Code computes the deadlines. A **conflict check** flags contracts where the entered data and the contract text disagree | 🟡 extraction + calculation exist; `notice_to`/term model mapping missing | H1.3 |
| **Partner** | Pick or create by hand; duplicates accumulate | AI matches the extracted supplier block to the partner master (name, address, VAT ID) and proposes a new partner pre-filled; a **duplicate detector** for existing partners | ❌ | H2.1 |
| **Type / category** | Pick from 24 × 68 lists | AI classifies from the title, subject and equipment, offering only catalogue values | ❌ | H2.2 |
| **Amendments (Nachtrag)** | Attach the PDF; someone retypes the changes by hand | AI compares the amendment with the current contract and produces a **change proposal** ("price 3.500 → 3.700 EUR from 01.01.2027, p. 2"); accepted per field | 🟡 processing path exists; diff mode missing | H3.1 |
| **Termination letters** | Set "gekündigt am/zum" by hand | AI reads the Kündigung/Kündigungsbestätigung → proposes the dates + status "Gekündigt" + checks whether the notice deadline was met | ❌ | H3.1 |
| **Framework contracts** | Link by hand via a picker | AI finds references ("auf Grundlage des Rahmenvertrags …") and proposes the link | ❌ | H3.2 |
| **Finance entries** | Enter amounts, VAT and periods by hand | AI proposes the entries (recurring fee, price steps, hourly rates, travel costs) with period and evidence; code aggregates | 🟡 extraction + cost calculation exist | H4.1 |
| **Price adjustment** | Not modelled | AI extracts the index or percentage clause → code projects future costs → a **warning before each adjustment date** | 🟡 free text only | H4.3 |
| **Invoice check** | Not available | Compare an uploaded invoice with the contract prices → flag overcharges | ✅ `ContractBillingPanel` | H3.1 link |
| **Service catalogue / SLA** | Free-text Gegenstand | AI extracts the included/excluded services, SLA times and maintenance intervals as structured data → generates maintenance deadlines | 🟡 extracted, not editable | H4.2, H5.1 |
| **Equipment** | Serial number inside the description text | AI extracts devices, serial and inventory numbers into the equipment registry; shows coverage per device ("Is this CT covered? Until when?") | ✅➕ exists | keep |
| **Deadlines & reminders** | Reminders set by hand; a wrong date goes unnoticed | Deadlines generated from the verified contract facts; AI proposes **additional deadlines found in the text** (Preisanpassung, Mindestabnahme, Wartungsintervall, Optionsrecht) | 🟡 warnings exist; sending missing | H5.1 |
| **Decision support** | None | Before the notice deadline, a **renewal brief**: cost trend, open issues, SLA problems, invoice deviations, comparable contracts → recommendation "kündigen / verhandeln / verlängern" (advice only; the human decides) | 🟡 lifecycle decisions + intelligence scaffold exist | after H5 |
| **Search** | Field search only | Full-text + semantic search across all contract **contents** ("Welche Verträge enthalten eine 24/7-Hotline?"), always with sources | 🟡 full-text on a few fields; LlamaIndex in `experiments/` | H7 |
| **Contract assistant** | None | A Q&A assistant per contract and across the portfolio, answering only from evidence and only within the user's scope (fail-closed) | ✅ exists (secure assistant) | extend H7/H8 |
| **Reports / analytics** | Static report templates | Portfolio insights: cost drivers, contracts without a responsible person, renewals without a decision, supplier concentration, savings potential | 🟡 dashboard KPIs | H7.5 |
| **Data quality** | Duplicates and gaps stay unnoticed | A continuous **data-quality score** per contract (missing required fields, unconfirmed AI values, conflicts between text and register); later also an audit of imported legacy data (H10, on hold) | 🟡 data-quality list exists | H1 |
| **Confidentiality / data protection** | Type "vertraulich" | AI detects GDPR-relevant contracts (AVV/Auftragsverarbeitung, personal data) and proposes the confidentiality flag and retention period | ❌ | H8.2, H9 |

**AI acceptance rule (applies to every row).** An AI value enters the register only as a proposal. It becomes "accepted" when (a) a user confirms it, or (b) the organisation has enabled auto-accept for that field (WP3 `review_mode = auto`) **and** the evidence and verification gates pass. Critical fields (end date, notice deadline, annual cost) always require a confirmation before the first reminder is based on them, unless an admin decides otherwise per organisation.

**Measuring the AI benefit** (for the pilot and for sales arguments):
- the share of fields pre-filled correctly (confirmed without correction) per field group;
- the time from upload to a "Gültig" contract, compared with manual entry;
- once a migration happens (H10, on hold): the number of data errors found in the legacy data;
- deadlines missed: target 0.

---

## 5. Recommended order, dependencies and effort

```
H0 ─► H1 (register core) ─┬─► H2 (catalogues) ─┬─► H3 (documents/framework)
                          │                    ├─► H4 (finance)
                          │                    └─► H10 (migration, ON HOLD until hospital agreement)
                          └─► H5 (deadlines/notifications) ◄── needs H1.3, H2.3
H6 (remarks/history) — any time after H1
H7 (grid/views/export) — after H1, H4, H5 (columns exist)
H8 (permissions) — start together with H1 (matrix), finish before pilot
H9 (retention) — after H5 (daily job)
```

Because MedFlux is built to **replace** the legacy system, the plan is grouped into four **milestones**. M1–M3 make MedFlux a complete contract manager that a hospital can start using with new contracts. M4 (the switch-over with data migration) only starts once there is a replacement agreement with the hospital. Each step ships its basic function together with its AI part from §4A.

**Milestone M1 – "Usable contract manager" (basics without AI dependency)**

| Order | Step | Size | Basic function | AI part delivered with it |
|---|---|---|---|---|
| 1 | H0 decisions + evidence + privacy fix | S | – | – |
| 2 | H1.1 + H1.5 register fields + numbering | L | editable master data, contract numbers, provenance | extraction → register mapping |
| 3 | H1.3 term engine | M | all 5 term models, "Kündigung zum Periodenende" | term-clause mapping + conflict check |
| 4 | H1.2 manual create + H1.4 status workflow | M | create without document, In Arbeit → Gültig → … | status suggestions (e.g. "auf Beendet setzen") |
| 5 | H2.1–H2.5 partners, types/categories, lookups, admin | L | catalogues | partner matching, duplicate detection, classification |
| 6 | H6 remarks + history | S–M | journal, field-level history | – |

**Milestone M2 – "Nothing is missed" (deadlines and documents)**

| Order | Step | Size | Basic function | AI part delivered with it |
|---|---|---|---|---|
| 7 | H5.1–H5.2 deadlines, scheduler, e-mail, ICS, monitoring | L | reminders actually reach people | additional deadlines found in the text |
| 8 | H5.3–H5.4 deputies + inbox | M | absence handling, personal inbox | – |
| 9 | H3.1–H3.3 documents, amendments, framework, import modes | L | several typed documents, Rahmenvertrag | amendment diff, termination-letter reading, framework detection |

**Milestone M3 – "Costs and control"**

| Order | Step | Size | Basic function | AI part delivered with it |
|---|---|---|---|---|
| 10 | H4.1–H4.3 finance, service catalogue, cost allocation, price adjustment | L | income/expenses, aggregates, cost centres | proposed finance entries, price-adjustment projection |
| 11 | H8 permission matrix, confidential contracts, user profile | M | roles and visibility | GDPR/AVV detection → confidentiality proposal |
| 12 | H7 grid, saved views, tree, Excel/PDF export, reports, analytics | L | lists and reporting | semantic search, portfolio insights |
| 13 | H9 retention | S | Löschen ab Ende, Lagerort | retention proposal |

**Milestone M4 – "Replacement go-live" (ON HOLD until a replacement agreement with the hospital)**

| Order | Step | Size | Basic function | AI part delivered with it |
|---|---|---|---|---|
| 14 | H10 legacy import (dry run → freeze → import) | M–L | takeover of all contracts and partners | AI quality audit of the legacy data |
| 15 | Parallel check + UAT + switch-off of the legacy system | M | – | measure the AI benefit (§4A) |

Renewal briefs / decision support (recommendations before notice deadlines, size M) do not depend on the migration. They move to the end of **M3** as step 13a.

Each row is one or more PRs on `feature/<domain>-<change>`, merged to `main` only with CI and the release gate green, and recorded in `docs/PROJECT_PROGRESS.md`.

---

## 6. Decisions

| # | Question | Options | Decision | Date |
|---|---|---|---|---|
| D1 | Replace or coexist with the legacy system | replace / coexist | **replace**: MedFlux is the single master. Data migration (H10) is **on hold** until an agreement with the hospital | 2026-10-04 |
| D2 | Business status set | HYDMedia set (In Arbeit, Gültig, Gekündigt, Beendet, Gelöscht) / extended | **HYDMedia set** (+ reactivation Beendet → Gültig) | 2026-10-04 |
| D3 | One contract → several Gesellschaften | n:m / duplicate per hospital | **n:m** (`contract_hospital` with `is_primary`; visible to members of any linked hospital) | 2026-10-04 |
| D4 | Contract scope | all contract types (as in the legacy system) / maintenance+service only | **all contract types** | 2026-10-04 |
| D5 | Scheduler technology | in-process APScheduler / Windows Task Scheduler | **both**: in-process thread (opt-in, no new dependency) or `python -m app.jobs.daily` via Task Scheduler; DB lock prevents double runs | 2026-10-04 |
| D6 | Mail server available on site (SMTP relay) | yes / no (then inbox only) | **optional**: SMTP when configured; otherwise inbox only, mails queue until SMTP exists | 2026-10-04 |
| D7 | Default catalogues (types, categories, lookups) | approve the cleaned set | | |
| D8 | Personnel-number ↔ account mapping source for the migration | manual / AD export | deferred (H10 on hold) | 2026-10-04 |
| D9 | AI auto-accept policy | always confirm / auto-accept non-critical fields when the gates pass | | |

---

## 7. What MedFlux must keep (its advantage over the legacy system)

- Evidence for every AI value (page, region, confidence) and the "nicht gefunden" honesty.
- Deterministic deadlines and costs with explanations (`CalculationBasisPanel`), and warning levels.
- Responsible vs beneficiary departments in a real org tree; cost-centre search.
- The equipment registry with structured serial and inventory numbers instead of free text.
- Fact review with the critical-field gate.
- Dashboard, work queue and data-quality list.
- Fully local operation: no contract content leaves the hospital.

**The target:** a hospital that switches from its old contract software finds every basic function it relied on, in a modern interface. But in MedFlux most values are already filled in from the document, every value shows its source, errors in the old data are flagged automatically, reminders arrive by themselves, and the AI helps decide what to do before each deadline.
