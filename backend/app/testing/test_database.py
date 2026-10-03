"""Fail-closed access to MedFlux's dedicated local test PostgreSQL cluster.

The Windows developer test path is pinned to the existing WSL cluster and
database. It deliberately ignores DATABASE_URL and backend/.env. GitHub Actions
uses its own ephemeral PostgreSQL service and is allowed only under the
explicit CI identity below.
"""

from __future__ import annotations

import getpass
import ipaddress
import os
import re
import socket
import subprocess
import sys
import time
from typing import Callable

import psycopg
from sqlalchemy.engine import URL, make_url

TEST_HOST = "127.0.0.1"
TEST_PORT = 55432
TEST_DATABASE = "medflux_trial_20261001"
TEST_USER = "sr415_flow"
TEST_CLUSTER_SYSTEM_IDENTIFIER = "7689962266201178762"
WSL_DISTRO = "Ubuntu"
CLUSTER_DATA = "/opt/medflux-test-pg/data"
PG_CTL = "/usr/lib/postgresql/18/bin/pg_ctl"
POSTGRES = "/usr/lib/postgresql/18/bin/postgres"
PG_CONTROLDATA = "/usr/lib/postgresql/18/bin/pg_controldata"
CI_IDENTITY = ("127.0.0.1", 5432, "medflux", "medflux")


class DatabaseSafetyError(RuntimeError):
    """Raised whenever the configured test database cannot be proven safe."""


def _is_github_actions() -> bool:
    return (
        os.name != "nt"
        and os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
        and os.environ.get("CI", "").lower() == "true"
        and bool(os.environ.get("GITHUB_RUN_ID"))
    )


def validate_test_database_url(database_url: str, *, ci: bool | None = None) -> URL:
    """Validate the URL without opening a socket or contacting PostgreSQL."""
    try:
        url = make_url(database_url)
    except Exception as exc:
        raise DatabaseSafetyError("Invalid test database URL") from exc
    if url.drivername != "postgresql+psycopg":
        raise DatabaseSafetyError("Test database must use the psycopg PostgreSQL driver")

    in_ci = _is_github_actions() if ci is None else ci
    expected = CI_IDENTITY if in_ci else (TEST_HOST, TEST_PORT, TEST_DATABASE, TEST_USER)
    actual = (url.host, url.port, url.database, url.username)
    if actual != expected:
        label = "approved ephemeral CI database" if in_ci else "approved isolated MedFlux test database"
        raise DatabaseSafetyError(f"Refusing database: URL does not identify the {label}")
    if not in_ci and url.host not in {"127.0.0.1", "localhost"}:
        raise DatabaseSafetyError("Test database must be loopback-only")
    return url


def resolve_test_database_url() -> str:
    """Resolve only explicit test credentials, never DATABASE_URL or .env."""
    if _is_github_actions():
        raw = os.environ.get("DATABASE_URL", "")
        validate_test_database_url(raw, ci=True)
        return raw

    raw = os.environ.get("MEDFLUX_TEST_DATABASE_URL") or os.environ.get("MEDFLUX_TRIAL_DSN")
    if raw:
        validate_test_database_url(raw, ci=False)
        return raw
    if os.name != "nt":
        raise DatabaseSafetyError("Set MEDFLUX_TEST_DATABASE_URL for the isolated local test database")
    password = getpass.getpass("MedFlux isolated test DB password (used for this process only): ")
    if not password:
        raise DatabaseSafetyError("No test database credential supplied")
    return URL.create(
        "postgresql+psycopg", username=TEST_USER, password=password,
        host=TEST_HOST, port=TEST_PORT, database=TEST_DATABASE,
    ).render_as_string(hide_password=False)


def _wsl(*args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["wsl.exe", "-d", WSL_DISTRO, "-u", "root", "--", *args],
        capture_output=True, text=True, timeout=timeout, check=False,
    )


