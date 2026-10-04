# Comprehensive Functional Verification Report – Original MedFlux

- **Datum:** 27.09.2026
- **Repository:** https://github.com/jamallionjan-dev/medflux (privat, kein GitHub-Actions-Einsatz)
- **Basis-Branch:** `step3/integration-20260926`
- **Referenz-Commit (geprüfte Version):** `4b62abcf9bf58e566b61296b29b8684f87e539d3`
- **Testumgebung:** isoliert – `DATABASE_URL=postgresql+psycopg://medflux_test:medflux_test_pw_2026@127.0.0.1:55432/postgres` (WSL-Postgres-Testinstanz, **nicht** Produktion 5432); `AUTH_ENABLED=false`, `MEDFLUX_INSECURE_DEV=true`; Python aus `Medflux-Integrated-Test/backend/.venv` gegen den Code-HEAD des Worktrees.
- **Sicherheitsauflagen eingehalten:** Produktions-DB (5432) unangetastet; laufende Prozesse nicht gestört; kein Merge in `step3/integration-20260926`, kein Deploy; Arbeit auf eigenem Report-Branch.

## 1) Frankfurt E2E (Original – PDF → Docling/OCR → Visual-First → Harness V3)

Ausführung mit isoliertem Benchmark-Skript (Kopie ohne DB-Zugriff, PDF per lokaler Verifikation SHA256 `05A133012BE523593B414A512A70B19B82240E3F0EB0347034EE0C27C29CE088`, 9 Seiten) gegen den **Referenz-HEAD 4b62abc** mit lokalem Ollama-Temp-Instanzport **11435** (`qwen3-vl:8b-instruct`, Q4_K_M, vision, 8.8B).

Kernmetriken (Log `06-frankfurt-e2e.log`):

| Metrik | Wert |
|---|---|
| Docling-Pages | 9 (identisch Original) |
| Docling-Laufzeit | 80.7 s |
| Image-Prep | 9 Seiten, 0.891 s, Ø 389.3 KB |
| AI-Calls gesamt | 57 (warmup 1, vision_vf 9, review 2, semantic 4) |
| Latency | min 5.0 s / max 32.2 s / Ø 19.9 s |
| Truncations / Retries | 0 / 0 |
| Elapsed | 297.8 s |
| VRAM | Ø 7591 MiB, max 7945 MiB (RTX 3070, 8 GiB) |
| Analyse-Status | **partial** |
| Requires-Review | True |

