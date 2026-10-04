# STEP 3 - Integrations-Review

**Datum:** 2026-09-27
**Branch:** `step3/integration-20260926` (Worktree: `Temp\opencode\step3-integration`)
**Basis:** `origin/JAMAL` (`356975d`)
**Status:** Abschlussbewertung. KEIN Merge, KEINE Bereitstellung.

---

## 1. Scope und Invarianten

- **Canonical (unveraendert, nur Lese-Zugriff):** `C:\Users\JAMAL\Desktop\Medflux-Integrated-Test`
  = Referenzstand von `origin/JAMAL`; dessen venv ist der einzige Ausfuehrungskontext
  (docling, PyMuPDF, sqlalchemy, psycopg).
- **Stale, nie verwenden:** `C:\Users\JAMAL\Desktop\Medflux`.
- **Integrations-Basis:** Worktree `step3-integration`, Branch `step3/integration-20260926`.
- Rollback jederzeit moeglich (siehe Abschnitt 7); Produktionsdaten, 5432
  (`MedFluxPostgres18`) und Bereitstellung unangetastet.

## 2. Commit-Liste (Integration, ueber `356975d` hinaus)

| Commit | Inhalt |
|--------|--------|
| `42a7564` | chore(dev): lokaler MedFlux-Launcher + isolierte Postgres-Hilfsskripte (Runde-4) |
| `b14bfe1` | feat(harness): Runde-4-Haertung - OCR-Toleranz, Geld-Locator, Kontextbudget |
| `db0aa30` | docs: Runde-4-Haertung + lokaler Launcher |
| `cb0431c` | merge(audit): Finance-Provenance (striktes `_steady_annual_amount(expected_years=)` + `derived_facts`, 3-Way-V3-Semantik-Merge) |
| `472f917` | fix(ai): lokaler Ollama-Streaming-Provider (getrennte Timeouts), `keep_alive`, Vision/Visual-First-Config-Knobs |
| `87671fc` | feat(harness): Visual-First-Seitenbild-Ablesung + STEP-5-Ambiguity-Guard + V3-Integration (`visual_first_experiment_enabled`) |
| `1854780` | chore(config): Visual-First-Konfigurations-Knobs aktiviert (config.py Defaults synchron) |
| `9977816` | docs: Projektfortschritt (Runde-4 + STEP-3) |
| `c5c9aaa` | feat(harness): Gate 1 - Finanz-Klassifikations-Guard (EUR 12.000) + Tests |
| `7696677` | fix(harness): Gate 1 auf geloester Seite + Seitentext-Anker-Evidenz |
| `d27550b` | fix(ai): `generate()` sendet `stream=false` (NDJSON nur fuer Harness-/Chat-Pfade) |

Basis-Head der Branch fuer das Review: Commit `d27550b` (Worktree-Clean, verifiziert).

## 3. Semantischer Vergleich vs. Canonical

### 3.1 `backend/app/ai/harness/v3.py` (modified)
- **Neu:** Finanz-Klassifikations-Guard
  `_financial_classification_verified(fact, visual_first_rows, *, page_texts=None,
  resolved_page=None)` fuer `_PERIOD_FIELDS` (annual/manual/expected).
  Akzeptanz NUR ueber Zeitraum-Anker im `fact.quote`, deterministischen Seitentext-Anker
  (`page_texts[target_page]`) oder korroborierte Beobachtung mit Anker in Label/Quote.
  Auswertung nach `locate()`-Seitenaufloesung. Zurueckweisung fail-closed:
  `financial_classification_unverified` + Issue "Financial classification requires manual
  review" + `continue`. Ohne Visual-First-Zeilen (`visual_first_rows` leer) unveraenderter
  Kontrollpfad (True).
- Behavior-Delta nur unter aktiviertem Visual-First und nur fuer ambige Jahresbetraege
  ohne Anker; der Gesamtpfad (Provenance-Merge, Ergebnisstruktur, Seitenreferenzen)
  ist unveraendert.

### 3.2 `backend/app/ai/providers/ollama.py` (modified)
- Bis `d27550b`: `generate()` sendete `stream=true` (NDJSON) - korrekt fuer Harness/Chat,
  aber falsch fuer den `generate()`-Vertrag (Tests erwarten einzeilige Antwort).
