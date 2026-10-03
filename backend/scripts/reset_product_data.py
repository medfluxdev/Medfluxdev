"""One-time destructive reset of contract/product data for local development/UAT.

This is intentionally NOT executed at application startup. A normal restart must
never erase hospital data. The operator must run this script explicitly with the
confirmation flag. Account, organization, authorization and AI-selection rows
are preserved.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.core.config import settings

CONFIRM = "EMPTY-CONTRACT-DATA"
ROOT_TABLES = ("contract", "document_file", "equipment", "demo_workspace")


def _assert_safe_runtime() -> None:
    env = settings.app_env.strip().casefold()
    if env not in {"development", "test"}:
        raise SystemExit(
            "Abbruch: Datenreset ist nur in APP_ENV=development/test erlaubt."
        )
    url = make_url(settings.database_url)
    host = (url.host or "").casefold()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit(
            f"Abbruch: Datenbank ist nicht lokal ({host or 'kein Host'})."
        )


def _wipe_database() -> list[str]:
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            existing = set(inspect(conn).get_table_names())
            roots = [name for name in ROOT_TABLES if name in existing]
            if roots:
                quoted = ", ".join(f'"{name}"' for name in roots)
                conn.execute(
                    text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
                )
            # ActivityLog has deliberately generic object references rather than
            # hard FKs. Remove only product-object history, preserving account/
            # security activity.
            if "activity_log" in existing:
                conn.execute(
                    text(
                        "DELETE FROM activity_log "
                        "WHERE object_type IN ('contract','document','document_version','equipment')"
                    )
                )
            return roots
    finally:
        engine.dispose()


def _wipe_contract_storage() -> int:
    base = Path(settings.contracts_dir).resolve()
    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
        return 0
    removed = 0
    for child in list(base.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Leert lokale Vertrags-/Dokumentdaten vor einer sauberen UAT."
    )
    parser.add_argument(
        "--confirm",
        required=True,
        help=f"Exakter Sicherheitswert: {CONFIRM}",
    )
    args = parser.parse_args()
    if args.confirm != CONFIRM:
        raise SystemExit("Abbruch: falscher Bestätigungswert.")

    _assert_safe_runtime()
    roots = _wipe_database()
    files = _wipe_contract_storage()
    print("MedFlux Produktdaten wurden lokal geleert.")
    print("Geleerte Root-Tabellen:", ", ".join(roots) if roots else "keine")
    print("Entfernte Einträge aus data/contracts:", files)
    print("Benutzer, Organisationen, Rechte und gespeicherte KI-Auswahl wurden beibehalten.")
    print("Der Login admin@medflux.local und sein bestehender Passwort-Hash bleiben unverändert.")


if __name__ == "__main__":
    main()
