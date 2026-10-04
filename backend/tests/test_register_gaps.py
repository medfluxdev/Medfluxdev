"""Nachzuegler zum HYDMedia-Plan: gepflegte Jahreskosten in der Vertragsliste."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import contract_finance, contract_register, contracts as contract_routes
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import Account, AccountMembership, Contract
from app.database.models.organization import Organization
from app.database.session import create_session
from app.finance.service import refresh_all_maintained_costs


def _seed():
    ids = {key: uuid4() for key in ("org", "admin")}
    slug = f"gaps-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Lücken Test", slug=slug))
        session.add(Account(id=ids["admin"], login_name=f"admin-{slug}@x.invalid", display_name="Admin", credential_digest="t"))
        session.flush()
        session.add(AccountMembership(organization_id=ids["org"], account_id=ids["admin"], role="admin"))
        session.commit()
    finally:
        session.close()
    return slug, ids


def _client(monkeypatch, ids):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role="admin", is_developer=False, display_name="Admin")
    monkeypatch.setattr(contract_register, "current_actor", lambda request, organization_slug: actor)
    monkeypatch.setattr(contract_register, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    for module in (contract_register, contract_finance, contract_routes):
        app.include_router(module.router)
    return TestClient(app)


def test_contract_list_sorts_and_filters_by_maintained_annual_cost(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids)
    created = {}
    for name, amount in (("Klein", "100"), ("Groß", "2000"), ("Ohne", None)):
        cid = client.post("/api/contracts", params=query, json={"values": {
            "short_description": name, "term_model": "terminable", "term_start_date": "2026-01-01",
            "notice_period_value": 3, "notice_period_unit": "months", "notice_to": "month_end",
        }}).json()["contract_id"]
        created[name] = cid
        if amount:
            response = client.post(f"/api/contracts/{cid}/finance/entries", params=query, json={"values": {
                "label": "Pauschale", "amount": amount, "vat_rate": "19", "interval": "monthly", "valid_from": "2026-01-01",
            }})
            assert response.status_code == 200, response.text

    session = create_session()
    try:
        big = session.get(Contract, UUID(created["Groß"]))
        assert big.maintained_annual_cost == Decimal("24000.00") and big.maintained_annual_currency == "EUR"
        assert session.get(Contract, UUID(created["Ohne"])).maintained_annual_cost is None
    finally:
        session.close()

    ordered = client.get("/api/contracts", params={**query, "sort": "annual_cost", "direction": "desc", "business_status": []}).json()["items"]
    ids_in_order = [item["contract_id"] for item in ordered]
    assert ids_in_order.index(created["Groß"]) < ids_in_order.index(created["Klein"])
    expensive = client.get("/api/contracts", params={**query, "annual_cost_min": "10000"}).json()["items"]
    assert [item["contract_id"] for item in expensive] == [created["Groß"]]

    # Preisanpassung in den Stammdaten wirkt ueber den Zwischenspeicher.
    client.patch(f"/api/contracts/{created['Klein']}/register", params=query, json={"changes": {
        "price_adjustment_kind": "percent", "price_adjustment_percent": "10", "price_adjustment_next_date": "2026-02-01",
    }})
    session = create_session()
    try:
        assert session.get(Contract, UUID(created["Klein"])).maintained_annual_cost == Decimal("1320.00")
        contract = session.get(Contract, UUID(created["Groß"]))
        contract.maintained_annual_cost = None
        session.commit()
        assert refresh_all_maintained_costs(session, date.today(), ids["org"]) == 2
        session.commit()
        assert session.get(Contract, UUID(created["Groß"])).maintained_annual_cost == Decimal("24000.00")
    finally:
        session.close()


def test_classic_list_views_are_stored_on_the_server(monkeypatch):
    from app.api.routes import register_grid

    slug, ids = _seed()
    query = {"organization_slug": slug}
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role="admin", is_developer=False, display_name="Admin")
    monkeypatch.setattr(register_grid, "current_actor", lambda request, organization_slug: actor)
    app = FastAPI()
    app.include_router(register_grid.router)
    client = TestClient(app)

    created = client.post("/api/register/views", params=query, json={
        "name": "Kritisch", "view_kind": "contracts", "config": {"query": "?risk=high&page=3&sort=annual_cost"},
    })
    assert created.status_code == 200, created.text
    assert created.json()["config"] == {"query": "risk=high&sort=annual_cost"}
    listed = client.get("/api/register/views", params={**query, "kind": "contracts"}).json()["items"]
    assert [item["name"] for item in listed] == ["Kritisch"]
    assert "Kritisch" not in [item["name"] for item in client.get("/api/register/views", params=query).json()["items"]]
    assert client.post("/api/register/views", params=query, json={"name": "x", "view_kind": "contracts", "config": {"query": 5}}).status_code == 422
    assert client.post("/api/register/views", params=query, json={"name": "x", "view_kind": "other"}).status_code == 422
    assert client.get("/api/register/views", params={**query, "kind": "other"}).status_code == 422


def test_cost_centre_split_in_grid_and_portfolio(monkeypatch):
    from app.api.routes import register_grid
    from app.database.models.organization_structure import CostCenter, Hospital

    slug, ids = _seed()
    query = {"organization_slug": slug}
    hospital, cc1, cc2 = uuid4(), uuid4(), uuid4()
    session = create_session()
    try:
        session.add(Hospital(id=hospital, organization_id=ids["org"], name="Klinikum", code="K"))
        session.flush()
        session.add_all([
            CostCenter(id=cc1, organization_id=ids["org"], hospital_id=hospital, code="4711", name="Radiologie"),
            CostCenter(id=cc2, organization_id=ids["org"], hospital_id=hospital, code="4712", name="IT"),
        ])
        session.commit()
    finally:
        session.close()
    client = _client(monkeypatch, ids)
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role="admin", is_developer=False, display_name="Admin")
    monkeypatch.setattr(register_grid, "current_actor", lambda request, organization_slug: actor)
    monkeypatch.setattr(register_grid, "current_scope_context", lambda: ScopeContext())
    client.app.include_router(register_grid.router)

    cid = client.post("/api/contracts", params=query, json={"hospital_id": str(hospital), "values": {
        "short_description": "Server", "term_model": "terminable", "term_start_date": "2026-01-01",
        "notice_period_value": 3, "notice_period_unit": "months", "notice_to": "month_end",
    }}).json()["contract_id"]
    client.post(f"/api/contracts/{cid}/finance/entries", params=query, json={"values": {
        "label": "Pauschale", "amount": "1000", "vat_rate": "19", "interval": "monthly", "valid_from": "2026-01-01",
    }})
    split = client.put(f"/api/contracts/{cid}/finance/allocations", params=query, json={"items": [
        {"cost_center_id": str(cc1), "share_percent": 60}, {"cost_center_id": str(cc2), "share_percent": 40},
    ]})
    assert split.status_code == 200, split.text

    import json as _json
    grid = client.get("/api/register/grid", params={**query, "spec": _json.dumps({"columns": ["register_number", "cost_center", "cost_allocation"]})}).json()
    assert grid["items"][0]["values"]["cost_allocation"] == "Radiologie 60 %, IT 40 %"
    report = client.get("/api/register/reports/portfolio", params=query).json()
    by_cc = {item["label"]: item["annual_cost"] for item in report["cost_by"]["cost_center"]}
    assert by_cc == {"Radiologie": "7200.00", "IT": "4800.00"}


def test_grid_cache_rebuilds_after_any_change(monkeypatch):
    import json as _json

    from app.api.routes import register_grid
    from app.database.models.organization_structure import Hospital

    slug, ids = _seed()
    query = {"organization_slug": slug}
    hospital = uuid4()
    session = create_session()
    try:
        session.add(Hospital(id=hospital, organization_id=ids["org"], name="Alt", code="A"))
        session.commit()
    finally:
        session.close()
    client = _client(monkeypatch, ids)
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role="admin", is_developer=False, display_name="Admin")
    monkeypatch.setattr(register_grid, "current_actor", lambda request, organization_slug: actor)
    monkeypatch.setattr(register_grid, "current_scope_context", lambda: ScopeContext())
    client.app.include_router(register_grid.router)
    cid = client.post("/api/contracts", params=query, json={"hospital_id": str(hospital), "values": {"short_description": "Vorher"}}).json()["contract_id"]

    spec = {"organization_slug": slug, "spec": _json.dumps({"columns": ["short_description", "hospital", "annual_cost"]}), "include_tree": "true"}
    first = client.get("/api/register/grid", params=spec).json()
    assert first["items"][0]["values"]["short_description"] == "Vorher"
    assert first["tree"][0]["label"] == "Alt"

    client.patch(f"/api/contracts/{cid}/register", params=query, json={"changes": {"short_description": "Nachher"}})
    client.post(f"/api/contracts/{cid}/finance/entries", params=query, json={"values": {
        "label": "Pauschale", "amount": "100", "vat_rate": "19", "interval": "monthly", "valid_from": "2026-01-01",
    }})
    session = create_session()
    try:
        session.get(Hospital, hospital).name = "Neu"
        session.commit()
    finally:
        session.close()
    second = client.get("/api/register/grid", params=spec).json()
    assert second["items"][0]["values"]["short_description"] == "Nachher"
    assert second["items"][0]["values"]["annual_cost"] == "1200.00"
    assert second["items"][0]["values"]["hospital"] == "Neu"
