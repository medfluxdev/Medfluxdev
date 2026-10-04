"""Actor organization guards for intelligence analytics and action transitions."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import intelligence_actions, intelligence_analytics


@pytest.mark.parametrize("actor_org", [None, uuid4()])
def test_analytics_rejects_missing_or_cross_org_actor(monkeypatch, actor_org):
    monkeypatch.setattr(intelligence_analytics.settings, "auth_enabled", True)
    org_id = uuid4()
    monkeypatch.setattr(intelligence_analytics, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    request = SimpleNamespace(state=SimpleNamespace(
        actor=None if actor_org is None else SimpleNamespace(organization_id=actor_org)
    ))
    with pytest.raises(HTTPException) as exc:
        intelligence_analytics._org(MagicMock(), "clinic", request)
    assert exc.value.status_code == 404


def test_action_transition_rejects_cross_org_before_proposal_lookup(monkeypatch):
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(intelligence_actions, "create_session", lambda: session)
    monkeypatch.setattr(intelligence_actions, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    monkeypatch.setattr(intelligence_actions, "_actor_or_forbid", lambda *_: SimpleNamespace(
        organization_id=uuid4(), role="admin", is_developer=False
    ))
    with pytest.raises(HTTPException) as exc:
        intelligence_actions.transition_action_proposal(
            request=SimpleNamespace(state=SimpleNamespace()),
            proposal_id=uuid4(),
            organization_slug="clinic",
            body=intelligence_actions.ActionTransition(status="approved"),
        )
    assert exc.value.status_code == 404
    session.get.assert_not_called()
    session.close.assert_called_once()
