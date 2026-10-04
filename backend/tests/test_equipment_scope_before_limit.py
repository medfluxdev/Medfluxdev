"""Equipment route scope and pre-limit query regression source."""
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import equipment as routes
from app.database.models import Equipment
from app.equipment.service import list_equipment


@pytest.mark.parametrize("auth_enabled,actor_kind,denied", [
    (True, "missing", True),
    (True, "different", True),
    (False, "different", True),
    (False, "missing", False),
])
def test_equipment_list_actor_guard(monkeypatch, auth_enabled, actor_kind, denied):
    org_id = uuid4()
    session = MagicMock()
    monkeypatch.setattr(routes, "settings", SimpleNamespace(auth_enabled=auth_enabled))
    monkeypatch.setattr(routes, "create_session", lambda: session)
    monkeypatch.setattr(routes, "get_organization", lambda *_: SimpleNamespace(id=org_id))
    monkeypatch.setattr(routes, "current_scope_context", lambda: SimpleNamespace(hospital_id=None, department_id=None))
    called = []
    monkeypatch.setattr(routes, "list_equipment", lambda *_args, **kwargs: called.append(kwargs) or [])
    actor = None if actor_kind == "missing" else SimpleNamespace(organization_id=uuid4())
    request = SimpleNamespace(state=SimpleNamespace(actor=actor))
    if denied:
        with pytest.raises(HTTPException) as exc:
            routes.equipment_list(request, "clinic", q=None, limit=10)
        assert exc.value.status_code == 404
        assert called == []
    else:
        assert routes.equipment_list(request, "clinic", q=None, limit=10) == []
        assert called[0]["organization_id"] == org_id
    session.close.assert_called_once()


@pytest.mark.parametrize("scope_field", ["hospital_id", "department_id"])
def test_equipment_scope_is_in_sql_before_limit(scope_field):
    session = MagicMock()
    org_id, scope_id = uuid4(), uuid4()
    session.execute.return_value = []
    kwargs = {scope_field: scope_id}
    assert list_equipment(session, organization_id=org_id, limit=10, **kwargs) == []
    statement = session.execute.call_args.args[0]
    compiled = statement.compile()
    sql = str(compiled)
    assert "equipment." + scope_field in sql
    assert "LIMIT" in sql.upper()
    assert scope_id in compiled.params.values()