- Nach `d27550b`: `_payload(..., *, stream: bool = True)`; `generate()` → `stream=False`
  (einzeiliges JSON), Harness-/Chat-Pfade → NDJSON (`stream=True`).
- Getrennte Timeouts connect/read/write/pool; `keep_alive`-Konfig aus config.py.

### 3.3 `backend/app/core/config.py` (modified)
- Provider-Vision-/Visual-First-Knoebbles (Vision-Output-Tokens, Visual-First enabled,
  max_pages/max_reviews, Kontext-/Timeout-Knobs) - defaults: Visual-First deaktiviert
  (opt-in), sonst verhaltensneutral. Keine Aenderung des Basis-Konfigschemas
  (pbkdf2-Hashing, Secret-Policies, Pfade).

### 3.4 Neu hinzugefuegt (added)
- `backend/app/ai/harness/visual_first.py`: lokale Seitenbild-Ablesung
  (PyMuPDF-Rendering + qwen3-vl:8b-instruct), Beobachtungen mit Seite + Tick/Quote,
  Budget-/Timeout-Schutz.
- `backend/app/ai/harness/visual_first_bridge.py`: Map Task→Frame→page, Dedupe,
  STEP-5-Ambiguity-Guard (multipage / other-page / unverified → review-only), Matcher/
  Wahrheitstabelle.

### 3.5 Tests (4 modified, 4 added)
- modified: `test_contract_identity_contact.py`, `test_evidence_dedupe.py`,
  `test_harness_v3_services.py`, `test_runtime_security_posture.py` (Angleichung an
  Item-Typ/Status-Enum und Visual-First-Gate; jeweils nur erwartungsseitige Anpassung).
- added: `test_visual_first_bridge.py` (12), `test_visual_first_isolated.py`,
  `test_finance_provenance_audit.py`, `test_financial_classification_gate.py` (3).

## 4. Verbleibende Konfliktpunkte / Env-Hinweise

1. **Auth / Env-Asymmetrie (dokumentiert, vorbestehend):**
   - API-/Auth-E2E-Tests erwarten `AUTH_ENABLED=false`; unter canonical-artiger
     Env (`AUTH_ENABLED=true` + gultiges Secret) ergeben sich 38 401-Failures
     (vorbestehend, kein Regression-Risiko).
   - `test_security_runtime_config.py` (11 Tests) erwartet Produktions-Env-Bild:
     `AUTH_ENABLED=true` + nicht-Default-Secret UND Abwesenheit von Unit-Dev-Variablen.
     Unter Unit-Dev-Env (`auth=false` + `MEDFLUX_INSECURE_DEV=true`) schlaegt genau
     dieser eine Test (`test_valid_production_security_posture_passes`) fehl
     (Environment-Leak-Artefakt).
   - Vollsuite-laeufer-Konfig: `AUTH_ENABLED=false` + `MEDFLUX_INSECURE_DEV=true`,
     `DATABASE_URL`=WSL-Test-Postgres (55432), KEIN `MEDFLUX_UNIT_ONLY`
     (`MEDFLUX_UNIT_ONLY` erzwingt die Phantom-URL → DB-Tests haengen).
2. **LlamaIndex:** `test_llama_archive*.py` weiterhin Environment-Gap in den
   verfuegbaren venvs (keine neuen Dateien, keine Aenderungen betroffen).
3. **Frankfurt-Fachluecken (unveraendert fail-closed):** `equipment`/Services/SLA 0/0/False,
   termination-Eckdaten None. Keine Invented-Werte.

## 5. Exakte Test-Matrix (final)

| Suite / Run | Ergebnis |
|---|---|
| Vollsuite auth-off + Dev-Variablen, DB=WSL-55432 | **988 passed, 1 failed** (Env-Leak-Artefakt, s.o.) |
| `test_security_runtime_config.py` unter Produktions-Env-Bild | 11/11 passed |
| Aenderungsflaechen-Unit-Set (harness v2/v3/money_ocr/services, bridge, isolated, finance_provenance, financial_classification_gate) | 101 passed |
| Frankfurt-Benchmark integriert (Gate 1 Re-Run, `frankfurt-gate2.log`) | Exit 0; contested amount abgewiesen |
| API/Auth-E2E unter auth-off-Env | Teil der 988 (grün) |

