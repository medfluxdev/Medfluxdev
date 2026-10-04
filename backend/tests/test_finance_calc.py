"""H4: deterministic finance calculation on whole months (pure)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.finance.calc import EntryInput, PriceAdjustment, adjustment_factor, allocate, net_gross, summarize

D = Decimal


def entry(**overrides) -> EntryInput:
    values = dict(
        direction="expense", amount=D("3500"), amount_basis="net", vat_rate=D("19"), interval="monthly",
        valid_from=date(2026, 1, 1),
    )
    values.update(overrides)
    return EntryInput(**values)


def test_net_gross_from_either_basis():
    assert net_gross(D("3500"), "net", D("19")) == (D("3500"), D("4165.00"))
    net, gross = net_gross(D("4165"), "gross", D("19"))
    assert net.quantize(D("0.01")) == D("3500.00") and gross == D("4165")


def test_hydmedia_monthly_example_with_known_end():
    [summary] = summarize([entry()], as_of=date(2026, 10, 4), contract_end=date(2027, 12, 31))
    expense = summary.as_dict()["expense"]
    assert expense["current_year"] == {"net": "42000.00", "gross": "49980.00"}
    assert expense["to_date"] == {"net": "35000.00", "gross": "41650.00"}
    assert expense["remaining_to_end"] == {"net": "49000.00", "gross": "58310.00"}  # Nov 2026 – Dec 2027: 14 months
    assert expense["total_term"] == {"net": "84000.00", "gross": "99960.00"}
    assert expense["annual_run_rate"] == {"net": "42000.00", "gross": "49980.00"}
    assert summary.notes == []


@pytest.mark.parametrize(
    "interval,amount,expected_year_net",
    [("quarterly", "3000", "12000.00"), ("semi_annual", "6000", "12000.00"), ("annual", "12000", "12000.00")],
)
def test_intervals_are_spread_over_whole_months(interval, amount, expected_year_net):
    [summary] = summarize([entry(interval=interval, amount=D(amount))], as_of=date(2026, 6, 15), contract_end=date(2026, 12, 31))
    assert summary.as_dict()["expense"]["current_year"]["net"] == expected_year_net


def test_partial_months_count_as_whole_months():
    [summary] = summarize(
        [entry(amount=D("100"), vat_rate=D("0"), valid_from=date(2026, 3, 20), valid_to=date(2026, 5, 2))],
        as_of=date(2026, 12, 1), contract_end=None,
    )
    assert summary.as_dict()["expense"]["total_term"]["net"] == "300.00"


def test_once_entry_only_in_first_month_and_not_in_run_rate():
    [summary] = summarize(
        [entry(amount=D("1000"), interval="once", valid_from=date(2026, 2, 1))],
        as_of=date(2026, 10, 1), contract_end=date(2028, 1, 31),
    )
    data = summary.as_dict()["expense"]
    assert data["current_year"]["net"] == "1000.00"
    assert data["remaining_to_end"]["net"] == "0.00"
    assert data["annual_run_rate"]["net"] == "0.00"


def test_unknown_end_with_open_recurring_entry_is_not_guessed():
    [summary] = summarize([entry()], as_of=date(2026, 10, 4), contract_end=None)
    data = summary.as_dict()["expense"]
    assert data["remaining_to_end"] is None and data["total_term"] is None
    assert data["current_year"]["net"] == "42000.00"
    assert "Kein Vertragsende bekannt" in summary.notes[0]


def test_unknown_end_but_all_entries_bounded_is_computable():
    [summary] = summarize(
        [entry(valid_to=date(2028, 6, 30))], as_of=date(2026, 10, 4), contract_end=None,
    )
    assert summary.as_dict()["expense"]["total_term"]["net"] == str(D("3500") * 30) + ".00"


def test_income_and_expense_are_separate():
    [summary] = summarize(
        [entry(), entry(direction="income", amount=D("500"), vat_rate=D("0"))],
        as_of=date(2026, 1, 31), contract_end=date(2026, 12, 31),
    )
    data = summary.as_dict()
    assert data["income"]["total_term"]["net"] == "6000.00"
    assert data["expense"]["total_term"]["net"] == "42000.00"


def test_percent_price_adjustment_projects_future_months():
    adjustment = PriceAdjustment(kind="percent", percent=D("3"), next_date=date(2027, 1, 1), interval_months=12)
    assert adjustment_factor(adjustment, date(2026, 12, 1)) == 1
    assert adjustment_factor(adjustment, date(2027, 1, 1)) == D("1.03")
    assert adjustment_factor(adjustment, date(2028, 3, 1)) == D("1.03") ** 2
    [summary] = summarize(
        [entry(amount=D("1000"), vat_rate=D("0"))], as_of=date(2026, 10, 4), contract_end=date(2027, 12, 31), adjustment=adjustment,
    )
    data = summary.as_dict()["expense"]
    assert data["remaining_to_end"]["net"] == "14360.00"  # 2 x 1000 + 12 x 1030
    assert summary.projected_adjustment is True


def test_entries_opting_out_of_adjustment_and_index_note():
    adjustment = PriceAdjustment(kind="index", next_date=date(2027, 1, 1))
    [summary] = summarize(
        [entry(amount=D("1000"), vat_rate=D("0"), apply_price_adjustment=False)],
        as_of=date(2026, 10, 4), contract_end=date(2027, 12, 31), adjustment=adjustment,
    )
    assert summary.as_dict()["expense"]["remaining_to_end"]["net"] == "14000.00"
    assert any("Index" in note for note in summary.notes)


def test_currencies_are_never_mixed():
    summaries = summarize([entry(), entry(currency="CHF", amount=D("100"))], as_of=date(2026, 1, 1), contract_end=date(2026, 12, 31))
    assert [item.currency for item in summaries] == ["CHF", "EUR"]


def test_allocation_rounding_remainder_goes_to_largest_share():
    parts = allocate(D("100.00"), [("a", D("33.33")), ("b", D("33.33")), ("c", D("33.34"))])
    assert sum(value for _, value in parts) == D("100.00")
    assert dict(parts)["c"] == D("33.34")
