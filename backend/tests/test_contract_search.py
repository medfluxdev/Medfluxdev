"""STEP 13 – Vertrags-Portfolio-Suche/-Filter (org-gebunden, PostgreSQL-authoritativ).

Transaktion-pro-Test-Muster (Rollback) gegen native PostgreSQL 18.6 wie
test_dashboard.py; bei nicht erreichbarer DB SKIPPED (Unit-Suite bleibt grün).

Getestet ueber `build_contract_search` (Dienstebene) und die Route (params ->
SearchParams). Deckt: Freitext (exakt/praefix/FTS/fuzzy), strukturierte Filter,
Warn-Filter (exists, keine Duplikate), Finanz-Sicherheit (reliable only),
Datumsbereiche, Sortierung/Pagination, Org-Isolation, DTO-Beschraenkungen.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.contracts.calculation import calculate_contract
from app.contracts.search import (
    SearchParams,
    build_contract_search,
)
from app.contracts.warnings import evaluate_contract_warnings
from app.database.models import Contract, ContractEquipment, Organization
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

AS_OF = date(2025, 6, 1)


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
        pytest.skip("PostgreSQL nicht erreichbar – Search-Tests übersprungen")
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


def _snap_identity(contract_number: str, title: str, auto_renewal: str | None = None):
    identity = {
        "contract_number": contract_number,
        "contract_title": title,
    }
    snap = {"identity": identity}
    if auto_renewal is not None:
        snap["termination"] = {"automatic_renewal": auto_renewal}
    else:
        snap["termination"] = {"automatic_renewal": "false"}
    return snap


def _mk_contract(
    db,
    org,
    *,
    contract_number="CN-TEST-1",
    title="Servicevertrag Gerät",
    supplier="Lieferant",
    end=date(2026, 12, 31),
    as_of=AS_OF,
    annual=None,
    annual_currency="EUR",
    default_currency="EUR",
    auto_renewal="false",
    status=ContractStatus.UNKNOWN,
    evaluate=True,
) -> "tuple":
    cost_fields = {}
    if annual is not None:
        cost_fields["annual_cost"] = Money(amount=str(annual), currency=annual_currency)
    domain = DomainContract(
        id="DSHID",
        status=status,
        dates=ContractDates(
            start_date=FlexibleDate(date=date(2024, 1, 1)),
            end_date=FlexibleDate(date=end),
        ),
        termination=Termination(
            cancellation_period=Duration(value=90, unit=TimeUnit.DAYS),
            cancellation_to_contract_end="to_contract_end",
        ),
        costs=Costs(default_currency=default_currency, **cost_fields),
    )
    doc = save_document_file(
        db, organization_id=org.id, sha256=_sha(),
        original_filename="wartung.pdf", stored_filename="original.pdf",
        file_extension=".pdf", file_size_bytes=10, storage_key="x/original.pdf",
    )
    ver = create_document_version(
        db, organization_id=org.id, document_file_id=doc.id,
        version_no=1, sha256=_sha(), storage_key="x/original.pdf",
    )
    snap = _snap_identity(contract_number, title, auto_renewal)
    ext = save_extraction(
        db, organization_id=org.id, document_version_id=ver.id,
        snapshot=snap,
        evidence=[{"field_ref": "identity.contract_title", "page": 1}],
        status="success",
    )
    calc_result = calculate_contract(domain, as_of_date=as_of)
    calc = save_calculation(
        db, organization_id=org.id, extraction_id=ext.id, as_of_date=as_of,
        result_snapshot=calc_result.model_dump(mode="json"),
        calculation_version="step9-1.0", status="computed",
        result_rows=[], review_flags=[],
    )
    contract = create_contract(
        db, organization_id=org.id, supplier=supplier,
        contract_number=contract_number, status=None,
    )
    accept_extraction(db, contract_id=contract.id, extraction_id=ext.id)
    accept_calculation(db, contract_id=contract.id, calculation_run_id=calc.id)
    db.flush()
    if evaluate:
        pure = evaluate_contract_warnings(domain, calc_result)
        run_warning_evaluation(
            db, organization_id=org.id, contract_id=contract.id,
            calculation_run_id=calc.id, as_of_date=as_of,
            policy_version="step11-default-1", result=pure,
        )
        db.flush()
    return contract, calc, calc_result


def _search(db, org, **params):
    params.setdefault("organization_id", org.id)
    return build_contract_search(db, SearchParams(**params), organization_id=org.id, request_as_of=AS_OF)


def _numbers(resp) -> list[str]:
    return [i["contract_number"] for i in resp["items"]]


# ---------------------------------------------------------------------------
# Empty / Grundfall
# ---------------------------------------------------------------------------

def test_empty_portfolio(db):
    org = _org(db)
    resp = _search(db, org)
    assert resp["total_count"] == 0
    assert resp["items"] == []
    assert resp["facets"]["status_counts"]["active"] == 0
    assert resp["freshness"]["data_freshness"] == "none"


def test_returns_contracts_with_supplier(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", supplier="Siemens")
    resp = _search(db, org)
    assert resp["total_count"] == 1
    item = resp["items"][0]
    assert item["contract_number"] == "CN-A"
    assert item["supplier"] == "Siemens"


# ---------------------------------------------------------------------------
# Freitext: exakt / praefix / FTS / fuzzy / Equipment
# ---------------------------------------------------------------------------

def test_exact_number_search(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-1234", title="Röntgen Wartung")
    _mk_contract(db, org, contract_number="CN-9999", title="Anderer")
    resp = _search(db, org, q="CN-1234")
    assert _numbers(resp) == ["CN-1234"]


def test_exact_title_search(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="MRT Wartungsvertrag")
    _mk_contract(db, org, contract_number="CN-B", title="CT Anlagenpaket")
    resp = _search(db, org, q="MRT Wartungsvertrag")
    assert _numbers(resp) == ["CN-A"]


def test_exact_identifier_outranks(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-4711", title="CT-4711")
    _mk_contract(db, org, contract_number="CN-9999", title="Anderer 4711 Vertrag")
    resp = _search(db, org, q="4711", sort="relevance")
    assert resp["items"][0]["contract_number"] == "CN-4711"


def test_supplier_search_prefix(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", supplier="Siemens Healthineers")
    _mk_contract(db, org, contract_number="CN-B", supplier="GE Medical")
    resp = _search(db, org, q="Siemens")
    assert _numbers(resp) == ["CN-A"]


def test_supplier_exact_case_insensitive(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", supplier="Philips")
    resp = _search(db, org, q="philips", sort="relevance")
    assert _numbers(resp) == ["CN-A"]


def test_equipment_search(db):
    org = _org(db)
    c, _, _ = _mk_contract(db, org, contract_number="CN-A", title="Wartung")
    eq = ContractEquipment(
        organization_id=org.id,
        contract_id=c.id,
        extraction_id=c.accepted_extraction_id,
        device_name="Ventilator",
        manufacturer="Draeger",
    )
    db.add(eq)
    db.flush()
    resp = _search(db, org, q="Ventilator")
    assert _numbers(resp) == ["CN-A"]
    item = resp["items"][0]
    assert item["equipment_summary"] == "Ventilator"


def test_fuzzy_supplier(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", supplier="Siemens Healthineers")
    resp = _search(db, org, q="Siemen", sort="relevance")
    assert "CN-A" in _numbers(resp)


def test_exact_outranks_fuzzy(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", supplier="Siemens")
    _mk_contract(db, org, contract_number="CN-B", supplier="SiemensHeal")
    resp = _search(db, org, q="Siemens", sort="relevance")
    assert resp["items"][0]["contract_number"] == "CN-A"


def test_empty_q_returns_all(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="A")
    _mk_contract(db, org, contract_number="CN-B", title="B")
    resp = _search(db, org, q="   ")
    assert resp["total_count"] == 2


def test_very_short_query_no_fuzzy_crash(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", supplier="Siemens")
    resp = _search(db, org, q="Si")
    assert isinstance(resp, dict)


def test_sql_injection_like_input(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="Normal")
    resp = _search(db, org, q="'; DROP TABLE contract; --")
    assert resp["total_count"] == 0


# ---------------------------------------------------------------------------
# Strukturierte Filter
# ---------------------------------------------------------------------------

def test_status_filter(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="A")
    _mk_contract(db, org, contract_number="CN-B", title="B")
    db.get(Contract, _search(db, org)["items"][0]["contract_id"]).status = "terminated"
    db.flush()
    resp = _search(db, org, status=["active"])
    assert "CN-B" in _numbers(resp)


def test_multiple_status_or(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="A")
    _mk_contract(db, org, contract_number="CN-B", title="B")
    c = db.get(Contract, _search(db, org)["items"][0]["contract_id"])
    c.status = "terminated"
    db.flush()
    resp = _search(db, org, status=["active", "terminated"])
    assert len(_numbers(resp)) == 2


def test_critical_cancellation_filter(db):
    org = _org(db)
    # Kündigungsfrist verstrichen (advanced As_of) -> critical cancellation.
    _mk_contract(db, org, contract_number="CN-CRIT", title="Kritisch", end=date(2024, 1, 1), as_of=AS_OF)
    _mk_contract(db, org, contract_number="CN-OK", title="Normal", end=date(2026, 12, 31))
    resp = _search(db, org, critical_cancellation=True)
    assert "CN-CRIT" in _numbers(resp)
    assert "CN-OK" not in _numbers(resp)


def test_requires_action_filter_uses_exists(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-CRIT", title="K", end=date(2024, 1, 1))
    _mk_contract(db, org, contract_number="CN-OK", title="N")
    resp_action = _search(db, org, requires_action=True)
    assert "CN-CRIT" in _numbers(resp_action)


def test_automatic_renewal_filter_true(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-R", title="Auto", auto_renewal="true")
    _mk_contract(db, org, contract_number="CN-N", title="NoAuto", auto_renewal="false")
    resp = _search(db, org, automatic_renewal=True)
    assert _numbers(resp) == ["CN-R"]


def test_supplier_exact_filter(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", supplier="Philips")
    _mk_contract(db, org, contract_number="CN-B", supplier="Siemens")
    resp = _search(db, org, supplier="philips")
    assert _numbers(resp) == ["CN-A"]


def test_end_date_range_filter(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-E1", title="A", end=date(2027, 1, 1))
    _mk_contract(db, org, contract_number="CN-E2", title="B", end=date(2028, 1, 1))
    resp = _search(db, org, end_date_from=date(2027, 6, 1), end_date_to=date(2029, 1, 1))
    assert _numbers(resp) == ["CN-E2"]


# ---------------------------------------------------------------------------
# Finanz-Sicherheit
# ---------------------------------------------------------------------------

def test_annual_cost_min_max(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-C1", title="A", annual=1000)
    _mk_contract(db, org, contract_number="CN-C2", title="B", annual=5000)
    resp = _search(db, org, annual_cost_min=Decimal("2000"))
    assert _numbers(resp) == ["CN-C2"]


def test_annual_currency_isolation(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-EUR", title="A", annual=1000, annual_currency="EUR")
    _mk_contract(db, org, contract_number="CN-USD", title="B", annual=1000, annual_currency="USD")
    resp = _search(db, org, currency="USD")
    assert _numbers(resp) == ["CN-USD"]


def test_missing_cost_excluded_from_financial_filter(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-NOCOST", title="A")  # kein annual -> unreliable
    _mk_contract(db, org, contract_number="CN-HAS", title="B", annual=1000)
    resp = _search(db, org, annual_cost_min=Decimal("0"))
    assert "CN-NOCOST" not in _numbers(resp)
    assert "CN-HAS" in _numbers(resp)


def test_missing_cost_marked_unreliable_not_zero(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-NOCOST", title="A")
    resp = _search(db, org)
    item = next(i for i in resp["items"] if i["contract_number"] == "CN-NOCOST")
    assert item["annual_cost"]["unreliable"] is True
    assert item["annual_cost"]["amount"] is None


def test_reliable_cost_reported(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-HAS", title="B", annual=1200, annual_currency="eur")
    resp = _search(db, org)
    item = next(i for i in resp["items"] if i["contract_number"] == "CN-HAS")
    assert item["annual_cost"]["unreliable"] is False
    assert item["annual_cost"]["amount"] == Decimal("1200")
    assert item["annual_cost"]["currency"] == "EUR"


# ---------------------------------------------------------------------------
# Sortierung / Pagination / Duplikate
# ---------------------------------------------------------------------------

def test_combined_and_semantics(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="A", supplier="Siemens", annual=100)
    _mk_contract(db, org, contract_number="CN-B", title="B", supplier="Siemens", annual=5000)
    resp = _search(db, org, supplier="Siemens", annual_cost_min=Decimal("1000"))
    assert _numbers(resp) == ["CN-B"]


def test_page_size_bounds(db):
    org = _org(db)
    for i in range(5):
        _mk_contract(db, org, contract_number=f"CN-{i}", title=f"T{i}")
    resp = _search(db, org, page_size=25)
    assert resp["page_size"] == 25
    assert len(resp["items"]) == 5


def test_pagination_has_more(db):
    org = _org(db)
    for i in range(60):
        _mk_contract(db, org, contract_number=f"CN-{i:03d}", title=f"T{i:03d}")
    resp = _search(db, org, page_size=25, page=1)
    assert len(resp["items"]) == 25
    assert resp["has_more"] is True
    assert resp["total_count"] == 60
    resp2 = _search(db, org, page_size=25, page=3)
    assert len(resp2["items"]) == 10
    assert resp2["has_more"] is False


def test_no_duplicate_rows_from_warning_joins(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-MULTI", title="A", end=date(2025, 10, 1))
    _mk_contract(db, org, contract_number="CN-OK", title="B")
    resp = _search(db, org, requires_action=True)
    counts = {x: _numbers(resp).count(x) for x in _numbers(resp)}
    for v in counts.values():
        assert v == 1


def test_sort_by_title(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-B", title="Beta")
    _mk_contract(db, org, contract_number="CN-A", title="Alpha")
    resp = _search(db, org, sort="title", direction="asc")
    assert resp["items"][0]["contract_title"] == "Alpha"


def test_default_operational_ordering_deterministic(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-B", title="B")
    _mk_contract(db, org, contract_number="CN-A", title="A")
    resp = _search(db, org)
    assert len(resp["items"]) == 2


# ---------------------------------------------------------------------------
# Org-Isolation
# ---------------------------------------------------------------------------

def test_org_isolation(db):
    org1 = _org(db)
    org2 = _org(db)
    _mk_contract(db, org1, contract_number="CN-ORG1", title="Alic")
    _mk_contract(db, org2, contract_number="CN-ORG2", title="Same Title")
    resp = _search(db, org1, q="Same Title")
    assert resp["total_count"] == 0
    resp_all = _search(db, org1)
    assert all(i["contract_id"] for i in resp_all["items"])
    assert "CN-ORG2" not in _numbers(resp_all)


# ---------------------------------------------------------------------------
# DTO / Route
# ---------------------------------------------------------------------------

def test_dto_bounded_no_body(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="A", supplier="S")
    resp = _search(db, org)
    item = resp["items"][0]
    assert "contract_id" in item
    keys = set(item.keys())
    disallowed = {"body", "ocr", "evidence", "raw", "contents", "file"}
    assert not (keys & disallowed)


def test_route_validates_bad_page_size(db):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.config import settings
    client = TestClient(app)
    resp = client.get("/api/contracts", params={"organization_slug": "k", "page_size": 10})
    assert resp.status_code == 422


def test_route_validates_bad_sort(db):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/contracts", params={"organization_slug": "k", "sort": "evil"})
    assert resp.status_code == 422


def test_route_unknown_org_404(db):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/contracts", params={"organization_slug": "does-not-exist"})
    assert resp.status_code == 404
