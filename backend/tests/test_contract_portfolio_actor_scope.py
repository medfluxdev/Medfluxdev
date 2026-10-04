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
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    request = SimpleNamespace(state=SimpleNamespace(actor=SimpleNamespace(organization_id=uuid4())))
    with pytest.raises(HTTPException) as exc:
        contracts.contract_list(
            request=request, organization_slug="other",
            status=[], business_status=[], risk=[], warning_type=[], page_size=25,
            sort="operational", direction="asc",
        )
    assert exc.value.status_code == 404
    search.assert_not_called()
    session.close.assert_called_once()


@pytest.mark.parametrize(
    "auth_enabled,insecure_dev,app_env,actor_kind,expected_mismatch",
    [
        (True, False, "production", "missing", True),
        (True, False, "production", "foreign", True),
        (True, False, "production", "matching", False),
        (False, True, "development", "missing", False),
        (False, True, "test", "missing", False),
        (False, False, "development", "missing", True),
        (False, True, "production", "missing", True),
        (False, True, "pilot", "missing", True),
    ],
)
def test_portfolio_org_guard_only_bypasses_actor_in_explicit_local_dev(
    monkeypatch, auth_enabled, insecure_dev, app_env, actor_kind, expected_mismatch,
):
    org_id = uuid4()
    actor = (
        None if actor_kind == "missing"
        else SimpleNamespace(organization_id=org_id if actor_kind == "matching" else uuid4())
    )
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    monkeypatch.setattr(contracts.settings, "auth_enabled", auth_enabled)
    monkeypatch.setattr(contracts.settings, "medflux_insecure_dev", insecure_dev)
    monkeypatch.setattr(contracts.settings, "app_env", app_env)
    assert contracts.actor_org_mismatch(request, org_id) is expected_mismatch


def test_portfolio_route_declares_fastapi_request_parameter():
    import inspect
    from typing import get_type_hints
    from fastapi import Request

    signature = inspect.signature(contracts.contract_list)
    assert "request" in signature.parameters
    assert get_type_hints(contracts.contract_list)["request"] is Request
