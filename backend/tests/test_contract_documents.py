"""H3: documents per contract, amendment proposals, termination letters and
framework detection through the single DocumentProcessingService path."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.contract_extractor import ContractAnalysisResult
from app.api.routes import contract_documents, contract_register
from app.core.scope_context import ScopeContext
from app.database.models import Contract, ContractDocument
from app.database.models.intelligence import ContractRelationRecord
from app.database.models.organization import Organization
from app.database.models.register import ContractFieldProvenance
from app.database.session import create_session
from app.documents.intelligence.canonical import (
    DocumentIntelligenceResult,
    Element,
    ElementType,
    Method,
    Page,
    ProcessingProvenance,
    TextSpan,
)
from app.documents.persistence import DocumentPersistenceService
from app.documents.processing import DocumentProcessingService
from app.documents.storage import DocumentStorage
from app.models.contract import Contract as DomainContract
from app.models.enums import ExtractionStatus, ValidationStatus
from app.register.service import RegisterActor, create_manual_contract


class TextProvider:
    name = "stub_di"

    def __init__(self, text: str) -> None:
        self.text = text

    def process(self, path: Path, settings=None) -> DocumentIntelligenceResult:
        source = path.read_bytes()
        return DocumentIntelligenceResult(
            source_sha256=hashlib.sha256(source).hexdigest(),
            source_filename=path.name,
            source_path=str(path),
            canonical_text=self.text,
            pages_text=[self.text],
            pages=[Page(
                page_number=1, width_pt=595, height_pt=842, text=self.text,
                elements=[Element(
                    element_id="p1-e1", type=ElementType.PARAGRAPH, text=self.text, page=1,
                    spans=[TextSpan(offset=0, length=len(self.text))], reading_order=0, method=Method.NATIVE,
                )],
            )],
            provenance=ProcessingProvenance(
                provider=self.name, provider_version="test-1", method=Method.NATIVE, do_ocr=False,
                do_table_structure=False, geometry_provider="stub", config={},
            ),
        )


class FixedAnalysis:
    def __init__(self, contract: DomainContract) -> None:
        self.contract = contract

    async def analyze(self, extraction):
        return ContractAnalysisResult(
            document_id=extraction.document_id, status=ExtractionStatus.SUCCESS,
            validation_status=ValidationStatus.VALID, contract=self.contract, message="ok", model="test",
        )


class NoLegacyExtraction:
    def extract_from_path(self, *args, **kwargs):
        raise AssertionError("PDF flow must not use legacy extraction")


def _pdf() -> bytes:
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n" + uuid.uuid4().hex.encode() + b"\n%%EOF\n"


def _service(tmp_path, text: str, contract: DomainContract) -> DocumentProcessingService:
    storage = DocumentStorage(tmp_path)
    return DocumentProcessingService(
        persistence=DocumentPersistenceService(storage=storage),
        extraction=NoLegacyExtraction(),
        analysis=FixedAnalysis(contract),
        storage=storage,
        intelligence=TextProvider(text),
    )


def _seed():
    slug = f"documents-{uuid.uuid4().hex[:12]}"
    session = create_session()
    try:
        org = Organization(name="Dokumente Test", slug=slug)
        session.add(org)
        session.flush()
        actor = RegisterActor(organization_id=org.id, account_id=None, display_name="Tester", role="admin")
        framework = create_manual_contract(session, actor=actor, hospital_id=None, values={
            "short_description": "Rahmenvertrag Medizintechnik", "is_framework": True, "internal_number": "RV-2024-77",
        })
        member = create_manual_contract(session, actor=actor, hospital_id=None, values={
            "short_description": "Wartung CT", "term_model": "terminable", "term_start_date": "2025-01-01",
            "notice_period_value": 3, "notice_period_unit": "months", "notice_to": "quarter_end",
        })
        session.commit()
        return slug, org.id, framework.id, member.id
    finally:
        session.close()


def test_amendment_creates_proposals_only_and_detects_framework(tmp_path):
    slug, _org_id, framework_id, member_id = _seed()
    amendment = DomainContract.model_validate({
        "dates": {"start_date": {"date": "2025-02-01"}},
        "termination": {"cancellation_period": {"value": 6, "unit": "months"}, "cancellation_condition": "zum Quartalsende"},
    })
    service = _service(tmp_path, "1. Nachtrag gemäß Rahmenvertrag RV-2024-77: Kündigungsfrist sechs Monate.", amendment)
    result = service.attach_to_contract(
        organization_slug=slug, contract_id=member_id, original_filename="nachtrag.pdf",
        content_type="application/pdf", content=_pdf(), attachment_type="nachtrag", title="1. Nachtrag",
        added_by_name="Tester", analyze=True,
    )
    assert result.status == "analyzed", result.message
    assert result.requires_review is True

    session = create_session()
    try:
        contract = session.get(Contract, member_id)
        assert contract.term_start_date.isoformat() == "2025-01-01"
        assert contract.notice_period_value == 3
        rows = {
            row.field_key: row for row in session.scalars(
                select(ContractFieldProvenance).where(ContractFieldProvenance.contract_id == member_id)
            ).all()
        }
        assert rows["term_start_date"].ai_proposed_value == {
            "value": "2025-02-01", "source_field": "dates.start_date", "document": "1. Nachtrag",
        }
        assert rows["notice_period_value"].ai_proposed_value["value"] == 6
        assert "notice_to" not in rows or rows["notice_to"].ai_proposed_value is None
        link = session.scalars(select(ContractDocument).where(ContractDocument.contract_id == member_id)).one()
        assert (link.role, link.attachment_type, link.is_main, link.title) == ("amendment", "nachtrag", False, "1. Nachtrag")
        relation = session.scalars(select(ContractRelationRecord).where(
            ContractRelationRecord.target_contract_id == member_id
        )).one()
        assert relation.source_contract_id == framework_id and relation.requires_review is True
        assert relation.relation_type == "governs"
    finally:
        session.close()

    letter = DomainContract.model_validate({"dates": {"end_date": {"date": "2026-12-31"}}})
    termination = _service(tmp_path, "Hiermit kündigen wir fristgerecht.", letter).attach_to_contract(
        organization_slug=slug, contract_id=member_id, original_filename="kuendigung.pdf",
        content_type="application/pdf", content=_pdf(), attachment_type="kuendigung", title=None,
        added_by_name="Tester", analyze=True,
    )
    assert termination.status == "analyzed"
    session = create_session()
    try:
        row = session.scalars(select(ContractFieldProvenance).where(
            ContractFieldProvenance.contract_id == member_id, ContractFieldProvenance.field_key == "terminated_effective"
        )).one()
        assert row.ai_proposed_value["value"] == "2026-12-31"
        assert session.get(Contract, member_id).terminated_effective is None
    finally:
        session.close()

    stored_only = _service(tmp_path, "Laufzettel", amendment).attach_to_contract(
        organization_slug=slug, contract_id=member_id, original_filename="laufzettel.pdf",
        content_type="application/pdf", content=_pdf(), attachment_type="laufzettel", title="Interner Laufzettel",
        added_by_name="Tester", analyze=True,
    )
    assert stored_only.status == "attached"


def _client(monkeypatch, org_id, role="admin"):
    actor = SimpleNamespace(organization_id=org_id, account_id=None, role=role, is_developer=False, display_name="Tester")
    for module in (contract_register, contract_documents):
        monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor, raising=False)
    monkeypatch.setattr(contract_register, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(contract_documents, "current_scope_context", lambda: ScopeContext())
    app = FastAPI()
    app.include_router(contract_documents.router)
    return TestClient(app)


def test_document_metadata_main_valid_and_framework_links(tmp_path, monkeypatch):
    slug, org_id, framework_id, member_id = _seed()
    query = {"organization_slug": slug}
    main_contract = DomainContract.model_validate({})
    service = _service(tmp_path, "Vertragstext", main_contract)
    for name, kind in (("vertrag.pdf", "vertrag"), ("angebot.pdf", "angebot")):
        service.attach_to_contract(
            organization_slug=slug, contract_id=member_id, original_filename=name, content_type="application/pdf",
            content=_pdf(), attachment_type=kind, title=None, added_by_name="Tester", analyze=False,
        )
    monkeypatch.setattr(contract_documents, "_processing_service", service)
    client = _client(monkeypatch, org_id)

    listing = client.get(f"/api/contracts/{member_id}/documents", params=query).json()
    assert [(item["attachment_type"], item["is_main"]) for item in listing["items"]] == [("vertrag", True), ("angebot", False)]
    assert "nachtrag" in listing["attachment_types"]
    main_link, offer = listing["items"][0]["link_id"], listing["items"][1]["link_id"]

    assert client.patch(f"/api/contracts/{member_id}/documents/{main_link}", params=query,
                        json={"values": {"is_valid": False}}).status_code == 409
    assert client.patch(f"/api/contracts/{member_id}/documents/{offer}", params=query,
                        json={"values": {"attachment_type": "erfunden"}}).status_code == 422
    switched = client.patch(f"/api/contracts/{member_id}/documents/{offer}", params=query,
                            json={"values": {"is_main": True, "title": "Angebot 2025"}})
    assert switched.status_code == 200
    assert [(item["title"], item["is_main"]) for item in switched.json()["items"]] == [("Angebot 2025", True), ("vertrag.pdf", False)]
    invalid = client.patch(f"/api/contracts/{member_id}/documents/{main_link}", params=query, json={"values": {"is_valid": False}})
    assert invalid.status_code == 200 and invalid.json()["items"][1]["is_valid"] is False

    upload = client.post(
        f"/api/contracts/{member_id}/documents", params=query,
        files=[("files", ("laufzettel.pdf", _pdf(), "application/pdf")), ("files", ("auskunft.pdf", _pdf(), "application/pdf"))],
        data={"attachment_type": "laufzettel", "analyze": "true"},
    )
    assert upload.status_code == 200, upload.text
    assert [item["status"] for item in upload.json()["results"]] == ["attached", "attached"]
    assert len(upload.json()["items"]) == 4
    rejected = client.post(
        f"/api/contracts/{member_id}/documents", params=query,
        files=[("files", ("x.txt", b"hello", "text/plain"))], data={"attachment_type": "laufzettel"},
    )
    assert rejected.status_code == 200 and rejected.json()["results"][0]["status"] == "rejected"

    relations = client.get(f"/api/contracts/{member_id}/relations", params=query).json()
    assert relations["frameworks"] == []
    assert [item["contract_id"] for item in relations["framework_options"]] == [str(framework_id)]
    assert client.post(f"/api/contracts/{framework_id}/relations", params=query,
                       json={"framework_contract_id": str(member_id)}).status_code == 422
    linked = client.post(f"/api/contracts/{member_id}/relations", params=query, json={"framework_contract_id": str(framework_id)})
    assert linked.status_code == 200
    assert linked.json()["frameworks"][0]["confirmed"] is True
    members = client.get(f"/api/contracts/{framework_id}/relations", params=query).json()["members"]
    assert members[0]["contract_id"] == str(member_id)
    removed = client.delete(f"/api/contracts/{member_id}/relations/{linked.json()['frameworks'][0]['relation_id']}", params=query)
    assert removed.status_code == 200 and removed.json()["frameworks"] == []

    viewer = _client(monkeypatch, org_id, role="viewer")
    assert viewer.patch(f"/api/contracts/{member_id}/documents/{offer}", params=query, json={"values": {"title": "x"}}).status_code == 403
