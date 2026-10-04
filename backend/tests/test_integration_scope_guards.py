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


def test_contract_csv_export_is_scope_filtered_and_role_restricted():
    source = _source("app/api/routes/operations.py")
    assert "current_scope_context" in source
    assert "scoped_contract_ids" in source
    assert "Contract.id.in_(visible_ids)" in source
    assert 'identity.role not in {"admin", "contract_manager"}' in source
    assert 'event_name="contracts.exported"' in source


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


def test_import_scope_is_validated_before_processing():
    source = _source("app/api/routes/documents.py")
    assert "_validate_import_scope" in source
    assert "hospital.organization_id != org.id" in source
    assert "department.hospital_id != hospital.id" in source
    assert "_validate_import_scope(organization_slug)" in source
    assert source.index("_validate_import_scope(organization_slug)") < source.index("_processing_service.process,")


def test_activity_feed_respects_current_scope():
    source = _source("app/api/routes/activity.py")
    assert "current_scope_context" in source
    assert "scoped_contract_ids" in source
    assert "intersect_ids" in source
    assert "row.department_id == scope.department_id" in source
    assert "row.hospital_id == scope.hospital_id" in source


def test_ownership_routes_enforce_scope_and_audit_changes():
    source = _source("app/api/routes/ownership.py")
    assert "_ensure_contract_visible" in source
    assert "scoped_contract_ids" in source
    assert "_ensure_equipment_visible" in source
    assert 'event_name="contract.ownership_updated"' in source
    assert 'event_name="equipment.ownership_updated"' in source


def test_user_scope_changes_are_audited():
    source = _source("app/api/routes/user_scopes.py")
    assert 'event_name="account.scope_updated"' in source


def test_work_queue_updates_are_scope_checked_and_audited():
    source = _source("app/api/routes/work_queue.py")
    assert "scoped_contract_ids" in source
    assert "row.contract_id not in allowed" in source
    assert 'event_name=f"work_item.{body.status}"' in source
    assert 'object_type="contract"' in source


def test_unassigned_non_admin_membership_is_fail_closed():
    source = _source("app/core/scope_context.py")
    assert "_NO_SCOPE_HOSPITAL = UUID(int=0)" in source
    assert "membership.hospital_id or _NO_SCOPE_HOSPITAL" in source
    assert "actor.role != \"admin\"" in source


def test_organization_structure_reads_are_scope_filtered():
    source = _source("app/api/routes/organization_structure.py")
    assert "current_scope_context" in source
    assert 'actor.role != "admin" and not actor.is_developer' in source
    assert "Hospital.id == scope.hospital_id" in source
    assert "Department.id == scope.department_id" in source


def test_cost_center_reads_are_scope_filtered():
    source = _source("app/api/routes/cost_center_routes.py")
    assert "current_scope_context" in source
    assert 'actor.role != "admin" and not actor.is_developer' in source
    assert "CostCenter.hospital_id == scope.hospital_id" in source
    assert "CostCenter.department_id == scope.department_id" in source


def test_ai_selection_and_test_require_admin_or_developer():
    source = _source("app/api/routes/ai.py")
    assert "_require_ai_admin" in source
    assert 'getattr(request.state, "is_developer", False)' in source
    assert 'actor is not None and actor.role == "admin"' in source
    assert "_require_ai_admin(request)" in source


def test_demo_workspace_is_developer_only():
    source = _source("app/api/routes/demo.py")
    assert "_require_developer" in source
    assert 'getattr(request.state, "is_developer", False)' in source
    assert "_require_developer(request)" in source
