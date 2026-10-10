# Medflux Restructure – Fortschritt

Plan: `docs/architecture/MEDFLUX_RESTRUCTURE_PLAN_20261010.md` (v2.0). Branch `design/ruhe-signal`.
Entscheidungen D1–D12 aus Plan §12 mit den vorgeschlagenen Standardwerten übernommen; der Product Owner
hat am 2026-10-10 angewiesen, alle Phasen ohne Zwischenstopp umzusetzen (ersetzt D3 für diesen Durchlauf).

| Phase | Inhalt | Status | Commit |
|---|---|---|---|
| 0 | Baseline | erledigt | (mit Phase A) |
| A | Datenwahrheit (Summen mit Abdeckung, Laufend-Definition, nicht bewertbare Fristen, Stichtag Europe/Berlin) | erledigt | siehe git log |
| B | Signal-Grundlage (R&S Phase 1) | erledigt | siehe git log |
| C | Glocke, Benachrichtigungen, Rahmen | erledigt | siehe git log |
| D | Vertragsregister mit Reitern | erledigt | siehe git log |
| E | Vertragsakte, Import, Prüfung | erledigt | siehe git log |
| F | Fristen & Aufgaben | erledigt | siehe git log |
| G | Mein Tag v3, Analysen | erledigt | siehe git log |
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

## Phase B – Signal-Grundlage (2026-10-10)

**Umgesetzt** (= Ruhe & Signal Phase 1; Antworten D4–D11 wie im Plan vorgeschlagen)
- Tokens v3 hell und in beiden dunklen Blöcken (`tokens.css`), neu `--color-icon`, `--color-ai-border`, `--color-neutral-border`.
  Kontraste nachgerechnet: alle Signaltexte ≥ 5,6:1 auf ihrem Grund (dunkel ≥ 6,9:1), `--color-border-strong` 3,5:1 / 3,6:1.
- `components/ui/Signal.tsx` (+ `SignalIcon`): sechs Stufen, jede mit eigener Form, Symbol `aria-hidden`, Wort trägt die Bedeutung.
- `Badge`, `StatusBadge` (Form statt Punkt), `InlineAlert`, `Toast` mit den Formen der Stufen; API unverändert.
- `KpiTile` immer neutral (graues Symbol vor der Beschriftung), neue Eigenschaft `signal`; `tone` bleibt nur zur Kompatibilität.
- `EmptyState variant="calm"` (grau, kein Grün); `compact` zeigt dasselbe.
- Alte Alias-Tokens (`--sev-*`, `--status-*`) entsprachen bereits der Zuordnung aus dem Inventar §5.
- Stilrichtlinie `/developer/components` zeigt die sechs Signale; `docs/VISUAL_IDENTITY.md` (Entscheidung 2026-10-10) und
  `docs/FRONTEND_CONVENTIONS.md` aktualisiert.

**Tests**: `test/signal.test.tsx` (neu), `test/kpi-tile.test.tsx` und `test/my-day.test.tsx` an die neutralen Kacheln angepasst.
**Verifikation**: `npm run verify` grün (51 Testdateien).

## Phase C – Glocke, Benachrichtigungen, Rahmen (2026-10-10)

**Ursache des Befunds „Glocke 1, Postfach 0“**: Das Abzeichen addierte offene Aufgaben/Freigaben der Organisation
(ohne Lesestatus) und persönliche ungelesene Benachrichtigungen; das Postfach zeigte nur Letztere.

**Umgesetzt**
- Backend: `GET /api/inbox/summary` liefert `unread_for_me` und `work_queue_open` mit denselben Abfragen wie die Listen
  (`deadlines.service.unread_count`, `notifications.work_queue_count`). `GET /api/inbox` mit `offset`, `unread_only`, `total`;
  Bereichsfilter jetzt in der Abfrage statt nachträglich. „Alle als gelesen“ gilt nur für den sichtbaren Bereich.
  Feed liefert die echte Gesamtzahl und verlinkt Aufgaben auf den Vertrag (`?tab=deadlines`) statt auf `/work-queue`.
