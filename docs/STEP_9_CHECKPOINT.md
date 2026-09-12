# Medflux — STEP 9 Checkpoint (Deterministische Date & Cost Engine)

Datum: 30.08.2026 · Fortschritt: **9 / 18 = 50,0 %**

STEP 9 setzt die (ursprünglich als „Schritt 9 – Date & Cost Engine" geplante)
deterministische Berechnungsschicht um. Sie ist strikt **getrennt** vom
extrahierten/source-of-truth `Contract`-Modell (`app/models/contract.py`),
das unverändert bleibt.

## 1. Architektur-Überblick

```
EXTRACTED                          CALCULATED (STEP 9)
app/models/contract.py     ──►    app/contracts/calculation/
  Contract (source of truth)        models.py    (Resultat-Modelle & Statusen)
  (unverändert)                     calendar_.py (kalenderbewusste Arithmetik)
                                    money.py     (Decimal-Grenze, kein Binär-Float)
                                    dates.py     (Date Engine)
                                    costs.py     (Cost Engine)
                                    engine.py    (calculate_contract)
```

Einstiegspunkt (pure Funktion, kein DB/HTTP/AI, kein verstecktes Datum):

```python
from app.contracts.calculation import calculate_contract
result = calculate_contract(contract, as_of_date=date(...))
# -> ContractCalculationResult(dates=..., costs=..., overall_review_required=..., review_reasons=[...])
```

Alle Zeitbezüge laufen ausschließlich über das explizite `as_of_date`.

## 2. Grundprinzipien

- **Nie fabrizieren:** bei fehlender/kollidierender Eingabe → `NOT_CALCULABLE`
  / `REVIEW_REQUIRED` / `CONFLICT`.
- **Feldautonomie:** ein fehlgeschlagenes Feld invalidisiert keine anderen.
- **Erklärbarkeit:** jedes Feld trägt `status`, `explanation`, `inputs`
  (stabile Feldreferenzen) und ggf. `review_required`.
- **Nur deterministisch:** Frei formulierte Bedingungen werden nicht per
  Heuristik als rechtliche Sicherheit interpretiert.

### `CalculationStatus`-Enum (str-Enum, passend zum bestehenden Stil)
| Wert | Bedeutung |
|------|-----------|
| `calculated` | deterministisch aus Eingaben berechnet |
| `explicit` | direkt aus dem Vertrag übernommen |
| `not_calculable` | Eingaben fehlen / ereignisbasiert |
| `review_required` | mehrdeutig, aber prüfbar |
| `conflict` | widersprüchliche Eingaben |

## 3. Berechnete Datumsfelder (`CalculatedDateField`)

Nur bei ausreichend deterministischer Information; sonst `NOT_CALCULABLE` /
`CONFLICT` / `REVIEW_REQUIRED`.

| Feld | Quelle/Regel |
|------|--------------|
| `calculated_end_date` | A) explizites `end_date` (EXPLICIT); B) `start_date + duration` kalenderbewusst (CALCULATED); C) ereignisbasiert → NOT_CALCULABLE; D) explizit vs. abgeleitet material abweichend → CONFLICT (explizit bleibt Basis, `review_required`) |
| `latest_cancellation_date` | Grenze minus Frist (CALCULATED) – NUR bei klarer Relation „zum Vertragsende"; sonst REVIEW_REQUIRED/NOT_CALCULABLE |
| `next_renewal_date` | `auto_renewal=True` + `renewal_period` + bekannter Grenze (RENEWAL_SHIFT); sonst NOT_CALCULABLE |
| `days_until_end` / `days_until_latest_cancellation` | Integer-Tage; negativ = bereits vergangen, wird **nicht** auf 0 geklemmt |
| `current_contract_status` | ACTIVE (as_of < Ende) / EXPIRED (as_of ≥ Ende) / UNKNOWN; TERMINATED nur bei expliziter Markierung |

`renewal_boundaries`: begrenzt – nur die **aktuell relevante Periode** (bzw.
initiale Laufzeit, wenn noch keine Verlängerung begann) plus die **nächste**
Periode (Konvention in §9.B). Keine unbegrenzte Historien-Erzeugung.

## 4. Datums-Arithmetik-Policy (`calendar_.py`)

- **Monate:** additive/subtraktive Monatsverschiebung mit dokumentierter
  End-of-Monat-Regel (Tag wird auf letztes gültiges Datum des Zielmonats
  geklemmt): `31.01.2024 + 1 Monat = 29.02.2024` (Schaltjahr),
  `31.01.2023 + 1 Monat = 28.02.2023`, `31.01.2024 + 2 Monate = 31.03.2024`.
