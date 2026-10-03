"""Selection endpoint must parse authority, never trust localhost string prefixes."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import ai


@pytest.mark.parametrize("endpoint", [
    "http://localhost:80@remote.example/v1",
    "http://127.0.0.1:80@remote.example/v1",
    "http://localhost:abc/v1",
    "http://localhost:1234#fragment",
    "https://localhost:1234/v1",
    "http://remote.example:1234/v1",
])
def test_generic_provider_rejects_unsafe_endpoints_before_probe(
    monkeypatch, endpoint,
):
    monkeypatch.setattr(ai, "_require_ai_admin", lambda request: None)
    monkeypatch.setattr(ai, "get_provider_spec", lambda provider: object())
    async def must_not_probe(*args, **kwargs):
        raise AssertionError("Unsafe endpoint reached network probe")
    monkeypatch.setattr(ai.discovery, "probe_provider_reachable", must_not_probe)
    payload = SimpleNamespace(
        provider_id="generic-openai", model_id="local-model",
        endpoint=endpoint,
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(ai.ai_set_selection(SimpleNamespace(), payload))
    assert exc.value.status_code == 400


@pytest.mark.parametrize("endpoint", [
    "http://localhost:1234/v1",
    "http://127.0.0.1:11434/v1",
])
def test_generic_provider_accepts_explicit_loopback_authority(
    monkeypatch, endpoint,
):
    monkeypatch.setattr(ai, "_require_ai_admin", lambda request: None)
    monkeypatch.setattr(ai, "get_provider_spec", lambda provider: object())
    probed = []
    async def probe(*args, **kwargs):
        probed.append(kwargs["endpoint_override"])
        return True
    class Adapter:
        async def discover_models(self):
            return [SimpleNamespace(model_id="local-model")]
    async def snapshot():
        return "snapshot"
    monkeypatch.setattr(ai.discovery, "probe_provider_reachable", probe)
    monkeypatch.setattr(ai, "build_provider", lambda *a, **k: Adapter())
    monkeypatch.setattr(ai, "set_ai_selection", lambda *a, **k: None)
    monkeypatch.setattr(ai, "build_snapshot", snapshot)
    payload = SimpleNamespace(
        provider_id="generic-openai", model_id="local-model",
        endpoint=endpoint,
    )
    result = asyncio.run(ai.ai_set_selection(SimpleNamespace(), payload))
    assert result == "snapshot"
    assert probed == [endpoint]
