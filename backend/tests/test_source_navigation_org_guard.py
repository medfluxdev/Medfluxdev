"""Source navigation must not follow a cross-organization extraction pointer."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.database.services import resolve_source_navigation


def test_navigation_rejects_cross_org_extraction_before_document_lookup():
    org_id, foreign_org, contract_id, extraction_id = (
        uuid4(), uuid4(), uuid4(), uuid4()
    )
    contract = SimpleNamespace(
        organization_id=org_id, accepted_extraction_id=extraction_id,
    )
    evidence = SimpleNamespace(extraction_id=extraction_id)
    foreign_extraction = SimpleNamespace(
        organization_id=foreign_org, document_version_id=uuid4(),
    )
    session = MagicMock()
    session.get.side_effect = [contract, foreign_extraction]
    session.scalars.return_value.first.return_value = evidence

    assert resolve_source_navigation(
        session, contract_id=contract_id, field_ref="supplier.name",
    ) is None
    assert session.get.call_count == 2



def test_navigation_rejects_foreign_document_version():
    org_id, foreign_org, extraction_id = uuid4(), uuid4(), uuid4()
    session = MagicMock()
    session.scalars.return_value.first.return_value = SimpleNamespace(extraction_id=extraction_id)
    session.get.side_effect = [
        SimpleNamespace(organization_id=org_id, accepted_extraction_id=extraction_id),
        SimpleNamespace(organization_id=org_id, document_version_id=uuid4()),
        SimpleNamespace(organization_id=foreign_org, document_file_id=uuid4()),
    ]
    assert resolve_source_navigation(
        session, contract_id=uuid4(), field_ref="supplier.name",
    ) is None
    assert session.get.call_count == 3


def test_navigation_rejects_foreign_document_file():
    org_id, foreign_org, extraction_id = uuid4(), uuid4(), uuid4()
    session = MagicMock()
    session.scalars.return_value.first.return_value = SimpleNamespace(extraction_id=extraction_id)
    session.get.side_effect = [
        SimpleNamespace(organization_id=org_id, accepted_extraction_id=extraction_id),
        SimpleNamespace(organization_id=org_id, document_version_id=uuid4()),
        SimpleNamespace(organization_id=org_id, document_file_id=uuid4()),
        SimpleNamespace(organization_id=foreign_org),
    ]
    assert resolve_source_navigation(
        session, contract_id=uuid4(), field_ref="supplier.name",
    ) is None
    assert session.get.call_count == 4
