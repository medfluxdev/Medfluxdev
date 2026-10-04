"""llama.cpp / llama-server-Provider – lokaler OpenAI-kompatibler Anbieter.

Native Fingerabdrücke von llama-server:
- `GET /props` – liefert `default_generation_settings`, `model_path`,
  `total_slots`, `chat_template` (autoritativer Nachweis).
- `GET /health` – liefert `200` mit Body `ok`.
- Modelle über `GET /v1/models`; Generierung über `POST /v1/chat/completions`.

Ohne konfigurierten Endpunkt (leerer `llama_cpp_base_url`) gilt der Provider
als "nicht konfiguriert" und spricht nie ein Netzwerk an.
"""

import logging
from typing import Any

import httpx

from app.ai.providers.openai_compat import OpenAICompatProvider
from app.ai.schemas import AIStatus, ModelCapabilities, ModelDescriptor
from app.core.config import Settings

logger = logging.getLogger(__name__)

MSG_NOT_CONFIGURED = "Der Endpunkt für llama.cpp ist nicht konfiguriert (llama_cpp_base_url leer)."


class LlamaCppProvider(OpenAICompatProvider):
    """Lokale KI über eine laufende llama.cpp / llama-server-Instanz."""

    provider_id = "llama-cpp"
    display_name = "llama.cpp"
    structured_mode = "json_schema"

    @property
    def _base_url(self) -> str:
        return self.settings.llama_cpp_base_url.rstrip("/")

    async def health_check(self) -> AIStatus:
        if not self.settings.llama_cpp_base_url:
            return AIStatus(
                provider=self.provider_id,
                available=False,
                model=self._model(),
                model_available=False,
                message=MSG_NOT_CONFIGURED,
            )
        return await super().health_check()

    async def discover_models(self) -> list[ModelDescriptor]:
        """Modelle aus /v1/models; Kontext aus /props (falls vorhanden)."""
        probes = await self._try_props()
        context_length = None
        if probes is not None and isinstance(probes, dict):
            settings_raw = probes.get("default_generation_settings")
            if isinstance(settings_raw, dict):
                n_ctx = settings_raw.get("n_ctx")
                if isinstance(n_ctx, (int, float)):
                    context_length = int(n_ctx)
        descriptor = ModelDescriptor(
            provider_id=self.provider_id,
            model_id="-",
            state="available",
            context_length=context_length,
            capabilities=ModelCapabilities(text=True),
        )
        models = await super().discover_models()
        return [
            descriptor.model_copy(
                update={
                    "model_id": m.model_id,
                    "context_length": context_length or m.context_length,
                }
            )
            for m in models
        ]

    async def _try_props(self) -> dict[str, Any] | None:
        if self._client is not None:
            client = self._client
            close = False
        else:
            client = httpx.AsyncClient(timeout=self.settings.ai_request_timeout_seconds)
            close = True
        try:
            resp = await client.get(f"{self._base_url}/props")
        except (httpx.TimeoutException, httpx.HTTPError):
            return None
        finally:
            if close:
                await client.aclose()
        if resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except ValueError:
            return None
        return data if isinstance(data, dict) else None


async def detect_llamacpp(client: httpx.AsyncClient, base_url: str) -> bool:
    """Autoritativer Fingerabdruck von llama.cpp/llama-server."""
    base = base_url.rstrip("/")
    try:
        props = await client.get(f"{base}/props")
        if props.status_code == 200:
            try:
                data = props.json()
            except ValueError:
                data = None
            if isinstance(data, dict) and (
                "default_generation_settings" in data
                or "model_path" in data
                or "total_slots" in data
            ):
                return True
        health = await client.get(f"{base}/health")
        if health.status_code == 200 and health.text.strip() == "ok":
            return True
    except (httpx.TimeoutException, httpx.HTTPError):
        return False
    return False


def build_llamacpp_provider(
    settings: Settings,
    model_resolver=None,
    client: httpx.AsyncClient | None = None,
) -> LlamaCppProvider:
    return LlamaCppProvider(settings, model_resolver=model_resolver, client=client)