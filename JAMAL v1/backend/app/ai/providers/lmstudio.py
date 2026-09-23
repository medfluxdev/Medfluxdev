"""LM Studio-Provider – lokaler OpenAI-kompatibler Anbieter.

Native Endpunkte von LM Studio (https://lmstudio.ai/docs):
- `GET /api/v1/models` – Modelle mit `type`, `key`, `display_name`,
  `architecture`, `quantization.name`, `params_string`, `loaded_instances`,
  `max_context_length`, `capabilities.vision` (autoritativ).
- `GET /api/v0/models` – älteres natives Format (`object: "list"`, `type`
  in `llm|vlm|embeddings`, `state`).
- Generierung über `POST /v1/chat/completions` (OpenAI-kompatibel).

Fähigkeiten werden aus den nativen Metadaten gelesen – nie aus Modell-Namen.
"""

import logging
from typing import Any

import httpx

from app.ai.exceptions import AIHTTPError, AIMalformedResponseError
from app.ai.providers.openai_compat import OpenAICompatProvider
from app.ai.schemas import ModelCapabilities, ModelDescriptor
from app.core.config import Settings

logger = logging.getLogger(__name__)


class LMStudioProvider(OpenAICompatProvider):
    """Lokale KI über eine laufende LM-Studio-Instanz."""

    provider_id = "lmstudio"
    display_name = "LM Studio"
    structured_mode = "json_object"

    @property
    def _base_url(self) -> str:
        return self.settings.lmstudio_base_url.rstrip("/")

    async def discover_models(self) -> list[ModelDescriptor]:
        try:
            native = await self._json_get("/api/v1/models")
        except (AIHTTPError, AIMalformedResponseError):
            native = None
        if native is not None and isinstance(native.get("models"), list):
            return self._parse_native_v1(native["models"])
        try:
            v0 = await self._json_get("/api/v0/models")
        except (AIHTTPError, AIMalformedResponseError):
            v0 = None
        if v0 is not None and isinstance(v0.get("data"), list):
            return self._parse_native_v0(v0["data"])
        return await super().discover_models()

    def _parse_native_v1(self, entries: list[Any]) -> list[ModelDescriptor]:
        result: list[ModelDescriptor] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            mtype = str(entry.get("type") or "")
            key = entry.get("key") or entry.get("id") or ""
            if not key:
                continue
            model_id = str(key)
            caps = ModelCapabilities(
                text=mtype != "embedding" if mtype else None,
                vision=None,
                embedding=mtype == "embedding" if mtype else None,
            )
            caps_raw = entry.get("capabilities")
            if isinstance(caps_raw, dict):
                vision = caps_raw.get("vision")
                if isinstance(vision, bool):
                    caps.vision = vision
                if caps.vision is None and mtype == "vlm":
                    caps.vision = True
            elif mtype == "vlm":
                caps.vision = True
            loaded_instances = entry.get("loaded_instances") or []
            loaded = isinstance(loaded_instances, list) and len(loaded_instances) > 0
            context = entry.get("max_context_length")
            if isinstance(loaded_instances, list) and loaded_instances:
                inst = loaded_instances[0]
                if isinstance(inst, dict):
                    inst_cfg = inst.get("config")
                    if isinstance(inst_cfg, dict):
                        inst_ctx = inst_cfg.get("context_length")
                        if isinstance(inst_ctx, (int, float)):
                            context = inst_ctx
            quant = entry.get("quantization")
            quantization = quant.get("name") if isinstance(quant, dict) else None
            result.append(
                ModelDescriptor(
                    provider_id=self.provider_id,
                    model_id=model_id,
                    display_name=entry.get("display_name"),
                    state="available",
                    loaded=loaded,
                    context_length=int(context) if isinstance(context, (int, float)) else None,
                    quantization=quantization,
                    family=entry.get("architecture"),
                    parameter_size=entry.get("params_string"),
                    capabilities=caps,
                )
            )
        return result

    def _parse_native_v0(self, data: list[Any]) -> list[ModelDescriptor]:
        result: list[ModelDescriptor] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            mtype = str(entry.get("type") or "")
            model_id = entry.get("id") or entry.get("key") or ""
            if not model_id:
                continue
            caps = ModelCapabilities(
                text=(mtype in ("llm", "vlm")) if mtype else None,
                vision=(mtype == "vlm") if mtype else None,
                embedding=(mtype == "embeddings") if mtype else None,
            )
            context = entry.get("max_context_length")
            result.append(
                ModelDescriptor(
                    provider_id=self.provider_id,
                    model_id=str(model_id),
                    display_name=entry.get("display_name"),
                    state="available" if entry.get("state") != "unavailable" else "unavailable",
                    loaded=True if entry.get("state") == "loaded" else None,
                    context_length=int(context) if isinstance(context, (int, float)) else None,
                    quantization=entry.get("quantization"),
                    family=entry.get("arch") or entry.get("architecture"),
                    capabilities=caps,
                )
            )
        return result


async def detect_lmstudio(client: httpx.AsyncClient, base_url: str) -> bool:
    """Natiwert Fingerabdruck von LM Studio (`/api/v1/models` oder `/api/v0/models`)."""
    base = base_url.rstrip("/")
    try:
        v1 = await client.get(f"{base}/api/v1/models")
        if v1.status_code == 200:
            try:
                data = v1.json()
            except ValueError:
                data = None
            if isinstance(data, dict) and isinstance(data.get("models"), list):
                probes = data["models"]
                if probes and isinstance(probes[0], dict):
                    first = probes[0]
                    if "type" in first and ("key" in first or "loaded_instances" in first):
                        return True
        v0 = await client.get(f"{base}/api/v0/models")
        if v0.status_code == 200:
            try:
                data = v0.json()
            except ValueError:
                data = None
            if (
                isinstance(data, dict)
                and data.get("object") == "list"
                and isinstance(data.get("data"), list)
            ):
                probes = data["data"]
                if probes and isinstance(probes[0], dict):
                    if str(probes[0].get("type")) in ("llm", "vlm", "embeddings"):
                        return True
    except (httpx.TimeoutException, httpx.HTTPError):
        return False
    return False


def build_lmstudio_provider(
    settings: Settings,
    model_resolver=None,
    client: httpx.AsyncClient | None = None,
) -> LMStudioProvider:
    return LMStudioProvider(settings, model_resolver=model_resolver, client=client)