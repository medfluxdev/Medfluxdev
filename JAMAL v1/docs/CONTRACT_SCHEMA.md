# Medflux – Vertragsdatenmodell (Contract Schema)

Dieses Dokument beschreibt das strukturierte Datenmodell, mit dem Medflux
Vertragsdaten aus Wartungs- und Serviceverträgen erfasst. Das Modell dient als
Grundlage für die lokale KI-Extraktion (Schritt 7), Validierung, Speicherung,
Berechnungen (Schritt 9) und die spätere Dashboard-Anzeige.

## Grundprinzipien

1. **EXTRACTED vs. CALCULATED**
   - **EXTRACTED:** Werte, die direkt aus dem Vertragsdokument stammen (durch
     lokale KI oder manuell). Diese werden im Modell gespeichert.
   - **CALCULATED:** Werte, die später ausschließlich durch **Code** berechnet
     werden (Date & Cost Engine, Schritt 9) – z. B. `latest_cancellation_date`,
     verbleibende Tage, Jahres-/Monatsumrechnung, aggregierte Kosten, Warnstufen.
   - **Berechnete Felder sind NICHT Teil des Extrakts.** Sie werden in späteren
     Schritten ergänzt. Damit bleibt das Datenmodell frei von Fachlogik.

2. **Keine Platzhalterstrings.** Unbekannte Werte werden als `null` (Python:
   `None`) dargestellt – niemals als `"unknown"`, `"nicht gefunden"` o. Ä.
   Bei Bedarf wird zusätzlich das Prüf-Flag `requires_review` gesetzt.

3. **Starke Typisierung.** Fachwerte werden durch dedizierte Modelle abgebildet
   (z. B. `Money`, `Duration`, `TimeValue`, `FlexibleDate`), nicht durch rohe
   Strings oder Zahlen.

4. **Nachvollziehbarkeit.** Wichtige Felder können über `SourceEvidence`
   (Seite, Originaltext, Confidence, Methode, Prüfbedarf) belegt werden.

5. **Enums** nur dort, wo eine begrenzte, bekannte Wertmenge existiert.

## Datei-Struktur

```text
backend/app/models/
├─ enums.py      # Enum-Typen
├─ evidence.py   # SourceEvidence
├─ values.py     # Money, Duration, TimeValue, FlexibleDate
└─ contract.py   # Contract + Abschnittsmodelle
```

## Wiederverwendbare Typen (`values.py`)

### Money – strukturierte Geldangabe

```json
{
  "amount": 24500.00,
  "currency": "EUR",
  "period": "annual"
}
```

| Feld      | Typ        | Nullbar | Bedeutung                              |
|-----------|------------|---------|----------------------------------------|
| `amount`  | float      | ja      | Betrag, `>= 0`; `null` = unbekannt     |
| `currency`| string(3)  | ja      | Währungscode (wird großgeschrieben)    |
| `period`  | string     | ja      | Bezug (annual/monthly/…), informativ   |

Validierung: `amount` darf nicht negativ und nicht NaN sein.

### Duration – Dauer/Frist

```json
{ "value": 6, "unit": "months" }
```

| Feld   | Typ   | Nullbar | Bedeutung                    |
|--------|-------|---------|------------------------------|
| `value`| int   | ja      | Anzahl der Einheiten, `>= 0` |
| `unit` | TimeUnit | ja  | `days|weeks|months|years|hours` |

Genutzt für Vertragsdauer, Mindestlaufzeit, Kündigungsfrist, Verlängerungsdauer.

### TimeValue – SLA-Zeitangabe

```json
{ "value": 4, "unit": "hours", "original_text": "Reaktionszeit 4 Stunden" }
```

| Feld          | Typ   | Nullbar | Bedeutung                          |
|---------------|-------|---------|------------------------------------|
| `value`       | float | ja      | numerischer Wert, `>= 0`          |
| `unit`        | TimeUnit | ja  | Zeiteinheit                        |
| `original_text`| string| ja    | Originaltext aus dem Vertrag       |

Genutzt für Reaktionszeit, Auflösungszeit, Servicezeiten, Notdienst.

### FlexibleDate – explizit / unbekannt / ereignisbasiert

```json
{ "date": "2025-01-01", "condition": null, "requires_review": false }
```

