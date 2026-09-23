# Medflux — STEP 11 Checkpoint (Production-Grade Warning & Action-Readiness System)

Datum: 31.08.2026 · Fortschritt: **11 / 18 = 61,1 %**

STEP 11 ist das durable Backend-Fachwerk für Krankenhaus-Vertragsmanagement,
STEP-12-Dashboard, STEP-13-Filter/Suche und STEP-14-Vertragsdetail – ohne diese
Schritte vorzeitig zu implementieren. Drei sauber getrennte Schichten:
**A)** deterministische Warn-Bewertung, **B)** durable Warn-Zustand/Historie,
**C)** dokumentierter Future-Action/Ownership-Erweiterungspunkt.

## 1. Architektur-Überblick

```
STEP 9              STEP 11 (reine Funktion)        STEP 11 (Persistenz)
ContractCalculationResult  ->  evaluate_contract_   ->  run_warning_evaluation()
 (deterministisch)           warnings(contract,             warning_evaluation_run   (immutabler Lauf)
                              calculation, policy)          contract_warning         (akkumulierte Issue-Zeile)
      │                      ------------------            contract.status/risk_level (Current-Projektion)
      │                       KEINE DB/Netz/KI/Zeitstempel  │
      └─ as_of_date kommt NUR aus dem Berechnungslauf ─────┘
```

- Pure Engine: `backend/app/contracts/warnings/{models,policy,engine}.py`
- Persistenz: neue ORM-Modelle `warning_evaluation_run` + `contract_warning`,
  Services in `backend/app/database/services.py` (einziger Schreib-Pfad).

## 2. Reine Engine & Prinzipien

Haupteinstieg (pure):

```python
from app.contracts.warnings import evaluate_contract_warnings, WarningPolicy
result = evaluate_contract_warnings(contract, calculation, policy=WarningPolicy.default())
# -> ContractWarningResult(as_of_date, policy_version, warnings=[...])  # sortiert
```

- PURE, deterministisch: gleiche Eingaben + gleiche Policy => identisches Ergebnis
  (per Test `model_dump() == model_dump()` verifiziert).
- **Keine KI** entscheidet Frist/Tage/Schweregrad/Zustand/Ablauf/Dringlichkeit.
- `as_of_date` kommt ausschließlich aus `ContractCalculationResult` (nie verstecktes `date.today()`).
- Die Engine **rechnet keine Termine neu**, sie konsumiert die STEP-9-Felder
  (`days_until_latest_cancellation`, `latest_cancellation_date`, `days_until_end`,
  `calculated_end_date`, `current_contract_status`, `next_renewal_date`,
  `costs.normalized_recurring`, `costs.currency_conflict`, `overall_review_required`).

## 3. Versionierte Warn-Policy (`policy.py`)

Keine verstreuten 180/90/...-Konstanten. Zentrale unveränderliche `WarningPolicy`:

```python
WarningPolicy(version="step11-default-1", thresholds=(180, 90, 60, 30, 14, 7))
```

- Konfigurierbar für spätere Krankenhaus-Vorlaufzeiten ohne Engine-Umbau.
- `match_threshold(days)` liefert den **kleinsten passenden Bucket**.
- Policy-Version wird bei jeder Evaluation aufgezeichnet (→ historische Warnungen
  reproduzierbar).
- Kalendertage; vertragliche Fristen werden NICHT zu Arbeitstagen umgerechnet.

### Exakte Schwellen-Semantik (Kalendertage)
| Resttage | Ergebnis |
|---|---|
| > 180 | keine Schwellen-Warnung |
| 91..180 | Bucket 180 |
| 61..90 | Bucket 90 |
| 31..60 | Bucket 60 |
| 15..30 | Bucket 30 |
| 8..14 | Bucket 14 |
| 1..7 | Bucket 7 |
| 0 | „heute fällig" (Heute) |
| < 0 | „verstrichen" (Passed) |

## 4. Schweregrad-Modell (§6)

Warn-Severity (INFO/LOW/MEDIUM/HIGH/CRITICAL) ist ein eigenes Warn-Enum; die
DIMENSION des bestehenden `RiskLevel`-Enums wird NICHT verändert.

| Resttage | Severity |
|---|---|
| 91..180 | LOW |
| 61..90 / 31..60 | MEDIUM |
| 15..30 / 8..14 | HIGH |
| 1..7 / 0 | CRITICAL |

