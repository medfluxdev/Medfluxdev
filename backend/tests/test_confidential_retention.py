"""H8.2 confidential contracts, H8.1 permission matrix, H9 retention, AI data-protection detection."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import catalogs as catalog_routes
from app.api.routes import contract_register, contracts as contract_routes
from app.auth.permissions import can, granted, matrix
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import Account, AccountMembership, Contract
from app.database.models.deadlines import ContractDeadline
from app.database.models.organization import Organization
from app.database.models.register import ContractFieldProvenance
from app.database.session import create_session
from app.deadlines.system import sync_system_deadlines
from app.register.documents import detect_data_protection


def test_permission_matrix_roles():
    admin = SimpleNamespace(role="admin", is_developer=False)
    manager = SimpleNamespace(role="contract_manager", is_developer=False)
    viewer = SimpleNamespace(role="viewer", is_developer=False)
    developer = SimpleNamespace(role="viewer", is_developer=True)
    assert can(manager, "finance.edit") and not can(manager, "catalog.admin")
    assert not can(viewer, "contract.edit") and can(viewer, "contract.read")
    assert can(admin, "contract.confidential_manage") and not can(manager, "contract.confidential_manage")
    assert can(developer, "user.admin")
    assert "export" in granted(manager) and "export" not in granted(viewer)
    assert {p["key"] for p in matrix()["permissions"]} >= {"contract.edit", "views.global", "job.admin"}


def _seed():
    ids = {key: uuid4() for key in ("org", "admin", "owner", "other", "viewer")}
    slug = f"conf-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Vertraulich Test", slug=slug))
        for key in ("admin", "owner", "other", "viewer"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@x.invalid", display_name=key.title(), credential_digest="t"))
        session.flush()
        for key, role in (("admin", "admin"), ("owner", "contract_manager"), ("other", "contract_manager"), ("viewer", "viewer")):
            session.add(AccountMembership(organization_id=ids["org"], account_id=ids[key], role=role))
        session.commit()
    finally:
        session.close()
    return slug, ids


def _as(monkeypatch, ids, key, role):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())
    for module in (contract_register, catalog_routes):
        monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
        monkeypatch.setattr(module, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    app.include_router(contract_register.router)
    app.include_router(catalog_routes.router)
    app.include_router(contract_routes.router)
    return TestClient(app)


def test_confidential_contract_visibility(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    owner = _as(monkeypatch, ids, "owner", "contract_manager")
    cid = owner.post("/api/contracts", params=query, json={"values": {"short_description": "Beratervertrag GF"}}).json()["contract_id"]
    assert owner.put(f"/api/contracts/{cid}/confidentiality", params=query, json={"is_confidential": True}).status_code == 403

    admin = _as(monkeypatch, ids, "admin", "admin")
    marked = admin.put(f"/api/contracts/{cid}/confidentiality", params=query,
                       json={"is_confidential": True, "grant_account_ids": [str(ids["viewer"])]})
    assert marked.status_code == 200, marked.text
    assert marked.json()["confidentiality"]["grants"][0]["display_name"] == "Viewer"
    assert admin.get(f"/api/contracts/{cid}/register", params=query).status_code == 200

    other = _as(monkeypatch, ids, "other", "contract_manager")
    assert other.get(f"/api/contracts/{cid}/register", params=query).status_code == 404
    assert cid not in [item["contract_id"] for item in other.get("/api/contracts", params=query).json()["items"]]
    assert other.get(f"/api/contracts/{cid}", params=query).status_code == 404

    owner = _as(monkeypatch, ids, "owner", "contract_manager")
    assert owner.get(f"/api/contracts/{cid}/register", params=query).status_code == 200
    viewer = _as(monkeypatch, ids, "viewer", "viewer")
    assert viewer.get(f"/api/contracts/{cid}/register", params=query).status_code == 200

    monkeypatch.setattr(scope_queries, "current_identity", lambda: None)
    session = create_session()
    try:
        assert UUID(cid) in scope_queries.hidden_confidential_ids(session, ids["org"])
    finally:
        session.close()


def test_confidential_contract_type_hides_contracts(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _as(monkeypatch, ids, "admin", "admin")
    types = admin.get("/api/catalogs/contract-types", params=query).json()["contract_types"]
    secret = next(item for item in types if item["is_confidential"])
    assert secret["retention_years"] == 10
    cid = admin.post("/api/contracts", params=query, json={"values": {"short_description": "LOI", "contract_type_id": secret["id"]}}).json()["contract_id"]
    other = _as(monkeypatch, ids, "other", "contract_manager")
    assert other.get(f"/api/contracts/{cid}/register", params=query).status_code == 404


def test_retention_from_type_or_contract_and_review_deadline(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _as(monkeypatch, ids, "admin", "admin")
    wartung = next(item for item in admin.get("/api/catalogs/contract-types", params=query).json()["contract_types"] if item["code"] == "wartung")
    created = admin.post("/api/contracts", params=query, json={"values": {
        "short_description": "Alter Wartungsvertrag", "contract_type_id": wartung["id"], "term_model": "fixed_term",
        "term_start_date": "2014-01-01", "term_fixed_end_date": "2015-06-30",
    }}).json()
    cid = created["contract_id"]
    assert created["retention"] == {"years": 10, "source": "contract_type", "contract_end": "2015-06-30", "deletion_from": "2026-01-01"}

    session = create_session()
    try:
        contract = session.get(Contract, UUID(cid))
        contract.supplier = "Altlieferant"
        session.commit()
    finally:
        session.close()
    admin.post(f"/api/contracts/{cid}/status", params=query, json={"target": "gueltig"})
    ended = admin.post(f"/api/contracts/{cid}/status", params=query, json={"target": "beendet", "effective_date": "2015-06-30"})
    assert ended.status_code == 200, ended.text
    session = create_session()
    try:
        contract = session.get(Contract, UUID(cid))
        sync_system_deadlines(session, contract, date(2026, 10, 4))
        session.commit()
        review = session.scalars(select(ContractDeadline).where(
            ContractDeadline.contract_id == contract.id, ContractDeadline.system_key == "retention_review"
        )).one()
        assert review.due_date == date(2026, 1, 1) and review.status == "open"
    finally:
        session.close()

    shorter = admin.patch(f"/api/contracts/{cid}/register", params=query, json={"changes": {"retention_years_after_end": 15}})
    assert shorter.json()["retention"]["deletion_from"] == "2031-01-01"
    assert shorter.json()["retention"]["source"] == "contract"


def test_ai_detects_data_protection_without_overriding_humans(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _as(monkeypatch, ids, "admin", "admin")
    cid = UUID(admin.post("/api/contracts", params=query, json={"values": {"short_description": "Fernwartung PACS"}}).json()["contract_id"])
    session = create_session()
    try:
        contract = session.get(Contract, cid)
        assert detect_data_protection(session, contract, "Ohne Bezug", None) is False
        assert detect_data_protection(session, contract, "Anlage 3: Vereinbarung zur Auftragsverarbeitung nach Art. 28 DSGVO", None) is True
        session.commit()
        row = session.scalars(select(ContractFieldProvenance).where(
            ContractFieldProvenance.contract_id == cid, ContractFieldProvenance.field_key == "data_protection_relevant"
        )).one()
        assert contract.data_protection_relevant is True and row.origin == "ai"
    finally:
        session.close()

    admin.patch(f"/api/contracts/{cid}/register", params=query, json={"changes": {"data_protection_relevant": False}})
    session = create_session()
    try:
        contract = session.get(Contract, cid)
        detect_data_protection(session, contract, "Verarbeitung personenbezogener Daten", None)
        session.commit()
        row = session.scalars(select(ContractFieldProvenance).where(
            ContractFieldProvenance.contract_id == cid, ContractFieldProvenance.field_key == "data_protection_relevant"
        )).one()
        assert contract.data_protection_relevant is False
        assert row.ai_proposed_value["value"] is True
    finally:
        session.close()
