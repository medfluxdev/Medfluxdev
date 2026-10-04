"""Database-free cost projection regressions for contract detail responses."""

from datetime import date
from decimal import Decimal

from app.contracts.calculation import calculate_contract
from app.contracts.detail.service import _costs_section
from app.models.contract import Contract, Costs
from app.models.values import Money


def test_cost_detail_preserves_one_time_installation_and_total_amounts():
    contract = Contract(
        id="ONE-TIME",
        costs=Costs(
            default_currency="EUR",
            one_time_cost=Money(amount="12000", currency="EUR"),
            setup_installation_cost=Money(amount="9500", currency="EUR"),
            total_contract_value=Money(amount="21500", currency="EUR"),
        ),
    )
    calculated = calculate_contract(contract, as_of_date=date(2025, 6, 1))

    result = _costs_section(calculated)

    projected = {item["key"]: item["amount"] for item in result["category_totals"]}
    assert projected["one_time_cost"] == Decimal("12000")
    assert projected["setup_installation_cost"] == Decimal("9500")
