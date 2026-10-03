"""Produkt-DB bereinigen: Benchmark-/Test-Fixtures raus, echte Daten behalten.

Root Cause PR-5 Defect 1: Tests/Benchmarks legten Organisationen und Vertraege
direkt ueber `settings.database_url` in der Produkt-DB (Schema `public`) an.
Dieses Skript stellt die STRUCTURELLE Sauberkeit wieder her:

1. Es berechnet die zu ERHALTENDE Teilmenge ueber den FK-Graphen (nur die
   Organisation `krankenhaus` + der angegebene echte/benutzerimportierte
   Vertrag, z. B. der MEDTRON-Vertrag). Kinder UND von den Kindern referenzierte
   Eltern (Ausruestung, Dokumente, Belege, Work-Items ...) werden via
   bidirektionaler Fixpunkt-Iteration automatisch mitgezogen.
2. Es sichert vorab ALLE Zeilen (Sicherheitsnetz) + die erhaltende Teilmenge
   als JSON nach data/backups/.
3. Es baut das Produktschema kanonisch NEU auf (`DROP SCHEMA public CASCADE`
   + `alembic upgrade head`) - identisch zu einer frischen Installation.
4. Es fuegt anschliessend ausschliesslich die erhaltende Teilmenge (mit
   Original-IDs, aus dem Sicherheitsnetz) wieder ein. Demo-Workspace-Daten
   werden NICHT restauriert (Workspace standardmaessig aus; Vertrag normal
   sichtbar).

Nutzung (workdir=backend, damit .env gefunden wird):
    .venv\\Scripts\\python.exe ..\\scripts\\cleanup_product_db.py <contract_id>

Sicherheit: Kein eigenstaendiges Aufraeumen - nur keep-Set via FK-Graph.
Kann das keep-Set nicht bestimmt werden, bricht das Skript ab.
"""

from __future__ import annotations

import datetime
import decimal
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import MetaData, Table, create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.database import models as db_models  # noqa: E402
from app.database.base import Base  # noqa: E402,F401
from app.database.session import create_session  # noqa: E402

KEEP_ORG_SLUG = "krankenhaus"
# Reine Dev-/UAT-Ebene: wird beim Schema-Neuaufbau nie mit restauriert.
SKIP_TABLES = {"demo_workspace", "demo_workspace_entry", "alembic_version"}


