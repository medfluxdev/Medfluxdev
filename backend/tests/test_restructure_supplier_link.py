"""Restructure Phase H: Lieferantennamen gesammelt einem Vertragspartner zuordnen (U8, T23)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.api.routes import catalogs as catalog_routes
from app.core.scope_context import ScopeContext
from app.database.models import ActivityLog, Contract
from app.database.models.register import ContractFieldProvenance, ContractPartner
from app.database.session import create_session
from tests.test_register_gaps import _client, _seed


def _setup(monkeypatch):
    slug, ids = _seed()
    client = _client(monkeypatch, ids)
    from types import SimpleNamespace
    admin = SimpleNamespace(organization_id=ids["org"], account_id=ids["admin"], role="admin", is_developer=False, display_name="Admin")
    monkeypatch.setattr(catalog_routes, "current_actor", lambda request, organization_slug: admin)
    monkeypatch.setattr(catalog_routes, "current_scope_context", lambda: ScopeContext())
    client.app.include_router(catalog_routes.router)
    return slug, ids, client


def test_unlinked_suppliers_are_grouped_and_linked_on_request(monkeypatch):
    slug, ids, client = _setup(monkeypatch)
    query = {"organization_slug": slug}
    created = []
    for supplier in ("ABIOMED", "ABIOMED ", "GE Healthcare"):
        response = client.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung"}})
        contract_id = response.json()["contract_id"]
        session = create_session()
        try:
            session.get(Contract, UUID(contract_id)).supplier = supplier
            session.commit()
        finally:
            session.close()
        created.append(contract_id)
    partner = client.post("/api/catalogs/partners", params=query, json={"values": {"short_name": "Abiomed", "name1": "Abiomed Europe GmbH"}, "allow_similar": True}).json()

    listing = client.get("/api/catalogs/partners/unlinked", params=query).json()
    groups = {item["supplier"]: item for item in listing["items"]}
    assert groups["ABIOMED"]["contracts"] == 2 and groups["GE Healthcare"]["contracts"] == 1
    assert groups["ABIOMED"]["suggestions"][0]["id"] == partner["id"]
    # Nichts wurde automatisch verknüpft.
    session = create_session()
    try:
        assert all(session.get(Contract, UUID(cid)).partner_id is None for cid in created)
    finally:
        session.close()

    result = client.post("/api/catalogs/partners/link-supplier", params=query, json={"supplier": "ABIOMED", "partner_id": partner["id"]}).json()
    assert result["linked"] == 2
    session = create_session()
    try:
        linked = [session.get(Contract, UUID(cid)) for cid in created[:2]]
        assert all(contract.partner_id == UUID(partner["id"]) for contract in linked)
        assert session.get(Contract, UUID(created[2])).partner_id is None
        origins = {row.origin for row in session.scalars(select(ContractFieldProvenance).where(
            ContractFieldProvenance.contract_id.in_([contract.id for contract in linked]),
            ContractFieldProvenance.field_key == "partner_id",
        )).all()}
        assert origins == {"manual"}
        rows = session.scalars(select(ActivityLog).where(ActivityLog.object_id.in_([contract.id for contract in linked]))).all()
        partner_changes = [row for row in rows if "partner_id" in ((row.context_data or {}).get("fields") or {})]
        assert len(partner_changes) == 2
    finally:
        session.close()
    remaining = client.get("/api/catalogs/partners/unlinked", params=query).json()["items"]
    assert [item["supplier"] for item in remaining] == ["GE Healthcare"]


def test_history_uses_register_field_labels():
    from app.history.service import field_labels

    assert field_labels({"fields": {"partner_id": {"before": None, "after": "x"}, "unknown_key": {}}}) == {"partner_id": "Vertragspartner"}
    assert field_labels({"note": "x"}) == {}