- **Jahre:** = 12 Monate (Schaltjahre über Tagesgrenzen automatisch korrekt).
- **Wochen/Tage:** exakte Kalendertage über `timedelta`.
- **Kein** „1 Monat = 30 Tage", kein „1 Jahr = 365 Tage".
- Reihenfolge (deterministisch): Monate zuerst, dann Tage/Wochen.

## 5. Automatische Verlängerung

Nur berechnet bei **allen** drei Voraussetzungen:
1. `termination.automatic_renewal is True`,
2. `renewal_period` (Duration) extrahiert,
3. bekannte Grenze (Ende bzw. start+duration).

Fehlt `renewal_period` → `NOT_CALCULABLE` mit `review_required=True`.
`next_renewal_date = Grenze + renewal_period` (kalenderbewusst, EOM-klemmend).

## 6. Kosten-Normalisierung & Decimal-Policy (`money.py`, `costs.py`)

- **Ein/Ausgabe exakt über `Decimal`**, keine Binär-Float-Arithmetik.
- `float` wird an der Berechnungsgrenze **stringbasiert** konvertiert
  (`Decimal(str(x))`); der bestehende `Money.amount: Optional[float]` bleibt
  unverändert (Rückwärtskompatibilität des Extraktionsmodells).
- `0.1 + 0.2 == 0.3` (verifiziert).
- **Normalisierung nur aus explizit wiederkehrenden Eingaben:** monthly→×12,
  quarterly→×4, semiannual→×2, annual→×1 (via `scaling_factor`).
- **NICHT annualisiert:** once, hourly, unknown, other, conditional.
- `normalized_recurring.annual`: aus EINER wiederkehrenden Quelle; bei
  zugleich annual+monthly → Übereinstimmung (exakt oder innerhalb dokumentierter
  Toleranz ≤ 0,5 %) = `CALCULATED` + Korroboration; sonst `CONFLICT`
  (`recurring_cost_conflict=True`), niemals Doppelzählung.
- `total_contract_value` wird **nicht automatisch** zu wiederkehrenden Kosten
  addiert (nur als Wert notiert).
- Stundensatz / Reise / Material / Ersatzteile / bedingte Zusatzkosten werden
  als getrennte Kategorien geführt, **nie blind summed** als jährlicher Total.
- **Mehrwährung:** keine Aggregation, kein FX → `currency_conflict=True`,
  betroffene Kategorien `NOT_CALCULABLE`.
- **Steuerbasis:** `tax_basis` = `UNKNOWN`; wird NUR gesetzt, wenn der Vertrag
  es explizit hergibt (future-safe NET/GROSS). **Keine 19 %-MwSt-Annahme.**
- Rundung (Währungsrundung, `ROUND_HALF_UP`) nur an echten Ausgabegrenzen;
  keine unnötigen Zwischenrundungen.

## 7. Gegenüber übergeordneten Regeln (Deckung)

| Vorgabe | Umsetzung |
|---------|-----------|
| Getrennt vom Source-of-Truth-Modell | neues Paket `contracts/calculation/`; `app/models/*` unverändert |
| Kein STEP 10, kein Qwen, kein OCR/Docling-Rerun, kein STEP-8B-Benchmark-Rerun | eingehalten |
| `(contract, as_of_date) -> result`, keine DB/HTTP/AI/verstecktes datetime | `calculate_contract`; Test prüft Quelle auf `datetime.now`/`date.today` |
| Kalenderbewusste Datumslogik | dezidierte `calendar_`-Arithmetik + Monats-End/Leap-Tests |
| Geld ohne Binär-Float | Decimal-Grenze (stringbasiert) |
| Conflicts → CONFLICT/REVIEW_REQUIRED, nie Doppelzählung/ghost-werte | Testabdeckung |
| Negative Tage nicht auf 0 klemmen | `DifferenceResult` erlaubt negative Werte |

## 8. Grenzen & bewusst NICHT unterstützt (STEP-9-Scope)

- **`EXPIRING_SOON`** (Warnstufe) gehört zu **Schritt 11**, hier nicht enthalten.
- **Kündigungsfrist** nur bei positiver strukturierter Relation „zum Vertragsende";
  fehlende/andere/freie Relation → KEINE definitive Frist (NOT_CALCULABLE /
  REVIEW_REQUIRED).
