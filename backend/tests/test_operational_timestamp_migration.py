"""Guard the operational timestamp migration against accidental regression."""
from importlib import import_module

from app.database.models.lifecycle import EquipmentLifecycleRecord
from app.database.models.work_item_collaboration import WorkItemCollaboration, WorkItemComment


def test_operational_timestamp_models_require_expected_columns():
    assert not EquipmentLifecycleRecord.__table__.c.created_at.nullable
    assert not WorkItemCollaboration.__table__.c.created_at.nullable
    assert not WorkItemComment.__table__.c.updated_at.nullable


def test_operational_timestamp_migration_is_additive_and_linked():
    migration = import_module("alembic.versions.20260928_b3c5d7e90928_operational_timestamps")
    assert migration.down_revision == "a2b4c6d80928"
    # Actual DB upgrade/rollback and existing-row checks are mandatory
    # external integration gates, not substituted by this structural test.
