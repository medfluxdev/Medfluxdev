# Medflux

Lokales, schlankes KI-System für deutsche Krankenhäuser zur Analyse und Überwachung von Wartungs- und Serviceverträgen.

Medflux importiert Verträge lokal (PDF/DOCX), analysiert sie vollständig lokal mit einer austauschbaren KI-Schicht und extrahiert strukturierte Vertragsdaten, überwacht Kündigungsfristen und wertet Kosten aus – ganz ohne externe KI-API.

## Funktionen (MVP-Roadmap)

- Lokaler Import mehrerer PDF/DOCX-Verträge
- Vollständig lokale KI-Analyse (Ollama)
- Strukturierte Extraktion von Vertragsdaten (Quelle + Seite + Confidence)
- Überwachung von Vertragsende und Kündigungsfristen
- Jährliche/monatliche/Gesamtkosten-Auswertung
- Warnungen und Handlungsbedarf
- Dashboard, Vertragsliste, Detailansicht mit Quellenanzeige
- Lokaler Login & Audit (Minimalversion)
- CSV/Excel-Export und lokales Backup

## Technologie-Stack

| Bereich        | Technologie                                   |
|----------------|-----------------------------------------------|
| Frontend       | Next.js / React / TypeScript                  |
| Backend        | Python + FastAPI                              |
| Lokale KI      | Ollama (Qwen3-VL 8B, lokal)                     |
| Datenbank      | PostgreSQL 18                                 |
| Produktion     | PostgreSQL (lokal / Docker)                    |
| PDF            | PyMuPDF                                       |
| DOCX           | python-docx                                   |
| OCR            | lokal, nur wenn nötig                         |

## Projektstatus

Siehe [docs/PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md) für den detaillierten Fortschritt.

## Projektstruktur

```text
Medflux/
├─ frontend/       # Next.js / React / TypeScript
├─ backend/        # Python + FastAPI + Ollama
├─ data/           # contracts, database, backups (lokal, ignoriert)
├─ docs/           # Projekt- und Architektur-Doku
├─ scripts/        # Hilfsskripte
├─ .env.example    # Umgebungsvariablen-Vorlage
├─ AGENTS.md       # Projektanweisungen für die Entwicklung
└─ docker-compose.yml
```

## Schnellstart

### Voraussetzungen

- Node.js 20+
- Python 3.11+
- Ollama (Produktionspfad: installiertes Vision-Modell `qwen3-vl:8b-instruct`)
- (optional) Docker

### Backend starten (lokal)

```bash
cd backend
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend starten (lokal)

```bash
cd frontend
npm install
npm run dev
```

Dann das Frontend unter `http://localhost:3000` öffnen.

### Umgebungsvariablen

Kopiere `.env.example` nach `.env` und passe die Werte an.

## Definition of Done (MVP)

Siehe [docs/PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md) – Abschnitt "Definition of Done für MVP".

## Lizenz

Proprietär / intern – keine externe Veröffentlichung vorgesehen.
