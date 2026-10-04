"""H4: AI finance/service suggestions and price adjustment parsing (pure)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.finance.ai import finance_suggestions, price_adjustment_from_text, service_suggestions
from app.models.contract import Contract as ExtractedContract
from app.register.ai_mapping import proposals_from_extraction


def _model(costs: dict) -> ExtractedContract:
    return ExtractedContract.model_validate({"costs": costs})


def test_monthly_cost_with_explicit_tax_has_no_assumptions():
    [item] = finance_suggestions(
        _model({"monthly_cost": {"amount": 3500, "currency": "EUR", "period": "monthly"}, "tax_basis": "net", "tax_rate_percent": 19}),
        start=date(2026, 1, 1),
    )
    assert item["key"] == "costs.monthly_cost"
    assert item["values"] == {
        "direction": "expense", "label": "Wiederkehrende Kosten (monatlich)", "amount": "3500.00", "amount_basis": "net",
        "vat_rate": "19.00", "currency": "EUR", "interval": "monthly", "valid_from": "2026-01-01", "valid_to": None,
        "apply_price_adjustment": True,
    }
    assert item["assumptions"] == []


def test_only_primary_recurring_cost_and_flagged_assumptions():
    items = finance_suggestions(
        _model({
            "monthly_cost": {"amount": 1000, "currency": "EUR"},
            "annual_cost": {"amount": 12000, "currency": "EUR"},
            "one_time_cost": {"amount": 500, "currency": "EUR"},
        }),
        start=date(2026, 4, 1),
    )
    assert [item["key"] for item in items] == ["costs.monthly_cost", "costs.one_time_cost"]
    assert items[0]["assumptions"] == ["Netto angenommen (Steuerbasis im Vertrag nicht eindeutig)", "19 % MwSt. angenommen"]
    assert items[1]["values"]["interval"] == "once"


def test_scheduled_prices_become_yearly_steps_without_adjustment():
    items = finance_suggestions(
        _model({
            "monthly_cost": {"amount": 999, "currency": "EUR"},
            "scheduled_prices": [
                {"period_index": 2, "amount": {"amount": 8200, "currency": "EUR", "period": "annual"}},
                {"period_index": 1, "amount": {"amount": 8000, "currency": "EUR", "period": "annual"}},
            ],
            "tax_basis": "gross", "tax_rate_percent": 19,
        }),
        start=date(2025, 4, 1),
    )
    assert [(i["values"]["valid_from"], i["values"]["valid_to"], i["values"]["amount"]) for i in items] == [
        ("2025-04-01", "2026-03-31", "8000.00"), ("2026-04-01", "2027-03-31", "8200.00"),
    ]
    assert all(item["values"]["apply_price_adjustment"] is False and item["values"]["amount_basis"] == "gross" for item in items)


def test_service_suggestions_from_variable_charges_and_rates():
    items = service_suggestions(_model({
        "variable_charges": [{"label": "Einsatz außerhalb der Servicezeit", "amount": {"amount": 180, "currency": "EUR"}, "unit": "per_hour"}],
        "hourly_rate": {"amount": 125, "currency": "EUR"},
        "travel_cost": {"amount": None},
    }))
    assert [(i["key"], i["values"]["label"], i["values"]["amount"]) for i in items] == [
        ("costs.variable_charges.0", "Einsatz außerhalb der Servicezeit", "180.00"),
        ("costs.hourly_rate", "Stundensatz", "125.00"),
    ]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Die Preise erhöhen sich jährlich um 3 %.", {"kind": "percent", "percent": Decimal("3"), "interval_months": 12}),
        ("Anpassung jährlich um 2,5 Prozent", {"kind": "percent", "percent": Decimal("2.5"), "interval_months": 12}),
        ("Anpassung entsprechend dem Verbraucherpreisindex (VPI)", {"kind": "index", "index_name": "Verbraucherpreisindex"}),
        ("Festpreis für die gesamte Laufzeit", {"kind": "fixed"}),
        ("Preise werden nach Vereinbarung neu verhandelt", {"kind": "negotiation"}),
        ("jährlich 3 % oder gemäß Index", None),
        ("", None),
    ],
)
def test_price_adjustment_from_text(text, expected):
    assert price_adjustment_from_text(text) == expected


def test_register_proposals_include_price_adjustment():
    proposals = proposals_from_extraction(_model({"price_indexation": "Erhöhung jährlich um 3 %"}))
    assert proposals["price_adjustment_kind"].value == "percent"
    assert proposals["price_adjustment_percent"].value == Decimal("3")
    assert proposals["price_adjustment_percent"].source_field == "costs.price_indexation"
