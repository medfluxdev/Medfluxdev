"""Billing endpoints reject a mismatched actor before contract data access."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import contract_billing


@pytest.mark.parametrize("actor_org", [None, uuid4()])
def test_billing_contract_loader_requires_matching_actor(monkeypatch, actor_org):
    monkeypatch.setattr(contract_billing.settings, "auth_enabled", True)
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


@pytest.mark.parametrize("same_extraction,owned_extraction", [
    (True, True), (False, True), (True, False),
])
def test_billing_accepted_result_requires_owned_accepted_extraction(
    monkeypatch, same_extraction, owned_extraction,
):
    """Only a run from this contract's accepted extraction can be returned."""
    org_id, contract_id, accepted_id = uuid4(), uuid4(), uuid4()
    run = SimpleNamespace(
        organization_id=org_id,
        extraction_id=accepted_id if same_extraction else uuid4(),
        result_snapshot={"snapshot": "opaque"},
    )
    session = MagicMock()
    session.get.return_value = run
    session.scalar.return_value = (
        SimpleNamespace(id=accepted_id) if owned_extraction else None
    )
    contract = SimpleNamespace(
        id=contract_id, accepted_calculation_run_id=uuid4(),
        accepted_extraction_id=accepted_id,
    )
    parsed = []
    monkeypatch.setattr(
        contract_billing.ContractCalculationResult, "model_validate",
        lambda snapshot: parsed.append(snapshot) or "accepted",
    )
    result = contract_billing._accepted_result(session, org_id, contract)
    if same_extraction and owned_extraction:
        assert result == "accepted"
        assert parsed == [run.result_snapshot]
    else:
        assert result is None
        assert parsed == []
        if not same_extraction:
            session.scalar.assert_not_called()
