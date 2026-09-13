from pathlib import Path


def test_organization_structure_uses_route_level_authentication():
    source = Path("app/api/routes/organization_structure.py").read_text(encoding="utf-8")
    assert "current_actor(request, organization_slug)" in source
    assert 'getattr(request.state, "actor", None)' not in source


def test_activity_uses_route_level_authentication():
    source = Path("app/api/routes/activity.py").read_text(encoding="utf-8")
    assert "current_actor(request, organization_slug)" in source
    assert 'getattr(request.state, "actor", None)' not in source