Gate-1-Re-Run-Diagnostik: `FULL_REAL_CONTESTED_AMOUNT_ASSIGNED_ANNUAL False`,
`FULL_REAL_ANNUAL_COST_PRESENT False`, akzeptierte Felder 7→6,
`financial_classification_unverified: 1`, Seite 3: uncertain 3 / vision_only 1 / ocr_only 5
(keine korroborierten Zeilen), `PAGE_TEXT_HAS_ANCHOR False`, `requires_review True`.

## 6. Datei-Inventar (executable, vs. Canonical per SHA256)

| Aenderung | Datei |
|---|---|
| ADDED | `app/ai/harness/visual_first.py` |
| ADDED | `app/ai/harness/visual_first_bridge.py` |
| ADDED | `tests/test_finance_provenance_audit.py` |
| ADDED | `tests/test_financial_classification_gate.py` |
| ADDED | `tests/test_visual_first_bridge.py` |
| ADDED | `tests/test_visual_first_isolated.py` |
| MODIFIED | `app/ai/harness/v3.py` |
| MODIFIED | `app/ai/providers/ollama.py` |
| MODIFIED | `app/core/config.py` |
| MODIFIED | `tests/test_contract_identity_contact.py` |
| MODIFIED | `tests/test_evidence_dedupe.py` |
| MODIFIED | `tests/test_harness_v3_services.py` |
| MODIFIED | `tests/test_runtime_security_posture.py` |
| REPLACED / OBSOLETE | keine |

Doku: `docs/PROJECT_PROGRESS.md` als einzige Doku-Aenderung (Runde-4 + STEP-3).

## 7. Rollback-Prozedur

1. Merge unterbleibt, solange der Eigentuemer nicht freigegeben hat. Kein Push ausserhalb
   des lokalen Branches.
2. Worktree-Verwurf: Branch `step3/integration-20260926` ist ein lokaler Branch ueber
   `origin/JAMAL`; alle 11 Commits liegen oberhalb von `356975d`. Entfernen =
   `git branch -D step3/integration-20260926` + Worktree loeschen; `origin/JAMAL` bleibt
   unberuehrt.
3. Falls ein Teil-Merge doch staende (nicht geplant): die drei betreffenden canonical-
   Dateien (`v3.py`, `ollama.py`, `config.py`) via `git checkout origin/JAMAL -- <pfad>`
   zuruecksetzen; neue Dateien/Tests entfernen; `docs/PROJECT_PROGRESS.md`-STEP-3-Abschnitt
   nicht mitfuehren.
4. Infrastruktur: Test-Postgres-Cluster `/opt/medflux-test-pg` (55432) kann jederzeit via
   `provision_pg.sh --cleanup` entfernt werden; Produktions-PG 5432 war nie beruehrt.

## 8. Bewertung / Empfehlung

- **Gate 1 (Finanz-Klassifikation):** verifiziert - ambige Jahresbetraege ohne
  Zeitraum-Anker verlassen die Kosten-Domain; fail-closed mit Review-Hinweis.
- **Gate 2 (isolierte Test-DB):** verifiziert - WSL-PostgreSQL 18.6, Port 55432,
  eigene Credentials, Produktion unangetastet; Vollsuite erstmals nahezu voll gruen.
- **Gate 3 (Review):** vorliegend - Deltas der 13 Dateien sind semantisch nachvollziehbar,
  Testlastig, default-neutral (Visual-First opt-in). Der einzige rote Test ist ein
  dokumentiertes Env-Artefakt ohne Produktionsrelevanz.
- **Go/No-Go:** Beide Sicherheits-Gates verifiziert, Review-Delta vollstaendig
  dokumentiert, Testbasis gruen (ein dokumentiertes Env-Artefakt). Der Branch ist bereit
  fuer die Freigabe-Entscheidung des Eigentuemers. Merge in `origin/JAMAL` oder jede
  Bereitstellung erst nach expliziter Freigabe.