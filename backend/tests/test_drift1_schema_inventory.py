"""Regression: generated columns must not crash DRIFT-1 inventory."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import Column, Computed, Integer, MetaData, Table, create_mock_engine


_PATH = Path(__file__).resolve().parents[1] / "scripts" / "drift1_schema_inventory.py"
_SPEC = importlib.util.spec_from_file_location("medflux_drift1_inventory_regression", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)


class _Inspector:
    def get_table_names(self, schema):
        assert schema == "public"
        return ["generated_example"]

    def get_columns(self, table_name, schema):
        assert table_name == "generated_example" and schema == "public"
        return [
            {"name": "id", "type": Integer(), "nullable": False, "default": None},
            {"name": "computed_value", "type": Integer(), "nullable": True,
             "default": None, "computed": {"sqltext": "(id + 1)", "persisted": True}},
        ]

    def get_indexes(self, table_name, schema):
        return []


def test_generated_column_inventory_does_not_read_default_arg():
    metadata = MetaData()
    Table("generated_example", metadata,
          Column("id", Integer, primary_key=True, nullable=False),
          Column("computed_value", Integer, Computed("id + 1", persisted=True)))
    engine = SimpleNamespace(dialect=create_mock_engine("postgresql://", lambda *args: None).dialect)
    with patch.object(_MODULE, "inspect", return_value=_Inspector()):
        report = _MODULE.build_schema_inventory(engine, metadata)
    assert report["missing_columns"] == {}
    assert report["default_differences"] == {}
    assert report["nullable_differences"] == {}


def test_inventory_format_is_valid_json():
    import json
    assert json.loads(_MODULE.format_inventory({"missing_columns": {}})) == {"missing_columns": {}}
