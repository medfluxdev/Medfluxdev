"""STEP 11 – Persistenz/Integration der Warn-Schicht (durable Zustand + Projektion).

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
from app.contracts.warnings import (
    WarningType,
    evaluate_contract_warnings,
)
from app.database.models import (
    CalculationRun,
    Contract,
    ContractWarning,
    Organization,
    WarningEvaluationRun,
)
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
        pytest.skip("PostgreSQL nicht erreichbar – Warn-Persistenz-Tests übersprungen")
    yield


@pytest.fixture
def db(engine):
    session = Session(engine, expire_on_commit=False)
    session.begin()
    yield session
    session.rollback()
    session.close()


def _org(db) -> Organization:
    return create_organization(
        db, name="Warnklinik", slug=f"warn-{uuid.uuid4().hex[:12]}"
    )


def _sha() -> str:
    return uuid.uuid4().hex + "0" * 16


def _domain_contract(
    *,
    end: date,
    as_of: date,
    cancellation=(90, TimeUnit.DAYS),
    status=ContractStatus.UNKNOWN,
    annual=None,
):
    return DomainContract(
        id="WARNID",
        status=status,
        dates=ContractDates(
            start_date=FlexibleDate(date=date(2024, 1, 1)),
            end_date=FlexibleDate(date=end),
        ),
        termination=Termination(
            cancellation_period=Duration(value=cancellation[0], unit=cancellation[1]),
            cancellation_to_contract_end="to_contract_end",
        ),
        costs=(
            Costs(default_currency="EUR", annual_cost=Money(amount=str(annual), currency="EUR"))
            if annual is not None
            else Costs(default_currency="EUR")
        ),
    )


def _chain(db, org, domain: DomainContract, as_of: date):
    """Legt Dokument->Extraktion->Berechnung->Vertrag mit akzeptierten Läufen an."""
    doc = save_document_file(
        db,
        organization_id=org.id,
        sha256=_sha(),
        original_filename="wartung.pdf",
        stored_filename="original.pdf",
        file_extension=".pdf",
        file_size_bytes=10,
        storage_key="x/original.pdf",
    )
    ver = create_document_version(
        db,
        organization_id=org.id,
        document_file_id=doc.id,
        version_no=1,
        sha256=_sha(),
        storage_key="x/original.pdf",
    )
    ext = save_extraction(
        db,
        organization_id=org.id,
        document_version_id=ver.id,
        snapshot={"identity": {"contract_number": "WN-1"}},
        evidence=[{"field_ref": "identity.contract_number", "page": 1}],
        status="success",
    )
    calc_result = calculate_contract(domain, as_of_date=as_of)
    calc = save_calculation(
        db,
        organization_id=org.id,
        extraction_id=ext.id,
        as_of_date=as_of,
        result_snapshot=calc_result.model_dump(mode="json"),
        calculation_version="step9-1.0",
        status="computed",
        result_rows=[],
        review_flags=[],
    )
    contract = create_contract(
        db, organization_id=org.id, supplier="Lieferant", status="active"
    )
    accept_extraction(db, contract_id=contract.id, extraction_id=ext.id)
    accept_calculation(db, contract_id=contract.id, calculation_run_id=calc.id)
    db.flush()
    return contract, calc, calc_result


def test_uuidv7_pk_on_warning_tables(db):
    org = _org(db)
    wr = None
    c, calc, cr = _chain(
        db, org, _domain_contract(end=date(2026, 1, 1), as_of=date(2025, 6, 1)), date(2025, 6, 1)
    )
    # Reine Bewertung
    pure = evaluate_contract_warnings(
        _domain_contract(end=date(2026, 1, 1), as_of=date(2025, 6, 1)),
        cr,
    )
    run_warning_evaluation(
        db,
        organization_id=org.id,
        contract_id=c.id,
        calculation_run_id=calc.id,
        as_of_date=date(2025, 6, 1),
        policy_version="step11-default-1",
        result=pure,
    )
    db.flush()
    run = db.scalars(
        select(WarningEvaluationRun).where(WarningEvaluationRun.contract_id == c.id)
    ).one()
    hexes = [f"{run.id.int:032x}"]
    assert hexes[0][12] == "7"


def test_persistence_roundtrip_and_current_projection(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    # Ende in 30 Tagen -> EXPIRING_SOON-Projektion
    end = date(2025, 7, 1)
    domain = _domain_contract(end=end, as_of=as_of)
    c, calc, cr = _chain(db, org, domain, as_of)
    pure = evaluate_contract_warnings(domain, cr)
    assert any(w.warning_type == WarningType.CONTRACT_END_APPROACHING for w in pure.warnings)

    run_warning_evaluation(
        db,
        organization_id=org.id,
        contract_id=c.id,
        calculation_run_id=calc.id,
        as_of_date=as_of,
        policy_version="step11-default-1",
        result=pure,
    )
    db.flush()

    runs = db.scalars(
        select(WarningEvaluationRun).where(WarningEvaluationRun.contract_id == c.id)
    ).all()
    rows = db.scalars(
        select(ContractWarning).where(ContractWarning.contract_id == c.id)
    ).all()
    assert len(runs) == 1
    assert runs[0].as_of_date == as_of
    assert runs[0].policy_version == "step11-default-1"
    assert len(rows) == len(pure.warnings)
    assert all(r.active for r in rows)
    # Current-Projektion: anstehendes Ende -> expiring_soon
    db.refresh(c)
    assert c.status == "expiring_soon"


def test_dedup_logical_issue_across_evaluations(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    end = date(2025, 7, 1)  # Ende 30 Tage -> eine End-Annäherung
    domain = _domain_contract(end=end, as_of=as_of)
    c, calc, cr = _chain(db, org, domain, as_of)
    pure = evaluate_contract_warnings(domain, cr)
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=c.id,
        calculation_run_id=calc.id, as_of_date=as_of,
        policy_version="step11-default-1", result=pure,
    )
    db.flush()
    # Zweite Evaluation mit ANDEREM Berechnungslauf (idempotenz pro run; neuer Run)
    calc2 = save_calculation(
        db, organization_id=org.id, extraction_id=domain.id if False else _calc_ext(db, calc),
        as_of_date=as_of, result_snapshot=cr.model_dump(mode="json"),
        status="computed", result_rows=[], review_flags=[],
    )
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=c.id,
        calculation_run_id=calc2.id, as_of_date=as_of,
        policy_version="step11-default-1", result=pure,
    )
    db.flush()
    rows = db.scalars(
        select(ContractWarning).where(ContractWarning.contract_id == c.id)
    ).all()
    # Keine Duplikat-Zeilen je logischem Problem -> Anzahl = Anzahl distinkt.
    fps = {r.logical_fingerprint for r in rows}
    assert len(rows) == len(fps)


def _calc_ext(db, calc):
    return calc.extraction_id


def test_severity_escalation_same_fingerprint(db):
    org = _org(db)
    end = date(2025, 7, 1)
    domain = _domain_contract(end=end, as_of=date(2025, 6, 1))  # Ende 30 Tage
    c, calc, cr = _chain(db, org, domain, date(2025, 6, 1))
    pure = evaluate_contract_warnings(domain, cr)
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=c.id,
        calculation_run_id=calc.id, as_of_date=date(2025, 6, 1),
        policy_version="step11-default-1", result=pure,
    )
    db.flush()
    row1 = db.scalars(
        select(ContractWarning).where(
            (ContractWarning.contract_id == c.id)
            & (ContractWarning.warning_type == "contract_end_approaching")
        )
    ).one()

    # Näher an der Grenze (6 Tage statt 30) -> gleiche logische Zeile, schwerer.
    nd_domain = _domain_contract(end=end, as_of=date(2025, 6, 25))
    calc2r = calculate_contract(nd_domain, as_of_date=date(2025, 6, 25))
    calc2 = save_calculation(
        db, organization_id=org.id, extraction_id=_calc_ext(db, calc),
        as_of_date=date(2025, 6, 25), result_snapshot=calc2r.model_dump(mode="json"),
        status="computed", result_rows=[], review_flags=[],
    )
    pure2 = evaluate_contract_warnings(nd_domain, calc2r)
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=c.id,
        calculation_run_id=calc2.id, as_of_date=date(2025, 6, 25),
        policy_version="step11-default-1", result=pure2,
    )
    db.flush()
    rows_end = db.scalars(
        select(ContractWarning).where(
            (ContractWarning.contract_id == c.id)
            & (ContractWarning.warning_type == "contract_end_approaching")
        )
    ).all()
    # Gleiche logische Zeile, aktualisiert statt Duplikat.
    assert len(rows_end) == 1
    assert rows_end[0].id == row1.id
    assert rows_end[0].days_remaining == 6
    assert rows_end[0].active is True


def test_warning_cleared_without_history_loss_and_action_preserved(db):
    org = _org(db)
    end = date(2025, 7, 1)
    domain = _domain_contract(end=end, as_of=date(2025, 6, 1))  # Ende 30 Tage
    c, calc, cr = _chain(db, org, domain, date(2025, 6, 1))
    pure = evaluate_contract_warnings(domain, cr)
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=c.id,
        calculation_run_id=calc.id, as_of_date=date(2025, 6, 1),
        policy_version="step11-default-1", result=pure,
    )
    db.flush()
    row = db.scalars(
        select(ContractWarning).where(
            (ContractWarning.contract_id == c.id)
            & (ContractWarning.warning_type == "contract_end_approaching")
        )
    ).one()
    row.action_state = "acknowledged"
    db.flush()

    # Neue Evaluation, in der das Ende weit weg ist (181 Tage) -> Warnung wird
    # inaktiv, aber die Zeile + action_state bleiben erhalten.
    nd_domain = _domain_contract(end=end, as_of=date(2025, 1, 1))
    calc2r = calculate_contract(nd_domain, as_of_date=date(2025, 1, 1))
    calc2 = save_calculation(
        db, organization_id=org.id, extraction_id=_calc_ext(db, calc),
        as_of_date=date(2025, 1, 1), result_snapshot=calc2r.model_dump(mode="json"),
        status="computed", result_rows=[], review_flags=[],
    )
    pure2 = evaluate_contract_warnings(nd_domain, calc2r)
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=c.id,
        calculation_run_id=calc2.id, as_of_date=date(2025, 1, 1),
        policy_version="step11-default-1", result=pure2,
    )
    db.flush()
    rows = db.scalars(
        select(ContractWarning).where(ContractWarning.contract_id == c.id)
    ).all()
    # Historie nicht gelöscht; die End-Zeile wurde inaktiv statt entfernt.
    end_rows = [r for r in rows if r.warning_type == "contract_end_approaching"]
    assert len(end_rows) == 1
    assert end_rows[0].active is False
    assert end_rows[0].action_state == "acknowledged"


def test_organization_isolation(db):
    org_a = _org(db)
    org_b = _org(db)
    as_of = date(2025, 6, 1)
    end = date(2025, 7, 1)

    def _mk(org):
        domain = _domain_contract(end=end, as_of=as_of)
        c, calc, cr = _chain(db, org, domain, as_of)
        pure = evaluate_contract_warnings(domain, cr)
        run_warning_evaluation(
            db, organization_id=org.id, contract_id=c.id,
            calculation_run_id=calc.id, as_of_date=as_of,
            policy_version="step11-default-1", result=pure,
        )
        db.flush()
        return c

    ca = _mk(org_a)
    cb = _mk(org_b)
    # Nur Warnungen von org A für Vertrag A
    rows = db.scalars(
        select(ContractWarning).where(ContractWarning.organization_id == org_a.id)
    ).all()
    assert all(r.contract_id == ca.id for r in rows)
    assert len(rows) == len(db.scalars(
        select(ContractWarning).where(ContractWarning.contract_id == ca.id)
    ).all())
    # org B hat eigene Zeilen
    rows_b = db.scalars(
        select(ContractWarning).where(ContractWarning.organization_id == org_b.id)
    ).all()
    assert all(r.contract_id == cb.id for r in rows_b)


def test_contract_delete_cascades_warnings(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    domain = _domain_contract(end=date(2025, 7, 1), as_of=as_of)
    c, calc, cr = _chain(db, org, domain, as_of)
    pure = evaluate_contract_warnings(domain, cr)
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=c.id,
        calculation_run_id=calc.id, as_of_date=as_of,
        policy_version="step11-default-1", result=pure,
    )
    db.flush()
    assert db.scalars(
        select(ContractWarning).where(ContractWarning.contract_id == c.id)
    ).all()
    # Löschen des Vertrags -> Warn-Zeilen + Evaluations-Runs (contract ondelete CASCADE)
    db.execute(
        text("DELETE FROM contract WHERE id = :cid"), {"cid": c.id}
    )
    db.flush()
    assert not db.scalars(
        select(ContractWarning).where(ContractWarning.contract_id == c.id)
    ).all()
    assert not db.scalars(
        select(WarningEvaluationRun).where(WarningEvaluationRun.contract_id == c.id)
    ).all()


def test_terminated_projection_never_overridden(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    domain = _domain_contract(
        end=date(2025, 6, 15), as_of=as_of, status=ContractStatus.TERMINATED
    )
    c, calc, cr = _chain(db, org, domain, as_of)
    c.status = "terminated"
    db.flush()
    pure = evaluate_contract_warnings(domain, cr)
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=c.id,
        calculation_run_id=calc.id, as_of_date=as_of,
        policy_version="step11-default-1", result=pure,
    )
    db.flush()
    db.refresh(c)
    # Explizit TERMINATED bleibt TERMINATED (auch wenn enges Ende).
    assert c.status == "terminated"


def test_expired_projection(db):
    org = _org(db)
    as_of = date(2025, 6, 1)
    domain = _domain_contract(end=date(2024, 12, 31), as_of=as_of)
    c, calc, cr = _chain(db, org, domain, as_of)
    pure = evaluate_contract_warnings(domain, cr)
    assert any(w.warning_type == WarningType.CONTRACT_EXPIRED for w in pure.warnings)
    run_warning_evaluation(
        db, organization_id=org.id, contract_id=c.id,
        calculation_run_id=calc.id, as_of_date=as_of,
        policy_version="step11-default-1", result=pure,
    )
    db.flush()
    db.refresh(c)
    assert c.status == "expired"