Spezialfälle: Kündigungsfrist verstrichen → CRITICAL; Vertrag ausgelaufen → HIGH;
kritischer Datumskonflikt → HIGH; fehlende Kosten → MEDIUM; Kosten-/Währungskonflikt
→ HIGH.

**Projektion auf `RiskLevel`** (deterministisch, keine Konkurrenz-Systeme):
`severity_to_risk` → CRITICAL/HIGH→high, MEDIUM→medium, LOW/INFO→low, (ohne Warnung)→unknown.

## 5. Warn-Typen

`CONTRACT_END_APPROACHING`, `CONTRACT_EXPIRED`, `CANCELLATION_DEADLINE_APPROACHING`,
`CANCELLATION_DEADLINE_TODAY`, `CANCELLATION_DEADLINE_PASSED`,
`AUTOMATIC_RENEWAL_ATTENTION`, `UNCLEAR_CONTRACT_DATA`, `CALCULATION_CONFLICT`,
`MANUAL_REVIEW_REQUIRED`, `MISSING_COST_DATA`, `COST_CONFLICT`, `CURRENCY_CONFLICT`.

Jede Warnung ist maschinenlesbar strukturiert: `warning_type`, `severity`,
`target_kind`, `target_date`, `days_remaining`, `matched_threshold_days`,
`as_of_date`, `policy_version`, `title_de`/`message_de`/`action_hint_de`,
`requires_action`, `requires_review`, `calculation_field_refs`, `source_field_refs`,
`logical_fingerprint`. Deutscher Freitext ist NIE Geschäftslogik-Quelle.

## 6. Kündigungsfrist = primärer Handlungstermin (§7)

- `days > 0` innerhalb Schwelle → `CANCELLATION_DEADLINE_APPROACHING`
- `days == 0` → `CANCELLATION_DEADLINE_TODAY`
- `days < 0` → `CANCELLATION_DEADLINE_PASSED`
- Bei NOT_CALCULABLE / REVIEW_REQUIRED / CONFLICT wird **kein** Termin erfunden,
  sondern eine Review-/Konflikt-Warnung erzeugt (Ziel-Feld identifiziert).
- Ein verstrichener Kündigungstermin bedeutet NICHT automatisch gekündigt/
  terminiert/auto-verlängert (nur mit autoritativen akzeptierten Daten).

## 7. Vertrags-Ende (§8) & Auto-Verlängerung (§9)

- Positiv innerhalb Schwelle → `CONTRACT_END_APPROACHING`.
- **0 kombiniert mit autoritativem STEP-9-EXPIRED** wird als `CONTRACT_EXPIRED`
  behandelt (STEP 9: `as_of == Ende` → EXPIRED).
- `TERMINATED` wird nie durch EXPIRING_SOON/EXPIRED/Warnung überschrieben
  (Invariante; Precedence in §18).
- `AUTOMATIC_RENEWAL_ATTENTION` nur bei explizit gesetzter automatischer
  Verlängerung UND kombiniert mit handlungsrelevanter Frist/Grenze; wenn
  ausgelöst, erklärt es die zusätzliche Verlängerungskonsequenz (§19). Ist die
  Verlängerung explizit, die Grenze aber unklar → review-orientierte Warnung.

## 8. Unklar / Konflikt / Review (§10) – konsolidiert

- Konkrete Feld-Probleme (Enddatum-Konflikt, Kündigung/Renewal REVIEW_REQUIRED)
  erzeugen gezielte Warnungen mit `target_kind` + Feld-Referenzen.
- **Deduplizierung:** Ein allgemeiner „overall_review"-Konsolidator wird nur
  erzeugt, wenn noch keine konkrete Review-/Konflikt-Warnung existiert – so
  wird ein zugrundeliegender Konflikt nicht 5-fach wiederholt (§19 / Alert-Fatigue).

## 9. Kosten (§11)

- `MISSING_COST_DATA` nur, wenn keine verwertbare wiederkehrende/jährliche
  Kostenangabe existiert (unbekannt ≠ 0).
- `COST_CONFLICT` bei widersprüchlichen wiederkehrenden Kosten; `CURRENCY_CONFLICT`
  bei mehreren Währungen (kein FX).
- `tax_basis == UNKNOWN` allein erzeugt KEINE Warnung (keine 19 %-/Netto-Annahme).
- STEP-9-Money/Decimal-Regeln unverändert.

