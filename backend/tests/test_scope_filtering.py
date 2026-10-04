from __future__ import annotations

import uuid

from app.database.scope_queries import intersect_ids


def test_intersect_ids_keeps_scope_when_workspace_disabled():
    scope = {uuid.uuid4(), uuid.uuid4()}
    assert intersect_ids(None, scope) == scope


def test_intersect_ids_keeps_workspace_when_scope_is_global():
    workspace = {uuid.uuid4(), uuid.uuid4()}
    assert intersect_ids(workspace, None) == workspace


def test_intersect_ids_requires_both_workspace_and_scope():
    shared = uuid.uuid4()
    workspace_only = uuid.uuid4()
    scope_only = uuid.uuid4()
    assert intersect_ids({shared, workspace_only}, {shared, scope_only}) == {shared}


def test_intersect_ids_global_global_is_unfiltered():
    assert intersect_ids(None, None) is None
