from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app
from app.api.routes import work_queue as routes
from app.work_queue.service import _references_as_dict


def test_patch_preflight_is_allowed():
    response = TestClient(app).options("/api/work-queue/" + str(uuid.uuid4()), headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "content-type"})
    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]


@pytest.mark.parametrize("bad_dto,commit_error,expected", [(True, False, 500), (False, True, 503), (False, False, 200)])
def test_patch_validates_before_commit(monkeypatch, bad_dto, commit_error, expected):
    session = MagicMock()
    org_id = uuid.uuid4()
    item_id = uuid.uuid4()
    contract_id = uuid.uuid4()
    row = SimpleNamespace(
        id=item_id,
        organization_id=org_id,
        contract_id=contract_id,
        status="open",
        item_type="manual_review",
    )
    session.get.return_value = row
    monkeypatch.setattr(routes, "create_session", lambda: session)
    monkeypatch.setattr(routes, "get_organization", lambda *a: SimpleNamespace(id=org_id))
    monkeypatch.setattr(routes, "scoped_contract_ids", lambda *a, **kw: None)
    mutation = MagicMock()
    monkeypatch.setattr(routes, "set_work_item_status", mutation)
    dto = {"id": str(item_id), "contract_id": str(contract_id), "item_type": "manual_review",
           "severity": "medium", "status": "acknowledged", "title_de": "Test"}
    monkeypatch.setattr(routes, "get_work_item_dto", lambda *a, **kw: {} if bad_dto else dto)
    if commit_error:
        session.commit.side_effect = SQLAlchemyError("private connection error")
    response = TestClient(app).patch(f"/api/work-queue/{item_id}?organization_slug=test",
                                    json={"status": "acknowledged"})
    assert response.status_code == expected
    assert mutation.call_args.kwargs["work_item_id"] == item_id
    if bad_dto:
        session.commit.assert_not_called()
    if expected != 200:
        session.rollback.assert_called_once()
        assert "private connection error" not in response.text


def test_legacy_references_keep_nonempty_content():
    assert _references_as_dict([{"source": 3}]) == {"legacy_refs": [{"source": 3}]}
    assert _references_as_dict([]) is None
