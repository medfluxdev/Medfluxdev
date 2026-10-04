"""Portfolio reporting must not aggregate another organization's data."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import reports


@pytest.mark.parametrize("actor_kind", ["missing", "different"])
def test_portfolio_report_rejects_unmatched_actor_before_aggregates(monkeypatch, actor_kind):
    monkeypatch.setattr(reports.settings, "auth_enabled", True)
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(reports, "create_session", lambda: session)
    monkeypatch.setattr(reports, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    with pytest.raises(HTTPException) as exc:
        reports.portfolio_report(request, "clinic")
    assert exc.value.status_code == 404
    session.scalar.assert_not_called()
    session.execute.assert_not_called()
    session.close.assert_called_once()
