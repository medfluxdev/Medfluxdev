"""Gemeinsame Basis für OpenAI-kompatible lokale Provider (LM Studio, llama.cpp).

Alle Provider sprechen `POST /v1/chat/completions` und `GET /v1/models`.
Native Metadaten (Vision/Fähigkeiten) werden von den konkreten Providern
geliefert – diese Basis liefert nur das, was das OpenAI-Protokoll kennt,
und lässt Unbekanntes als `None` stehen.
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
from app.ai.schemas import AIStatus, ModelCapabilities, ModelDescriptor, ModelInfo
from app.core.config import Settings

logger = logging.getLogger(__name__)

MSG_OK = "Lokale KI verfügbar."
MSG_UNAVAILABLE = "Die lokale KI ist derzeit nicht verfügbar."


class OpenAICompatProvider(AIProvider):
    """Basis eines lokalen, OpenAI-kompatiblen Providers."""

    kind = "openai-compatible"
    structured_mode: str = "json_object"  # "json_schema" | "json_object"

    def __init__(
        self,
        settings: Settings,
        model_resolver=None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(settings, model_resolver=model_resolver, client=client)

    @property
    def _base_url(self) -> str:
        raise NotImplementedError

    @contextlib.asynccontextmanager
    async def _get_client(self):
        if self._client is not None:
            yield self._client
        else:
            async with httpx.AsyncClient(timeout=self.settings.ai_request_timeout_seconds) as c:
                yield c

    async def _json_get(self, path: str) -> dict[str, Any]:
        async with self._get_client() as client:
            try:
                resp = await client.get(f"{self._base_url}{path}")
            except httpx.TimeoutException as exc:
                logger.warning("%s %s Timeout: %s", self.provider_id, path, exc)
                raise AITimeoutError() from exc
            except httpx.HTTPError as exc:
                logger.warning("%s %s nicht erreichbar: %s", self.provider_id, path, exc)
                raise AIUnavailableError() from exc
        if resp.status_code != 200:
            raise AIHTTPError(resp.status_code)
        try:
            data = resp.json()
        except ValueError as exc:
            raise AIMalformedResponseError() from exc
        if not isinstance(data, dict):
            raise AIMalformedResponseError()
        return data

    async def _list_model_ids(self) -> list[str]:
        data = await self._json_get("/v1/models")
        entries = data.get("data", [])
        return [m.get("id", "") for m in entries if isinstance(m, dict) and m.get("id")]

    async def model_info(self) -> ModelInfo:
        models = await self._list_model_ids()
        return ModelInfo(name=self._model(), available=self._model() in models)

    async def health_check(self) -> AIStatus:
        model = self._model()
        try:
            models = await self._list_model_ids()
        except AIUnavailableError as exc:
            return AIStatus(
                provider=self.provider_id,
                available=False,
                model=model,
                model_available=False,
                message=exc.user_message,
            )
        except AITimeoutError as exc:
            return AIStatus(
                provider=self.provider_id,
                available=False,
                model=model,
                model_available=False,
                message=exc.user_message,
            )
        model_available = model in models
        if model_available:
            return AIStatus(
                provider=self.provider_id,
                available=True,
                model=model,
                model_available=True,
                message=MSG_OK,
            )
        return AIStatus(
            provider=self.provider_id,
            available=True,
            model=model,
            model_available=False,
            message=f"Das lokale KI-Modell {model} ist nicht installiert.",
        )

    async def discover_models(self) -> list[ModelDescriptor]:
        """OpenAI-/v1/models-Fallback: nur IDs, Fähigkeiten unbekannt."""
        models = await self._list_model_ids()
        return [
            ModelDescriptor(
                provider_id=self.provider_id,
                model_id=m,
                state="available",
                capabilities=ModelCapabilities(text=True),
            )
            for m in models
        ]

    async def generate(
        self, text: str, system_prompt: str, max_tokens: int | None = None
    ) -> str:
        payload = self._chat_payload(text, system_prompt, max_tokens)
        return await self._chat(payload)

    async def generate_structured(
        self,
        text: str,
        system_prompt: str,
        schema: dict[str, Any],
        max_tokens: int | None = None,
    ) -> str:
        payload = self._chat_payload(text, system_prompt, max_tokens)
        if self.structured_mode == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "medflux_result", "schema": schema},
            }
        else:
            payload["response_format"] = {"type": "json_object"}
        return await self._chat(payload)

    def _chat_payload(
        self, text: str, system_prompt: str, max_tokens: int | None
    ) -> dict[str, Any]:
        return {
            "model": self._model(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": self.settings.ai_temperature,
            "max_tokens": max_tokens or self.settings.ai_max_tokens,
            "stream": False,
        }

    async def generate_request(self, text, system_prompt, schema, max_tokens,
                               context_tokens, images=None) -> str:
        # These servers configure context when loading the model. There is no
        # portable per-request context field: the planner enforces the budget.
        payload = self._chat_payload(text, system_prompt, max_tokens)
        if schema is not None:
            if self.structured_mode == "json_schema":
                payload["response_format"] = {"type": "json_schema", "json_schema": {
                    "name": "medflux_result", "schema": schema}}
            else:
                payload["response_format"] = {"type": "json_object"}
        if images:
            payload["messages"][1]["content"] = [{"type": "text", "text": text}] + [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + image}}
                for image in images]
        return await self._chat(payload)

    async def _chat(self, payload: dict[str, Any]) -> str:
        model = self._model()
        async with self._get_client() as client:
            try:
                resp = await client.post(f"{self._base_url}/v1/chat/completions", json=payload)
            except httpx.TimeoutException as exc:
                logger.warning("%s /v1/chat/completions Timeout (Modell %s): %s",
                               self.provider_id, model, exc)
                raise AITimeoutError() from exc
            except httpx.HTTPError as exc:
                logger.warning("%s /v1/chat/completions nicht erreichbar (Modell %s): %s",
                               self.provider_id, model, exc)
                raise AIUnavailableError() from exc

        if resp.status_code == 404:
            raise AIModelMissingError(model)
        if resp.status_code != 200:
            raise AIHTTPError(resp.status_code)

        try:
            data = resp.json()
        except ValueError as exc:
            raise AIMalformedResponseError() from exc

        choices = data.get("choices", []) if isinstance(data, dict) else []
        self.last_usage = data.get("usage", {}) if isinstance(data, dict) else {}
        self.last_done_reason = choices[0].get("finish_reason") if choices else None
        content = None
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            content = message.get("content") if isinstance(message, dict) else None
        if not content or not str(content).strip():
            raise AIEmptyResponseError()
        return str(content).strip()


async def probe_openai_models(client: httpx.AsyncClient, base_url: str) -> bool:
    """Ob unter `base_url` ein OpenAI-kompatibler /v1/models-Endpunkt antwortet.

    Dient ausschließlich als generischer Fingerabdruck – identifiziert KEINEN
    konkreten Provider (nur "OpenAI-kompatibel").
    """
    try:
        resp = await client.get(f"{base_url.rstrip('/')}/v1/models")
    except (httpx.TimeoutException, httpx.HTTPError):
        return False
    if resp.status_code != 200:
        return False
    try:
        data = resp.json()
    except ValueError:
        return False
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return False
    return True
