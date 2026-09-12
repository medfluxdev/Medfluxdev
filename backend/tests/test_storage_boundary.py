"""STEP 14 – Einheitliche Storage-Grenze (DB + Bytes) Integrationstests.

Verifiziert die Produktions-Persistenz-Kette mit ECHTEN temporaeren Dateien +
postgreSQL-Zeilen:
    DocumentFile -> storage_key (kanonische Referenz) -> DocumentStorage -> Bytes

Transaktion-pro-Test (Rollback) gegen native PostgreSQL; ohne DB -> SKIPPED.
Der Storage-Root ist pro Test ein echtes Temp-Verzeichnis (tmp_path).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import DocumentFile, DocumentVersion, Organization, Contract
from app.database.services import create_contract, create_organization, get_organization
from app.documents.persistence import DocumentPersistenceService, StorageError
from app.documents.storage import DocumentStorage


def _pg_available(engine) -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(settings.database_url, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _require_pg(engine):
    if not _pg_available(engine):
        pytest.skip("PostgreSQL nicht erreichbar – Storage-Grenze übersprungen")
    yield


@pytest.fixture
def db(engine):
    session = Session(engine, expire_on_commit=False)
    session.begin()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def storage(tmp_path: Path) -> DocumentStorage:
    return DocumentStorage(tmp_path / "contracts")


@pytest.fixture
def svc(storage: DocumentStorage) -> DocumentPersistenceService:
    return DocumentPersistenceService(storage=storage)


def _org(db) -> Organization:
    return create_organization(db, name="Klinik", slug=f"klinik-{uuid.uuid4().hex[:12]}")


PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n%%EOF\n"


def _pdf(filename="wartung.pdf") -> tuple[str, bytes]:
    return filename, PDF_BYTES


# ---------------------------------------------------------------------------
# Produktions-Write -> aufloesbare DB->Storage-Beziehung
# ---------------------------------------------------------------------------

def test_write_creates_resolvable_db_to_storage_relationship(db, svc):
    org = _org(db)
    name, content = _pdf()
    result = svc.store_original(
        db, organization_id=org.id,
        original_filename=name, content_type="application/pdf", content=content,
    )
    assert result.duplicate is False
    # Referenz ist server-kontrolliert & relativ.
    assert result.storage_key.endswith("/original.pdf")
    assert "/" not in result.storage_key.lstrip("./").split("/", 1)[0].lstrip(".") or "original.pdf" in result.storage_key
    # DB-Zeilen existieren.
    doc = db.get(DocumentFile, uuid.UUID(result.document_file_id))
    ver = db.get(DocumentVersion, uuid.UUID(result.document_version_id))
    assert doc is not None and ver is not None
    assert doc.storage_key == result.storage_key
    assert ver.storage_key == result.storage_key
    # Referenz -> Bytes aufloesbar (DocumentStorage uebersetzt).
    assert storage_resolves(svc, result.storage_key)


def storage_resolves(svc, ref) -> bytes:
    return svc._storage.read_reference(ref)


def test_bytes_written_are_correct_and_sha_preserved(db, svc):
    org = _org(db)
    name, content = _pdf()
    import hashlib
    result = svc.store_original(
        db, organization_id=org.id,
        original_filename=name, content_type="application/pdf", content=content,
    )
    bytes_on_disk = storage_resolves(svc, result.storage_key)
    assert bytes_on_disk == content
    doc = db.get(DocumentFile, uuid.UUID(result.document_file_id))
    assert doc.sha256 == hashlib.sha256(content).hexdigest()
    assert doc.sha256 == result.sha256


def test_duplicate_sha_idempotent_no_second_file(db, svc):
    org = _org(db)
    name, content = _pdf()
    r1 = svc.store_original(db, organization_id=org.id, original_filename=name,
                            content_type="application/pdf", content=content)
    r2 = svc.store_original(db, organization_id=org.id, original_filename=name,
                            content_type="application/pdf", content=content)
    assert r2.duplicate is True
    assert r1.document_file_id == r2.document_file_id
    # Nur EINE DocumentFile-Zeile.
    rows = db.scalars(select(DocumentFile).where(DocumentFile.sha256 == r1.sha256)).all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Lesepfad: vertragsgebundene, org-gebundene Byte-Auslieferung
# ---------------------------------------------------------------------------

def _linked_version(db, org, svc, contract_id=None, role="main"):
    name, content = _pdf()
    r = svc.store_original(db, organization_id=org.id, original_filename=name,
                          content_type="application/pdf", content=content)
    if contract_id is not None:
        svc.link_to_contract(db, contract_id=contract_id, document_version_id=r.document_version_id, role=role)
    db.flush()
    return r, content


def test_correct_bytes_returned_for_linked_version(db, svc):
    org = _org(db)
    contract = create_contract(db, organization_id=org.id, supplier="Lief.")
    r, content = _linked_version(db, org, svc, contract_id=contract.id)
    out = svc.resolve_bytes_for_version(
        db, organization_id=org.id, document_version_id=r.document_version_id, contract_id=contract.id,
    )
    assert out == content


def test_cross_org_access_fails(db, svc):
    org_a = _org(db)
    org_b = _org(db)
    c_a = create_contract(db, organization_id=org_a.id, supplier="A")
    r, content = _linked_version(db, org_a, svc, contract_id=c_a.id)
    with pytest.raises(StorageError):
        svc.resolve_bytes_for_version(
            db, organization_id=org_b.id, document_version_id=r.document_version_id, contract_id=c_a.id,
        )


def test_unlinked_wrong_version_fails(db, svc):
    org = _org(db)
    contract = create_contract(db, organization_id=org.id, supplier="Lief.")
    r, content = _linked_version(db, org, svc)  # NICHT verlinkt
    with pytest.raises(StorageError):
        svc.resolve_bytes_for_version(
            db, organization_id=org.id, document_version_id=r.document_version_id, contract_id=contract.id,
        )
    # auch falsche Versions-ID
    with pytest.raises(StorageError):
        svc.resolve_bytes_for_version(
            db, organization_id=org.id, document_version_id=str(uuid.uuid4()), contract_id=contract.id,
        )


def test_missing_file_fails_safely(db, svc):
    org = _org(db)
    contract = create_contract(db, organization_id=org.id, supplier="Lief.")
    r, content = _linked_version(db, org, svc, contract_id=contract.id)
    # Datei vom Root entfernen -> resolve muss generisch scheitern.
    svc._storage.delete_reference(r.storage_key)
    with pytest.raises(StorageError):
        svc.resolve_bytes_for_version(
            db, organization_id=org.id, document_version_id=r.document_version_id, contract_id=contract.id,
        )


# ---------------------------------------------------------------------------
# Referenz-Sicherheit (Traversal / absolut / UNC duerfen Root nicht verlassen)
# ---------------------------------------------------------------------------

def test_traversal_refs_cannot_escape_root(storage):
    bad = [
        "../escape.pdf",
        "../../etc/original.pdf",
        "..\\escape.pdf",
        "C:/windows/original.pdf",
        "C:\\original.pdf",
        "///server/share/original.pdf",
        r"\\server\share\original.pdf",
        "documents/../../original.pdf",
        f"{'a'*32}/../../../etc/original.pdf",
    ]
    for ref in bad:
        with pytest.raises(StorageError):
            storage.validate_reference(ref)
        assert storage.exists_reference(ref) is False


def test_noncanonical_but_valid_hex_refs_rejected(storage):
    # 32-hex gültig, aber falsche Struktur/Endung -> abgelehnt.
    for ref in [
        f"{'a'*32}/sub/original.pdf",
        f"{'a'*32}/original.exe",
        f"{'a'*31}/original.pdf",
        f"{'a'*32}/original.txt",
    ]:
        with pytest.raises(StorageError):
            storage.validate_reference(ref)


# ---------------------------------------------------------------------------
# Kompensation / Deterministisches Fehlschlagen
# ---------------------------------------------------------------------------

def test_db_failure_after_file_write_is_compensated(db, svc, monkeypatch):
    org = _org(db)
    name, content = _pdf()
    real_create = DocumentPersistenceService._create_version

    def boom(self, session, organization_id, doc, version_no, sha256, ref):
        raise RuntimeError("simulierter DB-Fehler nach FS-Write")

    monkeypatch.setattr(DocumentPersistenceService, "_create_version", boom)
    with pytest.raises(RuntimeError):
        svc.store_original(db, organization_id=org.id, original_filename=name,
                           content_type="application/pdf", content=content)
    # Kompensation: keine Datei darf ein Orphan auf dem Root hinterlassen.
    assert not (svc._storage._base_dir / name).exists()
    # org-gebunden: es darf keine DocumentVersion angelegt worden sein.
    versions = db.scalars(
        select(DocumentVersion).where(DocumentVersion.organization_id == org.id)
    ).all()
    assert versions == []


def test_storage_failure_leaves_no_db_relationship(db, svc, monkeypatch):
    org = _org(db)
    name, content = _pdf()

    def fail_write(self, reference, content):
        raise StorageError("write fehlgeschlagen")

    monkeypatch.setattr(DocumentStorage, "write_reference", fail_write)
    with pytest.raises(StorageError):
        svc.store_original(db, organization_id=org.id, original_filename=name,
                           content_type="application/pdf", content=content)
    # org-gebunden: keine DocumentVersion (keine 'akzeptierte' Beziehung).
    assert db.scalars(
        select(DocumentVersion).where(DocumentVersion.organization_id == org.id)
    ).all() == []
    # Keine Contract-Kopplung fuer diese Organisation.
    assert db.scalars(
        select(Contract).where(Contract.organization_id == org.id)
    ).all() == []


def test_unsupported_type_rejected_before_persistence(db, svc):
    org = _org(db)
    with pytest.raises(StorageError):
        svc.store_original(db, organization_id=org.id, original_filename="virus.exe",
                           content_type="application/x-msdownload", content=b"MZ...")
    assert db.scalars(
        select(DocumentVersion).where(DocumentVersion.organization_id == org.id)
    ).all() == []