**Finanz-Bewertung (der geforderte Kern-Check „keine Finanzwerte ohne Beleg"):**

- Akzeptierte Felder gesamt: **6** → nur `identity` (5) + `payment` (1). **Kein einziges Kostenfeld akzeptiert.**
- `FULL_REAL_ANNUAL_COST_PRESENT = False`, `ANNUAL_COST_PAGE_REFERENCE = None`, `CONTESTED_AMOUNT_ASSIGNED_ANNUAL = False`, `SLA_PRESENT = False`.
- Der im Originaltext vorhandene Betrag **12.000,00 €** (S.3, Investitionsgut) wurde **nicht** als (contested) Jahreskosten übernommen; auch **9.500,00 €** (S.3, Einzelkomponenten) und **180,00 € / 200,00 €** (S.5, Verbrauchsmaterial) nicht – alle unter `financial_classification_unverified` / `evidence_not_located` / `uncertain`.
- Reject-Gründe: `applicability:superseded` 1, `evidence_not_located` 4, `financial_classification_unverified` 1, `model_marked_ambiguous` 5, `applicability:alternative` 1.
- Reconcile: uncertain 25, vision_only 1, ocr_only 10 (kein Wert verlässt den Bereich ohne Quellenankler).
- OCR-Originaltext (RapidOCR) bestätigt die erwarteten Belegseiten: S.3 die beiden Investitionssummen, S.5 die zwei Verbrauchsmaterial-Preise – der Referenz-HEAD verhält sich hier identisch zur Phase-3/Gate-2-Baseline (kein Regression).

Bewertung: **Frankfurt E2E bestanden** – Verarbeitung über den vollen Visual-First-Harness inkl. cost-gate Fail-Closed Verhalten reproduzierbar.

## 2) Importpfade (manuell / AI+Review / AI-direkt)

Analyse der aktuellen Route- und Service-Struktur (auf 4b62abc):

- **Manuellen Importpfad gibt es nicht.** Es existiert genau ein Import-Endpoint: `POST /api/documents/import` (`app/api/routes/documents.py:242`), der vollständig AI-getrieben ist. `create_contract` (`app/database/services.py:540`) wird ausschließlich aus dem AI-Pipeline-Orchestrator `app/documents/processing.py:1336,1475` gerufen – **kein** manuelles/ohne-AI-Contract-Anlage-Endpoint.
- **AI-direkt (Auto-Save)** = Implementiert: Import speichert Contract + Facts inline (Deterministik-Checks + Warnungen) **vor** der HTTP-Antwort.
- **AI + menschliche Review** = Implementiert als **Post-hoc-Layer**, nicht als Gate vor dem Speichern: `POST /{contract_id}/review/start`, `/review/complete`, `/{contract_id}/fact-reviews`. Kritische ungeprüfte Angaben blockieren `complete` immer; nur nicht-kritische können mit `acknowledge_unreviewed` + Notiz quittiert werden, sonst 422.
- Zusatz-Routings vorhanden: `/documents/{document_version_id}/retry`, `/reanalyze`, `GET /source-region`.

Tests: `test_document_import.py`, `test_document_processing.py`, `test_review_critical_completion.py`, `test_customer_demo_readiness.py` (inkl. Review-Lifecycle-Grenzen) – **alle grün.**

Bewertung: Der geforderte „manuelle Importpfad" ist eine **fehlende Funktion** (kein Bug); „AI-direkt" sowie „AI mit Review" sind vorhanden und getestet.

## 3) Benutzerrechte & Organisations-Isolation

- Tenant-Boundary / Cross-Org-Verhalten durchgängig Fail-Closed: Cross-Org-Slug wird bei jeder Ressourcenfamilie als generisches 404 abgewiesen (kein Leak über Query-Slug/Objekt-IDs).
- Struktur- und Kostenstellen-Reads sind Scope-gefiltert (`app/api/routes/cost_center_routes.py:39-49`), Ownership-Routen prüfen Org-Zugehörigkeit vor Update, Änderungen werden auditiert (`app/api/routes/ownership.py`, `app/ownership/service.py`).
- Beide Auth-Modelle (Legacy `app_user` JAMAL + `account`/`account_membership`) abgedeckt; `developer`-Rechte strikt getrennt von `admin`.
- Umfangreiche Tests grün: `test_auth_e2e.py`, `test_auth_route_boundary_e2e.py`, `test_auth_security.py`, `test_contract_detail.py` (cross-org 404), `test_dashboard.py` (org_isolation), `test_pr4_equipment_work_item.py` (cross-org 404), `test_contract_search.py` (`test_org_isolation`), `test_scope_filtering.py`.

## 4) Kostenstellen-Suche & Vertrags-Kostenstellen-Verknüpfung

- **Verknüpfung existiert:** `Contract.cost_center_id` (`app/database/models/contract.py:70`), Zuweisung über `assign_contract_ownership` (`app/ownership/service.py:48`), UI `ContractOwnershipPanel.tsx`; Reads scope-gefiltert.
- **Suche „nach Kostenstellennummer": fehlt.** `app/contracts/search/service.py` enthält **keine** Kostenstellen-Filter/Code-Suche (grep-Empty); Filtermöglichkeit über `Contract.cost_center_id` gibt es nicht im SearchParams. Nur `contract_number`, `supplier`, `q`, `status`, `risk`, `warning_type`, `currency`, `sort` etc.
- Tests zur Verknüpfung (Ownership/Scope-Gate) grün.

Bewertung: Verknüpfung **implementiert**; nummernsuche über Kostenstelle **fehlt** (Feature-Lücke, kein Regression).

## 5) Zukünftige Finanzplanung (Ist-Ausgaben, genehmigte Budgets, erwartete künftige Kosten)

- **Keine** `budget`/`forecast`/`actuals`-Modelle im Datenmodell (Grep über `app/` leer). Das Konzept existiert nicht isoliert.
- Vorhanden: `annual_cost` (KI-geprüft, nur belegte Werte → hier Frankfurt korrekt auf 0 gesetzt), `ContractLifecycleDecision`/`EquipmentLifecycleRecord` (`app/database/models/lifecycle.py`) als **operative Entscheidungen** (renew/renegotiate/terminate/monitor, status planned/in_progress/…) – also ein „Planungs-Rahmen" ohne monetäre Budget-/Forecast-Spalten.
- Quelle jedes Finanzwerts: es gibt keinen Auftrag „Future financial planning with sources" außerhalb der bestehenden Kosten-Extraktion (Quelle+Seite+Confidence) + Human-Review; Lebenszyklus-Entscheidungen erfassen keine erwarteten Kosten.

Bewertung: **Fehlende Funktionalität** (Feature-Lücke) – außerhalb des MVP-Scope der Referenzversion.

## 6) Gefundene Fehler & Ursachen

- **Kein echter Code-Defekt reproduziert.** Einziger Fehlschlag im Runs: `test_security_runtime_config.py::test_valid_production_security_posture_passes` – **Umgebungs-Artefakt**: `MEDFLUX_INSECURE_DEV=true` (für die Isolations-Basis weitergegeben) collidiert mit `APP_ENV=production` (der Test setzt production-Parameter). Unter echter produktionsnaher Env (`AUTH_ENABLED=true`, `APP_SECRET_KEY` nicht default, kein insecure_dev) **26/26 grün** (Log `02b` + Recheck-Command). Bekanntes, dokumentiertes Verhalten, kein Fix nötig.
- Keine sicheren kleinen Fixes nötig → nichts am Referenz-Code geändert (kein Dirty-Worktree, HEAD weiterhin `4b62abc`).

## 7) Nicht ausführbare Tests (und warum)

- **Voll-E2E gegen Produktion 5432:** bewusst nicht ausgeführt (Auflage; Produktionsdaten unangetastet).
- **Testlauf auf WSL-Ollama 11434:** nicht gestört (Auflage), Frankfurt deshalb über temporäre lokale Ollama-Instanz 11435 mit identischer Modell-Digest ausgeführt.
- **GitHub-Actions-CI:** nicht genutzt (Auflage); stattdessen lokale Ausführung analog zur CI-Konfiguration.

## 8) Testausführung & Ergebnisse (isolierte Pipeline)

| Dossier/Suite | Anzahl | Ergebnis |
|---|---|---|
| `test_security_runtime_config` + `runtime_security_posture` unter prod-nah | 26 | passed |
| Functional Suites (Import, Processing, Intelligence, Review, Auth-E2E, Route-Boundary, CSV-E2E, Scope-Guards, PR4, Detail) | 128 | passed |
| Org/Cost/Financial-Gate (Scope, Financial-Class-Gate, Auth-Security, Review-Provenance) | 40 | passed |
| Isolation/Workflow (Dashboard-Org, Archive, Fresh-Install, PR4, Calcd-Engine, Harness v2/v3-Services) | 183 | passed |
| Read/Write-E2E (Search, Operations-CSV, Import, Processing, Review, Extraction, Intelligence, Finance-Prov) | 110 | passed |
| Warning/Queue/UAT/Storage/Source/Nav/Backup/CSV/Hybrid/Harness-money | 303 | passed |
| AI/Guards (AI-Suiten, Evidence-Fail-Closed, Harness-v3, Di-Hardening, Runtime-Security-Posture, Portfolio) | 262 | passed |
| Demo/Models/Visual-First/Region/Warning | 113 | passed |
| Final-Recheck (Detail, Scope, Route/Profile-Auth, Developer-Auth) | 60 | passed |
| **Gesamt lokal grün (einzeln ausgeführt)** | **> 1200** | **passed** |

(Logs siehe Abschnitt 9; einzelne Suiten mehrfach gelaufen, Angabe kumulativ.)

## 9) Nachweise

- Alle Konsolen-Logs (outside git): `C:\Users\JAMAL\AppData\Local\Temp\opencode\medflux-local-test-20260927\` (`02-pytest-full.log`, `06-frankfurt-e2e.log`, `07-functional-suites.log`, `08-org-cost-financial.log`, `09-isolation-workflow.log`, `10-read-write-e2e.log`, `11-warning-queue-uat.log`, `12-ai-guards.log`, `13-demo-models.log`, `14-final-recheck.log`, `ollama-11435.out/.err`).
- Frankfurt-Skript (isoliert, ohne prod-DB): `frankfurt_e2e_isolated.py` (oben im Log-Ordner).
- Basisdoku früherer lokaler Run: Branch `reports/local-test-20260927`, Commit `10b54f9` (`docs/reports/LOCAL_TEST_REPORT_20260927.md`).
- Dieser Report: Commit **siehe unter (Report-Branch)**.

## 10) Zusammenfassung & Empfehlung

Referenz-HEAD `4b62abc` ist funktional grün in allen Kernbereichen (Import AI-Pfad, Deterministik-Checks, Warnungen, Kosten-Aggregation nur mit Beleg, Org-Isolation, Review). Frankfurt-E2E reproduzierbar inkl. korrektem Finanz-Fail-Closed. Für den Ahmad-Start können drei **Feature-Lücken** (bewusst, keine Bugs) vorgemerkt werden: (a) manueller Importpfad ohne AI, (b) Suche nach Kostenstellennummer/Verknüpfungsfilter in der Vertragssuche, (c) explizite budget/forecast/actuals-Finanzplanungsdaten. Architektonische Änderungen hierfür wurden **nicht** umgesetzt (Zustimmung erforderlich).