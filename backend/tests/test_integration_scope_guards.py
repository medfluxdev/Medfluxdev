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


def test_document_routes_fail_closed_for_scoped_access():
    source = _source("app/api/routes/documents.py")
    assert "_ensure_document_visible" in source
    assert "ContractDocument.document_version_id" in source
    assert "scoped_contract_ids" in source
    assert "_preflight_document(organization_slug, document_version_id)" in source


def test_import_scope_is_persisted_server_side():
    source = _source("app/api/routes/documents.py")
    assert "_assign_import_scope" in source
    assert "assign_contract_ownership" in source
    assert "scope.department_id" in source
    assert "scope.hospital_id" in source


def test_activity_feed_respects_current_scope():
    source = _source("app/api/routes/activity.py")
    assert "current_scope_context" in source
    assert "scoped_contract_ids" in source
    assert "intersect_ids" in source
    assert "row.department_id == scope.department_id" in source
    assert "row.hospital_id == scope.hospital_id" in source
