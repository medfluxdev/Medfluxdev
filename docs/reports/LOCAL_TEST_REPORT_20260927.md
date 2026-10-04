# MedFlux — Lokaler Testbericht (ohne GitHub Actions)

**Datum:** 2026-09-27
**Branch:** `step3/integration-20260926` (Worktree, HEAD provisorisch beim Lauf: `4b62abc`)
**Umgebung:** Lokal (Windows), isolierte Test-DB WSL PostgreSQL 18.6 auf `127.0.0.1:55432`
(`postgresql+psycopg://medflux_test:***@127.0.0.1:55432/postgres`, `AUTH_ENABLED=false`,
`MEDFLUX_INSECURE_DEV=true`), venv = `Medflux-Integrated-Test\backend\.venv`.
Produktions-DB (5432 / lokale JAMAL-Instanz) unangetastet; keine Bereitstellung.

## Zusammenfassung

| # | Befehl | Ergebnis |
|---|--------|----------|
| 1 | Backend `python -m compileall -q app tests` | PASS (Exit 0) |
| 2 | Backend `python -m pytest -q` | 999 passed / 1 failed (dokumentiertes Env-Artefakt, s. u.) |
| 3 | Frontend `npm run verify` | PASS (lint, 152 Tests, Next.js-Produktionsbuild) |
| 4 | `scripts/test_start_local_postgres.ps1` | PASS (5/5 Checks) |

Alle Logs liegen außerhalb des Repos unter
`C:\Users\JAMAL\AppData\Local\Temp\opencode\medflux-local-test-20260927\`
(`01..05-*.log`) — nur dieser Bericht ist eingecheckt.

## Detail

### 1. compileall
`python -m compileall -q app tests` → **Exit 0**. Kein Syntaxfehler.

### 2. pytest (vollständig, DB-gestützt)
`999 passed, 1 failed, 6 warnings in 21.84s` — identisch mit der dokumentierten
Ausgangslage (Gate-2-Runde) plus der neuen Fail-Closed- und Euro-Varianten-Tests
(997 → 999, +2). **Kein Regression.**

Einziger Fehlschlag: `tests/test_security_runtime_config.py::test_valid_production_security_posture_passes`
→ `RuntimeError: MEDFLUX_INSECURE_DEV=true ist in pilot/production nicht erlaubt.`
Dies ist das bekannte **Environment-Leak-Artefakt** (die Test-Umgebung setzt
`MEDFLUX_INSECURE_DEV=true`; der Test prüft bewusst das gegenteilige Produktions-Bild).
Nachweis: Derselbe Test unter produktionsnaher Env (`AUTH_ENABLED=true`,
`APP_SECRET_KEY` nicht-default, ohne `MEDFLUX_INSECURE_DEV`) → **11 passed, Exit 0**.

### 3. Frontend `npm run verify` (= lint && vitest && next build)
- `node_modules` fehlte im Worktree → installiert via `npm ci` (Lockfile, 502 Pakete,
  kein `--production`-Bezug, keine Konfigurationsänderung).
- **Lint:** fehlerfrei.
- **Tests (vitest):** 29 Testdateien, **152 passed** (akt-Warnungen und jsdom-
  `HTMLCanvasElement.getContext`-Meldung sind bekannte, unkritische Test-Setup-Warnungen).
- **Build:** Next.js 14.2.15 Produktionsbuild erfolgreich (25 Routen, statisch/dynamisch).
  2 unkritische ESLint-Hooks-Warnungen (`react-hooks/exhaustive-deps`) in
  `ContractBackendAnalysisPanel.tsx` / `ContractLifecyclePanel.tsx`; npm meldet
  deprecated-Pakete und `allow-scripts`-Hinweise (esbuild/unrs-resolver) — keine Fehler.

### 4. Launcher / PostgreSQL-Startskript
`scripts/test_start_local_postgres.ps1` → **Exit 0, ["PASS"]-Checks**:
- PowerShell-Syntax
- Kein `pg_ctl start`-Pipeline-Zweig
- Bare TCP-Listener wird NICHT als PostgreSQL-ready gemeldet (Identitäts-Probe)
- PostgreSQL-Wire-Protocol-Responder wird erkannt (Identitäts-Probe positiv)
- Fehlender `pg_ctl` schlägt schnell fehl (missing-pgctl path)

## Nicht ausführbar / umgebungsbedingt ausgeklammert

- Es wurde **absichtlich nichts über GitHub Actions** ausgeführt (lokaler Lauf gemäß Auftrag).
- `gh` (GitHub-CLI) ist auf dieser Maschine nicht installiert → der Bericht wird per
  `git push` eines Berichts-Branches hochgeladen statt per PR-Automatik.
- AI-/GPU-benchmarklastige Strecken (Frankfurt-Original, Ollama `qwen3-vl:8b-instruct`,
  Docling) wurden **nicht** erneut ausgeführt — nicht Teil dieser Testmatrix, erfordern
  GPU-Freigabe/Zeitfenster. Letzter Stand dokumentiert in `docs/PROJECT_PROGRESS.md`.
- `test_llama_archive*.py` (LlamaIndex) — vorbestehender Environment-Gap der verfügbaren
  venvs; unabhängig von diesem Lauf.
- Die drei Document-Processing-Dateien
  (`test_document_processing`/`test_contract_extraction`/`test_document_intelligence`)
  hängen an echten Docling/PDF/Local-AI-/DB-Läufen — umgebungsbedingt, außerhalb des
  grünen Scopes der Suiten (vorbestehend, dokumentiert).

## Tatsächliche Befunde / offene Punkte

- Sicherheits-Konfiguration ist **vollständig grün unter produktionsnahem Env-Bild**
  (11/11 einschließlich `test_valid_production_security_posture_passes`).
- Kein Dritt-Befehl, kein Install, keine Änderung an Config, `.env` oder DB-Params der
  Produktion. `git status` des Worktrees nach dem Lauf: sauber (keine Spuren; Bericht wird
  auf eigenem Branch gepusht).
- Kein Merge in `JAMAL`, keine Bereitstellung, kein Tag erstellt.