from datetime import date
from decimal import Decimal

from app.contract_intelligence.copilot import copilot_response
from app.contract_intelligence.scenario import simulate_termination
from app.contract_intelligence.supplier import summarize_supplier_performance


def test_supplier_performance_is_explainable_rollup():
    result = summarize_supplier_performance([{"status": "breached"}, {"status": "satisfied"}])
    assert result["breach_rate"] == 0.5


def test_copilot_requires_evidence():
    result = copilot_response(answer="x", evidence=[])
    assert result["grounded"] is False
    assert result["requires_review"] is True


def test_scenario_refuses_missing_inputs():
    result = simulate_termination(annual_cost=None, termination_date=None, contract_end=None)
    assert result["known"] is False


def test_scenario_uses_only_explicit_inputs():
    result = simulate_termination(
        annual_cost=Decimal("3650"),
        termination_date=date(2026, 1, 1),
        contract_end=date(2026, 2, 1),
    )
    assert result["estimated_avoided_cost"] == Decimal("310.00")
