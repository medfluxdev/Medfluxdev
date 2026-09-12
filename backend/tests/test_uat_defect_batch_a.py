"""Fokussierte Tests – UAT Defect Batch A (Netto/Brutto, Preisfixierung,
ereignisbasierter Beginn, manueller Override/Confirm + append-only Audit).

Teil 1: Pure Cost-Engine (keine DB) – `derive_tax_breakdown` + `collect_price_development`.
Teil 2: Integration (PostgreSQL, committed chain) – Override-Endpoint + Detail-Read-Model.

Es wird NUR diese Batch getestet; keine volle Regression, keine OCR/LLM.
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

ROOT = Path(__file__).resolve().parents[2]
import sys  # noqa: E402
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.contracts.calculation.costs import (  # noqa: E402
    collect_price_development,
    derive_tax_breakdown,
)
from app.contracts.calculation.models import TaxBasis  # noqa: E402


# =========================================================================
# Teil 1 – Pure Cost-Engine (Netto/Brutto + Preisfixierung)
# =========================================================================


class TestTaxBreakdown:
    def test_net_derives_brutto(self):
        b = derive_tax_breakdown(
            annual=Decimal("71000.04"),
            monthly=Decimal("5916.67"),
            tax_basis=TaxBasis.NET,
            tax_rate_percent=19,
            currency="EUR",
        )
        assert b.computed is True
        assert b.base_tax_basis == TaxBasis.NET
        assert b.annual_net == Decimal("71000.04")
        assert b.monthly_net == Decimal("5916.67")
        assert b.monthly_gross == Decimal("7040.84")
        assert b.annual_gross == Decimal("84490.05")
        assert b.rate_percent == 19

    def test_unknown_basis_no_brutto(self):
        b = derive_tax_breakdown(
            annual=Decimal("71000.04"), monthly=Decimal("5916.67"),
            tax_basis=TaxBasis.UNKNOWN, tax_rate_percent=19, currency="EUR",
        )
        assert b.computed is False
        assert b.annual_gross is None
        assert "keine Annahme" in b.explanation

    def test_gross_derives_net(self):
        b = derive_tax_breakdown(
            annual=Decimal("11900"), monthly=Decimal("991.67"),
            tax_basis=TaxBasis.GROSS, tax_rate_percent=19, currency="EUR",
        )
        assert b.computed is True
        assert b.annual_gross == Decimal("11900")
        assert b.annual_net == Decimal("10000.00")
        assert b.monthly_gross == Decimal("991.67")
        assert b.monthly_net == Decimal("833.34")

    def test_missing_rate_no_brutto(self):
        b = derive_tax_breakdown(
            annual=Decimal("71000.04"), monthly=Decimal("5916.67"),
            tax_basis=TaxBasis.NET, tax_rate_percent=None, currency="EUR",
        )
        assert b.computed is False
        assert b.annual_gross is None

    def test_no_default_vat_rate(self):
        # Satz 0 -> brutto == netto (keine erfundene 19-%-Annahme).
        b = derive_tax_breakdown(
            annual=Decimal("100"), monthly=Decimal("8.33"),
            tax_basis=TaxBasis.NET, tax_rate_percent=0, currency="EUR",
        )
        assert b.computed is True
        assert b.annual_gross == Decimal("100.00")

    def test_derives_monthly_from_annual_when_monthly_missing(self):
        # Nur Jahreswert vorhanden -> Monatswerte deterministisch aus
        # Jahreswert / 12 (Code-Rechnung, keine Erfindung).
        b = derive_tax_breakdown(
            annual=Decimal("71000.04"), monthly=None,
            tax_basis=TaxBasis.NET, tax_rate_percent=19, currency="EUR",
        )
        assert b.computed is True
        assert b.monthly_net == Decimal("5916.67")
        assert b.monthly_gross == Decimal("7040.84")
        assert b.annual_net == Decimal("71000.04")
        assert b.annual_gross == Decimal("84490.05")
        assert "12" in b.explanation

    def test_rate_missing_keeps_evidence_backed_base_values(self):
        # Basis=net ist belegt („zzgl. USt."): Netto-Basiswerte werden IMMER
        # ausgewiesen. Brutto (Gegen-Basis) bleibt offen – KEINE 19-%-Annahme.
        b = derive_tax_breakdown(
            annual=Decimal("71000.04"), monthly=Decimal("5916.67"),
            tax_basis=TaxBasis.NET, tax_rate_percent=None, currency="EUR",
        )
        assert b.computed is False
        assert b.base_tax_basis == TaxBasis.NET
        assert b.monthly_net == Decimal("5916.67")
        assert b.annual_net == Decimal("71000.04")
        assert b.monthly_gross is None
        assert b.annual_gross is None
        assert b.monthly_tax is None
        assert "Steuersatz" in b.explanation

    def test_computed_exposes_tax_amounts(self):
        b = derive_tax_breakdown(
            annual=Decimal("71000.04"), monthly=Decimal("5916.67"),
            tax_basis=TaxBasis.NET, tax_rate_percent=19, currency="EUR",
        )
        assert b.monthly_tax == Decimal("1124.17")
        assert b.annual_tax == Decimal("13490.01")


class TestResolveMonthly:
    def test_read_model_resolves_evidence_backed_monthly(self):
        # Gespeicherte Berechnung: monthly leer, aber monatlicher Fakt liegt in
        # den Jahres-Eingaben -> Monat wird NIEMALS als Jahreswert/12 erfunden,
        # sondern aus dem belegten Eingabefeld uebernommen (status=explicit).
        from app.contracts.calculation.models import MoneyFieldResult
        from app.contracts.detail.service import _resolve_monthly

        annual = MoneyFieldResult(
            value=Decimal("71000.04"), currency="EUR",
            inputs={"monthly_cost": "5916.67"},
        )
        m = _resolve_monthly(MoneyFieldResult(), annual)
        assert m.value == Decimal("5916.67")
        assert m.status.value == "explicit"
        assert m.currency == "EUR"
        assert m.inputs == {"monthly_cost": "5916.67"}


class TestPriceDevelopment:
    def test_collects_clause_and_indexation(self):
        from app.models.contract import Costs
        c = Costs(price_adjustment_clause="Preisänderung nur nach Absprache",
                  price_indexation="jährlich an Verbraucherpreisindex")
        items = collect_price_development(c)
        keys = {i.key for i in items}
        assert "price_adjustment_clause" in keys
        assert "price_indexation" in keys
        assert all(i.evidence_field_ref for i in items)
        assert all(i.status.value == "explicit" for i in items)


# =========================================================================
# Teil 1.5 – UAT Re-Test: Recovery aus persistiertem kanonischem Dokumenttext
# + evidenzgestützte Netto/MwSt/Brutto-Ableitung (84.490,08 statt 84.490,05)
# =========================================================================


class TestRecoverFinancialFacts:
    def test_recover_financial_facts_from_canonical_pages(self):
        from app.contracts.detail.recovery import recover_financial_facts
        pages = [
            {
                "page": 7,
                "text": "",
                "elements": [],
                "tables": [
                    {
                        "cells": [
                            {"text": "Preis in € ab Zahlungsbeginn"},
                            {"text": "Gesamtdienstleistungspreis netto pro Monat in €",
                             "region": {"x0": 55, "y0": 230, "x1": 350, "y1": 240}},
                            {"text": "5.916,67", "region": {"x0": 489.3, "y0": 233.6, "x1": 527.6, "y1": 245}},
                            {"text": "zzgl. 19% MwSt.", "region": {"x0": 420, "y0": 251.3, "x1": 528.3, "y1": 262}},
                            {"text": "1.124,17", "region": {"x0": 490.6, "y0": 251.3, "x1": 528.3, "y1": 262}},
                            {"text": "Gesamtdienstleistungspreis brutto pro Monat in €",
                             "region": {"x0": 55, "y0": 267, "x1": 350, "y1": 279}},
                            {"text": "7.040,84", "region": {"x0": 490, "y0": 267.6, "x1": 527.6, "y1": 279}},
                        ]
                    }
                ],
            },
            {
                "page": 1,
                "text": ("SIEMENS\nVertragsbeginn:\nÜbergabedatum\nZahlungsbeginn:\n"
                         "3 Monate nach Ablauf der Gewährleistung\nMindestlaufzeit:\n96 Monate"),
                "elements": [
                    {"text": "3 Monate nach Ablauf der Gewährleistung",
                     "region": {"x0": 195.7, "y0": 393.8, "x1": 384.9, "y1": 408.3}},
                    {"text": "96 Monate", "region": {"x0": 195.7, "y0": 384.3, "x1": 246.9, "y1": 397}},
                ],
                "tables": [],
            },
        ]
        facts = recover_financial_facts(pages)
        m = facts.money
        assert m is not None
        assert m.monthly_net == Decimal("5916.67")
        assert m.monthly_vat == Decimal("1124.17")
        assert m.monthly_gross == Decimal("7040.84")
        assert m.vat_rate == 19
        assert m.basis == "net"
        assert m.page == 7
        assert m.net_region and m.vat_region and m.gross_region
        assert facts.laufzeit is not None
        assert facts.laufzeit.start_event == "Übergabedatum"
        assert facts.laufzeit.payment_start_rule == "3 Monate nach Ablauf der Gewährleistung"
        assert facts.laufzeit.minimum_duration_months == 96

    def test_minimum_duration_last_token_rule(self):
        # Seite-4-Layout: Werte aneinandergereiht. Der LAST-Zahlwert („96
        # Monate") ist die Mindestvertragslaufzeit, NICHT der Zahlungsbeginn
        # („3 Monate …"). Start-Ereignis wird hier NICHT erfasst (das Label
        # „Vertragsbeginn: Zahlungsbeginn:" traegt kein einzelnes Wort).
        from app.contracts.detail.recovery import recover_financial_facts
        pages = [
            {
                "page": 4,
                "text": ("Dienstleistungsvereinbarung\nVertragsbeginn: Zahlungsbeginn:\n"
                         "Mindestvertragslaufzeit:\nÜbergabedatum 3 Monate nach Ablauf "
                         "der Gewährleistung 96 Monate"),
                "elements": [],
                "tables": [],
            }
        ]
        facts = recover_financial_facts(pages)
        assert facts.laufzeit is not None
        assert facts.laufzeit.minimum_duration_months == 96
        assert facts.laufzeit.payment_start_rule == "3 Monate nach Ablauf der Gewährleistung"
        assert facts.laufzeit.start_event is None

    def test_recover_empty_pages_is_neutral(self):
        from app.contracts.detail.recovery import recover_financial_facts
        facts = recover_financial_facts([])
        assert facts.money is None
        assert facts.laufzeit is None


class TestTaxBreakdownRecovered:
    def test_evidenced_monthly_gross_preserves_contract_rounding(self):
        # Ohne extrahierten Steuersatz, aber mit direkt belegtem Vertrags-
        # Zahlen-Satz (Recovery): Satz 19 % kommt aus der Fundstelle, Jahres-
        # Brutto aus belegtem Monat x 12 = 84.490,08 (NICHT annual x 1,19).
        b = derive_tax_breakdown(
            annual=Decimal("71000.04"),
            monthly=Decimal("5916.67"),
            tax_basis=TaxBasis.NET,
            tax_rate_percent=None,
            currency="EUR",
            recovered_vat_rate=19.0,
            recovered_monthly_vat=Decimal("1124.17"),
            recovered_monthly_gross=Decimal("7040.84"),
            recovered_monthly_net=Decimal("5916.67"),
        )
        assert b.computed is True
        assert b.rate_percent == 19.0
        assert b.monthly_net == Decimal("5916.67")
        assert b.monthly_gross == Decimal("7040.84")
        assert b.monthly_tax == Decimal("1124.17")
        assert b.annual_net == Decimal("71000.04")
        assert b.annual_gross == Decimal("84490.08")
        assert b.annual_tax == Decimal("13490.04")
        assert "Vertragstext belegt" in b.explanation

    def test_gross_basis_recovered_monthly_net(self):
        b = derive_tax_breakdown(
            annual=Decimal("11900"),
            monthly=Decimal("991.67"),
            tax_basis=TaxBasis.GROSS,
            tax_rate_percent=19,
            currency="EUR",
            recovered_monthly_net=Decimal("833.34"),
        )
        assert b.computed is True
        assert b.monthly_net == Decimal("833.34")
        assert b.monthly_gross == Decimal("991.67")

    def test_recovered_rate_fills_missing_extracted_rate(self):
        b = derive_tax_breakdown(
            annual=Decimal("71000.04"),
            monthly=Decimal("5916.67"),
            tax_basis=TaxBasis.NET,
            tax_rate_percent=None,
            currency="EUR",
            recovered_vat_rate=19,
        )
        assert b.computed is True
        assert b.rate_percent == 19
        assert b.monthly_gross == Decimal("7040.84")
        assert b.annual_gross == Decimal("84490.05")


# =========================================================================
# Teil 2 – Integration (PostgreSQL): Override-Endpoint + Detail-Read-Model
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
    """Committed: org + PDF + Extraktion(monatl. netto + event-basierter Beginn +
    „Festpreis"-Evidenz) + Berechnung + akzeptierter Vertrag."""
    from app.database.services import (
        accept_calculation, accept_extraction, create_contract,
        create_organization, save_calculation, save_extraction,
    )
    from app.contracts.calculation import calculate_contract
    from app.models.contract import Contract as DomainContract
    from app.models.contract import ContractDates, Costs, Termination
    from app.models.enums import ContractStatus
    from app.models.values import Duration, FlexibleDate, Money

    session = Session(engine, expire_on_commit=False)
    try:
        session.begin()
        org = create_organization(session, name="Klinik",
                                  slug=f"uat-a-{uuid.uuid4().hex[:12]}")
        session.flush()
        content = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF\n" + uuid.uuid4().hex.encode()
        r = svc.store_original(session, organization_id=org.id,
                               original_filename="axIOM.pdf",
                               content_type="application/pdf", content=content)
        session.flush()
        evidence = [
            {"field_ref": "costs.monthly_cost", "source_type": "paragraph",
             "page": 6, "source_text": "Mtl. Wartungspreis: 5.916,67 zzgl. USt.",
             "confidence": 0.9},
            {"field_ref": "dates.start_date", "source_type": "paragraph",
             "page": 1, "source_text": "Vertragsbeginn: Übergabedatum",
             "confidence": 0.8},
            {"field_ref": "termination.evidence", "source_type": "paragraph",
             "page": 7, "source_text": "Festpreis über 8 Jahre.",
             "confidence": 0.95},
        ]
        ext = save_extraction(
            session, organization_id=org.id, document_version_id=r.document_version_id,
            snapshot={
                "identity": {"contract_number": "UAT-AX-1", "supplier": "Siemens"},
                "dates": {"start_date": {"date": None, "condition": "Übergabedatum",
                                        "requires_review": True},
                          "duration": {"value": 96, "unit": "months"}},
                "costs": {"monthly_cost": {"amount": 5916.67, "period": "monthly",
                                            "currency": "EUR"},
                          "maintenance_fee": {"amount": 5916.67, "period": "monthly",
                                               "currency": "EUR"}},
                "termination": {
                    "automatic_renewal": False,
                    "evidence": {"source_type": "paragraph", "page": 7,
                                 "source_text": "Festpreis über 8 Jahre."},
                },
            },
            evidence=evidence, status="success",
        )
        domain = DomainContract(
            id="UATA", status=ContractStatus.UNKNOWN,
            dates=ContractDates(start_date=FlexibleDate(date=None, condition="Übergabedatum"),
                                duration=Duration(value=96, unit="months")),
            termination=Termination(automatic_renewal=False),
            costs=Costs(default_currency="EUR",
                        monthly_cost=Money(amount=5916.67, currency="EUR", period="monthly"),
                        maintenance_fee=Money(amount=5916.67, currency="EUR", period="monthly")),
        )
        calc = calculate_contract(domain, as_of_date=date(2025, 6, 1))
        run = save_calculation(
            session, organization_id=org.id, extraction_id=ext.id,
            as_of_date=date(2025, 6, 1),
            result_snapshot=calc.model_dump(mode="json"),
            calculation_version="step9-1.0", status="computed",
            result_rows=[], review_flags=[],
        )
        contract = create_contract(session, organization_id=org.id, supplier="Siemens",
                                   status="active", contract_number="UAT-AX-1")
        accept_extraction(session, contract_id=contract.id, extraction_id=ext.id)
        accept_calculation(session, contract_id=contract.id, calculation_run_id=run.id)
        svc.link_to_contract(session, contract_id=contract.id,
                             document_version_id=r.document_version_id, role="main")
        session.commit()
        return org.slug, contract.id, r
    finally:
        session.close()


def test_override_net_brutto_and_audit(engine):
    from app.documents.persistence import DocumentPersistenceService
    from app.documents.storage import DocumentStorage
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        svc = DocumentPersistenceService(storage=DocumentStorage(Path(d) / "contracts"))
        org_slug, contract_id, _ = _build_committed_chain(engine, svc)
        client = TestClient(import_app())

        # BEFORE: evidence-first ohne Overrides. Basis=net aus „zzgl. USt.",
        # Monatswert 5916.67 belegt (aus Jahres-Eingaben), Brutto offen, kein
        # erfundener Termin, Preisfixierung 8 Jahre.
        r0 = client.get(f"/api/contracts/{contract_id}?organization_slug={org_slug}")
        assert r0.status_code == 200
        j0 = r0.json()
        assert j0["costs"]["tax_breakdown"]["computed"] is False
        assert j0["costs"]["tax_basis"] == "net"
        tb0 = j0["costs"]["tax_breakdown"]
        assert tb0["base_tax_basis"] == "net"
        assert tb0["monthly_net"] == "5916.67"
        assert tb0["annual_net"] == "71000.04"
        assert tb0["monthly_gross"] is None
        assert tb0["annual_gross"] is None
        assert j0["costs"]["monthly_recurring"]["amount"] == "5916.67"
        assert j0["costs"]["monthly_recurring"]["status"] == "explicit"
        assert j0["dates"]["start_condition"] == "Übergabedatum"
        assert j0["overrides"] == []
        pf0 = [p for p in j0["costs"]["price_development"] if p["key"] == "price_fixed"]
        assert pf0 and pf0[0]["period_years"] == 8

        # Override 1: Steuerbasis net + Satz 19
        r1 = client.post(
            f"/api/contracts/{contract_id}/overrides?organization_slug={org_slug}",
            json={"key": "cost.tax_basis", "action": "set", "value": "net",
                  "note": "Laut Angebot zzgl. USt."},
        )
        assert r1.status_code == 200, r1.text
        j1 = r1.json()
        assert j1["costs"]["tax_basis"] == "net"
        # Satz noch nicht gesetzt -> kein computable breakdown
        assert j1["costs"]["tax_breakdown"]["computed"] is False

        r2 = client.post(
            f"/api/contracts/{contract_id}/overrides?organization_slug={org_slug}",
            json={"key": "cost.tax_rate_percent", "action": "set", "value": 19.0},
        )
        assert r2.status_code == 200, r2.text
        j2 = r2.json()
        tb = j2["costs"]["tax_breakdown"]
        assert tb["computed"] is True
        assert tb["base_tax_basis"] == "net"
        assert tb["monthly_net"] == "5916.67"
        assert tb["monthly_gross"] == "7040.84"
        assert tb["annual_net"] == "71000.04"
        assert tb["annual_gross"] == "84490.05"
        # Preisfixierung aus termination-Evidenz
        pkeys = {p["key"] for p in j2["costs"]["price_development"]}
        assert "price_fixed" in pkeys

        r3 = client.post(
            f"/api/contracts/{contract_id}/overrides?organization_slug={org_slug}",
            json={"key": "date.event_start", "action": "set", "value": "2025-03-01"},
        )
        assert r3.status_code == 200, r3.text
        j3 = r3.json()
        assert j3["dates"]["overridden_start_date"] == "2025-03-01"
        assert j3["dates"]["start_date_status"] == "overridden"

        # Confirm-Fakt + Audit-Historie
        r4 = client.post(
            f"/api/contracts/{contract_id}/overrides?organization_slug={org_slug}",
            json={"key": "fact.confirm", "action": "confirm", "fact_ref": "costs.monthly_cost",
                  "note": "Betrag im Original geprüft"},
        )
        assert r4.status_code == 200, r4.text
        j4 = r4.json()
        assert len(j4["audit_log"]) >= 4
        actions = {a["action"] for a in j4["audit_log"]}
        assert "set" in actions and "confirm" in actions
        assert all(a["is_development"] is True for a in j4["audit_log"])
        assert all(a["actor_type"] is None for a in j4["audit_log"])
        eff_keys = {o["key"] for o in j4["overrides"]}
        assert "cost.tax_basis" in eff_keys
        assert "date.event_start" in eff_keys


def test_override_void_removes_effective(engine):
    from app.documents.persistence import DocumentPersistenceService
    from app.documents.storage import DocumentStorage
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        svc = DocumentPersistenceService(storage=DocumentStorage(Path(d) / "contracts"))
        org_slug, contract_id, _ = _build_committed_chain(engine, svc)
        client = TestClient(import_app())

        client.post(f"/api/contracts/{contract_id}/overrides?organization_slug={org_slug}",
                    json={"key": "cost.tax_rate_percent", "action": "set", "value": 19.0})
        rv = client.post(
            f"/api/contracts/{contract_id}/overrides?organization_slug={org_slug}",
            json={"key": "cost.tax_rate_percent", "action": "void"},
        )
        j = rv.json()
        eff_keys = {o["key"] for o in j["overrides"]}
        assert "cost.tax_rate_percent" not in eff_keys
        # Audit-Historie bleibt (append-only)
        assert any(a["action"] == "void" for a in j["audit_log"])


def import_app():
    from app.main import app
    return app
