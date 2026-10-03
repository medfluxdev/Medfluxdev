"""KI-Service: Provider-Auswahl, Status- und Generierungs-Orchestrierung.

Enthält keine Vertrags-Extraktionslogik (das folgt in Schritt 7). Die aktive
Provider-/Modell-Auswahl wird zur LAUFZEIT aufgelöst (ausschließlich die explizit persistierte Auswahl), sodass ein Wechsel in den
Einstellungen ohne Neustart und ohne Neuanalyse der Verträge wirksam wird.
"""

import logging
import time

import httpx

from app.ai.exceptions import AIProviderError, AIUnavailableError
from app.ai.providers.registry import build_provider, supports_provider
from app.ai.settings_service import (
    resolve_endpoint_for_provider,
    resolve_model_id,
    resolve_provider_id,
)
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
        self._client = client
        self._provider = None

    def active_provider_id(self) -> str | None:
        """Explizit gewählter Provider oder None."""
        return resolve_provider_id(self.settings)

    def active_model_id(self) -> str | None:
        """Explizit gewähltes Modell oder None."""
        return resolve_model_id(self.settings)

    def _model_resolver(self):
        provider_id = self.active_provider_id()

        def _resolve() -> str:
            return self.active_model_id()

        return _resolve

    def _ensure_provider(self):
        provider_id = self.active_provider_id()
        model_id = self.active_model_id()
        if not provider_id or not model_id or not supports_provider(provider_id):
            self._provider = None
            return None
        if self._provider is None or self._provider.provider_id != provider_id:
            endpoint_override = resolve_endpoint_for_provider(self.settings, provider_id)
            self._provider = build_provider(
                provider_id,
                self.settings,
                model_resolver=self._model_resolver(),
                client=self._client,
                endpoint_override=endpoint_override if provider_id == "generic-openai" else None,
            )
        return self._provider

    @property
    def configured(self) -> bool:
        return self._ensure_provider() is not None

    @property
    def last_done_reason(self) -> str | None:
        if self._provider is None or not hasattr(self._provider, "last_done_reason"):
            return None
        return getattr(self._provider, "last_done_reason")

    async def status(self) -> AIStatus:
        """Liefert einen sicheren, strukturierten KI-Status (nie eine Exception)."""
        provider_id = self.active_provider_id()
        model = self.active_model_id()
        provider = self._ensure_provider()
        if provider is None:
            return AIStatus(
                provider=provider_id,
                available=False,
                model=model,
                model_available=False,
                message="Kein KI-Modell ausgewählt. Bitte in den Einstellungen Provider und Modell auswählen.",
            )
        try:
            return await provider.health_check()
        except AIProviderError as exc:
            return AIStatus(
                provider=provider_id,
                available=False,
                model=model,
                model_available=False,
                message=exc.user_message,
            )

    async def generate(self, text: str) -> str:
        """Sendet Text an das lokale Modell. Wirft deutsche AIProviderError-Fehler."""
        provider = self._ensure_provider()
        if provider is None:
            raise AIUnavailableError()
        start = time.monotonic()
        try:
            result = await provider.generate(text, TEST_SYSTEM_PROMPT)
            logger.info(
                "KI-Generierung erfolgreich: provider=%s model=%s dauer=%.2fs",
                self.active_provider_id(), self.active_model_id(),
                time.monotonic() - start,
            )
            return result
        except AIProviderError:
            logger.warning(
                "KI-Generierung fehlgeschlagen: provider=%s model=%s dauer=%.2fs",
                self.active_provider_id(), self.active_model_id(),
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
        provider = self._ensure_provider()
        if provider is None:
            raise AIUnavailableError()
        start = time.monotonic()
        try:
            result = await provider.generate(text, system_prompt, max_tokens)
            logger.info(
                "KI-Extraktion erfolgreich: provider=%s model=%s dauer=%.2fs",
                self.active_provider_id(), self.active_model_id(),
                time.monotonic() - start,
            )
            return result
        except AIProviderError:
            logger.warning(
                "KI-Extraktion fehlgeschlagen: provider=%s model=%s dauer=%.2fs",
                self.active_provider_id(), self.active_model_id(),
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
        provider = self._ensure_provider()
        if provider is None:
            raise AIUnavailableError()
        start = time.monotonic()
        try:
            result = await provider.generate_structured(
                text, system_prompt, schema, max_tokens
            )
            logger.info(
                "KI-Strukturierte-Extraktion erfolgreich: provider=%s model=%s dauer=%.2fs",
                self.active_provider_id(), self.active_model_id(),
                time.monotonic() - start,
            )
            return result
        except AIProviderError:
            logger.warning(
                "KI-Strukturierte-Extraktion fehlgeschlagen: provider=%s model=%s dauer=%.2fs",
                self.active_provider_id(), self.active_model_id(),
                time.monotonic() - start,
            )
            raise

    async def generate_test(self, text: str) -> AITestResponse:
        """Test-Endpunkt-Antwort: Erfolg oder deutscher Hinweis (niemals Crash)."""
        provider_id = self.active_provider_id()
        model = self.active_model_id()
        try:
            response = await self.generate(text)
        except AIProviderError as exc:
            return AITestResponse(
                provider=provider_id,
                model=model,
                response=None,
                error=exc.user_message,
            )
        return AITestResponse(
            provider=provider_id,
            model=model,
            response=response,
            error=None,
        )

    async def harness_runtime(self):
        """Pin provider, endpoint and model for one processing run, without changing selection."""
        provider_id, model_id = self.active_provider_id(), self.active_model_id()
        if not provider_id or not model_id:
            raise AIUnavailableError("Kein KI-Modell ausgewählt.")
        endpoint = resolve_endpoint_for_provider(self.settings, provider_id)
        provider = build_provider(provider_id, self.settings, model_resolver=lambda: model_id,
                                  client=self._client,
                                  endpoint_override=endpoint if provider_id == "generic-openai" else None)
        models = await provider.discover_models()
        descriptor = next((m for m in models if m.model_id == model_id and m.state == "available"), None)
        if descriptor is None:
            raise AIUnavailableError()
        return provider, descriptor