| Feld             | Typ   | Nullbar | Bedeutung                             |
|------------------|-------|---------|---------------------------------------|
| `date`           | date  | ja      | explizites Datum, sonst `null`        |
| `condition`      | string| ja      | Textbedingung, z. B. `"Übergabedatum"`|
| `requires_review`| bool  | nein    | manuelle Prüfung nötig?               |

Beispiele:
- **Explizit:** `{ "date": "2025-01-01" }`
- **Ereignisbasiert:** `{ "date": null, "condition": "Übergabedatum", "requires_review": true }`
- **Unbekannt:** `{ "date": null, "condition": null }`

## Quellen-Nachweis (`evidence.py`)

### SourceEvidence

```json
{
  "page": 3,
  "source_text": "Vertrags-Nr.: WM-2024-001",
  "confidence": 0.98,
  "extraction_method": "ai",
  "requires_review": false
}
```

| Feld              | Typ   | Nullbar | Bedeutung                             |
|-------------------|-------|---------|---------------------------------------|
| `page`            | int   | ja      | Seitennummer (1-basiert), `>= 1`      |
| `source_text`     | string| ja      | Originaltext aus dem Dokument         |
| `confidence`      | float | ja      | `0.0 .. 1.0`                          |
| `extraction_method`| Enum | nein    | `ai|manual|programmatic`              |
| `requires_review` | bool  | nein    | erfordert manuelle Prüfung?           |

Validierung: `confidence` muss in `[0,1]` liegen; `page` muss `>= 1` sein.
`confidence` darf `null` sein (kein Sicherheitswert), aber nicht außerhalb des
gültigen Bereichs.

## Vertragsabschnitte (`contract.py`)

### Contract (Top-Level)

Der Einstiegspunkt des gesamten Vertragsmodells.

| Feld        | Typ                   | Bedeutung                              |
|-------------|------------------------|----------------------------------------|
| `id`        | string (nullbar)      | interne ID                             |
| `status`    | ContractStatus        | `active|expiring_soon|expired|terminated|draft|unknown` |
| `identity`  | ContractIdentity      | Vertragsidentität                      |
| `equipment` | list[Equipment]       | mehrere Geräte/Anlagen                 |
| `dates`     | ContractDates         | Laufzeit                               |
| `termination`| Termination          | Kündigung                              |
| `costs`     | Costs                 | Kosten                                 |
| `payment`   | Payment               | Zahlung                                |
| `services`  | Services              | Leistungen                             |
| `sla`       | SLA                   | Service-Level                          |
| `review`    | ReviewInfo            | Prüfung/Risiko                         |
| `analysis`  | AnalysisMetadata      | KI-Analyse-Metadata                    |

### ContractIdentity
`contract_title`, `contract_number`, `contract_type` (ContractType:
`maintenance|service|lease|rental|other|unknown`), `supplier`, `contractor`,
`customer`, `contact_person`, `customer_number`, `department`, `location`,
`evidence`.

### Equipment (pro Gerät/Anlage)
`device_name`, `manufacturer`, `model`, `serial_number`, `system_name`,
`equipment_category`. Mehrere Geräte pro Vertrag über `equipment: [...]`.

### ContractDates
`start_date`, `end_date` (jeweils `FlexibleDate`), `duration`, `minimum_duration`
(jeweils `Duration`), `start_condition`, `end_condition`, `evidence`.

### Termination (nur extrahiert, keine Berechnung)
`cancellation_period` (Duration), `cancellation_condition`, `cancellation_to_contract_end`,
`automatic_renewal` (bool|null), `renewal_period` (Duration), `extraordinary_termination`,
`evidence`.

> **Hinweis:** `latest_cancellation_date` ist bewusst KEIN Feld dieses Modells.
> Es wird in Schritt 9 (Date & Cost Engine) programmatisch berechnet.

### Costs
`default_currency`, `total_contract_value`, `annual_cost`, `monthly_cost`,
`one_time_cost`, `maintenance_fee`, `hourly_rate`, `travel_cost`,
`material_cost`, `spare_parts_cost`, `additional_costs`, `discounts`
(jeweils `Money`), `price_adjustment_clause`, `price_indexation` (string),
`evidence`.

### Payment
`payment_terms`, `payment_deadline_days` (int `>= 0`), `billing_interval`
(BillingInterval: `monthly|quarterly|semi_annual|annual|once|other`),
`advance_payment` (Money), `payment_notes`, `evidence`.