- **Steuer/Netto/Brutto/MwSt** werden nicht abgeleitet.
- **FX / Mehrwährung** werden nicht gerechnet.
- **Keine Persistenz** der Ergebnisse (folgt Schritt 10) und **keine API-Anbindung**.
- Kein separates strukturiertes Terminierungs-Evidence-Feld im Schema: TERMINATED
  wird konservativ NUR aus `Contract.status == TERMINATED` gemeldet (Detail in §12).

## 9. STEP-9-Korrektheits-Härtung (nach finaler Review)

Drei Korrektheitsbereiche wurden nach der initialen STEP-9-Umsetzung gehärtet.
Die Gesamtarchitektur blieb unverändert; nur `dates.py`, die Paket-Exporte und
`tests/test_calculation_engine.py` wurden angepasst.

### 9.A Kündigungs-Relation – KEINE Default-Annahme
- Vorher: `group_cancellation_relation()` fiel bei fehlender Relation auf
  „to_contract_end" zurück, sofern keine konkurrierenden Keywords (Quartal/
  Halbjahr) erkannt wurden → zu permissiv.
- Nachher: **streng**. Nur ein explizit gesetzter `cancellation_to_contract_end`
  mit einem to-contract-end-Wert zählt als **positive strukturierte Evidenz**
  (berechnet). Ergebnis-Klassifikation:
  - explizit „zum Vertragsende" → `CALCULATED` (erlaubt)
  - explizit andere Relation (`false/no/…`) → `NOT_CALCULABLE`
  - fehlende Relation → `NOT_CALCULABLE` (keine definitive Frist)
  - freie Formulierung / unbekannter Marker-Wert → `REVIEW_REQUIRED`
- Keyword-Absenz ist KEIN Beweis; STEP 9 erweitert sich nicht um juristische
  Sprach-Interpretation.

### 9.B Wiederholte automatische Verlängerungen (as_of-abhängig)
- Vorher: `calculate_renewal_boundaries()` konstruierte nur initiale Periode +
  eine Verlängerung.
- Nachher: `calculate_renewal_info()` ermittelt die **aktuell relevante Periode**
  relativ zu `as_of_date` (bounded-, arithmetische Suche, `MAX_SCAN_PERIODS=1200`
  als Schutz gegen malformed Endlosschleifen).

**BOUNDARY-KONVENTION (exakt, durchgängig):**
Eine Vertragsgrenze `B` beendet eine Periode „inklusive":
- `as_of_date == B` gehört zur **ENDENDEN** Periode (nächste beginnt am Tag B+1).
- aktuelle/relevante Periode = jene `p` mit `start_p < as_of <= end_p`.
- `next_renewal_date` = schliessende Grenze der aktuellen Periode (kann auf
  einer Grenze == `as_of` liegen).
- Kündigungsgrenze = schliessende Grenze der (ggf. bei abgelaufener Frist
  vorgeschobenen) aktuellen Periode.
- `days_until_x` = Countdown bis zur Grenze (Grenze = erreicht, negativ = vergangen).

`renewal_boundaries` enthält NUR begrenzte, nutzbare Info: die aktuell relevante
Periode + die nächste (keine unendliche Historien-Erzeugung).
Die Kündigungsgrenze nutzt die **aktuell relevante Verlängerungsgrenze**, nicht
die erste historische: ist die Frist der aktuellen Periode bereits abgelaufen
(> as_of), wird auf die nächste Verlängerungsgrenze vorgeschoben (bounded).

### 9.C Konflikt-Propagation – keine falsche Sicherheit
- Vorher: `calculate_contract_dates()` nahm bei CONFLICT den expliziten Wert als
  Basis weiter; abgeleitete Kündigungs-/Verlängerungsergebnisse hätten als
  unqualifizierte `CALCULATED` erscheinen können.
- Nachher: `boundary_conflicted` (Endstatus ∈ {CONFLICT, REVIEW_REQUIRED}) wird in
  `calculate_renewal_info()` und `calculate_latest_cancellation_date()` getragen.
  Abhängige Ergebnisse:
  - behalten ihren Wert (explizites Ende wird NICHT verworfen),
  - tragen aber Status `REVIEW_REQUIRED` + `review_required=True`
    (kein unqualifiziertes `CALCULATED`),
  - `days_until_end`/`days_until_latest_cancellation` und die Boundary-Einträge
    tragen `review_required` mit.
