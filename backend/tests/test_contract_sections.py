"""Abschnitte je Vertragstyp (Plan VERTRAGSPROFIL_ABSCHNITTE_PLAN_20261011)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.database.models.contract import Contract
from app.database.models.organization import Organization
from app.database.models.register import CatalogContractType
from app.database.session import create_session
from app.register import catalogs
from app.register.sections import contract_sections, default_sections, normalize, sections_for_type
from app.register.service import RegisterActor, create_manual_contract


def test_default_profiles_by_type_code():
    assert default_sections("wartung") == ["scope", "sla", "maintenance", "equipment"]
    assert default_sections("dienstleistung") == ["scope", "sla"]
    assert default_sections("miete") == ["equipment"]
    assert default_sections("versicherung") == []
    assert default_sections("eigener_typ") == ["scope", "sla", "maintenance", "equipment"]  # unbekannt: alles
    assert sections_for_type(None) == ["scope", "sla", "maintenance", "equipment"]
    assert contract_sections(None) is None  # ohne Typ: alle zeigen, nichts raten
    assert contract_sections(SimpleNamespace(code="miete", label="Mietvertrag", sections=None)) == {
        "type_label": "Mietvertrag", "scope": False, "sla": False, "maintenance": False, "equipment": True,
    }
    assert sections_for_type(SimpleNamespace(code="miete", label="Mietvertrag", sections=["sla", "scope"])) == ["scope", "sla"]
    assert normalize(None) is None
    with pytest.raises(ValueError):
        normalize(["erfunden"])


def test_custom_sections_reset_and_detail():
    from app.api.routes.contracts import _build_augmented_detail

    session = create_session()
    try:
        org = Organization(name="Abschnitte", slug=f"sections-{uuid4().hex[:10]}")
        session.add(org)
        session.flush()
        rent = catalogs.upsert_type(session, org.id, {"code": "miete", "label": "Mietvertrag"})
        assert catalogs.type_payload(rent)["sections"] == ["equipment"] and catalogs.type_payload(rent)["sections_default"] is True
        catalogs.upsert_type(session, org.id, {"sections": ["equipment", "maintenance"]}, rent)
        assert catalogs.type_payload(rent)["sections"] == ["maintenance", "equipment"]
        assert catalogs.type_payload(rent)["sections_default"] is False
        with pytest.raises(catalogs.CatalogError):
            catalogs.upsert_type(session, org.id, {"sections": ["unsinn"]}, rent)

        actor = RegisterActor(organization_id=org.id, account_id=None, display_name="Tester", role="admin")
        contract = create_manual_contract(session, actor=actor, hospital_id=None, values={"short_description": "Miete MRT"})
        session.commit()
        assert _build_augmented_detail(session, organization_id=org.id, contract_id=contract.id)["sections"] is None
        session.get(Contract, contract.id).contract_type_id = rent.id
        session.commit()
        detail = _build_augmented_detail(session, organization_id=org.id, contract_id=contract.id)
        assert detail["sections"] == {"type_label": "Mietvertrag", "scope": False, "sla": False, "maintenance": True, "equipment": True}

        catalogs.upsert_type(session, org.id, {"sections": None}, session.get(CatalogContractType, rent.id))
        session.commit()
        assert _build_augmented_detail(session, organization_id=org.id, contract_id=contract.id)["sections"]["maintenance"] is False
    finally:
        session.close()