## 10. Deduplizierung & Lebenszyklus (§12–§14, §19)

- **Logische Identität** = `logical_fingerprint` (SHA-256) über stabile Komponenten
  (contract, warning_type, target_kind, target_date/idfizierte Feld-Menge).
  Enthält NIEMALS UI-Text, Severity oder Bucket → identisches logisches Problem
  bleibt bei verschobener Dringlichkeit (30→14 Tage) stabil und eskaliert in
  der Severity, statt zu duplizieren.
- **Evaluations-Zustand vs. menschlicher Lebenszyklus getrennt:** `active`
  (objektiv aktiv in letzter Evaluation) und `action_state`
  (open/acknowledged/resolved/dismissed) sind getrennte Konzepte; eine weiterhin
  aktive Warnung kann zugleich acknowledged sein.
- **Clearing ohne Verlust:** Wird eine Warnung nicht mehr aktiv, bleibt die
  Zeile erhalten (`active=False`), Historie + `action_state` bleiben – nichts
  verschwindet, und eine zuvor bestätigte (acknowledged) Warnung, die wieder
  schwerer wird, bleibt detektierbar.
- **Re-Evaluation** löscht nie menschliche Lebenszyklus-Metadaten.
- **Deterministische Sortierung:** höchste Severity zuerst, dann nächstes
  `target_date`, dann stabiler Typ-Tie-Breaker.

## 11. Persistenz-Modell (§15) – erweitert STEP 10 (immutable Runs + Zeiger)

`warning_evaluation_run` (reproduzierbarer Lauf):
- `id` (UUIDv7, `uuidv7()`), `organization_id`, `contract_id` (CASCADE),
  `calculation_run_id` (RESTRICT), `as_of_date` (DATE), `policy_version`,
  `status` (computed|failed), `created_at` (TIMESTAMPTZ), kleines `result_snapshot`
  (JSONB, §7-Policy: klein, ganzheitlich gelesen).

`contract_warning` (akkumulierter Issue-Zustand):
- `id`, `organization_id`, `contract_id` (CASCADE), `last_evaluation_run_id`
  (SET NULL), `warning_type`/`severity`/`target_kind` (CK-beschränkt),
  `target_date` (DATE), `days_remaining`, `threshold`, `logical_fingerprint`,
  `active`, `requires_action`, `requires_review`, `action_state` (open/…),
  `action_updated_at`, `first_seen_at`/`last_seen_at`, strukturierte
  `calculation_field_refs`/`source_field_refs` (kleines JSONB), `references`.
- UNIQUE(`contract_id`, `logical_fingerprint`) → eine Zeile je logischem Problem.
- Relationale Spalten für STEP-12/13-Filter (contract_id, organization_id,
  active, warning_type, severity, target_date, requires_action).
- **Keine** Duplikate von Vertragstext/OCR; nur stabile Provenienz-Referenzen
  (Datenminimierung §21).

`run_warning_evaluation(...)` (Service):
1. Legt – idempotent je `calculation_run_id` – einen Lauf an (Retry erzeugt
   kein Duplikat-Run).
2. Gleicht `contract_warning`-Zeilen ab: aktiv/neu/inaktiv (Historie bleibt).
3. Projektion `contract.status`/`risk_level` deterministisch (§18).

## 12. Current-Projektion (§18) – deterministische Präzedenz

1. explizit TERMINATED bleibt TERMINATED
2. sonst autoritatives STEP-9-EXPIRED → EXPIRED
3. sonst aktiver Vertrag mit relevanter anstehender Aktion (End-/Kündigungs-
   Frist) → EXPIRING_SOON
4. sonst ACTIVE/UNKNOWN nach STEP-9-Zustand

`contract.risk_level` kommt aus der höchsten (aktiven) Warn-Severity (→ RiskLevel),
nie aus KI. Historische Wahrheit bleibt an die Läufe (Runs) gebunden; eine
`contract_warning`-Zeile ist nur die abfragbare aktuelle Projektion.

