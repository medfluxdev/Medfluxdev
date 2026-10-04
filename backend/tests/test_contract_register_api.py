"""H1/H2/H6 contract register API on PostgreSQL (pytest-isolated schema)."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import catalogs as catalog_routes
from app.api.routes import contract_register
from app.core.scope_context import ScopeContext
from app.database.models import Account, AccountMembership, ActivityLog, Contract
from app.database.models.organization import Organization
from app.database.models.organization_structure import ContractDepartment, Department, Hospital
from app.database.models.register import NumberAllocation
from app.database.session import create_session
from app.models.contract import Contract as ExtractedContract
from app.register.service import allocate_contract_number, sync_from_extraction


def _seed():
    ids = {name: uuid4() for name in ("org", "hospital_a", "hospital_b", "radio", "it", "admin", "manager", "viewer", "radio_manager")}
    slug = f"register-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Register Test", slug=slug))
        session.add_all([
            Hospital(id=ids["hospital_a"], organization_id=ids["org"], name="Klinikum A", code="A"),
            Hospital(id=ids["hospital_b"], organization_id=ids["org"], name="Klinikum B", code="B"),
        ])
        session.flush()
        session.add_all([
            Department(id=ids["radio"], organization_id=ids["org"], hospital_id=ids["hospital_a"], name="Radiologie", code="RAD"),
            Department(id=ids["it"], organization_id=ids["org"], hospital_id=ids["hospital_a"], name="IT", code="IT"),
        ])
        for key in ("admin", "manager", "viewer", "radio_manager"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@example.invalid", display_name=key.title(), credential_digest="test-only"))
        session.flush()
        session.add_all([
            AccountMembership(organization_id=ids["org"], account_id=ids["admin"], role="admin"),
            AccountMembership(organization_id=ids["org"], account_id=ids["manager"], role="contract_manager"),
            AccountMembership(organization_id=ids["org"], account_id=ids["viewer"], role="viewer"),
            AccountMembership(
                organization_id=ids["org"], account_id=ids["radio_manager"], role="contract_manager",
                hospital_id=ids["hospital_a"], department_id=ids["radio"],
            ),
        ])
        session.commit()
    finally:
        session.close()
    return slug, ids


def _actor(ids, key, role):
    return SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())


def _client(monkeypatch, actor, scope: ScopeContext | None = None):
    """Patches the route modules; only the most recently created client is valid."""
    scope = scope or ScopeContext()
    for module in (contract_register, catalog_routes):
        monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
        monkeypatch.setattr(module, "current_scope_context", lambda: scope)
    app = FastAPI()
    app.include_router(contract_register.router)
    app.include_router(catalog_routes.router)
    return TestClient(app)


HYDMEDIA_EXAMPLE = {
    "short_description": "Med. Versorgungsvertrag § 116b",
    "term_model": "terminable",
    "term_start_date": "2027-04-01",
    "notice_period_value": 3,
    "notice_period_unit": "months",
    "notice_to": "quarter_end",
    "reminder_lead_months": 3,
}


def test_manual_create_edit_audit_and_terms(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, _actor(ids, "manager", "contract_manager"))

    first = client.post("/api/contracts", params=query, json={"values": HYDMEDIA_EXAMPLE})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["register_number"] == "000001"
    assert body["business_status"] == "in_arbeit"
    assert body["fields"]["short_description"]["origin"] == "manual"
    assert body["fields"]["short_description"]["updated_by_name"] == "Manager"
    terms = body["terms"]
    assert terms["status"] == "complete"
    assert terms["possible_end"] and terms["cancel_by"] and terms["reminder_date"]

    second = client.post("/api/contracts", params=query, json={"values": {"short_description": "Zweiter Vertrag"}})
    assert second.json()["register_number"] == "000002"

    contract_id = body["contract_id"]
    patched = client.patch(
        f"/api/contracts/{contract_id}/register", params=query,
        json={"changes": {"notice_period_value": 6, "internal_number": "INT-7"}},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["fields"]["notice_period_value"]["value"] == 6

    invalid = client.patch(
        f"/api/contracts/{contract_id}/register", params=query, json={"changes": {"notice_period_unit": None}}
    )
    assert invalid.status_code == 422

    unknown = client.patch(
        f"/api/contracts/{contract_id}/register", params=query, json={"changes": {"register_number": "999999"}}
    )
    assert unknown.status_code == 422

    session = create_session()
    try:
        events = session.scalars(
            select(ActivityLog).where(ActivityLog.object_id == UUID(contract_id)).order_by(ActivityLog.created_at)
        ).all()
        names = [event.event_name for event in events]
        assert "contract.created_manual" in names
        update = [event for event in events if event.event_name == "contract.register_updated"][-1]
        assert update.context_data["fields"]["notice_period_value"] == {"before": 3, "after": 6}
        assert update.role_snapshot == "contract_manager"
    finally:
        session.close()

    viewer = _client(monkeypatch, _actor(ids, "viewer", "viewer"))
    assert viewer.get(f"/api/contracts/{contract_id}/register", params=query).status_code == 200
    assert viewer.patch(
        f"/api/contracts/{contract_id}/register", params=query, json={"changes": {"internal_number": "x"}}
    ).status_code == 403
    assert viewer.post("/api/contracts", params=query, json={"values": {}}).status_code == 403


def test_status_workflow_and_remarks(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, _actor(ids, "manager", "contract_manager"))
    contract_id = client.post("/api/contracts", params=query, json={"values": {"short_description": "Lizenz"}}).json()["contract_id"]
    base = f"/api/contracts/{contract_id}"

    missing = client.post(f"{base}/status", params=query, json={"target": "gueltig"})
    assert missing.status_code == 422
    assert set(missing.json()["detail"]["missing"]) >= {"term_model", "term_start_date", "partner_id"}

    partner = client.post(
        "/api/catalogs/partners", params=query, json={"values": {"short_name": "LIZENZ AG", "name1": "Lizenz AG"}}
    )
    assert partner.status_code == 200, partner.text
    client.patch(
        f"{base}/register", params=query,
        json={"changes": {"term_model": "perpetual", "term_start_date": "2020-01-01", "partner_id": partner.json()["id"]}},
    )
    valid = client.post(f"{base}/status", params=query, json={"target": "gueltig"})
    assert valid.status_code == 200, valid.text
    assert valid.json()["business_status"] == "gueltig"
    assert [item["target"] for item in valid.json()["allowed_transitions"]] == ["gekuendigt", "beendet"]

    assert client.post(f"{base}/status", params=query, json={"target": "gekuendigt"}).status_code == 422
    terminated = client.post(
        f"{base}/status", params=query,
        json={"target": "gekuendigt", "terminated_on": "2026-09-01", "effective_date": "2026-12-31"},
    )
    assert terminated.status_code == 200
    assert terminated.json()["terms"]["actual_end"] == "2026-12-31"
    assert client.post(f"{base}/status", params=query, json={"target": "geloescht"}).status_code == 409

    reactivated = client.post(f"{base}/status", params=query, json={"target": "gueltig", "note": "Kündigung zurückgenommen"})
    assert reactivated.status_code == 200
    assert reactivated.json()["fields"]["terminated_effective"]["value"] is None

    assert client.post(f"{base}/remarks", params=query, json={"body": "   "}).status_code == 422
    client.post(f"{base}/remarks", params=query, json={"body": "Erste Bemerkung"})
    remarks = client.post(f"{base}/remarks", params=query, json={"body": "Zweite Bemerkung"}).json()["items"]
    assert [item["body"] for item in remarks] == ["Zweite Bemerkung", "Erste Bemerkung"]
    assert remarks[0]["author_name"] == "Manager"


def test_ai_values_never_overwrite_human_values(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, _actor(ids, "manager", "contract_manager"))
    contract_id = UUID(client.post("/api/contracts", params=query, json={"values": {}}).json()["contract_id"])

    def extraction(start: str, months: int) -> ExtractedContract:
        return ExtractedContract.model_validate({
            "identity": {"contract_title": "Wartung MRT"},
            "dates": {"start_date": {"date": start}},
            "termination": {"cancellation_period": {"value": months, "unit": "months"}, "cancellation_condition": "zum Quartalsende"},
        })

    session = create_session()
    try:
        contract = session.get(Contract, contract_id)
        actions = sync_from_extraction(session, contract=contract, extracted=extraction("2026-01-01", 3), extraction_id=None)
        session.commit()
        assert actions["term_start_date"] == "set"
    finally:
        session.close()

    register = client.get(f"/api/contracts/{contract_id}/register", params=query).json()
    assert register["fields"]["term_start_date"]["origin"] == "ai"
    assert register["fields"]["term_start_date"]["source_field"] == "dates.start_date"
    assert register["fields"]["term_model"]["value"] == "terminable"

    corrected = client.patch(
        f"/api/contracts/{contract_id}/register", params=query,
        json={"changes": {"term_start_date": "2026-02-01"}, "confirm": ["notice_to"]},
    ).json()
    assert corrected["fields"]["term_start_date"]["origin"] == "ai_corrected"
    assert corrected["fields"]["notice_to"]["origin"] == "ai_confirmed"
    assert corrected["fields"]["notice_to"]["confirmed_by_name"] == "Manager"

    session = create_session()
    try:
        contract = session.get(Contract, contract_id)
        actions = sync_from_extraction(session, contract=contract, extracted=extraction("2026-03-01", 6), extraction_id=None)
        session.commit()
        assert actions["term_start_date"] == "proposed"
        assert actions["notice_period_value"] == "set"
        assert contract.term_start_date.isoformat() == "2026-02-01"
    finally:
        session.close()

    register = client.get(f"/api/contracts/{contract_id}/register", params=query).json()
    assert register["fields"]["term_start_date"]["ai_proposed_value"]["value"] == "2026-03-01"
    accepted = client.post(
        f"/api/contracts/{contract_id}/register/proposals/term_start_date/accept", params=query
    ).json()
    assert accepted["fields"]["term_start_date"]["value"] == "2026-03-01"
    assert accepted["fields"]["term_start_date"]["origin"] == "ai_confirmed"
    assert accepted["fields"]["term_start_date"]["ai_proposed_value"] is None
    assert client.post(
        f"/api/contracts/{contract_id}/register/proposals/term_start_date/accept", params=query
    ).status_code == 404


def test_department_scope_and_multi_hospital_visibility(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    radio_scope = ScopeContext(organization_slug=slug, hospital_id=ids["hospital_a"], department_id=ids["radio"])
    radio = _client(monkeypatch, _actor(ids, "radio_manager", "contract_manager"), radio_scope)
    created = radio.post("/api/contracts", params=query, json={"values": {"short_description": "Radiologie-Wartung"}})
    assert created.status_code == 200, created.text
    contract_id = created.json()["contract_id"]
    assert radio.get(f"/api/contracts/{contract_id}/register", params=query).status_code == 200

    session = create_session()
    try:
        link = session.scalars(select(ContractDepartment).where(ContractDepartment.contract_id == UUID(contract_id))).one()
        assert link.department_id == ids["radio"] and link.relation_role == "responsible"
    finally:
        session.close()

    it_scope = ScopeContext(organization_slug=slug, hospital_id=ids["hospital_a"], department_id=ids["it"])
    it_client = _client(monkeypatch, _actor(ids, "manager", "contract_manager"), it_scope)
    assert it_client.get(f"/api/contracts/{contract_id}/register", params=query).status_code == 404

    radio = _client(monkeypatch, _actor(ids, "radio_manager", "contract_manager"), radio_scope)
    assert radio.put(
        f"/api/contracts/{contract_id}/hospitals", params=query,
        json={"hospital_ids": [str(ids["hospital_a"]), str(ids["hospital_b"])]},
    ).status_code == 403

    admin = _client(monkeypatch, _actor(ids, "admin", "admin"))
    shared = admin.put(
        f"/api/contracts/{contract_id}/hospitals", params=query,
        json={"hospital_ids": [str(ids["hospital_a"]), str(ids["hospital_b"])], "primary_hospital_id": str(ids["hospital_a"])},
    )
    assert shared.status_code == 200, shared.text
    assert [item["is_primary"] for item in shared.json()["items"]] == [True, False]
    switch = admin.put(
        f"/api/contracts/{contract_id}/hospitals", params=query,
        json={"hospital_ids": [str(ids["hospital_b"])], "primary_hospital_id": str(ids["hospital_b"])},
    )
    assert switch.status_code == 409

    hospital_b = _client(
        monkeypatch, _actor(ids, "manager", "contract_manager"),
        ScopeContext(organization_slug=slug, hospital_id=ids["hospital_b"]),
    )
    assert hospital_b.get(f"/api/contracts/{contract_id}/register", params=query).status_code == 200


def test_catalogs_partners_types_lookups_and_number_range(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _client(monkeypatch, _actor(ids, "admin", "admin"))

    catalog = admin.get("/api/catalogs/contract-types", params=query).json()
    assert len(catalog["contract_types"]) >= 20
    software = next(item for item in catalog["contract_categories"] if item["code"] == "software")
    licence = next(item for item in catalog["contract_types"] if item["code"] == "lizenz")
    assert licence["id"] in software["contract_type_ids"]
    again = admin.post("/api/catalogs/defaults", params=query).json()["created"]
    assert again == {"contract_types": 0, "contract_categories": 0, "type_category_links": 0, "lookups": 0}

    duplicate_type = admin.post("/api/catalogs/contract-types", params=query, json={"values": {"label": "Wartungsvertrag"}})
    assert duplicate_type.status_code == 409
    new_type = admin.post("/api/catalogs/contract-types", params=query, json={"values": {"label": "Pachtvertrag"}})
    assert new_type.status_code == 200 and new_type.json()["code"] == "pachtvertrag"

    lookups = admin.get("/api/catalogs/lookups", params={**query, "field_key": "storage_location"}).json()
    assert any(item["code"] == "archiv_original" for item in lookups["items"])
    assert admin.post(
        "/api/catalogs/lookups", params=query, json={"values": {"field_key": "storage_location", "label": "Archiv (Original)"}}
    ).status_code == 409
    assert admin.post(
        "/api/catalogs/lookups", params=query, json={"values": {"field_key": "unknown", "label": "x"}}
    ).status_code == 422

    manager = _client(monkeypatch, _actor(ids, "manager", "contract_manager"))
    created = manager.post(
        "/api/catalogs/partners", params=query,
        json={"values": {"short_name": "SIEMENS HC", "name1": "Siemens Healthcare GmbH", "city": "Erlangen"}},
    )
    assert created.status_code == 200
    similar = manager.post(
        "/api/catalogs/partners", params=query, json={"values": {"short_name": "SIEMENS2", "name1": "SIEMENS HEALTHCARE"}}
    )
    assert similar.status_code == 409
    assert similar.json()["detail"]["similar"][0]["short_name"] == "SIEMENS HC"
    forced = manager.post(
        "/api/catalogs/partners", params=query,
        json={"values": {"short_name": "SIEMENS2", "name1": "SIEMENS HEALTHCARE"}, "allow_similar": True},
    )
    assert forced.status_code == 200
    assert manager.post(
        "/api/catalogs/partners", params=query, json={"values": {"short_name": "siemens hc", "name1": "Andere"}}
    ).status_code == 409
    groups = manager.get("/api/catalogs/partners/duplicates", params=query).json()["groups"]
    assert len(groups) == 1 and len(groups[0]) == 2
    assert manager.post("/api/catalogs/contract-types", params=query, json={"values": {"label": "X"}}).status_code == 403

    admin = _client(monkeypatch, _actor(ids, "admin", "admin"))
    reserved = admin.post("/api/catalogs/number-range/reserve", params=query, json={"values": [1, 2], "note": "Altsystem"})
    assert reserved.status_code == 200, reserved.text
    first = admin.post("/api/contracts", params=query, json={"values": {}}).json()
    assert first["register_number"] == "000003"
    assert admin.patch("/api/catalogs/number-range", params=query, json={"next_value": 2}).status_code == 422
    assert admin.patch("/api/catalogs/number-range", params=query, json={"next_value": 100, "prefix": "V-"}).status_code == 200
    assert admin.post("/api/contracts", params=query, json={"values": {}}).json()["register_number"] == "V-000100"


def test_concurrent_number_allocation_is_unique():
    _slug, ids = _seed()
    results: list[str] = []
    errors: list[BaseException] = []
    contract_ids = []
    session = create_session()
    try:
        for _ in range(6):
            contract = Contract(organization_id=ids["org"])
            session.add(contract)
            session.flush()
            contract_ids.append(contract.id)
        session.commit()
    finally:
        session.close()

    barrier = threading.Barrier(len(contract_ids))

    def worker(contract_id):
        session = create_session()
        try:
            barrier.wait(timeout=30)
            results.append(allocate_contract_number(session, organization_id=ids["org"], contract_id=contract_id, account_id=None))
            session.commit()
        except BaseException as exc:  # noqa: BLE001 - collected for the assertion below
            errors.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(contract_id,)) for contract_id in contract_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    assert sorted(results) == [f"{value:06d}" for value in range(1, 7)]
    session = create_session()
    try:
        assert session.scalar(
            select(NumberAllocation.value).where(NumberAllocation.organization_id == ids["org"]).order_by(NumberAllocation.value.desc())
        ) == 6
    finally:
        session.close()


def test_contract_list_shows_register_fields_and_filters_business_status(monkeypatch):
    from app.api.routes import contracts as contract_routes

    slug, ids = _seed()
    query = {"organization_slug": slug}
    client = _client(monkeypatch, _actor(ids, "admin", "admin"))
    partner = client.post(
        "/api/catalogs/partners", params=query, json={"values": {"short_name": "MEDTEC", "name1": "Medtec GmbH"}}
    ).json()
    created = client.post(
        "/api/contracts", params=query,
        json={"values": {"short_description": "Wartung Röntgen", "partner_id": partner["id"], **{
            key: value for key, value in HYDMEDIA_EXAMPLE.items() if key != "short_description"
        }}},
    ).json()

    app = FastAPI()
    app.include_router(contract_routes.router)
    listing = TestClient(app)
    items = listing.get("/api/contracts", params=query).json()["items"]
    row = next(item for item in items if item["contract_id"] == created["contract_id"])
    assert row["register_number"] == "000001"
    assert row["business_status"] == "in_arbeit"
    assert row["contract_title"] == "Wartung Röntgen"
    assert row["supplier"] == "MEDTEC"
    assert row["latest_cancellation_date"] == created["terms"]["cancel_by"]
    assert row["contract_end_date"] == created["terms"]["possible_end"]

    found = listing.get("/api/contracts", params={**query, "q": "Röntgen"}).json()["items"]
    assert [item["contract_id"] for item in found] == [created["contract_id"]]
    assert listing.get("/api/contracts", params={**query, "business_status": "gueltig"}).json()["items"] == []
    assert listing.get("/api/contracts", params={**query, "business_status": "bogus"}).status_code == 422
