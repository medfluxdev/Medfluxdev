"""Ollama-Provider – ausschließlich lokale Kommunikation über die Ollama-API.

Es werden nur die lokalen Endpunkte `/api/tags` (Modell-Liste) und
`/api/chat` (Generierung) verwendet. Keine externen Netzwerkaufrufe.
"""

import contextlib
import logging
from typing import Any

import httpx

from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIEmptyResponseError,
    AIHTTPError,
    AIMalformedResponseError,
    AIModelMissingError,
    AITimeoutError,
    AIUnavailableError,
)
from app.ai.schemas import AIStatus, ModelInfo
from app.core.config import Settings

logger = logging.getLogger(__name__)

MSG_OK = "Lokale KI verfügbar."
MSG_UNAVAILABLE = "Die lokale KI ist derzeit nicht verfügbar."
MSG_TIMEOUT = "Die lokale KI hat nicht rechtzeitig geantwortet (Zeitüberschreitung)."


class OllamaProvider(AIProvider):
    """Lokale KI über eine laufende Ollama-Instanz."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        # Letzter `done_reason` der letzten Generierung (z. B. "stop"/"length")
        self.last_done_reason: str | None = None

    @contextlib.asynccontextmanager
    async def _get_client(self):
        if self._client is not None:
            yield self._client
        else:
            async with httpx.AsyncClient(
                timeout=self.settings.ai_request_timeout_seconds
            ) as c:
                yield c

    @property
    def _base_url(self) -> str:
        return self.settings.ollama_base_url.rstrip("/")

    async def _list_models(self) -> list[str]:
        async with self._get_client() as client:
            try:
                resp = await client.get(f"{self._base_url}/api/tags")
            except httpx.TimeoutException as exc:
                logger.warning("Ollama /api/tags Timeout: %s", exc)
                raise AITimeoutError() from exc
            except httpx.HTTPError as exc:
                logger.warning("Ollama /api/tags nicht erreichbar: %s", exc)
                raise AIUnavailableError() from exc
        if resp.status_code != 200:
            raise AIHTTPError(resp.status_code)
        try:
            data = resp.json()
        except ValueError as exc:
            raise AIMalformedResponseError() from exc
        models = data.get("models", []) if isinstance(data, dict) else []
        return [m.get("name", "") for m in models if isinstance(m, dict)]

    async def model_info(self) -> ModelInfo:
        models = await self._list_models()
        return ModelInfo(
            name=self.settings.ollama_model,
            available=self.settings.ollama_model in models,
        )

    async def health_check(self) -> AIStatus:
        try:
            models = await self._list_models()
        except AIUnavailableError as exc:
            return AIStatus(
                provider=self.settings.ai_provider,
                available=False,
                model=self.settings.ollama_model,
                model_available=False,
                message=exc.user_message,
            )
        except AITimeoutError as exc:
            return AIStatus(
                provider=self.settings.ai_provider,
                available=False,
                model=self.settings.ollama_model,
                model_available=False,
                message=exc.user_message,
            )

        model_available = self.settings.ollama_model in models
        if model_available:
            return AIStatus(
                provider=self.settings.ai_provider,
                available=True,
                model=self.settings.ollama_model,
                model_available=True,
                message=MSG_OK,
            )
        return AIStatus(
            provider=self.settings.ai_provider,
            available=True,
            model=self.settings.ollama_model,
            model_available=False,
            message=f"Das lokale KI-Modell {self.settings.ollama_model} ist nicht installiert.",
        )

    def _options(self, max_tokens: int | None) -> dict[str, Any]:
        options: dict[str, Any] = {
            "temperature": self.settings.ai_temperature,
            "num_predict": max_tokens or self.settings.ai_max_tokens,
        }
        rp = self.settings.ai_repeat_penalty
        if rp is not None and rp > 0:
            options["repeat_penalty"] = rp
        return options

    async def generate(
        self, text: str, system_prompt: str, max_tokens: int | None = None
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "think": self.settings.ollama_think,
            "options": self._options(max_tokens),
        }
        return await self._chat(payload)

    async def generate_structured(
        self,
        text: str,
        system_prompt: str,
        schema: dict[str, Any],
        max_tokens: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "think": self.settings.ollama_think,
            # Native strukturierte Ausgabe: Ollama erzwingt die Struktur/Enums
            # des übergebenen (selbstenthaltenen) JSON-Schemas.
            "format": schema,
            "options": self._options(max_tokens),
        }
        return await self._chat(payload)

    async def _chat(self, payload: dict[str, Any]) -> str:
        async with self._get_client() as client:
            try:
                resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            except httpx.TimeoutException as exc:
                logger.warning("Ollama /api/chat Timeout (Modell %s): %s",
                               self.settings.ollama_model, exc)
                raise AITimeoutError() from exc
            except httpx.HTTPError as exc:
                logger.warning("Ollama /api/chat nicht erreichbar (Modell %s): %s",
                               self.settings.ollama_model, exc)
                raise AIUnavailableError() from exc

        if resp.status_code == 404:
            raise AIModelMissingError(self.settings.ollama_model)
        if resp.status_code != 200:
            raise AIHTTPError(resp.status_code)

        try:
            data = resp.json()
        except ValueError as exc:
            raise AIMalformedResponseError() from exc

        message = data.get("message", {}) if isinstance(data, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        self.last_done_reason = data.get("done_reason")
        if not content or not str(content).strip():
            raise AIEmptyResponseError()
        return str(content).strip()


def build_ollama_provider(
    settings: Settings, client: httpx.AsyncClient | None = None
) -> OllamaProvider:
    """Erzeugt einen OllamaProvider aus den zentralen Settings.

    `client` erlaubt das Injizieren eines (gemockten) httpx-Clients in Tests.
    """
    return OllamaProvider(settings, client=client)