Failed-/Unaccepted-Runs können keine Warn-Projection treiben: Nur ein explizit
akzeptierter Berechnungslauf wird der Wach-Engine übergeben (Service erhält
konkrete `calculation_run_id`; kein generischer „neuester Lauf" ohne Accept).

## 13. Organisation / Ownership & Datenminimierung (§16, §21)

- Jede Warn-Zeile trägt `organization_id` (OrgOwnedMixin) + Index; lokale/on-prem
  Architektur, KEINE Multi-Tenant-SaaS-Fake. Isolation auf Persistenz-Ebene getestet.
- Warnrecords minimal: Referenzen statt Vertragstext; keine Secrets/Credentials; keine
  externen APIs; keine Notification-Delivery ohne Autorisierungs-/Empfänger-Regeln.

## 14. Future Owner / Escalation-Integration (§17)

Dokumentierter Erweiterungspunkt: `contract_warning.action_state` +
`references`-JSONB sind die heutige Basis. Spätere eigene Schritte (STEP 16)
führen owner/department/escalation/notification über **saubere FK-Migrationen**
ein – ohne Warn-Identität (`logical_fingerprint`) oder Evaluations-Semantik zu
ändern. **Keine** Fake-User-Entitäten, **kein** Notification-Delivery in STEP 11.

## 15. Alembic-Revision & PG-18-Migration

Neue Revision `20260831_81aa19e5d946` („step11 warning evaluation and contract
warnings"), `down_revision=4d930fb1d75e`. Addiert `warning_evaluation_run` +
`contract_warning` (UUID(v7) PKs, FK/ondelete, CK-Constraints, UNIQUE-, Filter-Indexe).
Die initiale `20260831_4d930fb1d75e_initial_schema.py` wurde **NICHT** verändert.

**Migration auf nativer PostgreSQL 18.6 verifiziert:** upgrade head →
downgrade base → re-upgrade head (jeweils EXIT 0); beide Tabellen vorhanden,
leer nach frischem Re-Upgrade.

## 16. Fokussierte STEP-11-Tests

**Pure Engine – `tests/test_warning_engine.py` (50 Tests):**
- Grenzen für Kündigungsfrist UND Vertragsende: 181/180/91/90/61/60/31/30/15/14/8/7/1/0/−1.
- Nur dringlichster Bucket; deterministische Sortierung; Kündigungs-Priorität vor Ende;
  Annäherung/heute/verstrichen; Ende-Annäherung; ausgelaufen; TERMINATED nie überschrieben;
  Auto-Renewal+handlungsfähig/unklar/false; NOT_CALCULABLE/REVIEW_REQUIRED/CONFLICT;
  Review-Deduplizierung; fehlende Kosten/Kostenkonflikt/Währungskonflikt; tax_basis UNKNOWN
  allein nicht schwer; keine erfundenen Werte; gleiche Eingabe/Policy → ident;
  explizites as_of (kein today()); Policy-Version erfasst; Fingerprint stabil;
  Severity-Eskalation ohne Duplikat.

**Persistenz/Integration – `tests/test_warning_persistence.py` (9 Tests):**
- UUIDv7-PK auf neuen Tabellen; Roundtrip + Current-Projektion (EXPIRING_SOON);
  Dedup logisches Problem über Läufe; Severity-Eskalation gleiche Zeile;
  Cleared ohne History-Verlust + action_state erhalten; Organisations-Isolation;
  Vertrag-Delete-Cascade; TERMINATED-Projektion nie überschrieben; EXPIRED-Projektion.

## 17. Volle Backend-Regression (einmal)

**375 passed, 0 Failures** (Baseline 316 + 50 pure + 9 Persistenz), 5 benigne
PyMuPDF-SWIG-Warnungen. Keine Regressionen.

## 18. Bekannte Grenzen / bewusst NICHT in STEP 11

- KEIN Dashboard/UI, KEIN Email/Slack/externe Notification, KEIN volles RBAC/Auth,
  KEINE Fake-User, KEINE Notification-Delivery (bis Autorisierung/Recipient-Regeln).
- `action_state`-Übergänge (open→acknowledged→resolved/dismissed) sind persistiert,
  aber benutzergetriebene Transitionen folgen in STEP 12/16.
- Kein volles Event-Sourcing (Ziel: ausreichende Historie für Audit/Reproduzierbarkeit).
- Gleiche Empfang der Kosten-Orchestratoren-/Import-Verdrahtung und API-Bindung
  folgt in späteren Schritten.

## Nächster Schritt

- **STEP 12 – Dashboard**. **STOP – kein STEP-12-Start in dieser Sitzung.**
