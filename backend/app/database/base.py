"""SQLAlchemy 2.x Declarative-Basis fuer die Medflux-Persistenz (STEP 10).

Gemeinsame `MetaData` mit deterministischer Naming-Convention (stabile
Constraint-/Index-Namen fuer Alembic) und `eager_defaults=True`, damit
DB-server-gera erzeugte Werte (uuidv7(), now()) beim INSERT per RETURNING
sofort in Python verfuegbar sind.

Konvention (STEP 10A §2A): PostgreSQL `UUID`-Typ; neue persistierte Entity-IDs
werden **database-side** per Postgres-nativem `uuidv7()` erzeugt. In Python
werden sie deshalb als `server_default` beschrieben und nach dem INSERT
zurueckgelesen – es wird KEINE dritte UUID-Bibliothek verwendet.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Basisklasse aller Medflux-DB-ORM-Modelle."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Server-Defaults (uuidv7(), now()) sofort per RETURNING abholen.
    __mapper_args__ = {"eager_defaults": True}
