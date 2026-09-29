"""Security regressions for the read-only assistant boundary (no GPU or DB needed)."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import ai


def request(actor=None):
    return SimpleNamespace(state=SimpleNamespace(actor=actor))


@pytest.mark.asyncio
async def test_assistant_requires_auth_even_when_dev_auth_is_disabled(monkeypatch):
    monkeypatch.setattr(ai.settings, "auth_enabled", False)
    with pytest.raises(HTTPException) as exc:
        await ai.ai_assistant(request(), "hospital", ai.AssistantRequest(message="Hallo"))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_assistant_rejects_cross_org_before_db_access(monkeypatch):
    monkeypatch.setattr(ai.settings, "auth_enabled", True)
    monkeypatch.setattr(ai, "create_session", lambda: pytest.fail("DB opened for wrong org"))
    actor = SimpleNamespace(organization_slug="first", organization_id=uuid4(), account_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        await ai.ai_assistant(request(actor), "second", ai.AssistantRequest(message="Hallo"))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_assistant_rejects_revoked_membership_before_model(monkeypatch):
    monkeypatch.setattr(ai.settings, "auth_enabled", True)
    monkeypatch.setattr(ai, "create_session", lambda: SimpleNamespace(
        get=lambda cls, identifier: None, close=lambda: None))
    actor = SimpleNamespace(organization_slug="hospital", organization_id=uuid4(), account_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        await ai.ai_assistant(request(actor), "hospital", ai.AssistantRequest(message="Hallo"))
    assert exc.value.status_code == 404


def test_assistant_rejects_blank_or_oversized_prompts():
    from pydantic import ValidationError
    for text in ("", "x" * 2001):
        with pytest.raises(ValidationError):
            ai.AssistantRequest(message=text)
