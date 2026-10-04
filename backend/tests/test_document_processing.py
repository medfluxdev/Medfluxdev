"""Focused production-flow integration tests for DocumentProcessingService.

Expensive local DI/OCR/AI is stubbed; PostgreSQL persistence and real temporary
storage are exercised.  Each test runs inside an outer transaction so the
shared development database is rolled back after the test.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.ai.contract_extractor import ContractAnalysisResult
from app.api.routes import documents as documents_route
from app.contracts.detail.service import build_contract_detail
from app.contracts.search.service import SearchParams, build_contract_search
from app.core.config import settings
from app.dashboard.service import build_dashboard_overview
from app.database.models import (
    CalculationRun,
    Contract,
    ContractEquipment,
    ContractExtraction,
    DocumentArtifact,
    ExtractionEvidence,
    ProcessingRun,
    ProcessingSummary,
    WarningEvaluationRun,
)
from app.database.services import create_organization
from app.documents.extraction.schemas import (
    ExtractionUnit,
    FileType,
    SourceType,
    TextExtractionResult,
    UnitMethod,
)
from app.documents.intelligence.canonical import (
    DocumentIntelligenceResult,
    Element,
    LogicalUnit,
    ElementType,
    Method,
    Page,
    ProcessingProvenance,
    TextSpan,
)
from app.documents.persistence import DocumentPersistenceService
from app.documents.processing import DocumentProcessingService, ProcessedDocument
from app.documents.service import DocumentImportService
from app.documents.storage import DocumentStorage
from app.main import app
from app.models.contract import Contract as DomainContract
from app.models.contract import ContractIdentity, Equipment
from app.models.enums import ExtractionStatus, ValidationStatus
from app.models.evidence import SourceEvidence


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with eng.connect() as connection:
            connection.execute(text("select 1"))
    except Exception:
        eng.dispose()
        pytest.skip("PostgreSQL nicht erreichbar – Processing-Integration übersprungen")
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine, monkeypatch):
    connection = engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    from app.documents import processing as processing_module

    monkeypatch.setattr(processing_module, "create_session", factory)
    try:
        yield factory
    finally:
        outer.rollback()
        connection.close()


def _organization(factory) -> tuple[str, object]:
    slug = f"processing-{uuid.uuid4().hex[:12]}"
    with factory() as session:
        org = create_organization(session, name="Processing Testklinik", slug=slug)
        session.commit()
        return slug, org.id


def _pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
        + uuid.uuid4().hex.encode("ascii")
        + b"\n%%EOF\n"
    )


class StubIntelligenceProvider:
    name = "stub_di"

    def __init__(self) -> None:
        self.calls = 0

    def process(self, path: Path, settings=None) -> DocumentIntelligenceResult:
        self.calls += 1
        source = path.read_bytes()
        page_text = "Wartungsvertrag CT-Scanner Lieferant Alpha"
        return DocumentIntelligenceResult(
            source_sha256=hashlib.sha256(source).hexdigest(),
            source_filename=path.name,
            source_path=str(path),
            canonical_text=page_text,
            pages_text=[page_text],
            pages=[
                Page(
                    page_number=1,
                    width_pt=595,
                    height_pt=842,
                    text=page_text,
                    elements=[
                        Element(
                            element_id="p1-e1",
                            type=ElementType.PARAGRAPH,
                            text=page_text,
                            page=1,
                            spans=[TextSpan(offset=0, length=len(page_text))],
                            reading_order=0,
                            method=Method.NATIVE,
                        )
                    ],
                )
            ],
            provenance=ProcessingProvenance(
                provider=self.name,
                provider_version="test-1",
                method=Method.NATIVE,
                do_ocr=False,
                do_table_structure=True,
                geometry_provider="stub_geometry",
                config={"fixture": True},
            ),
            warnings=["diagnostic-warning"],
            processing_time_s=0.25,
        )


class NoLegacyPdfExtraction:
    def extract_from_path(self, *args, **kwargs):
        raise AssertionError("PDF production flow must not repeat legacy text/OCR extraction")


class DocxExtraction:
    def __init__(self) -> None:
        self.calls = 0

    def extract_from_path(self, document_id, extension, path):
        self.calls += 1
        assert extension == ".docx"
        units = [
            ExtractionUnit(
                source_type=SourceType.PARAGRAPH,
                index=1,
                text="Vertragsnummer DOCX-1 Lieferant Beta",
                method=UnitMethod.TEXT,
            ),
            ExtractionUnit(
                source_type=SourceType.TABLE,
                index=1,
                text="Gerät | MRT",
                method=UnitMethod.TEXT,
            ),
        ]
        return TextExtractionResult(
            document_id=document_id,
            file_type=FileType.DOCX,
            extraction_status=ExtractionStatus.SUCCESS,
            page_count=0,
            total_characters=sum(len(unit.text) for unit in units),
            text_available=True,
            units=units,
        )


class SequencedAnalysis:
    def __init__(self, *results: ContractAnalysisResult) -> None:
        self.results = list(results)
        self.calls = 0

    async def analyze(self, extraction):
        result = self.results[self.calls]
        self.calls += 1
        result.document_id = extraction.document_id
        return result


def _analysis_success(*, docx: bool = False) -> ContractAnalysisResult:
    evidence = (
        SourceEvidence(
            page=None,
            source_type="paragraph",
            paragraph_index=1,
            source_text="Vertragsnummer DOCX-1",
            confidence=0.91,
        )
        if docx
        else SourceEvidence(
            page=1,
            source_type="page",
            source_text="Wartungsvertrag CT-Scanner",
            confidence=0.97,
        )
    )
    contract = DomainContract(
        identity=ContractIdentity(
            contract_title="Wartungsvertrag",
            contract_number="DOCX-1" if docx else "PDF-1",
            supplier="Lieferant Beta" if docx else "Lieferant Alpha",
            evidence=evidence,
        ),
        equipment=[
            Equipment(
                device_name="MRT" if docx else "CT-Scanner",
                manufacturer="MedTech",
                serial_number="SER-1",
            )
        ],
    )
    assert contract.review.requires_manual_review is False
    return ContractAnalysisResult(
        document_id="",
        status=ExtractionStatus.SUCCESS,
        validation_status=ValidationStatus.VALID,
        requires_review=False,
        contract=contract,
        message="Analyse erfolgreich.",
        model="local-test-model",
        prompt_version="test-prompt-v1",
        chunk_count=3,
        processing_duration=1.25,
        timeout_count=1,
        retry_count=2,
        truncated_chunks=3,
        ai_call_count=4,
        groups_processed=5,
        evidence_issues=6,
        verifier_issues=7,
        normalization_issues=8,
    )


def test_equipment_evidence_without_locator_is_not_persistable():
    """An evidence object alone must not imply a navigable equipment source."""
    contract = DomainContract(
        equipment=[
            Equipment(
                system_name="Accutron MR",
                evidence=SourceEvidence(
                    source_text="Accutron MR",
                    confidence=0.9,
                ),
            )
        ]
    )
    _snapshot, evidence = DocumentProcessingService._build_extraction(contract)
    assert not any(
        row["field_ref"] == "identity_equipment.evidence.0"
        for row in evidence
    )


def test_equipment_evidence_with_locator_is_persistable():
    contract = DomainContract(
        equipment=[
            Equipment(
                system_name="Accutron MR",
                evidence=SourceEvidence(
                    source_type="page",
                    page=2,
                    source_text="Accutron MR",
                    confidence=0.9,
                ),
            )
        ]
    )
    _snapshot, evidence = DocumentProcessingService._build_extraction(contract)
    assert any(
        row["field_ref"] == "identity_equipment.evidence.0"
        and row["page"] == 2
        for row in evidence
    )


def test_equipment_with_incomplete_identity_and_source_evidence_remains_persistable():
    contract = DomainContract(
        equipment=[
            Equipment(
                device_name="Exactrac X-Ray System",
                evidence=SourceEvidence(
                    source_type="page",
                    page=2,
                    source_text="Exactrac X-Ray System",
                    confidence=0.9,
                    requires_review=True,
                ),
            )
        ]
    )
    _snapshot, evidence = DocumentProcessingService._build_extraction(contract)
    assert contract.equipment[0].device_name == "Exactrac X-Ray System"
    assert contract.equipment[0].evidence.requires_review is True
    assert any(
        row["field_ref"] == "identity_equipment.evidence.0"
        and row["page"] == 2
        and row["requires_review"] is True
        for row in evidence
    )


def _analysis_failure() -> ContractAnalysisResult:
    return ContractAnalysisResult(
        document_id="",
        status=ExtractionStatus.FAILED,
        validation_status=ValidationStatus.INVALID,
        requires_review=True,
        contract=None,
        message="Analyse nicht möglich.",
        error="internal-local-ai-diagnostic",
        model="local-test-model",
        chunk_count=2,
        processing_duration=0.75,
        timeout_count=1,
        retry_count=1,
        ai_call_count=2,
    )


def _service(storage, provider, analysis, extraction=None):
    return DocumentProcessingService(
        persistence=DocumentPersistenceService(storage=storage),
        extraction=extraction or NoLegacyPdfExtraction(),
        analysis=analysis,
        storage=storage,
        intelligence=provider,
    )


def test_pdf_production_flow_persists_canonical_provenance_and_read_models(
    tmp_path, session_factory
):
    slug, organization_id = _organization(session_factory)
    storage = DocumentStorage(tmp_path / "contracts")
    provider = StubIntelligenceProvider()
    service = _service(
        storage,
        provider,
        SequencedAnalysis(_analysis_success()),
    )

    result = service.process(
        organization_slug=slug,
        original_filename="wartung.pdf",
        content_type="application/pdf",
        content=_pdf_bytes(),
        as_of_date=date(2026, 1, 1),
    )

    assert result.status == "imported"
    assert result.contract_id is not None
    assert provider.calls == 1

    with session_factory() as session:
        runs = session.scalars(
            select(ProcessingRun).where(ProcessingRun.organization_id == organization_id)
        ).all()
        assert len(runs) == 1
        assert runs[0].status == "succeeded"
        assert runs[0].provider == "stub_di"
        assert runs[0].geometry_provider == "stub_geometry"
        assert runs[0].canonical_artifact_id is not None

        summary = session.scalars(
            select(ProcessingSummary).where(
                ProcessingSummary.organization_id == organization_id
            )
        ).one()
        assert summary.page_count == 1
        assert summary.success_count == 1
        assert summary.failure_count == 0
        assert summary.last_success_run_id == runs[0].id

        artifact = session.get(DocumentArtifact, runs[0].canonical_artifact_id)
        assert artifact is not None
        assert artifact.artifact_type == "canonical"
        canonical_payload = json.loads(storage.read_reference(artifact.storage_key))
        assert canonical_payload["provenance"]["provider"] == "stub_di"
        assert canonical_payload["warnings"] == ["diagnostic-warning"]

        extraction = session.scalars(
            select(ContractExtraction).where(
                ContractExtraction.organization_id == organization_id
            )
        ).one()
        assert extraction.chunk_count == 3
        assert extraction.processing_duration == pytest.approx(1.25)
        assert extraction.timeout_count == 1
        assert extraction.retry_count == 2
        assert extraction.truncated_chunks == 3
        assert extraction.ai_call_count == 4
        assert extraction.groups_processed == 5
        assert extraction.evidence_issues == 6
        assert extraction.verifier_issues == 7
        assert extraction.normalization_issues == 8

        calculation = session.scalars(
            select(CalculationRun).where(CalculationRun.organization_id == organization_id)
        ).one()
        assert calculation.overall_review_required is True

        contract = session.get(Contract, uuid.UUID(result.contract_id))
        assert contract.accepted_extraction_id == extraction.id
        assert contract.accepted_calculation_run_id == calculation.id

        equipment = session.scalars(
            select(ContractEquipment).where(
                ContractEquipment.contract_id == contract.id
            )
        ).all()
        assert [(item.device_name, item.serial_number) for item in equipment] == [
            ("CT-Scanner", "SER-1")
        ]
        assert session.scalars(
            select(WarningEvaluationRun).where(
                WarningEvaluationRun.contract_id == contract.id
            )
        ).one()

        search_result = build_contract_search(
            session,
            SearchParams(organization_id=organization_id, q="PDF-1"),
            organization_id=organization_id,
            request_as_of=date(2026, 1, 1),
        )
        assert search_result["total_count"] == 1
        assert str(search_result["items"][0]["contract_id"]) == result.contract_id

        detail = build_contract_detail(
            session, organization_id=organization_id, contract_id=contract.id
        )
        assert detail["equipment"][0]["device_name"] == "CT-Scanner"
        assert detail["evidence"][0]["page"] == 1

        dashboard = build_dashboard_overview(
            session, organization_id=organization_id, as_of_date=date(2026, 1, 1)
        )
        assert dashboard["freshness"]["warning_evaluation_as_of_date"] == date(
            2026, 1, 1
        )


def test_docx_evidence_and_canonical_artifact_keep_logical_address_without_page(
    tmp_path, session_factory
):
    slug, organization_id = _organization(session_factory)
    storage = DocumentStorage(tmp_path / "contracts")
    provider = StubIntelligenceProvider()
    docx_extraction = DocxExtraction()
    service = _service(
        storage,
        provider,
        SequencedAnalysis(_analysis_success(docx=True)),
        extraction=docx_extraction,
    )

    result = service.process(
        organization_slug=slug,
        original_filename="wartung.docx",
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        content=b"PK\x03\x04" + uuid.uuid4().bytes,
        as_of_date=date(2026, 1, 1),
    )

    assert result.status == "imported"
    assert provider.calls == 0
    assert docx_extraction.calls == 1

    with session_factory() as session:
        evidence = session.scalars(
            select(ExtractionEvidence).where(
                ExtractionEvidence.organization_id == organization_id
            )
        ).one()
        assert evidence.page is None
        assert evidence.source_type == "paragraph"
        assert evidence.paragraph_index == 1

        run = session.scalars(
            select(ProcessingRun).where(ProcessingRun.organization_id == organization_id)
        ).one()
        artifact = session.get(DocumentArtifact, run.canonical_artifact_id)
        payload = json.loads(storage.read_reference(artifact.storage_key))
        assert payload["pages"] == []
        assert payload["logical_units"][0] == {
            "source_type": "paragraph",
            "index": 1,
            "text": "Vertragsnummer DOCX-1 Lieferant Beta",
            "method": "native",
        }
        assert payload["provenance"]["provider"] == "python-docx"

        detail = build_contract_detail(
            session,
            organization_id=organization_id,
            contract_id=uuid.UUID(result.contract_id),
        )
        assert detail["evidence"][0]["page"] is None
        assert detail["evidence"][0]["paragraph_index"] == 1
        assert detail["evidence"][0]["table_index"] is None


def test_failed_analysis_can_resume_same_version_and_reuses_canonical_artifact(
    tmp_path, session_factory
):
    slug, organization_id = _organization(session_factory)
    storage = DocumentStorage(tmp_path / "contracts")
    provider = StubIntelligenceProvider()
    analysis = SequencedAnalysis(_analysis_failure(), _analysis_success())
    service = _service(storage, provider, analysis)
    content = _pdf_bytes()

    first = service.process(
        organization_slug=slug,
        original_filename="retry.pdf",
        content_type="application/pdf",
        content=content,
        as_of_date=date(2026, 1, 1),
    )
    assert first.status == "analysis_failed"
    assert first.contract_id is not None

    resumed = service.resume_document(
        organization_slug=slug,
        document_version_id=first.document_version_id,
        as_of_date=date(2026, 1, 1),
    )
    assert resumed.status == "imported"
    assert resumed.contract_id is not None
    assert provider.calls == 1
    assert analysis.calls == 2

    duplicate = service.process(
        organization_slug=slug,
        original_filename="retry-copy.pdf",
        content_type="application/pdf",
        content=content,
        as_of_date=date(2026, 1, 1),
    )
    assert duplicate.status == "duplicate"
    assert duplicate.contract_id == resumed.contract_id
    assert provider.calls == 1
    assert analysis.calls == 2

    with session_factory() as session:
        runs = session.scalars(
            select(ProcessingRun)
            .where(ProcessingRun.organization_id == organization_id)
            .order_by(ProcessingRun.created_at)
        ).all()
        assert [run.status for run in runs] == ["partial", "succeeded"]
        assert runs[0].canonical_artifact_id == runs[1].canonical_artifact_id

        summary = session.scalars(
            select(ProcessingSummary).where(
                ProcessingSummary.organization_id == organization_id
            )
        ).one()
        assert summary.failure_count == 1
        assert summary.success_count == 1
        assert summary.last_success_run_id == runs[1].id

        extractions = session.scalars(
            select(ContractExtraction)
            .where(ContractExtraction.organization_id == organization_id)
            .order_by(ContractExtraction.created_at)
        ).all()
        assert [item.status for item in extractions] == ["failed", "success"]
        assert extractions[0].timeout_count == 1
        assert extractions[0].retry_count == 1


def test_legacy_reconciliation_uses_same_orchestrator_without_modifying_original(
    tmp_path, session_factory
):
    slug, _organization_id = _organization(session_factory)
    storage = DocumentStorage(tmp_path / "contracts")
    legacy = DocumentImportService(storage=storage)
    original = _pdf_bytes()
    legacy_result = legacy.import_file("legacy.pdf", "application/pdf", original)
    original_path = storage.resolve_document(legacy_result.document_id)[1]
    index_before = storage._index_path().read_bytes()
    bytes_before = original_path.read_bytes()

    provider = StubIntelligenceProvider()
    service = _service(
        storage,
        provider,
        SequencedAnalysis(_analysis_success()),
    )
    results = service.reconcile_legacy(
        organization_slug=slug,
        document_ids=[legacy_result.document_id],
        as_of_date=date(2026, 1, 1),
    )

    assert len(results) == 1
    assert results[0].status == "imported"
    assert results[0].contract_id is not None
    assert original_path.read_bytes() == bytes_before
    assert storage._index_path().read_bytes() == index_before
    assert provider.calls == 1


def test_import_route_requires_organization_and_never_exposes_internal_error(monkeypatch):
    client = TestClient(app)
    missing_org = client.post(
        "/api/documents/import",
        files=[("files", ("bad.exe", b"MZ", "application/x-msdownload"))],
    )
    assert missing_org.status_code == 422

    class FailingProcessing:
        def process(self, **kwargs):
            return ProcessedDocument(
                document_id="",
                document_version_id="",
                sha256="",
                original_filename=kwargs["original_filename"],
                status="failed",
                message=None,
                error="password=secret; postgres://internal-host/private",
            )

    monkeypatch.setattr(documents_route, "_processing_service", FailingProcessing())
    response = client.post(
        "/api/documents/import?organization_slug=krankenhaus",
        files=[("files", ("safe.pdf", b"%PDF-1.4", "application/pdf"))],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["documents"][0]["status"] == "failed"
    assert payload["documents"][0]["message"] == "Verarbeitung fehlgeschlagen."
    assert "secret" not in response.text
    assert "internal-host" not in response.text


def test_canonical_to_extraction_uses_source_extension_not_logical_unit_shape():
    """A structured PDF must never be reclassified as DOCX."""
    canonical = DocumentIntelligenceResult(
        document_id="doc-1",
        source_sha256="a" * 64,
        source_filename="structured-contract.pdf",
        source_path=None,
        canonical_text="",
        pages_text=[],
        pages=[],
        logical_units=[
            LogicalUnit(
                source_type="paragraph",
                index=1,
                text="Vertragsnummer PDF-LOGICAL-1",
                method=Method.NATIVE,
            )
        ],
        provenance=ProcessingProvenance(
            provider="test",
            provider_version="1",
            method=Method.NATIVE,
            do_ocr=False,
            do_table_structure=True,
            geometry_provider=None,
            config={},
        ),
        warnings=[],
        processing_time_s=0.0,
    )

    extraction = DocumentProcessingService._canonical_to_extraction(canonical)

    assert extraction.file_type == FileType.PDF
    assert extraction.text_available is True
    assert extraction.total_characters == len("Vertragsnummer PDF-LOGICAL-1")
    assert len(extraction.units) == 1


def test_harness_evidence_persistence_is_not_coupled_to_exact_version():
    contract = DomainContract()
    source = SourceEvidence(
        page=2,
        source_type="page",
        source_text="Jahrespreis 12.000 EUR",
        confidence=0.98,
    )
    contract.analysis.harness_version = "v2.1"
    contract.analysis.harness = {
        "evidence": [
            {
                "field": "costs.annual_cost",
                "source": source.model_dump(mode="json"),
            }
        ]
    }

    _snapshot, evidence = DocumentProcessingService._build_extraction(contract)

    assert len(evidence) == 1
    assert evidence[0]["field_ref"] == "costs.annual_cost.evidence.0"
    assert evidence[0]["page"] == 2
    assert evidence[0]["source_text"] == "Jahrespreis 12.000 EUR"


def test_harness_diagnostics_do_not_report_fake_zero_chunks():
    analysis = ContractAnalysisResult(
        document_id="doc-1",
        status=ExtractionStatus.FAILED,
        validation_status=ValidationStatus.UNKNOWN,
        requires_review=True,
        contract=None,
        prompt_version="harness-v2.1",
        ai_call_count=0,
        groups_processed=0,
    )

    diagnostics = DocumentProcessingService._analysis_diagnostics(analysis)

    assert diagnostics["chunk_count"] is None
    assert diagnostics["truncated_chunks"] is None
    assert diagnostics["ai_call_count"] == 0


def test_scanned_pdf_without_text_is_eligible_for_v3_visual_path():
    canonical = DocumentIntelligenceResult(
        document_id="scan-1", source_sha256="b" * 64, source_filename="scan.pdf",
        source_path=None, canonical_text="", pages_text=[],
        pages=[Page(page_number=1, width_pt=595, height_pt=842, text="", elements=[])],
        logical_units=[],
        provenance=ProcessingProvenance(provider="test", provider_version="1",
            method=Method.UNKNOWN, do_ocr=True, do_table_structure=True,
            geometry_provider=None, config={}),
        warnings=[], processing_time_s=0.0,
    )
    extraction = DocumentProcessingService._canonical_to_extraction(canonical)
    assert extraction.text_available is False
    assert extraction.units == []
    assert settings.harness_engine == "v3"
    assert Path(canonical.source_filename).suffix.lower() == ".pdf"
    assert bool(canonical.pages) is True


def test_build_canonical_falls_back_to_native_pdf_when_primary_di_fails(tmp_path):
    class BrokenProvider:
        name = "docling"

        def process(self, path, settings):
            raise RuntimeError("simulated local DI failure")

    import fitz

    pdf = fitz.open()
    pdf.new_page()
    content = pdf.tobytes()
    pdf.close()
    path = tmp_path / "fallback.pdf"
    path.write_bytes(content)
    stored = ProcessedDocument(
        document_id=str(uuid.uuid4()),
        document_version_id=str(uuid.uuid4()),
        sha256=hashlib.sha256(content).hexdigest(),
        original_filename="fallback.pdf",
        status="imported",
    )
    service = DocumentProcessingService(intelligence=BrokenProvider())
    canonical, extraction = service._build_canonical(stored, path)
    assert canonical.provenance.provider == "native_pdf"
    assert canonical.pages
    assert extraction.file_type == FileType.PDF
    assert any("Vision-Fallback" in warning for warning in canonical.warnings)


def test_textless_v3_pdf_still_runs_document_intelligence_ocr(
    tmp_path, monkeypatch
):
    """A scanned V3 PDF must retain an OCR/layout evidence layer before vision."""
    import fitz
    from app.documents import processing as processing_module
    from app.documents.intelligence.native_provider import NativePdfDocumentProvider

    pdf = fitz.open()
    pdf.new_page()
    content = pdf.tobytes()
    pdf.close()
    path = tmp_path / "textless-scan.pdf"
    path.write_bytes(content)

    native = NativePdfDocumentProvider()

    class TrackingDocling:
        name = "docling"

        def __init__(self):
            self.calls = 0

        def process(self, path, settings):
            self.calls += 1
            canonical = native.process(path, settings)
            page = canonical.pages[0].model_copy(update={
                "text": "Vertragsnummer OCR-1 Jahrespreis 8.000 EUR",
            })
            return canonical.model_copy(update={
                "canonical_text": page.text,
                "pages_text": [page.text],
                "pages": [page],
            })

    docling = TrackingDocling()

    def provider_factory(name):
        if name == "docling":
            return docling
        if name == "native_pdf":
            return native
        raise AssertionError(f"unexpected provider: {name}")

    monkeypatch.setattr(processing_module, "get_provider", provider_factory)
    monkeypatch.setattr(settings, "document_intelligence_provider", "docling")
    monkeypatch.setattr(settings, "harness_engine", "v3")

    stored = ProcessedDocument(
        document_id=str(uuid.uuid4()),
        document_version_id=str(uuid.uuid4()),
        sha256=hashlib.sha256(content).hexdigest(),
        original_filename="textless-scan.pdf",
        status="imported",
    )

    service = DocumentProcessingService()
    canonical, extraction = service._build_canonical(stored, path)

    assert docling.calls == 1
    assert canonical.pages
    assert canonical.pages[0].text == "Vertragsnummer OCR-1 Jahrespreis 8.000 EUR"
    assert extraction.text_available is True
    assert extraction.units
    assert not any("direkter V3-Vision-Pfad" in w for w in canonical.warnings)



def test_docling_cuda_failure_retries_auto_before_native_fallback(tmp_path, monkeypatch):
    import fitz
    from app.documents import processing as processing_module
    from app.documents.intelligence.native_provider import NativePdfDocumentProvider

    pdf = fitz.open()
    pdf.new_page()
    content = pdf.tobytes()
    pdf.close()
    path = tmp_path / "cuda-retry-scan.pdf"
    path.write_bytes(content)

    native = NativePdfDocumentProvider()

    class RetryDocling:
        name = "docling"

        def __init__(self):
            self.devices = []

        def process(self, path, di_settings):
            self.devices.append(di_settings.device)
            if di_settings.device == "cuda":
                raise RuntimeError("CUDA backend unavailable")
            canonical = native.process(path, di_settings)
            page = canonical.pages[0].model_copy(update={"text": "Laufzeit 4 Jahre"})
            return canonical.model_copy(update={
                "canonical_text": page.text,
                "pages_text": [page.text],
                "pages": [page],
            })

    docling = RetryDocling()

    def provider_factory(name):
        if name == "docling":
            return docling
        if name == "native_pdf":
            return native
        raise AssertionError(name)

    monkeypatch.setattr(processing_module, "get_provider", provider_factory)
    monkeypatch.setattr(settings, "document_intelligence_provider", "docling")
    monkeypatch.setattr(settings, "document_intelligence_device", "cuda")

    stored = ProcessedDocument(
        document_id=str(uuid.uuid4()),
        document_version_id=str(uuid.uuid4()),
        sha256=hashlib.sha256(content).hexdigest(),
        original_filename="cuda-retry-scan.pdf",
        status="imported",
    )

    canonical, extraction = DocumentProcessingService()._build_canonical(stored, path)

    assert docling.devices == ["cuda", "auto"]
    assert extraction.text_available is True
    assert canonical.pages[0].text == "Laufzeit 4 Jahre"
    assert any("automatischer Beschleunigerwahl" in w for w in canonical.warnings)
