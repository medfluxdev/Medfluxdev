"""Opt-in ORM smoke test on an independently migrated disposable database."""
import os

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url


def approved_url(raw):
    url = make_url(raw)
    if not (
        url.get_backend_name() == "postgresql"
        and url.host in ("127.0.0.1", "localhost", "::1")
        and url.port == 55432
        and url.database
        and url.database.startswith("medflux_drift1_")
        and len(url.database) > len("medflux_drift1_")
        and "/" not in url.database
        and not url.query
    ):
        raise ValueError("Requires explicit isolated disposable database")
    return raw


@pytest.mark.skipif(not os.environ.get("DRIFT1_MIGRATED_TEST_DATABASE_URL"), reason="Opt-in only")
def test_orm_selects_on_real_migrations():
    from app.database import models  # noqa: F401
    from app.database.base import Base

    raw = approved_url(os.environ["DRIFT1_MIGRATED_TEST_DATABASE_URL"])
    engine = create_engine(raw, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            actual_name, port = conn.execute(text("SELECT current_database(), inet_server_port()")).one()
            assert (actual_name, port) == (make_url(raw).database, 55432)
            assert conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == "b3c5d7e90928"
            assert set(Base.metadata.tables) <= set(inspect(conn).get_table_names(schema="public"))
            assert len(Base.registry.mappers) == 44, "Mapped entity registration changed; review expected count"
            for mapper in sorted(Base.registry.mappers, key=lambda m: m.local_table.name):
                conn.execute(select(mapper.class_).limit(0))
    finally:
        engine.dispose()


@pytest.mark.parametrize("raw", [
    "postgresql+psycopg://u@127.0.0.1:5432/medflux_drift1_test",
    "postgresql+psycopg://u@127.0.0.1:55432/medflux",
    "postgresql+psycopg://u@remote:55432/medflux_drift1_test",
    "postgresql+psycopg://u@127.0.0.1:55432/medflux_drift1_",
    "postgresql+psycopg://u@127.0.0.1:55432/medflux_drift1_test?options=override",
])
def test_reject_unsafe_urls(raw):
    with pytest.raises(ValueError):
        approved_url(raw)
