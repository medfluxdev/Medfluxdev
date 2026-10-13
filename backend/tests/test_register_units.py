"""H1/H2 pure logic: AI mapping, field validation, status workflow, partner matching."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.contract import Contract as ExtractedContract
from app.register.ai_mapping import notice_target_from_text, proposals_from_extraction
from app.register.catalogs import normalize_partner_name, partner_similarity
from app.register.fields import FieldValidationError, coerce_value, validate_pairs
from app.register.status import TransitionError, allowed_targets, plan_transition


def _extracted(**groups) -> ExtractedContract:
    return ExtractedContract.model_validate(groups)


# --------------------------------------------------------------------------- AI mapping


@pytest.mark.parametrize(
    "text,expected",
    [
        ("mit einer Frist von 3 Monaten zum Quartalsende", "quarter_end"),
        ("zum Ende eines Kalendermonats", "month_end"),
        ("zum Ende des Kalenderjahres", "year_end"),
        ("zum Halbjahresende", "half_year_end"),
        ("zum Monatsende oder Quartalsende", None),
        ("schriftlich", None),
        (None, None),
    ],
)
def test_notice_target_from_text(text, expected):
    assert notice_target_from_text(text) == expected


def test_auto_renewal_mapping_with_evidence_sources():
    model = _extracted(
        identity={"contract_title": "Servicevertrag CT Scanner"},
        dates={"start_date": {"date": "2025-01-01"}, "duration": {"value": 1, "unit": "years"}},
        termination={
            "cancellation_period": {"value": 3, "unit": "months"},
            "cancellation_to_contract_end": "to_contract_end",
            "automatic_renewal": True,
            "renewal_period": {"value": 1, "unit": "years"},
        },
    )
    proposals = proposals_from_extraction(model)
    assert proposals["term_model"].value == "auto_renewal"
    assert proposals["term_start_date"].value == date(2025, 1, 1)
    assert proposals["notice_to"].value == "contract_end"
    assert proposals["notice_period_value"].value == 3
    assert proposals["notice_period_unit"].value == "months"
    assert proposals["renewal_period_unit"].source_field == "termination.renewal_period"
    assert proposals["short_description"].value == "Servicevertrag CT Scanner"


def test_terminable_mapping_from_condition_text():
    model = _extracted(
        dates={"start_date": {"date": "2027-04-01"}},
        termination={
            "cancellation_period": {"value": 3, "unit": "months"},
            "cancellation_condition": "zum Quartalsende",
        },
    )
    proposals = proposals_from_extraction(model)
    assert proposals["term_model"].value == "terminable"
    assert proposals["notice_to"].value == "quarter_end"


def test_ambiguous_extraction_leaves_fields_empty():
    model = _extracted(termination={"cancellation_condition": "nach Absprache"})
    proposals = proposals_from_extraction(model)
    assert "term_model" not in proposals
    assert "notice_to" not in proposals


def test_event_based_start_is_not_invented():
    model = _extracted(dates={"start_date": {"condition": "Übergabedatum"}})
    assert "term_start_date" not in proposals_from_extraction(model)


# --------------------------------------------------------------------------- fields


def test_coerce_values():
    assert coerce_value("term_start_date", "2026-01-31") == date(2026, 1, 31)
    assert coerce_value("short_description", "  Wartung  ") == "Wartung"
    assert coerce_value("short_description", "  ") is None
    assert coerce_value("is_framework", True) is True
    assert coerce_value("notice_to", "quarter_end") == "quarter_end"
    assert isinstance(coerce_value("partner_id", str(uuid.uuid4())), uuid.UUID)


@pytest.mark.parametrize(
    "key,value",
    [
        ("term_start_date", "31.01.2026"),
        ("notice_to", "sometimes"),
        ("is_framework", "yes"),
        ("reminder_lead_months", 99),
        ("notice_period_value", True),
        ("register_number", "000001"),
        ("short_description", "x" * 501),
    ],
)
def test_coerce_rejects_invalid(key, value):
    with pytest.raises(FieldValidationError):
        coerce_value(key, value)


def test_pairs_and_date_order():
    with pytest.raises(FieldValidationError):
        validate_pairs({"notice_period_value": 3, "notice_period_unit": None})
    with pytest.raises(FieldValidationError):
        validate_pairs({"term_start_date": date(2026, 2, 1), "term_fixed_end_date": date(2026, 1, 1)})
    validate_pairs({"notice_period_value": 3, "notice_period_unit": "months"})


# --------------------------------------------------------------------------- status


def _plan(**overrides):
    params = dict(
        current="in_arbeit",
        target="gueltig",
        role="contract_manager",
        is_developer=False,
        values={"short_description": "Wartung", "term_model": "perpetual", "term_start_date": date(2026, 1, 1), "supplier": "X"},
        effective_date=None,
        terminated_on=None,
        review_pending=False,
        acknowledge_unreviewed=False,
    )
    params.update(overrides)
    return plan_transition(**params)


def test_allowed_targets_by_role():
    assert allowed_targets("in_arbeit", "contract_manager") == ["gueltig"]
    assert allowed_targets("in_arbeit", "admin") == ["gueltig", "geloescht"]
    assert allowed_targets("beendet", "contract_manager") == ["gueltig"]
    assert allowed_targets("gueltig", "viewer") == []
    assert allowed_targets("gueltig", "reviewer") == []
    assert allowed_targets("geloescht", "admin") == ["in_arbeit"]
    assert allowed_targets("geloescht", "admin", restore_to="beendet") == ["beendet"]
    assert allowed_targets("geloescht", "contract_manager", restore_to="beendet") == []
    assert allowed_targets("in_arbeit", "viewer", is_developer=True) == ["gueltig", "geloescht"]


def test_valid_requires_master_data():
    with pytest.raises(TransitionError) as excinfo:
        _plan(values={"supplier": None})
    assert excinfo.value.status_code == 422
    assert set(excinfo.value.missing) == {"short_description", "term_model", "term_start_date", "partner_id"}


def test_valid_requires_review_or_acknowledgement():
    with pytest.raises(TransitionError) as excinfo:
        _plan(review_pending=True)
    assert excinfo.value.status_code == 409
    assert _plan(review_pending=True, acknowledge_unreviewed=True).target == "gueltig"


def test_terminate_requires_dates_in_order():
    with pytest.raises(TransitionError):
        _plan(current="gueltig", target="gekuendigt")
    with pytest.raises(TransitionError):
        _plan(current="gueltig", target="gekuendigt", terminated_on=date(2026, 5, 1), effective_date=date(2026, 4, 1))
    plan = _plan(current="gueltig", target="gekuendigt", terminated_on=date(2026, 5, 1), effective_date=date(2026, 12, 31))
    assert plan.updates == {"terminated_on": date(2026, 5, 1), "terminated_effective": date(2026, 12, 31)}


def test_reactivation_clears_termination():
    plan = _plan(current="gekuendigt", target="gueltig")
    assert plan.updates == {"terminated_on": None, "terminated_effective": None, "ended_on": None}


def test_forbidden_and_impossible_transitions():
    with pytest.raises(TransitionError) as excinfo:
        _plan(current="in_arbeit", target="beendet")
    assert excinfo.value.status_code == 409
    with pytest.raises(TransitionError) as excinfo:
        _plan(current="beendet", target="geloescht")
    assert excinfo.value.status_code == 403
    assert _plan(current="beendet", target="geloescht", role="admin").target == "geloescht"


# --------------------------------------------------------------------------- partners


def test_partner_name_normalisation():
    assert normalize_partner_name("Siemens Healthcare GmbH") == "siemens healthcare"
    assert normalize_partner_name("Müller & Söhne KG") == "muller sohne"


@pytest.mark.parametrize(
    "left,right,minimum",
    [
        ("Siemens Healthcare GmbH", "SIEMENS HEALTHCARE", 1.0),
        ("AGFA HealthCare GmbH", "AGFA HealthCare Germany GmbH", 0.85),
        ("Philips GmbH", "Philips Medizin Systeme", 0.85),
    ],
)
def test_partner_similarity_detects_variants(left, right, minimum):
    assert partner_similarity(left, right) >= minimum


def test_partner_similarity_keeps_distinct_vendors_apart():
    assert partner_similarity("Siemens Healthcare GmbH", "GE Healthcare GmbH") < 0.85
    assert partner_similarity("", "GE") == 0.0


def test_cancel_storno_returns_to_previous_status_without_changes():
    plan = _plan(current="geloescht", target="beendet", role="admin", restore_to="beendet")
    assert plan.target == "beendet" and plan.updates == {}
    assert _plan(current="geloescht", target="in_arbeit", role="admin").target == "in_arbeit"
    with pytest.raises(TransitionError) as excinfo:
        _plan(current="geloescht", target="in_arbeit", role="admin", restore_to="beendet")
    assert excinfo.value.status_code == 409
    with pytest.raises(TransitionError) as excinfo:
        _plan(current="geloescht", target="gueltig", role="admin", restore_to="beendet")
    assert excinfo.value.status_code == 409
    with pytest.raises(TransitionError) as excinfo:
        _plan(current="geloescht", target="beendet", role="contract_manager", restore_to="beendet")
    assert excinfo.value.status_code == 403
