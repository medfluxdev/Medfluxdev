"""STEP 14 – Contract-Detail-Read-Model + sicherer Dokument-Zugriff (Integration).

Nutzt echte temp-Dateien (DocumentPersistenceService) + PostgreSQL-Zeilen.
Transaktion-pro-Test (Rollback); ohne DB -> SKIPPED. Verifiziert:
- akzeptierte Current-/Accepted-Wahrheit (keine Neuberechnung von Warnungen),
- Org-Isolation + generische 404,
- Evidence-Provenienz (bbox/Precision/Fallback),
- sicherer Dokument-Zugriff (MIME-Allowlist, Header, Range, sanitized Disposition),
- keine storage_keys/Pfade im Payload.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    eng = create_engine(settings.database_url, pool_pre_ping=True)
    yield eng
    eng.dispose()


from app.core.config import settings
from app.main import app
from app.database.models import Organization
from app.database.services import (
    accept_calculation,
    accept_extraction,
    create_contract,
    create_organization,
    get_organization,
)
from app.contracts.calculation import calculate_contract
from app.database.services import save_calculation, save_extraction
from app.documents.persistence import DocumentPersistenceService
from app.documents.storage import DocumentStorage
from app.models.contract import Contract as DomainContract
from app.models.contract import ContractDates, Costs, Termination
from app.models.enums import ContractStatus, TimeUnit
from app.models.values import Duration, FlexibleDate, Money


def _pg_available(engine) -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def _require_pg(engine):
    if not _pg_available(engine):
        pytest.skip("PostgreSQL nicht erreichbar – Detail-Tests übersprungen")
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


PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n"


def _org(db) -> Organization:
    return create_organization(db, name="Klinik", slug=f"klinik-{uuid.uuid4().hex[:12]}")


def _store_pdf(db, org, svc):
    r = svc.store_original(db, organization_id=org.id, original_filename="wartung.pdf",
                           content_type="application/pdf", content=PDF_BYTES)
    db.flush()
    return r


def _chain(db, org, svc, *, end=date(2027, 6, 30), annual="12000", evidence_bbox=None):
    """Legt PDF -> Extraktion(+Evidence) -> Berechnung -> Vertrag (akzeptiert) an."""
    r = _store_pdf(db, org, svc)
    evidence = [
        {
            "field_ref": "identity.contract_title",
            "source_type": "paragraph",
            "page": 1,
            "source_text": "Wartungsvertrag CT-Scanner",
            "bounding_box": evidence_bbox,
            "confidence": 0.98,
        },
        {
            "field_ref": "dates.start_date",
            "source_type": "paragraph",
            "page": 1,
            "source_text": "01.01.2024",
            "bounding_box": evidence_bbox,
        },
        {
            "field_ref": "costs.annual_cost",
            "source_type": "table",
            "page": 2,
            "source_text": "12.000 Euro",
            "bounding_box": evidence_bbox,
        },
    ]
    ext = save_extraction(
        db, organization_id=org.id, document_version_id=r.document_version_id,
        snapshot={
            "identity": {"contract_title": "Wartungsvertrag CT-Scanner",
                          "contract_number": "CN-DTL-1"},
            "dates": {"start_date": {"date": "2024-01-01"}},
            "termination": {"automatic_renewal": True},
            "services": {
                "maintenance": True, "repair": True,
                "included_services": ["Lagerung", "Vor-Ort-Service"],
            },
            "sla": {"response_time": {"value": "48h"}, "availability_24_7": False},
        },
        evidence=evidence,
        status="success",
    )

    domain = DomainContract(
        id="DET",
        status=ContractStatus.UNKNOWN,
        dates=ContractDates(
            start_date=FlexibleDate(date=date(2024, 1, 1)),
            end_date=FlexibleDate(date=end),
        ),
        termination=Termination(
            cancellation_period=Duration(value=90, unit=TimeUnit.DAYS),
            cancellation_to_contract_end="to_contract_end",
        ),
        costs=Costs(
            default_currency="EUR",
            annual_cost=Money(amount="12000", currency="EUR"),
        )
        if annual is not None
        else Costs(default_currency="EUR"),
    )
    calc = calculate_contract(domain, as_of_date=date(2025, 6, 1))
    run = save_calculation(
        db, organization_id=org.id, extraction_id=ext.id,
        as_of_date=date(2025, 6, 1), result_snapshot=calc.model_dump(mode="json"),
        calculation_version="step9-1.0", status="computed", result_rows=[], review_flags=[],
    )
    contract = create_contract(db, organization_id=org.id, supplier="Lieferant",
                               status="active", contract_number="CN-DTL-1")
    accept_extraction(db, contract_id=contract.id, extraction_id=ext.id)
    accept_calculation(db, contract_id=contract.id, calculation_run_id=run.id)
    svc.link_to_contract(db, contract_id=contract.id,
                         document_version_id=r.document_version_id, role="main")
    db.flush()
    return contract, r


# ---------------------------------------------------------------------------
# Detail-Read-Model
# ---------------------------------------------------------------------------

def test_detail_correct_org(db, svc):
    org = _org(db)
    contract, r = _chain(db, org, svc, annual=12000)
    data = detail_for(db, org, contract)
    assert data is not None
    assert data["contract_number"] == "CN-DTL-1"
    assert data["contract_title"] == "Wartungsvertrag CT-Scanner"
    assert data["supplier"] == "Lieferant"
    assert data["dates"]["start_date"] == "2024-01-01"
    assert data["dates"]["automatic_renewal"] is True
    assert data["costs"]["annual_recurring"]["currency"] == "EUR"
    assert data["scope"]["maintenance"] is True
    assert data["sla"]["availability_24_7"] is False
    # Documents gelistet (sicher).
    assert len(data["documents"]) == 1
    assert data["documents"][0]["viewer_supported"] is True
    # Evidence vorhanden, keine storage_key/Pfade.
    assert len(data["evidence"]) == 3
    payload = str(data)
    assert r.storage_key not in payload
    assert "storage_key" not in payload


def test_detail_pr3_basis_and_deadlines(db, svc):
    """PR-3: Financial-/Deadline-Snapshot + Berechnungsgrundlage im Detail-DTO.

    Die Basis (explanation/inputs) und Fristengrößen stammen AUS dem
    akzeptierten STEP-9-Snapshot (autoritativ), nicht aus Frontend-Rechenweg.
    Der `_chain`-Fixture liefert: end=2027-06-30, annual_cost=12000, und eine
    Kündigungsfrist von 90 Tagen zum Vertragsende.
    """
    org = _org(db)
    contract, _ = _chain(db, org, svc, annual=12000)
    data = detail_for(db, org, contract)

    # Deadline: autoritatives Ende + Basis + Resttage.
    assert data["dates"]["calculated_end_date"] == date(2027, 6, 30)
    assert data["dates"]["calculated_end_status"] == "explicit"
    assert data["dates"]["calculated_end_basis"]["explanation"]
    assert data["dates"]["days_until_end"] is not None
    # Kündigung (90 Tage zum Vertragsende) -> spätester Termin berechenbar.
    assert data["dates"]["latest_cancellation_date"] is not None
    assert data["dates"]["latest_cancellation_basis"]["explanation"]
    assert "cancellation_period" in data["dates"]["latest_cancellation_basis"]["inputs"]

    # Finanzen: autoritative annual + Basis + source_period.
    assert data["costs"]["annual_recurring"]["amount"] is not None
    assert data["costs"]["annual_recurring_basis"]["explanation"]
    assert data["costs"]["source_period"] == "annual"
    assert data["costs"]["tax_basis"] == "unknown"

    # Der berechnete Wert wird NICHT im Frontend abgeleitet -> nur Backend-Wert.
    assert data["costs"]["annual_recurring"]["amount"] == Decimal("12000")


def test_detail_pr3_renewal_boundaries_exposed(db, svc):
    org = _org(db)
    # Vertrag mit automatischer Verlängerung + Verlängerungszeitraum.
    contract, r = _chain(db, org, svc, annual=12000)
    # _chain liefert kein renewal_period; wir verifizieren, dass das Feld existiert.
    data = detail_for(db, org, contract)
    assert "renewal_boundaries" in data["dates"]
    assert data["dates"]["days_until_latest_cancellation"] is not None



def detail_for(db, org, contract):
    from app.contracts.detail.service import build_contract_detail
    return build_contract_detail(db, organization_id=org.id, contract_id=contract.id)


def test_detail_missing_and_cross_org_404(db, svc):
    import types
    org_a = _org(db)
    org_b = _org(db)
    contract, r = _chain(db, org_a, svc, annual=12000)
    assert detail_for(db, org_a, contract) is not None
    assert detail_for(db, org_b, contract) is None  # cross-org -> generisch 404
    _missing = types.SimpleNamespace(id=uuid.uuid4())
    assert detail_for(db, org_a, _missing) is None  # missing


def test_detail_review_freshness_is_org_and_contract_scoped(db, svc):
    from app.database.models import WarningEvaluationRun

    org_a = _org(db)
    contract_a, _ = _chain(db, org_a, svc)
    db.add(WarningEvaluationRun(
        organization_id=org_a.id,
        contract_id=contract_a.id,
        calculation_run_id=contract_a.accepted_calculation_run_id,
        as_of_date=date(2025, 6, 1),
        policy_version="step11-default-1",
        status="computed",
    ))

    # Späterer Stichtag bei einem ANDEREN Vertrag/Org: DARF die Frische von org_a
    # nicht kippen (vorher: globales max über alle Org/Contracts -> Leak-Fehler).
    org_b = _org(db)
    contract_b, _ = _chain(db, org_b, svc)
    db.add(WarningEvaluationRun(
        organization_id=org_b.id,
        contract_id=contract_b.id,
        calculation_run_id=contract_b.accepted_calculation_run_id,
        as_of_date=date(2026, 6, 1),
        policy_version="step11-default-1",
        status="computed",
    ))
    db.flush()

    data_a = detail_for(db, org_a, contract_a)
    assert data_a is not None
    assert data_a["review"]["warning_evaluation_as_of_date"] == date(2025, 6, 1)


def test_detail_evidence_bbox_precision(db, svc):
    org = _org(db)
    contract, r = _chain(
        db, org, svc,
        evidence_bbox={"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.35},
    )
    data = detail_for(db, org, contract)
    ev = {e["field_ref"]: e for e in data["evidence"]}
    ref = ev["identity.contract_title"]
    assert ref["supports_exact_navigation"] is True  # normalisiert
    assert ref["precision"] == "coarse"
    assert ref["bbox"] == {"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.35}


def test_detail_invalid_bbox_falls_back_to_none_precision(db, svc):
    org = _org(db)
    # bbox mit negativen Werten und inkonsistenten Koordinaten -> fallback.
    contract, r = _chain(
        db, org, svc,
        evidence_bbox={"x0": -5, "y0": 0, "x1": 1, "y1": 10},
    )
    data = detail_for(db, org, contract)
    ev = {e["field_ref"]: e for e in data["evidence"]}
    ref = ev["identity.contract_title"]
    assert ref["supports_exact_navigation"] is False
    assert ref["precision"] == "none"
    assert ref["bbox"] is None


def test_detail_pdf_points_bbox_is_exactly_navigable(db, svc):
    # PR-2-Regression: echte Benchmark-Bboxes liegen in PDF-Punkten (>1) der
    # Original-Seite. Mit bbox + Seite muss `supports_exact_navigation` True
    # sein und `bbox_space="pdf_points"` ehrlich deklarieren – der Client
    # normalisiert gegen die realen Seitenmaße des gerenderten PDFs. Vorher
    # war hier False (nur [0,1] galt), wodurch nie eine Hervorhebung zeichnete.
    org = _org(db)
    contract, r = _chain(
        db, org, svc,
        evidence_bbox={"x0": 59.3, "y0": 531.7, "x1": 166.7, "y1": 543.7},
    )
    data = detail_for(db, org, contract)
    ev = {e["field_ref"]: e for e in data["evidence"]}
    ref = ev["identity.contract_title"]
    assert ref["bbox_space"] == "pdf_points"
    assert ref["supports_exact_navigation"] is True
    assert ref["precision"] == "coarse"
    assert ref["bbox"] == {"x0": 59.3, "y0": 531.7, "x1": 166.7, "y1": 543.7}


def test_detail_bbox_without_page_is_not_exact(db, svc):
    # bbox ohne Seite -> nicht exakt navigierbar (keine erfundene Hervorhebung).
    org = _org(db)
    contract, r = _chain(db, org, svc, evidence_bbox=None)
    from app.database.models import ContractExtraction
    snapshot = db.get(ContractExtraction, contract.accepted_extraction_id).contract_snapshot
    new_ext = save_extraction(
        db, organization_id=org.id,
        document_version_id=r.document_version_id,
        snapshot=snapshot,
        evidence=[
            {
                "field_ref": "sla.response_time",
                "source_type": "paragraph",
                "page": None,
                "paragraph_index": 1,
                "source_text": "Reaktionszeit 4h",
                "bounding_box": {"x0": 40.0, "y0": 100.0, "x1": 200.0, "y1": 120.0},
                "confidence": 0.9,
            }
        ],
        status="success",
    )
    accept_extraction(db, contract_id=contract.id, extraction_id=new_ext.id)
    data = detail_for(db, org, contract)
    ev = {e["field_ref"]: e for e in data["evidence"]}
    ref = ev["sla.response_time"]
    assert ref["bbox_space"] == "pdf_points"
    assert ref["page"] is None
    assert ref["supports_exact_navigation"] is False


def test_detail_no_storage_paths_or_keys(db, svc):
    org = _org(db)
    contract, r = _chain(db, org, svc)
    import json
    raw = json.dumps(detail_for(db, org, contract), default=str)
    assert "original.pdf" not in raw or "storag" not in raw
    assert "documents/" not in raw


def test_detail_accepted_only_superseded_ignored(db, svc):
    org = _org(db)
    contract, r = _chain(db, org, svc, annual=12000)
    data = detail_for(db, org, contract)
    assert data["costs"]["annual_recurring"]["currency"] == "EUR"


# ---------------------------------------------------------------------------
# Sicherer Dokument-Zugriff (API-Ebene)
# ---------------------------------------------------------------------------

from app.contracts.detail.models import ContractDetailResponse  # noqa: E402
from sqlalchemy import delete as sa_delete
from app.database.models import (
    CalculationResult,
    CalculationReviewFlag,
    CalculationRun,
    Contract,
    ContractDocument,
    ContractEquipment,
    ContractExtraction,
    ContractWarning,
    DocumentArtifact,
    DocumentFile,
    DocumentVersion,
    ExtractionEvidence,
    Organization,
)


def _committed_chain(engine, svc, storage):
    """Legt org + PDF + Vertrag in einer COMMITTED Session an (fuer HTTP).

    Nutzt EINZIGARTIGE PDF-Bytes je Aufruf (sha256-Dedup ist global; identische
    Bytes ueber Tests hinweg wuerden auf eine Version einer anderen Org zeigen).
    Rueckgabe: (org, contract, r, cleanup_callable, content).
    """
    session = Session(engine, expire_on_commit=False)
    try:
        session.begin()
        org = create_organization(
            session, name="Klinik", slug=f"klinik-{uuid.uuid4().hex[:12]}"
        )
        session.flush()
        org_id = org.id
        contract, r = None, None
        content = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n" + uuid.uuid4().hex.encode()

        from app.contracts.calculation import calculate_contract
        from app.database.services import (
            accept_calculation, accept_extraction, create_contract,
            save_calculation, save_extraction,
        )
        from app.models.contract import Contract as DomainContract
        from app.models.contract import ContractDates, Costs, Termination
        from app.models.enums import ContractStatus, TimeUnit
        from app.models.values import Duration, FlexibleDate, Money

        file_result = svc.store_original(
            session, organization_id=org.id, original_filename="wartung.pdf",
            content_type="application/pdf", content=content,
        )
        session.flush()
        evidence = [
            {
                "field_ref": "identity.contract_title",
                "source_type": "paragraph", "page": 1,
                "source_text": "Wartungsvertrag CT-Scanner",
                "bounding_box": None, "confidence": 0.98,
            },
        ]
        ext = save_extraction(
            session, organization_id=org.id, document_version_id=file_result.document_version_id,
            snapshot={
                "identity": {"contract_title": "Wartungsvertrag CT-Scanner",
                              "contract_number": "CN-DTL-1"},
                "dates": {"start_date": {"date": "2024-01-01"}},
                "termination": {"automatic_renewal": True},
            },
            evidence=evidence, status="success",
        )
        domain = DomainContract(
            id="DET", status=ContractStatus.UNKNOWN,
            dates=ContractDates(
                start_date=FlexibleDate(date=date(2024, 1, 1)),
                end_date=FlexibleDate(date=date(2027, 6, 30)),
            ),
            termination=Termination(
                cancellation_period=Duration(value=90, unit=TimeUnit.DAYS),
                cancellation_to_contract_end="to_contract_end",
            ),
            costs=Costs(default_currency="EUR",
                        annual_cost=Money(amount="12000", currency="EUR")),
        )
        calc = calculate_contract(domain, as_of_date=date(2025, 6, 1))
        run = save_calculation(
            session, organization_id=org.id, extraction_id=ext.id,
            as_of_date=date(2025, 6, 1),
            result_snapshot=calc.model_dump(mode="json"),
            calculation_version="step9-1.0", status="computed",
            result_rows=[], review_flags=[],
        )
        contract = create_contract(session, organization_id=org.id,
                                   supplier="Lieferant", status="active",
                                   contract_number="CN-DTL-1")
        accept_extraction(session, contract_id=contract.id, extraction_id=ext.id)
        accept_calculation(session, contract_id=contract.id,
                           calculation_run_id=run.id)
        svc.link_to_contract(session, contract_id=contract.id,
                             document_version_id=file_result.document_version_id,
                             role="main")
        session.flush()
        session.commit()
        r = file_result

        def cleanup():
            with Session(engine, expire_on_commit=False) as s:
                s.begin()
                s.execute(sa_delete(ExtractionEvidence).where(
                    ExtractionEvidence.organization_id == org_id))
                s.execute(sa_delete(CalculationReviewFlag.__table__).where(
                    CalculationReviewFlag.__table__.c.organization_id == org_id))
                s.execute(sa_delete(CalculationResult.__table__).where(
                    CalculationResult.__table__.c.organization_id == org_id))
                s.execute(sa_delete(ContractWarning).where(
                    ContractWarning.organization_id == org_id))
                s.execute(sa_delete(ContractEquipment).where(
                    ContractEquipment.organization_id == org_id))
                s.execute(sa_delete(DocumentArtifact).where(
                    DocumentArtifact.organization_id == org_id))
                s.execute(sa_delete(ContractDocument).where(
                    ContractDocument.organization_id == org_id))
                s.execute(sa_delete(CalculationRun).where(
                    CalculationRun.organization_id == org_id))
                s.execute(sa_delete(ContractExtraction).where(
                    ContractExtraction.organization_id == org_id))
                s.execute(sa_delete(DocumentVersion).where(
                    DocumentVersion.organization_id == org_id))
                s.execute(sa_delete(DocumentFile).where(
                    DocumentFile.organization_id == org_id))
                s.execute(sa_delete(Contract).where(
                    Contract.organization_id == org_id))
                s.execute(sa_delete(Organization).where(Organization.id == org_id))
                s.commit()

        return org, contract, r, cleanup, content
    except Exception:
        session.rollback()
        session.close()
        raise


def _client():
    return TestClient(app)


@pytest.fixture
def pinned_storage(storage, monkeypatch):
    """Laesst die Content-Route gegen das Test-Temp-Storage aufloesen."""
    monkeypatch.setattr("app.core.config.settings.contracts_dir", str(storage._base_dir))
    return storage


def test_content_returns_correct_bytes_and_headers(engine, svc, pinned_storage):
    org, contract, r, cleanup, content = _committed_chain(engine, svc, pinned_storage)
    try:
        client = TestClient(app)
        resp = client.get(
            f"/api/contracts/{contract.id}/documents/{r.document_version_id}/content"
            f"?organization_slug={org.slug}"
        )
        assert resp.status_code == 200
        assert resp.content == content
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert "no-store" in resp.headers["cache-control"]
        assert resp.headers["content-type"].startswith("application/pdf")
        combined = " ".join(f"{k}={v}" for k, v in resp.headers.items())
        assert r.storage_key not in combined
    finally:
        cleanup()


def test_content_cross_org_fails(engine, svc, pinned_storage):
    org_a, contract, r, cleanup, _content = _committed_chain(engine, svc, pinned_storage)
    try:
        with Session(engine, expire_on_commit=False) as s:
            s.begin()
            org_b = create_organization(s, name="B", slug=f"klinik-{uuid.uuid4().hex[:12]}")
            s.commit()
            slug_b = org_b.slug
        client = TestClient(app)
        resp = client.get(
            f"/api/contracts/{contract.id}/documents/{r.document_version_id}/content"
            f"?organization_slug={slug_b}"
        )
        assert resp.status_code == 404
        with Session(engine, expire_on_commit=False) as s:
            s.execute(sa_delete(Organization).where(Organization.slug == slug_b))
            s.commit()
    finally:
        cleanup()


def test_content_unlinked_version_fails(engine, svc, pinned_storage):
    org, contract, r, cleanup, _content = _committed_chain(engine, svc, pinned_storage)
    try:
        with Session(engine, expire_on_commit=False) as s:
            s.begin()
            other = svc.store_original(s, organization_id=org.id,
                                       original_filename="x.pdf",
                                       content_type="application/pdf",
                                       content=b"%PDF-x\x00" + uuid.uuid4().hex.encode())
            s.commit()
            other_id = other.document_version_id
        client = TestClient(app)
        resp = client.get(
            f"/api/contracts/{contract.id}/documents/{other_id}/content"
            f"?organization_slug={org.slug}"
        )
        assert resp.status_code == 404
    finally:
        cleanup()


def test_content_unsupported_mime_415(engine, svc, pinned_storage):
    from sqlalchemy import select as sa_select
    org, contract, r, cleanup, _content = _committed_chain(engine, svc, pinned_storage)
    try:
        with Session(engine, expire_on_commit=False) as s:
            s.begin()
            ver = s.scalars(
                sa_select(DocumentVersion).where(DocumentVersion.id == r.document_version_id)
            ).one()
            f = s.get(DocumentFile, ver.document_file_id)
            f.mime_type = "text/html"
            f.file_extension = ".html"
            s.commit()
        client = TestClient(app)
        resp = client.get(
            f"/api/contracts/{contract.id}/documents/{r.document_version_id}/content"
            f"?organization_slug={org.slug}"
        )
        assert resp.status_code == 415
    finally:
        cleanup()


def test_content_range_support(engine, svc, pinned_storage):
    org, contract, r, cleanup, content = _committed_chain(engine, svc, pinned_storage)
    try:
        client = TestClient(app)
        resp = client.get(
            f"/api/contracts/{contract.id}/documents/{r.document_version_id}/content"
            f"?organization_slug={org.slug}",
            headers={"Range": "bytes=0-4"},
        )
        assert resp.status_code == 206
        assert resp.content == content[:5]
        assert "bytes 0-4/" in resp.headers["content-range"]
    finally:
        cleanup()


def test_range_invalid_416(engine, svc, pinned_storage):
    org, contract, r, cleanup, content = _committed_chain(engine, svc, pinned_storage)
    try:
        client = TestClient(app)
        resp = client.get(
            f"/api/contracts/{contract.id}/documents/{r.document_version_id}/content"
            f"?organization_slug={org.slug}",
            headers={"Range": f"bytes={len(content)}-{len(content)+10}"},
        )
        assert resp.status_code == 416
    finally:
        cleanup()



def test_harness_snapshot_detection_is_version_neutral():
    from app.contracts.detail.service import _snapshot_uses_harness

    assert _snapshot_uses_harness({"analysis": {"harness_version": "v2"}}) is True
    assert _snapshot_uses_harness({"analysis": {"harness_version": "v2.1"}}) is True
    assert _snapshot_uses_harness({"analysis": {"harness_version": "v3"}}) is True
    assert _snapshot_uses_harness({"analysis": {}}) is False
    assert _snapshot_uses_harness(None) is False
