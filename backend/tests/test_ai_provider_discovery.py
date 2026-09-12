"""Fokussierte Tests: Provider-Erkennung und Modell-Normalisierung (Schritt 6B).

Nur Mock-Transports (httpx.MockTransport) – es wird KEINE echte Ollama-,
LM-Studio- oder llama.cpp-Installation vorausgesetzt oder konsultiert.
"""

from __future__ import annotations

from typing import Callable

import httpx
import pytest

from app.ai.providers.discovery import discover_providers
from app.ai.schemas import ProviderInfo
from app.core.config import Settings

OLLAMA_URL = "http://127.0.0.1:11434"
LMSTUDIO_URL = "http://127.0.0.1:1234"
LLAMACPP_URL = "http://127.0.0.1:8080"


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _route(routes: dict[str, httpx.Response]) -> httpx.AsyncClient:
    def handler(req: httpx.Request) -> httpx.Response:
        return routes.get(req.url.path, httpx.Response(404, json={"error": "missing"}))

    return _client(handler)


def _json(data, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=data)


def _settings(**overrides) -> Settings:
    base = {
        "ollama_base_url": OLLAMA_URL,
        "lmstudio_base_url": LMSTUDIO_URL,
        "llama_cpp_base_url": "",
        "generic_openai_base_url": "",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


# ------------------------------------------------------------ Ollama-Erkennung

@pytest.mark.asyncio
async def test_discovery_identifies_ollama_natively():
    settings = _settings()
    ollama_tag = {"models": [{"name": "qwen3:8b", "details": {"family": "qwen3"}}]}
    client = _route({"/api/tags": _json(ollama_tag)})
    providers = await discover_providers(settings, client=client)

    ollama = next(p for p in providers if p.provider_id == "ollama")
    assert ollama.reachable is True
    assert ollama.detection == "native"
    assert ollama.endpoint == OLLAMA_URL
    assert ollama.models[0].model_id == "qwen3:8b"
    # lmstudio-Base wurde nicht identifiziert und ist NICHT OpenAI-kompatibel
    lmstudio = next(p for p in providers if p.provider_id == "lmstudio")
    assert lmstudio.reachable is False
    assert "nicht erreichbar" in lmstudio.message_de
    # llama.cpp ohne Endpunkt = nicht konfiguriert
    llamacpp = next(p for p in providers if p.provider_id == "llama-cpp")
    assert llamacpp.reachable is False
    assert "nicht konfiguriert" in llamacpp.message_de
    # kein generischer Fallback auf dem Ollama-Port
    assert not any(p.provider_id == "generic-openai" for p in providers)


# ------------------------------------------------------------ LM Studio (nativ)

@pytest.mark.asyncio
async def test_discovery_identifies_lmstudio_via_native_v1():
    settings = _settings(llama_cpp_base_url=LLAMACPP_URL)
    natives = {
        "/api/v1/models": _json(
            {
                "models": [
                    {
                        "type": "vlm",
                        "key": "qwen2.5-vl-7b",
                        "display_name": "Qwen2.5 VL 7B",
                        "architecture": "qwen2.5-vl",
                        "quantization": {"name": "Q4_K_M"},
                        "params_string": "7.8B",
                        "loaded_instances": [{"id": "1", "config": {"context_length": 32768}}],
                        "max_context_length": 131072,
                        "capabilities": {"vision": True},
                    }
                ]
            }
        ),
        "/v1/models": _json({"object": "list", "data": [{"id": "qwen2.5-vl-7b"}]}),
        "/props": httpx.Response(404),
        "/health": httpx.Response(404),
    }
    client = _route(natives)
    providers = await discover_providers(settings, client=client)

    lmstudio = next(p for p in providers if p.provider_id == "lmstudio")
    assert lmstudio.reachable is True
    assert lmstudio.detection == "openai-compatible"
    model = lmstudio.models[0]
    assert model.model_id == "qwen2.5-vl-7b"
    assert model.capabilities.text is True
    assert model.capabilities.vision is True
    assert model.capabilities.embedding is False
    assert model.loaded is True
    assert model.context_length == 32768
    assert model.quantization == "Q4_K_M"
    assert model.family == "qwen2.5-vl"
    assert model.parameter_size == "7.8B"
    # llama.cpp-Port wurde nicht als llama.cpp erkannt
    llamacpp = next(p for p in providers if p.provider_id == "llama-cpp")
    assert llamacpp.reachable is False


@pytest.mark.asyncio
async def test_discovery_identifies_lmstudio_via_native_v0():
    settings = _settings()
    client = _route(
        {
            "/api/v0/models": _json(
                {
                    "object": "list",
                    "data": [
                        {
                            "id": "modell",
                            "type": "vlm",
                            "arch": "qwen2.5-vl",
                            "quantization": "Q4_K_M",
                            "state": "loaded",
                            "max_context_length": 131072,
                        }
                    ],
                }
            )
        }
    )
    providers = await discover_providers(settings, client=client)
    lmstudio = next(p for p in providers if p.provider_id == "lmstudio")
    assert lmstudio.reachable is True
    assert lmstudio.models[0].model_id == "modell"
    assert lmstudio.models[0].capabilities.vision is True
    assert lmstudio.models[0].loaded is True


@pytest.mark.asyncio
async def test_lmstudio_detection_requires_native_signature():
    # NUR /v1/models (OpenAI-Shape) ist KEIN LM-Studio-Nachweis.
    settings = _settings()
    client = _route(
        {"/v1/models": _json({"object": "list", "data": [{"id": "irgendwas"}]})}
    )
    providers = await discover_providers(settings, client=client)
    lmstudio = next(p for p in providers if p.provider_id == "lmstudio")
    assert lmstudio.reachable is False
    assert lmstudio.detection is None
    # ... aber der generische Fallback (nicht falsch als LM Studio):
    generic = next(
        p for p in providers if p.provider_id == "generic-openai" and p.endpoint == LMSTUDIO_URL
    )
    assert generic.reachable is True
    assert generic.endpoint == LMSTUDIO_URL
    assert generic.detection == "openai-compatible"


# ------------------------------------------------------------ llama.cpp

@pytest.mark.asyncio
async def test_discovery_identifies_llamacpp_via_props():
    settings = _settings(llama_cpp_base_url=LLAMACPP_URL)
    client = _route(
        {
            "/props": _json(
                {
                    "default_generation_settings": {"n_ctx": 4096},
                    "model_path": "/models/qwen.gguf",
                    "total_slots": 1,
                }
            ),
            "/health": httpx.Response(200, text="ok"),
            "/v1/models": _json(
                {"object": "list", "data": [{"id": "qwen3", "object": "model"}]}
            ),
        }
    )
    providers = await discover_providers(settings, client=client)
    llamacpp = next(p for p in providers if p.provider_id == "llama-cpp")
    assert llamacpp.reachable is True
    model = llamacpp.models[0]
    assert model.model_id == "qwen3"
    assert model.capabilities.text is True
    assert model.capabilities.vision is None
    assert model.context_length == 4096


@pytest.mark.asyncio
async def test_unknown_openai_endpoint_not_falsely_identified():
    settings = _settings(llama_cpp_base_url=LLAMACPP_URL)
    client = _route(
        {
            # llama.cpp-Port antwortet nur OpenAI-kompatibel, kein /props-/health-Proof
            "/v1/models": _json(
                {"object": "list", "data": [{"id": "whatever"}]}
            ),
        }
    )
    providers = await discover_providers(settings, client=client)
    llamacpp = next(p for p in providers if p.provider_id == "llama-cpp")
    assert llamacpp.reachable is False
    assert llamacpp.detection is None
    generic = next(
        p for p in providers if p.provider_id == "generic-openai" and p.endpoint == LLAMACPP_URL
    )
    assert generic.reachable is True
    assert generic.endpoint == LLAMACPP_URL


# ------------------------------------------------ Modell-Normalisierung (Ollama)

@pytest.mark.asyncio
async def test_ollama_model_normalization_authoritative_vision():
    settings = _settings()
    tags = {
        "models": [
            {
                "name": "qwen3-vl:8b-instruct",
                "details": {"family": "qwen3vl", "parameter_size": "8.8B", "quantization_level": "Q4_K_M"},
            },
            {
                "name": "nomic-embed-text",
                "details": {"family": "nomic-embed"},
            },
        ]
    }
    show_vl = {
        "model_info": {
            "general.architecture": "qwen3vl",
            "qwen3vl.vision.patch_size": 14,
            "qwen3vl.vision.num_channels": 3,
            "qwen3vl.attention.head_count": 36,
            "qwen3vl.context_length": 32768,
        },
        "details": {"family": "qwen3vl", "parameter_size": "8.8B", "quantization_level": "Q4_K_M"},
    }

    client = _client(
        lambda req: (
            _json(tags)
            if req.url.path == "/api/tags"
            else _json(
                show_vl
                if "qwen3-vl" in req.content.decode("utf-8")
                else {"model_info": {}, "details": {}}
            )
        )
    )
    providers = await discover_providers(settings, client=client)
    ollama = next(p for p in providers if p.provider_id == "ollama")
    by_id = {m.model_id: m for m in ollama.models}

    vl = by_id["qwen3-vl:8b-instruct"]
    # Autoritativ über `qwen3vl.vision.*`-Metadaten, NICHT über den Modell-Namen:
    assert vl.capabilities.vision is True
    assert vl.capabilities.text is True
    assert vl.capabilities.embedding is None
    assert vl.context_length == 32768
    assert vl.quantization == "Q4_K_M"
    assert vl.family == "qwen3vl"

    embed = by_id["nomic-embed-text"]
    assert embed.capabilities.text is False
    assert embed.capabilities.embedding is True
    assert embed.capabilities.vision is None


@pytest.mark.asyncio
async def test_vl_name_substring_not_treated_as_vision():
    settings = _settings()
    tags = {
        "models": [
            {"name": "smol-vl:latest", "details": {"family": "smol"}},
        ]
    }
    client = _route({"/api/tags": _json(tags)})
    providers = await discover_providers(settings, client=client)
    ollama = next(p for p in providers if p.provider_id == "ollama")
    model = ollama.models[0]
    # Kein autoritatives Vision-Metadatum und Familie nicht in Vision-Wissen:
    assert model.capabilities.vision is None
    assert model.capabilities.text is True


@pytest.mark.asyncio
async def test_unknown_capability_stays_unknown_on_openai_fallback():
    settings = _settings(llama_cpp_base_url=LLAMACPP_URL)
    client = _route(
        {
            "/v1/models": _json(
                {"object": "list", "data": [{"id": "irgendwas"}]}
            )
        }
    )
    providers = await discover_providers(settings, client=client)
    generic = next(p for p in providers if p.provider_id == "generic-openai")
    model = generic.models[0]
    assert model.capabilities.text is True
    assert model.capabilities.vision is None
    assert model.capabilities.embedding is None
    assert model.context_length is None
    assert model.quantization is None


# ------------------------------------------- Keine Inferenz bei Erkennung

@pytest.mark.asyncio
async def test_discovery_performs_no_inference():
    calls: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.url.path)
        if req.url.path == "/api/tags":
            return _json({"models": [{"name": "qwen3:8b", "details": {"family": "qwen3"}}]})
        return _json({"error": "not found"}, 404)

    settings = _settings()
    providers = await discover_providers(settings, client=_client(handler))
    ollama = next(p for p in providers if p.provider_id == "ollama")
    assert ollama.reachable is True
    assert "/api/chat" not in calls
    assert "/v1/chat/completions" not in calls