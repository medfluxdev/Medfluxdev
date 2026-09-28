"""Read-only phase 2C nullability probe on independently migrated disposable DB.

No synthetic verdict is inferred from NULL. Data-writing fixture design remains
separate until its complete foreign-key setup has been reviewed.
"""
import os

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.test_drift1_migrated_integration import approved_url

FIELDS = ("identification_quality", "relationship_quality", "requires_review")


def classify_legacy_fields(values):
    """Preserve unknown legacy states rather than inventing AI conclusions."""
    return {field: ("unknown_legacy" if values[field] is None else "recorded")
            for field in FIELDS}


@pytest.mark.parametrize("values,expected", [
    (dict.fromkeys(FIELDS), dict.fromkeys(FIELDS, "unknown_legacy")),
    ({"identification_quality": "unknown", "relationship_quality": "ambiguous",
      "requires_review": True}, dict.fromkeys(FIELDS, "recorded")),
    ({"identification_quality": None, "relationship_quality": "ambiguous",
      "requires_review": False},
     {"identification_quality": "unknown_legacy",
      "relationship_quality": "recorded", "requires_review": "recorded"}),
])
def test_synthetic_legacy_null_classification(values, expected):
    assert classify_legacy_fields(values) == expected


@pytest.mark.skipif(not os.environ.get("DRIFT1_MIGRATED_TEST_DATABASE_URL"), reason="Opt-in only")
def test_migration_preserves_nullable_legacy_columns():
    from app.database import models  # noqa: F401
    from app.database.base import Base

    raw = approved_url(os.environ["DRIFT1_MIGRATED_TEST_DATABASE_URL"])
    engine = create_engine(raw)
    try:
        with engine.connect() as conn:
            db_name, port = conn.execute(text("SELECT current_database(), inet_server_port()")).one()
            assert (db_name, port) == (engine.url.database, 55432)
            actual = {col["name"]: col for col in inspect(conn).get_columns("contract_equipment", schema="public")}
            orm = Base.metadata.tables["contract_equipment"].columns
            assert all(not orm[field].nullable and actual[field]["nullable"] for field in FIELDS)
            counts = conn.execute(text(
                "SELECT count(*) AS total, "
                "count(*) FILTER (WHERE identification_quality IS NULL) AS identification_nulls, "
                "count(*) FILTER (WHERE relationship_quality IS NULL) AS relationship_nulls, "
                "count(*) FILTER (WHERE requires_review IS NULL) AS review_nulls "
                "FROM public.contract_equipment"
            )).one()
            assert len(counts) == 4
            # Counts are measured, not assumed zero; no writes or backfills.
    finally:
        engine.dispose()
