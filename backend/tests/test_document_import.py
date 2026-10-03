"""Tests für den Medflux-Dokumentimport (Schritt 4).

Arbeiten mit temporären Speicherverzeichnissen, keine externen Dateien.
"""

import hashlib
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.routes import documents as documents_module
from app.documents.schemas import ImportStatus
from app.documents.service import (
    MSG_DUPLICATE,
    MSG_EMPTY,
    MSG_SUCCESS,
    MSG_TOO_LARGE,
    MSG_UNSUPPORTED_TYPE,
    DocumentImportService,
)
from app.documents.storage import DocumentStorage
from app.main import app as medflux_app

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
DOCX_BYTES = b"PK\x03\x04 hier ein docx-platzhalter-bytes"


@pytest.fixture
def contracts_dir(tmp_path):
    d = tmp_path / "contracts"
    d.mkdir()
    return d


@pytest.fixture
def storage(contracts_dir):
    return DocumentStorage(contracts_dir)


@pytest.fixture
def service(storage):
    return DocumentImportService(storage=storage)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_valid_pdf_import(service):
    result = service.import_file("vertrag.pdf", "application/pdf", PDF_BYTES)
    assert result.status == ImportStatus.IMPORTED
    assert result.sha256 == sha(PDF_BYTES)
    assert result.message == MSG_SUCCESS


def test_valid_docx_import(service):
    result = service.import_file(
        "wartung.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        DOCX_BYTES,
    )
    assert result.status == ImportStatus.IMPORTED


def test_multiple_valid_files(service):
    response = service.import_many(
        [
            ("a.pdf", "application/pdf", PDF_BYTES),
            ("b.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", DOCX_BYTES),
        ]
    )
    assert response.total == 2
    assert response.successful == 2
    assert response.failed == 0
    assert all(r.status == ImportStatus.IMPORTED for r in response.documents)


def test_unsupported_extension_rejected(service):
    result = service.import_file("vertrag.txt", "text/plain", b"text")
    assert result.status == ImportStatus.REJECTED
    assert result.message == MSG_UNSUPPORTED_TYPE


def test_empty_file_rejected(service):
    result = service.import_file("leer.pdf", "application/pdf", b"")
    assert result.status == ImportStatus.REJECTED
    assert result.message == MSG_EMPTY


def test_oversized_file_rejected(service):
    service._max_size_bytes = 5
    result = service.import_file("gross.pdf", "application/pdf", b"1234567890")
    assert result.status == ImportStatus.REJECTED
    assert result.message == MSG_TOO_LARGE


def test_duplicate_detected(service):
    first = service.import_file("vertrag.pdf", "application/pdf", PDF_BYTES)
    second = service.import_file("kopie.pdf", "application/pdf", PDF_BYTES)
    assert first.status == ImportStatus.IMPORTED
    assert second.status == ImportStatus.DUPLICATE
    assert second.duplicate_of_document_id == first.document_id
    assert second.message == MSG_DUPLICATE
    # Original wird nicht überschrieben
    assert first.document_id == second.duplicate_of_document_id


def test_safe_storage_path(service, contracts_dir):
    result = service.import_file("../../evil.pdf", "application/pdf", PDF_BYTES)
    storage_path = contracts_dir / result.document_id / "original.pdf"
    assert storage_path.exists()
    # Der Dateipfad liegt innerhalb des Basisverzeichnisses
    assert storage_path.is_relative_to(contracts_dir)
    # Kein Traversal außerhalb
    assert ".." not in str(storage_path.relative_to(contracts_dir))


def test_sha256_generation(service):
    result = service.import_file("vertrag.pdf", "application/pdf", PDF_BYTES)
    assert result.sha256 == sha(PDF_BYTES)
    assert len(result.sha256) == 64


