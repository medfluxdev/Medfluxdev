"""Fail-closed evidence verification regressions.

A location pointer without a concrete source excerpt is navigation metadata, not
proof. Both PDF and DOCX evidence must therefore require review when
``source_text`` is missing, even if the referenced unit exists.
"""

from app.ai.groups.evidence import verify_evidence
from app.documents.extraction.schemas import ExtractionUnit, SourceType, UnitMethod
from app.models.evidence import SourceEvidence


def test_docx_pointer_without_source_text_requires_review():
    units = [
        ExtractionUnit(
            source_type=SourceType.PARAGRAPH,
            index=3,
            text="Mindestvertragslaufzeit 2 Jahre",
            method=UnitMethod.TEXT,
        )
    ]
    evidence = SourceEvidence(
        source_type="paragraph",
        paragraph_index=3,
        source_text=None,
        confidence=0.95,
        requires_review=False,
    )

    verified, issues = verify_evidence(evidence, units)

    assert verified is not None
    assert verified.requires_review is True
    assert verified.confidence == 0.5
    assert any("ohne source_text" in issue for issue in issues)


def test_pdf_page_pointer_without_source_text_requires_review():
    units = [
        ExtractionUnit(
            source_type=SourceType.PAGE,
            index=1,
            text="Vertragsnummer V-123",
            method=UnitMethod.TEXT,
        )
    ]
    evidence = SourceEvidence(
        page=1,
        source_type="page",
        source_text="",
        confidence=1.0,
        requires_review=False,
    )

    verified, issues = verify_evidence(evidence, units)

    assert verified is not None
    assert verified.requires_review is True
    assert verified.confidence == 0.5
    assert any("ohne source_text" in issue for issue in issues)


def test_valid_source_text_keeps_supported_evidence_unflagged():
    units = [
        ExtractionUnit(
            source_type=SourceType.PAGE,
            index=2,
            text="Kündigungsfrist: sechs Monate zum Vertragsende",
            method=UnitMethod.TEXT,
        )
    ]
    evidence = SourceEvidence(
        page=2,
        source_type="page",
        source_text="Kündigungsfrist: sechs Monate",
        confidence=0.9,
        requires_review=False,
    )

    verified, issues = verify_evidence(evidence, units)

    assert verified is not None
    assert verified.requires_review is False
    assert verified.confidence == 0.9
    assert issues == []
