"""Notification feed actor isolation and intentional local development access."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import notifications


@pytest.mark.parametrize("auth_enabled,actor_kind,denied", [
    (True, "missing", True),
    (True, "different", True),
    (False, "different", True),
    (False, "missing", False),
])
def test_notification_feed_actor_scope_before_queries(monkeypatch, auth_enabled, actor_kind, denied):
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(notifications, "settings", SimpleNamespace(auth_enabled=auth_enabled))
    monkeypatch.setattr(notifications, "create_session", lambda: session)
    monkeypatch.setattr(notifications, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    monkeypatch.setattr(notifications, "current_scope_context", lambda: SimpleNamespace(hospital_id=None, department_id=None))
    monkeypatch.setattr(notifications, "scoped_contract_ids", lambda *_: None)
    session.scalars.return_value.all.return_value = []
    session.scalar.return_value = 0
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    if denied:
        with pytest.raises(HTTPException) as exc:
            notifications.notification_feed(request, "clinic", limit=10)
        assert exc.value.status_code == 404
        session.scalars.assert_not_called()
    else:
        assert notifications.notification_feed(request, "clinic", limit=10) == {"items": [], "total": 0}
    session.close.assert_called_once()
