"""Restore a verified MedFlux backup into an explicit non-production target.

Safety properties:
- the target PostgreSQL URL is mandatory,
- target URL must differ from the configured MedFlux DATABASE_URL,
- pg_restore is invoked without shell=True,
- existing target content is not dropped unless --clean-target is explicit,
- document files are restored only into an explicit empty/new directory,
- manifest hashes are verified before any restore operation starts.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.core.config import settings  # noqa: E402
from verify_backup import verify_backup  # noqa: E402


def _normalized(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _postgres_connection(url: str) -> tuple[list[str], dict[str, str]]:
    parsed = urlparse(_normalized(url))
    if parsed.scheme != "postgresql" or not parsed.hostname or not parsed.path.strip("/"):
        raise ValueError("Ziel muss eine PostgreSQL-URL sein.")
    args = [
        "-h", parsed.hostname,
        "-p", str(parsed.port or 5432),
        "-U", unquote(parsed.username or ""),
        "-d", unquote(parsed.path.lstrip("/")),
    ]
    env = dict(os.environ)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    return args, env


def restore_backup(
    *,
    backup: Path,
    target_database_url: str,
    target_documents_dir: Path,
    pg_restore_bin: str = "pg_restore",
    clean_target: bool = False,
) -> None:
    backup = backup.resolve()
    verify_backup(backup)

    if _normalized(target_database_url) == _normalized(settings.database_url):
        raise RuntimeError("Restore in die konfigurierte laufende MedFlux-Datenbank ist verboten.")

    target_documents_dir = target_documents_dir.resolve()
    if target_documents_dir.exists() and any(target_documents_dir.iterdir()):
        raise RuntimeError("Dokument-Ziel ist nicht leer; Restore wird abgebrochen.")
    target_documents_dir.mkdir(parents=True, exist_ok=True)

    conn_args, env = _postgres_connection(target_database_url)
    dump_path = backup / "database.dump"
    cmd = [pg_restore_bin, *conn_args, "--no-owner", "--no-acl", "--exit-on-error"]
    if clean_target:
        cmd.extend(["--clean", "--if-exists"])
    cmd.append(str(dump_path))

    result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "pg_restore fehlgeschlagen").strip())

    source_documents = backup / "documents"
    try:
        if source_documents.exists():
            for source in source_documents.iterdir():
                if not source.is_file():
                    continue
                destination = target_documents_dir / source.name
                shutil.copy2(source, destination)
    except Exception:
        # DB-Restore ist bereits erfolgt; Dokumentziel wird wenigstens nicht als
        # vollstaendig erfolgreich zurueckgelassen.
        shutil.rmtree(target_documents_dir, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifiziertes MedFlux-Backup isoliert wiederherstellen")
    parser.add_argument("backup", type=Path)
    parser.add_argument("--target-database-url", required=True)
    parser.add_argument("--target-documents-dir", required=True, type=Path)
    parser.add_argument("--pg-restore", default="pg_restore")
    parser.add_argument("--clean-target", action="store_true")
    args = parser.parse_args()
    try:
        restore_backup(
            backup=args.backup,
            target_database_url=args.target_database_url,
            target_documents_dir=args.target_documents_dir,
            pg_restore_bin=args.pg_restore,
            clean_target=args.clean_target,
        )
    except Exception as exc:
        print(f"RESTORE_FAILED: {exc}", file=sys.stderr)
        return 2
    print("RESTORE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
