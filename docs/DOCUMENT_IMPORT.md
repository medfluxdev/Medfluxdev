# Medflux – Dokumentimport (Document Import)

Dieses Dokument beschreibt den aktuellen produktiven Dokumentimport. Der
Endpunkt nimmt Dateien an, validiert und persistiert sie und führt anschließend
denselben synchronen Produktionspfad für Document Intelligence, lokale
KI-Analyse, deterministische Berechnungen und Persistenz der akzeptierten
Vertragswahrheit aus. Importstatus und Analysestatus sind getrennt zu lesen.

## Unterstützte Formate

| Format | Endung | Erwarteter MIME-Typ                                      |
|--------|--------|----------------------------------------------------------|
| PDF    | `.pdf` | `application/pdf`                                        |
| DOCX   | `.docx`| `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |

Andere Formate (DOC, XLSX, Bilder, ZIP, RAR usw.) werden abgelehnt. Es wird
sowohl die Dateiendung **als auch** – wo erkennbar – der Content-Type geprüft.
Beide müssen zueinander passen, sonst wird die Datei abgelehnt.

## API-Endpunkt

```
POST /api/documents/import
Content-Type: multipart/form-data
```

Ein oder mehrere Dateien über das Feld `files` übertragbar. Jede Datei wird
unabhängig verarbeitet; eine ungültige Datei blockiert nicht die anderen.

Beispiel-Antwort:

```json
{
  "total": 3,
  "successful": 2,
  "failed": 1,
  "duplicates": 1,
  "documents": [
    {
      "document_id": "abc123…",
      "original_filename": "vertrag.pdf",
      "status": "imported",
      "size": 12345,
      "sha256": "…64 Zeichen…",
      "message": "Dokument erfolgreich importiert"
    },
    {
      "document_id": null,
      "original_filename": "kopie.pdf",
      "status": "duplicate",
      "size": 12345,
      "sha256": "…",
      "duplicate_of_document_id": "abc123…",
      "message": "Duplikat erkannt"
    },
    {
      "document_id": null,
      "original_filename": "bild.png",
      "status": "rejected",
      "size": 999,
      "message": "Dateityp nicht unterstützt"
    }
  ]
}
```

Mögliche per-Datei-Status:
- `imported` – Dokument wurde gespeichert **und** der Produktionspfad erfolgreich abgeschlossen
- `reanalyzed` – gespeicherte Version wurde erfolgreich neu analysiert
- `analysis_failed` – Datei ist gespeichert, aber die Vertragsanalyse wurde nicht akzeptiert; ein sichtbarer Draft/Placeholder kann existieren
- `rejected` – abgelehnt (falscher Typ, zu groß, leer)
- `duplicate` – identische Datei bzw. bereits akzeptierte Version vorhanden
- `failed` – Speicher-/Systemfehler

Der HTTP-Request wartet auf die serverseitige Verarbeitung; der aktuelle
Importendpunkt startet **keinen** separaten Background-AI-Job.

## Bildbasierte PDF-Verarbeitung

Der produktive Standard ist Harness V3 mit einem lokalen Vision-Modell. Wenn
Docling/OCR keinen brauchbaren Text liefert, aber echte PDF-Seiten vorhanden
sind, endet der Import nicht mehr am Text-Gate. Die Seiten werden lokal,
größenbegrenzt gerendert und dem konfigurierten lokalen Vision-Modell übergeben.
Visuell gelesene Belege bleiben prüfpflichtig. Ein Analysefehler wird in der
Import-UI ausdrücklich als Analysefehler (nicht als grüner Erfolg) dargestellt.

Der synchrone Browser-Request hat wegen lokaler OCR/VLM-Laufzeiten ein
30-Minuten-Fenster; dies ändert nichts an den serverseitigen begrenzten
Provider-/Call-Budgets.

## Lokale Speicherung (nur lokal)

Dateien bleiben ausschließlich lokal unter `data/contracts/`. Es gibt keine
Cloud-, S3- oder externe API-Anbindung und keine Weiterleitung der Dateien.

### Verzeichnisstruktur

```text
data/contracts/
├─ .index.json                     # SHA-256 → Metadaten (Duplikat-Erkennung)
└─ <document_id>/                  # eindeutige ID (UUID hex)
   └─ original.<pdf|docx>          # physikalischer Dateiname (von Medflux festgelegt)
