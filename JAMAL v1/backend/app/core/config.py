"""Zentrale Konfiguration von Medflux (aus .env bzw. Umgebungsvariablen)."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Medflux"
    app_version: str = "0.1.0"
    app_env: str = "development"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # STEP 10: PostgreSQL ist die Ziel-DB. Credentials NIE hier hartkodieren –
    # sie kommen ausschließlich aus .env / Umgebung (DATABASE_URL). Der Default
    # ist ein lokaler, passwortloser WSL-PostgreSQL-Zugang ohne Secret.
    database_url: str = "postgresql+psycopg://medflux@127.0.0.1:5432/medflux"
    cors_origins: str = "http://localhost:3000"

    max_upload_size_mb: int = 50

    # Lokale KI. Provider-Endpunkte sind konfigurierbar; das aktive Modell
    # wird ausschließlich durch den Benutzer in der DB ausgewählt.
    ai_provider: str = "ollama"
    harness_context_tokens: int = 8192
    harness_output_tokens: int = 1800
    harness_max_calls: int = 32
    harness_engine: str = "v3"
    harness_vision_pages_per_batch: int = 4
    harness_vision_batch_scale: int = 1600
    harness_vision_min_pages_for_batch: int = 2
    harness_vision_max_calls: int = 16
    document_intelligence_atomic_geometry: bool = False
    document_intelligence_atomic_geometry_dpi: int = 200
    ollama_base_url: str = "http://127.0.0.1:11434"
    # Legacy-Kompatibilitätsfeld; wird NICHT als aktive Modellauswahl verwendet.
    ollama_model: str = ""
    lmstudio_base_url: str = "http://127.0.0.1:1234"
    llama_cpp_base_url: str = ""
    generic_openai_base_url: str = ""
    ai_discovery_timeout_seconds: float = 2.0
    ai_request_timeout_seconds: int = 300
    ai_temperature: float = 0.1
    ai_max_tokens: int = 256
    ai_repeat_penalty: float | None = 1.3
    ollama_think: bool = False
    # None = Ollama entscheidet automatisch. Fuer lokale GPU-Tests kann ein
    # expliziter Layer-Wert (z. B. 999 fuer "so viele wie moeglich") gesetzt
    # werden; der Wert wird pro Request als num_gpu an Ollama uebergeben.
    ollama_num_gpu: int | None = None
    ai_extraction_max_tokens: int = 8192
    ai_max_chunk_characters: int = 6000
    ai_run_semantic_verification: bool = True

    # OCR / Dokument-Intelligence
    ocr_enabled: bool = True
    tesseract_cmd: str = ""
    ocr_lang: str = "deu"
    document_intelligence_provider: str = "docling"
    document_intelligence_table_structure: bool = True
    # Docling darf nicht hart auf CPU festgenagelt sein. "auto" nutzt den
    # verfuegbaren Beschleuniger (CUDA auf kompatibler NVIDIA-Hardware).
    document_intelligence_device: Literal["auto", "cuda", "cpu"] = "auto"
    document_processing_stale_minutes: int = 60

    data_dir: str = "./data"
    contracts_dir: str = "./data/contracts"
    backups_dir: str = "./data/backups"

    # STEP 16 + integriertes Ahmad-Accountmodell.
    app_secret_key: str = "change-me"
    auth_enabled: bool = False
    auth_cookie_name: str = "medflux_session"
    auth_session_ttl_seconds: int = 8 * 60 * 60
    auth_session_days: int = 14
    development_auth_mode: bool = True
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_auth_runtime(self) -> None:
        env = self.app_env.strip().casefold()
        if env not in {"development", "test", "pilot", "production"}:
            raise RuntimeError(
                "APP_ENV muss development, test, pilot oder production sein."
            )
        if env in {"pilot", "production"} and not self.auth_enabled:
            raise RuntimeError(
                "APP_ENV=pilot/production erfordert AUTH_ENABLED=true."
            )
        if self.auth_enabled and self.app_secret_key == "change-me":
            raise RuntimeError(
                "AUTH_ENABLED=true erfordert einen eigenen APP_SECRET_KEY."
            )
        if env in {"pilot", "production"} and not self.auth_cookie_secure:
            raise RuntimeError(
                "APP_ENV=pilot/production erfordert AUTH_COOKIE_SECURE=true."
            )
        if self.auth_session_ttl_seconds < 300:
            raise RuntimeError("AUTH_SESSION_TTL_SECONDS muss mindestens 300 sein.")
        if self.auth_cookie_samesite not in {"lax", "strict", "none"}:
            raise RuntimeError("AUTH_COOKIE_SAMESITE ist ungueltig.")
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            raise RuntimeError(
                "AUTH_COOKIE_SAMESITE=none erfordert AUTH_COOKIE_SECURE=true."
            )
        if "*" in self.cors_origins_list:
            raise RuntimeError(
                "CORS-Wildcard-Origin ist nicht erlaubt, weil der "
                "Frontend-Client Requests mit Credentials sendet."
            )


settings = Settings()
settings.validate_auth_runtime()
