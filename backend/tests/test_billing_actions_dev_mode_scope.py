"""Billing and human action transitions preserve explicit local dev mode only."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import contract_billing, intelligence_actions


@pytest.mark.parametrize("auth_enabled,actor_kind,denied", [
    (True, "missing", True),
    (True, "different", True),
    (False, "different", True),
    (False, "missing", False),
])
def test_billing_actor_mode_before_contract_lookup(monkeypatch, auth_enabled, actor_kind, denied):
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(contract_billing, "settings", SimpleNamespace(auth_enabled=auth_enabled))
    monkeypatch.setattr(contract_billing, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    if denied:
        with pytest.raises(HTTPException) as exc:
            contract_billing._load_contract(session, "clinic", uuid4(), request)
        assert exc.value.status_code == 404
        session.scalar.assert_not_called()
    else:
        session.scalar.return_value = None
        with pytest.raises(HTTPException) as exc:
            contract_billing._load_contract(session, "clinic", uuid4(), request)
        assert exc.value.detail == "Vertrag nicht gefunden."
        session.scalar.assert_called_once()


@pytest.mark.parametrize("auth_enabled,actor_kind,denied", [
    (True, "missing", True),
    (True, "different", True),
    (False, "different", True),
    (False, "missing", False),
])
def test_action_transition_actor_mode_before_proposal_lookup(monkeypatch, auth_enabled, actor_kind, denied):
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(intelligence_actions, "settings", SimpleNamespace(auth_enabled=auth_enabled))
    monkeypatch.setattr(intelligence_actions, "create_session", lambda: session)
    monkeypatch.setattr(intelligence_actions, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    actor = None if actor_kind == "missing" else SimpleNamespace(
        organization_id=uuid4(), is_developer=False, role="admin"
    )
    monkeypatch.setattr(intelligence_actions, "_actor_or_forbid", lambda *_: actor)
    session.get.return_value = None
    with pytest.raises(HTTPException) as exc:
        intelligence_actions.transition_action_proposal(
            request=SimpleNamespace(state=SimpleNamespace(actor=actor)),
            proposal_id=uuid4(), organization_slug="clinic",
            body=intelligence_actions.ActionTransition(status="approved"),
        )
    if denied:
        assert exc.value.detail == "Organisation nicht gefunden."
        session.get.assert_not_called()
    else:
        assert exc.value.detail == "Aktionsvorschlag nicht gefunden."
        session.get.assert_called_once()
    session.close.assert_called_once()
