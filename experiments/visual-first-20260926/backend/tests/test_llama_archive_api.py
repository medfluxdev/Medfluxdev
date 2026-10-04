import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from app.api.routes import contracts
from app.core.config import settings

ORG=uuid.uuid4()
DOC=uuid.uuid4()
VERSION=uuid.uuid4()
class FakeSession:
    def __init__(self):
        self.closed=False
        self.query_count=0
    def execute(self, query):
        self.query_count+=1
        class Result:
            def all(self):
                return [SimpleNamespace(
                    contract_id=DOC,revision=VERSION,source_sha256="c"*64,
                    page=1,field="equipment",source_quote="OPTIS Mobile Next")]
        return Result()
    def close(self):
        self.closed=True

def test_archive_api_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings,"llama_archive_experiment_enabled",False)
    monkeypatch.setattr(contracts,"create_session",lambda: (_ for _ in ()).throw(
        AssertionError("Off mode must not open a database session")))
    with pytest.raises(HTTPException) as err:
        contracts.archive_evidence_search(organization_slug="hospital",q="OPTIS",limit=10)
    assert err.value.status_code==404

def test_acl_scope_and_actual_llamaindex(monkeypatch):
    monkeypatch.setattr(settings,"llama_archive_experiment_enabled",True)
    monkeypatch.setattr(settings,"app_env","test")
    session=FakeSession()
    monkeypatch.setattr(contracts,"create_session",lambda: session)
    monkeypatch.setattr(contracts,"get_organization",lambda sess, slug: SimpleNamespace(id=ORG))
    monkeypatch.setattr(contracts,"current_scope_context",lambda: SimpleNamespace(
        hospital_id=None,department_id=None))
    monkeypatch.setattr(contracts,"scoped_contract_ids",lambda *args: {DOC})
    result=contracts.archive_evidence_search(organization_slug="hospital",q="OPTIS",limit=10)
    assert result["experimental"] is True and result["indexed_sources"]==1
    assert result["items"][0]["document_id"]==str(DOC)
    assert result["items"][0]["source_sha256"]=="c"*64
    assert session.closed is True

def test_empty_acl_never_queries_data(monkeypatch):
    monkeypatch.setattr(settings,"llama_archive_experiment_enabled",True)
    monkeypatch.setattr(settings,"app_env","test")
    session=FakeSession()
    monkeypatch.setattr(contracts,"create_session",lambda: session)
    monkeypatch.setattr(contracts,"get_organization",lambda sess, slug: SimpleNamespace(id=ORG))
    monkeypatch.setattr(contracts,"current_scope_context",lambda: SimpleNamespace(
        hospital_id=None,department_id=None))
    monkeypatch.setattr(contracts,"scoped_contract_ids",lambda *args: set())
    result=contracts.archive_evidence_search(organization_slug="hospital",q="OPTIS",limit=10)
    assert result["items"]==[]
    assert session.query_count==0
    assert session.closed is True

def test_route_registered():
    from app.main import app
    assert any(route.path=="/api/contracts/archive-evidence/search" for route in app.routes)