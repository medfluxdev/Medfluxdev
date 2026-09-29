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


@pytest.mark.asyncio
async def test_assistant_returns_503_when_local_model_unconfigured(monkeypatch):
    org = uuid4()
    actor = SimpleNamespace(organization_slug="hospital", organization_id=org, account_id=uuid4())
    account = SimpleNamespace(id=actor.account_id, is_active=True)
    monkeypatch.setattr(ai.settings, "auth_enabled", True)
    monkeypatch.setattr(ai, "create_session", lambda: SimpleNamespace(
        get=lambda cls, identifier: account, close=lambda: None))
    monkeypatch.setattr(ai, "actor_for_account", lambda session, user, slug: actor)
    monkeypatch.setattr(ai._ai_service, "_ensure_provider", lambda: None)
    with pytest.raises(HTTPException) as exc:
        await ai.ai_assistant(request(actor), "hospital", ai.AssistantRequest(message="Hallo"))
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_assistant_discards_answer_if_membership_revoked_during_generation(monkeypatch):
    org = uuid4()
    actor = SimpleNamespace(organization_slug="hospital", organization_id=org, account_id=uuid4())
    account = SimpleNamespace(id=actor.account_id)
    calls = []
    monkeypatch.setattr(ai.settings, "auth_enabled", True)
    monkeypatch.setattr(ai, "create_session", lambda: SimpleNamespace(
        get=lambda cls, identifier: account, close=lambda: None))
    def fresh_actor(session, user, slug):
        calls.append(True)
        return actor if len(calls) == 1 else None
    monkeypatch.setattr(ai, "actor_for_account", fresh_actor)
    monkeypatch.setattr(ai._ai_service, "_ensure_provider", lambda: object())
    async def answer(*args, **kwargs):
        return "Sensitive generated answer"
    monkeypatch.setattr(ai._ai_service, "generate_text", answer)
    with pytest.raises(HTTPException) as exc:
        await ai.ai_assistant(request(actor), "hospital", ai.AssistantRequest(message="Hallo"))
    assert exc.value.status_code == 404
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_assistant_rejects_deactivated_account_before_model(monkeypatch):
    org = uuid4()
    actor = SimpleNamespace(organization_slug="hospital", organization_id=org, account_id=uuid4())
    monkeypatch.setattr(ai.settings, "auth_enabled", True)
    monkeypatch.setattr(ai, "create_session", lambda: SimpleNamespace(
        get=lambda cls, identifier: SimpleNamespace(id=actor.account_id, is_active=False),
        close=lambda: None,
    ))
    monkeypatch.setattr(ai, "actor_for_account",
                        lambda *args: pytest.fail("Deactivated account reached membership lookup"))
    with pytest.raises(HTTPException) as exc:
        await ai.ai_assistant(request(actor), "hospital", ai.AssistantRequest(message="Hallo"))
    assert exc.value.status_code == 404


def test_assistant_rechecks_fresh_membership_scope(monkeypatch):
    org, contract_id = uuid4(), uuid4()
    actor = SimpleNamespace(account_id=uuid4(), organization_id=org,
                            role="viewer", is_developer=False)
    stale_hospital, newly_assigned_hospital = uuid4(), uuid4()
    monkeypatch.setattr(ai, "current_scope_context", lambda: SimpleNamespace(
        hospital_id=stale_hospital, department_id=None))
    membership = SimpleNamespace(hospital_id=newly_assigned_hospital, department_id=None)
    session = SimpleNamespace(scalar=lambda stmt: membership)
    seen = []
    def scoped(session, organization_id, hospital_id, department_id):
        seen.append(hospital_id)
        return {contract_id} if hospital_id == stale_hospital else set()
    monkeypatch.setattr(ai, "scoped_contract_ids", scoped)
    assert ai._assistant_visible_contracts(session, actor) == set()
    assert seen == [stale_hospital, newly_assigned_hospital]


def test_assistant_unassigned_membership_is_not_global(monkeypatch):
    actor = SimpleNamespace(account_id=uuid4(), organization_id=uuid4(),
                            role="viewer", is_developer=False)
    monkeypatch.setattr(ai, "current_scope_context", lambda: SimpleNamespace(
        hospital_id=None, department_id=None))
    monkeypatch.setattr(ai, "scoped_contract_ids",
                        lambda session, org, hospital, department: None if hospital is None else set())
    session = SimpleNamespace(scalar=lambda stmt: SimpleNamespace(hospital_id=None, department_id=None))
    assert ai._assistant_visible_contracts(session, actor) == set()


def test_source_region_denies_cross_organization_before_loading_document(monkeypatch):
    from app.api.routes import documents
    requested_org, actor_org = uuid4(), uuid4()
    request = SimpleNamespace(state=SimpleNamespace(actor=SimpleNamespace(
        organization_id=actor_org)))
    monkeypatch.setattr(documents.settings, "auth_enabled", True)
    # A real context manager is needed because the route uses with create_session().
    class Session:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def scalars(self, stmt):
            pytest.fail("Cross-organization request reached document query")
    monkeypatch.setattr(documents, "create_session", lambda: Session())
    monkeypatch.setattr(documents, "get_organization",
                        lambda session, slug: SimpleNamespace(id=requested_org))
    with pytest.raises(HTTPException) as exc:
        documents.document_source_region(str(uuid4()), request,
                                         organization_slug="other", snippet="valid text", page=1)
    assert exc.value.status_code == 404
