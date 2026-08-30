# AGENTS.md – Projektanweisungen Medflux

Diese Datei ist die maßgebliche Anweisungsquelle für die Arbeit mit dem Medflux-Projekt.

## Projektüberblick

Medflux ist ein lokales, schlankes KI-System für deutsche Krankenhäuser zur Analyse und Überwachung von Wartungs- und Serviceverträgen. Es arbeitet **vollständig lokal** – ohne externe KI-API.

Kernfunktionen (Roadmap):
- Lokaler Import mehrerer PDF/DOCX-Verträge
- Vollständig lokale KI-Analyse (Ollama, Qwen3 8B Q4)
- Strukturierte Extraktion von Vertragsdaten (Quelle + Seite + Confidence)
- Überwachung von Vertragsende und Kündigungsfristen
- Kostenauswertung (jährlich/monatlich/Gesamt)
- Warnungen und Handlungsbedarf
- Dashboard, Vertragsliste, Detailansicht mit Quellenanzeige

## Tech-Stack

| Bereich       | Technologie                        |
|---------------|------------------------------------|
| Frontend      | Next.js / React / TypeScript       |
| Backend       | Python + FastAPI                   |
| Lokale KI     | Ollama (Qwen3 8B Q4)               |
| DB MVP        | SQLite, Produktion: PostgreSQL     |
| PDF           | PyMuPDF                            |
| DOCX          | python-docx                        |
| OCR           | lokal, nur wenn nötig              |
| Architektur   | KI-Schicht austauschbar            |

## Repository-Struktur

```text
Medflux/            <- Projekt-Root (kein verschachtelter Projektordner!)
├─ frontend/        # Next.js / React / TypeScript
├─ backend/         # Python + FastAPI + Ollama
├─ data/            # contracts, database, backups (nicht eingecheckt)
├─ docs/            # Projekt-Historie & Architektur-Doku
├─ scripts/         # Hilfsskripte
├─ .env.example     # Umgebungsvariablen-Vorlage
├─ AGENTS.md        # diese Datei
├─ README.md
└─ docker-compose.yml
```

Wichtig:
- Der Projekt-Root ist das `Medflux`-Verzeichnis. **Keine** verschachtelten Ordner `vertragsmonitor-ai` oder `Medflux` anlegen.
- `PROJECT_PROGRESS.md` liegt unter `docs/PROJECT_PROGRESS.md`.
- Dateneinstände unter `data/` werden nie eingecheckt (siehe `.gitignore`).

## Projektfortschritt

Der Fortschritt wird in `docs/PROJECT_PROGRESS.md` nachvollzogen, mit 18 Hauptschritten. Jeder Schritt wird in PHP-artiger Detailstruktur (Status, Datum, Implementiertes, Dateien, Tests, Probleme, nächster Schritt) dokumentiert.

**Arbeitsregel:** Nach jedem abgeschlossenen Schritt muss `docs/PROJECT_PROGRESS.md` aktualisiert werden (Status, Datum, Dokumentation, Dateiliste, Tests/Ergebnis, bekannte Probleme, nächster Schritt, Fortschritt x/18 und Prozent). Kein neuer Hauptschritt beginnt, bevor die Fortschrittsdatei aktualisiert wurde.

## Definition of Done (MVP)

Das MVP ist fertig, wenn:
1. mehrere PDF/DOCX-Verträge importiert werden können
2. Qwen lokal analysiert
3. Kerninformationen zuverlässig extrahiert werden
4. Ergebnisse gespeichert werden
5. Kündigungsfristen programmatisch berechnet werden
6. Warnungen erscheinen
7. jährliche Kosten aggregiert werden
8. Dashboard funktioniert
9. Vertragsliste funktioniert
10. Vertragsdetail + Quellenanzeige funktioniert
11. keine externe KI-API notwendig ist
12. ein lokales Backup möglich ist

## Entwicklungskommandos

### Backend (Python/FastAPI)

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Tests (Backend)

```bash
cd backend
pytest
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build
npm run lint
```

## Konventionen

- Backend-Python: Pydantic-Modelle, Typ-Hints, keine unnötigen Kommentare.
- Frontend-TypeScript: strikte Typisierung.
- Lokale KI: Die KI extrahiert **Fakten**; Berechnungen (Fristen, Kostenaggregation, Warnstufen) macht **Code**, nicht die KI.
- Keine erfundenen Werte: "nicht gefunden" statt Halluzination.
- Sensible Daten (Zugänge, Secrets) nie committen; nur über `.env.example` dokumentieren.
