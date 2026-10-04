"""Collaboration reads require actor organization in authenticated mode."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import work_queue_collaboration as routes


@pytest.mark.parametrize("auth_enabled,actor_kind,denied", [
    (True, "missing", True),
    (True, "different", True),
    (False, "different", True),
    (False, "missing", False),
])
def test_collaboration_read_actor_guard(monkeypatch, auth_enabled, actor_kind, denied):
    org_id, work_id = uuid4(), uuid4()
    session = MagicMock()
    monkeypatch.setattr(routes, "settings", SimpleNamespace(auth_enabled=auth_enabled))
    monkeypatch.setattr(routes, "create_session", lambda: session)
    monkeypatch.setattr(routes, "_context", lambda *_: (
        SimpleNamespace(id=org_id), SimpleNamespace(id=work_id), SimpleNamespace()
    ))
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    if denied:
        with pytest.raises(HTTPException) as exc:
            routes.get_collaboration(request, work_id, "clinic")
        assert exc.value.status_code == 404
        session.scalars.assert_not_called()
    else:
        session.scalars.return_value.first.return_value = None
        session.scalars.return_value.all.return_value = []
        assert routes.get_collaboration(request, work_id, "clinic")["comments"] == []
    session.close.assert_called_once()
