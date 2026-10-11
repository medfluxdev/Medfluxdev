"""Gerätearten an Verträgen (Plan GERAETEARTEN_PLAN_20261011)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import catalogs as catalog_routes, contract_register, register_grid
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models.activity_log import ActivityLog
from app.database.models.organization import Organization
from app.database.session import create_session
from app.reports.exports import device_type_comparison
from app.reports.grid import MONEY_KEYS, GridRow, GridSpec, apply_filters


def _seed():
    org_id = uuid4()
    slug = f"devices-{uuid4().hex[:10]}"
    session = create_session()
    try:
        session.add(Organization(id=org_id, name="Geräte Test", slug=slug))
        session.commit()
    finally:
        session.close()
    return slug, org_id


def _client(monkeypatch, org_id, role="contract_manager"):
    actor = SimpleNamespace(organization_id=org_id, account_id=None, role=role, is_developer=False, display_name="Tester")
    for module in (catalog_routes, contract_register, register_grid):
        if hasattr(module, "current_actor"):
            monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
        if hasattr(module, "current_scope_context"):
            monkeypatch.setattr(module, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    for module in (catalog_routes, contract_register, register_grid):
        app.include_router(module.router)
    return TestClient(app)


def test_catalog_defaults_permissions_and_contract_assignment(monkeypatch):
    slug, org_id = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, org_id)
    listing = client.get("/api/catalogs/device-types", params=query).json()
    labels = {item["label"]: item for item in listing["items"]}
    assert labels["CT"]["area"] == "medizintechnik" and labels["Server"]["area_label"] == "IT"
    assert listing["areas"]["haustechnik"] == "Haustechnik"
    # Ein zweiter Abruf legt nichts doppelt an.
    assert len(client.get("/api/catalogs/device-types", params=query).json()["items"]) == len(listing["items"])

    created = client.post("/api/catalogs/device-types", params=query, json={"values": {"label": "Herz-Lungen-Maschine", "area": "medizintechnik", "keywords": "HLM"}})
    assert created.status_code == 200, created.text
    assert client.post("/api/catalogs/device-types", params=query, json={"values": {"label": "CT"}}).status_code == 409
    assert client.post("/api/catalogs/device-types", params=query, json={"values": {"label": "X", "area": "mond"}}).status_code == 422
    viewer = _client(monkeypatch, org_id, role="viewer")
    assert viewer.post("/api/catalogs/device-types", params=query, json={"values": {"label": "Y"}}).status_code == 403
    client = _client(monkeypatch, org_id)

    contract = client.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung CT Haus A"}})
    assert contract.status_code == 200, contract.text
    cid = contract.json()["contract_id"]
    path = f"/api/contracts/{cid}/device-types"
    assert client.get(path, params=query).json() == {"items": [], "suggestions": []}
    assert client.put(path, params=query, json={"items": [{"device_type_id": labels["CT"]["id"], "quantity": 0}]}).status_code == 422
    saved = client.put(path, params=query, json={"items": [
        {"device_type_id": labels["CT"]["id"], "quantity": 2, "note": "Haus A"},
        {"device_type_id": labels["MRT"]["id"]},
    ]})
    assert saved.status_code == 200, saved.text
    assert [(item["label"], item["quantity"], item["note"]) for item in saved.json()["items"]] == [("CT", 2, "Haus A"), ("MRT", None, None)]
    viewer = _client(monkeypatch, org_id, role="viewer")
    assert viewer.put(path, params=query, json={"items": []}).status_code == 403
    client = _client(monkeypatch, org_id)

    session = create_session()
    try:
        logged = session.scalars(select(ActivityLog).where(ActivityLog.object_id == UUID(cid), ActivityLog.event_name == "contract.device_types_updated")).one()
        assert logged.context_data == {"before": [], "after": ["CT × 2", "MRT"]}
    finally:
        session.close()

    # Vertragsliste: Spalte und Mehrfachwert-Filter (der Vertrag erscheint unter CT und unter MRT).
    spec = json.dumps({"columns": ["register_number", "device_types"], "filters": [{"column": "device_types", "op": "in", "value": ["MRT"]}]})
    grid = client.get("/api/register/grid", params={**query, "spec": spec})
    assert grid.status_code == 200, grid.text
    items = grid.json()["items"]
    assert len(items) == 1 and items[0]["values"]["device_types"] == "CT (2), MRT"
    values = client.get("/api/register/grid/values", params={**query, "column": "device_types"}).json()["values"]
    assert {item["value"] for item in values} >= {"CT", "MRT"}

    assert client.put(path, params=query, json={"items": []}).json()["items"] == []


def _row(number: str, devices: dict, annual, others=()):
    return GridRow(
        contract_id=uuid4(),
        values={
            **{key: None for key in MONEY_KEYS},
            "business_status": "gueltig", "term_start_date": date(2025, 1, 1), "possible_end": date(2028, 12, 31),
            "register_number": number, "short_description": f"Vertrag {number}", "partner": "Siemens", "hospital": "Nord",
            "department": "Medizintechnik", "annual_cost": annual, "cost_current_year": annual, "_currency": "EUR",
            "_device_quantities": {**devices, **{label: None for label in others}},
            "device_types": None,
        },
        ids={},
        lists={"device_types": tuple(devices) + tuple(others)},
    )


def test_comparison_cost_per_device_only_when_known_and_unambiguous():
    rows = [
        _row("001", {"CT": 2}, Decimal("40000")),
        _row("002", {"CT": None}, Decimal("30000")),
        _row("003", {"CT": 1}, Decimal("50000"), others=("MRT",)),
        _row("004", {"CT": 3}, None),
        _row("005", {}, Decimal("1000")),
    ]
    summary = device_type_comparison(rows, date(2026, 10, 11))
    assert summary["without_count"] == 1
    ct = next(item for item in summary["items"] if item["label"] == "CT")
    assert ct["count"] == 4 and ct["devices_known"] == 6 and ct["devices_missing"] == 1

    detail = device_type_comparison(rows, date(2026, 10, 11), "CT")
    by_number = {item["register_number"]: item for item in detail["items"]}
    assert by_number["001"]["cost_per_device"] == "20000.00"
    assert by_number["002"]["cost_per_device"] is None and by_number["002"]["cost_per_device_reason"] == "Anzahl Geräte nicht gepflegt"
    assert by_number["003"]["cost_per_device_reason"] == "Vertrag umfasst weitere Gerätearten"
    assert by_number["003"]["other_device_types"] == ["MRT"]
    assert by_number["004"]["cost_per_device_reason"] == "Jährliche Kosten nicht gepflegt"
    assert detail["items"][0]["register_number"] == "001"  # berechenbare zuerst
    assert detail["register_filter"] == [{"column": "device_types", "op": "in", "value": ["CT"]}]


def test_filter_in_matches_each_listed_value():
    rows = [_row("001", {"CT": 1}, None, others=("MRT",)), _row("002", {"Server": 1}, None), _row("003", {}, None)]
    spec = GridSpec.parse({"filters": [{"column": "device_types", "op": "in", "value": ["MRT"]}]})
    assert [row.values["register_number"] for row in apply_filters(rows, spec, date(2026, 10, 11), None)] == ["001"]
    spec = GridSpec.parse({"filters": [{"column": "device_types", "op": "in", "value": [""]}]})
    assert [row.values["register_number"] for row in apply_filters(rows, spec, date(2026, 10, 11), None)] == ["003"]


def test_suggestions_match_whole_words_only():
    from app.register.device_types import match_device_types

    ct = SimpleNamespace(id=uuid4(), label="CT", keywords="Computertomograph, Somatom")
    server = SimpleNamespace(id=uuid4(), label="Server", keywords="Rechenzentrum")
    found = match_device_types(["SOMATOM go.Up Computertomograph", "Victory Desk"], [ct, server])
    assert [(item["label"], item["reason"]) for item in found] == [("CT", "im Dokument: „computertomograph“")]
    # „CT“ steckt in „Victory“ – kein ganzes Wort, kein Vorschlag.
    assert match_device_types(["Victory Desk"], [ct]) == []



def test_partner_filter_by_id_and_legacy_name():
    from app.reports.grid import distinct_values, filter_labels

    siemens_a, siemens_b = uuid4(), uuid4()
    rows = [_row("001", {}, None), _row("002", {}, None), _row("003", {}, None)]
    for row, partner, name in zip(rows, (siemens_a, siemens_b, None), ("Siemens", "Siemens", "Freitext GmbH")):
        row.values["partner"] = name
        row.ids["partner"] = partner
    by_id = GridSpec.parse({"filters": [{"column": "partner", "op": "in", "value": [f"id:{siemens_b}"]}]})
    assert [row.values["register_number"] for row in apply_filters(rows, by_id, date(2026, 10, 11), None)] == ["002"]
    # Alte Links über den Namen und freie Lieferantentexte funktionieren weiter.
    by_name = GridSpec.parse({"filters": [{"column": "partner", "op": "in", "value": ["Siemens", "Freitext GmbH"]}]})
    assert len(apply_filters(rows, by_name, date(2026, 10, 11), None)) == 3
    values = distinct_values(rows, "partner")
    assert {item["value"] for item in values} == {f"id:{siemens_a}", f"id:{siemens_b}", "Freitext GmbH"}
    assert [item["label"] for item in values].count("Siemens") == 2
    assert filter_labels(rows, by_id) == {f"id:{siemens_b}": "Siemens"}
