"""Import-Assistent: Erfassungsart, Sammelziel, manuelle Erfassung und Prüfmodus je Vertrag."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import contract_register, documents
from app.contracts.review import service as review_service
from app.core.scope_context import ScopeContext
from app.database.models import Contract
from app.database.models.organization import Organization
from app.database.models.organization_structure import Hospital
from app.database.session import create_session
from app.documents.processing import DocumentProcessingService
from tests.test_register_gaps import _seed


def _setup(monkeypatch, *, role="admin"):
    slug, ids = _seed()
    hospital_id = uuid4()
    with create_session() as session:
        session.add(Hospital(id=hospital_id, organization_id=ids["org"], name="Klinikum A", code=f"A-{slug[-6:]}"))
        session.commit()
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role=role, is_developer=False, display_name="Admin")
    monkeypatch.setattr(documents, "current_actor", lambda *_args: actor)
    monkeypatch.setattr(contract_register, "current_actor", lambda *_args: actor)
    monkeypatch.setattr(contract_register, "current_scope_context", lambda: ScopeContext())
    app = FastAPI()
    app.include_router(documents.router)
    return slug, ids, hospital_id, actor, TestClient(app)


def _fake_ai_import(ids, created):
    """Ersetzt die KI-Pipeline: legt je Datei einen Vertrag an (wie ein erfolgreicher Import)."""
    def process(**kwargs):
        contract_id = uuid4()
        with create_session() as session:
            session.add(Contract(id=contract_id, organization_id=ids["org"], supplier="Synthetisch", scope_type="organization"))
            session.commit()
        created.append(contract_id)
        return SimpleNamespace(
            document_id="", document_version_id="", sha256="", original_filename=kwargs["original_filename"],
            status="imported", contract_id=str(contract_id), analysis_status="success", requires_review=True, message=None,
        )
    return process


PDF = ("files", ("vertrag.pdf", b"%PDF-1.4 synthetic", "application/pdf"))


def test_intake_mode_is_validated_and_recorded(monkeypatch):
    slug, ids, hospital_id, _actor, client = _setup(monkeypatch)
    created: list[UUID] = []
    monkeypatch.setattr(documents, "_processing_service", SimpleNamespace(process=_fake_ai_import(ids, created)))
    query = {"organization_slug": slug}

    assert client.post("/api/documents/import", params=query, files=[PDF], data={"intake_mode": "magic"}).status_code == 422
    # Automatische Übernahme ist erst nach Freigabe in der Verwaltung möglich.
    blocked = client.post("/api/documents/import", params=query, files=[PDF], data={"intake_mode": "ai_direct"})
    assert blocked.status_code == 422 and "nicht freigegeben" in blocked.json()["detail"]
    assert created == []

    reviewed = client.post("/api/documents/import", params=query, files=[PDF], data={"intake_mode": "ai_human_review"})
    assert reviewed.status_code == 200, reviewed.text
    with create_session() as session:
        session.get(Organization, ids["org"]).review_mode = "auto_noncritical"
        session.commit()
    direct = client.post("/api/documents/import", params=query, files=[PDF], data={"intake_mode": "ai_direct"})
    assert direct.status_code == 200, direct.text

    with create_session() as session:
        modes = [session.get(Contract, cid).intake_mode for cid in created]
        assert modes == ["ai_human_review", "ai_direct"]
        # Prüfmodus je Vertrag: ausdrücklich „mit manueller Prüfung“ importiert -> nie automatisch.
        assert review_service.auto_accept_allowed(session, ids["org"], created[0]) is False
        assert review_service.auto_accept_allowed(session, ids["org"], created[1]) is True


def test_batch_with_destination_requires_explicit_confirmation(monkeypatch):
    slug, ids, hospital_id, _actor, client = _setup(monkeypatch)
    created: list[UUID] = []
    monkeypatch.setattr(documents, "_processing_service", SimpleNamespace(process=_fake_ai_import(ids, created)))
    query = {"organization_slug": slug}
    two = [PDF, ("files", ("anlage.pdf", b"%PDF-1.4 other", "application/pdf"))]
    data = {"intake_mode": "ai_human_review", "assignment_hospital_id": str(hospital_id)}

    refused = client.post("/api/documents/import", params=query, files=two, data=data)
    assert refused.status_code == 422 and "alle Dateien" in refused.json()["detail"]
    assert created == []
    accepted = client.post("/api/documents/import", params=query, files=two, data={**data, "same_destination_confirmed": "true"})
    assert accepted.status_code == 200, accepted.text
    assert len(created) == 2


def test_manual_capture_creates_contract_without_analysis(monkeypatch):
    slug, ids, hospital_id, _actor, client = _setup(monkeypatch)
    calls = []

    def manual(**kwargs):
        calls.append(kwargs["original_filename"])
        with create_session() as session:
            contract = kwargs["create_contract"](session)
            session.commit()
            contract_id = str(contract.id)
        return SimpleNamespace(
            document_id="", document_version_id="", sha256="", original_filename=kwargs["original_filename"],
            status="imported", contract_id=contract_id, analysis_status=None, requires_review=False,
            message="Original gespeichert – die Vertragsdaten werden manuell erfasst (keine KI-Analyse).",
        )

    def no_ai(**_kwargs):
        raise AssertionError("Bei manueller Erfassung darf keine KI-Analyse laufen.")

    monkeypatch.setattr(documents, "_processing_service", SimpleNamespace(process=no_ai, import_for_manual_capture=manual))
    response = client.post(
        "/api/documents/import", params={"organization_slug": slug},
        files=[("files", ("Wartung Impella 2026.pdf", b"%PDF-1.4 manual", "application/pdf"))],
        data={"intake_mode": "manual", "assignment_hospital_id": str(hospital_id)},
    )
    assert response.status_code == 200, response.text
    result = response.json()["documents"][0]
    assert result["status"] == "imported" and result["analysis_status"] is None and calls == ["Wartung Impella 2026.pdf"]
    with create_session() as session:
        contract = session.get(Contract, UUID(result["contract_id"]))
        assert contract.intake_mode == "manual"
        assert contract.short_description == "Wartung Impella 2026"
        assert contract.hospital_id == hospital_id
        assert contract.business_status == "in_arbeit" and contract.register_number


def test_manual_capture_requires_create_permission(monkeypatch):
    slug, _ids, _hospital_id, actor, client = _setup(monkeypatch, role="reviewer")
    monkeypatch.setattr(documents, "_processing_service", SimpleNamespace())
    response = client.post("/api/documents/import", params={"organization_slug": slug}, files=[PDF], data={"intake_mode": "manual"})
    assert response.status_code == 403


def test_manual_capture_duplicate_creates_no_contract():
    service = DocumentProcessingService.__new__(DocumentProcessingService)
    duplicate = SimpleNamespace(status="duplicate")
    service._persist_document = lambda *args: (duplicate, uuid4(), "key")

    def create_contract(_session):
        raise AssertionError("Dublette darf keinen Vertrag anlegen.")

    result = service.import_for_manual_capture(
        organization_slug="x", original_filename="a.pdf", content_type="application/pdf", content=b"x",
        create_contract=create_contract, added_by_name="Admin",
    )
    assert result is duplicate


def test_processing_jobs_hide_raw_errors_from_non_admins(monkeypatch):
    from app.api.routes import processing_jobs
    from app.database.models import ProcessingRun

    slug, ids = _seed()
    with create_session() as session:
        rows = session.scalars(select(ProcessingRun).limit(0)).all()  # Schema vorhanden
        assert rows == []
    row = SimpleNamespace(
        id=uuid4(), document_version_id=uuid4(), status="failed", provider=None, provider_version=None, schema_version=None,
        ocr_engine=None, ocr_engine_version=None, do_ocr=False, do_table_structure=False, geometry_provider=None,
        processing_duration=None, message="Traceback intern", error="RuntimeError: /pfad/geheim", created_at=None,
    )
    hidden = processing_jobs._serialize(row, None, diagnostics=False, origin=("c-1", "vertrag.pdf"))
    assert hidden["error"] is None and hidden["message"] is None
    assert hidden["result_label_de"] == "Verarbeitung fehlgeschlagen."
    assert (hidden["contract_id"], hidden["original_filename"]) == ("c-1", "vertrag.pdf")
    shown = processing_jobs._serialize(row, None, diagnostics=True)
    assert shown["error"].startswith("RuntimeError")

    viewer = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role="viewer", is_developer=False)
    monkeypatch.setattr(processing_jobs, "current_actor", lambda *_args: viewer)
    assert processing_jobs._diagnostics_allowed(None, slug) is False
    viewer.role = "admin"
    assert processing_jobs._diagnostics_allowed(None, slug) is True
