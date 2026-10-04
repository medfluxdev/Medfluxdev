import uuid
from types import SimpleNamespace
import pytest
from sqlalchemy.dialects import postgresql
from app.contracts.search.llama_adapter import (
    verified_evidence_query, collect_indexable_evidence,
    build_readonly_archive, search_readonly_archive,
)

ORG=uuid.uuid4()
C1=uuid.uuid4()
class FakeSession:
    def __init__(self, rows):
        self.rows=rows
        self.calls=0
    def execute(self, stmt):
        self.calls+=1
        class R:
            def __init__(self, rows): self.rows=rows
            def all(self): return self.rows
        return R(self.rows)
class FakeArchive:
    _stores={}
    def rebuild(self, tenant, records):
        self.tenant,self.records=tenant,records
        return len(records)
    def search(self, **kwargs):
        return kwargs

def test_query_requires_org_and_contract_acl():
    with pytest.raises(ValueError):
        verified_evidence_query(organization_id=None,allowed_contract_ids=[C1])
    assert verified_evidence_query(organization_id=ORG,allowed_contract_ids=[]) is None
    sql=str(verified_evidence_query(organization_id=ORG,allowed_contract_ids=[C1]).compile(
        dialect=postgresql.dialect()))
    assert "accepted_extraction_id" in sql
    assert sql.count("organization_id") >= 4
    assert "requires_review" in sql
    assert "document_version" in sql

def test_collect_source_only_and_empty_acl_never_queries():
    sess=FakeSession([SimpleNamespace(contract_id=C1, revision=uuid.uuid4(),
        source_sha256="a"*64,page=2,field="equipment",source_quote="OPTIS Mobile Next")])
    assert collect_indexable_evidence(sess,organization_id=ORG,allowed_contract_ids=[])==[]
    assert sess.calls==0
    rows=collect_indexable_evidence(sess,organization_id=ORG,allowed_contract_ids=[C1])
    assert len(rows)==1
    assert rows[0].source_quote=="OPTIS Mobile Next"
    assert rows[0].verified is True

def test_archive_rechecks_acl_and_avoids_reuse():
    sess=FakeSession([])
    archive=FakeArchive()
    assert build_readonly_archive(sess,archive,organization_id=ORG,allowed_contract_ids=[C1])==0
    result=search_readonly_archive(archive,organization_id=ORG,
        allowed_contract_ids=[],phrase="OPTIS")
    assert result["allowed_documents"]==set()
    with pytest.raises(ValueError):
        build_readonly_archive(sess,SimpleNamespace(_stores={"stale":1}),
            organization_id=ORG,allowed_contract_ids=[C1])


def test_real_medflux_llama_archive_integration():
    pytest.importorskip("llama_index")
    from app.ai.harness.llama_archive import LlamaArchive
    session=FakeSession([SimpleNamespace(contract_id=C1, revision=uuid.uuid4(),
        source_sha256="b"*64,page=2,field="equipment",source_quote="OPTIS Mobile Next")])
    archive=LlamaArchive()
    assert build_readonly_archive(session,archive,organization_id=ORG,
                                  allowed_contract_ids=[C1])==1
    hits=search_readonly_archive(archive,organization_id=ORG,
        allowed_contract_ids=[C1],phrase="OPTIS")
    assert len(hits)==1 and hits[0]["page"]==2
    assert hits[0]["source_sha256"]=="b"*64
    assert search_readonly_archive(archive,organization_id=ORG,
        allowed_contract_ids=[],phrase="OPTIS")==[]
    assert search_readonly_archive(archive,organization_id=uuid.uuid4(),
        allowed_contract_ids=[C1],phrase="OPTIS")==[]