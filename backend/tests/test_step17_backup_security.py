from __future__ import annotations

import importlib.util
import json
import sys
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_verify_backup_accepts_matching_manifest(tmp_path: Path):
    verify = _load("medflux_verify_backup_test", "scripts/verify_backup.py")
    dump = tmp_path / "database.dump"
    dump.write_bytes(b"pg-dump")
    docs = tmp_path / "documents"
    docs.mkdir()
    doc = docs / "one.pdf"
    doc.write_bytes(b"pdf-bytes")
    manifest = {
        "format": "medflux-backup-v1",
        "organization_slug": "hospital",
        "database": {
            "path": "database.dump",
            "sha256": sha256(dump.read_bytes()).hexdigest(),
            "size_bytes": dump.stat().st_size,
        },
        "documents": [
            {
                "document_file_id": "doc-1",
                "backup_path": "documents/one.pdf",
                "sha256": sha256(doc.read_bytes()).hexdigest(),
                "size_bytes": doc.stat().st_size,
            }
        ],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = verify.verify_backup(tmp_path)

    assert result["organization_slug"] == "hospital"
    assert result["document_count"] == 1


def test_verify_backup_rejects_tampering(tmp_path: Path):
    verify = _load("medflux_verify_backup_tamper_test", "scripts/verify_backup.py")
    dump = tmp_path / "database.dump"
    dump.write_bytes(b"pg-dump")
    manifest = {
        "format": "medflux-backup-v1",
        "organization_slug": "hospital",
        "database": {
            "path": "database.dump",
            "sha256": "0" * 64,
            "size_bytes": dump.stat().st_size,
        },
        "documents": [],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="SHA-256"):
        verify.verify_backup(tmp_path)


def test_verify_backup_rejects_path_escape(tmp_path: Path):
    verify = _load("medflux_verify_backup_escape_test", "scripts/verify_backup.py")
    manifest = {
        "format": "medflux-backup-v1",
        "organization_slug": "hospital",
        "database": {"path": "../database.dump", "sha256": "0" * 64, "size_bytes": 1},
        "documents": [],
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="Unsicherer Manifest-Pfad"):
        verify.verify_backup(tmp_path)


def test_restore_rejects_configured_database(monkeypatch, tmp_path: Path):
    verify = _load("verify_backup", "scripts/verify_backup.py")
    restore = _load("medflux_restore_backup_test", "scripts/restore_backup.py")
    monkeypatch.setattr(restore, "verify_backup", lambda _path: {"ok": True})
    monkeypatch.setattr(restore.settings, "database_url", "postgresql+psycopg://u:p@127.0.0.1:5432/medflux")

    with pytest.raises(RuntimeError, match="laufende MedFlux-Datenbank"):
        restore.restore_backup(
            backup=tmp_path,
            target_database_url="postgresql://u:p@127.0.0.1:5432/medflux",
            target_documents_dir=tmp_path / "documents-restored",
        )
