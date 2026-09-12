"""Generischer OpenAI-kompatibler Provider (Fallback).

Wenn ein lokaler Endpunkt über `/v1/models` antwortet, sich aber KEIN
konkreter Provider (Ollama/LM Studio/llama.cpp) autoritativ nachweisen lässt,
repräsentiert Medflux ihn als diesen generischen Anbieter – er wird nie
fälschlich als LM Studio oder llama.cpp ausgegeben. Fähigkeiten bleiben bis auf
Text-Chat unbekannt (`None`).
"""

import logging

import httpx

from app.ai.providers.openai_compat import OpenAICompatProvider, probe_openai_models
from app.core.config import Settings

logger = logging.getLogger(__name__)


class GenericOpenAIProvider(OpenAICompatProvider):
    """OpenAI-kompatibler lokaler Anbieter unbekannter Herkunft."""

    provider_id = "generic-openai"
    display_name = "Kompatibler lokaler Anbieter (OpenAI)"
    structured_mode = "json_object"

    def __init__(
        self,
        settings: Settings,
        model_resolver=None,
        client: httpx.AsyncClient | None = None,
        base_url_override: str | None = None,
    ) -> None:
        self._base_url_override = base_url_override
        super().__init__(settings, model_resolver=model_resolver, client=client)

    @property
    def _base_url(self) -> str:
        return (self._base_url_override or self.settings.generic_openai_base_url).rstrip("/")


def build_generic_openai_provider(
    settings: Settings,
    model_resolver=None,
    client: httpx.AsyncClient | None = None,
    base_url_override: str | None = None,
) -> GenericOpenAIProvider:
    return GenericOpenAIProvider(
        settings,
        model_resolver=model_resolver,
        client=client,
        base_url_override=base_url_override,
    )


async def detect_generic_openai(client: httpx.AsyncClient, base_url: str) -> bool:
    """Generischer Nachweis: OpenAI-kompatible /v1/models-Liste."""
    return await probe_openai_models(client, base_url)