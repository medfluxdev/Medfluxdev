"""DB-free regressions for evidence aliases preserved during detail deduplication."""

from app.contracts.detail.models import EvidenceRef
from app.contracts.detail.service import _dedupe_evidence


def _source(evidence_id: str):
    return {
        "evidence_id": evidence_id,
        "field_ref": "dates.start_date",
        "document_version_id": "version-1",
        "page": 2,
        "paragraph_index": 1,
        "table_index": None,
        "source_type": "paragraph",
        "snippet": "Beginning 01.01.2025",
        "confidence": 0.7,
        "requires_review": False,
        "bbox": None,
    }


def test_dedupe_preserves_every_original_evidence_id():
    refs = [_source("db-evidence-1"), _source("db-evidence-2"),
            _source("recovered:dates.start_date")]
    result = _dedupe_evidence(refs)
    assert len(result) == 1
    assert set(result[0]["merged_evidence_ids"]) == {
        "db-evidence-1", "db-evidence-2", "recovered:dates.start_date",
    }
    assert result[0]["evidence_id"] == "recovered:dates.start_date"
    dto = EvidenceRef.model_validate(result[0])
    assert "db-evidence-1" in dto.merged_evidence_ids


def test_dedupe_aliases_do_not_cross_distinct_sources():
    first = _source("evidence-a")
    second = {**_source("evidence-b"), "page": 3}
    result = _dedupe_evidence([first, second])
    assert len(result) == 2
    assert all("evidence-b" not in item["merged_evidence_ids"] for item in result if item["page"] == 2)


def test_dedupe_aliases_are_order_independent():
    refs = [_source("db-b"), _source("recovered:dates.start_date"), _source("db-a")]
    forward = _dedupe_evidence(refs)
    backward = _dedupe_evidence(list(reversed(refs)))
    assert forward == backward
    assert forward[0]["merged_evidence_ids"] == [
        "db-a", "db-b", "recovered:dates.start_date",
    ]


def test_dedupe_does_not_mutate_input_or_share_alias_lists():
    first = _source("db-a")
    first["merged_evidence_ids"] = ["older-id"]
    second = _source("db-b")
    result = _dedupe_evidence([first, second])
    assert result[0]["merged_evidence_ids"] == ["db-a", "db-b", "older-id"]
    result[0]["merged_evidence_ids"].append("new-id")
    assert first["merged_evidence_ids"] == ["older-id"]
    assert "merged_evidence_ids" not in second
