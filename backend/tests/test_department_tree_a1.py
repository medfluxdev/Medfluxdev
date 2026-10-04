"""Focused safety tests for the additive department hierarchy validator."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.organization_structure import _validate_department_parent
from app.database.models.organization_structure import Department


class FakeSession:
    def __init__(self, departments):
        self.departments = {d.id: d for d in departments}

    def get(self, model, key):
        assert model is Department
        return self.departments.get(key)


def dept(org, hospital, *, parent=None):
    return SimpleNamespace(id=uuid4(), organization_id=org, hospital_id=hospital, parent_id=parent)


def check(session, org, hospital, current, parent):
    return _validate_department_parent(
        session, organization_id=org, hospital_id=hospital,
        department_id=current, parent_id=parent,
    )


def test_root_and_valid_nested_parent():
    org, hospital = uuid4(), uuid4()
    root = dept(org, hospital)
    child = dept(org, hospital, parent=root.id)
    session = FakeSession([root, child])
    assert check(session, org, hospital, None, None) is None
    assert check(session, org, hospital, None, child.id) is None


@pytest.mark.parametrize("other_scope", ["organization", "hospital"])
def test_cross_scope_parent_rejected(other_scope):
    org, hospital = uuid4(), uuid4()
    other = dept(uuid4() if other_scope == "organization" else org,
                 uuid4() if other_scope == "hospital" else hospital)
    with pytest.raises(HTTPException) as exc:
        check(FakeSession([other]), org, hospital, None, other.id)
    assert exc.value.status_code == 422


def test_missing_parent_rejected():
    with pytest.raises(HTTPException) as exc:
        check(FakeSession([]), uuid4(), uuid4(), None, uuid4())
    assert exc.value.status_code == 422


def test_self_parent_rejected():
    org, hospital = uuid4(), uuid4()
    node = dept(org, hospital)
    with pytest.raises(HTTPException) as exc:
        check(FakeSession([node]), org, hospital, node.id, node.id)
    assert exc.value.status_code == 422


def test_indirect_cycle_rejected():
    org, hospital = uuid4(), uuid4()
    root = dept(org, hospital)
    child = dept(org, hospital, parent=root.id)
    grandchild = dept(org, hospital, parent=child.id)
    with pytest.raises(HTTPException) as exc:
        check(FakeSession([root, child, grandchild]), org, hospital, root.id, grandchild.id)
    assert exc.value.status_code == 422


def test_preexisting_cycle_rejected():
    org, hospital = uuid4(), uuid4()
    a = dept(org, hospital)
    b = dept(org, hospital, parent=a.id)
    a.parent_id = b.id
    with pytest.raises(HTTPException) as exc:
        check(FakeSession([a, b]), org, hospital, None, a.id)
    assert exc.value.status_code == 422
