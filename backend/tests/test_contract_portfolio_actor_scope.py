"""Contract portfolio route rejects mismatched organization before querying search."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import contracts


def test_portfolio_list_rejects_other_organization(monkeypatch):
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(contracts, "create_session", lambda: session)
    monkeypatch.setattr(contracts, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    search = MagicMock()
    monkeypatch.setattr(contracts, "build_contract_search", search)
    request = SimpleNamespace(state=SimpleNamespace(actor=SimpleNamespace(organization_id=uuid4())))
    with pytest.raises(HTTPException) as exc:
        contracts.contract_list(
            request=request, organization_slug="other",
            status=[], risk=[], warning_type=[], page_size=25,
        )
    assert exc.value.status_code == 404
    search.assert_not_called()
    session.close.assert_called_once()
