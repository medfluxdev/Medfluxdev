"""DB-free authorization and input guards for work item collaboration."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import work_queue_collaboration as routes


def _setup(monkeypatch):
    org_id, work_id, contract_id = uuid4(), uuid4(), uuid4()
    session = MagicMock()
    org = SimpleNamespace(id=org_id)
    work = SimpleNamespace(id=work_id, organization_id=org_id, contract_id=contract_id)
    monkeypatch.setattr(routes, "create_session", lambda: session)
    monkeypatch.setattr(routes, "_context", lambda *args: (org, work, SimpleNamespace(hospital_id=None, department_id=None)))
    return session, org_id, work_id


def test_collaboration_write_rejects_actor_from_other_organization(monkeypatch):
    session, org_id, work_id = _setup(monkeypatch)
    actor = SimpleNamespace(organization_id=uuid4())
    with pytest.raises(HTTPException) as error:
        routes.update_collaboration(SimpleNamespace(state=SimpleNamespace(actor=actor)), work_id, "hospital", routes.CollaborationUpdate())
    assert error.value.status_code == 403
    session.commit.assert_not_called()
    session.close.assert_called_once()


def test_comment_write_rejects_actor_from_other_organization(monkeypatch):
    session, org_id, work_id = _setup(monkeypatch)
    actor = SimpleNamespace(organization_id=uuid4())
    with pytest.raises(HTTPException) as error:
        routes.add_comment(SimpleNamespace(state=SimpleNamespace(actor=actor)), work_id, "hospital", routes.CommentCreate(body="hello"))
    assert error.value.status_code == 403
    session.commit.assert_not_called()
    session.close.assert_called_once()


def test_comment_write_rejects_whitespace_only(monkeypatch):
    session, org_id, work_id = _setup(monkeypatch)
    actor = SimpleNamespace(organization_id=org_id)
    with pytest.raises(HTTPException) as error:
        routes.add_comment(SimpleNamespace(state=SimpleNamespace(actor=actor)), work_id, "hospital", routes.CommentCreate(body="     "))
    assert error.value.status_code == 422
    session.commit.assert_not_called()
    session.close.assert_called_once()