- „Meine“ Termine: eine Definition (`owned_deadline_condition`: zugewiesen oder – ohne Zuweisung – verantwortlich, inkl.
  Vertretung) für Postfach-Wiedervorlage und `/api/deadlines?mine=true` (vorher nur Zuweisung).
- Glocke: zwei Bereiche „Für mich“ (zählt im Abzeichen) und „Arbeitsvorrat“ (eigene Zahl, kein Abzeichen); Ladefehler zeigt
  keine 0; Klick auf eine Benachrichtigung markiert nur diese als gelesen und öffnet das Ziel (keine Aufgabe wird erledigt).
- `/postfach` ist das vollständige Protokoll „Benachrichtigungen“ (seitenweise, Filter „Nur ungelesene“); die Wiedervorlage
  steht unter Fristen & Aufgaben → Termine → „Nur meine“ (`/postfach#wiedervorlage` leitet dorthin). Postfach nicht mehr in der
  Seitenleiste, aber über Strg+K („Benachrichtigungen“) und `g p` erreichbar.
- Rahmen (R&S Phase 2): Navigationssymbole `--color-icon`, aktiv in Akzentfarbe; Status „Lokale KI“ als ruhige Form (neutral),
  nur bei Ausfall kritisch bzw. ohne Modell „prüfen“.

**Tests**: `backend/tests/test_restructure_notifications.py` (T17, T29, T08-Teil), `frontend/test/deadlines.test.tsx` erweitert;
`test_notifications_actor_scope.py` Mock um `scalar` ergänzt.
**Verifikation**: Backend 1586 passed / 7 umgebungsbedingt; `npm run verify` grün (51 Testdateien).

## Phase D – Vertragsliste mit Reitern (2026-10-10)

**Befund**: `/register`, `/review` und `/archiv` waren drei Seiten und drei Menüpunkte um dieselbe Komponente; nur `?ansicht=`
stand in der Adresse, Filter/Sortierung gingen beim Zurückkehren verloren, eine gespeicherte Reiter-Ansicht konnte die Liste
unbemerkt ins Archiv umschalten.

**Umgesetzt**
- `/register` „Verträge“ mit Reitern **Bestand · Zu prüfen · Archiv** und Zahlen (`GET /api/register/grid/counts`, gleiche Sichtbarkeit
  wie die Liste, ohne gelöschte). Zu prüfen nur für Prüfrollen, Archiv nur für Bearbeiter (wie vorher die Menüpunkte).
- `/review` und `/archiv` leiten mit allen Parametern auf `/register?ansicht=review|archive` weiter.
- Listenzustand vollständig in der Adresse (U4): `sicht` (gespeicherte Ansicht), `q`, `filter`, `sort`, `gruppe`, `seite`; beim Laden
  gelesen, bei jeder Änderung zurückgeschrieben. Reiter-Ansichten erscheinen nicht in der Auswahl „Ansicht“ und werden im Bestand nie
  aus dem lokalen Speicher geöffnet.
- Eigener Leerzustand bei Filtern ohne Treffer mit „Filter und Suche zurücksetzen“ (U13); Text je Reiter bei echter Leere.
- „Prüfen“ merkt sich die Reihenfolge der aktuellen Seite (`sessionStorage medflux.reviewQueue`) für „Weiter zum nächsten Vertrag“ (Phase E).
- Alle Weiterleitungen behalten ihre Parameter (`lib/redirect-params.withParams`): `/contracts`, `/review`, `/archiv`, `/termine`,
  `/verlaengerungen`, `/work-queue`, `/partners`, `/settings/catalogs`, `/settings/organization` (U12).
- Seitenleiste nach Plan §5: **Arbeit** (Mein Tag, Verträge, Fristen & Aufgaben, Geräte, Analysen, Nachweise*) und **Daten & Verwaltung**
  (Stammdaten, Historie*, Verwaltung, Entwicklung); *Nachweise und Historie wandern in E bzw. H. Prüfungen, Archiv, Import, Postfach sind
  über Reiter, „Vertrag hinzufügen“ (Aus Dokument / Manuell erfassen), Glocke und Strg+K erreichbar. Vertragsakte und Import markieren „Verträge“.

