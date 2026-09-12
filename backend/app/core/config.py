"""Zentrale Konfiguration von Medflux (aus .env bzw. Umgebungsvariablen)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Medflux"
    app_version: str = "0.1.0"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    database_url: str = "postgresql+psycopg://medflux@127.0.0.1:5432/medflux"
    cors_origins: str = "http://localhost:3000"
    max_upload_size_mb: int = 50

    ai_provider: str = "ollama"
    harness_context_tokens: int = 8192
    harness_output_tokens: int = 1800
    harness_max_calls: int = 32
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    lmstudio_base_url: str = "http://127.0.0.1:1234"
    llama_cpp_base_url: str = ""
    generic_openai_base_url: str = ""
    ai_discovery_timeout_seconds: float = 2.0
    ai_request_timeout_seconds: int = 300
    ai_temperature: float = 0.1
    ai_max_tokens: int = 256
    ai_repeat_penalty: float | None = 1.3
    ollama_think: bool = False
    ai_extraction_max_tokens: int = 8192
    ai_max_chunk_characters: int = 6000
    ai_run_semantic_verification: bool = True

    ocr_enabled: bool = True
    tesseract_cmd: str = ""
    ocr_lang: str = "deu"
    document_intelligence_provider: str = "docling"
    document_intelligence_table_structure: bool = True
    document_processing_stale_minutes: int = 60

    data_dir: str = "./data"
    contracts_dir: str = "./data/contracts"
    backups_dir: str = "./data/backups"

    app_secret_key: str = "change-me"
    # Authentication is now first-class. Disable only for isolated migration/tests.
    auth_enabled: bool = True
    auth_cookie_name: str = "medflux_session"
    auth_cookie_secure: bool = False  # local HTTP; set true behind HTTPS
    auth_session_days: int = 14

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
