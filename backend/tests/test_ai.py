"""Tests für die lokale KI-Integration (Schritt 6).

Alle Ollama-HTTP-Antworten werden über httpx.MockTransport gemockt –
es wird KEINE echte Ollama-Installation vorausgesetzt.
"""

from typing import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai.exceptions import (
    AIEmptyResponseError,
    AIHTTPError,
    AIMalformedResponseError,
    AIModelMissingError,
    AITimeoutError,
    AIUnavailableError,
)
from app.ai.providers.ollama import OllamaProvider
from app.ai.schemas import AITestRequest
from app.ai.service import AIService
from app.api.routes import ai as ai_router
from app.core.config import Settings
from app.database.ai_selection import set_ai_selection, set_setting
from app.main import app

client = TestClient(app)
settings = Settings(_env_file=None)

MODEL = "qwen3:8b-test"
SYSTEM = "Systemhinweis."


@pytest.fixture(autouse=True)
def _explicit_model_selection():
    set_ai_selection("ollama", MODEL)
    yield
    for key in ("ai_provider", "ai_model", "ai_provider_endpoint"):
        set_setting(key, None)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _json(json: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=json)


def _provider(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaProvider:
    return OllamaProvider(settings, model_resolver=lambda: MODEL, client=_client(handler))


# ---------------------------------------------------------------- Konfiguration

def test_ai_provider_configuration():
    assert settings.ai_provider == "ollama"
    assert settings.ollama_model == ""
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ai_request_timeout_seconds > 0
    assert 0.0 <= settings.ai_temperature <= 1.0
    assert settings.ai_max_tokens > 0


def test_no_user_selection_means_ai_not_configured():
    for key in ("ai_provider", "ai_model", "ai_provider_endpoint"):
        set_setting(key, None)
    s = Settings(_env_file=None)
    svc = AIService(s)
    assert svc.configured is False


@pytest.mark.asyncio
async def test_generate_raises_without_configured_provider():
    for key in ("ai_provider", "ai_model", "ai_provider_endpoint"):
        set_setting(key, None)
    s = Settings(_env_file=None)
    svc = AIService(s)
    with pytest.raises(AIUnavailableError):
        await svc.generate("x")


@pytest.mark.asyncio
async def test_status_without_configured_provider():
    for key in ("ai_provider", "ai_model", "ai_provider_endpoint"):
        set_setting(key, None)
    s = Settings(_env_file=None)
    svc = AIService(s)
    st = await svc.status()
    assert st.available is False
    assert st.model_available is False
    assert st.provider is None
    assert st.model is None
    assert "Kein KI-Modell ausgewählt" in st.message


# ---------------------------------------------------------------- Ollama verfügbar

@pytest.mark.asyncio
async def test_ollama_available():
    p = _provider(lambda req: _json({"models": [{"name": MODEL}]}))
    st = await p.health_check()
    assert st.available is True
    assert st.model_available is True
    assert st.provider == "ollama"
    assert st.model == MODEL


# ---------------------------------------------------------------- Ollama NICHT verfügbar

@pytest.mark.asyncio
async def test_ollama_unavailable():
    def conn(req):
        raise httpx.ConnectError("refused", request=req)

    p = _provider(conn)
    st = await p.health_check()
    assert st.available is False
    assert st.model_available is False
    assert st.message == "Die lokale KI ist derzeit nicht verfügbar."


@pytest.mark.asyncio
async def test_ollama_timeout_on_health():
    def to(req):
        raise httpx.ConnectTimeout("timeout", request=req)

    p = _provider(to)
    st = await p.health_check()
    assert st.available is False
    assert "Zeitüberschreitung" in st.message


# ---------------------------------------------------------------- Modell verfügbar / fehlt

@pytest.mark.asyncio
async def test_model_available():
    p = _provider(lambda req: _json({"models": [{"name": MODEL}]}))
    info = await p.model_info()
    assert info.name == MODEL
    assert info.available is True


@pytest.mark.asyncio
async def test_model_missing():
    p = _provider(lambda req: _json({"models": [{"name": "llama3:8b"}]}))
    info = await p.model_info()
    assert info.available is False
    st = await p.health_check()
    assert st.available is True
    assert st.model_available is False
    assert st.message == f"Das lokale KI-Modell {MODEL} ist nicht installiert."


# ---------------------------------------------------------------- Generierung (Erfolg)

@pytest.mark.asyncio
async def test_successful_generation():
    p = _provider(lambda req: _json(
        {"message": {"role": "assistant", "content": "Antwort vom lokalen Modell."}}
    ))
    out = await p.generate("Eingabe", SYSTEM)
    assert out == "Antwort vom lokalen Modell."


@pytest.mark.asyncio
async def test_generation_sends_think_and_stream_opts():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = req.content
        return _json({"message": {"role": "assistant", "content": "ok"}})

    p = _provider(handler)
    await p.generate("Eingabe", SYSTEM)
    payload = captured["body"].decode("utf-8")
    import json as _jsonlib
    data = _jsonlib.loads(payload)
    assert data["think"] is False
    assert data["stream"] is False
    assert data["model"] == MODEL


@pytest.mark.asyncio
async def test_generation_forwards_explicit_num_gpu():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = req.content
        return _json({"message": {"role": "assistant", "content": "ok"}})

    gpu_settings = Settings(_env_file=None, ollama_num_gpu=999)
    p = OllamaProvider(
        gpu_settings,
        model_resolver=lambda: MODEL,
        client=_client(handler),
    )
    await p.generate("Eingabe", SYSTEM)

    import json as _jsonlib
    payload = _jsonlib.loads(captured["body"].decode("utf-8"))
    assert payload["options"]["num_gpu"] == 999


# ---------------------------------------------------------------- Generierung (Fehler)

@pytest.mark.asyncio
async def test_generation_timeout():
    def to(req):
        raise httpx.ConnectTimeout("timeout", request=req)

    p = _provider(to)
    with pytest.raises(AITimeoutError) as exc:
        await p.generate("Eingabe", SYSTEM)
    assert "Zeitüberschreitung" in exc.value.user_message


@pytest.mark.asyncio
async def test_generation_http_error():
    p = _provider(lambda req: _json({"oops": True}, status=500))
    with pytest.raises(AIHTTPError) as exc:
        await p.generate("Eingabe", SYSTEM)
    assert exc.value.status_code == 500
    assert "Fehler" in exc.value.user_message


@pytest.mark.asyncio
async def test_generation_model_missing():
    p = _provider(lambda req: _json({"error": "not found"}, status=404))
    with pytest.raises(AIModelMissingError) as exc:
        await p.generate("Eingabe", SYSTEM)
    assert "nicht installiert" in exc.value.user_message


@pytest.mark.asyncio
async def test_generation_malformed_response():
    p = _provider(lambda req: httpx.Response(200, text="kein-json"))
    with pytest.raises(AIMalformedResponseError) as exc:
        await p.generate("Eingabe", SYSTEM)
    assert "ungültige Antwort" in exc.value.user_message


@pytest.mark.asyncio
async def test_generation_empty_response():
    p = _provider(lambda req: _json({"message": {"role": "assistant", "content": "  "}}))
    with pytest.raises(AIEmptyResponseError) as exc:
        await p.generate("Eingabe", SYSTEM)
    assert "keine Antwort" in exc.value.user_message


@pytest.mark.asyncio
async def test_generation_unavailable():
    def conn(req):
        raise httpx.ConnectError("refused", request=req)

    p = _provider(conn)
    with pytest.raises(AIUnavailableError) as exc:
        await p.generate("Eingabe", SYSTEM)
    assert "nicht verfügbar" in exc.value.user_message


# ---------------------------------------------------------------- Service-Ebene (deutsche Meldungen)

@pytest.mark.asyncio
async def test_generate_test_success():
    p = _provider(lambda req: _json({"message": {"role": "assistant", "content": "Hallo."}}))
    svc = AIService(settings, client=_client(lambda req: _json(
        {"message": {"role": "assistant", "content": "Hallo."}}
    )))
    resp = await svc.generate_test("Test")
    assert resp.response == "Hallo."
    assert resp.error is None
    assert resp.provider == "ollama"


@pytest.mark.asyncio
async def test_generate_test_error_message():
    svc = AIService(settings, client=_client(lambda req: httpx.Response(500, text="x")))
    resp = await svc.generate_test("Test")
    assert resp.error is not None
    assert "Fehler" in resp.error
    assert resp.response is None


# ---------------------------------------------------------------- API-Endpunkte

def _install(handler: Callable[[httpx.Request], httpx.Response]) -> None:
    ai_router._ai_service = AIService(settings, client=_client(handler))


def _reset_service() -> None:
    ai_router._ai_service = AIService(settings)


def test_status_api_available():
    _install(lambda req: _json({"models": [{"name": MODEL}]}))
    r = client.get("/api/ai/status")
    body = r.json()
    assert r.status_code == 200
    assert body["provider"] == "ollama"
    assert body["available"] is True
    assert body["model_available"] is True


def test_status_api_unavailable():
    def conn(req):
        raise httpx.ConnectError("refused", request=req)

    _install(conn)
    r = client.get("/api/ai/status")
    body = r.json()
    assert r.status_code == 200
    assert body["available"] is False
    assert body["message"] == "Die lokale KI ist derzeit nicht verfügbar."


def test_test_api_success():
    _install(lambda req: _json({"message": {"role": "assistant", "content": "Komplette Antwort."}}))
    r = client.post("/api/ai/test", json=AITestRequest(text="Hallo lokal").model_dump())
    body = r.json()
    assert r.status_code == 200
    assert body["response"] == "Komplette Antwort."
    assert body["error"] is None


def test_test_api_error_returns_german_message():
    def conn(req):
        raise httpx.ConnectError("refused", request=req)

    _install(conn)
    r = client.post("/api/ai/test", json={"text": "Hallo"})
    body = r.json()
    assert r.status_code == 200
    assert body["response"] is None
    assert body["error"] == "Die lokale KI ist derzeit nicht verfügbar."


def test_test_api_rejects_empty_text():
    _install(lambda req: _json({"models": [{"name": MODEL}]}))
    r = client.post("/api/ai/test", json={"text": ""})
    assert r.status_code == 422


_reset_service()
