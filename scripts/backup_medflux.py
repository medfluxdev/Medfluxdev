"""Create a MedFlux organization backup (STEP 17).

The backup is written to a new target directory and contains:
- a PostgreSQL custom-format dump created with pg_dump (no shell=True),
- all organization-owned canonical storage objects referenced by the DB,
- a JSON manifest with SHA-256 for every backup artifact.

The script never deletes or overwrites an existing backup directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.database.models import (  # noqa: E402
    DocumentArtifact,
    DocumentFile,
    DocumentVersion,
    Organization,
)
from app.database.session import create_session  # noqa: E402
from app.documents.storage import DocumentStorage, StorageError  # noqa: E402


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _postgres_connection(url: str) -> tuple[list[str], dict[str, str]]:
    """Translate SQLAlchemy PostgreSQL URL into pg_dump CLI args safely."""
    normalized = url.replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    if parsed.scheme != "postgresql" or not parsed.hostname or not parsed.path.strip("/"):
        raise ValueError("DATABASE_URL muss eine PostgreSQL-URL sein.")
    args = [
        "-h",
        parsed.hostname,
        "-p",
        str(parsed.port or 5432),
        "-U",
        unquote(parsed.username or ""),
        "-d",
        unquote(parsed.path.lstrip("/")),
    ]
    env = dict(os.environ)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    return args, env


def _organization(session, slug: str) -> Organization:
    org = session.scalars(select(Organization).where(Organization.slug == slug)).first()
    if org is None:
        raise RuntimeError("Organisation nicht gefunden.")
    return org


def _assert_single_org_backup_scope(session, slug: str) -> Organization:
    """Fail closed: a full pg_dump must never masquerade as a tenant-only backup.

    STEP 17 currently stores a PostgreSQL custom dump of the complete database.
    Until a truly tenant-filtered relational export exists, allowing that dump
    in a multi-organization database would leak other tenants into an archive
    labelled with a single organization slug.
    """
    organizations = list(session.scalars(select(Organization)).all())
    if len(organizations) != 1:
        raise RuntimeError(
            "Organisationsbezogenes Backup ist nur bei genau einer Organisation "
            "in der Datenbank erlaubt; ein Voll-Dump darf keine fremden Mandanten enthalten."
        )
    org = organizations[0]
    if org.slug != slug:
        raise RuntimeError("Organisation nicht gefunden.")
    return org


def _remember_object(
    objects: dict[str, dict],
    *,
    storage_key: str,
    sha256: str,
    size_bytes: int | None,
    source_type: str,
    source_id: str,
) -> None:
    DocumentStorage.validate_reference(storage_key)
    existing = objects.get(storage_key)
    if existing is not None:
        if existing["sha256"] != sha256:
            raise RuntimeError(f"Widerspruechliche SHA-256 fuer Storage-Referenz {storage_key}.")
        existing["sources"].append({"type": source_type, "id": source_id})
        return
    objects[storage_key] = {
        "storage_key": storage_key,
        "sha256": sha256,
        "size_bytes": size_bytes,
        "sources": [{"type": source_type, "id": source_id}],
    }


def create_backup(*, organization_slug: str, target: Path, pg_dump_bin: str = "pg_dump") -> Path:
    if target.exists():
        raise RuntimeError("Backup-Ziel existiert bereits; es wird nichts ueberschrieben.")
    target.mkdir(parents=True, exist_ok=False)
    storage_backup_dir = target / "storage"
    storage_backup_dir.mkdir()

    manifest: dict = {
        "format": "medflux-backup-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "organization_slug": organization_slug,
        "database": {},
        "storage_objects": [],
    }

    dump_path = target / "database.dump"
    try:
        scope_session = create_session()
        try:
            _assert_single_org_backup_scope(scope_session, organization_slug)
        finally:
            scope_session.close()

        conn_args, env = _postgres_connection(settings.database_url)
        cmd = [
            pg_dump_bin,
            *conn_args,
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--file",
            str(dump_path),
        ]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            message = (result.stderr or "pg_dump fehlgeschlagen").strip()
            raise RuntimeError(f"pg_dump fehlgeschlagen: {message}")
        if not dump_path.is_file():
            raise RuntimeError("pg_dump hat keine Dump-Datei erzeugt.")

        manifest["database"] = {
            "path": dump_path.name,
            "sha256": _sha256_file(dump_path),
            "size_bytes": dump_path.stat().st_size,
            "format": "postgresql-custom",
        }

        storage = DocumentStorage(settings.contracts_dir)
        session = create_session()
        try:
            org = _organization(session, organization_slug)
            objects: dict[str, dict] = {}

            files = session.scalars(
                select(DocumentFile).where(DocumentFile.organization_id == org.id)
            ).all()
            for row in files:
                _remember_object(
                    objects,
                    storage_key=row.storage_key,
                    sha256=row.sha256,
                    size_bytes=row.file_size_bytes,
                    source_type="document_file",
                    source_id=str(row.id),
                )

            versions = session.scalars(
                select(DocumentVersion).where(DocumentVersion.organization_id == org.id)
            ).all()
            for row in versions:
                _remember_object(
                    objects,
                    storage_key=row.storage_key,
                    sha256=row.sha256,
                    size_bytes=None,
                    source_type="document_version",
                    source_id=str(row.id),
                )

            artifacts = session.scalars(
                select(DocumentArtifact).where(
                    (DocumentArtifact.organization_id == org.id)
                    & (DocumentArtifact.lifecycle_state != "deleted")
                )
            ).all()
            for row in artifacts:
                _remember_object(
                    objects,
                    storage_key=row.storage_key,
                    sha256=row.sha256,
                    size_bytes=row.size_bytes,
                    source_type="document_artifact",
                    source_id=str(row.id),
                )

            for storage_key in sorted(objects):
                item = objects[storage_key]
                try:
                    content = storage.read_reference(storage_key)
                except StorageError as exc:
                    raise RuntimeError(f"Storage-Objekt kann nicht gelesen werden: {storage_key}: {exc}") from exc
                actual_sha = _sha256_bytes(content)
                if actual_sha != item["sha256"]:
                    raise RuntimeError(f"SHA-256-Abweichung beim Storage-Objekt {storage_key}.")
                if item["size_bytes"] is not None and len(content) != int(item["size_bytes"]):
                    raise RuntimeError(f"Groessenabweichung beim Storage-Objekt {storage_key}.")

                backup_rel = Path("storage") / Path(storage_key)
                destination = target / backup_rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                manifest["storage_objects"].append(
                    {
                        **item,
                        "size_bytes": len(content),
                        "backup_path": backup_rel.as_posix(),
                    }
                )
        finally:
            session.close()

        manifest_path = target / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest_path
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="MedFlux PostgreSQL + Storage-Backup erstellen")
    parser.add_argument("--organization", required=True, help="Organisations-Slug")
    parser.add_argument("--target", required=True, type=Path, help="Neues Backup-Verzeichnis")
    parser.add_argument("--pg-dump", default="pg_dump", help="Pfad zu pg_dump")
    args = parser.parse_args()
    try:
        manifest = create_backup(
            organization_slug=args.organization,
            target=args.target.resolve(),
            pg_dump_bin=args.pg_dump,
        )
    except Exception as exc:
        print(f"BACKUP_FAILED: {exc}", file=sys.stderr)
        return 2
    print(f"BACKUP_OK: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