def test_partial_batch_success(service):
    response = service.import_many(
        [
            ("ok.pdf", "application/pdf", PDF_BYTES),
            ("bad.txt", "text/plain", b"text"),
            ("ok2.pdf", "application/pdf", PDF_BYTES + b"\n"),
        ]
    )
    assert response.total == 3
    assert response.successful == 2
    assert response.failed == 1
    statuses = [r.status for r in response.documents]
    assert statuses.count(ImportStatus.IMPORTED) == 2
    assert statuses.count(ImportStatus.REJECTED) == 1


def test_mime_mismatch_rejected(service):
    # Endung .pdf, aber Content-Type sagt deutlich etwas anderes
    result = service.import_file("bild.pdf", "image/png", PDF_BYTES)
    assert result.status == ImportStatus.REJECTED
    assert result.message == MSG_UNSUPPORTED_TYPE


def test_api_import_endpoint(monkeypatch):
    from app.documents.processing import ProcessedDocument

    class StubProcessingService:
        def process(self, **kwargs):
            if kwargs["original_filename"].endswith(".exe"):
                return ProcessedDocument(
                    document_id="",
                    document_version_id="",
                    sha256="",
                    original_filename=kwargs["original_filename"],
                    status="rejected",
                    message="Dokument wurde abgelehnt.",
                )
            return ProcessedDocument(
                document_id="11111111-1111-1111-1111-111111111111",
                document_version_id="22222222-2222-2222-2222-222222222222",
                sha256="a" * 64,
                original_filename=kwargs["original_filename"],
                status="imported",
                contract_id="33333333-3333-3333-3333-333333333333",
                message="Dokument erfolgreich verarbeitet.",
            )

    monkeypatch.setattr(
        documents_module, "_processing_service", StubProcessingService()
    )
    client = TestClient(medflux_app)
    files = [
        ("files", ("ok.pdf", PDF_BYTES, "application/pdf")),
        ("files", ("bad.exe", b"MZ...", "application/x-msdownload")),
    ]
    response = client.post(
        "/api/documents/import?organization_slug=krankenhaus", files=files
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["successful"] == 1
    assert body["failed"] == 1
    imported = [item for item in body["documents"] if item["status"] == "imported"]
    assert imported[0]["document_id"]
    assert imported[0]["contract_id"]


def test_api_import_requires_organization_and_empty_batch_is_supported():
    client = TestClient(medflux_app)
    missing_org = client.post("/api/documents/import")
    assert missing_org.status_code == 422

    response = client.post(
        "/api/documents/import?organization_slug=krankenhaus"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["documents"] == []


def test_api_import_forwards_explicit_contract_assignment(monkeypatch):
    from types import SimpleNamespace
    from app.documents.processing import ProcessedDocument

    class StubProcessingService:
        def process(self, **kwargs):
            return ProcessedDocument(
                document_id="11111111-1111-1111-1111-111111111111",
                document_version_id="22222222-2222-2222-2222-222222222222",
                sha256="a" * 64,
                original_filename=kwargs["original_filename"],
                status="imported",
                contract_id="33333333-3333-3333-3333-333333333333",
            )

    assignment = (
        UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        [UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")],
        UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
    )
    assigned = []
    monkeypatch.setattr(documents_module, "_processing_service", StubProcessingService())
    monkeypatch.setattr(documents_module, "_validate_import_scope", lambda _slug: None)
    monkeypatch.setattr(documents_module, "current_actor", lambda *_args: SimpleNamespace(role="admin", is_developer=False))
    monkeypatch.setattr(documents_module, "_validate_import_assignment", lambda _slug, value, _actor: assigned.append(value))
    monkeypatch.setattr(documents_module, "_assign_import_scope", lambda _slug, cid, status, value: assigned.append((cid, status, value)))

    client = TestClient(medflux_app)
    response = client.post(
        "/api/documents/import?organization_slug=krankenhaus",
        files=[("files", ("neu.pdf", PDF_BYTES, "application/pdf"))],
        data={
            "assignment_hospital_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "responsible_department_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "beneficiary_department_ids": ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
            "cost_center_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        },
    )
    assert response.status_code == 200
    assert assigned == [assignment, ("33333333-3333-3333-3333-333333333333", "imported", assignment)]
