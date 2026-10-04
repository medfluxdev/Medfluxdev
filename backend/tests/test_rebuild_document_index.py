"""scripts/rebuild_document_index.py must produce the index DocumentStorage reads."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from app.documents.storage import DocumentStorage

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "rebuild_document_index.py"
_SPEC = importlib.util.spec_from_file_location("medflux_rebuild_document_index", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
rebuild = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rebuild)


def _store(base: Path, doc_id: str, name: str, content: bytes) -> str:
    folder = base / doc_id
    folder.mkdir(parents=True)
    (folder / name).write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def test_rebuilt_index_is_readable_by_document_storage(tmp_path):
    pdf_sha = _store(tmp_path, "aa11", "original.pdf", b"%PDF-1.4 a")
    docx_sha = _store(tmp_path, "bb22", "original.docx", b"PK docx")

    index, problems = rebuild.rebuild_index(tmp_path)
    assert problems == []
    rebuild.write_index(tmp_path, index)

    storage = DocumentStorage(tmp_path)
    assert storage.find_by_sha256(pdf_sha)["document_id"] == "aa11"
    assert storage.find_by_sha256(docx_sha)["file_extension"] == ".docx"
    assert storage.find_by_document_id("bb22")["sha256"] == docx_sha
    assert storage.resolve_document("aa11")[0] == ".pdf"


def test_existing_metadata_is_preserved_and_old_index_backed_up(tmp_path):
    sha = _store(tmp_path, "cc33", "original.pdf", b"%PDF-1.4 c")
    old = {sha: {"sha256": sha, "document_id": "cc33",
                 "original_filename": "Wartungsvertrag.pdf",
                 "imported_at": "2026-09-01T10:00:00+00:00"}}
    (tmp_path / ".index.json").write_text(json.dumps(old), encoding="utf-8")

    index, _ = rebuild.rebuild_index(tmp_path)
    backup = rebuild.write_index(tmp_path, index)

    assert backup is not None and json.loads(backup.read_text(encoding="utf-8")) == old
    record = DocumentStorage(tmp_path).find_by_sha256(sha)
    assert record["original_filename"] == "Wartungsvertrag.pdf"
    assert record["imported_at"] == "2026-09-01T10:00:00+00:00"


def test_ambiguous_or_unsafe_folders_are_reported_not_indexed(tmp_path):
    _store(tmp_path, "dd44", "original.pdf", b"same")
    _store(tmp_path, "ee55", "original.pdf", b"same")
    both = tmp_path / "ff66"
    both.mkdir()
    (both / "original.pdf").write_bytes(b"x")
    (both / "original.docx").write_bytes(b"y")
    _store(tmp_path, "Not-An-Id", "original.pdf", b"z")

    index, problems = rebuild.rebuild_index(tmp_path)

    assert [row["document_id"] for row in index.values()] == ["dd44"]
    assert len(problems) == 3


def test_dry_run_does_not_write(tmp_path, capsys):
    _store(tmp_path, "aa11", "original.pdf", b"%PDF")
    assert rebuild.main(["--contracts-dir", str(tmp_path)]) == 0
    assert not (tmp_path / ".index.json").exists()
    assert "Dry run" in capsys.readouterr().out
