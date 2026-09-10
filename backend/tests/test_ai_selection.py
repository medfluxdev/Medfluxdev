"""Fokussierte Tests: Auswahl-Persistenz und kanonischer Zustand (Schritt 6B).

Persistenz läuft gegen das isolierte Test-Schema (conftest). Provider-/Modell-
Erkennung findet hier nicht statt (keine echte Inferenz, keine realen
Endpoints); die Auswahl-Route wird über Patches geführt (Stub-Adapter ohne
`generate`).
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.ai.schemas import (
    AISnapshot,
    ModelDescriptor,
    ProviderInfo,
    SelectionInfo,
)
from app.ai.selection import build_selection
from app.ai.service import AIService
from app.api.routes import ai as ai_router
from app.core.config import Settings
from app.database.ai_selection import (
    get_ai_selection,
    set_ai_selection,
    set_setting,
)


def _pg_available(engine) -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def engine():
    from app.core.config import settings as live_settings

    eng = create_engine(live_settings.database_url, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _require_pg(engine):
    if not _pg_available(engine):
        pytest.skip("PostgreSQL nicht erreichbar – AI-Selektion-Tests übersprungen")
    yield


@pytest.fixture(autouse=True)
def _clean(engine):
    yield
    for key in ("ai_provider", "ai_model", "ai_provider_endpoint"):
        set_setting(key, None)


def _settings(**overrides) -> Settings:
    base = {}
    base.update(overrides)
    return Settings(_env_file=None, **base)


def _provider(provider_id: str, models: list[str], reachable: bool = True) -> ProviderInfo:
    return ProviderInfo(
        provider_id=provider_id,
        display_name=provider_id,
        kind="native" if provider_id in ("ollama",) else "openai-compatible",
        endpoint="http://localhost:1",
        reachable=reachable,
        detection="native" if reachable else None,
        models=[ModelDescriptor(provider_id=provider_id, model_id=m) for m in models],
    )


# ---------------------------------------------------------------- Persistenz

def test_selection_roundtrip():
    set_ai_selection("ollama", "qwen3-vl:8b-instruct")
    provider, model, endpoint = get_ai_selection()
    assert (provider, model) == ("ollama", "qwen3-vl:8b-instruct")
    assert endpoint is None


def test_selection_endpoint_persisted_and_cleared():
    set_ai_selection("generic-openai", "m", endpoint="http://127.0.0.1:1234")
    _provider, _model, endpoint = get_ai_selection()
    assert endpoint == "http://127.0.0.1:1234"
    set_ai_selection("ollama", "qwen3:8b")
    _provider2, _model2, endpoint2 = get_ai_selection()
    assert endpoint2 is None


def test_resolve_defaults_to_environment_when_unset():
    settings = _settings()
    from app.ai.settings_service import (
        resolve_model_id,
        resolve_provider_id,
        selection_source,
    )

    assert resolve_provider_id(settings) == settings.ai_provider
    assert resolve_model_id(settings) == settings.ollama_model
    assert selection_source(settings) == "env"


def test_resolve_prefers_persisted_selection():
    settings = _settings()
    set_ai_selection("lmstudio", "anderes-modell")
    from app.ai.settings_service import (
        resolve_model_id,
        resolve_provider_id,
        selection_source,
    )

    assert resolve_provider_id(settings) == "lmstudio"
    assert resolve_model_id(settings) == "anderes-modell"
    assert selection_source(settings) == "db"


def test_services_resolve_persisted_active_ids():
    settings = _settings()
    set_ai_selection("lmstudio", "modell-x")
    svc = AIService(settings)
    assert svc.active_provider_id() == "lmstudio"
    assert svc.active_model_id() == "modell-x"


def test_db_failure_falls_back_to_environment(monkeypatch):
    settings = _settings()

    def boom():
        raise RuntimeError("DB weg")

    monkeypatch.setattr("app.database.ai_selection.get_ai_selection", boom)
    from app.ai.settings_service import resolve_model_id, resolve_provider_id

    assert resolve_provider_id(settings) == settings.ai_provider
    assert resolve_model_id(settings) == settings.ollama_model


# ---------------------------------------------------------------- Auswahl-Zustand

def test_selection_ready_env_source():
    settings = _settings()
    providers = [_provider("ollama", [settings.ollama_model])]
    sel = build_selection(settings, providers)
    assert sel.state == "ready"
    assert sel.provider_reachable is True
    assert sel.model_available is True
    assert sel.source == "env"
    assert "Bereit" in sel.message_de


def test_saved_unreachable_provider_no_silent_fallback():
    settings = _settings()
    set_ai_selection("ollama", settings.ollama_model)
    providers = [
        _provider("ollama", [], reachable=False),
        _provider("lmstudio", ["anderes"], reachable=True),
    ]
    sel = build_selection(settings, providers)
    assert sel.state == "unavailable"
    assert sel.provider_reachable is False
    assert "nicht erreichbar" in sel.message_de
    # Es wird NICHT still auf lmstudio umgeschaltet:
    from app.ai.settings_service import resolve_provider_id

    assert resolve_provider_id(settings) == "ollama"


def test_saved_model_missing_flagged_not_silent():
    settings = _settings()
    set_ai_selection("ollama", "geister-modell")
    providers = [_provider("ollama", [settings.ollama_model], reachable=True)]
    sel = build_selection(settings, providers)
    assert sel.state == "unavailable"
    assert sel.provider_reachable is True
    assert sel.model_available is False
    assert "nicht (mehr) installiert" in sel.message_de
    from app.ai.settings_service import resolve_model_id

    assert resolve_model_id(settings) == "geister-modell"


def test_saved_unknown_provider_flagged():
    settings = _settings()
    set_ai_selection("bogus", "x")
    sel = build_selection(settings, [_provider("ollama", ["qwen3:8b"])])
    assert sel.state == "unavailable"
    assert "nicht verfügbar" in sel.message_de
    from app.ai.settings_service import resolve_provider_id

    assert resolve_provider_id(settings) == "bogus"


def test_generic_selection_readiness_uses_endpoint():
    settings = _settings()
    endpoint = "http://127.0.0.1:1234"
    set_ai_selection("generic-openai", "m", endpoint=endpoint)
    providers = [
        ProviderInfo(
            provider_id="generic-openai",
            display_name="Kompatibler lokaler Anbieter (OpenAI)",
            kind="openai-compatible",
            endpoint=endpoint,
            reachable=True,
            detection="openai-compatible",
            models=[ModelDescriptor(provider_id="generic-openai", model_id="m")],
        ),
        _provider("ollama", ["qwen3:8b"]),
    ]
    sel = build_selection(settings, providers)
    assert sel.state == "ready"
    assert sel.source == "db"


# ---------------------------------------------------------- Kanonischer Zustand

@pytest.mark.asyncio
async def test_status_and_selection_state_agree():
    settings = _settings()
    mock = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200, json={"models": [{"name": settings.ollama_model}]}
            )
        )
    )
    svc = AIService(settings, client=mock)
    st = await svc.status()
    providers = [_provider("ollama", [settings.ollama_model])]
    sel = build_selection(settings, providers)
    assert st.available is True
    assert st.model_available is True
    assert sel.state == "ready"
    assert st.provider == sel.provider_id
    assert st.model == sel.model_id


# ---------------------------------------------------------------- Auswahl-Route

class _StubAdapter:
    """Wie ein Provider, ABER ohne generate – Inferenz kann so nie angetriggert werden."""

    def __init__(self, models: list[str]):
        self._models = models

    async def discover_models(self) -> list[ModelDescriptor]:
        return [ModelDescriptor(provider_id="ollama", model_id=m) for m in self._models]


def test_put_selection_persists_and_returns_snapshot(monkeypatch, engine):
    from app.main import app

    tc = TestClient(app)
    fake_snapshot = AISnapshot(
        selection=SelectionInfo(
            provider_id="ollama",
            model_id="qwen3:8b",
            source="db",
            state="ready",
            provider_reachable=True,
            model_available=True,
            message_de="Bereit: 'Ollama' mit Modell 'qwen3:8b'.",
        ),
        providers=[_provider("ollama", ["qwen3:8b"])],
        configured_default_provider="ollama",
        configured_default_model="qwen3:8b",
        application_version="0.1.0",
    )

    async def _fake_probe(*args, **kwargs):
        return True

    async def _fake_build_snapshot():
        return fake_snapshot

    monkeypatch.setattr(ai_router.discovery, "probe_provider_reachable", _fake_probe)
    monkeypatch.setattr(
        ai_router,
        "build_provider",
        lambda *a, **k: _StubAdapter(["qwen3:8b"]),
    )
    monkeypatch.setattr(ai_router, "build_snapshot", _fake_build_snapshot)

    r = tc.put("/api/ai/selection", json={"provider_id": "ollama", "model_id": "qwen3:8b"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["selection"]["state"] == "ready"
    assert body["selection"]["source"] == "db"
    provider, model, _endpoint = get_ai_selection()
    assert (provider, model) == ("ollama", "qwen3:8b")


def test_put_selection_rejects_unknown_provider(monkeypatch, engine):
    from app.main import app

    tc = TestClient(app)
    r = tc.put("/api/ai/selection", json={"provider_id": "spaceship", "model_id": "x"})
    assert r.status_code == 400
    assert "wird nicht unterstützt" in r.json()["detail"]


def test_put_selection_rejects_unreachable_provider(monkeypatch, engine):
    from app.main import app

    tc = TestClient(app)

    async def _fake_probe(*args, **kwargs):
        return False

    monkeypatch.setattr(ai_router.discovery, "probe_provider_reachable", _fake_probe)
    r = tc.put("/api/ai/selection", json={"provider_id": "ollama", "model_id": "qwen3:8b"})
    assert r.status_code == 400
    assert "nicht erreichbar" in r.json()["detail"]
    # Nichts persistiert:
    provider, model, _endpoint = get_ai_selection()
    assert (provider, model) == (None, None)


def test_put_selection_rejects_model_not_listed(monkeypatch, engine):
    from app.main import app

    tc = TestClient(app)

    async def _fake_probe(*args, **kwargs):
        return True

    monkeypatch.setattr(ai_router.discovery, "probe_provider_reachable", _fake_probe)
    monkeypatch.setattr(
        ai_router,
        "build_provider",
        lambda *a, **k: _StubAdapter(["qwen3:8b"]),
    )
    r = tc.put("/api/ai/selection", json={"provider_id": "ollama", "model_id": "gibtsnicht"})
    assert r.status_code == 400
    assert "nicht (mehr) verfügbar" in r.json()["detail"]