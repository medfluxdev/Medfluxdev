"""Experimental provider-neutral skeleton for scanned-contract understanding.

This file intentionally does NOT integrate with production MedFlux. It defines
routing/fusion contracts that OpenCode can exercise against real documents.

No cloud calls, no database writes, no contract-specific rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class PageRoute(str, Enum):
    TEXT_NATIVE = "text_native"
    OCR_REQUIRED = "ocr_required"
    VISION_REQUIRED = "vision_required"
    HYBRID_REQUIRED = "hybrid_required"


@dataclass(frozen=True)
class Region:
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class SourceFragment:
    page: int
    text: str
    source_type: str
    region: Region | None = None
    confidence: float | None = None
    element_id: str | None = None


@dataclass
class PageSignals:
    page: int
    native_text_chars: int = 0
    ocr_text_chars: int = 0
    has_ocr_elements: bool = False
    has_table: bool = False
    has_form_controls: bool = False
    has_visual_only_elements: bool = False
    extraction_quality: float | None = None


@dataclass
class FusedPage:
    page: int
    route: PageRoute
    native_fragments: list[SourceFragment] = field(default_factory=list)
    ocr_fragments: list[SourceFragment] = field(default_factory=list)
    visual_observations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def evidence_fragments(self) -> list[SourceFragment]:
        # Prefer exact textual evidence. Vision remains a supporting observation,
        # not a substitute for textual evidence when text is recoverable.
        return [*self.native_fragments, *self.ocr_fragments]


@dataclass(frozen=True)
class FactProposal:
    field_ref: str
    value: Any
    page: int
    quote: str | None = None
    region: Region | None = None
    source_type: str = "semantic"
    confidence: float | None = None


@dataclass(frozen=True)
class VerifiedFact:
    proposal: FactProposal
    accepted: bool
    matched_fragment: SourceFragment | None = None
    reason: str = ""
    requires_review: bool = False


def classify_page(signals: PageSignals) -> PageRoute:
    """Deterministic compute routing only; never decides contract meaning."""
    native_good = signals.native_text_chars >= 80
    ocr_good = signals.ocr_text_chars >= 80

    if native_good and not (
        signals.has_visual_only_elements or signals.has_form_controls
    ):
        return PageRoute.TEXT_NATIVE

    if native_good and (
        signals.has_table
        or signals.has_form_controls
        or signals.has_visual_only_elements
    ):
        return PageRoute.HYBRID_REQUIRED

    if ocr_good and not signals.has_visual_only_elements:
        return PageRoute.OCR_REQUIRED

    if ocr_good:
        return PageRoute.HYBRID_REQUIRED

    return PageRoute.VISION_REQUIRED


def normalize_for_match(text: str) -> str:
    return " ".join(text.split()).casefold()


def verify_quote(
    proposal: FactProposal,
    pages: Iterable[FusedPage],
) -> VerifiedFact:
    """Fail closed when a material proposal cannot be tied to source evidence."""
    page = next((item for item in pages if item.page == proposal.page), None)
    if page is None:
        return VerifiedFact(proposal, False, reason="page_not_found", requires_review=True)

    if proposal.quote:
        needle = normalize_for_match(proposal.quote)
        if needle:
            for fragment in page.evidence_fragments:
                if needle in normalize_for_match(fragment.text):
                    return VerifiedFact(
                        proposal,
                        True,
                        matched_fragment=fragment,
                        reason="exact_text_located",
                    )

    # Region-only visual support is useful, but deliberately weaker than exact
    # textual evidence. Keep it reviewable rather than silently accepting it.
    if proposal.region is not None and page.visual_observations:
        return VerifiedFact(
            proposal,
            False,
            reason="visual_region_requires_review",
            requires_review=True,
        )

    return VerifiedFact(
        proposal,
        False,
        reason="evidence_not_located",
        requires_review=True,
    )


def choose_recovery_pages(
    pages: Iterable[FusedPage],
    missing_material_fields: Iterable[str],
) -> list[int]:
    """Return a bounded set of pages for targeted visual recovery.

    The caller should additionally use field/page relevance from the existing
    semantic packs. This function intentionally does not encode ABIOMED facts.
    """
    missing = list(missing_material_fields)
    if not missing:
        return []

    candidates = [
        page.page
        for page in pages
        if page.route in {PageRoute.VISION_REQUIRED, PageRoute.HYBRID_REQUIRED}
    ]
    return candidates[:4]
