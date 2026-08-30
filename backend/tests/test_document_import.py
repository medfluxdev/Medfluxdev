"""Tests für den Medflux-Dokumentimport (Schritt 4).

Arbeiten mit temporären Speicherverzeichnissen, keine externen Dateien.
"""

import hashlib

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


def test_api_import_endpoint(tmp_path, monkeypatch):
    test_base = tmp_path / "contracts"
    test_base.mkdir()
    test_storage = DocumentStorage(test_base)
    test_service = DocumentImportService(storage=test_storage)

    monkeypatch.setattr(documents_module, "_service", test_service)

    client = TestClient(medflux_app)

    files = [
        ("files", ("ok.pdf", PDF_BYTES, "application/pdf")),
        ("files", ("bad.exe", b"MZ...", "application/x-msdownload")),
    ]
    r = client.post("/api/documents/import", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["successful"] == 1
    assert body["failed"] == 1
    assert len(body["documents"]) == 2
    # Erfolgreiche Datei hat document_id
    imported = [d for d in body["documents"] if d["status"] == "imported"]
    assert imported[0]["document_id"]
    # Ablage existiert lokal
    doc_id = imported[0]["document_id"]
    assert (test_base / doc_id / "original.pdf").exists()


def test_api_import_empty_request(monkeypatch):
    client = TestClient(medflux_app)
    r = client.post("/api/documents/import")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 0
    assert body["documents"] == []