def _run_as_postgres(*args: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return _wsl("runuser", "-u", "postgres", "--", *args, timeout=timeout)


def cluster_status() -> bool:
    """Return status of only the approved cluster; fail on ambiguous errors."""
    if os.name != "nt":
        raise DatabaseSafetyError("Automatic WSL cluster management is supported on Windows only")
    version = _wsl("cat", f"{CLUSTER_DATA}/PG_VERSION")
    if version.returncode != 0 or version.stdout.strip() != "18":
        raise DatabaseSafetyError("Approved WSL test cluster is missing or has an unexpected PostgreSQL version")
    control = _run_as_postgres(PG_CONTROLDATA, CLUSTER_DATA)
    system_identifier = re.search(r"Database system identifier:\s*(\d+)", control.stdout)
    if control.returncode != 0 or not system_identifier or system_identifier.group(1) != TEST_CLUSTER_SYSTEM_IDENTIFIER:
        raise DatabaseSafetyError("WSL data directory is not the approved MedFlux test cluster")
    port = _run_as_postgres(POSTGRES, "-D", CLUSTER_DATA, "-C", "port")
    addresses = _run_as_postgres(POSTGRES, "-D", CLUSTER_DATA, "-C", "listen_addresses")
    if port.returncode != 0 or port.stdout.strip() != str(TEST_PORT):
        raise DatabaseSafetyError("Approved cluster configuration does not use port 55432")
    if addresses.returncode != 0 or addresses.stdout.strip() != TEST_HOST:
        raise DatabaseSafetyError("Approved cluster configuration is not bound only to 127.0.0.1")
    status = _run_as_postgres(PG_CTL, "-D", CLUSTER_DATA, "status")
    if status.returncode == 0:
        return True
    if "no server running" in (status.stdout + status.stderr).lower():
        return False
    raise DatabaseSafetyError("Could not determine the approved test cluster state")


def ensure_cluster_running() -> None:
    """Start only the approved cluster, and only after validating its config."""
    if cluster_status():
        return
    # Refuse to start if some unrelated listener already occupies the test port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        if probe.connect_ex((TEST_HOST, TEST_PORT)) == 0:
            raise DatabaseSafetyError("Port 55432 is occupied while the approved cluster reports stopped")
    start = _run_as_postgres(PG_CTL, "-D", CLUSTER_DATA, "-l", "/tmp/medflux-test-pg-startup.log", "start", timeout=45)
    if start.returncode != 0:
        raise DatabaseSafetyError("Could not start the approved WSL test cluster")
    for _ in range(20):
        if cluster_status():
            return
        time.sleep(0.5)
    raise DatabaseSafetyError("The approved WSL test cluster did not reach running state")


def verify_database_identity(
    database_url: str,
    *,
    connector: Callable[..., object] = psycopg.connect,
    ci: bool | None = None,
) -> None:
    """Check actual server identity. Invalid URLs fail before connector use."""
    url = validate_test_database_url(database_url, ci=ci)
    # psycopg.connect accepts PostgreSQL libpq conninfo, not SQLAlchemy's
    # ``postgresql+psycopg`` dialect URL prefix.
    conninfo = url.set(drivername="postgresql").render_as_string(hide_password=False)
    try:
        connection = connector(conninfo, connect_timeout=4)
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), current_user, inet_server_port(), "
                    "inet_server_addr()::text, system_identifier::text FROM pg_control_system()"
                )
                database, user, port, address, system_identifier = cursor.fetchone()
    except DatabaseSafetyError:
        raise
    except Exception as exc:
        # Exception text from a database driver may include connection details;
        # expose only the class to keep usernames/passwords out of logs.
        raise DatabaseSafetyError(
            f"Could not verify PostgreSQL server identity ({type(exc).__name__})"
        ) from exc
    expected = CI_IDENTITY if (_is_github_actions() if ci is None else ci) else (TEST_HOST, TEST_PORT, TEST_DATABASE, TEST_USER)
    expected_host, expected_port, expected_db, expected_user = expected
    if (database, user, port) != (expected_db, expected_user, expected_port):
        raise DatabaseSafetyError("Connected PostgreSQL identity differs from the approved test identity")
    if expected_port != 5432 and system_identifier != TEST_CLUSTER_SYSTEM_IDENTIFIER:
        raise DatabaseSafetyError("Connected PostgreSQL cluster is not the approved MedFlux test cluster")
    if expected_port != 5432 and ipaddress.ip_interface(address).ip.compressed != expected_host:
        raise DatabaseSafetyError("Connected test database is not bound to the approved loopback address")


def prepare_test_database() -> str:
    """Resolve, validate, start-if-needed, and verify the test database."""
    database_url = resolve_test_database_url()
    validate_test_database_url(database_url)
    if not _is_github_actions():
        ensure_cluster_running()
    verify_database_identity(database_url)
    return database_url


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    action = args[0] if args else "prepare"
    try:
        if action == "status":
            print("Test cluster running." if cluster_status() else "Test cluster stopped.")
        elif action in {"start", "prepare"}:
            url = prepare_test_database()
            del url
            print("Approved MedFlux test database is ready and identity-verified.")
        elif action == "verify":
            verify_database_identity(resolve_test_database_url())
            print("Approved MedFlux test database identity verified.")
        else:
            raise DatabaseSafetyError("Use status, start, verify, or prepare")
    except DatabaseSafetyError as exc:
        print(f"Test database safety check failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
