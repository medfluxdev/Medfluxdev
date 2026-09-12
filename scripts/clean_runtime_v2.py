"""Explicit PR-6 business reset. Dry-run default; schema/settings/source files preserved."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.database.base import Base
from app.database import models  # register the application-owned schema
from app.database.session import get_engine
from app.documents.storage import DocumentStorage

PRESERVE = {"application_setting", "organization"}


def clean(apply=False):
    storage_root = Path(settings.contracts_dir).resolve()
    # Only the actual configured runtime store underneath this project is authorized.
    if not any(storage_root.is_relative_to(root) for root in (ROOT / "data", ROOT / "backend" / "data")):
        raise RuntimeError("Configured contracts store is outside Medflux/data; refusing cleanup")
    storage = DocumentStorage(storage_root)
    engine = get_engine()
    tables = [t for t in Base.metadata.tables.values() if t.name not in PRESERVE]
    with engine.begin() as conn:
        # Block concurrent imports/mutations while planning and clearing the business rows.
        names = ", ".join('"' + t.name + '"' for t in tables)
        conn.execute(sa.text("LOCK TABLE " + names + " IN ACCESS EXCLUSIVE MODE"))
        running = conn.execute(sa.text("SELECT count(*) FROM document_processing_result WHERE status='running'")).scalar()
        if running:
            raise RuntimeError("Processing runs are active; stop workers before cleanup")
        counts = {t.name: conn.execute(sa.select(sa.func.count()).select_from(t)).scalar() for t in tables}
        selected = list(conn.execute(sa.text("SELECT key, value FROM application_setting ORDER BY key")))
        refs = set()
        for name in ("document_file", "document_version", "document_artifact"):
            refs.update(conn.execute(sa.select(Base.metadata.tables[name].c.storage_key)).scalars())
        # The manifest is an application-owned registry, not an arbitrary filesystem search.
        manifest = storage._load_index()
        for record in manifest.values():
            doc_id = record.get("document_id", "")
            extension = record.get("file_extension")
            if doc_id and extension in {".pdf", ".docx"}:
                refs.add(f"{doc_id}/original{extension}")
        paths = [storage.safe_path(ref) for ref in sorted(refs)]
        report = {"apply": apply, "storage_root": str(storage_root), "before": counts,
                  "registered_files": len(paths), "preserved": sorted(PRESERVE)}
        if not apply:
            return report
        # Explicit table set, no CASCADE: an unknown outside dependency makes the reset fail safely.
        conn.execute(sa.text("TRUNCATE TABLE " + names))
        if selected != list(conn.execute(sa.text("SELECT key, value FROM application_setting ORDER BY key"))):
            raise RuntimeError("Application settings changed during cleanup")
        report["after"] = {t.name: conn.execute(sa.select(sa.func.count()).select_from(t)).scalar() for t in tables}
    # Files are independently validated again immediately before deletion. No recursive tree deletion.
    failures = []
    for ref in sorted(refs):
        target = storage.safe_path(ref)
        try:
            target.unlink(missing_ok=True)
        except OSError:
            failures.append(ref)
    storage._save_index({})
    report["file_failures"] = failures
    if failures:
        raise RuntimeError("Runtime rows cleared, but registered file cleanup is incomplete")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(clean(args.apply), indent=2))
