"""Intelligence reads must reject absent and cross-organization actors."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import intelligence


@pytest.mark.parametrize("actor_kind", ["missing", "other"])
def test_intelligence_org_requires_matching_actor(monkeypatch, actor_kind):
    monkeypatch.setattr(intelligence.settings, "auth_enabled", True)
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(intelligence, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    with pytest.raises(HTTPException) as exc:
        intelligence._org(session, "clinic", request)
    assert exc.value.status_code == 404
