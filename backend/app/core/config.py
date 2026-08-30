"""Zentrale Konfiguration von Medflux (aus .env bzw. Umgebungsvariablen)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Medflux"
    app_version: str = "0.1.0"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    database_url: str = "sqlite:///./data/database/medflux.db"
    cors_origins: str = "http://localhost:3000"

    max_upload_size_mb: int = 50

    # Lokale KI (Provider-Abstraktion, Standard: Ollama)
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    # STEP 8B: bei nativer strukturierter Ausgabe (format=JSON-Schema) kann eine
    # Generierung lokal deutlich länger dauern als der frühere 120s-Default.
    # 300s verhindert falsche Timeouts, ohne die Zuverlässigkeit auszubremsen.
    ai_request_timeout_seconds: int = 300
    # Konservative, für faktenorientierte Verarbeitung geeignete Vorgaben
    ai_temperature: float = 0.1
    ai_max_tokens: int = 256
    # STEP 8B: qwen3:8b degeneriert bei nativer strukturierter Ausgabe in
    # Wiederholungsschleifen (Endlosschleife in einem Freitextfeld). Ein
    # repeat_penalty > 1.0 unterbricht diese Schleife (getestet: 1.3 liefert
    # kompaktes, abgeschlossenes, valides JSON). None/0 = Provider-Vorgabe.
    ai_repeat_penalty: float | None = 1.3
    # Thinking-Modus von Qwen3-artigen Modellen (aus: Modell antwortet direkt)
    ollama_think: bool = False
    # Strukturierte Extraktion (Schritt 7): eigenes, größeres Ausgabe-Budget,
    # da das komplette Vertrags-JSON nicht in 256 Tokens passt. Realer
    # qwen3:8b-Smoke-Test zeigte, dass 1024 Tokens bei ausführlichen
    # source_text-Belegen unzureichend sind (JSON wurde mitten im String
    # abgeschnitten, done_reason=length). 2048 ist ein sicherer, konservativer
    # Wert für qwen3:8b auf der Zielhardware; formal erst in Schritt 8
    # gebenchmarkt. Konfigurierbar über AI_EXTRACTION_MAX_TOKENS.
    # Aus dem Schritt-8-Benchmark wurde 8192 gesetzt: bei komplexen Verträgen
    # erzeugt qwen3:8b vollständige Vertrags-JSONs von >7000 Zeichen; 2048 führte
    # regelmäßig zu abgeschnittenem JSON (done_reason=length) und damit zu
    # verlorenen Chunks (Siemens, Apoplex, Truebeam, Abiomed).
    ai_extraction_max_tokens: int = 8192
    # Deterministische Chunk-Größe (Zeichen) für lange Verträge.
    ai_max_chunk_characters: int = 6000
    # STEP 8B-Semantik: Führt nach der Feldgruppen-Extraktion einen semantischen
    # Verifier-Durchlauf für sensible Felder aus (Kündigungsfrist, Verlängerung,
    # Daten, Kosten, Zahlungsintervall, Vertragsnummer). Kein 'Raten' – nur
    # Stützung prüfen und Unsicherheit erhalten. Konfigurierbar über
    # AI_RUN_SEMANTIC_VERIFICATION.
    ai_run_semantic_verification: bool = True

    # OCR / Textextraktion
    ocr_enabled: bool = True
    tesseract_cmd: str = ""
    ocr_lang: str = "deu"

    data_dir: str = "./data"
    contracts_dir: str = "./data/contracts"
    backups_dir: str = "./data/backups"

    app_secret_key: str = "change-me"
    auth_enabled: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
