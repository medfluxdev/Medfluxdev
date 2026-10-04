"""Schritt 13a: Entscheidungsvorlage vor Kuendigungsfristen (nur Beratung)."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import contract_finance, contract_register, register_grid
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import Account, AccountMembership, Contract
from app.database.models.lifecycle import ContractLifecycleDecision
from app.database.models.organization import Organization
from app.database.models.register import ContractPartner
from app.database.session import create_session
from app.reports.renewal import renewal_brief, urgency


def test_urgency_levels():
    today = date(2026, 10, 4)
    assert urgency(None, today) == "unknown"
    assert urgency(date(2026, 10, 1), today) == "missed"
    assert urgency(date(2026, 10, 20), today) == "critical"
    assert urgency(date(2026, 12, 1), today) == "soon"
    assert urgency(date(2027, 6, 1), today) == "planned"


def _setup(monkeypatch):
    ids = {key: uuid4() for key in ("org", "admin", "other", "partner")}
    slug = f"renew-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Verlängerung Test", slug=slug))
        for key in ("admin", "other"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@x.invalid", display_name=key.title(), credential_digest="t"))
        session.flush()
        session.add(AccountMembership(organization_id=ids["org"], account_id=ids["admin"], role="admin"))
        session.add(AccountMembership(organization_id=ids["org"], account_id=ids["other"], role="contract_manager"))
        session.add(ContractPartner(id=ids["partner"], organization_id=ids["org"], short_name="MEDTEC", name1="Medtec GmbH"))
        session.commit()
    finally:
        session.close()

    def client(key, role):
        actor = SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())
        for module in (contract_register, register_grid):
            monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
            monkeypatch.setattr(module, "current_scope_context", lambda: ScopeContext())
        monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
        app = FastAPI()
        for module in (contract_register, contract_finance, register_grid):
            app.include_router(module.router)
        return TestClient(app)

    return slug, ids, client


def test_brief_for_auto_renewal_with_costs_partner_and_decision(monkeypatch):
    slug, ids, client = _setup(monkeypatch)
    query = {"organization_slug": slug}
    admin = client("admin", "admin")
    values = {
        "short_description": "Wartung CT", "partner_id": str(ids["partner"]), "term_model": "auto_renewal",
        "term_start_date": "2024-01-01", "initial_term_value": 3, "initial_term_unit": "years",
        "notice_period_value": 3, "notice_period_unit": "months", "notice_to": "contract_end",
        "renewal_period_value": 1, "renewal_period_unit": "years",
        "price_adjustment_kind": "percent", "price_adjustment_percent": "3", "price_adjustment_next_date": "2027-01-01",
    }
    cid = admin.post("/api/contracts", params=query, json={"values": values}).json()["contract_id"]
    admin.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung MRT", "partner_id": str(ids["partner"])}})
    admin.post(f"/api/contracts/{cid}/finance/entries", params=query, json={"values": {
        "label": "Pauschale", "amount": "1000", "vat_rate": "19", "interval": "monthly", "valid_from": "2024-01-01",
    }})
    session = create_session()
    try:
        contract = session.get(Contract, UUID(cid))
        brief = renewal_brief(session, contract, date(2026, 8, 15))
    finally:
        session.close()

    assert brief["cancel_by"] == "2026-09-30" and brief["days_left"] == 46 and brief["urgency"] == "soon"
    assert brief["next_end_if_no_action"] == "2027-12-31"
    assert "verlängert sich der Vertrag um 1 Jahr bis 31.12.2027" in brief["if_no_action"]
    assert brief["renewal_cost"] == "12360.00"  # 12 x 1000 x 1,03
    texts = " ".join(hint["text"] for hint in brief["hints"])
    assert "Bis 30.09.2026 entscheiden" in texts
    assert "12.360,00 €" in texts and "+3 %" in texts
    assert "1 weitere laufende Verträge" in texts
    assert all(hint["reason"] for hint in brief["hints"])
    assert brief["decision"] is None

    session = create_session()
    try:
        session.add(ContractLifecycleDecision(
            organization_id=ids["org"], contract_id=UUID(cid), decision="renegotiate", status="planned",
            actor_display_name="Admin",
        ))
        session.commit()
        brief = renewal_brief(session, session.get(Contract, UUID(cid)), date(2026, 8, 15))
    finally:
        session.close()
    assert brief["decision"]["label"] == "Neu verhandeln"
    assert not any(hint["kind"] == "action" for hint in brief["hints"])


def test_renewal_list_and_brief_route_respect_scope(monkeypatch):
    slug, ids, client = _setup(monkeypatch)
    query = {"organization_slug": slug}
    admin = client("admin", "admin")
    start = (date.today() - timedelta(days=400)).isoformat()
    cid = admin.post("/api/contracts", params=query, json={"values": {
        "short_description": "Reinigung", "term_model": "terminable", "term_start_date": start,
        "notice_period_value": 1, "notice_period_unit": "months", "notice_to": "month_end",
    }}).json()["contract_id"]
    admin.put(f"/api/contracts/{cid}/confidentiality", params=query, json={"is_confidential": True})

    listed = admin.get("/api/register/renewals", params=query).json()
    assert [item["contract_id"] for item in listed["items"]] == [cid]
    assert listed["items"][0]["urgency"] in ("critical", "soon")
    brief = admin.get(f"/api/contracts/{cid}/renewal-brief", params=query)
    assert brief.status_code == 200 and "läuft der Vertrag weiter" in brief.json()["if_no_action"]

    other = client("other", "contract_manager")
    assert other.get("/api/register/renewals", params=query).json()["items"] == []
    assert other.get(f"/api/contracts/{cid}/renewal-brief", params=query).status_code == 404


def test_fixed_term_needs_no_notice(monkeypatch):
    slug, ids, client = _setup(monkeypatch)
    admin = client("admin", "admin")
    cid = admin.post("/api/contracts", params={"organization_slug": slug}, json={"values": {
        "short_description": "Projekt", "term_model": "fixed_term", "term_start_date": "2026-01-01", "term_fixed_end_date": "2028-12-31",
    }}).json()["contract_id"]
    session = create_session()
    try:
        brief = renewal_brief(session, session.get(Contract, UUID(cid)), date(2026, 10, 4))
    finally:
        session.close()
    assert brief["urgency"] == "none"
    assert brief["if_no_action"].startswith("Der Vertrag endet am 31.12.2028 ohne Kündigung")
