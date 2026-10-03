"""Dashboard overview must reject cross-organization actors before aggregation."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import dashboard


@pytest.mark.parametrize("auth_enabled,actor_kind,denied", [
    (True, "missing", True),
    (True, "different", True),
    (False, "different", True),
    (False, "missing", False),
])
def test_dashboard_actor_scope_before_aggregation(monkeypatch, auth_enabled, actor_kind, denied):
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(dashboard, "settings", SimpleNamespace(auth_enabled=auth_enabled))
    monkeypatch.setattr(dashboard, "create_session", lambda: session)
    monkeypatch.setattr(dashboard, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    monkeypatch.setattr(dashboard, "current_scope_context", lambda: SimpleNamespace(hospital_id=None, department_id=None))
    monkeypatch.setattr(dashboard, "scoped_contract_ids", lambda *_: None)
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    if denied:
        with pytest.raises(HTTPException) as exc:
            dashboard.dashboard_overview(request, "clinic")
        assert exc.value.status_code == 404
        session.scalar.assert_not_called()
    else:
        # Reaching the dashboard builder verifies that the organization guard passed;
        # the model's complete shape is tested separately by its own suite.
        called = []
        def builder(*args, **kwargs):
            called.append(kwargs["organization_id"])
            raise RuntimeError("stop after guard")
        monkeypatch.setattr(dashboard, "build_dashboard_overview", builder)
        with pytest.raises(RuntimeError, match="stop after guard"):
            dashboard.dashboard_overview(request, "clinic")
        assert called == [org_id]
    session.close.assert_called_once()
