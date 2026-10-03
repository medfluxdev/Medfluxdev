"""Source-level migration contract; real PostgreSQL upgrade/downgrade is separate."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

from app.database.models import ContractEquipment


def _migration():
    path = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions"
        / "20260930_c4d6e8f00930_equipment_occurrence_identity.py"
    )
    spec = importlib.util.spec_from_file_location("occurrence_migration_test", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_model_and_migration_share_occurrence_constraint():
    migration = _migration()
    assert migration.revision == "c4d6e8f00930"
    assert migration.down_revision == "b3c5d7e90928"
    assert "occurrence_fingerprint" in ContractEquipment.__table__.c
    constraints = {
        c.name for c in ContractEquipment.__table__.constraints
    }
    assert "uq_contract_equipment_contract_extraction_occurrence" in constraints


def test_upgrade_backfills_before_replacing_unique_constraint():
    migration = _migration()
    events = []
    with patch.object(migration.op, "add_column", side_effect=lambda *a, **k: events.append("column")), \
         patch.object(migration.op, "execute", side_effect=lambda *a, **k: events.append("backfill")), \
         patch.object(migration.op, "drop_constraint", side_effect=lambda *a, **k: events.append("drop")), \
         patch.object(migration.op, "create_unique_constraint", side_effect=lambda *a, **k: events.append("unique")):
        migration.upgrade()
    assert events == ["column", "backfill", "drop", "unique"]


def test_downgrade_checks_for_collisions_before_dropping_occurrence_constraint():
    migration = _migration()
    events = []
    with patch.object(migration.op, "execute", side_effect=lambda *a, **k: events.append("guard")), \
         patch.object(migration.op, "drop_constraint", side_effect=lambda *a, **k: events.append("drop")), \
         patch.object(migration.op, "create_unique_constraint", side_effect=lambda *a, **k: events.append("unique")), \
         patch.object(migration.op, "drop_column", side_effect=lambda *a, **k: events.append("column")):
        migration.downgrade()
    assert events == ["guard", "drop", "unique", "column"]
