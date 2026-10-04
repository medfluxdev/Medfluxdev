# Medflux Backend

FastAPI-Backend mit lokaler KI-Anbindung (Ollama) für Medflux.

## Struktur

```text
backend/
├─ app/
│  ├─ api/          # API-Routers
│  ├─ ai/           # austauschbare ModelProvider-Schnittstelle (Ollama)
│  ├─ contracts/    # Vertrags-Business-Logik
│  ├─ documents/    # PDF/DOCX-Import & Textextraktion
│  ├─ alerts/       # Warnsystem
│  ├─ database/     # DB-Anbindung (SQLite MVP)
│  ├─ models/       # Datenmodelle
│  └─ main.py       # FastAPI-Einstiegspunkt
├─ tests/           # Tests
└─ requirements.txt
```

## Setup

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head
```

Die Migration ist auch nach jedem Pull auszuführen, damit neue Funktionen (zum Beispiel die editierbaren Profilfelder) die benötigten Datenbankspalten besitzen. `scripts/setup.ps1` erledigt diesen Schritt automatisch.

## Starten

```bash
uvicorn app.main:app --reload --port 8000
```

API-Dokumentation: `http://localhost:8000/docs`
