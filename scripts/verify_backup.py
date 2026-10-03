"""Verify a MedFlux STEP 17 backup without restoring it."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_child(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if not relative or rel.is_absolute() or ".." in rel.parts:
        raise RuntimeError(f"Unsicherer Manifest-Pfad: {relative}")
    target = (root / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Manifest-Pfad verlaesst Backup-Root: {relative}") from exc
    return target


def _verify_file(root: Path, item: dict, *, label: str) -> str:
    relative = str(item.get("backup_path") or "")
    path = _safe_child(root, relative)
    if not path.is_file():
        raise RuntimeError(f"{label} fehlt: {relative}")
    if _sha256_file(path) != item.get("sha256"):
        raise RuntimeError(f"SHA-256 stimmt nicht: {relative}")
    if path.stat().st_size != int(item.get("size_bytes") or -1):
        raise RuntimeError(f"Dateigroesse stimmt nicht: {relative}")
    return str(path.relative_to(root))


def verify_backup(root: Path) -> dict:
    root = root.resolve()
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("manifest.json fehlt.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "medflux-backup-v1":
        raise RuntimeError("Unbekanntes Backup-Format.")

    checked: list[str] = []
    db = manifest.get("database") or {}
    db_path = _safe_child(root, str(db.get("path") or ""))
    if not db_path.is_file():
        raise RuntimeError("Datenbank-Dump fehlt.")
    if _sha256_file(db_path) != db.get("sha256"):
        raise RuntimeError("SHA-256 des Datenbank-Dumps stimmt nicht.")
    if db_path.stat().st_size != int(db.get("size_bytes") or -1):
        raise RuntimeError("Groesse des Datenbank-Dumps stimmt nicht.")
    checked.append(str(db_path.relative_to(root)))

    # Current v1 format: canonical storage objects preserving their storage_key.
    seen_keys: set[str] = set()
    storage_objects = manifest.get("storage_objects")
    if storage_objects is not None:
        if not isinstance(storage_objects, list):
            raise RuntimeError("storage_objects muss eine Liste sein.")
        for item in storage_objects:
            storage_key = str(item.get("storage_key") or "")
            if not storage_key or storage_key in seen_keys:
                raise RuntimeError("Fehlende oder doppelte storage_key im Manifest.")
            # storage_key itself is persisted into the restored DB/storage mapping,
            # so apply the same generic traversal/absolute-path rejection here.
            _safe_child(Path("/tmp/medflux-storage-root"), storage_key)
            seen_keys.add(storage_key)
            checked.append(_verify_file(root, item, label="Storage-Objekt"))

    # Backward-compatible verification for the initial pre-layout v1 draft.
    seen_ids: set[str] = set()
    for item in manifest.get("documents") or []:
        doc_id = str(item.get("document_file_id") or "")
        if not doc_id or doc_id in seen_ids:
            raise RuntimeError("Fehlende oder doppelte document_file_id im Manifest.")
        seen_ids.add(doc_id)
        checked.append(_verify_file(root, item, label="Dokument"))

    return {
        "format": manifest["format"],
        "organization_slug": manifest.get("organization_slug"),
        "checked_files": checked,
        "document_count": len(seen_ids),
        "storage_object_count": len(seen_keys),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MedFlux-Backup-Integritaet pruefen")
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    try:
        result = verify_backup(args.backup)
    except Exception as exc:
        print(f"VERIFY_FAILED: {exc}", file=sys.stderr)
        return 2
    print(
        "VERIFY_OK: "
        f"organization={result['organization_slug']} "
        f"storage_objects={result['storage_object_count']} "
        f"legacy_documents={result['document_count']} "
        f"files={len(result['checked_files'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
