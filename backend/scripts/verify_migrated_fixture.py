"""DRIFT-1 opt-in migration fidelity gate for an EMPTY, dedicated test database.

Run from backend/ after independently provisioning a throwaway database:
    DRIFT1_DISPOSABLE_DATABASE_URL=postgresql+psycopg://...@127.0.0.1:55432/medflux_drift1_<random> python scripts/verify_migrated_fixture.py

This script never creates/drops databases or touches the normal pytest fixture.
It refuses any non-local/non-55432/non-drift1 database, nonempty schema,
or database with existing migration history. It does not alter public on the
regular MedFlux database. Only the explicitly supplied disposable DB is changed.
"""
from __future__ import annotations

import os
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.database import models  # noqa: F401
from app.database.base import Base


def validate_target(raw: str) -> None:
    if not raw:
        raise RuntimeError("DRIFT1_DISPOSABLE_DATABASE_URL is required")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("Only PostgreSQL disposable databases are allowed")
    if url.host not in {"127.0.0.1", "localhost", "::1"} or url.port != 55432:
        raise RuntimeError("Only local isolated PostgreSQL port 55432 is allowed")
    if not url.database or not url.database.startswith("medflux_drift1_") or len(url.database) <= len("medflux_drift1_") or "/" in url.database or "\\" in url.database:
        raise RuntimeError("Database name must start with medflux_drift1_")
    if url.database in {"medflux", "postgres", "template0", "template1"}:
        raise RuntimeError("Protected database")
    if url.query:
        raise RuntimeError("Connection options/host overrides are forbidden")


def main() -> int:
    raw = os.environ.get("DRIFT1_DISPOSABLE_DATABASE_URL", "")
    validate_target(raw)
    engine = create_engine(raw, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            db_name, port = conn.execute(text(
                "SELECT current_database(), inet_server_port()"
            )).one()
            if db_name != make_url(raw).database or port != 55432:
                raise RuntimeError("Connected target differs from approved disposable database")
            if conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_tables "
                "WHERE schemaname NOT IN ('pg_catalog', 'information_schema') "
                "AND tablename NOT LIKE 'pg_%')"
            )).scalar():
                raise RuntimeError("Disposable database is not empty; refusing migrations")
            # Prevent unexpected pre-existing user objects, not just tables.
            if conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace "
                "WHERE nspname NOT IN ('public','information_schema','pg_catalog') "
                "AND nspname NOT LIKE 'pg_%')"
            )).scalar():
                raise RuntimeError("Unexpected schema exists in disposable database")
    finally:
        engine.dispose()

    # Alembic env.py reads this in-process settings object.
    settings.database_url = raw
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    verify_engine = create_engine(raw)
    try:
        inspector = inspect(verify_engine)
        actual = set(inspector.get_table_names(schema="public"))
        expected = set(Base.metadata.tables)
        missing = expected - actual
        if missing:
            raise RuntimeError(f"Migration-built schema missing ORM tables: {sorted(missing)}")
        with verify_engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
            role_column = conn.execute(text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='contract_department' "
                "AND column_name='relation_role'"
            )).scalar_one()
            if role_column != 1:
                raise RuntimeError("A2 role column missing from migrated database")
            indexes = {index["name"] for index in inspector.get_indexes("contract_department", schema="public")}
            if "uq_contract_department_one_responsible" not in indexes:
                raise RuntimeError("A2 partial unique index missing")
            print(f"DRIFT1 MIGRATED FIXTURE PASS: db={make_url(raw).database}, "
                  f"revision={version}, tables={len(actual)}, role_column=present, "
                  "responsible_index=present")
    finally:
        verify_engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"DRIFT1 FAIL CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(2)
