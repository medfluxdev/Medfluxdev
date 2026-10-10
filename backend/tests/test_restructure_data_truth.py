"""Restructure Phase A: unbekannte Beträge bleiben unbekannt, Laufend-Definition, Stichtag, Fristen-Abdeckung."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from app.core.clock import today_local
from app.database.models import Contract
from app.database.session import create_session
from app.register.status import is_running
from app.reports.exports import portfolio
from app.reports.grid import COLUMNS, GridRow, money_totals
from tests.test_register_grid import _as, _populate, _seed

AS_OF = date(2026, 10, 10)


def _row(annual=None, currency="EUR", status="gueltig", start=None, end=None, term_status="Vollständig", **extra) -> GridRow:
    values = {column.key: None for column in COLUMNS}
    values.update({
        "business_status": status, "annual_cost": annual, "cost_current_year": annual, "_currency": currency if annual is not None else None,
        "term_start_date": start, "possible_end": end, "term_status": term_status, "register_number": "V-1",
        "short_description": "Test", "cancel_by": None, "deletion_from": None, "responsible": "X", "reminder_recipient": "Y",
    })
    values.update(extra)
    return GridRow(contract_id=uuid.uuid4(), values=values, ids={})


def test_totals_never_turn_unknown_into_zero():
    payload = money_totals([_row(), _row()]).payload()
    assert payload["sums"]["annual_cost"] is None
    assert payload["coverage"]["annual_cost"] == {"known": 0, "missing": 2}


def test_totals_report_partial_coverage_and_real_zero():
    payload = money_totals([_row(Decimal("4200.00")), _row(Decimal("0.00")), _row()]).payload()
    assert payload["sums"]["annual_cost"] == "4200.00"
    assert payload["coverage"]["annual_cost"] == {"known": 2, "missing": 1}
    zero = money_totals([_row(Decimal("0"))]).payload()
    assert zero["sums"]["annual_cost"] == "0.00"


def test_totals_keep_currencies_apart():
    payload = money_totals([_row(Decimal("100")), _row(Decimal("50"), currency="CHF")]).payload()
    assert payload["sums"]["annual_cost"] == "100.00"
    assert payload["other_currencies"]["annual_cost"] == {"CHF": "50.00"}
    only_chf = money_totals([_row(Decimal("50"), currency="CHF")]).payload()
    assert only_chf["sums"]["annual_cost"] is None
    assert only_chf["coverage"]["annual_cost"] == {"known": 1, "missing": 0}


def test_running_definition():
    assert is_running("gueltig", date(2026, 1, 1), None, AS_OF)
    assert is_running("gekuendigt", None, date(2026, 12, 31), AS_OF)
    assert not is_running("gekuendigt", None, date(2026, 10, 9), AS_OF)
    assert not is_running("in_arbeit", None, None, AS_OF)
    assert not is_running("gueltig", date(2026, 11, 1), None, AS_OF)
    assert not is_running("beendet", None, None, AS_OF)


def test_portfolio_counts_running_and_separates_perpetual_from_incomplete():
    rows = [
        _row(Decimal("1000"), term_status="Vollständig"),
        _row(term_status="Unbefristet"),
        _row(term_status="Unvollständig"),
        _row(status="in_arbeit", term_status="Unvollständig"),
    ]
    report = portfolio(rows, AS_OF, range(AS_OF.year - 1, AS_OF.year + 2))
    assert report["totals"]["running"] == 3
    assert report["totals"]["in_progress"] == 1
    assert report["totals"]["perpetual"] == 1
    assert report["totals"]["amounts"]["annual_cost"]["known"] == 1
    assert report["totals"]["amounts"]["annual_cost"]["missing"] == 2
    no_end = next(item for item in report["insights"] if item["key"] == "no_end")
    assert no_end["count"] == 2
    assert no_end["filter"] == {"column": "term_status", "op": "in", "value": ["Unvollständig"]}
    assert all(item["expense"] is None for item in report["cost_by_year"])


def test_today_local_uses_org_timezone_around_midnight():
    # 22:30 UTC am 10.10. ist in Berlin (Sommerzeit, UTC+2) schon der 11.10.
    assert today_local(datetime(2026, 10, 10, 22, 30, tzinfo=timezone.utc)) == date(2026, 10, 11)
    # 23:30 UTC am 31.12. ist in Berlin (Winterzeit, UTC+1) schon Neujahr.
    assert today_local(datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc)) == date(2027, 1, 1)
    assert today_local(datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)) == date(2026, 10, 10)


def test_grid_totals_and_renewals_are_honest(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _as(monkeypatch, ids, "admin", "admin")
    a, b, _ = _populate(admin, slug, ids)
    incomplete = admin.post("/api/contracts", params=query, json={"values": {
        "short_description": "Ohne Laufzeit", "term_model": "fixed_term",
    }}).json()["contract_id"]
    perpetual = admin.post("/api/contracts", params=query, json={"values": {
        "short_description": "Unbefristet", "term_model": "perpetual",
    }}).json()["contract_id"]

    grid = admin.get("/api/register/grid", params={**query, "spec": json.dumps({"columns": ["register_number", "annual_cost", "term_status"]})}).json()
    assert grid["totals"]["sums"]["annual_cost"] == "18000.00"
    assert grid["totals"]["coverage"]["annual_cost"] == {"known": 2, "missing": 2}
    statuses = {item["contract_id"]: item["values"]["term_status"] for item in grid["items"]}
    assert statuses[incomplete] == "Unvollständig" and statuses[perpetual] == "Unbefristet"

    session = create_session()
    try:
        for cid in (incomplete, perpetual):
            session.get(Contract, UUID(cid)).business_status = "gueltig"
        session.commit()
    finally:
        session.close()
    renewals = admin.get("/api/register/renewals", params=query).json()
    assert [item["contract_id"] for item in renewals["not_evaluable"]] == [incomplete]
    assert renewals["not_evaluable"][0]["reason"] == "Laufzeitangaben unvollständig"
