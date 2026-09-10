"""Abstraktion der lokalen KI – austauschbare Provider (Schritt 6).

Medflux ist nicht fest an ein konkretes lokales Modell gekoppelt. Ein
`AIProvider` kapselt Health-Check, Modell-Info, Modell-Erkennung und
Textgenerierung, damit später ein anderes lokales Modell (oder eine andere
lokale Engine) ohne Änderung an der restlichen Anwendung eingesetzt werden kann.

Provider sind von der Auswahl-ENTSCHEIDUNG getrennt: Die Persistenz (Schritt 6B)
liest die aktive Provider-/Modell-Auswahl zur Laufzeit. Ein Provider erhält über
einen `model_resolver`-Callback das aktive Modell, ohne selbst die DB zu kennen.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable

from app.ai.schemas import AIStatus, ModelDescriptor, ModelInfo
from app.core.config import Settings

ModelResolver = Callable[[], str]


class AIProvider(ABC):
    """Basis-Interface für lokale KI-Anbieter."""

    provider_id: str = "unknown"
    display_name: str = "Unbekannt"
    kind: str = "native"
    supports_structured_output: bool = True

    def __init__(
        self,
        settings: Settings,
        model_resolver: ModelResolver | None = None,
        client: Any | None = None,
    ) -> None:
        self.settings = settings
        self._model_resolver = model_resolver
        self._client = client
        # Letzter `done_reason` der letzten Generierung, falls verfügbar.
        self.last_done_reason: str | None = None
        self.last_usage: dict[str, int | None] = {}

    async def generate_request(
        self, text: str, system_prompt: str, schema: dict[str, Any] | None,
        max_tokens: int, context_tokens: int, images: list[str] | None = None,
    ) -> str:
        """Provider-neutral request; adapters must implement context/image transport."""
        raise NotImplementedError("Provider does not implement Harness requests")

    @property
    def default_model(self) -> str:
        """Bootstrap-Modell aus der Umgebungskonfiguration."""
        return self.settings.ollama_model

    def _model(self) -> str:
        """Aktives Modell: aufgelöste Persistenz oder Bootstrap-Default."""
        if self._model_resolver is not None:
            return self._model_resolver()
        return self.default_model

    @abstractmethod
    async def health_check(self) -> AIStatus:
        """Prüft Erreichbarkeit und Modellverfügbarkeit."""

    @abstractmethod
    async def model_info(self) -> ModelInfo:
        """Liefert Name und Verfügbarkeit des konfigurierten Modells."""

    @abstractmethod
    async def discover_models(self) -> list[ModelDescriptor]:
        """Liefert alle beim Provider gefundenen Modelle (normalisiert).

        Felder, für die keine autoritativen Metadaten vorliegen, bleiben `None`
        ("unbekannt") – es wird nichts geraten.
        """

    @abstractmethod
    async def generate(
        self, text: str, system_prompt: str, max_tokens: int | None = None
    ) -> str:
        """Sendet Text an das lokale Modell und liefert die Antwort.

        `max_tokens` erlaubt ein aufgabenabhängiges Ausgabe-Budget (z. B. ein
        größeres Budget für strukturierte Extraktion). Bei None wird der
        Provider-Standard (ai_max_tokens) verwendet.
        Wirft bei Fehlern eine `AIProviderError`-Unterklasse mit deutscher Meldung.
        """

    @abstractmethod
    async def generate_structured(
        self,
        text: str,
        system_prompt: str,
        schema: dict[str, Any],
        max_tokens: int | None = None,
    ) -> str:
        """Sendet Text an das lokale Modell und erzwingt eine JSON-Antwort
        gemäß dem übergebenen JSON-Schema (native strukturierte Ausgabe).

        `schema` ist ein selbstenthaltenes JSON-Schema (ohne `$ref`/`$defs`),
        das der Provider nativ erzwingt. Die Antwort ist ein JSON-String, der
        der Struktur des Schemas entspricht (Semantik bleibt der KI überlassen).
        Wirft bei Fehlern eine `AIProviderError`-Unterklasse mit deutscher Meldung.
        """