**Tests**: `frontend/test/restructure-register.test.tsx` (T15, T20, T30, U13), `backend/tests/test_restructure_data_truth.py::test_register_tab_counts`;
angepasst: `shell.test.tsx`, `register-grid.test.tsx`, `rules-and-contract-help.test.tsx`, `analytics-notes.test.tsx`, e2e-Seitenlisten.
**Verifikation**: Backend 1587 passed / 7 umgebungsbedingt; `npm run verify` grün (52 Testdateien).

## Phase E – Vertragsakte, Import, Prüfung (2026-10-10)

**Umgesetzt**
- Reiter der Vertragsakte (Schlüssel unverändert, Links bleiben gültig): Übersicht · **Vertragsdaten** · **Fristen & Aufgaben** · Finanzen ·
  **Dokumente** (Dokument · Nachweise · Prüfung · Anlagen · **Korrekturen**) · **Verknüpfungen** · Verlauf (U11).
- „Fristen & Aufgaben“ im Vertrag zeigt zusätzlich die offenen Aufgaben dieses Vertrags (dieselben WorkItems wie im Reiter Aufgaben).
- Kopf: Geschäftsstatus neutral (D1/D4), „KI-Prüfung offen“ als ai-Signal, KI-Risiko hoch/mittel als warning (D6); Löschantrag führt zu `/register`.
- Prüfreihenfolge (U5): „Prüfen“ in „Zu prüfen“ merkt die Reihenfolge; in der Prüfung „Vertrag N von M“, Zurück, „Weiter zum nächsten Vertrag“,
  am Ende „Zurück zur Liste“ (`ReviewQueueNav`, `lib/review-queue.ts`).
- `/nachweise` ist eine Weiterleitung: mit `?contract=<uuid>` in Dokumente → Nachweise des Vertrags (weitere Parameter bleiben), sonst in „Zu prüfen“.
  Die frühere Auswahlseite war eine Kopie der Vertragsakte; ihre Tests (Seitenauswahl, Detailfehler) entfallen mit ihr, die Belegdarstellung
  bleibt über `contracts-detail.test.tsx` und `evidence-pane-presentation.test.tsx` abgedeckt. Menüpunkt entfernt.
- Faktprüfung: Status als Signal (Bestätigt/Korrigiert = done, offen = „KI-Vorschlag“ ai) statt Farbpunkt; Icon-Knöpfe ✓/✎/◷ mit sprechendem Namen;
  ein sichtbares „
“ im Prüfkopf entfernt.
- Nachweise: drei Dimensionen getrennt benannt – Lage, „KI-Konfidenz“ (kein Prüfergebnis), menschliche Prüfung im Reiter „Prüfung“.
- Doppelte Prüfaktionen (T14): `record_fact_action` und `record_override` sperren den Vertrag (`FOR UPDATE`) und speichern eine identische Aktion
  derselben Person innerhalb von 30 s nicht erneut. Optionaler Versionsstand `expected_reviewed_at`: weicht er ab, antwortet der Server 409
  (`ReviewConflict`) statt still zu überschreiben; die Oberfläche sendet ihn mit und lädt bei 409 neu. Keine Schemaänderung nötig.
- Import: ohne gewähltes Krankenhaus kein Weiter, sobald Krankenhäuser eingerichtet sind („Alle Krankenhäuser“ ist kein Ablageort); Dublette als Hinweis (info).
- Signale statt Farbe in Kündigungs-Dringlichkeit (verstrichen kritisch, ≤ 30 Tage prüfen, sonst ruhig), Terminliste, Tageslauf, Anhänge, Rechtematrix.

**Tests**: `backend/tests/test_restructure_review_idempotency.py` (T14), `frontend/test/review-queue.test.tsx`, `nachweise-redirect.test.ts` (T13/T20);
angepasst: `contracts-detail`, `contract-detail-reload-scroll`, `fact-confirm-reviewer`, `evidence-pane-presentation`, `interaction-audit`.
**Verifikation**: Backend 1590 passed / 7 umgebungsbedingt; `npm run verify` grün.

## Phase F – Fristen & Aufgaben (2026-10-10)

**Umgesetzt**
- Termine: Überfälliges als eigener Abschnitt vor „Anstehend“, mit Signal „Überfällig“ statt eingefärbter Zeile; „Heute“ als warning.
  Herkunft je Termin ausgeschrieben („Berechnet aus den Vertragsdaten“ / „Manuelle Wiedervorlage“) plus ai-Signal bei ungeprüften KI-Werten.
