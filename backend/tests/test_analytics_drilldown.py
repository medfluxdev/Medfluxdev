"""Analysen: Drilldown Krankenhaus -> Abteilung -> Verträge und Leistung bei 1.000 Verträgen."""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.reports.exports import NONE_VALUE, drilldown, portfolio
from app.reports.grid import MONEY_KEYS, GridRow

AS_OF = date(2026, 10, 10)


def _row(hospital, department, cost, *, status="gueltig", currency="EUR", number="000001"):
    values = {key: None for key in MONEY_KEYS}
    values.update({
        "business_status": status, "term_start_date": date(2025, 1, 1), "possible_end": None,
        "hospital": hospital, "department": department, "_currency": currency,
        "register_number": number, "short_description": f"Vertrag {number}", "partner": "Partner",
        "term_status": "Vollständig",
        "cost_current_year": Decimal(cost) if cost is not None else None,
        "annual_cost": Decimal(cost) if cost is not None else None,
    })
    return GridRow(contract_id=uuid4(), values=values, ids={})


ROWS = [
    _row("Klinikum A", "Radiologie", "1000", number="000001"),
    _row("Klinikum A", "Radiologie", None, number="000002"),
    _row("Klinikum A", "Kardiologie", "500", number="000003"),
    _row("Klinikum B", None, "200", number="000004"),
    _row(None, None, "50", number="000005"),
    _row("Klinikum A", "Radiologie", "9999", status="in_arbeit", number="000006"),  # nicht laufend
]


def test_first_level_groups_running_contracts_by_hospital_with_coverage():
    report = drilldown(ROWS, AS_OF)
    assert report["level"] == "hospital" and report["path"] == [] and report["count"] == 5
    labels = [(item["label"], item["value"], item["count"], item["cost_current_year"]) for item in report["items"]]
    assert labels == [
        ("Klinikum A", "Klinikum A", 3, "1500.00"),
        ("Klinikum B", "Klinikum B", 1, "200.00"),
        ("Ohne Zuordnung", NONE_VALUE, 1, "50.00"),
    ]
    first = report["items"][0]
    assert (first["known"], first["missing"]) == (2, 1)
    assert report["totals"]["value"] == "1750.00" and report["totals"]["missing"] == 1


def test_second_level_and_contract_list_keep_the_path_and_register_filter():
    report = drilldown(ROWS, AS_OF, hospital="Klinikum A")
    assert report["level"] == "department"
    assert [item["label"] for item in report["items"]] == ["Radiologie", "Kardiologie"]
    assert report["register_filter"] == [{"column": "hospital", "op": "in", "value": ["Klinikum A"]}]

    contracts = drilldown(ROWS, AS_OF, hospital="Klinikum A", department="Radiologie")
    assert contracts["level"] == "contract"
    assert [item["register_number"] for item in contracts["items"]] == ["000001", "000002"]  # unbekannte Kosten zuletzt
    assert contracts["items"][1]["cost_current_year"] is None
    assert [step["name"] for step in contracts["path"]] == ["Klinikum A", "Radiologie"]

    unassigned = drilldown(ROWS, AS_OF, hospital="Klinikum B", department=NONE_VALUE)
    assert [item["register_number"] for item in unassigned["items"]] == ["000004"]
    assert unassigned["register_filter"][1] == {"column": "department", "op": "in", "value": [""]}


def test_department_without_hospital_is_rejected():
    with pytest.raises(ValueError):
        drilldown(ROWS, AS_OF, department="Radiologie")


def test_other_currencies_are_not_added_to_euro_sums():
    rows = [_row("Klinikum A", "X", "100"), _row("Klinikum A", "X", "100", currency="CHF")]
    item = drilldown(rows, AS_OF)["items"][0]
    assert item["cost_current_year"] == "100.00" and item["count"] == 2


def test_portfolio_and_drilldown_on_1000_contracts_stay_fast():
    """WP5.6: Kennzahlen und Drilldown auf 1.000 Verträgen (Berechnung auf den Registerzeilen)."""
    rows = [
        _row(f"Klinikum {index % 4}", f"Abteilung {index % 25}", str(100 + index) if index % 7 else None, number=f"{index:06d}")
        for index in range(1000)
    ]
    for row in rows:
        row.yearly.update({year: {"expense": Decimal("100"), "income": Decimal("0")} for year in range(2024, 2030)})
        row.values.update({"cancel_by": None, "responsible": "X", "reminder_recipient": "X", "deletion_from": None,
                           "contract_type": "Wartung", "cost_center": None, "next_deadline": None})
    started = time.perf_counter()
    report = portfolio(rows, AS_OF, range(2024, 2030))
    level1 = drilldown(rows, AS_OF)
    level2 = drilldown(rows, AS_OF, hospital="Klinikum 1")
    level3 = drilldown(rows, AS_OF, hospital="Klinikum 1", department="Abteilung 1")
    elapsed = time.perf_counter() - started
    assert report["totals"]["running"] == 1000
    assert sum(item["count"] for item in level1["items"]) == 1000
    assert sum(item["count"] for item in level2["items"]) == 250
    assert level3["count"] == 10
    assert elapsed < 0.5, f"Portfolio + Drilldown dauerten {elapsed:.3f} s"


def test_drilldown_api_on_1000_seeded_contracts(monkeypatch):
    """Ende-zu-Ende über die API auf 1.000 Verträgen (Postgres): kalt einmal, danach aus dem Zeilen-Cache."""
    from app.database.models import Contract
    from app.database.models.finance import ContractFinanceEntry
    from app.database.session import create_session
    from tests.test_register_grid import _as, _seed

    slug, ids = _seed()
    session = create_session()
    try:
        contracts = []
        for index in range(1000):
            contract = Contract(
                id=uuid4(), organization_id=ids["org"], scope_type="hospital",
                hospital_id=ids["hospital_a"] if index % 2 else ids["hospital_b"],
                business_status="gueltig", short_description=f"Last {index}", term_model="perpetual",
                term_start_date=date(2025, 1, 1),
            )
            contracts.append(contract)
        session.add_all(contracts)
        session.flush()
        session.add_all([
            ContractFinanceEntry(organization_id=ids["org"], contract_id=contract.id, label="Pauschale",
                                 amount=Decimal("100"), interval="monthly", valid_from=date(2025, 1, 1))
            for contract in contracts[::2]
        ])
        session.commit()
    finally:
        session.close()

    client = _as(monkeypatch, ids, "admin", "admin")
    query = {"organization_slug": slug}
    started = time.perf_counter()
    cold = client.get("/api/register/reports/drilldown", params=query)
    cold_seconds = time.perf_counter() - started
    assert cold.status_code == 200, cold.text
    body = cold.json()
    assert sum(item["count"] for item in body["items"]) == 1000
    assert body["totals"]["known"] == 500 and body["totals"]["missing"] == 500

    started = time.perf_counter()
    warm = client.get("/api/register/reports/drilldown", params={**query, "hospital": "Klinikum A"})
    warm_seconds = time.perf_counter() - started
    assert warm.status_code == 200 and warm.json()["level"] == "department"
    print(f"\ndrilldown 1000 Verträge: kalt {cold_seconds:.2f} s, warm {warm_seconds:.3f} s")
    assert warm_seconds < 0.5, f"warm {warm_seconds:.3f} s"
    assert cold_seconds < 5, f"kalt {cold_seconds:.2f} s"
