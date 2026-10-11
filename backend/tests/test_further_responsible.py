"""Weitere verantwortliche Personen je Vertrag und die Kostenstelle ohne Aufteilung.

Weitere Verantwortliche bekommen dasselbe wie die Hauptverantwortliche: Erinnerungen,
„Ich verantwortlich“ in der Vertragsliste und Zugriff auf vertrauliche Vertraege.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import contract_finance, contract_register, ownership, register_grid
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import Account, AccountMembership, Contract
from app.database.models.deadlines import ContractDeadline, Notification
from app.database.models.organization import Organization
from app.database.models.organization_structure import CostCenter, Hospital
from app.database.session import create_session
from app.deadlines.notify import process_deadlines


def _seed():
    ids = {key: uuid4() for key in ("org", "admin", "main", "second", "third", "outsider", "hospital", "center")}
    slug = f"resp-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Verantwortung Test", slug=slug))
        session.add(Hospital(id=ids["hospital"], organization_id=ids["org"], name="Klinikum", code="K"))
        for key in ("admin", "main", "second", "third", "outsider"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@x.invalid", display_name=key.title(), credential_digest="t"))
        session.flush()
        session.add(CostCenter(id=ids["center"], organization_id=ids["org"], hospital_id=ids["hospital"], code="950000", name="Radiologie"))
        for key, role in (("admin", "admin"), ("main", "contract_manager"), ("second", "viewer"), ("third", "viewer")):
            session.add(AccountMembership(organization_id=ids["org"], account_id=ids[key], role=role))
        session.commit()
    finally:
        session.close()
    return slug, ids


def _client(monkeypatch, ids, key, role):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())
    for module in (contract_register, register_grid, ownership, contract_finance):
        if hasattr(module, "current_actor"):
            monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
        if hasattr(module, "current_scope_context"):
            monkeypatch.setattr(module, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    for module in (contract_register, register_grid, ownership, contract_finance):
        app.include_router(module.router)
    return TestClient(app)


def _contract(client, slug, **values):
    response = client.post("/api/contracts", params={"organization_slug": slug}, json={"values": {"short_description": "Wartung CT", **values}})
    assert response.status_code == 200, response.text
    return response.json()["contract_id"]


def _patch(client, slug, contract_id, **payload):
    body = {"hospital_id": None, "department_ids": [], "cost_center_id": None, **payload}
    return client.patch(f"/api/ownership/contracts/{contract_id}", params={"organization_slug": slug}, json=body)


def test_set_further_persons_validation_and_main_never_twice(monkeypatch):
    slug, ids = _seed()
    admin = _client(monkeypatch, ids, "admin", "admin")
    cid = _contract(admin, slug)
    # Nur Benutzer der Organisation.
    assert _patch(admin, slug, cid, responsible_account_id=str(ids["main"]), further_responsible_account_ids=[str(ids["outsider"])]).status_code == 422
    saved = _patch(admin, slug, cid, responsible_account_id=str(ids["main"]),
                   further_responsible_account_ids=[str(ids["second"]), str(ids["main"]), str(ids["second"]), str(ids["third"])])
    assert saved.status_code == 200, saved.text
    assert saved.json()["further_responsible_account_ids"] == [str(ids["second"]), str(ids["third"])]
    # Wird eine weitere Person Hauptverantwortliche, steht sie nicht mehr doppelt da.
    moved = _patch(admin, slug, cid, responsible_account_id=str(ids["second"]))
    assert moved.json()["further_responsible_account_ids"] == [str(ids["third"])]
    got = admin.get(f"/api/ownership/contracts/{cid}", params={"organization_slug": slug}).json()
    assert got["responsible_account_id"] == str(ids["second"]) and got["further_responsible_account_ids"] == [str(ids["third"])]
    # Leere Liste entfernt alle weiteren.
    assert _patch(admin, slug, cid, responsible_account_id=str(ids["second"]), further_responsible_account_ids=[]).json()["further_responsible_account_ids"] == []


def test_further_person_gets_me_filter_confidential_access_and_reminders(monkeypatch):
    slug, ids = _seed()
    admin = _client(monkeypatch, ids, "admin", "admin")
    cid = _contract(admin, slug)
    _patch(admin, slug, cid, responsible_account_id=str(ids["main"]), further_responsible_account_ids=[str(ids["second"])])
    session = create_session()
    try:
        contract = session.get(Contract, UUID(cid))
        contract.is_confidential = True
        session.add(ContractDeadline(
            organization_id=ids["org"], contract_id=contract.id, title="Kündigung prüfen", kind="custom",
            due_date=date.today() + timedelta(days=10), remind_on=date.today() - timedelta(days=1), status="open",
        ))
        session.commit()
    finally:
        session.close()

    # „Ich verantwortlich“ und vertraulicher Zugriff fuer die weitere Person, nicht fuer andere.
    for key, visible in (("second", True), ("third", False)):
        client = _client(monkeypatch, ids, key, "viewer")
        spec = '{"filters":[{"column":"responsible","op":"me"}]}'
        grid = client.get("/api/register/grid", params={"organization_slug": slug, "spec": spec})
        assert grid.status_code == 200, grid.text
        assert (cid in {row["contract_id"] for row in grid.json()["items"]}) is visible
        detail = client.get(f"/api/contracts/{cid}/register", params={"organization_slug": slug})
        assert (detail.status_code == 200) is visible

    # Die Spalte nennt die weiteren Verantwortlichen.
    rows = _client(monkeypatch, ids, "admin", "admin").get("/api/register/grid", params={"organization_slug": slug, "spec": '{"columns":["further_responsible"]}'}).json()["items"]
    assert next(row for row in rows if row["contract_id"] == cid)["values"]["further_responsible"] == "Second"

    # Erinnerung an Haupt- und weitere Verantwortliche.
    session = create_session()
    try:
        process_deadlines(session, date.today(), {}, organization_id=ids["org"])
        session.commit()
        recipients = set(session.scalars(select(Notification.account_id).where(Notification.contract_id == UUID(cid))).all())
        assert recipients == {ids["main"], ids["second"]}
    finally:
        session.close()


def test_finance_shows_cost_center_from_assignment_without_split(monkeypatch):
    slug, ids = _seed()
    admin = _client(monkeypatch, ids, "admin", "admin")
    cid = _contract(admin, slug)
    finance = admin.get(f"/api/contracts/{cid}/finance", params={"organization_slug": slug}).json()
    assert finance["allocations"] == [] and finance["primary_cost_center"] is None
    assert _patch(admin, slug, cid, hospital_id=str(ids["hospital"]), cost_center_id=str(ids["center"])).status_code == 200
    finance = admin.get(f"/api/contracts/{cid}/finance", params={"organization_slug": slug}).json()
    assert finance["primary_cost_center"]["code"] == "950000" and finance["primary_cost_center"]["name"] == "Radiologie"


def test_contract_detail_shows_assignment_names_for_every_role(monkeypatch):
    from app.api.routes.contracts import _build_augmented_detail

    slug, ids = _seed()
    admin = _client(monkeypatch, ids, "admin", "admin")
    cid = _contract(admin, slug)
    session = create_session()
    try:
        empty = _build_augmented_detail(session, organization_id=ids["org"], contract_id=UUID(cid))["assignment"]
    finally:
        session.close()
    assert empty == {"hospital": None, "responsible_department": None, "beneficiary_departments": [], "other_departments": [],
                     "cost_center": None, "responsible": "Admin", "further_responsible": []}  # Anleger ist verantwortlich
    _patch(admin, slug, cid, hospital_id=str(ids["hospital"]), cost_center_id=str(ids["center"]),
           responsible_account_id=str(ids["main"]), further_responsible_account_ids=[str(ids["second"])])
    session = create_session()
    try:
        assignment = _build_augmented_detail(session, organization_id=ids["org"], contract_id=UUID(cid))["assignment"]
    finally:
        session.close()
    assert assignment["hospital"] == "Klinikum"
    assert assignment["cost_center"] == {"code": "950000", "name": "Radiologie"}
    assert assignment["responsible"] == "Main" and assignment["further_responsible"] == ["Second"]


def test_contract_detail_carries_start_date_and_linked_partner(monkeypatch):
    from app.api.routes.contracts import _build_augmented_detail
    from app.database.models.register import ContractPartner

    slug, ids = _seed()
    admin = _client(monkeypatch, ids, "admin", "admin")
    cid = _contract(admin, slug, term_start_date="2025-04-01")
    session = create_session()
    try:
        detail = _build_augmented_detail(session, organization_id=ids["org"], contract_id=UUID(cid))
        assert detail["register_facts"]["contract_start"] == "2025-04-01"
        assert detail["partner"] is None  # noch nicht zugeordnet
        partner = ContractPartner(organization_id=ids["org"], short_name="ABIOMED", name1="ABIOMED Europe GmbH")
        session.add(partner)
        session.flush()
        session.get(Contract, UUID(cid)).partner_id = partner.id
        session.commit()
        detail = _build_augmented_detail(session, organization_id=ids["org"], contract_id=UUID(cid))
        assert detail["partner"] == {"id": str(partner.id), "name": "ABIOMED Europe GmbH", "short_name": "ABIOMED"}
    finally:
        session.close()


def test_risk_confirm_override_reset(monkeypatch):
    from app.api.routes.contracts import _build_augmented_detail

    slug, ids = _seed()
    admin = _client(monkeypatch, ids, "admin", "admin")
    cid = _contract(admin, slug)
    session = create_session()
    try:
        contract = session.get(Contract, UUID(cid))
        contract.risk_computed = contract.risk_level = "high"
        session.commit()
    finally:
        session.close()
    url, query = f"/api/contracts/{cid}/risk", {"organization_slug": slug}

    confirmed = admin.post(url, params=query, json={"action": "confirm"}).json()
    assert confirmed["effective"] == "high" and confirmed["confirmed"]["by"] == "Admin"
    assert admin.post(url, params=query, json={"action": "override", "level": "low"}).status_code == 422  # Begruendung fehlt
    assert admin.post(url, params=query, json={"action": "override", "level": "extrem", "reason": "x" * 5}).status_code == 422
    overridden = admin.post(url, params=query, json={"action": "override", "level": "low", "reason": "Gerät wird 2026 ersetzt"}).json()
    assert overridden["effective"] == "low" and overridden["computed"] == "high"
    assert overridden["override"]["reason"] == "Gerät wird 2026 ersetzt" and overridden["confirmed"] is None
    assert admin.post(url, params=query, json={"action": "confirm"}).status_code == 422  # erst zuruecksetzen

    session = create_session()
    try:
        # Neue Berechnung aendert das festgelegte Risiko nicht.
        contract = session.get(Contract, UUID(cid))
        contract.risk_computed = "medium"
        contract.risk_level = contract.risk_override or contract.risk_computed
        session.commit()
        detail = _build_augmented_detail(session, organization_id=ids["org"], contract_id=UUID(cid))
        assert detail["risk_level"] == "low" and detail["risk"]["computed"] == "medium"
    finally:
        session.close()

    reset = admin.post(url, params=query, json={"action": "reset"}).json()
    assert reset["effective"] == "medium" and reset["override"] is None
    assert reset["confirmed"] is None  # bestaetigt war „hoch“, berechnet ist jetzt „mittel“

    viewer = _client(monkeypatch, ids, "second", "viewer")
    assert viewer.post(url, params=query, json={"action": "confirm"}).status_code == 403
