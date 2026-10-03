"""Read-only ORM-versus-migration schema inventory for a verified disposable DB.

This module reports differences; it NEVER treats every difference as a defect.
It is called only after verify_migrated_fixture has validated the target,
created the migration schema, and verified the Alembic head.
"""
from __future__ import annotations

import json

from sqlalchemy import Computed, inspect


def build_schema_inventory(engine, metadata) -> dict:
    inspector = inspect(engine)
    report = {
        "missing_tables": [],
        "missing_columns": {},
        "migration_only_columns": {},
        "nullable_differences": {},
        "type_differences": {},
        "default_differences": {},
        "migration_only_indexes": {},
        "orm_only_indexes": {},
    }
    actual_tables = set(inspector.get_table_names(schema="public"))
    expected_tables = set(metadata.tables)
    report["missing_tables"] = sorted(expected_tables - actual_tables)

    for table_name in sorted(expected_tables & actual_tables):
        table = metadata.tables[table_name]
        actual_columns = {col["name"]: col for col in inspector.get_columns(table_name, schema="public")}
        model_columns = {col.name: col for col in table.columns}
        missing = sorted(model_columns.keys() - actual_columns.keys())
        extra = sorted(actual_columns.keys() - model_columns.keys())
        if missing:
            report["missing_columns"][table_name] = missing
        if extra:
            report["migration_only_columns"][table_name] = extra
        for name in sorted(model_columns.keys() & actual_columns.keys()):
            model = model_columns[name]
            migrated = actual_columns[name]
            if bool(model.nullable) != bool(migrated["nullable"]):
                report["nullable_differences"][f"{table_name}.{name}"] = {
                    "orm": bool(model.nullable),
                    "migration": bool(migrated["nullable"]),
                }
            # Type string differences are candidates for review, not proof of
            # semantic incompatibility (dialect aliases can differ).
            orm_type = str(model.type.compile(dialect=engine.dialect)).lower()
            db_type = str(migrated["type"].compile(dialect=engine.dialect)).lower()
            if orm_type != db_type:
                report["type_differences"][f"{table_name}.{name}"] = {
                    "orm": orm_type, "migration": db_type,
                }
            sd = model.server_default
            if isinstance(sd, Computed):
                # Generated columns are not ordinary server defaults. Keep
                # their expressions visible without assuming DefaultClause.arg.
                orm_default = {"kind": "generated", "expression": str(sd.sqltext), "persisted": sd.persisted}
            elif sd is None:
                orm_default = None
            else:
                orm_default = str(sd.arg)
            db_default = migrated.get("computed") if isinstance(sd, Computed) else migrated.get("default")
            # Normalization is intentionally minimal; human review required.
            if (orm_default is None) != (db_default is None):
                report["default_differences"][f"{table_name}.{name}"] = {
                    "orm": orm_default, "migration": db_default,
                }

        orm_indexes = {index.name for index in table.indexes if index.name}
        db_indexes = {index["name"] for index in inspector.get_indexes(table_name, schema="public")}
        migration_only = sorted(db_indexes - orm_indexes)
        orm_only = sorted(orm_indexes - db_indexes)
        if migration_only:
            report["migration_only_indexes"][table_name] = migration_only
        if orm_only:
            report["orm_only_indexes"][table_name] = orm_only
    return report


def format_inventory(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
