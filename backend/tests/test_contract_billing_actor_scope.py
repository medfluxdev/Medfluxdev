"""Billing endpoints reject a mismatched actor before contract data access."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import contract_billing


@pytest.mark.parametrize("actor_org", [None, uuid4()])
def test_billing_contract_loader_requires_matching_actor(monkeypatch, actor_org):
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(
        contract_billing, "get_organization",
        lambda *_: SimpleNamespace(id=org_id),
    )
    request = SimpleNamespace(
        state=SimpleNamespace(
            actor=None if actor_org is None else SimpleNamespace(organization_id=actor_org)
        )
    )
    with pytest.raises(HTTPException) as exc:
        contract_billing._load_contract(session, "clinic", uuid4(), request)
    assert exc.value.status_code == 404
    session.scalar.assert_not_called()
