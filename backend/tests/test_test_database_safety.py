from __future__ import annotations

import pytest

import app.testing.test_database as test_database
from app.testing.test_database import (
    TEST_DATABASE,
    TEST_HOST,
    TEST_PORT,
    TEST_CLUSTER_SYSTEM_IDENTIFIER,
    TEST_USER,
    DatabaseSafetyError,
    validate_test_database_url,
    verify_database_identity,
)


def _url(*, host=TEST_HOST, port=TEST_PORT, database=TEST_DATABASE, user=TEST_USER):
    return f"postgresql+psycopg://{user}:not-a-real-secret@{host}:{port}/{database}"


def test_approved_local_database_url_is_accepted_without_connection():
    parsed = validate_test_database_url(_url(), ci=False)
    assert (parsed.host, parsed.port, parsed.database, parsed.username) == (
        TEST_HOST, TEST_PORT, TEST_DATABASE, TEST_USER
    )


@pytest.mark.parametrize(
    "url",
    [
        _url(port=5432),
        _url(database="medflux"),
        _url(user="postgres"),
        _url(host="localhost"),
        "postgresql://sr415_flow@127.0.0.1:55432/medflux_trial_20261001",
    ],
)
def test_unsafe_or_unapproved_urls_are_rejected(url):
    with pytest.raises(DatabaseSafetyError):
        validate_test_database_url(url, ci=False)


def test_5432_rejection_happens_before_any_connector_call():
    called = False

    def connector(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("connector must not run for an unsafe URL")

    with pytest.raises(DatabaseSafetyError):
        verify_database_identity(_url(port=5432), connector=connector, ci=False)
    assert called is False


def test_running_cluster_is_not_restarted(monkeypatch):
    calls = []
    monkeypatch.setattr(test_database, "cluster_status", lambda: True)
    monkeypatch.setattr(test_database, "_run_as_postgres", lambda *args, **kwargs: calls.append(args))
    test_database.ensure_cluster_running()
    assert calls == []


def test_stopped_cluster_start_targets_only_approved_data_directory(monkeypatch):
    states = iter((False, True))
    commands = []

    class _PortProbe:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, _timeout):
            pass

        def connect_ex(self, address):
            assert address == (TEST_HOST, TEST_PORT)
            return 1

    monkeypatch.setattr(test_database, "cluster_status", lambda: next(states))
    monkeypatch.setattr(test_database.socket, "socket", lambda *args, **kwargs: _PortProbe())
    monkeypatch.setattr(test_database.time, "sleep", lambda _seconds: None)

    def run_as_postgres(*args, **kwargs):
        commands.append(args)
        return test_database.subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(test_database, "_run_as_postgres", run_as_postgres)
    test_database.ensure_cluster_running()

    assert len(commands) == 1
    assert commands[0][:3] == (test_database.PG_CTL, "-D", test_database.CLUSTER_DATA)
    assert commands[0][-1] == "start"
    assert "systemctl" not in commands[0]


class _Cursor:
    def __init__(self, identity):
        self.identity = identity

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, _query):
        pass

    def fetchone(self):
        return self.identity


class _Connection:
    def __init__(self, identity):
        self.identity = identity

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return _Cursor(self.identity)


@pytest.mark.parametrize(
    "identity",
    [
        (TEST_DATABASE, TEST_USER, TEST_PORT, TEST_HOST, TEST_CLUSTER_SYSTEM_IDENTIFIER),
        ("medflux", TEST_USER, TEST_PORT, TEST_HOST, TEST_CLUSTER_SYSTEM_IDENTIFIER),
        (TEST_DATABASE, "postgres", TEST_PORT, TEST_HOST, TEST_CLUSTER_SYSTEM_IDENTIFIER),
        (TEST_DATABASE, TEST_USER, 5432, TEST_HOST, TEST_CLUSTER_SYSTEM_IDENTIFIER),
        (TEST_DATABASE, TEST_USER, TEST_PORT, "0.0.0.0", TEST_CLUSTER_SYSTEM_IDENTIFIER),
        (TEST_DATABASE, TEST_USER, TEST_PORT, TEST_HOST, "wrong-cluster"),
    ],
)
def test_live_identity_verification_accepts_only_the_expected_database(identity):
    def connector(*args, **kwargs):
        return _Connection(identity)

    if identity == (TEST_DATABASE, TEST_USER, TEST_PORT, TEST_HOST, TEST_CLUSTER_SYSTEM_IDENTIFIER):
        verify_database_identity(_url(), connector=connector, ci=False)
    else:
        with pytest.raises(DatabaseSafetyError):
            verify_database_identity(_url(), connector=connector, ci=False)
