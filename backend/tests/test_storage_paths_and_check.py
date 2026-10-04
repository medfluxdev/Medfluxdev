"""Storage paths are anchored to backend/ and the store check is read-only."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import BACKEND_DIR, Settings
from app.documents.storage_check import document_store_findings


def test_relative_storage_paths_are_anchored_to_backend_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    settings = Settings(_env_file=None, contracts_dir="./data/contracts")
    assert Path(settings.contracts_dir) == (BACKEND_DIR / "data" / "contracts").resolve()
    assert Path(settings.data_dir).is_absolute()
    assert Path(settings.backups_dir).is_absolute()


def test_absolute_storage_path_is_kept(tmp_path):
    settings = Settings(_env_file=None, contracts_dir=str(tmp_path / "store"))
    assert settings.contracts_dir == str((tmp_path / "store").resolve())


def test_store_check_reports_missing_dir_and_index(tmp_path):
    assert document_store_findings(tmp_path / "missing")
    (tmp_path / "abc123").mkdir()
    assert "no .index.json" in document_store_findings(tmp_path)[0]
    assert not (tmp_path / ".index.json").exists()  # read-only


def test_store_check_detects_wrong_format_and_gaps(tmp_path):
    (tmp_path / "aa").mkdir()
    (tmp_path / "bb").mkdir()
    (tmp_path / ".index.json").write_text(json.dumps({"version": "1.0", "documents": {}}))
    assert "format" in document_store_findings(tmp_path)[0]
    (tmp_path / ".index.json").write_text(json.dumps({"x": {"sha256": "x", "document_id": "aa"}}))
    assert "1 of 2" in document_store_findings(tmp_path)[0]
    (tmp_path / ".index.json").write_text(json.dumps({
        "x": {"sha256": "x", "document_id": "aa"},
        "y": {"sha256": "y", "document_id": "bb"},
    }))
    assert document_store_findings(tmp_path) == []
