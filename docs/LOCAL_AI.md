# Medflux – Lokale KI (Local AI, Schritt 6)

Dieses Dokument beschreibt die lokale KI-Integration von Medflux (Schritt 6).
Es geht ausschließlich um eine **zuverlässige lokale KI-Verbindung** und eine
**saubere Provider-Abstraktion**. Die strukturierte Extraktion von
Vertragsfeldern (Anbieter, Kosten, SLA usw.) **folgt erst in Schritt 7**.

## Warum lokale KI?

Medflux arbeitet für deutsche Krankenhäuser mit sensiblen Vertragsdaten.
Der gesamte KI-Betrieb läuft **lokal** – ohne OpenAI, Anthropic, Gemini, Azure
OpenAI oder andere Cloud-Inferenz-Dienste. Vertragstext verlässt den lokalen
Medflux-Rechner **nie**.

## Architektur (Ollama)

Ollama ist die lokale KI-Engine. Medflux spricht ausschließlich den lokalen
Ollama-HTTP-Endpunkt an:

- `GET  {OLLAMA_BASE_URL}/api/tags`  → Liste der installierten Modelle
- `POST {OLLAMA_BASE_URL}/api/chat` → Generierung (system + user)

Default-Modell: **`qwen3:8b`** (konfigurierbar über `OLLAMA_MODEL`).

## Provider-Abstraktion

Medflux ist **nicht** dauerhaft an Ollama gekoppelt. Eine schlanke
`AIProvider`-Schnittstelle (in `backend/app/ai/base.py`) definiert:

- `health_check() -> AIStatus` – Erreichbarkeit + Modellverfügbarkeit
- `model_info() -> ModelInfo` – Name + Verfügbarkeit des Modells
- `generate(text, system_prompt) -> str` – Textgenerierung

`OllamaProvider` (in `backend/app/ai/providers/ollama.py`) ist die erste
Implementierung. Später kann ein anderes lokales Modell bzw. eine andere lokale
Engine eingebunden werden, ohne die restliche Anwendung zu ändern.

## Konfiguration

In `.env.example` bzw. `backend/app/core/config.py` (zentral, nicht
mehrfach hartkodiert):

| Variable                     | Standard                      | Bedeutung                                  |
|------------------------------|-------------------------------|--------------------------------------------|
| `AI_PROVIDER`                | `ollama`                      | Aktiver KI-Anbieter (nur lokal)            |
| `OLLAMA_BASE_URL`            | `http://127.0.0.1:11434`     | Lokaler Ollama-Endpunkt                    |
| `OLLAMA_MODEL`               | `qwen3:8b`                    | Konfiguriertes lokales Modell              |
| `AI_REQUEST_TIMEOUT_SECONDS` | `120`                         | Timeout je Anfrage (Sekunden)              |
| `AI_TEMPERATURE`             | `0.1`                         | Niedrige Variation (faktenorientiert)      |
| `AI_MAX_TOKENS`              | `256`                         | Max. Ausgabe-Tokens (num_predict)          |
| `OLLAMA_THINK`               | `false`                       | Thinking-Modus (Qwen3) aus – Antwort direkt |

> **Thinking-Modus (Qwen3):** Qwen3-artige Modelle haben einen eingebauten
> „Thinking“-Schritt. Ist er aktiv, kann er das Token-Budget verbrauchen und die
> eigentliche Antwort landet nicht in `message.content` (Medflux würde sonst
> „keine Antwort“ melden). Mit `OLLAMA_THINK=false` (Standard) antwortet das
> Modell direkt – geeignet für die faktenorientierte, ressourcenschonende
> Verarbeitung.

## Status-Endpunkt

```
GET /api/ai/status
```

Liefert strukturierte Information (nie einen Crash):

```json
{
  "provider": "ollama",
  "available": true,
  "model": "qwen3:8b",
  "model_available": true,
  "message": "Lokale KI verfügbar."
}
```

Es werden keine unnötigen Systemdetails preisgegeben.

## Test-/Entwicklungs-Endpunkt

```
POST /api/ai/test
Body: { "text": "..." }
```