```

Der physikalische Dateiname wird von Medflux bestimmt. Der ursprüngliche
Dateiname wird ausschließlich als Metadatum gespeichert.

### Dateimetadaten

`document_id`, `original_filename`, `stored_filename`, `file_extension`,
`mime_type`, `file_size_bytes`, `sha256`, `storage_path`, `imported_at`,
`import_status`, optional `duplicate_detected` / `duplicate_of_document_id`.

## Dateigrößen-Limit

Maximal **50 MB** pro Datei (konfigurierbar). Die Grenze ist über die
Umgebungsvariable `MAX_UPLOAD_SIZE_MB` einstellbar (siehe `.env.example`)
und wird zentral im Settings-Objekt gelesen.

## Integrität (SHA-256)

Für jede importierte Datei wird lokal ein **SHA-256**-Hash berechnet. Er dient
später für Duplikat-Erkennung, Integritätsprüfung und Auditierbarkeit.

## Duplikat-Erkennung

Zwei exakt identische Dateien (gleicher SHA-256) werden erkannt. Ein Duplikat
wird **nicht** überschrieben und **nicht** erneut gespeichert. Es wird ein
`duplicate`-Ergebnis mit Verweis auf die ursprüngliche `document_id` geliefert.

Der Index liegt als lokale JSON-Datei (`.index.json`) vor; dies ist bewusst eine
Lösung ohne Datenbank, bis die Persistenz in einem späteren Schritt (Schritt 10)
eingeführt wird.

## Sicherheitsverhalten

- **Keine Ausführung** hochgeladener Dateien
- **Kein automatisches Öffnen** der Dateien
- **Lokale Inhaltsverarbeitung:** Parsing/OCR/Document Intelligence und KI-Analyse bleiben vollständig lokal
- **Keine externen Dienste**
- **Pfadsicherheit:** Nutzerdateinamen werden nie als Dateipfad verwendet;
  Path-Traversal (`../`, absolute Pfade) wird dadurch wirkungslos.
- **Fehlerbehandlung:** Kann eine Datei nicht gespeichert werden, wird sie
  nicht als erfolgreich gemeldet; unvollständige Ablagen werden aufgeräumt.
- **Deutsche Meldungen** für die UI (z. B. „Dokument erfolgreich importiert“,
  „Dateityp nicht unterstützt“, „Datei ist zu groß“, „Duplikat erkannt“,
  „Import fehlgeschlagen“). Keine Python-Tracebacks für Endnutzer.

## Backend-Struktur (Schritt 4)

```text
backend/app/documents/
├─ schemas.py   # ImportStatus, DocumentFile, ImportFileResult, ImportBatchResponse
├─ storage.py   # Ablage, sichere Pfade, Manifest-Index, Aufräumen
└─ service.py   # Validierung, SHA-256, Duplikat-Erkennung, Orchestrierung

backend/app/api/routes/documents.py   # POST /api/documents/import (dünn)
```

## Frontend

Die Seite **`/import`** (deutsch) ermöglicht:
- Auswahl einer oder mehrerer Dateien (`.pdf`, `.docx`)
- Drag & Drop
- Anzeige der ausgewählten Dateinamen vor dem Upload
- Button „Import starten“
- Anzeige des Ergebnisses pro Datei („Importiert“, „Duplikat“, „Fehlgeschlagen“)

## Tests

Backend-Tests abgedeckt:
- gültiger PDF-Import, gültiger DOCX-Import
- mehrere gültige Dateien (Batch)
- nicht unterstützte Dateiendung
- leere Datei
- zu große Datei
- Duplikat-Erkennung
- sicherer Speicherpfad
- SHA-256-Berechnung
- partieller Batch-Erfolg
- MIME-Konflikt
- API-Endpunkt (Batch + leerer Request)