### Services
`included_services` (list[str]), `excluded_services` (list[str]),
`maintenance`, `inspection`, `repair`, `calibration`, `software_updates`,
`remote_support`, `technical_support`, `spare_parts_included`,
`consumables_included`, `emergency_service` (bool|null), `evidence`.

### SLA
`response_time`, `resolution_time`, `service_hours`, `emergency_availability`
(jeweils `TimeValue`), `availability_24_7` (bool|null), `sla_notes`, `evidence`.

### ReviewInfo
`review_status` (ReviewStatus: `reviewed|needs_review|auto_accepted`),
`requires_manual_review` (bool), `review_reasons` (list[ReviewFlag]),
`risk_level` (RiskLevel: `low|medium|high|unknown`), `risk_score`
(float `0..1`, nullbar), `risk_notes`.

> `risk_level`/`risk_score` werden in Schritt 11 durch Code abgeleitet; hier
> werden nur Anhaltspunkte abgelegt.

### AnalysisMetadata
`model_name`, `analysis_timestamp`, `analysis_version`, `processing_duration`
(float `>= 0`), `extraction_status` (ExtractionStatus:
`pending|running|success|partial|failed`), `validation_status`
(ValidationStatus: `valid|invalid|unknown`).

## Nullbar / Unbekannt – Regeln

- Unbekannte Werte **immer** als `null`.
- Kein String wie `"unknown"`, `"n.a."`, `"nicht gefunden"`.
- `null` wird im JSON als `null` und in Python als `None` repräsentiert.
- Wo es semantisch sinnvoll ist, zusätzlich `requires_review = true` setzen,
  damit der Wert später von einem Menschen geprüft wird.

## Berechnete Felder (NICHT Teil des Extrakts)

Folgende Werte werden in Schritt 9 (Date & Cost Engine) bzw. Schritt 11
(Warnsystem) durch Code berechnet und sind im Schritt-3-Modell bewusst nicht
enthalten:

- `latest_cancellation_date` (spätester Kündigungstermin)
- verbleibende Tage bis zur Kündigungsfrist
- verbleibende Tage bis zum Vertragsende
- Umrechnung Jahreskosten ↔ Monatskosten
- aggregierte Gesamtkosten
- Warnstufen (180/90/60/30/14/7 Tage, abgelaufen)
- endgültige Risikobewertung (`risk_score`-Ableitung)

## Beispiel (vollständig)

```json
{
  "id": "C-001",
  "status": "active",
  "identity": {
    "contract_title": "Wartungsvertrag CT",
    "contract_number": "WM-2024-001",
    "contract_type": "maintenance",
    "supplier": "Siemens Healthineers",
    "customer": "Klinikum Mitte",
    "department": "Radiologie"
  },
  "equipment": [
    {
      "device_name": "CT-Scanner",
      "manufacturer": "Siemens",
      "model": "Somatom go.Top",
      "serial_number": "SN-12345",
      "system_name": "Radiologie-CT"
    }
  ],
  "dates": {
    "start_date": { "date": "2024-01-01" },
    "end_date": { "date": "2026-12-31" },
    "duration": { "value": 36, "unit": "months" }
  },
  "termination": {
    "cancellation_period": { "value": 6, "unit": "months" },
    "automatic_renewal": true,
    "renewal_period": { "value": 12, "unit": "months" }
  },
  "costs": {
    "default_currency": "EUR",
    "annual_cost": { "amount": 24500.0, "currency": "EUR", "period": "annual" },
    "monthly_cost": { "amount": 2000.0, "currency": "EUR", "period": "monthly" }
  },
  "payment": {
    "payment_terms": "30 Tage netto",
    "payment_deadline_days": 30,
    "billing_interval": "annual"
  },
  "services": {
    "included_services": ["Wartung", "Reparatur"],
    "maintenance": true,
    "repair": true
  },
  "sla": {
    "response_time": { "value": 4, "unit": "hours", "original_text": "Reaktionszeit 4 Stunden" },
    "availability_24_7": true
  },
  "review": {
    "review_status": "reviewed",
    "requires_manual_review": false
  },
  "analysis": {
    "model_name": "qwen3:8b-q4",
    "extraction_status": "success",
    "validation_status": "valid"
  }
}
```

## Beispiel (ereignisbasierter Beginn, ohne Berechnungen)

```json
{
  "dates": {
    "start_date": {
      "date": null,
      "condition": "Übergabedatum",
      "requires_review": true
    }
  },
  "termination": {
    "cancellation_period": { "value": 3, "unit": "months" }
  }
}
```