Sendet den Text an das lokale Modell und liefert die Antwort. Bei Fehlern wird
eine **deutsche** Meldung im `error`-Feld zurückgegeben (Status bleibt `200`).
Dieser Endpunkt dient **nur** der Verifikation der lokalen KI – er ist **keine**
strukturierte Vertragsextraktion.

Erfolg:
```json
{ "provider": "ollama", "model": "qwen3:8b", "response": "…", "error": null }
```

Fehler:
```json
{ "provider": "ollama", "model": "qwen3:8b", "response": null,
  "error": "Die lokale KI ist derzeit nicht verfügbar." }
```

Das minimale System-Prompt ist:
> „Du bist eine lokale KI-Komponente von Medflux. Antworte auf Deutsch.
> Erfinde keine Informationen, die nicht im Eingabetext enthalten sind.“

## Verhalten / Fehlerbehandlung

| Situation                        | Verhalten                                              |
|----------------------------------|--------------------------------------------------------|
| Ollama nicht gestartet/erreichbar| „Die lokale KI ist derzeit nicht verfügbar.“            |
| Modell `qwen3:8b` nicht installiert | „Das lokale KI-Modell qwen3:8b ist nicht installiert.“ |
| Timeout                          | „… nicht rechtzeitig geantwortet (Zeitüberschreitung).“ |
| HTTP-Fehler                      | „Die lokale KI hat einen Fehler zurückgegeben.“         |
| Ungültiges JSON                  | „Die lokale KI hat eine ungültige Antwort geliefert.“   |
| Leere Antwort                    | „Die lokale KI hat keine Antwort geliefert.“            |

Kein Modellwechsel, kein automatischer Download, keine Roh-Exceptions für Nutzer.
Es wird **nicht** still auf ein anderes Modell ausgewichen.

## Datenschutz / Privatsphäre

- **Alles lokal** – keine externen Netzwerkaufrufe.
- In Logs werden Provider, Modell, Dauer und Erfolg/Misserfolg erfasst,
  **nicht** der volle Vertragstext und keine sensiblen Dokumentinhalte.

## Hardware-Überlegungen

Zielhardware: Ryzen 7 5800X, 32 GB RAM, RTX 3070 (8 GB VRAM), Windows 10.
Die Standardwerte sind bewusst konservativ: kurzer Kontext, `num_predict=256`,
Timeout 120 s. Es wird in diesem Schritt **kein** 12B+ Modell konfiguriert oder
heruntergeladen.

## Modell-Austauschstrategie

Das Modell ist über `OLLAMA_MODEL` konfigurierbar. Die Provider-Abstraktion
funktioniert auch mit einem anderen Ollama-Modell. Ein anderes Modell wird in
Ollama installiert und `OLLAMA_MODEL` entsprechend gesetzt – ohne Codeänderung.
Ein komplett anderer Provider (nicht Ollama) würde eine neue Klasse implementieren,
die `AIProvider` erfüllt.

## Backend-Struktur (Schritt 6)

```text
backend/app/ai/
├─ __init__.py            # Exports
├─ base.py                # AIProvider (abstrakt)
├─ schemas.py             # AIStatus, AITestRequest/Response, ModelInfo
├─ exceptions.py          # AIProviderError + spezifische Fehler (deutsche Meldungen)
├─ service.py             # AIService (Provider-Auswahl, Status, Generierung, Logging)
└─ providers/
   ├─ __init__.py
   └─ ollama.py           # OllamaProvider (httpx, /api/tags, /api/chat)

backend/app/api/routes/ai.py   # GET /api/ai/status, POST /api/ai/test
```

## Tests

Alle Tests laufen **ohne echte Ollama-Installation** (httpx.MockTransport).
Abgedeckt: Provider-Konfiguration, Ollama verfügbar/nicht verfügbar, Modell
verfügbar/fehlt, erfolgreiche Generierung, Timeout, HTTP-Fehler, fehlerhafte
Antwort, leere Antwort, Status-API, Test-API, deutsche Meldungen und „kein
externer Provider konfiguriert“. Alle bisherigen Tests (Schritt 3–5) bleiben grün.
