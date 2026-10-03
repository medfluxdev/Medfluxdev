"""Acceptance pointers must never cross organization or extraction boundaries."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.database.services import (
    PersistenceError, accept_calculation, accept_extraction, link_document, save_extraction, save_document_file, create_document_version, save_calculation,
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



def test_save_extraction_rejects_cross_org_document_before_insert():
    org, foreign = uuid4(), uuid4()
    session = MagicMock()
    session.get.return_value = SimpleNamespace(organization_id=foreign)
    with pytest.raises(PersistenceError, match="organisation mismatch"):
        save_extraction(
            session, organization_id=org, document_version_id=uuid4(),
            snapshot={}, evidence=[],
        )
    session.add.assert_not_called()
    session.flush.assert_not_called()



def test_document_hash_cannot_reuse_foreign_org_file():
    org, foreign = uuid4(), uuid4()
    session = MagicMock()
    existing = SimpleNamespace(organization_id=foreign, duplicate_detected=False)
    session.scalars.return_value.first.return_value = existing
    with pytest.raises(PersistenceError, match="another organisation"):
        save_document_file(
            session, organization_id=org, sha256="a" * 64,
            original_filename="x.pdf", stored_filename="x.pdf",
            file_extension=".pdf", file_size_bytes=1, storage_key="x.pdf",
        )
    assert existing.duplicate_detected is False
    session.add.assert_not_called()


def test_document_version_cannot_reuse_foreign_file_hash():
    org = uuid4()
    session = MagicMock()
    session.scalars.return_value.first.return_value = SimpleNamespace(
        organization_id=org, document_file_id=uuid4(),
    )
    with pytest.raises(PersistenceError, match="another owner or file"):
        create_document_version(
            session, organization_id=org, document_file_id=uuid4(),
            version_no=1, sha256="b" * 64, storage_key="v1.pdf",
        )
    session.add.assert_not_called()


def test_new_document_version_requires_owned_file():
    org = uuid4()
    session = MagicMock()
    session.scalars.return_value.first.return_value = None
    session.get.return_value = SimpleNamespace(organization_id=uuid4())
    with pytest.raises(PersistenceError, match="organisation mismatch"):
        create_document_version(
            session, organization_id=org, document_file_id=uuid4(),
            version_no=1, sha256="b" * 64, storage_key="v1.pdf",
        )
    session.add.assert_not_called()


def test_calculation_requires_same_org_extraction():
    org = uuid4()
    session = MagicMock()
    session.get.return_value = SimpleNamespace(organization_id=uuid4())
    from datetime import date
    with pytest.raises(PersistenceError, match="organisation mismatch"):
        save_calculation(
            session, organization_id=org, extraction_id=uuid4(),
            as_of_date=date(2026, 9, 30), result_snapshot={},
        )
    session.add.assert_not_called()
