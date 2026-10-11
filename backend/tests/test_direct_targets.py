"""Direkt zur Stelle: Hinweise des Backends nennen den Ort, an dem die fehlende Angabe gepflegt wird."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.finance.calc import EntryInput, summarize
from app.rules.service import evaluate, rule_target


def _rule(kind: str, **extra):
    return SimpleNamespace(id=uuid4(), label="Regel", rule_kind=kind, contract_type_ids=[], threshold="3", field_key=None, **extra)


def _contract(**values):
    base = dict(
        term_model="terminable", contract_type_id=None, notice_period_value=None, notice_period_unit=None,
        minimum_term_value=None, minimum_term_unit=None, initial_term_value=None, initial_term_unit=None,
        renewal_period_value=None, renewal_period_unit=None, term_start_date=None, term_fixed_end_date=None,
        price_adjustment_kind=None, price_adjustment_percent=None, responsible_account_id=None,
    )
    base.update(values)
    return SimpleNamespace(**base)


def test_rule_results_point_to_the_field_they_check():
    contract = _contract()
    assert rule_target(_rule("min_notice_months"), contract) == {"tab": "register", "field": "notice_period"}
    assert rule_target(_rule("min_notice_months"), _contract(term_model=None)) == {"tab": "register", "field": "term_model"}
    assert rule_target(_rule("max_term_months"), _contract(term_model="terminable_min_term")) == {"tab": "register", "field": "minimum_term"}
    assert rule_target(_rule("max_term_months"), _contract(term_model="fixed_term")) == {"tab": "register", "field": "initial_term"}
    assert rule_target(_rule("max_renewal_months"), contract) == {"tab": "register", "field": "renewal_period"}
    assert rule_target(_rule("max_price_increase_percent"), contract) == {"tab": "register", "field": "price_adjustment_kind"}
    assert rule_target(_rule("max_price_increase_percent"), _contract(price_adjustment_kind="percent")) == {"tab": "register", "field": "price_adjustment_percent"}
    assert rule_target(_rule("max_annual_cost"), contract) == {"tab": "finance", "section": "entries"}
    required = _rule("required_field")
    required.field_key = "responsible_account_id"
    assert rule_target(required, contract) == {"tab": "register", "field": "responsible_account_id"}

    payload = evaluate(_rule("min_notice_months"), contract, None).payload()
    assert payload["outcome"] == "unknown"
    assert payload["target"] == {"tab": "register", "field": "notice_period"}
    assert payload["rule_kind"] == "min_notice_months"


def test_finance_notes_carry_targets_in_the_same_order():
    entry = EntryInput(direction="expense", amount=Decimal("100"), amount_basis="net", vat_rate=Decimal("19"), interval="monthly", valid_from=date(2026, 1, 1))
    [summary] = summarize([entry], as_of=date(2026, 10, 11), contract_end=None)
    data = summary.as_dict()
    assert data["notes"][0].startswith("Kein Vertragsende bekannt")
    assert data["note_items"][0] == {"text": data["notes"][0], "target": {"tab": "register", "section": "term"}}
    assert [item["text"] for item in data["note_items"]] == data["notes"]

    [known] = summarize([entry], as_of=date(2026, 10, 11), contract_end=date(2027, 12, 31))
    assert known.as_dict()["note_items"] == []
