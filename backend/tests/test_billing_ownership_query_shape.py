"""Compile the real ORM billing ownership query, not only mocked results."""

from uuid import uuid4

from sqlalchemy.dialects import postgresql
from unittest.mock import MagicMock

from app.api.routes.contract_billing import _accepted_result
from app.database.models import Contract
from app.database.models.contract import ContractDocument
from app.database.models.extraction import ContractExtraction


def test_billing_accepted_result_uses_mapped_document_ownership_query():
    org_id, contract_id, extraction_id = uuid4(), uuid4(), uuid4()
    contract = Contract(
        id=contract_id, organization_id=org_id,
        accepted_calculation_run_id=uuid4(),
        accepted_extraction_id=extraction_id,
    )
    session = MagicMock()
    session.get.return_value = type("Run", (), dict(
        organization_id=org_id, extraction_id=extraction_id,
        result_snapshot={"opaque": True},
    ))()
    def check_query(query):
        compiled = str(query.compile(dialect=postgresql.dialect()))
        assert ContractExtraction.__tablename__ in compiled
        assert ContractDocument.__tablename__ in compiled
        assert "document_version_id" in compiled
        return None
    session.scalar.side_effect = check_query
    assert _accepted_result(session, org_id, contract) is None
