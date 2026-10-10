# Medflux Restructure – Fortschritt

Plan: `docs/architecture/MEDFLUX_RESTRUCTURE_PLAN_20261010.md` (v2.0). Branch `design/ruhe-signal`.
Entscheidungen D1–D12 aus Plan §12 mit den vorgeschlagenen Standardwerten übernommen; der Product Owner
hat am 2026-10-10 angewiesen, alle Phasen ohne Zwischenstopp umzusetzen (ersetzt D3 für diesen Durchlauf).

| Phase | Inhalt | Status | Commit |
|---|---|---|---|
| 0 | Baseline | erledigt | (mit Phase A) |
| A | Datenwahrheit (Summen mit Abdeckung, Laufend-Definition, nicht bewertbare Fristen, Stichtag Europe/Berlin) | erledigt | siehe git log |
| B | Signal-Grundlage (R&S Phase 1) | offen | |
| C | Glocke, Benachrichtigungen, Rahmen | offen | |
| D | Vertragsregister mit Reitern | offen | |
| E | Vertragsakte, Import, Prüfung | offen | |
| F | Fristen & Aufgaben | offen | |
| G | Mein Tag v3, Analysen | offen | |
| H | Stammdaten, Verwaltung, Geräte, Verlauf | offen | |
| I | Aufräumen, Kompatibilität, Abschluss | offen | |

## Testumgebung auf diesem Rechner

Kein WSL-Testcluster. Backend-Tests laufen in Wegwerf-Containern (`medflux-pytest-pg` = postgres:18,
`medflux-pytest-py` = python:3.12 mit `/venv`, Backend schreibgeschützt unter `/src`, Kopie nach `/work`, CI-Variablen gesetzt).

## Phase 0 – Baseline (2026-10-10)

- Backend: `pytest -q --ignore=tests/test_rebuild_document_index.py` → **1577 passed, 3 skipped, 7 failed**.
  Alle 7 Fehler und der ignorierte Sammelfehler sind umgebungsbedingt: die Tests lesen Dateien außerhalb von
  `backend/` (`.github/workflows/release-gate.yml`, `scripts/verify_backup.py`, `scripts/rebuild_document_index.py`),
  die im Container nicht eingehängt sind. Kein Bezug zu dieser Arbeit.
- Frontend: `npm run verify` grün (49 Testdateien, 215 Tests, Build ok).
- Code-Befunde mit Datei/Zeile: Plan §3. Zu erhaltende Funktionen: gespeicherte Ansichten, Sortierung/Gruppierung,
  Excel/PDF-Export, Archiv-Wiederherstellung, Stapel-Import, Neuanalyse, Dokumentversionen, Deep-Links
  (`?tab=`, `?subtab=`, `?ansicht=`, `?filter=`, `?q=`).

## Phase A – Datenwahrheit (2026-10-10)

**Umgesetzt**
- Summen mit Abdeckung: `reports/grid.py` `MoneyTotals`/`money_totals` – je Betragsspalte Summe der bekannten Werte in EUR
  (null, wenn keiner bekannt), `coverage` (bekannt/fehlend), andere Währungen getrennt in `other_currencies` (keine Umrechnung,
  vorher wurden Fremdwährungen still als EUR summiert). Gilt für Raster-Summen, Gruppen, Excel (Info-Blatt mit Abdeckung),
  Portfolio (Mein Tag, Analysen, Portfolio-Excel). Unbekannt wird nirgends mehr 0.
- Laufend-Definition (D1): `register/status.is_running` – gültig/gekündigt und am Stichtag innerhalb der Laufzeit;
  „In Arbeit“ zählt getrennt (`totals.in_progress`). Portfolio liefert `definitions` als Klartext.
- Laufzeitangaben: neue Rasterspalte `term_status` (Vollständig / Unvollständig / Unbefristet). Hinweis `no_end` zählt nur noch
  unvollständige Laufzeiten (vorher auch unbefristete Verträge) und filtert auf `term_status`.
- `GET /api/register/renewals` liefert `not_evaluable` (Verträge ohne berechenbare Kündigungsfrist).
- Stichtag: `app/core/clock.today_local()` mit `ORG_TIMEZONE` (Standard `Europe/Berlin`, validiert beim Start, in `.env.example`);
  alle `date.today()`-Aufrufe in Routen/Diensten ersetzt. Rechenfunktionen bleiben mit explizitem Datum.
- Frontend: `components/ui/CoverageValue.tsx` + `coverageNote()`; Register-Fußzeile und Gruppensummen, Analysen-Kacheln,
  Kostenverteilung und Jahreskurve (keine Nullkurve ohne Daten), Mein-Tag-Kostenkachel; Vertragskopf trennt „Gepflegt“
  von „KI-Vorschlag“ mit Sprung „In Finanzen übernehmen“ (Übernahme über die bestehenden Finanz-Vorschläge);
  „Alles entschieden“ nur noch, wenn keine Verträge unbewertbar sind.

**Beabsichtigte Verhaltensänderungen**
- Kennzahl „Laufende Verträge“ zählt keine Verträge „In Arbeit“ mehr und keine mit abgelaufenem Ende.
- Kostensummen ohne gepflegte Werte zeigen „—“ statt „0,00 €“; Teilsummen sind gekennzeichnet.
- Test `test_register_grid.py::test_excel_export_portfolio_and_cover` an die Laufend-Definition angepasst.

**Tests**: `backend/tests/test_restructure_data_truth.py` (T01, T02, T05, T21, T26, T27, T28), `frontend/test/coverage-value.test.tsx`.
- Zusätzlich angepasst: `test_register_gaps.py::test_cost_centre_split_in_grid_and_portfolio` (Vertrag vor dem Portfolio auf „gültig“).

**Verifikation**: Backend 1583 passed / 8 umgebungsbedingt (wie Baseline); Frontend `npm run verify` grün (50 Testdateien).
