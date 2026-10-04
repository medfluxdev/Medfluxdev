"""Provider-Registry: bekannte lokale KI-Provider und Bau-Fabriken.

Die Registry ist die einzige Stelle, an der neue lokale Provider registriert
werden. Erkennung, Modell-Erkennung und Auswahl-Arbeit sind davon getrennt
(Discovery/Modell-Erkennung/Persistenz).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx

from app.ai.base import AIProvider
from app.core.config import Settings

logger = logging.getLogger(__name__)


class UnknownProviderError(Exception):
    """Wird geworfen, wenn ein Provider-Id nicht registriert ist."""


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    display_name: str
    kind: str  # "native" | "openai-compatible"
    endpoint: Callable[[Settings], str]
    detect: Callable[[httpx.AsyncClient, str], Awaitable[bool]]
    build: Callable[..., AIProvider]


_REGISTRY: dict[str, ProviderSpec] = {}


def register(spec: ProviderSpec) -> None:
    _REGISTRY[spec.provider_id] = spec


def register_all() -> None:
    """Registriert alle mitgelieferten Provider (Idempotent)."""
    from app.ai.providers.generic import (
        build_generic_openai_provider,
        detect_generic_openai,
    )
    from app.ai.providers.llamacpp import (
        build_llamacpp_provider,
        detect_llamacpp,
    )
    from app.ai.providers.lmstudio import (
        build_lmstudio_provider,
        detect_lmstudio,
    )
    from app.ai.providers.ollama import (
        build_ollama_provider,
        detect_ollama,
    )

    if _REGISTRY:
        return

    def _ollama_endpoint(s: Settings) -> str:
        return s.ollama_base_url

    def _lmstudio_endpoint(s: Settings) -> str:
        return s.lmstudio_base_url

    def _llamacpp_endpoint(s: Settings) -> str:
        return s.llama_cpp_base_url

    def _generic_endpoint(s: Settings) -> str:
        return s.generic_openai_base_url

    register(
        ProviderSpec(
            provider_id="ollama",
            display_name="Ollama",
            kind="native",
            endpoint=_ollama_endpoint,
            detect=detect_ollama,
            build=lambda settings, **kw: build_ollama_provider(settings, **kw),
        )
    )
    register(
        ProviderSpec(
            provider_id="lmstudio",
            display_name="LM Studio",
            kind="openai-compatible",
            endpoint=_lmstudio_endpoint,
            detect=detect_lmstudio,
            build=lambda settings, **kw: build_lmstudio_provider(settings, **kw),
        )
    )
    register(
        ProviderSpec(
            provider_id="llama-cpp",
            display_name="llama.cpp",
            kind="openai-compatible",
            endpoint=_llamacpp_endpoint,
            detect=detect_llamacpp,
            build=lambda settings, **kw: build_llamacpp_provider(settings, **kw),
        )
    )
    register(
        ProviderSpec(
            provider_id="generic-openai",
            display_name="Kompatibler lokaler Anbieter (OpenAI)",
            kind="openai-compatible",
            endpoint=_generic_endpoint,
            detect=detect_generic_openai,
            build=lambda settings, **kw: build_generic_openai_provider(settings, **kw),
        )
    )


def supported_provider_ids() -> list[str]:
    register_all()
    return list(_REGISTRY.keys())


def supports_provider(provider_id: str) -> bool:
    register_all()
    return provider_id in _REGISTRY


def get_provider_spec(provider_id: str) -> ProviderSpec | None:
    register_all()
    return _REGISTRY.get(provider_id)


def provider_display_name(provider_id: str) -> str:
    spec = get_provider_spec(provider_id)
    return spec.display_name if spec else provider_id


def build_provider(
    provider_id: str,
    settings: Settings,
    model_resolver: Callable[[], str] | None = None,
    client: httpx.AsyncClient | None = None,
    endpoint_override: str | None = None,
) -> AIProvider:
    spec = get_provider_spec(provider_id)
    if spec is None:
        raise UnknownProviderError(f"Unbekannter KI-Provider: {provider_id}")
    if provider_id == "generic-openai" and endpoint_override:
        return spec.build(
            settings,
            model_resolver=model_resolver,
            client=client,
            base_url_override=endpoint_override,
        )
    return spec.build(settings, model_resolver=model_resolver, client=client)


def endpoint_for(provider_id: str, settings: Settings, endpoint_override: str | None = None) -> str:
    spec = get_provider_spec(provider_id)
    if spec is None:
        return ""
    if endpoint_override:
        return endpoint_override
    return spec.endpoint(settings).strip()