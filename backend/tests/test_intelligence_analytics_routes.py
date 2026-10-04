from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_analytics_router_is_registered():
    source = _source("app/main.py")
    assert "intelligence_analytics" in source
    assert "app.include_router(intelligence_analytics.router)" in source


def test_contract_analytics_are_scope_guarded():
    source = _source("app/api/routes/intelligence_analytics.py")
    assert "current_scope_context" in source
    assert "scoped_contract_ids" in source
    assert "contract_id not in visible" in source


def test_backend_engines_are_exposed_through_analytics_facade():
    source = _source("app/api/routes/intelligence_analytics.py")
    assert "summarize_risk" in source
    assert "simulate_termination" in source
    assert "answer_portfolio_question" in source
    assert "summarize_supplier_performance" in source
    assert "reconcile_invoice" in source
    assert "fingerprint_clause" in source
