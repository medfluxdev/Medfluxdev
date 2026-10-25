"""Stammdaten-Vorschlaege fuer Vertragspartner: belegte Partner-Angaben aus der Analyse, nie automatisch geschrieben."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import catalogs as catalog_routes
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import ActivityLog, Contract
from app.database.models.register import ContractPartner
from app.database.session import create_session
from app.register.partner_suggestions import parse_address
from tests.test_contract_documents import _pdf, _service
from tests.test_reextraction import TEXT, _model, _seed

FOUND = {
    "identity": {"supplier": "ABIOMED Europe GmbH", "service_email": "service@abiomed.example",
                 "service_phone": "+49 241 8860 0"},
}
FOUND_EVIDENCE = [
    {"field": "identity.supplier", "source": {"page": 1, "source_text": "ABIOMED Europe GmbH Neuenhofer Weg 3 D-52074 Aachen"}},
    {"field": "identity.service_email", "source": {"page": 9, "source_text": "E-Mail: service@abiomed.example"}},
    {"field": "identity.service_phone", "source": {"page": 9, "source_text": "Telefon +49 241 8860 0"}},
]


def test_address_is_read_only_from_a_clear_quote():
    assert parse_address("ABIOMED Europe GmbH Neuenhofer Weg 3 D-52074 Aachen") == {
        "street": "Neuenhofer Weg 3", "postal_code": "52074", "city": "Aachen", "country": "Deutschland"}
    assert parse_address("Siemens Healthcare GmbH, Henkestraße 127, 91052 Erlangen") == {
        "street": "Henkestraße 127", "postal_code": "91052", "city": "Erlangen"}
    assert parse_address("Krankenhaus Nordwest GmbH Frankfurt Steinbacher Hohl 2-26 D-60488 Frankfurt am Main")["street"] == "Steinbacher Hohl 2-26"
    # Ohne Strasse mit Hausnummer oder ohne PLZ + Ort: nichts raten.
    assert parse_address("ABIOMED Europe GmbH") == {}
    assert parse_address("ABIOMED Europe GmbH, 52074 Aachen") == {}
    assert parse_address("Neuenhofer Weg 3") == {}


def _contract_with_partner(tmp_path, slug, org_id, **partner):
    result = _service(tmp_path, TEXT, _model(FOUND, FOUND_EVIDENCE)).process(
        organization_slug=slug, original_filename="abiomed.pdf", content_type="application/pdf", content=_pdf(),
    )
    assert result.status == "imported", result.message
    session = create_session()
    try:
        row = ContractPartner(organization_id=org_id, short_name=f"ABIOMED {uuid4().hex[:6]}", name1="ABIOMED Europe GmbH", **partner)
        session.add(row)
        session.flush()
        session.get(Contract, UUID(result.contract_id)).partner_id = row.id
        session.commit()
        return result.contract_id, row.id
    finally:
        session.close()


def _client(monkeypatch, org_id, role="contract_manager"):
    actor = SimpleNamespace(organization_id=org_id, account_id=None, role=role, is_developer=False, display_name="Tester")
    monkeypatch.setattr(catalog_routes, "current_actor", lambda request, organization_slug: actor)
    monkeypatch.setattr(catalog_routes, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    app.include_router(catalog_routes.router)
    return TestClient(app)


def test_found_partner_data_is_suggested_applied_and_ignored(tmp_path, monkeypatch):
    slug, ids = _seed()
    contract_id, partner_id = _contract_with_partner(tmp_path, slug, ids["org"], phone="0241 999")
    client = _client(monkeypatch, ids["org"])
    params = {"organization_slug": slug}
    url = f"/api/catalogs/partners/{partner_id}/suggestions"

    data = client.get(url, params={**params, "contract_id": contract_id}).json()
    items = {item["field"]: item for item in data["items"]}
    assert data["can_apply"] is True
    assert items["email"]["value"] == "service@abiomed.example" and items["email"]["kind"] == "new"
    assert items["email"]["page"] == 9 and items["email"]["contract_id"] == contract_id
    # Vorhandener, anderer Wert: nur als Abweichung, nichts wird ueberschrieben.
    assert items["phone"]["kind"] == "deviating" and items["phone"]["current"] == "0241 999"
    assert (items["street"]["value"], items["postal_code"]["value"], items["city"]["value"], items["country"]["value"]) == (
        "Neuenhofer Weg 3", "52074", "Aachen", "Deutschland")

    # Uebernehmen schreibt genau diesen Wert; ein nicht angebotener Wert wird abgelehnt.
    assert client.post(f"{url}/apply", params=params, json={"field": "email", "value": "fremd@x.example"}).status_code == 404
    applied = client.post(f"{url}/apply", params=params, json={"field": "email", "value": "service@abiomed.example"})
    assert applied.status_code == 200, applied.text
    assert applied.json()["email"] == "service@abiomed.example"
    # Ignorieren: Partner bleibt, derselbe Wert kommt nicht wieder.
    assert client.post(f"{url}/dismiss", params=params, json={"field": "phone", "value": "+49 241 8860 0"}).status_code == 200
    after = {item["field"] for item in client.get(url, params=params).json()["items"]}
    assert "email" not in after and "phone" not in after and "city" in after
    session = create_session()
    try:
        assert session.get(ContractPartner, partner_id).phone == "0241 999"
        events = {row.event_name for row in session.scalars(select(ActivityLog).where(ActivityLog.object_id == partner_id))}
        assert {"partner.updated", "partner.suggestion_dismissed"} <= events
    finally:
        session.close()

    viewer = _client(monkeypatch, ids["org"], role="viewer")
    assert viewer.get(url, params=params).json()["can_apply"] is False
    assert viewer.post(f"{url}/apply", params=params, json={"field": "city", "value": "Aachen"}).status_code == 403


def test_hospital_contact_is_not_offered_to_the_partner():
    """E-Mail mit der Domain des Auftraggebers (Krankenhaus) und das Telefon auf derselben Seite gehören nicht zum Partner."""
    from app.register.partner_suggestions import found_in_contract

    partner = ContractPartner(short_name="GE HealthCare", name1="GE HealthCare GmbH")
    hospital_contact = _model(
        {"identity": {"supplier": "GE HealthCare GmbH", "customer": "Krankenhaus Nordwest GmbH",
                      "service_email": "arras.monique@khnw.de", "service_phone": "(069)7601 3264"}},
        [{"field": "identity.service_email", "source": {"page": 5, "source_text": "E-Mail: arras.monique@khnw.de"}},
         {"field": "identity.service_phone", "source": {"page": 5, "source_text": "Tel (069)7601 3264"}}],
    )
    assert found_in_contract(hospital_contact, partner) == []
    partner_contact = _model(
        {"identity": {"supplier": "GE HealthCare GmbH", "customer": "Krankenhaus Nordwest GmbH",
                      "service_email": "service@gehealthcare.com"}},
        [{"field": "identity.service_email", "source": {"page": 2, "source_text": "service@gehealthcare.com"}}],
    )
    assert [item[0] for item in found_in_contract(partner_contact, partner)] == ["email"]


def test_new_partner_is_prefilled_from_what_the_ai_found(tmp_path):
    from app.register.partner_suggestions import prefill_for_new_partner

    slug, ids = _seed()
    result = _service(tmp_path, TEXT, _model(FOUND, FOUND_EVIDENCE)).process(
        organization_slug=slug, original_filename="abiomed.pdf", content_type="application/pdf", content=_pdf(),
    )
    session = create_session()
    try:
        found = prefill_for_new_partner(session, session.get(Contract, UUID(result.contract_id)))
    finally:
        session.close()
    assert found["values"]["email"] == "service@abiomed.example"
    assert (found["values"]["street"], found["values"]["postal_code"], found["values"]["city"]) == ("Neuenhofer Weg 3", "52074", "Aachen")
    assert {item["field"] for item in found["sources"]} == set(found["values"])
