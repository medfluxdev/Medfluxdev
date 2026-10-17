"""Leistungen & SLA: Leistungsumfang (Text), Verfügbarkeit (%) und Pönalen als gepflegte Vertragsdaten."""

from __future__ import annotations

from app.register.fields import FIELDS, FieldValidationError, coerce_value
from tests.test_renewal_brief import _setup

import pytest


def test_service_fields_are_validated():
    assert FIELDS["sla_availability_percent"].group == "service"
    assert str(coerce_value("sla_availability_percent", "99,5")) == "99.500"
    with pytest.raises(FieldValidationError):
        coerce_value("sla_availability_percent", "101")
    with pytest.raises(FieldValidationError):
        coerce_value("sla_availability_percent", "-1")
    assert coerce_value("penalty_terms", "  0,5 % je Tag Verzug  ") == "0,5 % je Tag Verzug"


def test_service_fields_round_trip_through_register(monkeypatch):
    slug, ids, client = _setup(monkeypatch)
    query = {"organization_slug": slug}
    admin = client("admin", "admin")
    cid = admin.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung MRT"}}).json()["contract_id"]
    response = admin.patch(f"/api/contracts/{cid}/register", params=query, json={"changes": {
        "service_scope_text": "Wartung und Reparatur aller MRT-Komponenten",
        "sla_availability_percent": "99.5",
        "penalty_terms": "0,5 % der Monatspauschale je Stunde Überschreitung",
    }})
    assert response.status_code == 200, response.text
    fields = admin.get(f"/api/contracts/{cid}/register", params=query).json()["fields"]
    assert fields["sla_availability_percent"]["value"] in ("99.500", 99.5, "99.5")
    assert fields["sla_availability_percent"]["group"] == "service"
    assert fields["service_scope_text"]["value"].startswith("Wartung und Reparatur")
    assert fields["penalty_terms"]["origin"] == "manual"
    bad = admin.patch(f"/api/contracts/{cid}/register", params=query, json={"changes": {"sla_availability_percent": "150"}})
    assert bad.status_code == 422
