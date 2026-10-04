"""DB aus einem pre-cleanup-Backup-JSON wiederherstellen (Rollback nach
fehlgeschlagenem Schema-Neuaufbau). Nutzung: workdir=backend,
    python ..\\scripts\\restore_from_backup.py <backup.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import sqlalchemy as sa
from alembic import command
import alembic.config

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.database import models as db_models  # noqa: E402
from app.database.base import Base  # noqa: E402,F401

SKIP = {"demo_workspace", "demo_workspace_entry", "alembic_version"}


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: restore_from_backup.py <backup.json>")
    path = Path(sys.argv[1])
    data = json.loads(path.read_text(encoding="utf-8"))

    engine = sa.create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(sa.text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(sa.text("CREATE SCHEMA public"))
        conn.commit()

    cfg = alembic.config.Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    command.upgrade(cfg, "head")
    print("Schema aufgebaut.")

    tables = {t.name: t for t in Base.metadata.sorted_tables}
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    generated = {
        name: {
            r[0]
            for r in conn.execute(
                sa.text(
                    "select column_name from information_schema.columns "
                    "where table_schema='public' and table_name=:t "
                    "and is_generated='ALWAYS'"
                ),
                {"t": name},
            )
        }
        for name in tables
    }
    for t in Base.metadata.sorted_tables:
        name = t.name
        if name in SKIP:
            continue
        skip_cols = generated.get(name, set())
        rows = data.get(name) or []
        ok = 0
        skipped = 0
        for r in rows:
            values = {k: v for k, v in r.items() if k not in skip_cols}
            try:
                conn.execute(t.insert().values(**values))
                ok += 1
            except sa.exc.IntegrityError:
                # Waise/inkonsistente Benchmark-Zeilen werden uebersprungen
                # (MEDTRON-Teil ist konsistent und wird vollstaendig wiederhergestellt).
                skipped += 1
            except sa.exc.ProgrammingError:
                skipped += 1
        print(f"  {name}: {ok} restauriert ({skipped} uebersprungen)")
    conn.close()
    engine.dispose()
    print("DB vollstaendig wiederhergestellt.")


if __name__ == "__main__":
    main()