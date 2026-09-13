"""Safety regressions for the development-only demo workspace."""

import pytest

from app.core.config import settings
from app.demo.workspace import set_workspace_enabled, workspace_enabled


class _ExplodingSession:
    def get(self, *args, **kwargs):
        raise AssertionError("production demo guard must not touch workspace state")


def test_demo_workspace_is_forced_off_in_production(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    assert workspace_enabled(_ExplodingSession()) is False


def test_demo_workspace_cannot_be_enabled_in_pilot(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "pilot")
    with pytest.raises(RuntimeError, match="Entwicklung/Test"):
        set_workspace_enabled(_ExplodingSession(), enabled=True)
