import hashlib
import uuid
from types import SimpleNamespace

import pytest

from app.documents.persistence import (
    DocumentPersistenceService,
    StorageError,
    canonical_storage_key,
)
from app.documents.storage import DocumentStorage


class _Rows:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _Session:
    def __init__(self, document, version):
        self._rows = iter((document, version))

    def scalars(self, _statement):
        return _Rows(next(self._rows))


def _existing_rows(content):
    document_id = uuid.uuid4()
    version_id = uuid.uuid4()
    ref = canonical_storage_key(document_id, ".pdf")
    sha256 = hashlib.sha256(content).hexdigest()
    document = SimpleNamespace(
        id=document_id,
        file_extension=".pdf",
        storage_key=ref,
        mime_type="application/pdf",
        original_filename="source.pdf",
    )
    version = SimpleNamespace(id=version_id, storage_key=ref)
    return document, version, ref, sha256


def test_duplicate_upload_restores_missing_original(tmp_path):
    content = b"%PDF-1.4\nsource bytes\n%%EOF"
    document, version, ref, sha256 = _existing_rows(content)
    storage = DocumentStorage(tmp_path / "contracts")
    service = DocumentPersistenceService(storage=storage)
    storage.write_reference(ref, content)
    storage.delete_reference(ref)
    assert not storage.exists_reference(ref)

    result = service.store_original(
        _Session(document, version),
        organization_id=uuid.uuid4(),
        original_filename="reimport.pdf",
        content_type="application/pdf",
        content=content,
    )

    assert result.duplicate is True
    assert result.document_file_id == str(document.id)
    assert result.document_version_id == str(version.id)
    assert result.storage_key == ref
    assert result.sha256 == sha256
    assert storage.read_reference(ref) == content


def test_duplicate_upload_rejects_noncanonical_document_reference(tmp_path):
    content = b"%PDF-1.4\nsource bytes\n%%EOF"
    document, version, _, _ = _existing_rows(content)
    document.storage_key = "../outside.pdf"
    storage = DocumentStorage(tmp_path / "contracts")
    service = DocumentPersistenceService(storage=storage)

    with pytest.raises(StorageError, match="Dokumentreferenz"):
        service.store_original(
            _Session(document, version),
            organization_id=uuid.uuid4(),
            original_filename="reimport.pdf",
            content_type="application/pdf",
            content=content,
        )

    assert not list((tmp_path / "contracts").rglob("*"))


def test_duplicate_upload_rejects_version_with_different_storage_reference(tmp_path):
    content = b"%PDF-1.4\nsource bytes\n%%EOF"
    document, version, _, _ = _existing_rows(content)
    version.storage_key = "../outside.pdf"
    storage = DocumentStorage(tmp_path / "contracts")
    service = DocumentPersistenceService(storage=storage)

    with pytest.raises(StorageError, match="Dokumentreferenz"):
        service.store_original(
            _Session(document, version),
            organization_id=uuid.uuid4(),
            original_filename="reimport.pdf",
            content_type="application/pdf",
            content=content,
        )

    assert not list((tmp_path / "contracts").rglob("*"))
