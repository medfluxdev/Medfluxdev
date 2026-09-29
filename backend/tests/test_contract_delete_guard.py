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


def test_deletion_disabled_by_default(monkeypatch):
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", False)
    with pytest.raises(HTTPException) as exc:
        contracts._require_explicit_delete_permission(_request())
    assert exc.value.status_code == 403


@pytest.mark.parametrize("role", ["viewer", "contract_manager", "", None])
def test_editing_roles_never_grant_deletion(monkeypatch, role):
    monkeypatch.setattr(contracts.settings, "auth_enabled", True)
    monkeypatch.setattr(contracts.settings, "contracts_allow_delete", True)
    with pytest.raises(HTTPException) as exc:
        contracts._require_explicit_delete_permission(_request(role=role))
    assert exc.value.status_code == 403


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
    assert result == {"can_delete": False, "can_restore": False, "requires_confirmation": True}


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
    ) == {"can_delete": True, "can_restore": True, "requires_confirmation": True}
    assert contracts.contract_deletion_capabilities(
        _request(role="contract_manager", organization_id=organization), "test-org"
    )["can_delete"] is False


@pytest.mark.parametrize("handler", [contracts.contract_archive, contracts.contract_unarchive])
def test_archive_routes_reject_cross_organization_before_query(monkeypatch, handler):
    organization = uuid4()
    fake_session = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(contracts, "create_session", lambda: fake_session)
    monkeypatch.setattr(contracts, "get_organization", lambda session, slug: SimpleNamespace(id=organization))
    with pytest.raises(HTTPException) as exc:
        handler(_request(organization_id=uuid4()), "other-org", str(uuid4()))
    assert exc.value.status_code == 404
