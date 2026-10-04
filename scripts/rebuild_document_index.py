#!/usr/bin/env python3
"""Rebuild the document storage index (.index.json) from the files on disk.

The index format MUST match ``app.documents.storage.DocumentStorage``:
a flat mapping ``{sha256: record}`` where every record carries the same keys
``DocumentStorage.save`` writes (document_id, original_filename,
stored_filename, file_extension, mime_type, file_size_bytes, sha256,
storage_path, imported_at, import_status).

Safety:
- Default is a dry run: the rebuilt index is only printed as a summary.
- ``--write`` replaces ``<contracts-dir>/.index.json`` atomically and first
  copies an existing index to ``.index.json.bak-<timestamp>``.
- Metadata from an existing index entry (original filename, import time) is
  preserved when the same SHA-256 is still present on disk.
- Only folders whose name is a valid storage id (lowercase hex) and that hold
  exactly one ``original.pdf`` / ``original.docx`` are indexed; everything else
  is reported, never guessed.

Usage (from the repository root):
    python scripts/rebuild_document_index.py --contracts-dir backend/data/contracts
    python scripts/rebuild_document_index.py --contracts-dir backend/data/contracts --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INDEX_FILENAME = ".index.json"
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_storage_id(name: str) -> bool:
    return bool(name) and all(c in "0123456789abcdef" for c in name)


def _load_existing(index_path: Path) -> dict[str, dict[str, Any]]:
    if not index_path.exists():
        return {}
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    # Ignore the broken legacy layout {"version", "documents", ...}.
    return {
        key: value for key, value in raw.items()
        if isinstance(value, dict) and value.get("sha256") == key
    }


def rebuild_index(contracts_dir: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return ``(index, problems)`` for the storage directory."""
    contracts_dir = Path(contracts_dir)
    if not contracts_dir.is_dir():
        raise FileNotFoundError(f"Contracts directory not found: {contracts_dir}")

    existing = _load_existing(contracts_dir / INDEX_FILENAME)
    index: dict[str, dict[str, Any]] = {}
    problems: list[str] = []

    for folder in sorted(contracts_dir.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if not _is_storage_id(folder.name):
            problems.append(f"{folder.name}: folder name is not a storage id (skipped)")
            continue
        originals = [
            folder / f"original{ext}" for ext in sorted(MIME_TYPES)
            if (folder / f"original{ext}").is_file()
        ]
        if len(originals) != 1:
            problems.append(
                f"{folder.name}: expected exactly one original file, found {len(originals)} (skipped)"
            )
            continue
        original = originals[0]
        sha256 = compute_sha256(original)
        if sha256 in index:
            problems.append(
                f"{folder.name}: same SHA-256 as {index[sha256]['document_id']} (duplicate, skipped)"
            )
            continue
        previous = existing.get(sha256, {})
        extension = original.suffix.lower()
        index[sha256] = {
            "document_id": folder.name,
            "original_filename": previous.get("original_filename") or original.name,
            "stored_filename": original.name,
            "file_extension": extension,
            "mime_type": previous.get("mime_type") or MIME_TYPES[extension],
            "file_size_bytes": original.stat().st_size,
            "sha256": sha256,
            "storage_path": str(original),
            "imported_at": previous.get("imported_at")
            or datetime.fromtimestamp(original.stat().st_mtime, timezone.utc).isoformat(),
            "import_status": previous.get("import_status") or "imported",
        }
    return index, problems


def write_index(contracts_dir: Path, index: dict[str, dict[str, Any]]) -> Path | None:
    """Atomically replace the index; back up an existing file first."""
    target = Path(contracts_dir) / INDEX_FILENAME
    backup: Path | None = None
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = target.with_name(f"{INDEX_FILENAME}.bak-{stamp}")
        shutil.copy2(target, backup)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return backup


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the document storage index")
    parser.add_argument("--contracts-dir", type=Path, default=Path("backend/data/contracts"))
    parser.add_argument(
        "--write", action="store_true",
        help="replace <contracts-dir>/.index.json (default: dry run)",
    )
    args = parser.parse_args(argv)

    try:
        index, problems = rebuild_index(args.contracts_dir)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    total = sum(row["file_size_bytes"] for row in index.values())
    print(f"Indexed documents: {len(index)} ({total:,} bytes)")
    for problem in problems:
        print(f"  ! {problem}")
    if not args.write:
        print("Dry run: nothing written. Re-run with --write to replace the index.")
        return 0
    backup = write_index(args.contracts_dir, index)
    if backup is not None:
        print(f"Previous index saved as {backup}")
    print(f"Index written to {Path(args.contracts_dir) / INDEX_FILENAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