def _as_json_compat(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, set, tuple)):
        return [_as_json_compat(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _as_json_compat(v) for k, v in value.items()}
    return str(value)


def fk_edges(meta: MetaData) -> list[tuple[str, str, str]]:
    """(child_table, child_column, parent_table) je FK-Kante."""
    edges: list[tuple[str, str, str]] = []
    for table in meta.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table is not None:
                edges.append((table.name, fk.parent.name, fk.column.table.name))
    return edges


def pk_cols(table: Table) -> list[str]:
    return [c.name for c in table.primary_key.columns]


def keep_closure(
    meta: MetaData,
    seed_org_id: uuid.UUID,
    seed_contract_ids: set[uuid.UUID],
) -> dict[str, set[tuple]]:
    """Keep-Set via bidirektionaler Fixpunkt-Iteration ueber den FK-Graphen.

    - Seeds: Organisation `krankenhaus` + die erhaltenden Vertraege.
    - Kanten zu `organization` als Elter werden GAR NICHT propagiert (sonst
      blieben alle alten Benchmark-Vertraege der Klinik erhalten). Kind-Zeilen
      von `organization` (z. B. document_file.organization_id) werden daher
      NICHT ueber die Organisation erreicht - nur ueber die Vertrags-Kette.
    - Demo-/Workspace-Tabellen sind keine Quellen (child_exclude).
    """
    tables = {t.name: t for t in meta.sorted_tables}
    edges = fk_edges(meta)
    keep: dict[str, set[tuple]] = {name: set() for name in tables}
    keep["organization"].add((seed_org_id,))
    keep["contract"].update((i,) for i in seed_contract_ids)

    session = create_session()
    try:
        fk_cache: dict[tuple, Any] = {}

        def child_fk_value(child_name: str, col: str, tup: tuple) -> Any:
            key = (child_name, col, tup)
            if key not in fk_cache:
                child = tables[child_name]
                cpk = pk_cols(child)
                if len(cpk) != 1:
                    raise NotImplementedError(
                        "Cleanup unterstuetzt nur Einspalten-PKs"
                    )
                fk_cache[key] = session.execute(
                    sa.select(child.c[col]).where(child.c[cpk[0]] == tup[0])
                ).scalar_one_or_none()
            return fk_cache[key]

        changed = True
        while changed:
            changed = False
            for child_name, col, parent_name in edges:
                if child_name in SKIP_TABLES or parent_name == "organization":
                    continue
                child, parent = tables[child_name], tables[parent_name]
                ppk = pk_cols(parent)
                if len(ppk) != 1:
                    continue
                child_pk_map = {name: c for name, c in child.primary_key.columns.items()}

                # a) Kindzeilen der erhaltenden Eltern (downward).
                parent_ids = {r[0] for r in keep[parent_name]} if len(ppk) == 1 else set()
                if parent_ids:
                    fkid = parent.c[ppk[0]]
                    st = sa.select(*child.primary_key.columns).where(
                        child.c[col].in_(parent_ids)
                    )
                    for row in session.execute(st):
                        tup = tuple(row)
                        if tup not in keep[child_name]:
                            keep[child_name].add(tup)
                            changed = True

                # b) Elternzeilen der erhaltenden Kindzeilen (upward, via FK-Wert).
                for ctup in list(keep[child_name]):
                    fkval = child_fk_value(child_name, col, ctup)
                    if fkval is None:
                        continue
                    if (fkval,) not in keep[parent_name]:
                        keep[parent_name].add((fkval,))
                        changed = True
        return keep
    finally:
        session.close()


def dump_rows(engine, table: Table) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(sa.select(table)).mappings().all()
    return [{k: _as_json_compat(v) for k, v in r.items()} for r in rows]


def pk_value(pk: list[str], row: dict) -> tuple:
    return tuple(row[c] for c in pk)


def _norm(value: Any) -> Any:
    """UUID und UUID-Strings vergleichbar machen (JSON-Backup vs. live)."""
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(
            "usage: cleanup_product_db.py <keep_contract_id> "
            "[--apply --confirm-drop-schema=DROP-PUBLIC-SCHEMA]"
        )
    keep_contract_id = uuid.UUID(sys.argv[1])

    meta: MetaData = Base.metadata
    tables = {t.name: t for t in meta.sorted_tables}
    engine = create_engine(settings.database_url, pool_pre_ping=True)

    with create_session() as s:
        org = s.execute(
            text("select id from organization where slug = :slug"),
            {"slug": KEEP_ORG_SLUG},
        ).first()
        if org is None:
            sys.exit(f"Organisation '{KEEP_ORG_SLUG}' nicht gefunden.")
        keep_org_id: uuid.UUID = org[0]
        exists = s.execute(
            text("select id from contract where id = :cid"), {"cid": keep_contract_id}
        ).first()
        if exists is None:
            sys.exit(f"Keep-Vertrag {keep_contract_id} nicht gefunden.")

    keep = keep_closure(meta, keep_org_id, {keep_contract_id})
    keep_count = sum(len(v) for v in keep.values())
    print(f"Keep-Teilmenge: {keep_count} Zeilen ueber {len(keep)} Tabellen")

    # Destructive schema rebuild is never implicit. A plain invocation is a
    # dry-run that proves the keep-set can be calculated. Two explicit signals
    # are required before DROP SCHEMA is reachable.
    apply = "--apply" in sys.argv[2:]
    confirmed = "--confirm-drop-schema=DROP-PUBLIC-SCHEMA" in sys.argv[2:]
    if not apply or not confirmed:
        print(
            "DRY-RUN: keine Daten veraendert. Fuer den destruktiven Lauf sind "
            "--apply und --confirm-drop-schema=DROP-PUBLIC-SCHEMA erforderlich."
        )
        return

    backup_dir = ROOT / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"pre-cleanup-{stamp}.json"
    backup_path.write_text(
        json.dumps(
            {name: dump_rows(engine, t) for name, t in tables.items()},
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Sicherung aller Zeilen -> {backup_path}")

    # Erhaltende Zeilen aus dem Sicherungsnetz f�r den Rueckspieler.
    keep_rows: dict[str, list[dict]] = {}
    backup = json.loads(backup_path.read_text(encoding="utf-8"))
    for name, t in tables.items():
        if name in SKIP_TABLES:
            continue
        pk = pk_cols(t)
        wanted = {tuple(_norm(v) for v in tup) for tup in keep[name]}
        keep_rows[name] = [
            r for r in backup.get(name, []) if tuple(_norm(r[c]) for c in pk) in wanted
        ]
    restored_n = sum(len(v) for v in keep_rows.values())
    print(f"Zu restaurieren: {restored_n} Zeilen")

    # Schema kanonisch neu aufbauen (wie frische Installation).
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    engine.dispose()

    import alembic.config
    from alembic import command

    cfg = alembic.config.Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    command.upgrade(cfg, "head")
    print("Produkt-Schema neu aufgebaut (alembic upgrade head).")

    # Erhaltende Teilmenge mit Original-IDs zurueckspielen (zeilenweise,
    # autocommit; Fehlerfälle nur fuer nie zu erhaltende Orphans).
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    generated = {
        name: {
            r[0]
            for r in conn.execute(
                text(
                    "select column_name from information_schema.columns "
                    "where table_schema='public' and table_name=:t "
                    "and is_generated='ALWAYS'"
                ),
                {"t": name},
            )
        }
        for name in tables
    }
    total_ok = 0
    for t in meta.sorted_tables:
        name = t.name
        if name in SKIP_TABLES:
            continue
        rows = keep_rows.get(name) or []
        skip_cols = generated.get(name, set())
        ok = 0
        for r in rows:
            try:
                conn.execute(
                    t.insert().values(
                        **{k: v for k, v in r.items() if k not in skip_cols}
                    )
                )
                ok += 1
            except sa.exc.IntegrityError:
                print(f"  {name}: Zeile uebersprungen (FK-Orphan)")
            except sa.exc.ProgrammingError as exc:
                print(f"  {name}: Zeile uebersprungen ({str(exc.orig)[:80]})")
        total_ok += ok
        print(f"  {name}: {ok} Zeile(n) restauriert")
    conn.close()
    engine.dispose()
    print(f"Insgesamt restauriert: {total_ok}")

    with create_session() as s:
        orgs = s.execute(text("select count(*) from organization")).scalar()
        contracts = s.execute(text("select count(*) from contract")).scalar()
        work = s.execute(text("select count(*) from work_item")).scalar()
        ev = s.execute(text("select count(*) from extraction_evidence")).scalar()
        eq = s.execute(text("select count(*) from equipment")).scalar()
        ws = s.execute(text("select count(*) from demo_workspace")).scalar()
        medtron = s.execute(
            text("select count(*) from contract where id = :cid"),
            {"cid": keep_contract_id},
        ).scalar()
    print(f"Nachher: organization={orgs} contract={contracts} work_item={work} "
          f"equipment={eq} evidence={ev} demo_workspace={ws}")
    if contracts != 1 or medtron != 1:
        sys.exit("Achtung: erwartete 1 erhaltenen Vertrag - bitte pruefen.")


if __name__ == "__main__":
    main()