"""Fast, database-free safety checks for opt-in contract deletion."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import contracts


def _request(*, role="admin", organization_id=None, actor=True):
    identity = SimpleNamespace(
        role=role,
        account_id=uuid4(),
        organization_id=organization_id or uuid4(),
    ) if actor else None
    return SimpleNamespace(state=SimpleNamespace(actor=identity))


@pytest.fixture(autouse=True)
def _keep_organization_isolation_checks_in_secure_mode(monkeypatch):
    # CI enables the local unauthenticated test mode globally. These tests model
    # authenticated actors, so exercise the fail-closed organization check.
    monkeypatch.setattr(contracts.settings, "medflux_insecure_dev", False)


def test_deletion_off_when_switched_off(monkeypatch):
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", False)
    with pytest.raises(HTTPException) as exc:
        contracts._require_explicit_delete_permission(_request())
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", ["viewer", "reviewer", "contract_manager", "", None])
def test_only_admin_confirms_or_restores(monkeypatch, role):
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    with pytest.raises(HTTPException) as exc:
        contracts._require_explicit_delete_permission(_request(role=role))
    assert exc.value.status_code == 403


@pytest.mark.parametrize(("role", "allowed"), [("admin", True), ("contract_manager", True), ("reviewer", False), ("viewer", False), (None, False)])
def test_request_deletion_editors_only(monkeypatch, role, allowed):
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    if allowed:
        contracts._require_explicit_delete_permission(_request(role=role), "contract.delete_request")
    else:
        with pytest.raises(HTTPException):
            contracts._require_explicit_delete_permission(_request(role=role), "contract.delete_request")


def test_deletion_enabled_by_default():
    from app.core.config import Settings

    assert Settings.model_fields["contracts_allow_delete"].default is True


def test_missing_actor_cannot_delete(monkeypatch):
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    with pytest.raises(HTTPException) as exc:
        contracts._require_explicit_delete_permission(_request(actor=False))
    assert exc.value.status_code == 403


def test_auth_disabled_cannot_delete(monkeypatch):
    monkeypatch.setattr(contracts.settings, "auth_enabled", False)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    with pytest.raises(HTTPException) as exc:
        contracts._require_explicit_delete_permission(_request())
    assert exc.value.status_code == 403


def test_actor_organization_isolation():
    organization = uuid4()
    assert contracts.actor_org_mismatch(_request(organization_id=organization), organization) is False
    assert contracts.actor_org_mismatch(_request(), organization) is True
    assert contracts.actor_org_mismatch(_request(actor=False), organization) is True


def test_capability_denied_without_explicit_opt_in(monkeypatch):
    organization = uuid4()
    actor_request = _request(organization_id=organization)
    fake_session = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(contracts, "create_session", lambda: fake_session)
    monkeypatch.setattr(contracts, "get_organization", lambda session, slug: SimpleNamespace(id=organization))
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", False)
    result = contracts.contract_deletion_capabilities(actor_request, "test-org")
    assert result == {"can_request": False, "can_delete": False, "can_restore": False, "requires_confirmation": True}


def test_capability_rejects_cross_org(monkeypatch):
    fake_session = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(contracts, "create_session", lambda: fake_session)
    monkeypatch.setattr(contracts, "get_organization", lambda session, slug: SimpleNamespace(id=uuid4()))
    with pytest.raises(HTTPException) as exc:
        contracts.contract_deletion_capabilities(_request(), "another-org")
    assert exc.value.status_code == 404


def test_capability_granted_only_to_opted_in_admin(monkeypatch):
    organization = uuid4()
    fake_session = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(contracts, "create_session", lambda: fake_session)
    monkeypatch.setattr(contracts, "get_organization", lambda session, slug: SimpleNamespace(id=organization))
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    assert contracts.contract_deletion_capabilities(
        _request(role="admin", organization_id=organization), "test-org"
    ) == {"can_request": True, "can_delete": True, "can_restore": True, "requires_confirmation": True}
    # Vertragsmanagement darf beantragen, aber nicht bestätigen oder wiederherstellen.
    assert contracts.contract_deletion_capabilities(
        _request(role="contract_manager", organization_id=organization), "test-org"
    ) == {"can_request": True, "can_delete": False, "can_restore": False, "requires_confirmation": True}
    assert contracts.contract_deletion_capabilities(
        _request(role="viewer", organization_id=organization), "test-org"
    )["can_request"] is False


@pytest.mark.parametrize("handler", [contracts.contract_archive, contracts.contract_unarchive])
def test_archive_routes_reject_cross_organization_before_query(monkeypatch, handler):
    organization = uuid4()
    fake_session = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(contracts, "create_session", lambda: fake_session)
    monkeypatch.setattr(contracts, "get_organization", lambda session, slug: SimpleNamespace(id=organization))
    with pytest.raises(HTTPException) as exc:
        handler(_request(organization_id=uuid4()), "other-org", str(uuid4()))
    assert exc.value.status_code == 404


def test_static_deletion_routes_precede_dynamic_contract_route():
    paths = [route.path for route in contracts.router.routes]
    dynamic = paths.index("/api/contracts/{contract_id}")
    assert paths.index("/api/contracts/deletion/queue") < dynamic
    assert paths.index("/api/contracts/capabilities/deletion") < dynamic


def test_deletion_queue_denied_when_feature_disabled(monkeypatch):
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", False)
    with pytest.raises(HTTPException) as exc:
        contracts.contract_deletion_queue(_request(), "test-org", offset=0)
    assert exc.value.status_code == 403


def test_deletion_queue_rejects_cross_organization_before_database_query(monkeypatch):
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    fake_session = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(contracts, "create_session", lambda: fake_session)
    monkeypatch.setattr(contracts, "get_organization", lambda session, slug: SimpleNamespace(id=uuid4()))
    with pytest.raises(HTTPException) as exc:
        contracts.contract_deletion_queue(_request(), "another-org", offset=0)
    assert exc.value.status_code == 404


@pytest.mark.parametrize(("expected", "target", "event"), [
    ("active", "pending_deletion", "contract.deletion_requested"),
    ("pending_deletion", "active", "contract.deletion_cancelled"),
    ("pending_deletion", "deleted", "contract.deletion_confirmed"),
    ("deleted", "active", "contract.restored"),
])
def test_deletion_transition_is_audited_and_reversible(monkeypatch, expected, target, event):
    organization = uuid4()
    contract_id = uuid4()
    row = SimpleNamespace(is_archived=False, lifecycle_state=expected,
                          deletion_owner="prior-owner", deleted_at=object())
    query_result = SimpleNamespace(scalar_one_or_none=lambda: row)
    committed = []
    session = SimpleNamespace(execute=lambda query: query_result,
                              commit=lambda: committed.append(True),
                              rollback=lambda: None, close=lambda: None)
    audit = []
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    monkeypatch.setattr(contracts, "create_session", lambda: session)
    monkeypatch.setattr(contracts, "get_organization", lambda db, slug: SimpleNamespace(id=organization))
    monkeypatch.setattr(contracts, "_scope_denies", lambda db, org, cid: False)
    monkeypatch.setattr(contracts, "_record_account_activity",
                        lambda db, req, name, cid, context: audit.append((name, context)))
    receipt = contracts._deletion_transition(
        _request(organization_id=organization), "test-org", str(contract_id),
        expected=expected, target=target)
    assert receipt == {"contract_id": str(contract_id), "lifecycle_state": target}
    assert row.lifecycle_state == target
    assert audit == [(event, {"previous_state": expected, "new_state": target})]
    assert committed == [True]
    if target == "active":
        assert row.deletion_owner is None
        assert row.deleted_at is None
    elif target == "deleted":
        assert row.deletion_owner is not None
        assert row.deleted_at is not None
    else:
        assert row.deleted_at is None


def test_archived_contract_cannot_enter_deletion_queue(monkeypatch):
    organization = uuid4()
    row = SimpleNamespace(is_archived=True, lifecycle_state="active")
    session = SimpleNamespace(execute=lambda query: SimpleNamespace(scalar_one_or_none=lambda: row),
                              commit=lambda: pytest.fail("Archived contract was committed"),
                              rollback=lambda: None, close=lambda: None)
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    monkeypatch.setattr(contracts, "create_session", lambda: session)
    monkeypatch.setattr(contracts, "get_organization", lambda db, slug: SimpleNamespace(id=organization))
    monkeypatch.setattr(contracts, "_scope_denies", lambda db, org, cid: False)
    with pytest.raises(HTTPException) as exc:
        contracts._deletion_transition(_request(organization_id=organization),
                                       "test-org", str(uuid4()), expected="active",
                                       target="pending_deletion")
    assert exc.value.status_code == 409


@pytest.mark.parametrize(("count", "offset", "expected_more", "expected_next"), [
    (0, 0, False, None),
    (2, 0, False, None),
    (100, 0, False, None),
    (101, 0, True, 100),
    (1, 100, False, None),
])
def test_deletion_queue_pagination_contract(monkeypatch, count, offset, expected_more, expected_next):
    organization = uuid4()
    rows = [SimpleNamespace(id=uuid4(), contract_number=str(i), register_number=None, short_description=None, supplier=None,
                            lifecycle_state="deleted", deletion_owner=None, deleted_at=None)
            for i in range(count)]
    query_result = SimpleNamespace(all=lambda: rows)
    session = SimpleNamespace(scalars=lambda query: query_result, close=lambda: None)
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    monkeypatch.setattr(contracts, "create_session", lambda: session)
    monkeypatch.setattr(contracts, "get_organization", lambda db, slug: SimpleNamespace(id=organization))
    monkeypatch.setattr(contracts, "current_scope_context",
                        lambda: SimpleNamespace(hospital_id=None, department_id=None))
    monkeypatch.setattr(contracts, "scoped_contract_ids", lambda *args: None)
    result = contracts.contract_deletion_queue(
        _request(organization_id=organization), "test-org", offset=offset)
    assert len(result["items"]) == min(count, 100)
    assert result["has_more"] is expected_more
    assert result["next_offset"] == expected_next


@pytest.mark.parametrize(("expected", "target"), [
    ("active", "pending_deletion"),
    ("pending_deletion", "active"),
    ("pending_deletion", "deleted"),
    ("deleted", "active"),
])
def test_deletion_transition_rejects_missing_or_wrong_state(monkeypatch, expected, target):
    organization = uuid4()
    rolled_back = []
    session = SimpleNamespace(
        execute=lambda query: SimpleNamespace(scalar_one_or_none=lambda: None),
        commit=lambda: pytest.fail("Invalid transition committed"),
        rollback=lambda: rolled_back.append(True), close=lambda: None,
    )
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    monkeypatch.setattr(contracts, "create_session", lambda: session)
    monkeypatch.setattr(contracts, "get_organization", lambda db, slug: SimpleNamespace(id=organization))
    monkeypatch.setattr(contracts, "_scope_denies", lambda db, org, cid: False)
    with pytest.raises(HTTPException) as exc:
        contracts._deletion_transition(_request(organization_id=organization),
                                       "test-org", str(uuid4()), expected=expected, target=target)
    assert exc.value.status_code == 404
    assert rolled_back == [True]


def test_contract_detail_rejects_cross_organization_before_read(monkeypatch):
    fake_session = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(contracts, "create_session", lambda: fake_session)
    monkeypatch.setattr(contracts, "get_organization",
                        lambda session, slug: SimpleNamespace(id=uuid4()))
    with pytest.raises(HTTPException) as exc:
        contracts.contract_detail(_request(), "another-org", str(uuid4()))
    assert exc.value.status_code == 404


@pytest.mark.parametrize("handler,payload", [
    (contracts.contract_fact_review, SimpleNamespace()),
    (contracts.contract_review_start, SimpleNamespace()),
    (contracts.contract_review_complete, SimpleNamespace()),
    (contracts.contract_override, SimpleNamespace()),
])
def test_contract_write_routes_reject_cross_org_before_contract_query(monkeypatch, handler, payload):
    session = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(contracts, "create_session", lambda: session)
    monkeypatch.setattr(contracts, "get_organization",
                        lambda db, slug: SimpleNamespace(id=uuid4()))
    with pytest.raises(HTTPException) as exc:
        handler(_request(), "other-org", str(uuid4()), payload)
    assert exc.value.status_code == 404


def test_contract_document_content_rejects_cross_org_before_storage(monkeypatch):
    session = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(contracts, "create_session", lambda: session)
    monkeypatch.setattr(contracts, "get_organization",
                        lambda db, slug: SimpleNamespace(id=uuid4()))
    with pytest.raises(HTTPException) as exc:
        contracts.contract_document_content(_request(), "other-org", str(uuid4()), str(uuid4()))
    assert exc.value.status_code == 404
