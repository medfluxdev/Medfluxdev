"""STEP 12 – Dashboard-Read-Model (org-gebunden, READ-ONLY, deterministisch).

Nutzt das Transaktion-pro-Test-Muster (Rollback) gegen native PostgreSQL 18.6.
Bei nicht erreichbarer DB wird SKIPPED (Unit-Suite bleibt ohne DB grün).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.contracts.calculation import calculate_contract
from app.contracts.warnings import evaluate_contract_warnings
from app.dashboard import build_dashboard_overview
from app.database.models import ContractWarning, Organization
from app.database.services import (
    accept_calculation,
    accept_extraction,
    create_contract,
    create_document_version,
    create_organization,
    run_warning_evaluation,
    save_calculation,
    save_document_file,
    save_extraction,
)
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


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(settings.database_url, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _require_pg(engine):
    if not _pg_available(engine):
        pytest.skip("PostgreSQL nicht erreichbar – Dashboard-Tests übersprungen")
    yield


@pytest.fixture
def db(engine):
    session = Session(engine, expire_on_commit=False)
    session.begin()
    yield session
    session.rollback()
    session.close()


def _org(db) -> Organization:
    return create_organization(db, name="Klinik", slug=f"klinik-{uuid.uuid4().hex[:12]}")


def _sha() -> str:
    return uuid.uuid4().hex + "0" * 16


def _domain_contract(
    *,
    end: date,
    as_of: date,
    cancellation=(90, TimeUnit.DAYS),
    status=ContractStatus.UNKNOWN,
    annual=None,
    annual_currency="EUR",
    default_currency="EUR",
    total_value=None,
    tcv_currency="EUR",
):
    cost_fields: dict = {}
    if annual is not None:
        cost_fields["annual_cost"] = Money(amount=str(annual), currency=annual_currency)
    if total_value is not None:
        cost_fields["total_contract_value"] = Money(
            amount=str(total_value), currency=tcv_currency
        )
    return DomainContract(
        id="DSHID",
        status=status,
        dates=ContractDates(
            start_date=FlexibleDate(date=date(2024, 1, 1)),
            end_date=FlexibleDate(date=end),
        ),
        termination=Termination(
            cancellation_period=Duration(value=cancellation[0], unit=cancellation[1]),
            cancellation_to_contract_end="to_contract_end",
        ),
        costs=Costs(default_currency=default_currency, **cost_fields),
    )


def _chain(db, org, domain: DomainContract, as_of: date, status="active"):
    """Legt Dokument->Extraktion->Berechnung->Vertrag mit akzeptierten Läufen an."""
    doc = save_document_file(
        db, organization_id=org.id, sha256=_sha(),
        original_filename="wartung.pdf", stored_filename="original.pdf",
        file_extension=".pdf", file_size_bytes=10, storage_key="x/original.pdf",
    )
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id,
        version_no=1, sha256=_sha(), storage_key="x/original.pdf",
    )
    ext = save_extraction(
        db, organization_id=org.id, document_version_id=ver.id,
        snapshot={
            "identity": {"contract_number": f"CN-{uuid.uuid4().hex[:6]}"},
            "costs": _costs_snapshot(domain),
        },
        evidence=[{"field_ref": "identity.contract_number", "page": 1}],
        status="success",
    )
    calc_result = calculate_contract(domain, as_of_date=as_of)
    calc = save_calculation(
        db, organization_id=org.id, extraction_id=ext.id, as_of_date=as_of,
        result_snapshot=calc_result.model_dump(mode="json"),
        calculation_version="step9-1.0", status="computed",
        result_rows=[], review_flags=[],
    )
    contract = create_contract(db, organization_id=org.id, supplier="Lieferant", status=status)
    accept_extraction(db, contract_id=contract.id, extraction_id=ext.id)
    accept_calculation(db, contract_id=contract.id, calculation_run_id=calc.id)
    db.flush()
    return contract, calc, calc_result


def _costs_snapshot(domain: DomainContract) -> dict:
    out: dict = {}
    if domain.costs.total_contract_value is not None:
        m = domain.costs.total_contract_value
        out["total_contract_value"] = {"amount": m.amount, "currency": m.currency}
    return out


def _evaluate(db, org, contract, calc, calc_result, domain, as_of):
    pure = evaluate_contract_warnings(domain, calc_result)
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=contract.id,
        calculation_run_id=calc.id, as_of_date=as_of,
        policy_version="step11-default-1", result=pure,
    )
    db.flush()


def _overview(db, org, as_of=date(2025, 6, 1)):
    return build_dashboard_overview(db, organization_id=org.id, as_of_date=as_of)


# ---------------------------------------------------------------------------
# KPIs / Portfolio
# ---------------------------------------------------------------------------

def test_empty_database(db):
    org = _org(db)
    ov = _overview(db, org)
    assert ov["kpis"]["active_contracts"]["value"] == 0
    assert ov["action_items"] == []
    assert ov["total_action_items"] == 0
    assert ov["financial"]["contracts_without_reliable_annual_cost"] == 0
    assert ov["freshness"]["data_freshness"] == "none"


def test_active_portfolio_includes_expiring_soon(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    # Ende in 30 Tagen -> expiring_soon (via Warnung)
    domain = _domain_contract(end=date(2025, 7, 1), as_of=as_of)
    c, calc, cr = _chain(db, org, domain, as_of)
    _evaluate(db, org, c, calc, cr, domain, as_of)
    # Zweiter, normal aktiver Vertrag (Ende & Kündigungsfrist weit weg)
    d2 = _domain_contract(end=date(2026, 6, 1), as_of=as_of)
    c2, calc2, cr2 = _chain(db, org, d2, as_of, status="active")
    _evaluate(db, org, c2, calc2, cr2, d2, as_of)
    ov = _overview(db, org)
    kpi = ov["kpis"]["active_contracts"]
    assert kpi["value"] == 2
    assert "1 aktiv · 1 bald auslaufend" in kpi["secondary_de"]


def test_terminated_and_expired_excluded_from_active(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    # Terminated (explizit) – zaehlt nicht zum aktiven Portfolio.
    d_term = _domain_contract(end=date(2025, 7, 1), as_of=as_of, status=ContractStatus.TERMINATED)
    c_t, calc_t, cr_t = _chain(db, org, d_term, as_of, status="terminated")
    _evaluate(db, org, c_t, calc_t, cr_t, d_term, as_of)
    # Abgelaufen -> EXPIRED.
    d_exp = _domain_contract(end=date(2024, 12, 31), as_of=as_of)
    c_e, calc_e, cr_e = _chain(db, org, d_exp, as_of)
    _evaluate(db, org, c_e, calc_e, cr_e, d_exp, as_of)
    assert db.get(type(c_e), c_e.id).status == "expired"
    ov = _overview(db, org)
    assert ov["kpis"]["active_contracts"]["value"] == 0


def test_expiring_soon_semantics(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    domain = _domain_contract(end=date(2025, 7, 1), as_of=as_of)  # 30 Tage
    c, calc, cr = _chain(db, org, domain, as_of)
    _evaluate(db, org, c, calc, cr, domain, as_of)
    ov = _overview(db, org)
    assert ov["kpis"]["expiring_soon"]["value"] == 1


def test_critical_cancellation_count_and_passed(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    # Ende 2025-07-20, Kündigungsfrist 90 Tage -> Stichtag 2025-04-21 = vor as_of -> PASSED (critical)
    d1 = _domain_contract(end=date(2025, 7, 20), as_of=as_of)
    c1, calc1, cr1 = _chain(db, org, d1, as_of)
    _evaluate(db, org, c1, calc1, cr1, d1, as_of)
    ov = _overview(db, org)
    assert ov["kpis"]["critical_cancellation"]["value"] == 1


def test_passed_deadline_no_termination_inference(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d1 = _domain_contract(end=date(2025, 7, 20), as_of=as_of)  # cancellation passed
    c1, calc1, cr1 = _chain(db, org, d1, as_of)
    _evaluate(db, org, c1, calc1, cr1, d1, as_of)
    db.refresh(c1)
    # Verstrichene Kündigungsfrist != gekündigt/terminiert.
    assert c1.status != "terminated"


# ---------------------------------------------------------------------------
# Finanzen
# ---------------------------------------------------------------------------

def test_annual_cost_aggregation(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d1 = _domain_contract(end=date(2026, 1, 1), as_of=as_of, annual="12000")
    c1, calc1, cr1 = _chain(db, org, d1, as_of)
    d2 = _domain_contract(end=date(2026, 2, 1), as_of=as_of, annual="3000")
    c2, calc2, cr2 = _chain(db, org, d2, as_of)
    ov = _overview(db, org)
    fin = ov["financial"]
    assert len(fin["annual_recurring"]) == 1
    assert fin["annual_recurring"][0]["currency"] == "EUR"
    assert float(fin["annual_recurring"][0]["amount"]) == 15000.0
    assert fin["annual_recurring"][0]["contract_count"] == 2


def test_multi_currency_separation(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d1 = _domain_contract(end=date(2026, 1, 1), as_of=as_of, annual="12000", annual_currency="EUR", default_currency="EUR")
    c1, _, _ = _chain(db, org, d1, as_of)
    d2 = _domain_contract(end=date(2026, 2, 1), as_of=as_of, annual="5000", annual_currency="CHF", default_currency="CHF")
    c2, _, _ = _chain(db, org, d2, as_of)
    ov = _overview(db, org)
    fin = ov["financial"]
    assert fin["multi_currency"] is True
    currs = {t["currency"] for t in fin["annual_recurring"]}
    assert currs == {"EUR", "CHF"}


def test_missing_cost_is_not_zero(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d = _domain_contract(end=date(2026, 1, 1), as_of=as_of)  # keine Kosten
    c, calc, cr = _chain(db, org, d, as_of)
    _evaluate(db, org, c, calc, cr, d, as_of)
    ov = _overview(db, org)
    fin = ov["financial"]
    assert fin["annual_recurring"] == []
    assert fin["contracts_without_reliable_annual_cost"] == 1
    dq = {q["label_de"]: q["count"] for q in ov["data_quality"]}
    assert dq.get("Fehlende Kostenangaben", 0) == 1


def test_conflicting_cost_excluded_and_reported(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    # Monatlich 1000 vs. jährlich 5000 -> CONFLICT
    domain = DomainContract(
        id="CFL",
        status=ContractStatus.UNKNOWN,
        dates=ContractDates(
            start_date=FlexibleDate(date=date(2024, 1, 1)),
            end_date=FlexibleDate(date=date(2026, 1, 1)),
        ),
        termination=Termination(
            cancellation_period=Duration(value=90, unit=TimeUnit.DAYS),
            cancellation_to_contract_end="to_contract_end",
        ),
        costs=Costs(
            default_currency="EUR",
            monthly_cost=Money(amount="1000", currency="EUR"),
            annual_cost=Money(amount="5000", currency="EUR"),
        ),
    )
    c, calc, cr = _chain(db, org, domain, as_of)
    _evaluate(db, org, c, calc, cr, domain, as_of)
    ov = _overview(db, org)
    fin = ov["financial"]
    assert fin["annual_recurring"] == []
    assert fin["contracts_without_reliable_annual_cost"] == 1
    dq = {q["label_de"]: q["count"] for q in ov["data_quality"]}
    assert dq.get("Kostenkonflikte", 0) == 1


def test_total_contract_value_semantics(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d1 = _domain_contract(end=date(2026, 1, 1), as_of=as_of, annual="12000", total_value="240000")
    c1, _, _ = _chain(db, org, d1, as_of)
    d2 = _domain_contract(end=date(2026, 2, 1), as_of=as_of, annual="3000")
    c2, _, _ = _chain(db, org, d2, as_of)  # ohne total value -> ohne verlaesslichen Wert
    ov = _overview(db, org)
    fin = ov["financial"]
    assert len(fin["total_contract_value"]) == 1
    assert fin["total_contract_value"][0]["currency"] == "EUR"
    assert float(fin["total_contract_value"][0]["amount"]) == 240000.0
    assert fin["contracts_without_reliable_total_value"] == 1


# ---------------------------------------------------------------------------
# Akzeptanz / Aktuellheit
# ---------------------------------------------------------------------------

def test_only_accepted_and_superseded_runs(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    domain = _domain_contract(end=date(2026, 1, 1), as_of=as_of, annual="12000")
    c, calc, cr = _chain(db, org, domain, as_of)

    # Ein NICHT-akzeptierter, älterer Berechnungslauf mit abweichenden Kosten.
    old_result = calculate_contract(
        _domain_contract(end=date(2026, 1, 1), as_of=as_of, annual="99999999"),
        as_of_date=as_of,
    )
    save_calculation(
        db, organization_id=org.id,
        extraction_id=_calc_ext_id(db, c),
        as_of_date=as_of, result_snapshot=old_result.model_dump(mode="json"),
        status="computed", result_rows=[], review_flags=[],
    )
    db.flush()
    # Der Dashboard-Wert darf NUR auf dem AKZEPTIERTEN Lauf basieren.
    ov = _overview(db, org)
    fin = ov["financial"]
    assert len(fin["annual_recurring"]) == 1
    assert float(fin["annual_recurring"][0]["amount"]) == 12000.0


def _calc_ext_id(db, contract):
    return contract.accepted_extraction_id


def test_organization_isolation(db):
    org_a = _org(db)
    org_b = _org(db)
    as_of = date(2025, 6, 1)
    d = _domain_contract(end=date(2026, 1, 1), as_of=as_of, annual="9000")
    c, _, _ = _chain(db, org_a, d, as_of)
    c2, _, _ = _chain(db, org_b, d, as_of)
    ov_a = _overview(db, org_a)
    ov_b = _overview(db, org_b)
    assert ov_a["kpis"]["active_contracts"]["value"] == 1
    assert ov_b["kpis"]["active_contracts"]["value"] == 1
    assert len(ov_a["financial"]["annual_recurring"]) == 1
    assert len(ov_b["financial"]["annual_recurring"]) == 1


# ---------------------------------------------------------------------------
# Handlungsbedarf
# ---------------------------------------------------------------------------

def test_action_queue_ordering(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    # Kritische Kündigungsfrist verstrichen (critical) vs. Ende-Annäherung (medium).
    d_crit = _domain_contract(end=date(2025, 7, 20), as_of=as_of)  # cancellation passed -> critical
    c_crit, calc_crit, cr_crit = _chain(db, org, d_crit, as_of)
    _evaluate(db, org, c_crit, calc_crit, cr_crit, d_crit, as_of)
    # Ende in 30 Tagen + Kündigungsschwelle 180 (weite Frist) -> Ende medium/high.
    d_end = _domain_contract(end=date(2025, 7, 1), as_of=as_of)
    c_end, calc_end, cr_end = _chain(db, org, d_end, as_of)
    _evaluate(db, org, c_end, calc_end, cr_end, d_end, as_of)
    ov = _overview(db, org)
    items = ov["action_items"]
    assert items, "erwarte Handlungsbedarf-Elemente"
    assert items[0]["severity"] == "critical"


def test_action_queue_limit(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    # Viele Verträge mit kritischer / anstehender Aktion.
    for i in range(15):
        d = _domain_contract(end=date(2025, 7, 20), as_of=as_of)
        c, calc, cr = _chain(db, org, d, as_of)
        _evaluate(db, org, c, calc, cr, d, as_of)
    ov = _overview(db, org)
    assert ov["total_action_items"] >= 15
    assert len(ov["action_items"]) <= 12


def test_no_duplicate_logical_warning_in_queue(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d = _domain_contract(end=date(2026, 1, 1), as_of=as_of, annual="12000")
    c, calc, cr = _chain(db, org, d, as_of)
    _evaluate(db, org, c, calc, cr, d, as_of)
    ov = _overview(db, org)
    fps = {i["warning_type"] for i in ov["action_items"]}
    # Kein Duplikat je logischem Problem (je contract + fingerprint).
    assert len(ov["action_items"]) == len({(i["contract_title"], i["warning_type"]) for i in ov["action_items"]})


def test_no_action_required(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    # Ende weit weg (>180 Tage) + Jahreskosten -> keine aktive Aktion.
    d = _domain_contract(end=date(2026, 12, 31), as_of=as_of, annual="12000")
    c, calc, cr = _chain(db, org, d, as_of)
    _evaluate(db, org, c, calc, cr, d, as_of)
    ov = _overview(db, org)
    assert ov["total_action_items"] == 0


# ---------------------------------------------------------------------------
# Frische & Determinismus
# ---------------------------------------------------------------------------

def test_deterministic_for_explicit_as_of(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d = _domain_contract(end=date(2025, 7, 1), as_of=as_of, annual="12000")
    c, calc, cr = _chain(db, org, d, as_of)
    _evaluate(db, org, c, calc, cr, d, as_of)
    a = _overview(db, org, as_of)
    b = _overview(db, org, as_of)
    # Determinismus: gleiche Ausgabe bei gleichem explizitem Stichtag.
    assert a["kpis"] == b["kpis"]
    assert a["action_items"] == b["action_items"]


def test_stale_fresh_warning_behavior(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d = _domain_contract(end=date(2025, 7, 1), as_of=as_of)
    c, calc, cr = _chain(db, org, d, as_of)
    _evaluate(db, org, c, calc, cr, d, as_of)
    # Frisch: angefragter Stichtag == Evaluationsstichtag.
    ov_fresh = _overview(db, org, as_of)
    assert ov_fresh["freshness"]["data_freshness"] == "current"
    # Stale: angefragter Stichtag liegt NACH dem Evaluationsstichtag.
    ov_stale = _overview(db, org, date(2025, 8, 1))
    assert ov_stale["freshness"]["data_freshness"] == "stale"
    assert ov_stale["freshness"]["warning_evaluation_as_of_date"] == as_of
    assert ov_stale["freshness"]["requested_as_of_date"] == date(2025, 8, 1)


def test_no_unbounded_contract_payload(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    for i in range(5):
        d = _domain_contract(end=date(2025, 7, 1), as_of=as_of)
        c, calc, cr = _chain(db, org, d, as_of)
        _evaluate(db, org, c, calc, cr, d, as_of)
    ov = _overview(db, org)
    # Kein Feld führt die vollen Verträge zurück.
    assert set(ov.keys()) - {"as_of_date", "freshness", "kpis", "deadlines", "action_items", "total_action_items", "financial", "data_quality"} == set()
    assert len(ov["action_items"]) <= 12


def test_partial_financial_data(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d_ok = _domain_contract(end=date(2026, 1, 1), as_of=as_of, annual="1000")
    c1, _, _ = _chain(db, org, d_ok, as_of)
    d_missing = _domain_contract(end=date(2026, 2, 1), as_of=as_of)
    c2, _, _ = _chain(db, org, d_missing, as_of)
    ov = _overview(db, org)
    assert len(ov["financial"]["annual_recurring"]) == 1
    assert ov["financial"]["contracts_without_reliable_annual_cost"] == 1


def test_manual_review_counts(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d = _domain_contract(end=date(2025, 7, 1), as_of=as_of)  # Ende eng + fehlende Kosten -> Review
    c, calc, cr = _chain(db, org, d, as_of)
    _evaluate(db, org, c, calc, cr, d, as_of)
    ov = _overview(db, org)
    dq = {q["label_de"]: q["count"] for q in ov["data_quality"]}
    assert "Fehlende Kostenangaben" in dq
    assert dq["Fehlende Kostenangaben"] >= 1


def test_deadline_distribution_includes_buckets(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    d = _domain_contract(end=date(2025, 7, 1), as_of=as_of)  # Ende 30 Tage
    c, calc, cr = _chain(db, org, d, as_of)
    _evaluate(db, org, c, calc, cr, d, as_of)
    ov = _overview(db, org)
    assert any(b["label_de"] == "30 Tage" and b["contract_end"] > 0 for b in ov["deadlines"])


def test_no_active_warning_projections_ok(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    # Vertrag vorhanden, aber noch KEINE Warn-Evaluation gelaufen.
    d = _domain_contract(end=date(2025, 7, 1), as_of=as_of)
    c, calc, cr = _chain(db, org, d, as_of)
    ov = _overview(db, org)
    assert ov["kpis"]["active_contracts"]["value"] == 1
    assert ov["action_items"] == []
    assert ov["freshness"]["data_freshness"] == "none"
