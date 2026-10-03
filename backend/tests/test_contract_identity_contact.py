"""UAT Round-3 Fix 2: wörtliche Rechtsnamen + Service-Kontakt (Seite 9).

- Lieferant/Kunde bleiben im Produktions-Harness wörtlich erhalten (nur
  `strip`, keine Übersetzungs-/Transliterations-/Qualifier-Normalisierung).
- `identity.service_email` / `identity.service_phone` sind generische
  Schema-Felder (nicht ABIOMED-spezifisch), im KI-Feldkatalog, im Snapshot
  und im Detail-Identity-Block sichtbar.
"""
from app.ai.harness.pipeline import field_types, strict_value
from app.ai.harness.v3 import _normalize_fact_value
from app.contracts.detail.service import _identity_section
from app.models.contract import Contract
from app.models.values import FlexibleDate


def test_supplier_and_customer_stay_verbatim():
    assert (
        _normalize_fact_value("identity.supplier", "  ABIOMED Europe GmbH  ")
        == "ABIOMED Europe GmbH"
    )
    assert (
        _normalize_fact_value("identity.customer", "KRANKENHAUS NORDWEST gmbH")
        == "KRANKENHAUS NORDWEST gmbH"
    )
    assert (
        _normalize_fact_value("identity.customer", "Frankfurt am Main GmbH")
        == "Frankfurt am Main GmbH"
    )
    assert _normalize_fact_value("identity.contractor", "  Firma X   ") == "Firma X"


def test_service_contact_fields_are_in_extraction_schema():
    types = field_types()
    assert "identity.service_email" in types
    assert "identity.service_phone" in types
    validated = strict_value(
        types["identity.service_email"], "EUFieldService@its.jnj.com"
    )
    assert validated == "EUFieldService@its.jnj.com"


def test_service_contact_lives_in_snapshot_and_identity_section():
    contract = Contract()
    contract.identity.service_email = "EUFieldService@its.jnj.com"
    contract.identity.service_phone = "+49 241 8860 520"
    contract.dates.start_date = FlexibleDate(date="2025-04-01")
    snapshot = contract.model_dump(mode="json")
    assert snapshot["identity"]["service_email"] == "EUFieldService@its.jnj.com"
    assert snapshot["identity"]["service_phone"] == "+49 241 8860 520"

    out = _identity_section(snapshot)
    assert out["service_email"] == "EUFieldService@its.jnj.com"
    assert out["service_phone"] == "+49 241 8860 520"
    assert "service_email" not in _identity_section({})


def test_service_contact_is_optional_and_absent_when_unknown():
    assert _identity_section({"identity": {"supplier": "ABIOMED Europe GmbH"}}) == {}