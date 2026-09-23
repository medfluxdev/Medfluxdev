"""contract search: pg_trgm + fts vector + indexes

Revision ID: a3f9c1127305
Revises: 81aa19e5d946
Create Date: 2026-08-31 15:00:00

STEP 13 – Production-Grade Contract Portfolio / Search / Filter.

Legt die deterministische, PostgreSQL-eigene Suchgrundlage fuer Vertrags-Metadaten:
- pg_trgm-Erweiterung (vertrauenswuerdig; DB-Owner kann sie ohne Superuser anlegen).
- Stored generated `search_vector` (tsvector) auf `contract` – abgeleitet NUR aus
  akzeptierten/aktuellen Projektions-Metadaten (contract_number/supplier/status).
  Identifikatoren (contract_number) nutzen die 'simple'-TS-Config (keine
  linguistische Stemmung auf Kennungen – siehe STEP 13 Checkpoint §5/§4).
- Fokussierte btree-/gin-Indexe fuer belegte STEP-13-Querypfade (siehe Checkpoint
  §29/§35). Keine alten Migrationen geaendert.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a3f9c1127305'
down_revision = '81aa19e5d946'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Vertrauenswuerdige Erweiterung; DB-Owner (medflux) kann sie ohne Superuser anlegen.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Stored generated tsvector: deterministisch synchron mit Current-State.
    op.add_column(
        "contract",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "(setweight(to_tsvector('simple', coalesce(contract_number, '')), 'A') || ' ' || "
                "setweight(to_tsvector('german', coalesce(supplier, '')), 'B') || ' ' || "
                "setweight(to_tsvector('simple', coalesce(status, '')), 'C'))",
                persisted=True,
            ),
            nullable=False,
        ),
    )

    # Strukturierte Query-Pfade (org-gebunden).
    op.create_index("ix_contract_org_lifecycle", "contract", ["organization_id", "lifecycle_state"])
    op.create_index("ix_contract_org_status", "contract", ["organization_id", "status"])
    op.create_index("ix_contract_org_end_date", "contract", ["organization_id", "end_date"])

    # Volltext / exakt / praefix / fuzzy.
    op.create_index(
        "ix_contract_search_vector", "contract", ["search_vector"], postgresql_using="gin"
    )
    op.create_index(
        "ix_contract_supplier_trgm",
        "contract",
        ["supplier"],
        postgresql_using="gin",
        postgresql_ops={"supplier": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_contract_number_trgm",
        "contract",
        ["contract_number"],
        postgresql_using="gin",
        postgresql_ops={"contract_number": "gin_trgm_ops"},
    )

    # Anlagen-/Geraete-Suche (trigram ueber alle nutzbaren Geratefelder eines Vertrags).
    op.execute(
        "CREATE INDEX ix_contract_equipment_trgm ON contract_equipment "
        "USING gin ("
        "(coalesce(device_name, '') || ' ' || coalesce(system_name, '') || ' ' || "
        " coalesce(model, '') || ' ' || coalesce(manufacturer, '') || ' ' || "
        " coalesce(serial_number, '')) gin_trgm_ops"
        ")"
    )

    # Warn-Subquery-Filter (Isolation + active) fuer STEP-13-Filter.
    op.create_index(
        "ix_contract_warning_org_active",
        "contract_warning",
        ["organization_id", "contract_id", "active"],
    )


def downgrade() -> None:
    op.drop_index("ix_contract_warning_org_active", table_name="contract_warning")
    op.execute("DROP INDEX IF EXISTS ix_contract_equipment_trgm")
    op.drop_index("ix_contract_number_trgm", table_name="contract")
    op.drop_index("ix_contract_supplier_trgm", table_name="contract")
    op.drop_index("ix_contract_search_vector", table_name="contract")
    op.drop_index("ix_contract_org_end_date", table_name="contract")
    op.drop_index("ix_contract_org_status", table_name="contract")
    op.drop_index("ix_contract_org_lifecycle", table_name="contract")
    op.drop_column("contract", "search_vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
