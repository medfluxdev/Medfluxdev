"""Fokussierte Tests – Customer-Demo-Readiness (blind Ingestion + faktgenaue
menschliche Verifikation + Audit + Demo-Workspace).

Teil 1: Pure Logik (Material-Fakt-Register, Zustands-Ableitung).
Teil 2: Integration (PostgreSQL, committed chain):
  - Faktgenaues Prüfen (Bestätigen/Korrigieren/Wiederöffnen, append-only)
  - Vertragsreview (Abschluss-Gate, Änderung nach Prüfung)
  - Demo-Workspace (Enable/Disable-Isolation)
  - Failure-safe Import (Platzhalter-Vertrag + Retry + Verwaist)

Keine volle Regression, keine OCR/LLM, KEINE manuell gepflegten Testartefakte.
Ein Bugfix hier testet ausschließlich diese Befähigung.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
import sys  # noqa: E402
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))


# =========================================================================
# Teil 1 – Pure Logik
# =========================================================================


class TestMaterialRegistry:
    def test_all_material_facts_have_german_labels(self):
        from app.contracts.review.material import MATERIAL_FACTS, fact_label

        keys = [k for k, _, _ in MATERIAL_FACTS]
        assert keys
        assert len(keys) == len(set(keys))
        for key in keys:
            label = fact_label(key)
            assert label and label != key

    def test_present_detection_uses_value_not_struct(self):
        from app.contracts.review.material import material_report

        r = {
            "identity": {"contract_number": "AX-1"},
            "costs": {
                "monthly_recurring": {"amount": "5916.67", "currency": "EUR"},
                "tax_breakdown": {"monthly_net": "5916.67", "rate_percent": 19.0},
            },
        }
        report = material_report(r)
        assert report["identity.contract_number"]["present"] is True
        assert report["costs.monthly_net"]["present"] is True
        assert report["costs.vat_rate"]["value"] == 19.0
        assert report["equipment.serial"]["present"] is False

    def test_empty_detail_is_neutral(self):
        from app.contracts.review.material import material_report

        report = material_report({})
        assert all(not v["present"] for v in report.values())


class TestReviewSummary:
    def test_counts_confirmed_and_corrected_only(self):
        from app.contracts.review.service import build_review_summary

        states = [
            {"present": True, "state": "confirmed"},
            {"present": True, "state": "corrected"},
            {"present": True, "state": "unreviewed"},
            {"present": True, "state": "voided"},
            {"present": False, "state": "confirmed"},
        ]
        s = build_review_summary(states)
        assert s["relevant_count"] == 3  # voided & not present raus
        assert s["reviewed_count"] == 2
        assert s["unresolved_count"] == 1


# =========================================================================
# Teil 2 – Integration (PostgreSQL)
# =========================================================================


@pytest.fixture(scope="module")
def engine():
    from app.core.config import settings

    eng = create_engine(settings.database_url, pool_pre_ping=True)
    yield eng
    eng.dispose()


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
        pytest.skip("PostgreSQL nicht erreichbar – Integration übersprungen")
    yield


def _build_committed_chain(engine, svc):
    """Committed: org + PDF + Extraktion + Berechnung + akzeptierter Vertrag."""
    from app.database.services import (
        accept_calculation,
        accept_extraction,
        create_contract,
        create_organization,
        save_calculation,
        save_extraction,
    )
    from app.contracts.calculation import calculate_contract
    from app.models.contract import Contract as DomainContract
    from app.models.contract import ContractDates, Costs, Termination
    from app.models.enums import ContractStatus
    from app.models.values import Duration, FlexibleDate, Money

    session = Session(engine, expire_on_commit=False)
    try:
        session.begin()
        org = create_organization(
            session, name="Klinik", slug=f"uat-a-{uuid.uuid4().hex[:12]}"
        )
        session.flush()
        content = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n" + uuid.uuid4().hex.encode()
        r = svc.store_original(
            session,
            organization_id=org.id,
            original_filename="demo.pdf",
            content_type="application/pdf",
            content=content,
        )
        session.flush()
        evidence = [
            {"field_ref": "identity.contract_number", "source_type": "paragraph",
             "page": 1, "source_text": "Vertragsnummer: DEMO-1", "confidence": 0.95},
            {"field_ref": "costs.monthly_net", "source_type": "paragraph",
             "page": 2, "source_text": "Mtl. Preis netto: 1.200,00", "confidence": 0.9},
        ]
        ext = save_extraction(
            session, organization_id=org.id, document_version_id=r.document_version_id,
            snapshot={
                "identity": {"contract_number": "DEMO-1", "supplier": "Demo GmbH"},
                "dates": {"start_date": {"date": "2025-01-01", "condition": None}},
                "costs": {"monthly_cost": {"amount": 1200.00, "period": "monthly",
                                            "currency": "EUR"}},
            },
            evidence=evidence, status="success",
        )
        domain = DomainContract(
            id="DEMO1", status=ContractStatus.ACTIVE,
            dates=ContractDates(start_date=FlexibleDate(date=date(2025, 1, 1), condition=None)),
            termination=Termination(automatic_renewal=False),
            costs=Costs(default_currency="EUR",
                        monthly_cost=Money(amount=1200.00, currency="EUR", period="monthly")),
        )
        calc = calculate_contract(domain, as_of_date=date(2025, 6, 1))
        run = save_calculation(
            session, organization_id=org.id, extraction_id=ext.id,
            as_of_date=date(2025, 6, 1),
            result_snapshot=calc.model_dump(mode="json"),
            calculation_version="step9-1.0", status="computed",
            result_rows=[], review_flags=[],
        )
        contract = create_contract(
            session, organization_id=org.id, supplier="Demo GmbH",
            status="active", contract_number="DEMO-1",
        )
        accept_extraction(session, contract_id=contract.id, extraction_id=ext.id)
        accept_calculation(session, contract_id=contract.id, calculation_run_id=run.id)
        svc.link_to_contract(
            session, contract_id=contract.id,
            document_version_id=r.document_version_id, role="main",
        )
        session.commit()
        return org.slug, contract.id, str(r.document_version_id)
    finally:
        session.close()


def _temp_env():
    import tempfile

    from app.documents.persistence import DocumentPersistenceService
    from app.documents.storage import DocumentStorage

    d = tempfile.TemporaryDirectory()
    storage = DocumentStorage(Path(d.name) / "contracts")
    svc = DocumentPersistenceService(storage=storage)
    return d, storage, svc



def _confirm_all_critical_facts(client: TestClient, org_slug: str, contract_id) -> None:
    detail = client.get(
        f"/api/contracts/{contract_id}?organization_slug={org_slug}"
    )
    assert detail.status_code == 200, detail.text
    for state in detail.json().get("fact_review_states", []):
        if not state.get("present") or not state.get("is_critical"):
            continue
        if state.get("state") in {"confirmed", "corrected", "voided"}:
            continue
        response = client.post(
            f"/api/contracts/{contract_id}/fact-reviews?organization_slug={org_slug}",
            json={
                "fact_key": state["fact_key"],
                "action": "confirmed",
                "reviewer_display_name": "M. Kraft",
            },
        )
        assert response.status_code == 200, response.text


def import_app():
    from app.main import app

    return app


class TestFactReviewFlow:
    def test_confirm_keeps_value_and_identity_is_manual(self, engine):
        d, storage, svc = _temp_env()
        try:
            org_slug, contract_id, _ = _build_committed_chain(engine, svc)
            client = TestClient(import_app())
            r = client.post(
                f"/api/contracts/{contract_id}/fact-reviews?organization_slug={org_slug}",
                json={
                    "fact_key": "identity.contract_number",
                    "action": "confirmed",
                    "reviewer_display_name": "M. Kraft",
                    "note": "laut Original geprüft",
                },
            )
            assert r.status_code == 200, r.text
            j = r.json()
            st = next(s for s in j["fact_review_states"] if s["fact_key"] == "identity.contract_number")
            assert st["state"] == "confirmed"
            assert st["state_label_de"] == "Geprüft und bestätigt"
            assert st["effective_value"] == "DEMO-1"  # Bestätigen ändert NICHT
            assert st["reviewer_display_name"] == "M. Kraft"
            assert len(j["fact_reviews"]) == 1
            e = j["fact_reviews"][0]
            assert e["reviewer_identity_type"] == "manual_unverified"
            assert e["authenticated_actor_id"] is None
            assert e["original_value"] == "DEMO-1"
            # Vertragsreview bleibt startbar und zählt als geprüft
            assert j["contract_review"]["relevant_count"] >= 1
        finally:
            d.cleanup()

    def test_corrected_value_differs_adds_audit(self, engine):
        d, storage, svc = _temp_env()
        try:
            org_slug, contract_id, _ = _build_committed_chain(engine, svc)
            client = TestClient(import_app())
            r = client.post(
                f"/api/contracts/{contract_id}/fact-reviews?organization_slug={org_slug}",
                json={
                    "fact_key": "costs.monthly_net",
                    "action": "corrected",
                    "reviewer_display_name": "M. Kraft",
                    "corrected_value": "1200.50",
                    "note": "Handauszug 1.200,50",
                },
            )
            assert r.status_code == 200, r.text
            j = r.json()
            st = next(s for s in j["fact_review_states"] if s["fact_key"] == "costs.monthly_net")
            assert st["state"] == "corrected"
            assert st["effective_value"] == "1200.50"
            assert st["original_value"] == "1200.00"
            e = j["fact_reviews"][0]
            assert e["original_value"] == "1200.00"
            assert e["previous_effective_value"] == "1200.00"
            assert e["new_effective_value"] == "1200.50"

        finally:
            d.cleanup()

    def test_reopen_preserves_audit(self, engine):
        d, storage, svc = _temp_env()
        try:
            org_slug, contract_id, _ = _build_committed_chain(engine, svc)
            client = TestClient(import_app())
            client.post(
                f"/api/contracts/{contract_id}/fact-reviews?organization_slug={org_slug}",
                json={"fact_key": "identity.supplier", "action": "confirmed",
                      "reviewer_display_name": "M"},
            )
            r = client.post(
                f"/api/contracts/{contract_id}/fact-reviews?organization_slug={org_slug}",
                json={"fact_key": "identity.supplier", "action": "reopened",
                      "reviewer_display_name": "M", "note": "erneute Prüfung"},
            )
            j = r.json()
            st = next(s for s in j["fact_review_states"] if s["fact_key"] == "identity.supplier")
            # UAT Re-Test-Fix (Defect Batch F): Wieder geöffnet = nicht mehr
            # bestätigt. Ohne evidence-getragenen Beleg (Test-Kette trägt keinen
            # Recovered-Ref) bleibt der Fakt ehrlich „Zu prüfen".
            assert st["state"] in ("unreviewed", "needs_review")
            assert len(j["fact_reviews"]) == 2
            assert {e["action"] for e in j["fact_reviews"]} == {"reopened", "confirmed"}
        finally:
            d.cleanup()

    def test_complete_review_requires_acknowledgement(self, engine):
        d, storage, svc = _temp_env()
        try:
            org_slug, contract_id, _ = _build_committed_chain(engine, svc)
            client = TestClient(import_app())
            _confirm_all_critical_facts(client, org_slug, contract_id)
            r_nack = client.post(
                f"/api/contracts/{contract_id}/review/complete?organization_slug={org_slug}",
                json={"reviewer_display_name": "M. Kraft"},
            )
            assert r_nack.status_code == 422
            assert "ungeprüft" in r_nack.json()["detail"]
            r_ack = client.post(
                f"/api/contracts/{contract_id}/review/complete?organization_slug={org_slug}",
                json={
                    "reviewer_display_name": "M. Kraft",
                    "acknowledge_unreviewed": True,
                    "note": "Rest bewusst akzeptiert",
                },
            )
            assert r_ack.status_code == 200, r_ack.text
            j = r_ack.json()
            assert j["contract_review"]["status"] == "reviewed"
            assert j["contract_review"]["status_label_de"] == "Geprüft"
            assert j["contract_review"]["reviewed_at"]
        finally:
            d.cleanup()

    def test_correction_after_review_marks_changed(self, engine):
        d, storage, svc = _temp_env()
        try:
            org_slug, contract_id, _ = _build_committed_chain(engine, svc)
            client = TestClient(import_app())
            _confirm_all_critical_facts(client, org_slug, contract_id)
            client.post(
                f"/api/contracts/{contract_id}/review/complete?organization_slug={org_slug}",
                json={"reviewer_display_name": "M", "acknowledge_unreviewed": True,
                      "note": "alles akzeptiert"},
            )
            r = client.post(
                f"/api/contracts/{contract_id}/fact-reviews?organization_slug={org_slug}",
                json={"fact_key": "identity.supplier", "action": "corrected",
                      "reviewer_display_name": "M", "corrected_value": "Demo GmbH (überarbeitet)"},
            )
            j = r.json()
            assert j["contract_review"]["status"] == "changed_after_review"
            assert j["contract_review"]["status_label_de"] == "Änderung nach Prüfung"
            assert j["contract_review"]["changed_noted_at"]
        finally:
            d.cleanup()


class TestNoDemoWorkspace:
    def test_demo_workspace_runtime_is_removed(self, engine):
        d, storage, svc = _temp_env()
        try:
            org_slug, contract_id, _ = _build_committed_chain(engine, svc)
            client = TestClient(import_app())

            before = client.get(
                f"/api/contracts?organization_slug={org_slug}&page_size=25"
            )
            assert before.status_code == 200
            assert len(before.json()["items"]) == 1

            assert client.post("/api/demo/workspace/enable").status_code == 404
            assert client.post("/api/demo/workspace/disable").status_code == 404

            after = client.get(
                f"/api/contracts?organization_slug={org_slug}&page_size=25"
            )
            assert after.status_code == 200
            assert len(after.json()["items"]) == 1

            detail = client.get(
                f"/api/contracts/{contract_id}?organization_slug={org_slug}"
            )
            assert detail.status_code == 200
        finally:
            d.cleanup()


class TestFailureSafeImport:
    def _svc_with_fakes(self, storage, persistence):
        from app.documents.processing import DocumentProcessingService

        svc = DocumentProcessingService(storage=storage, persistence=persistence)
        return svc

    def test_failed_analysis_placeholder_then_retry_success_orphans(self, engine):
        import tempfile

        from app.ai.contract_extractor import ContractAnalysisResult
        from app.documents.extraction.schemas import (
            ExtractionStatus,
            ExtractionUnit,
            FileType,
            SourceType,
            TextExtractionResult,
            UnitMethod,
        )
        from app.documents.persistence import DocumentPersistenceService
        from app.documents.processing import DocumentProcessingService
        from app.documents.storage import DocumentStorage
        from app.database.models import Contract, ContractDocument

        with tempfile.TemporaryDirectory() as d:
            storage = DocumentStorage(Path(d) / "contracts")
            persistence = DocumentPersistenceService(storage=storage)
            svc = DocumentProcessingService(storage=storage, persistence=persistence)

            # Deterministischer Fake: erste Analyse schlägt fehl, zweite gelingt.
            calls = {"n": 0}
            base_content = (
                "SIEMENS Demo-Vertrag\nVertragsnummer: DEMO-RETRY\n"
                "Mtl. Preis netto: 1.200,00 zzgl. 19% MwSt.\n"
            )

            async def fake_analyze(extraction):
                calls["n"] += 1
                if calls["n"] == 1:
                    return ContractAnalysisResult(
                        document_id=extraction.document_id,
                        status=ExtractionStatus.FAILED,
                        contract=None,
                        error="(Ollama) connection refused - Modell nicht verfügbar",
                        message="Lokale KI nicht verfügbar.",
                    )
                from app.models.contract import Contract as DomainContract
                from app.models.contract import ContractDates, Costs, Termination
                from app.models.enums import ContractStatus
                from app.models.values import Duration, FlexibleDate, Money

                contract = DomainContract(
                    id="DEMO-RETRY", status=ContractStatus.ACTIVE,
                    dates=ContractDates(
                        start_date=FlexibleDate(date=date(2025, 1, 1), condition=None)
                    ),
                    termination=Termination(automatic_renewal=False),
                    costs=Costs(
                        default_currency="EUR",
                        monthly_cost=Money(amount=1200.00, currency="EUR", period="monthly"),
                    ),
                )
                return ContractAnalysisResult(
                    document_id=extraction.document_id,
                    status=ExtractionStatus.SUCCESS,
                    validation_status="valid",
                    contract=contract,
                    requires_review=False,
                )

            if svc._analysis is None:
                from types import SimpleNamespace
                svc._analysis = SimpleNamespace(analyze=fake_analyze)
            else:
                svc._analysis.analyze = fake_analyze

            def fake_build_canonical(stored, path):
                extraction = TextExtractionResult(
                    document_id=stored.document_id,
                    file_type=FileType.PDF,
                    extraction_status=ExtractionStatus.SUCCESS,
                    page_count=1,
                    total_characters=len(base_content),
                    text_available=True,
                    units=[
                        ExtractionUnit(
                            source_type=SourceType.PAGE,
                            index=0,
                            text=base_content,
                            method=UnitMethod.TEXT,
                        )
                    ],
                )
                canonical = None
                return canonical, extraction

            svc._build_canonical = fake_build_canonical
            svc._persist_canonical_artifact = lambda **_: None

            org_slug = f"uat-a-{uuid.uuid4().hex[:12]}"
            content = b"%PDF-1.4\n1 0 obj<></endobj>\n%%EOF\n" + b"DEMO"

            org_session = Session(engine, expire_on_commit=False)
            org_session.begin()
            from app.database.services import create_organization as _create_org

            with Session(engine, expire_on_commit=False) as org_session:
                org_session.begin()
                _create_org(org_session, name="Klinik", slug=org_slug)
                org_session.commit()

            # Erster Lauf schlägt fehl -> Platzhalter + sichtbarer Vertrag.
            r1 = svc.process(
                organization_slug=org_slug,
                original_filename="demo-retry.pdf",
                content_type="application/pdf",
                content=content,
            )
            assert r1.status == "analysis_failed"
            assert r1.contract_id, "Platzhalter-Vertrag fehlt bei Analyse-Fehler"
            assert r1.message == "Lokale KI nicht verfügbar."

            session = Session(engine, expire_on_commit=False)
            try:
                ph = session.get(Contract, uuid.UUID(r1.contract_id))
                assert ph is not None
                assert ph.lifecycle_state == "active"
                assert ph.status == "draft"
                assert ph.accepted_extraction_id is None
                linked = session.query(ContractDocument).filter(
                    ContractDocument.contract_id == ph.id
                ).count()
                assert linked == 1
            finally:
                session.close()

            # Retry gelingt -> echter Vertrag, Platzhalter verwaist.
            r2 = svc.resume_document(
                organization_slug=org_slug,
                document_version_id=r1.document_version_id,
            )
            assert r2.status in {"imported", "duplicate"}, r2.status
            assert r2.contract_id and r2.contract_id != r1.contract_id
            session = Session(engine, expire_on_commit=False)
            try:
                real = session.get(Contract, uuid.UUID(r2.contract_id))
                assert real is not None and real.accepted_extraction_id is not None
                ph = session.get(Contract, uuid.UUID(r1.contract_id))
                assert ph.lifecycle_state == "orphan"
            finally:
                session.close()


class TestImportState:
    def test_analysis_ok_reports_no_retry(self, engine):
        d, storage, svc = _temp_env()
        try:
            org_slug, contract_id, _ = _build_committed_chain(engine, svc)
            client = TestClient(import_app())
            j = client.get(
                f"/api/contracts/{contract_id}?organization_slug={org_slug}"
            ).json()
            is_ = j["import_state"]
            assert is_["import_state"] == "analysis_ok"
            assert is_["state_label_de"] == "Analyse erfolgreich"
            assert is_.get("can_retry") is False
        finally:
            d.cleanup()