"""H4 finance API on PostgreSQL: entries, summary, services, allocations,
AI suggestions, price adjustment projection, export and list integration."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import contract_finance, contract_register, contracts as contract_routes
from app.core.scope_context import ScopeContext
from app.database.models import Account, AccountMembership
from app.database.models.organization import Organization
from app.database.models.organization_structure import CostCenter, Hospital
from app.database.session import create_session
from app.finance import service as finance_service
from app.models.contract import Contract as ExtractedContract


def _seed():
    ids = {key: uuid4() for key in ("org", "hospital", "other_hospital", "cc1", "cc2", "cc_foreign", "admin", "viewer")}
    slug = f"finance-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Finanz Test", slug=slug))
        session.add_all([
            Hospital(id=ids["hospital"], organization_id=ids["org"], name="Klinikum", code="K"),
            Hospital(id=ids["other_hospital"], organization_id=ids["org"], name="Anderes", code="A"),
        ])
        session.flush()
        session.add_all([
            CostCenter(id=ids["cc1"], organization_id=ids["org"], hospital_id=ids["hospital"], code="471100", name="Radiologie"),
            CostCenter(id=ids["cc2"], organization_id=ids["org"], hospital_id=ids["hospital"], code="471200", name="Kardiologie"),
            CostCenter(id=ids["cc_foreign"], organization_id=ids["org"], hospital_id=ids["other_hospital"], code="999", name="Fremd"),
        ])
        for key in ("admin", "viewer"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@x.invalid", display_name=key.title(), credential_digest="t"))
        session.flush()
        session.add(AccountMembership(organization_id=ids["org"], account_id=ids["admin"], role="admin"))
        session.commit()
    finally:
        session.close()
    return slug, ids


def _client(monkeypatch, ids, role="admin"):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role=role, is_developer=False, display_name="Admin")
    monkeypatch.setattr(contract_register, "current_actor", lambda request, organization_slug: actor)
    monkeypatch.setattr(contract_register, "current_scope_context", lambda: ScopeContext())
    app = FastAPI()
    app.include_router(contract_register.router)
    app.include_router(contract_finance.router)
    app.include_router(contract_routes.router)
    return TestClient(app)


def _contract(client, slug, ids):
    response = client.post("/api/contracts", params={"organization_slug": slug}, json={
        "hospital_id": str(ids["hospital"]),
        "values": {"short_description": "Wartung MRT", "term_model": "fixed_term", "term_start_date": "2026-01-01",
                   "term_fixed_end_date": "2027-12-31"},
    })
    assert response.status_code == 200, response.text
    return response.json()["contract_id"]


def test_entries_summary_services_allocations_and_export(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids)
    cid = _contract(client, slug, ids)
    base = f"/api/contracts/{cid}/finance"

    assert client.post(f"{base}/entries", params=query, json={"values": {"label": "x", "amount": -1, "valid_from": "2026-01-01"}}).status_code == 422
    assert client.post(f"{base}/entries", params=query, json={"values": {"label": "x", "amount": 1, "valid_from": "2026-05-01", "valid_to": "2026-01-01"}}).status_code == 422
    assert client.post(f"{base}/entries", params=query, json={"values": {"label": "x", "amount": 1, "valid_from": "2026-01-01", "bogus": 1}}).status_code == 422

    created = client.post(f"{base}/entries", params=query, json={"values": {
        "label": "Wartungspauschale", "amount": "3500", "amount_basis": "net", "vat_rate": "19", "interval": "monthly",
        "valid_from": "2026-01-01", "cost_type_code": "wartung",
    }})
    assert created.status_code == 200, created.text
    data = created.json()
    [summary] = data["summaries"]
    assert summary["expense"]["total_term"] == {"net": "84000.00", "gross": "99960.00"}
    assert summary["expense"]["annual_run_rate"]["gross"] == "49980.00"
    entry_id = data["entries"][0]["id"]
    assert data["entries"][0]["origin"] == "manual" and data["entries"][0]["created_by_name"] == "Admin"

    income = client.post(f"{base}/entries", params=query, json={"values": {
        "direction": "income", "label": "Weiterberechnung", "amount": "100", "vat_rate": "0", "interval": "annual", "valid_from": "2026-01-01",
    }}).json()
    assert income["summaries"][0]["income"]["total_term"]["net"] == "200.00"

    patched = client.patch(f"{base}/entries/{entry_id}", params=query, json={"values": {"amount": "4000"}})
    assert patched.json()["summaries"][0]["expense"]["total_term"]["net"] == "96000.00"

    service = client.post(f"{base}/services", params=query, json={"values": {"label": "Stundensatz Techniker", "amount": "125", "unit": "pro Stunde"}})
    assert service.status_code == 200 and service.json()["services"][0]["plus_vat"] is True

    bad_sum = client.put(f"{base}/allocations", params=query, json={"items": [
        {"cost_center_id": str(ids["cc1"]), "share_percent": 60}, {"cost_center_id": str(ids["cc2"]), "share_percent": 30},
    ]})
    assert bad_sum.status_code == 422
    foreign = client.put(f"{base}/allocations", params=query, json={"items": [{"cost_center_id": str(ids["cc_foreign"]), "share_percent": 100}]})
    assert foreign.status_code == 422
    split = client.put(f"{base}/allocations", params=query, json={"items": [
        {"cost_center_id": str(ids["cc1"]), "share_percent": 70, "recharge_mode": "teilweise"},
        {"cost_center_id": str(ids["cc2"]), "share_percent": 30},
    ]})
    assert split.status_code == 200, split.text
    allocations = split.json()["allocations"]
    assert [(a["code"], a["share_percent"], a["annual_net"]) for a in allocations] == [("471100", "70.00", "33600.00"), ("471200", "30.00", "14400.00")]
    assert split.json()["primary_cost_center_id"] == str(ids["cc1"])

    exported = client.get(f"{base}/export.csv", params={**query, "income": "false"})
    assert exported.status_code == 200
    text = exported.content.decode("utf-8-sig")
    assert "Wartungspauschale;wartung;4000,00;netto;19,00" in text and "Weiterberechnung" not in text

    listing = client.get("/api/contracts", params=query).json()["items"]
    row = next(item for item in listing if item["contract_id"] == cid)
    assert row["annual_cost"]["amount"] == "48000.00" and row["annual_cost"]["unreliable"] is False

    assert client.delete(f"{base}/entries/{entry_id}", params=query).status_code == 200
    viewer = _client(monkeypatch, ids, role="viewer")
    assert viewer.post(f"{base}/entries", params=query, json={"values": {"label": "x", "amount": 1, "valid_from": "2026-01-01"}}).status_code == 403
    assert viewer.get(base, params=query).status_code == 200


def test_ai_suggestions_accept_dismiss_and_price_adjustment(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, ids)
    cid = _contract(client, slug, ids)
    base = f"/api/contracts/{cid}/finance"
    extracted = ExtractedContract.model_validate({"costs": {
        "monthly_cost": {"amount": 1000, "currency": "EUR", "period": "monthly"},
        "tax_basis": "net", "tax_rate_percent": 19,
        "hourly_rate": {"amount": 125, "currency": "EUR"},
    }})
    monkeypatch.setattr(finance_service, "accepted_extraction", lambda session, contract: extracted)

    data = client.get(base, params=query).json()
    assert [item["key"] for item in data["suggestions"]["entries"]] == ["costs.monthly_cost"]
    assert [item["key"] for item in data["suggestions"]["services"]] == ["costs.hourly_rate"]

    accepted = client.post(f"{base}/suggestions/finance/costs.monthly_cost/accept", params=query, json={"values": {"cost_type_code": "wartung"}})
    assert accepted.status_code == 200, accepted.text
    entry = accepted.json()["entries"][0]
    assert (entry["origin"], entry["source_key"], entry["amount"], entry["cost_type_code"]) == ("ai_confirmed", "costs.monthly_cost", "1000.00", "wartung")
    assert accepted.json()["suggestions"]["entries"] == []
    assert client.post(f"{base}/suggestions/finance/costs.monthly_cost/accept", params=query, json={}).status_code == 404

    dismissed = client.post(f"{base}/suggestions/service/costs.hourly_rate/dismiss", params=query)
    assert dismissed.json()["suggestions"]["services"] == []

    client.patch(f"/api/contracts/{cid}/register", params=query, json={"changes": {
        "price_adjustment_kind": "percent", "price_adjustment_percent": "3", "price_adjustment_next_date": f"{date.today().year + 1}-01-01",
    }})
    projected = client.get(base, params=query).json()
    assert projected["price_adjustment"]["percent"] == "3.000"
    assert projected["summaries"][0]["projected_adjustment"] is True
    assert any("prozentuale Preisanpassung" in note for note in projected["summaries"][0]["notes"])
