"""H1.3: deterministic term engine for register contracts (pure, no DB)."""

from __future__ import annotations

from datetime import date

import pytest

from app.register.terms import (
    Period,
    TermInputs,
    compute_terms,
    first_boundary_on_or_after,
    next_boundary,
    term_end,
)

MONTHS_3 = Period(3, "months")


@pytest.mark.parametrize(
    "day,target,expected",
    [
        (date(2027, 4, 1), "quarter_end", date(2027, 6, 30)),
        (date(2027, 6, 30), "quarter_end", date(2027, 6, 30)),
        (date(2027, 7, 1), "quarter_end", date(2027, 9, 30)),
        (date(2027, 12, 31), "quarter_end", date(2027, 12, 31)),
        (date(2028, 2, 10), "month_end", date(2028, 2, 29)),
        (date(2027, 7, 1), "half_year_end", date(2027, 12, 31)),
        (date(2027, 1, 1), "year_end", date(2027, 12, 31)),
        (date(2027, 12, 31), "month_end", date(2027, 12, 31)),
    ],
)
def test_first_boundary(day, target, expected):
    assert first_boundary_on_or_after(day, target) == expected


def test_next_boundary_rolls_over_year():
    assert next_boundary(date(2027, 12, 31), "quarter_end") == date(2028, 3, 31)


def test_term_end_is_inclusive():
    assert term_end(date(2026, 4, 1), Period(3, "years")) == date(2029, 3, 31)


def test_hydmedia_example_terminable_quarter_end():
    """Screenshot 152449: start 01.04.2027, 3 Monate zum Quartalsende, Erinnerung 3 Monate."""
    result = compute_terms(
        TermInputs(
            term_model="terminable",
            start_date=date(2027, 4, 1),
            notice_period=MONTHS_3,
            notice_to="quarter_end",
            reminder_lead_months=3,
        ),
        as_of=date(2026, 10, 1),
    )
    assert result.status == "complete"
    assert result.possible_end == date(2027, 9, 30)
    assert result.cancel_by == date(2027, 6, 30)
    assert result.reminder_date == date(2027, 3, 30)
    assert result.earliest_end == date(2027, 9, 30)


def test_terminable_moves_forward_with_as_of():
    result = compute_terms(
        TermInputs(term_model="terminable", start_date=date(2020, 1, 1), notice_period=MONTHS_3, notice_to="quarter_end"),
        as_of=date(2026, 10, 4),
    )
    assert result.possible_end == date(2027, 3, 31)
    assert result.cancel_by == date(2026, 12, 31)
    assert result.earliest_end == date(2020, 6, 30)


def test_terminable_anytime():
    result = compute_terms(
        TermInputs(term_model="terminable", start_date=date(2020, 1, 1), notice_period=Period(4, "weeks"), notice_to="anytime"),
        as_of=date(2026, 10, 4),
    )
    assert result.cancel_by == date(2026, 10, 4)
    assert result.possible_end == date(2026, 11, 1)


def test_terminable_min_term_respects_minimum():
    result = compute_terms(
        TermInputs(
            term_model="terminable_min_term",
            start_date=date(2026, 1, 1),
            minimum_term=Period(2, "years"),
            notice_period=MONTHS_3,
            notice_to="year_end",
        ),
        as_of=date(2026, 10, 4),
    )
    assert result.possible_end == date(2027, 12, 31)
    assert result.cancel_by == date(2027, 9, 30)
    assert result.earliest_end == date(2027, 12, 31)


def test_terminable_requires_calendar_target():
    result = compute_terms(
        TermInputs(term_model="terminable", start_date=date(2026, 1, 1), notice_period=MONTHS_3, notice_to="contract_end"),
        as_of=date(2026, 10, 4),
    )
    assert result.status == "incomplete"
    assert "notice_to" in result.missing


def test_hydmedia_example_auto_renewal_weeks():
    """List row: frueh. Ende 16.06.2027, kuendbar bis 21.04.2027 (8 Wochen)."""
    result = compute_terms(
        TermInputs(
            term_model="auto_renewal",
            start_date=date(2025, 6, 17),
            fixed_end_date=date(2027, 6, 16),
            notice_period=Period(8, "weeks"),
            renewal_period=Period(1, "years"),
        ),
        as_of=date(2026, 10, 1),
    )
    assert result.earliest_end == date(2027, 6, 16)
    assert result.possible_end == date(2027, 6, 16)
    assert result.cancel_by == date(2027, 4, 21)


def test_auto_renewal_rolls_into_next_period():
    result = compute_terms(
        TermInputs(
            term_model="auto_renewal",
            start_date=date(2024, 1, 1),
            initial_term=Period(1, "years"),
            notice_period=MONTHS_3,
            renewal_period=Period(1, "years"),
            reminder_lead_months=2,
        ),
        as_of=date(2026, 10, 4),
    )
    assert result.earliest_end == date(2024, 12, 31)
    assert result.possible_end == date(2027, 12, 31)
    assert result.cancel_by == date(2027, 9, 30)
    assert result.reminder_date == date(2027, 7, 30)


def test_auto_renewal_without_renewal_period_is_incomplete_after_deadline():
    result = compute_terms(
        TermInputs(
            term_model="auto_renewal",
            start_date=date(2024, 1, 1),
            initial_term=Period(1, "years"),
            notice_period=MONTHS_3,
        ),
        as_of=date(2026, 10, 4),
    )
    assert result.status == "incomplete"
    assert result.missing == ["renewal_period_value"]


def test_fixed_term():
    result = compute_terms(
        TermInputs(term_model="fixed_term", start_date=date(2024, 7, 29), initial_term=Period(3, "years"), reminder_lead_months=6),
        as_of=date(2026, 10, 4),
    )
    assert result.possible_end == date(2027, 7, 28)
    assert result.cancel_by is None
    assert result.reminder_date == date(2027, 1, 28)


def test_perpetual_has_no_deadlines():
    result = compute_terms(TermInputs(term_model="perpetual", start_date=date(2010, 1, 1)), as_of=date(2026, 10, 4))
    assert result.status == "not_applicable"
    assert result.possible_end is None and result.cancel_by is None


def test_terminated_contract_reports_actual_end():
    result = compute_terms(
        TermInputs(term_model="auto_renewal", start_date=date(2020, 1, 1), terminated_effective=date(2022, 11, 20)),
        as_of=date(2026, 10, 4),
    )
    assert result.actual_end == date(2022, 11, 20)
    assert result.cancel_by is None


@pytest.mark.parametrize(
    "inputs,missing",
    [
        (TermInputs(), ["term_model"]),
        (TermInputs(term_model="fixed_term"), ["term_start_date"]),
        (TermInputs(term_model="fixed_term", start_date=date(2026, 1, 1)), ["term_fixed_end_date", "initial_term_value"]),
        (
            TermInputs(term_model="terminable_min_term", start_date=date(2026, 1, 1)),
            ["notice_period_value", "notice_to", "minimum_term_value"],
        ),
    ],
)
def test_missing_inputs_are_reported(inputs, missing):
    result = compute_terms(inputs, as_of=date(2026, 10, 4))
    assert result.status == "incomplete"
    assert result.missing == missing


def test_end_before_start_is_rejected():
    result = compute_terms(
        TermInputs(term_model="fixed_term", start_date=date(2026, 1, 1), fixed_end_date=date(2025, 1, 1)),
        as_of=date(2026, 10, 4),
    )
    assert result.status == "incomplete"
