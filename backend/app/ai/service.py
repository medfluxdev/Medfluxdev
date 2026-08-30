"""KI-Service: Provider-Auswahl, Status- und Generierungs-Orchestrierung.

Enthält keine Vertrags-Extraktionslogik (das folgt in Schritt 7).
"""

import logging
import time

import httpx

from app.ai.exceptions import AIProviderError, AIUnavailableError
from app.ai.providers.ollama import build_ollama_provider
from app.ai.schemas import AITestResponse, AIStatus
from app.core.config import Settings

logger = logging.getLogger(__name__)

TEST_SYSTEM_PROMPT = (
    "Du bist eine lokale KI-Komponente von Medflux. "
    "Antworte auf Deutsch. Erfinde keine Informationen, "
    "die nicht im Eingabetext enthalten sind."
)


class AIService:
    """Fasst die lokale KI zusammen und stellt eine schlanke Schnittstelle bereit."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._provider = None
        if settings.ai_provider == "ollama":
            self._provider = build_ollama_provider(settings, client=client)
        else:
            logger.warning("Unbekannter AI_PROVIDER %r – kein Provider aktiv",
                           settings.ai_provider)

    @property
    def configured(self) -> bool:
        return self._provider is not None

    @property
    def last_done_reason(self) -> str | None:
        """Letzter `done_reason` der letzten Generierung, falls verfügbar."""
        if self._provider is None or not hasattr(self._provider, "last_done_reason"):
            return None
        return getattr(self._provider, "last_done_reason")

    async def status(self) -> AIStatus:
        """Liefert einen sicheren, strukturierten KI-Status (nie eine Exception)."""
        if not self.configured:
            return AIStatus(
                provider=self.settings.ai_provider,
                available=False,
                model=self.settings.ollama_model,
                model_available=False,
                message="Kein lokaler KI-Provider konfiguriert.",
            )
        try:
            return await self._provider.health_check()
        except AIProviderError as exc:
            return AIStatus(
                provider=self.settings.ai_provider,
                available=False,
                model=self.settings.ollama_model,
                model_available=False,
                message=exc.user_message,
            )

    async def generate(self, text: str) -> str:
        """Sendet Text an das lokale Modell. Wirft deutsche AIProviderError-Fehler."""
        if not self.configured:
            raise AIUnavailableError()
        start = time.monotonic()
        try:
            result = await self._provider.generate(text, TEST_SYSTEM_PROMPT)
            logger.info(
                "KI-Generierung erfolgreich: provider=%s model=%s dauer=%.2fs",
                self.settings.ai_provider, self.settings.ollama_model,
                time.monotonic() - start,
            )
            return result
        except AIProviderError:
            logger.warning(
                "KI-Generierung fehlgeschlagen: provider=%s model=%s dauer=%.2fs",
                self.settings.ai_provider, self.settings.ollama_model,
                time.monotonic() - start,
            )
            raise

    async def generate_text(
        self, text: str, system_prompt: str, max_tokens: int | None = None
    ) -> str:
        """Sendet Text mit eigenem System-Prompt und Ausgabe-Budget an die KI.

        Wird für die strukturierte Vertragsextraktion (Schritt 7) genutzt, die
        ein größeres `max_tokens`-Budget als der Test-Endpunkt benötigt.
        Wirft deutsche AIProviderError-Fehler; loggt nur Metadaten.
        """
        if not self.configured:
            raise AIUnavailableError()
        start = time.monotonic()
        try:
            result = await self._provider.generate(text, system_prompt, max_tokens)
            logger.info(
                "KI-Extraktion erfolgreich: provider=%s model=%s dauer=%.2fs",
                self.settings.ai_provider, self.settings.ollama_model,
                time.monotonic() - start,
            )
            return result
        except AIProviderError:
            logger.warning(
                "KI-Extraktion fehlgeschlagen: provider=%s model=%s dauer=%.2fs",
                self.settings.ai_provider, self.settings.ollama_model,
                time.monotonic() - start,
            )
            raise

    async def generate_structured(
        self,
        text: str,
        system_prompt: str,
        schema: dict,
        max_tokens: int | None = None,
    ) -> str:
        """Sendet Text und erzwingt JSON gemäß `schema` (native strukturierte
        Ausgabe). Nutzung für die Vertragsextraktion (STEP 8B).
        Wirft deutsche AIProviderError-Fehler; loggt nur Metadaten.
        """
        if not self.configured:
            raise AIUnavailableError()
        start = time.monotonic()
        try:
            result = await self._provider.generate_structured(
                text, system_prompt, schema, max_tokens
            )
            logger.info(
                "KI-Strukturierte-Extraktion erfolgreich: provider=%s model=%s dauer=%.2fs",
                self.settings.ai_provider, self.settings.ollama_model,
                time.monotonic() - start,
            )
            return result
        except AIProviderError:
            logger.warning(
                "KI-Strukturierte-Extraktion fehlgeschlagen: provider=%s model=%s dauer=%.2fs",
                self.settings.ai_provider, self.settings.ollama_model,
                time.monotonic() - start,
            )
            raise

    async def generate_test(self, text: str) -> AITestResponse:
        """Test-Endpunkt-Antwort: Erfolg oder deutscher Hinweis (niemals Crash)."""
        try:
            response = await self.generate(text)
        except AIProviderError as exc:
            return AITestResponse(
                provider=self.settings.ai_provider,
                model=self.settings.ollama_model,
                response=None,
                error=exc.user_message,
            )
        return AITestResponse(
            provider=self.settings.ai_provider,
            model=self.settings.ollama_model,
            response=response,
            error=None,
        )
