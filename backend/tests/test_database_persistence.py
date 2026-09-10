"""Fokussierte PostgreSQL-Persistenz-Tests (STEP 10B).

Lauf gegen die native PostgreSQL 18.6-Instanz (backend/.env DATABASE_URL).
Verwendet ein Transaktion-pro-Test-Muster (Rollback am Ende), damit die
geteilte Dev-DB nach dem Lauf unverändert bleibt. Ist PostgreSQL nicht
erreichbar (Schema nicht migriert / keine DB), wird SKIPPED – die bestehende
Unit-Suite bleibt dadurch ohne DB-Verbindung grün.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import (
    CalculationResult,
    CalculationRun,
    ContractEquipment,
    DocumentVersion,
    ExtractionEvidence,
    Organization,
)
from app.database.services import (
    PersistenceError,
    accept_calculation,
    accept_extraction,
    add_equipment,
    create_contract,
    create_document_version,
    create_organization,
    create_processing_run,
    finish_processing_run,
    link_document,
    project_contract,
    resolve_source_navigation,
    save_artifact,
    save_calculation,
    save_document_file,
    save_extraction,
    upsert_processing_summary,
    verify_extraction_integrity,
)
from app.database.models.contract import Contract
from app.database.models.extraction import ContractExtraction


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
        pytest.skip("PostgreSQL nicht erreichbar – Persistenz-Tests übersprungen")
    yield


@pytest.fixture
def db(engine):
    session = Session(engine, expire_on_commit=False)
    session.begin()
    yield session
    session.rollback()
    session.close()


def _org(db: Session) -> Organization:
    return create_organization(
        db, name="Testklinik", slug=f"test-{uuid.uuid4().hex[:12]}"
    )


def _sha() -> str:
    return uuid.uuid4().hex + "0" * 16  # 64 hex


def _doc(db: Session):
    org = _org(db)
    doc = save_document_file(
        db,
        organization_id=org.id,
        sha256=_sha(),
        original_filename="Wartungsvertrag.pdf",
        stored_filename="original.pdf",
        file_extension=".pdf",
        file_size_bytes=1024,
        storage_key="abc/original.pdf",
    )
    db.flush()
    return org, doc


def test_uuidv7_pk_is_v7(engine, db):
    org = _org(db)
    db.flush()
    hexes = [f"{org.id.int:032x}"]
    # Version-Nibble ist Index 12 (0-basiert)
    assert hexes[0][12] == "7"


def test_organization_create_idempotent(db):
    org1 = create_organization(db, name="A", slug="slugidem")
    db.flush()
    org2 = create_organization(db, name="B", slug="slugidem")
    assert org1.id == org2.id


def test_save_document_file_sha256_dedup(db):
    _, doc = _doc(db)
    db.flush()
    again = save_document_file(
        db,
        organization_id=doc.organization_id,
        sha256=doc.sha256,
        original_filename="geändert.pdf",
        stored_filename="original.pdf",
        file_extension=".pdf",
        file_size_bytes=999,
        storage_key="different/original.pdf",
    )
    assert again.id == doc.id
    assert again.duplicate_detected is True


def test_document_file_invalid_status_rejected(db):
    org = _org(db)
    with pytest.raises(PersistenceError):
        save_document_file(
            db,
            organization_id=org.id,
            sha256=_sha(),
            original_filename="x.pdf",
            stored_filename="original.pdf",
            file_extension=".pdf",
            file_size_bytes=1,
            storage_key="k/original.pdf",
            import_status="bogus",
        )


def test_storage_key_is_relative(db):
    _, doc = _doc(db)
    db.flush()
    assert ":" not in doc.storage_key
    assert not doc.storage_key.startswith("/")
    assert not doc.storage_key.startswith("C:")


def test_document_version_idempotent_by_sha(db):
    org, doc = _doc(db)
    db.flush()
    v1 = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=_sha(), storage_key="v/original.pdf"
    )
    db.flush()
    v2 = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=v1.sha256, storage_key="v/original.pdf"
    )
    assert v1.id == v2.id


def test_artifact_allowed_and_invalid_type(db):
    org, doc = _doc(db)
    db.flush()
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=_sha(), storage_key="v/original.pdf"
    )
    art = save_artifact(
        db,
        organization_id=org.id,
        document_version_id=ver.id,
        artifact_type="canonical",
        storage_key="art/canonical.json",
        sha256=_sha(),
        size_bytes=10,
    )
    db.flush()
    assert art.lifecycle_state == "active"
    with pytest.raises(PersistenceError):
        save_artifact(
            db,
            organization_id=org.id,
            document_version_id=ver.id,
            artifact_type="nope",
            storage_key="x",
            sha256=_sha(),
            size_bytes=1,
        )


def test_processing_run_create_and_finish(db):
    org, doc = _doc(db)
    db.flush()
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=_sha(), storage_key="v/original.pdf"
    )
    run = create_processing_run(
        db, organization_id=org.id, document_version_id=ver.id, status="running"
    )
    db.flush()
    finished = finish_processing_run(
        db, run_id=run.id, status="succeeded", processing_duration=1.5
    )
    assert finished.status == "succeeded"


def test_processing_summary_increments(db):
    org, doc = _doc(db)
    db.flush()
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=_sha(), storage_key="v/original.pdf"
    )
    s1 = upsert_processing_summary(
        db, organization_id=org.id, document_version_id=ver.id, file_key="v/original.pdf"
    )
    db.flush()
    s2 = upsert_processing_summary(
        db, organization_id=org.id, document_version_id=ver.id, file_key="v/original.pdf"
    )
    assert s1.id == s2.id
    assert s2.success_count == 2


def test_extraction_atomic_write_snapshot_and_evidence(db):
    org, doc = _doc(db)
    db.flush()
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=_sha(), storage_key="v/original.pdf"
    )
    snapshot = {
        "supplier": {"value": "ACME", "confidence": 0.9, "evidence": {"source_type": "page", "page": 2}},
        "costs": {"annual": 1200.5},
    }
    run = save_extraction(
        db,
        organization_id=org.id,
        document_version_id=ver.id,
        snapshot=snapshot,
        evidence=[
            {
                "field_ref": "supplier.evidence",
                "source_type": "page",
                "page": 2,
                "source_text": "ACME Vertrag",
                "bounding_box": {"x0": 0, "y0": 0, "x1": 10, "y1": 10},
                "ocr_confidence": 0.85,
                "extraction_method": "programmatic",
            }
        ],
    )
    db.flush()
    assert run.id is not None
    assert run.snapshot_sha256 is not None
    assert run.contract_snapshot == snapshot
    ev = db.scalars(
        select(ExtractionEvidence).where(ExtractionEvidence.extraction_id == run.id)
    ).all()
    assert len(ev) == 1
    assert ev[0].field_ref == "supplier.evidence"
    assert Decimal(ev[0].ocr_confidence) == Decimal("0.8500")


def test_extraction_integrity_quicktest(db):
    org, doc = _doc(db)
    db.flush()
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=_sha(), storage_key="v/original.pdf"
    )
    snapshot = {
        "supplier": {"value": "ACME", "evidence": {"source_type": "page", "page": 2}}
    }
    run = save_extraction(
        db,
        organization_id=org.id,
        document_version_id=ver.id,
        snapshot=snapshot,
        evidence=[
            {
                "field_ref": "supplier.evidence",
                "source_type": "page",
                "page": 2,
                "source_text": "ACME",
            }
        ],
    )
    db.flush()
    result = verify_extraction_integrity(db, run.id)
    assert result["evidence_count"] == 1
    assert result["mismatches"] == []
    assert result["snapshot_sha256"] == run.snapshot_sha256


def test_extraction_invalid_status_rejected(db):
    org, doc = _doc(db)
    db.flush()
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=_sha(), storage_key="v/original.pdf"
    )
    with pytest.raises(PersistenceError):
        save_extraction(
            db,
            organization_id=org.id,
            document_version_id=ver.id,
            snapshot={},
            evidence=[],
            status="nonsense",
        )


def _extraction(db):
    org, doc = _doc(db)
    db.flush()
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=_sha(), storage_key="v/original.pdf"
    )
    run = save_extraction(
        db,
        organization_id=org.id,
        document_version_id=ver.id,
        snapshot={"supplier": {"value": "ACME"}},
        evidence=[
            {"field_ref": "supplier.value", "source_type": "page", "page": 1}
        ],
    )
    db.flush()
    return org, ver, run


def test_calculation_atomic_run_result_flags(db):
    org, ver, ext = _extraction(db)
    cal = save_calculation(
        db,
        organization_id=org.id,
        extraction_id=ext.id,
        as_of_date=date(2026, 12, 31),
        result_snapshot={"annual": 1200.5},
        result_rows=[
            {
                "field_key": "annual",
                "status": "computed",
                "amount": "1200.50",
                "currency": "EUR",
                "value": "1200.50",
            }
        ],
        review_flags=[
            {"flag_key": "expiring_soon", "severity": "warning", "reason": "Ende < 90 Tage"}
        ],
    )
    db.flush()
    assert cal.as_of_date == date(2026, 12, 31)
    res = db.scalars(
        select(CalculationRun).where(CalculationRun.id == cal.id)
    ).one()
    assert res.as_of_date == date(2026, 12, 31)
    # Über die relationship laden
    assert len(cal.review_flags) == 1
    assert cal.review_flags[0].severity == "warning"


def test_calculation_amount_is_decimal_not_float(db):
    org, ver, ext = _extraction(db)
    cal = save_calculation(
        db,
        organization_id=org.id,
        extraction_id=ext.id,
        as_of_date=date(2026, 1, 1),
        result_snapshot={},
        result_rows=[
            {"field_key": "monthly", "status": "computed", "amount": "1234.56", "currency": "EUR"}
        ],
    )
    db.flush()
    rows = db.execute(
        select(CalculationResult).where(CalculationResult.run_id == cal.id)
    ).all()
    amount = rows[0][0].amount
    assert isinstance(amount, Decimal)
    assert amount == Decimal("1234.56")
    assert not isinstance(amount, float)


def test_calculation_as_of_date_persisted_explicit(db):
    org, ver, ext = _extraction(db)
    cal = save_calculation(
        db,
        organization_id=org.id,
        extraction_id=ext.id,
        as_of_date=date(2024, 5, 17),
        result_snapshot={},
    )
    db.flush()
    assert cal.as_of_date == date(2024, 5, 17)


def test_project_contract_writes_projection(db):
    org, ver, ext = _extraction(db)
    contract = create_contract(db, organization_id=org.id, supplier="ACME")
    project_contract(
        db,
        contract=contract,
        supplier="ACME GmbH",
        contract_number="W-4711",
        start_date=date(2026, 1, 1),
        end_date=date(2028, 1, 1),
        status="active",
        risk_level="medium",
    )
    db.flush()
    assert contract.contract_number == "W-4711"
    assert contract.start_date == date(2026, 1, 1)
    assert contract.end_date == date(2028, 1, 1)
    assert contract.status == "active"


def test_terminated_only_from_explicit_status(db):
    org = _org(db)
    contract = create_contract(db, organization_id=org.id)
    # Abgelaufenes Ende darf NICHT automatisch TERMINATED ableiten.
    project_contract(db, contract=contract, end_date=date(2020, 1, 1), status=None)
    db.flush()
    assert contract.status is None
    # Explizit gesetzter Status wird übernommen.
    project_contract(db, contract=contract, status="TERMINATED")
    db.flush()
    assert contract.status == "terminated"


def test_accept_extraction_and_calculation_pointers(db):
    org, ver, ext = _extraction(db)
    contract = create_contract(db, organization_id=org.id)
    cal = save_calculation(
        db,
        organization_id=org.id,
        extraction_id=ext.id,
        as_of_date=date(2026, 1, 1),
        result_snapshot={},
    )
    db.flush()
    accept_extraction(db, contract_id=contract.id, extraction_id=ext.id)
    accept_calculation(db, contract_id=contract.id, calculation_run_id=cal.id)
    db.flush()
    assert contract.accepted_extraction_id == ext.id
    assert contract.accepted_calculation_run_id == cal.id


def test_link_document_idempotent_nm(db):
    org, doc = _doc(db)
    db.flush()
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id, version_no=1, sha256=_sha(), storage_key="v/original.pdf"
    )
    contract = create_contract(db, organization_id=org.id)
    l1 = link_document(
        db, contract_id=contract.id, document_version_id=ver.id, role="main"
    )
    db.flush()
    l2 = link_document(
        db, contract_id=contract.id, document_version_id=ver.id, role="main"
    )
    assert l1.id == l2.id


def test_link_document_invalid_role_rejected(db):
    org, ver, ext = _extraction(db)
    contract = create_contract(db, organization_id=org.id)
    with pytest.raises(PersistenceError):
        link_document(
            db, contract_id=contract.id, document_version_id=ver.id, role="bogus"
        )


def test_add_equipment(db):
    org, ver, ext = _extraction(db)
    contract = create_contract(db, organization_id=org.id)
    eq = add_equipment(
        db,
        contract_id=contract.id,
        device_name="CT-Scanner",
        manufacturer="Siemens",
        serial_number="A-1",
    )
    db.flush()
    assert eq.contract_id == contract.id
    got = db.get(ContractEquipment, eq.id)
    assert got.device_name == "CT-Scanner"


def test_source_navigation_full_chain(db):
    org, ver, ext = _extraction(db)
    contract = create_contract(db, organization_id=org.id)
    accept_extraction(db, contract_id=contract.id, extraction_id=ext.id)
    db.flush()
    nav = resolve_source_navigation(
        db, contract_id=contract.id, field_ref="supplier.value"
    )
    assert nav is not None
    assert nav.field_ref == "supplier.value"
    assert nav.page == 1
    assert nav.storage_key == "v/original.pdf"
    assert nav.original_filename == "Wartungsvertrag.pdf"
    assert nav.bounding_box is None  # keine Geometrie erfunden


def test_source_navigation_none_without_geometry_exists(db):
    org, ver, ext = _extraction(db)
    contract = create_contract(db, organization_id=org.id)
    db.flush()
    # kein akzeptierter Lauf -> None
    assert resolve_source_navigation(db, contract_id=contract.id, field_ref="x") is None


def test_snapshot_jsonb_roundtrip(db):
    org, ver, ext = _extraction(db)
    db.flush()
    stored = db.get(ContractExtraction, ext.id)
    assert stored.contract_snapshot == {"supplier": {"value": "ACME"}}


def test_extraction_cascade_delete_to_evidence(db):
    org, ver, ext = _extraction(db)
    db.flush()
    evid = db.scalars(
        select(ExtractionEvidence).where(ExtractionEvidence.extraction_id == ext.id)
    ).all()
    assert len(evid) == 1
    db.delete(ext)
    db.flush()
    gone = db.scalars(
        select(ExtractionEvidence).where(ExtractionEvidence.extraction_id == ext.id)
    ).all()
    assert gone == []
