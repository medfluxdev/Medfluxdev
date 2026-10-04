"""Startup diagnostics for the local document store (read-only).

Reports, without changing anything, whether the configured contracts folder
exists and whether its `.index.json` is readable in the format
`DocumentStorage` uses. Findings are logged as warnings so an operator notices
a wrong working directory or a broken index before imports silently create a
second store or SHA-256 duplicate detection stops working.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("medflux.storage")


def document_store_findings(contracts_dir: str | Path) -> list[str]:
    base = Path(contracts_dir)
    if not base.is_dir():
        return [f"contracts directory does not exist: {base}"]
    folders = [
        p for p in base.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]
    index_path = base / ".index.json"
    if not index_path.exists():
        return (
            [f"{len(folders)} stored documents but no .index.json (run scripts/rebuild_document_index.py)"]
            if folders else []
        )
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return [".index.json is not valid JSON"]
    if not isinstance(raw, dict) or not all(
        isinstance(v, dict) and v.get("sha256") == k for k, v in raw.items()
    ):
        return [".index.json is not in the {sha256: record} format DocumentStorage reads"]
    if len(raw) < len(folders):
        return [f".index.json lists {len(raw)} of {len(folders)} stored document folders"]
    return []


def log_document_store_findings(contracts_dir: str | Path) -> list[str]:
    findings = document_store_findings(contracts_dir)
    for finding in findings:
        logger.warning("Document store check: %s", finding)
    return findings
