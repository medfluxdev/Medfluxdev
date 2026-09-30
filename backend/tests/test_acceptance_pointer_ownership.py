"""Acceptance pointers must never cross organization or extraction boundaries."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.database.services import (
    PersistenceError, accept_calculation, accept_extraction, link_document,
)


def test_reject_foreign_extraction_without_mutating_pointer():
    org, foreign = uuid4(), uuid4()
    contract = SimpleNamespace(organization_id=org, accepted_extraction_id=None)
    extraction = SimpleNamespace(organization_id=foreign)
    session = MagicMock()
    session.get.side_effect = [contract, extraction]
    with pytest.raises(PersistenceError, match="organisation mismatch"):
        accept_extraction(session, contract_id=uuid4(), extraction_id=uuid4())
    assert contract.accepted_extraction_id is None
    session.flush.assert_not_called()


@pytest.mark.parametrize("foreign_org,stale_extraction", [
    (True, False), (False, True),
])
def test_reject_foreign_or_stale_calculation_without_mutating_pointer(
    foreign_org, stale_extraction,
):
    org, foreign, accepted_id, prior = uuid4(), uuid4(), uuid4(), uuid4()
    contract = SimpleNamespace(
        organization_id=org, accepted_extraction_id=accepted_id,
        accepted_calculation_run_id=prior,
    )
    run = SimpleNamespace(
        organization_id=foreign if foreign_org else org,
        extraction_id=uuid4() if stale_extraction else accepted_id,
    )
    session = MagicMock()
    session.get.side_effect = [contract, run]
    with pytest.raises(PersistenceError, match="does not belong"):
        accept_calculation(session, contract_id=uuid4(), calculation_run_id=uuid4())
    assert contract.accepted_calculation_run_id == prior
    session.flush.assert_not_called()


def test_accept_matching_calculation():
    org, accepted_id, run_id = uuid4(), uuid4(), uuid4()
    contract = SimpleNamespace(
        organization_id=org, accepted_extraction_id=accepted_id,
        accepted_calculation_run_id=None,
    )
    session = MagicMock()
    session.get.side_effect = [
        contract, SimpleNamespace(organization_id=org, extraction_id=accepted_id),
    ]
    assert accept_calculation(
        session, contract_id=uuid4(), calculation_run_id=run_id,
    ) is contract
    assert contract.accepted_calculation_run_id == run_id
    session.flush.assert_called_once()



def test_reject_cross_org_contract_document_link_before_query():
    org, foreign = uuid4(), uuid4()
    session = MagicMock()
    session.get.side_effect = [
        SimpleNamespace(organization_id=org),
        SimpleNamespace(organization_id=foreign),
    ]
    with pytest.raises(PersistenceError, match="organisation mismatch"):
        link_document(session, contract_id=uuid4(), document_version_id=uuid4())
    session.scalars.assert_not_called()
    session.add.assert_not_called()


def test_reject_missing_contract_document_link_target():
    session = MagicMock()
    session.get.side_effect = [None, SimpleNamespace(organization_id=uuid4())]
    with pytest.raises(PersistenceError, match="not found"):
        link_document(session, contract_id=uuid4(), document_version_id=uuid4())
    session.add.assert_not_called()



def test_accept_new_extraction_invalidates_old_accepted_calculation():
    org, old_id, new_id = uuid4(), uuid4(), uuid4()
    contract = SimpleNamespace(
        organization_id=org, accepted_extraction_id=old_id,
        accepted_calculation_run_id=uuid4(),
    )
    session = MagicMock()
    session.get.side_effect = [
        contract, SimpleNamespace(organization_id=org),
    ]
    assert accept_extraction(
        session, contract_id=uuid4(), extraction_id=new_id,
    ) is contract
    assert contract.accepted_extraction_id == new_id
    assert contract.accepted_calculation_run_id is None


def test_reaccept_same_extraction_preserves_accepted_calculation():
    org, accepted_id, calculation_id = uuid4(), uuid4(), uuid4()
    contract = SimpleNamespace(
        organization_id=org, accepted_extraction_id=accepted_id,
        accepted_calculation_run_id=calculation_id,
    )
    session = MagicMock()
    session.get.side_effect = [
        contract, SimpleNamespace(organization_id=org),
    ]
    accept_extraction(session, contract_id=uuid4(), extraction_id=accepted_id)
    assert contract.accepted_calculation_run_id == calculation_id