- Unabhängige, gültige Felder (z. B. Kosten) bleiben davon unberührt.

## 10. Tests

- Neu/erweitert: `backend/tests/test_calculation_engine.py` – **72 Tests**:
  - Kalender: EOM Januar/Februar/Schaltjahr, Subtraktion.
  - Datum: explizit, abgeleitet (Monate/Jahre/Leap), ereignisbasiert,
    explizit-vs-abgeleitet Konflikt/Korroboration.
  - Status/Tage: ACTIVE/EXPIRED/UNKNOWN/TERMINATED, as_of exakt auf Grenze,
    negative Tage nicht geklemmt.
  - Kündigungs-Relation (streng): fehlende/andere/freie/Quartal-Relation →
    keine Frist; positive Markierung → berechnet.
  - Wiederholte Verlängerungen: vor initialem Ende, erste Verlängerung, viele
    historische jährliche Verlängerungen, monatliche über Jahre (EOM-Ketten),
    as_of genau auf Grenze, Schaltjahr/EOM, fehlende Verlängerungsfrist,
    nicht-positive Verlängerungsfrist (0 – kein Loop-Risiko), Kündigung nutzt
    relevante Verlängerungsgrenze; semantisches Invariant
    `start < as_of <= end` + `next_renewal == closing boundary`.
  - Konflikt-Propagation: Konflikt bleibt sichtbar; Kündigung/Verlängerung
    NIE unqualifiziert CALCULATED; Boundary-Einträge = review; unabhängige
    Kosten bleiben valide.
  - Safety-Invarianten (D): TERMINATED nie aus abgelaufenem Ende; annual+monthly
    nie addiert (korroboriert); total_contract_value nie addiert; Währungen nie
    aggregiert; keine Default-MwSt; Feld-Autonomie.
  - Kosten: monthly→annual, annual, annual+monthly korroborierend/konflikt,
    0.1+0.2==0.3, once nicht annualisiert, Stundensatz nicht blind-summiert,
    Währungsmismatch, Steuerbasis unbekannt, zero vs None, scaling_factor,
    Währungsrundung.
  - Engine: keine versteckte Zeit, Review-Reasons.
- **Volle Backend-Suite: 291 passed** (219 Bestand + 72 STEP-9, 0 Regressionen).

## 11. Geänderte/neue Dateien

- `backend/app/contracts/calculation/__init__.py` (Paket-Exporte:
  `calculate_renewal_info` ersetzt `calculate_renewal_boundaries`,
  `group_cancellation_relation` ergänzt)
- `backend/app/contracts/calculation/models.py` (Resultat-Modelle & Statusen)
- `backend/app/contracts/calculation/calendar_.py` (Datum-Arithmetik)
- `backend/app/contracts/calculation/money.py` (Decimal-Grenze)
- `backend/app/contracts/calculation/dates.py` (Date Engine – gehärtet:
  strenge Kündigungs-Relation, as_of-abhängige Verlängerung, Konflikt-Propagation)
- `backend/app/contracts/calculation/costs.py` (Cost Engine)
- `backend/app/contracts/calculation/engine.py` (`calculate_contract`)
- `backend/tests/test_calculation_engine.py` (72 Tests)
- `docs/PROJECT_PROGRESS.md` (Status, Fortschritt 9/18 = 50,0 %)

Unverändert: `app/models/*` (source of truth), `app/documents/*`,
`app/ai/*`-Quell-Navigation, STEP-8B-Artefakte (`data/benchmark_v2/...`).

## 12. TERMINATED-Verhalten & Terminierungs-Evidence

- Schema-Prüfung: `Contract` besitzt `status: ContractStatus`, `Termination`
  besitzt `extraordinary_termination: Optional[str]` (Freitext) und die
  generischen `ReviewInfo.review_reasons` (ReviewFlag). Ein **zuverlässiges,
  strukturiertes Kündigungs-Evidence-Feld (z. B. „termination_date" oder
  „termination_reason_enum") existiert NICHT**.
- Daher bleibt die konservative Regel: TERMINATED wird NUR aus
  `Contract.status == TERMINATED` (explizite extrahierte/manuelle Markierung)
  gemeldet. Ein bloß abgelaufenes deterministisches Ende → **EXPIRED**, nie
  TERMINATED.
- Limitierung für ein späteres Schema-Step (kein STEP 9-Invent): strukturiertes
  Terminierungs-Evidence fehlt im Extraktionsmodell.
