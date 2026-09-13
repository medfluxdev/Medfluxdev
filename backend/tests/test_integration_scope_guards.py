from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_intelligence_routes_enforce_contract_scope():
    source = _source("app/api/routes/intelligence.py")
    assert "current_scope_context" in source
    assert "scoped_contract_ids" in source
    assert "_require_visible_contract" in source
    assert "contract_graph" in source
    assert "contract_obligations" in source
    assert "contract_policies" in source
    assert "contract_actions" in source


def test_intelligence_events_are_scope_filtered():
    source = _source("app/api/routes/intelligence.py")
    assert "IntelligenceEvent.contract_id.in_(visible)" in source


def test_contract_csv_export_is_scope_filtered():
    source = _source("app/api/routes/operations.py")
    assert "current_scope_context" in source
    assert "scoped_contract_ids" in source
    assert "Contract.id.in_(visible_ids)" in source
