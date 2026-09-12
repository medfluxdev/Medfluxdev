"""Test-Isolation: kein Test darf die Produkt-Datenbank beruehren.

Struktur (Root Cause PR-5 Defect 1):
- Viele Backend-Tests legten Organisationen/Vertraege direkt ueber
  `settings.database_url` an und COMMITTED diese – gegen dieselbe PostgreSQL
  wie der laufende Produkt-Server. Ergebnis: Benchmark-/UAT-Fixtures sammeln
  sich im Produkt-DB-Schema `public`.
- Dieses conftest stellt sicher, dass der GESAMTE pytest-Lauf gegen ein
  dediziertes, isoliertes PostgreSQL-SCHEMA `test` laeuft:
    * Schema `test` wird bei Session-Start dropped und neu angelegt.
    * `settings.database_url` wird auf `...?options=-csearch_path=test`
      umgestellt und die gecachte Engine zurueckgesetzt.
    * Alle Tabellen werden im Test-Schema per ORM-Metadata (create_all)
      angelegt – identischer Stand wie die Produktions-Migrationen, aber
      vollstaendig getrennt.
- Das Produktschema `public` bleibt unveraendert. "Demo/UAT"-Fixtures koennen
  nie mehr in der Produkt-DB landen.

Wenn PostgreSQL nicht erreichbar ist, laeuft die Suite wie bisher weiter
(Persistenz-Tests skippen selbst), das Produktschema bleibt unberuehrt.
"""

from __future__ import annotations

import logging
import os
import uuid
from urllib.parse import quote

import pytest
from sqlalchemy import create_engine, text

import app.core.config as config
from app.database import models as db_models  # noqa: F401,E402  (registriert alle Tabellen)
from app.database.base import Base

logger = logging.getLogger("medflux.tests")

TEST_SCHEMA = "medflux_test_" + uuid.uuid4().hex


def _schema_url(base_url: str) -> str:
    """Haengt die search_path-Option an die Basis-URL (Schema-Isolation)."""
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}options={quote('-csearch_path=' + TEST_SCHEMA + ',public')}"


def pytest_sessionstart(session) -> None:
    base_url = config.settings.database_url
    config.settings.database_url = _schema_url(base_url)
    from app.database.session import reset_engine_for_tests
    reset_engine_for_tests()
    if os.environ.get("MEDFLUX_UNIT_ONLY") == "1":
        config.settings.database_url = "postgresql+psycopg://invalid@127.0.0.1:1/disabled"
        return
    try:
        admin = create_engine(
            base_url,
            pool_pre_ping=True,
            isolation_level="AUTOCOMMIT",
        )
        with admin.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
        admin.dispose()

        # Alle weiteren Engines/Sessions der Tests laufen gegen das Test-Schema.
        config.settings.database_url = _schema_url(base_url)
        from app.database.session import reset_engine_for_tests

        reset_engine_for_tests()

        # Alle Tabellen im Test-Schema per ORM-Metadata anlegen (identisch zum
        # Migrationsstand der Produktion, aber vollstaendig getrennt).
        test_engine = create_engine(config.settings.database_url, pool_pre_ping=True)
        Base.metadata.create_all(test_engine)
        test_engine.dispose()
        logger.info("Test-Isolation aktiv: Schema '%s' frisch fuer pytest.", TEST_SCHEMA)
    except Exception as exc:
        raise pytest.UsageError("Test isolation unavailable; refusing database tests") from exc


def pytest_sessionfinish(session, exitstatus):
    if os.environ.get("MEDFLUX_UNIT_ONLY") == "1":
        return
    from app.database.session import reset_engine_for_tests
    reset_engine_for_tests()
    engine = create_engine(config.settings.database_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE'))
    finally:
        engine.dispose()
