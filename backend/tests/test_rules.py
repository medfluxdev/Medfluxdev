"""Vertragsregeln: deterministische Pruefung, Pflege, Ergebnis je Vertrag und in der Vertragsliste."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import contract_register, master_data, register_grid
from app.api.routes import rules as rule_routes
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import Account, AccountMembership
from app.database.models.organization import Organization
from app.database.session import create_session
from app.rules.service import evaluate, summary_status

ROUTES = (contract_register, register_grid, rule_routes, master_data)


def _rule(kind, threshold=None, field_key=None, types=()):
    return SimpleNamespace(id=uuid.uuid4(), label=f"Regel {kind}", rule_kind=kind, threshold=threshold, field_key=field_key, contract_type_ids=list(types))


def _contract(**values):
    base = dict(
        contract_type_id=None, term_model=None, notice_period_value=None, notice_period_unit=None,
        minimum_term_value=None, minimum_term_unit=None, initial_term_value=None, initial_term_unit=None,
        term_start_date=None, term_fixed_end_date=None, renewal_period_value=None, renewal_period_unit=None,
        price_adjustment_kind=None, price_adjustment_percent=None, partner_id=None,
    )
    return SimpleNamespace(**{**base, **values})


def test_rule_kinds_are_evaluated_without_guessing():
    notice = _rule("min_notice_months", Decimal("3"))
    assert evaluate(notice, _contract(), None).outcome == "unknown"
    assert evaluate(notice, _contract(term_model="fixed_term"), None).outcome == "na"
    assert evaluate(notice, _contract(term_model="terminable"), None).outcome == "unknown"
    assert evaluate(notice, _contract(term_model="terminable", notice_period_value=6, notice_period_unit="weeks"), None).outcome == "fail"
    passed = evaluate(notice, _contract(term_model="auto_renewal", notice_period_value=3, notice_period_unit="months"), None)
    assert passed.outcome == "pass" and passed.detail == "Kündigungsfrist 3 Monate (mindestens 3)."

    term = _rule("max_term_months", Decimal("24"))
    assert evaluate(term, _contract(term_model="terminable_min_term", minimum_term_value=3, minimum_term_unit="years"), None).outcome == "fail"
    assert evaluate(term, _contract(term_model="fixed_term", term_start_date=date(2026, 1, 1), term_fixed_end_date=date(2027, 12, 31)), None).outcome == "pass"
    assert evaluate(term, _contract(term_model="perpetual"), None).outcome == "na"

    renewal = _rule("max_renewal_months", Decimal("12"))
    assert evaluate(renewal, _contract(term_model="terminable"), None).outcome == "na"
    assert evaluate(renewal, _contract(term_model="auto_renewal", renewal_period_value=2, renewal_period_unit="years"), None).outcome == "fail"

    price = _rule("max_price_increase_percent", Decimal("3"))
    assert evaluate(price, _contract(), None).outcome == "unknown"
    assert evaluate(price, _contract(price_adjustment_kind="fixed"), None).outcome == "pass"
    assert evaluate(price, _contract(price_adjustment_kind="index"), None).outcome == "unknown"
    assert evaluate(price, _contract(price_adjustment_kind="percent", price_adjustment_percent=Decimal("4.5")), None).outcome == "fail"

    cost = _rule("max_annual_cost", Decimal("10000"))
    assert evaluate(cost, _contract(), None).outcome == "unknown"
    over = evaluate(cost, _contract(), Decimal("12000.00"))
    assert over.outcome == "fail" and over.detail == "12.000,00 € jährlich (Grenze 10.000,00 €)."

    required = _rule("required_field", field_key="partner_id")
    assert evaluate(required, _contract(), None).detail == "Vertragspartner fehlt."
    assert evaluate(required, _contract(partner_id=uuid.uuid4()), None).outcome == "pass"

    scoped = _rule("required_field", field_key="partner_id", types=[str(uuid.uuid4())])
    assert evaluate(scoped, _contract(contract_type_id=uuid.uuid4()), None).outcome == "na"

    results = [evaluate(notice, _contract(), None), evaluate(required, _contract(partner_id=uuid.uuid4()), None)]
    assert summary_status(results) == "Unvollständig"
    assert summary_status([evaluate(scoped, _contract(), None)]) is None


def _seed():
    ids = {key: uuid4() for key in ("org", "admin", "manager")}
    slug = f"regeln-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Regel Klinik", slug=slug))
        for key in ("admin", "manager"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@x.invalid", display_name=key.title(), credential_digest="t"))
        session.flush()
        session.add_all([
            AccountMembership(organization_id=ids["org"], account_id=ids["admin"], role="admin"),
            AccountMembership(organization_id=ids["org"], account_id=ids["manager"], role="contract_manager"),
        ])
        session.commit()
    finally:
        session.close()
    return slug, ids


def _as(monkeypatch, ids, key, role):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())
    for module in ROUTES:
        monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
        if hasattr(module, "current_scope_context"):
            monkeypatch.setattr(module, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    for module in ROUTES:
        app.include_router(module.router)
    return TestClient(app)


def test_rules_are_maintained_by_admins_and_shown_per_contract_and_in_the_list(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    manager = _as(monkeypatch, ids, "manager", "contract_manager")
    assert manager.post("/api/rules", params=query, json={"values": {"label": "x", "rule_kind": "min_notice_months", "threshold": 3}}).status_code == 403
    short = manager.post("/api/contracts", params=query, json={"values": {
        "short_description": "Wartung kurz", "term_model": "terminable", "term_start_date": "2026-01-01",
        "notice_period_value": 4, "notice_period_unit": "weeks", "notice_to": "month_end",
    }}).json()["contract_id"]
    long = manager.post("/api/contracts", params=query, json={"values": {
        "short_description": "Wartung lang", "term_model": "terminable", "term_start_date": "2026-01-01",
        "notice_period_value": 6, "notice_period_unit": "months", "notice_to": "quarter_end",
    }}).json()["contract_id"]

    admin = _as(monkeypatch, ids, "admin", "admin")
    assert admin.post("/api/rules", params=query, json={"values": {"label": "Ohne Grenzwert", "rule_kind": "min_notice_months"}}).status_code == 422
    assert admin.post("/api/rules", params=query, json={"values": {"label": "Feld fehlt", "rule_kind": "required_field"}}).status_code == 422
    assert admin.post("/api/rules", params=query, json={"values": {"label": "Unbekannt", "rule_kind": "gibt_es_nicht", "threshold": 1}}).status_code == 422
    notice = admin.post("/api/rules", params=query, json={"values": {"label": "Kündigungsfrist ≥ 3 Monate", "rule_kind": "min_notice_months", "threshold": "3"}})
    assert notice.status_code == 200, notice.text
    partner = admin.post("/api/rules", params=query, json={"values": {"label": "Partner erfasst", "rule_kind": "required_field", "field_key": "partner_id"}}).json()

    listed = admin.get("/api/rules", params=query).json()
    assert [item["label"] for item in listed["items"]] == ["Kündigungsfrist ≥ 3 Monate", "Partner erfasst"]
    assert {kind["key"] for kind in listed["kinds"]} >= {"min_notice_months", "required_field"}

    result = admin.get(f"/api/contracts/{short}/rules", params=query).json()
    assert result["status"] == "Verstoß"
    assert {item["label"]: item["outcome"] for item in result["items"]} == {"Kündigungsfrist ≥ 3 Monate": "fail", "Partner erfasst": "fail"}

    grid = admin.get("/api/register/grid", params={**query, "spec": json.dumps({"columns": ["register_number", "rules_status", "rules_violated"]})}).json()
    by_id = {item["contract_id"]: item["values"] for item in grid["items"]}
    assert by_id[short]["rules_violated"] == "Kündigungsfrist ≥ 3 Monate, Partner erfasst"
    assert by_id[long]["rules_violated"] == "Partner erfasst"

    usage = admin.get("/api/master-data/usage", params={**query, "kind": "rule"}).json()["counts"]
    assert usage == {notice.json()["id"]: 1, partner["id"]: 2}

    # Deaktivierte Regeln zaehlen nicht mehr; die Liste baut sich neu auf.
    assert admin.patch(f"/api/rules/{partner['id']}", params=query, json={"values": {"is_active": False}}).status_code == 200
    grid = admin.get("/api/register/grid", params={**query, "spec": json.dumps({"columns": ["register_number", "rules_status"]})}).json()
    statuses = {item["contract_id"]: item["values"]["rules_status"] for item in grid["items"]}
    assert statuses == {short: "Verstoß", long: "Erfüllt"}
