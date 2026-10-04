from __future__ import annotations

import uuid

import pytest

from app.auth.service import Actor, require_role


def _actor(*, role: str, is_developer: bool) -> Actor:
    return Actor(
        account_id=uuid.uuid4(),
        login_name="developer@medflux.local",
        display_name="Medflux Developer",
        organization_id=uuid.uuid4(),
        organization_slug="test-organization",
        role=role,
        is_developer=is_developer,
    )


def test_developer_bypasses_organization_role_restrictions():
    actor = _actor(role="viewer", is_developer=True)
    require_role(actor, "admin")
    require_role(actor, "contract_manager")
    require_role(actor, "reviewer")


def test_non_developer_still_requires_an_allowed_role():
    actor = _actor(role="viewer", is_developer=False)
    with pytest.raises(PermissionError):
        require_role(actor, "admin")
