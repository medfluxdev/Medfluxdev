"""Lifecycle organization access respects authenticated isolation and explicit local dev mode."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import lifecycle


@pytest.mark.parametrize("auth_enabled,actor_kind,expected", [
    (True, "missing", 404),
    (True, "different", 404),
    (False, "different", 404),
    (False, "missing", None),
])
def test_lifecycle_org_actor_scope(monkeypatch, auth_enabled, actor_kind, expected):
    org_id = uuid4()
    monkeypatch.setattr(lifecycle, "settings", SimpleNamespace(auth_enabled=auth_enabled))
    monkeypatch.setattr(lifecycle, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    if expected:
        with pytest.raises(HTTPException) as exc:
            lifecycle._org(MagicMock(), "clinic", request)
        assert exc.value.status_code == expected
    else:
        assert lifecycle._org(MagicMock(), "clinic", request).id == org_id


@pytest.mark.parametrize("is_archived,lifecycle_state,allowed", [
    (False, "active", True),
    (True, "active", False),
    (False, "deleted", False),
])
def test_lifecycle_contract_rejects_archived_and_inactive(
    monkeypatch, is_archived, lifecycle_state, allowed,
):
    org_id, contract_id = uuid4(), uuid4()
    contract = SimpleNamespace(
        organization_id=org_id, lifecycle_state=lifecycle_state,
        is_archived=is_archived,
    )
    session = MagicMock()
    session.get.return_value = contract
    monkeypatch.setattr(
        lifecycle, "current_scope_context",
        lambda: SimpleNamespace(hospital_id=None, department_id=None),
    )
    monkeypatch.setattr(lifecycle, "scoped_contract_ids", lambda *_: None)
    if allowed:
        row, _ = lifecycle._require_contract(session, org_id, contract_id)
        assert row is contract
    else:
        with pytest.raises(HTTPException) as exc:
            lifecycle._require_contract(session, org_id, contract_id)
        assert exc.value.status_code == 404
