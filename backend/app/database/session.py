"""Engine-/Session-Handling fuer die Medflux-Persistenz (PostgreSQL, synchron).

Gegenueber einem SQLite-Umstieg: PostgreSQL ist die Ziel-DB. Die Engine wird
LAZY erzeugt (kein Verbindungsaufbau beim Import), damit bestehende
Logik-/Unit-Tests ohne DB weiterlaufen.

Transaktions-Disziplin (STEP 10A §3): grosse Objekte nicht in einer lang
offenen DB-Transaktion verarbeiten. `session_scope()` liefert kurze
Transaktionen (commit auf Erfolg, rollback bei Fehler). Laenger laufende
pipelines erzeugen zuerst eine run/status-Zeile (commit) und persistieren das
Ergebnis danach in einer neuen kurzen Transaktion.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Lazy erzeugte Engine (PostgreSQL via psycopg v3)."""
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker:
    """Lazy erzeugte Session-Factory (expire_on_commit=False fuer Projektions-Arbeit)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), expire_on_commit=False, future=True
        )
    return _session_factory


def create_session() -> Session:
    """Erzeugt eine neue, unabhaengige Session."""
    return get_session_factory()()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Kurze Transaktion: commit bei Erfolg, rollback bei Fehler."""
    session = create_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_for_tests() -> None:
    """Loescht gecachte Engine/Factories (nur fuer Test-Isolation)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
