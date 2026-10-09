"""Stammdaten: Uebersicht, Verwendung, Zusammenfuehren, CSV-Import, Einzelhistorie (PostgreSQL)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import catalogs as catalog_routes
from app.api.routes import contract_register, cost_center_routes, master_data, organization_structure
from app.api.routes import history as history_routes
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import Account, AccountMembership, ActivityLog, Contract
from app.database.models.organization import Organization
from app.database.models.organization_structure import ContractDepartment, CostCenter, Department, Hospital
from app.database.models.register import ContractPartner, LookupValue
from app.database.session import create_session

ROUTES = (contract_register, catalog_routes, master_data, history_routes, organization_structure, cost_center_routes)


def _seed():
    ids = {name: uuid4() for name in ("org", "other_org", "hospital_a", "hospital_b", "radio", "it", "center", "admin", "manager", "viewer")}
    slug = f"stammdaten-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add_all([
            Organization(id=ids["org"], name="Stammdaten Test", slug=slug),
            Organization(id=ids["other_org"], name="Fremd", slug=f"fremd-{uuid4().hex[:12]}"),
        ])
        session.flush()
        session.add_all([
            Hospital(id=ids["hospital_a"], organization_id=ids["org"], name="Klinikum A", code="A"),
            Hospital(id=ids["hospital_b"], organization_id=ids["org"], name="Klinikum B", code="B"),
        ])
        session.flush()
        session.add_all([
            Department(id=ids["radio"], organization_id=ids["org"], hospital_id=ids["hospital_a"], name="Radiologie", code="RAD"),
            Department(id=ids["it"], organization_id=ids["org"], hospital_id=ids["hospital_a"], name="IT", code="IT"),
        ])
        session.flush()
        session.add(CostCenter(id=ids["center"], organization_id=ids["org"], hospital_id=ids["hospital_a"], department_id=ids["radio"], code="471100", name="Radiologie"))
        for key in ("admin", "manager", "viewer"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@example.invalid", display_name=key.title(), credential_digest="test-only"))
        session.flush()
        session.add_all([
            AccountMembership(organization_id=ids["org"], account_id=ids["admin"], role="admin"),
            AccountMembership(organization_id=ids["org"], account_id=ids["manager"], role="contract_manager"),
            AccountMembership(organization_id=ids["org"], account_id=ids["viewer"], role="viewer", hospital_id=ids["hospital_b"]),
        ])
        session.commit()
    finally:
        session.close()
    return slug, ids


def _as(monkeypatch, ids, key, role, scope: ScopeContext | None = None):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())
    scope = scope or ScopeContext()
    for module in ROUTES:
        monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
        if hasattr(module, "current_scope_context"):
            monkeypatch.setattr(module, "current_scope_context", lambda: scope)
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    for module in ROUTES:
        app.include_router(module.router)
    return TestClient(app)


def _partner(client, slug, short_name, name1=None, allow_similar=True):
    response = client.post(
        "/api/catalogs/partners", params={"organization_slug": slug},
        json={"values": {"short_name": short_name, "name1": name1 or short_name}, "allow_similar": allow_similar},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _contract(client, slug, **values):
    response = client.post("/api/contracts", params={"organization_slug": slug}, json={"values": {"short_description": "Wartung", **values}})
    assert response.status_code == 200, response.text
    return response.json()["contract_id"]


def test_summary_and_usage_count_only_live_visible_contracts(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    manager = _as(monkeypatch, ids, "manager", "contract_manager")
    siemens = _partner(manager, slug, "Siemens", "Siemens Healthineers GmbH")
    _partner(manager, slug, "Siemens HC", "Siemens Healthineers AG")
    unused = _partner(manager, slug, "Dräger", "Drägerwerk AG")
    storage = manager.get("/api/catalogs/lookups", params={**query, "field_key": "storage_location"}).json()["items"][0]
    contract_type = manager.get("/api/catalogs/contract-types", params=query).json()["contract_types"][0]

    first = _contract(manager, slug, partner_id=siemens, storage_location_code=storage["code"], contract_type_id=contract_type["id"])
    deleted = _contract(manager, slug, partner_id=siemens)
    session = create_session()
    try:
        session.add(ContractDepartment(organization_id=ids["org"], contract_id=first, department_id=ids["radio"], relation_role="responsible"))
        row = session.get(Contract, first)
        row.cost_center_id = ids["center"]
        session.get(Contract, deleted).deleted_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()

    admin = _as(monkeypatch, ids, "admin", "admin")
    summary = admin.get("/api/master-data/summary", params=query)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["kinds"]["partner"] == {**body["kinds"]["partner"], "total": 3, "active": 3, "inactive": 0}
    assert body["kinds"]["partner"]["last_change"]
    assert body["kinds"]["hospital"]["total"] == 2
    assert body["kinds"]["department"]["total"] == 2
    assert body["kinds"]["cost_center"]["total"] == 1
    assert body["hints"]["partner_duplicate_groups"] == 1
    assert body["hints"]["partners_without_contracts"] == 2
    storage_list = next(item for item in body["lookup_lists"] if item["field_key"] == "storage_location")
    assert storage_list["active"] >= 1

    def counts(kind):
        response = admin.get("/api/master-data/usage", params={**query, "kind": kind})
        assert response.status_code == 200, response.text
        return response.json()["counts"]

    assert counts("partner") == {siemens: 1}  # der geloeschte Vertrag zaehlt nicht
    assert unused not in counts("partner")
    assert counts("department") == {str(ids["radio"]): 1}
    assert counts("cost_center") == {str(ids["center"]): 1}
    assert counts("contract_type") == {contract_type["id"]: 1}
    assert counts("lookup") == {storage["id"]: 1}
    assert admin.get("/api/master-data/usage", params={**query, "kind": "unbekannt"}).status_code == 422

    viewer = _as(monkeypatch, ids, "viewer", "viewer", ScopeContext(hospital_id=ids["hospital_b"]))
    scoped = viewer.get("/api/master-data/summary", params=query).json()
    assert scoped["kinds"]["hospital"]["total"] == 1
    assert scoped["kinds"]["department"]["total"] == 0
    assert scoped["kinds"]["cost_center"]["total"] == 0
    assert scoped["hints"]["partners_without_contracts"] is None
    assert viewer.get("/api/master-data/usage", params={**query, "kind": "partner"}).json()["counts"] == {}


def test_merge_partners_moves_contracts_deactivates_sources_and_logs(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    manager = _as(monkeypatch, ids, "manager", "contract_manager")
    target = _partner(manager, slug, "Siemens")
    duplicate = _partner(manager, slug, "Siemens AG")
    contract_id = _contract(manager, slug, partner_id=duplicate)

    assert manager.post(f"/api/catalogs/partners/{target}/merge", params=query, json={"source_ids": [target]}).status_code == 422
    assert manager.post(f"/api/catalogs/partners/{target}/merge", params=query, json={"source_ids": [str(uuid4())]}).status_code == 404

    merged = manager.post(f"/api/catalogs/partners/{target}/merge", params=query, json={"source_ids": [duplicate]})
    assert merged.status_code == 200, merged.text
    assert merged.json()["merged"] == [{"id": duplicate, "short_name": "Siemens AG", "contracts": 1}]

    session = create_session()
    try:
        assert str(session.get(Contract, contract_id).partner_id) == target
        assert session.get(ContractPartner, duplicate).is_active is False
        events = set(session.scalars(select(ActivityLog.event_name).where(ActivityLog.organization_id == ids["org"])).all())
        assert {"partner.merged", "partner.merged_into", "contract.partner_merged"} <= events
    finally:
        session.close()

    # Deaktivierter Ziel-Partner und fremde Organisation werden abgewiesen.
    other = _partner(manager, slug, "Philips")
    manager.patch(f"/api/catalogs/partners/{other}", params=query, json={"values": {"is_active": False}})
    third = _partner(manager, slug, "GE")
    assert manager.post(f"/api/catalogs/partners/{other}/merge", params=query, json={"source_ids": [third]}).status_code == 422

    viewer = _as(monkeypatch, ids, "viewer", "viewer")
    assert viewer.post(f"/api/catalogs/partners/{target}/merge", params=query, json={"source_ids": [third]}).status_code == 403


def test_partner_import_checks_first_then_all_or_nothing(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    manager = _as(monkeypatch, ids, "manager", "contract_manager")
    _partner(manager, slug, "Siemens", "Siemens Healthineers GmbH")

    rows = [
        {"short_name": "Siemens", "name1": "Doppelt"},
        {"short_name": "Philips", "name1": "Philips GmbH", "city": "Hamburg"},
        {"short_name": "philips", "name1": "Philips Medizin"},
        {"short_name": "", "name1": "Ohne Kurzname"},
    ]
    checked = manager.post("/api/master-data/import/partner", params=query, json={"rows": rows, "dry_run": False})
    assert checked.status_code == 200, checked.text
    result = checked.json()
    assert result["valid"] is False and result["created"] == 0
    errors = {item["line"]: item["errors"] for item in result["rows"]}
    assert errors[1] == ["Diesen Kurznamen gibt es bereits."]
    assert errors[2] == []
    assert errors[3][0].startswith("Doppelt in der Liste")
    assert errors[4] == ["Kurzname fehlt."]

    good = [
        {"short_name": "Philips", "name1": "Philips GmbH", "city": "Hamburg"},
        {"short_name": "Siemens Healthineers", "name1": "Siemens Healthineers AG"},
    ]
    dry = manager.post("/api/master-data/import/partner", params=query, json={"rows": good, "dry_run": True}).json()
    assert dry["valid"] is True and dry["created"] == 0
    assert any(warning.startswith("Ähnlich zu: Siemens") for warning in dry["rows"][1]["warnings"])

    done = manager.post("/api/master-data/import/partner", params=query, json={"rows": good, "dry_run": False}).json()
    assert done["created"] == 2
    session = create_session()
    try:
        names = set(session.scalars(select(ContractPartner.short_name).where(ContractPartner.organization_id == ids["org"])).all())
        assert names == {"Siemens", "Philips", "Siemens Healthineers"}
        events = list(session.scalars(select(ActivityLog.event_name).where(ActivityLog.organization_id == ids["org"])).all())
        assert events.count("partner.created") == 3 and "partner.bulk_imported" in events
    finally:
        session.close()

    viewer = _as(monkeypatch, ids, "viewer", "viewer")
    assert viewer.post("/api/master-data/import/partner", params=query, json={"rows": good}).status_code == 403
    assert manager.post("/api/master-data/import/hospital", params=query, json={"rows": good}).status_code == 404


def test_structure_import_resolves_parents_in_file_and_requires_admin(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    manager = _as(monkeypatch, ids, "manager", "contract_manager")
    departments = [{"hospital": "A", "name": "Kardiologie", "code": "KAR", "unit_type": "Klinik"}]
    assert manager.post("/api/master-data/import/department", params=query, json={"rows": departments}).status_code == 403

    admin = _as(monkeypatch, ids, "admin", "admin")
    departments = [
        {"hospital": "Klinikum A", "name": "Kardiologie", "code": "kar", "unit_type": "Klinik"},
        {"hospital": "A", "name": "Herzkatheterlabor", "code": "HKL", "parent": "KAR", "unit_type": "funktionsbereich"},
        {"hospital": "A", "name": "Röntgen", "code": "RNT", "parent": "Radiologie"},
        {"hospital": "A", "name": "Doppelt", "code": "RAD"},
        {"hospital": "Z", "name": "Fremd", "code": "Z1"},
        {"hospital": "A", "name": "Typ", "code": "TYP", "unit_type": "Labor"},
    ]
    result = admin.post("/api/master-data/import/department", params=query, json={"rows": departments, "dry_run": True}).json()
    errors = {item["line"]: item["errors"] for item in result["rows"]}
    assert errors[1] == [] and errors[2] == [] and errors[3] == []
    assert errors[4] == ["Dieses Kürzel gibt es in diesem Krankenhaus bereits."]
    assert errors[5] == ["Krankenhaus „Z“ gibt es nicht."]
    assert errors[6] == ["Unbekannter Einheitentyp „Labor“."]

    done = admin.post("/api/master-data/import/department", params=query, json={"rows": departments[:3], "dry_run": False}).json()
    assert done["created"] == 3, done
    session = create_session()
    try:
        by_code = {row.code: row for row in session.scalars(select(Department).where(Department.organization_id == ids["org"])).all()}
        assert by_code["HKL"].parent_id == by_code["KAR"].id
        assert by_code["RNT"].parent_id == ids["radio"]
        assert by_code["KAR"].unit_type == "klinik"
    finally:
        session.close()

    centers = [
        {"hospital": "A", "department": "KAR", "code": "471200", "name": "Kardiologie"},
        {"hospital": "A", "code": "471100", "name": "Schon da"},
        {"hospital": "B", "department": "RAD", "code": "471300", "name": "Falsches Haus"},
    ]
    result = admin.post("/api/master-data/import/cost_center", params=query, json={"rows": centers, "dry_run": False}).json()
    errors = {item["line"]: item["errors"] for item in result["rows"]}
    assert result["created"] == 0
    assert errors[1] == []
    assert errors[2] == ["Diese Kostenstelle gibt es bereits."]
    assert errors[3] == ["Abteilung „RAD“ gibt es nicht. (im gewählten Krankenhaus)"]
    assert admin.post("/api/master-data/import/cost_center", params=query, json={"rows": centers[:1], "dry_run": False}).json()["created"] == 1


def test_lookup_import_needs_known_list_and_rejects_duplicates(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _as(monkeypatch, ids, "admin", "admin")
    existing = admin.get("/api/catalogs/lookups", params={**query, "field_key": "storage_location"}).json()["items"][0]

    unknown = admin.post("/api/master-data/import/lookup", params=query, json={"rows": [{"label": "X"}], "field_key": "nope"}).json()
    assert unknown["valid"] is False and unknown["errors"] == ["Unbekannte Auswahlliste."]

    rows = [{"label": "Keller Haus B"}, {"label": existing["label"]}, {"label": "keller haus b"}]
    result = admin.post("/api/master-data/import/lookup", params=query, json={"rows": rows, "field_key": "storage_location", "dry_run": False}).json()
    errors = {item["line"]: item["errors"] for item in result["rows"]}
    assert result["created"] == 0 and errors[1] == []
    assert errors[2] == ["Diesen Eintrag gibt es bereits."]
    assert errors[3][0].startswith("Doppelt in der Liste")

    done = admin.post("/api/master-data/import/lookup", params=query, json={"rows": rows[:1], "field_key": "storage_location", "dry_run": False}).json()
    assert done["created"] == 1
    session = create_session()
    try:
        row = session.scalar(select(LookupValue).where(LookupValue.organization_id == ids["org"], LookupValue.label == "Keller Haus B"))
        assert row is not None and row.code == "keller_haus_b"
    finally:
        session.close()


def test_history_can_be_filtered_to_one_master_data_entry(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    manager = _as(monkeypatch, ids, "manager", "contract_manager")
    first = _partner(manager, slug, "Siemens")
    _partner(manager, slug, "Philips")
    manager.patch(f"/api/catalogs/partners/{first}", params=query, json={"values": {"city": "Erlangen"}})

    history = manager.get("/api/history", params={**query, "object_type": "contract_partner", "object_id": first})
    assert history.status_code == 200, history.text
    assert [item["event"] for item in history.json()["items"]] == ["partner.updated", "partner.created"]
    assert manager.get("/api/history", params={**query, "object_type": "contract_partner"}).status_code == 422
    assert manager.get("/api/history", params={**query, "object_type": "account", "object_id": first}).status_code == 422


def test_duplicate_structure_codes_return_conflict_instead_of_server_error(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _as(monkeypatch, ids, "admin", "admin")
    assert admin.post("/api/organization-structure/hospitals", params=query, json={"name": "Neu", "code": "a"}).status_code == 409
    assert admin.post("/api/organization-structure/hospitals", params=query, json={"name": " ", "code": "N"}).status_code == 422
    assert admin.post("/api/organization-structure/departments", params=query, json={"hospital_id": str(ids["hospital_a"]), "name": "X", "code": "rad"}).status_code == 409
    assert admin.patch(f"/api/organization-structure/departments/{ids['it']}", params=query, json={"code": "RAD"}).status_code == 409
    assert admin.post("/api/cost-centers", params=query, json={"hospital_id": str(ids["hospital_a"]), "code": "471100", "name": "X"}).status_code == 409
    second = admin.post("/api/cost-centers", params=query, json={"hospital_id": str(ids["hospital_a"]), "code": "471101", "name": "Y"})
    assert second.status_code == 200
    assert admin.patch(f"/api/cost-centers/{second.json()['id']}", params=query, json={"code": "471100"}).status_code == 409
