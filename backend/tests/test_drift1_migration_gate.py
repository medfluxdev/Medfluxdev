"""DRIFT-1: target validation is independent of a live PostgreSQL server."""
import importlib.util
from pathlib import Path

import pytest

_GATE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_migrated_fixture.py"
_GATE_SPEC = importlib.util.spec_from_file_location("medflux_drift1_gate_test", _GATE_PATH)
assert _GATE_SPEC is not None and _GATE_SPEC.loader is not None
_GATE_MODULE = importlib.util.module_from_spec(_GATE_SPEC)
_GATE_SPEC.loader.exec_module(_GATE_MODULE)
validate_target = _GATE_MODULE.validate_target


@pytest.mark.parametrize("url", [
    "",
    "postgresql+psycopg://medflux@127.0.0.1:5432/medflux",
    "postgresql+psycopg://medflux@127.0.0.1:55432/medflux",
    "postgresql+psycopg://medflux@db.example.com:55432/medflux_drift1_safe",
    "sqlite:///medflux_drift1_safe",
    "postgresql+psycopg://medflux@127.0.0.1:55432/postgres",
    "postgresql+psycopg://medflux@127.0.0.1:55432/medflux_drift1_safe?options=-csearch_path=public",
])
def test_disposable_target_rejects_unsafe_url(url):
    with pytest.raises(RuntimeError):
        validate_target(url)


def test_disposable_target_accepts_explicit_isolated_url():
    validate_target("postgresql+psycopg://medflux@127.0.0.1:55432/medflux_drift1_fixture")


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://medflux@127.0.0.1:55432/medflux_drift1_",
    "postgresql+psycopg://medflux@127.0.0.1:55432/medflux_drift1_safe?port=5432",
    "postgresql+psycopg://medflux@127.0.0.1:55432/medflux_drift1_safe?service=other",
    "postgresql+psycopg://medflux@127.0.0.1:55432/medflux_drift1_../other",
])
def test_disposable_target_rejects_ambiguous_url(url):
    with pytest.raises(RuntimeError):
        validate_target(url)
