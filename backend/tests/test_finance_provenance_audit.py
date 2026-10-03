"""Regression gates for inferred annual rates from staged contract prices.

A recurring annual display must never be inferred from a partial, duplicate,
or mixed-currency price schedule. No contract-specific values are hard-coded
into extraction logic; these are synthetic fixtures only.
"""
from app.ai.harness.v3 import _steady_annual_amount


def schedule(amounts, *, currency="EUR"):
    return [
        {"period_index": index, "amount": {"amount": amount, "currency": currency}}
        for index, amount in enumerate(amounts, start=1)
    ]


def test_complete_four_year_staged_rate():
    assert _steady_annual_amount(
        schedule([0, 8000, 8000, 8000]), expected_years=4
    ) == 8000.0


def test_partial_schedule_must_not_be_presented_as_annual():
    incomplete = [
        {"period_index": 1, "amount": {"amount": 0, "currency": "EUR"}},
        {"period_index": 3, "amount": {"amount": 8000, "currency": "EUR"}},
        {"period_index": 4, "amount": {"amount": 8000, "currency": "EUR"}},
    ]
    assert _steady_annual_amount(incomplete, expected_years=4) is None
    assert _steady_annual_amount(schedule([0, 8000, 8000]), expected_years=4) is None


def test_duplicates_are_not_silently_overwritten():
    duplicated = schedule([0, 8000, 8000, 8000])
    duplicated.append(
        {"period_index": 2, "amount": {"amount": 9999, "currency": "EUR"}}
    )
    assert _steady_annual_amount(duplicated, expected_years=4) is None


def test_currency_conflicts_do_not_produce_annual_price():
    rows = schedule([0, 8000, 8000, 8000])
    rows[2]["amount"]["currency"] = "USD"
    assert _steady_annual_amount(rows, expected_years=4) is None


def test_yearly_rate_must_not_hide_actual_price_escalation():
    assert _steady_annual_amount(
        schedule([0, 8000, 9000, 9000]), expected_years=4
    ) is None


def test_only_one_paid_year_cannot_establish_steady_rate():
    assert _steady_annual_amount(
        schedule([0, 8000]), expected_years=2
    ) is None
