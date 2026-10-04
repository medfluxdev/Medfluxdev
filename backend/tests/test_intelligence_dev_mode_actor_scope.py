"""Explicit auth-disabled local development must not bypass cross-org checks for known actors."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import intelligence, intelligence_analytics, reports


@pytest.mark.parametrize("module", [intelligence, intelligence_analytics])
@pytest.mark.parametrize("actor_kind", ["missing", "different"])
def test_intelligence_local_dev_actor_policy(monkeypatch, module, actor_kind):
    org_id = uuid4()
    monkeypatch.setattr(module, "settings", SimpleNamespace(auth_enabled=False))
    monkeypatch.setattr(module, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    if actor is None:
        assert module._org(MagicMock(), "clinic", request).id == org_id
    else:
        with pytest.raises(HTTPException) as exc:
            module._org(MagicMock(), "clinic", request)
        assert exc.value.status_code == 404


@pytest.mark.parametrize("actor_kind", ["missing", "different"])
def test_reports_local_dev_actor_policy(monkeypatch, actor_kind):
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(reports, "settings", SimpleNamespace(auth_enabled=False))
    monkeypatch.setattr(reports, "create_session", lambda: session)
    monkeypatch.setattr(reports, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    monkeypatch.setattr(reports, "current_scope_context", lambda: SimpleNamespace(hospital_id=None, department_id=None))
    monkeypatch.setattr(reports, "scoped_contract_ids", lambda *_: None)
    session.execute.return_value.all.return_value = []
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    if actor is None:
        result = reports.portfolio_report(request, "clinic")
        assert "contracts" in result
    else:
        with pytest.raises(HTTPException) as exc:
            reports.portfolio_report(request, "clinic")
        assert exc.value.status_code == 404
        session.scalar.assert_not_called()
    session.close.assert_called_once()