- „Nur meine“ und Zeitraum (`nur=meine`, `zeitraum=7|30|90|180|alle`) in der Adresse – Mein Tag kann gezielt verlinken; Reiterwechsel räumt beides ab.
- Hinweis „N Verträge – Kündigungsfrist nicht berechenbar“ in Termine und Kündigungsentscheidungen (aus `not_evaluable`, Phase A), mit Link in die Liste.
- Leere Zustände ruhig und ehrlich: „Keine Termine für diese Auswahl“ mit „Alle offenen Termine anzeigen“ vs. „Keine offenen Termine“; Aufgaben ebenso (kein grüner Haken).
- Fehler beim Laden zeigen „Erneut versuchen“ statt einer leeren Liste.

**Geprüft, unverändert gültig** (bestehende Tests `test_deadlines_api.py`): Neuberechnung behält dieselbe Termin-ID (T07), berechnete Termine
sind nur über die Vertragsdaten änderbar (422/409), der Tageslauf erzeugt am selben Tag keine zweite Erinnerung (Dedupe-Schlüssel), Erledigen,
Entscheidung, Kündigung und Lesen bleiben getrennte Vorgänge (T09).

**Tests**: `frontend/test/restructure-deadlines.test.tsx` (T08, T24).
**Verifikation**: `npm run verify` grün (53 Testdateien); Backend unverändert seit Phase E (1590 passed).

## Phase G – Mein Tag v3 und Analysen (2026-10-10)

**Mein Tag** (= R&S Phase 3; Entwurf `Claude outputs/Mein-Tag-Entwurf-v3.html` nur als Bildvorlage)
- Kopf ohne Karte und ohne Eyebrow (Serifentitel + Datum, „Vertrag anlegen“ rechts).
- **Lagebild**: ein Satz („Heute brauchen N Themen Ihre Aufmerksamkeit“ mit warning-Form bzw. „Heute ist nichts dringend“ neutral).
  N zählt Themen, nicht Verträge: kritische Portfolio-Hinweise, überfällige eigene Termine, offene KI-Prüfung, Entscheidungen ≤ 30 Tage.
  Bis zu drei Signale, ruhige Zustände als neutrale Signale („Keine Termine diese Woche“).
- **Drei Kennzahlen**, neutral: Laufende Verträge (mit „N in Arbeit“), Jährliche Kosten (Abdeckung bzw. Signal „Kosten fehlen bei N Verträgen“
  statt „0,00 €“), Kündigungsfristen in 90 Tagen. Die Kachel „Ungelesene Erinnerungen“ entfällt (Glocke).
- **Zu erledigen – nach Dringlichkeit** (Portfolio): ganze Zeile als Link, Signal mit Wort (Kritisch · KI-Prüfung · Prüfen), Zahl, Text und
  Erläuterung; Überschrift nennt „N Problemarten“ (keine Summe von Zeilen als Vertragszahl). Kritisch = Laufzeitangaben unvollständig
  (Ende/Frist unberechenbar); Prüfen = ohne Verantwortliche, Frist ohne Erinnerungsempfänger, ohne Kosten, Löschprüfung.
- Rechts **persönlich**: Meine Termine (Überfälliges zuerst mit Signal; Links `nur=meine&zeitraum=7` bzw. `zeitraum=alle`) und Entscheidungen
  (ehrlicher Leerzustand bei unbewertbaren Verträgen). Ab 1100 px zwei Spalten 1,5 : 1.

**Analysen** (= R&S Phase 7): Kennzahlen mit Abdeckung und Definitionen (Phase A); keine Jahreskurve aus Nullen; der doppelte Block
„Handlungsbedarf im Portfolio“ ist jetzt eine kurze „Datenqualität des Berichts“ mit Signalen und Links (die Arbeitsliste steht auf Mein Tag).

**Tests**: `frontend/test/my-day.test.tsx` neu geschrieben (T01/T02/T24 auf der Oberfläche, axe).
**Verifikation**: `npm run verify` grün (53 Testdateien).
