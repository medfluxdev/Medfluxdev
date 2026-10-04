"""Guard the operational timestamp migration against accidental regression."""
import importlib.util
from pathlib import Path

from app.database.models.lifecycle import EquipmentLifecycleRecord
from app.database.models.work_item_collaboration import WorkItemCollaboration, WorkItemComment


def test_operational_timestamp_models_require_expected_columns():
    assert not EquipmentLifecycleRecord.__table__.c.created_at.nullable
    assert not WorkItemCollaboration.__table__.c.created_at.nullable
    assert not WorkItemComment.__table__.c.updated_at.nullable


def test_operational_timestamp_migration_is_additive_and_linked():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260928_b3c5d7e90928_operational_timestamps.py"
    )
    spec = importlib.util.spec_from_file_location(
        "medflux_operational_timestamps_migration_test", migration_path
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "b3c5d7e90928"
    assert migration.down_revision == "a2b4c6d80928"
    # DB upgrade/rollback and existing-row checks remain separate integration gates.
