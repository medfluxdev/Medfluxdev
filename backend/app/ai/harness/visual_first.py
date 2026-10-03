"""Isolated Visual-First evidence experiment; NO trusted contract writes.

The source PDF image is the authority. Two independent readings are retained.
A reconciled item is only a candidate for the existing Harness V3 evidence gate.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Iterable

VISION_PROMPT = (
    "Inspect this ORIGINAL contract-page IMAGE, independently of OCR. "
    "Transcribe literal visible text, including amount AND its nearby label, "
    "equipment names, table row/column context, dates and obscured handwriting. "
    "Quote precisely, identify the page and local region when possible. "
    "Mark missing or obscured text as uncertain. NEVER guess unseen content. "
    "Output structured observations only; no contract decisions."
)
REVIEW_PROMPT = (
    "Reinspect the ORIGINAL page image for this disputed observation, independently "
    "grounding what is visibly present. Compare both previous readings only AFTER "
    "looking at the image. Return an observation with quote, label, region and "
    "uncertainty. If obscured, return uncertain. Do not self-certify a fact."
)

@dataclass(frozen=True)
class Observation:
    page: int
    label: str
    value: str
    quote: str
    source: str
    region: tuple[float, float, float, float] | None = None
    uncertain: bool = False
    source_sha256: str = ""

    def __post_init__(self):
        if self.page < 1 or self.source not in {"vision", "ocr", "review"}:
            raise ValueError("Invalid observation source/page")
        if self.region is not None and (len(self.region) != 4 or
                                        self.region[2] < self.region[0] or
                                        self.region[3] < self.region[1]):
            raise ValueError("Invalid region")

@dataclass
class Reconciled:
    page: int
    label: str
    value: str
    status: str  # corroborated | vision_only | ocr_only | disputed | uncertain
    observations: list[Observation] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    # Deliberately never 'verified': only Harness V3 with ORIGINAL provenance can prove.
    requires_review: bool = True


def norm(value: str) -> str:
    return " ".join((value or "").casefold().split())


def amount(value: str) -> str | None:
    """Normalize unambiguous German EUR literals, not their contractual meaning."""
    found = re.fullmatch(r"\s*(?:\u20AC\s*)?([0-9][0-9. ]*)(?:,([0-9]{2}))?\s*(?:\u20AC|EUR)?\s*", value, re.I)
    if not found:
        return None
    whole = re.sub(r"[. ]", "", found.group(1))
    return str(int(whole)) + "." + (found.group(2) or "00")


def same_value(a: str, b: str) -> bool:
    x, y = amount(a), amount(b)
    return (x == y) if x is not None and y is not None else norm(a) == norm(b)


def region_overlap(a, b) -> bool:
    if a is None or b is None:
        return True  # Missing region must trigger review elsewhere, not false certainty.
    return max(a[0], b[0]) <= min(a[2], b[2]) and max(a[1], b[1]) <= min(a[3], b[3])


def reconcile(vision: Iterable[Observation], ocr: Iterable[Observation]) -> list[Reconciled]:
    """Never match identical numbers on different pages, labels, or disjoint regions."""
    a, b = list(vision), list(ocr)
    if any(x.source != "vision" for x in a) or any(x.source != "ocr" for x in b):
        raise ValueError("Initial reads must be independent")
    rows: list[Reconciled] = []
    consumed: set[int] = set()
    for v in a:
        candidates = [(j, x) for j, x in enumerate(b) if j not in consumed and
                      x.page == v.page and norm(x.label) == norm(v.label) and
                      region_overlap(v.region, x.region)]
        exact = [(j, x) for j, x in candidates if same_value(v.value, x.value)]
        if v.uncertain or not v.quote.strip() or not v.label.strip():
            rows.append(Reconciled(v.page, v.label, v.value, "uncertain", [v],
                                   ["vision_ambiguous_or_missing_context"]))
        elif len(exact) == 1 and len(candidates) == 1 and not exact[0][1].uncertain:
            j, o = exact[0]
            consumed.add(j)
            reasons = []
            if v.region is None or o.region is None:
                reasons.append("location_requires_original_page_check")
            if not o.quote.strip():
                reasons.append("ocr_quote_missing")
            rows.append(Reconciled(v.page, v.label, v.value,
                                   "corroborated" if not reasons else "uncertain",
                                   [v, o], reasons))
        elif candidates:
            # Repeated same-label amounts or conflicting values must never auto-bind.
            for j, _ in candidates:
                consumed.add(j)
            rows.append(Reconciled(v.page, v.label, v.value, "disputed",
                                   [v, *(o for _, o in candidates)],
                                   ["value_disagreement_or_duplicate"]))
        else:
            rows.append(Reconciled(v.page, v.label, v.value, "vision_only",
                                   [v], ["ocr_missing"]))
    for j, x in enumerate(b):
        if j not in consumed:
            rows.append(Reconciled(x.page, x.label, x.value,
                                   "uncertain" if x.uncertain else "ocr_only",
                                   [x], ["vision_missing"]))
    return rows


async def run_independent(
    page_images: dict[int, bytes],
    vision_reader: Callable[[int, bytes, str], Awaitable[list[Observation]]],
    ocr_reader: Callable[[], Awaitable[list[Observation]]],
    *,
    max_pages: int = 20,
    timeout_seconds: float = 240.0,
    reviewer: Callable[[int, bytes, str, Reconciled], Awaitable[Observation | None]] | None = None,
    max_reviews: int = 2,
) -> tuple[list[Reconciled], dict]:
    """Concurrent INDEPENDENT first passes; no OCR passed to vision_reader.

    Caller must use the currently selected MedFlux vision model in both vision_reader
    and reviewer. The OCR reader must read the ORIGINAL PDF independently.
    All outputs remain review-required, with original image hashes in provenance.
    """
    if not page_images or len(page_images) > max_pages or max_pages < 1:
        raise ValueError("Invalid page budget")
    if timeout_seconds <= 0 or max_reviews < 0:
        raise ValueError("Invalid resource budget")
    if any(not isinstance(img, bytes) or not img for img in page_images.values()):
        raise ValueError("Original page images must be nonempty bytes")
    hashes = {p: hashlib.sha256(data).hexdigest() for p, data in page_images.items()}
    async def all_visual():
        reads = await asyncio.gather(*[
            vision_reader(page, image, VISION_PROMPT)
            for page, image in sorted(page_images.items())
        ])
        return [obs for row in reads for obs in row]
    # Both tasks start before either result is consumed.
    visual, optical = await asyncio.wait_for(
        asyncio.gather(all_visual(), ocr_reader()), timeout=timeout_seconds)
    for obj in visual + optical:
        if obj.page not in hashes or (obj.source_sha256 and obj.source_sha256 != hashes[obj.page]):
            raise ValueError("Evidence source/page hash mismatch")
    aligned = reconcile(visual, optical)
    attempted = 0
    if reviewer is not None:
        for row in aligned:
            if row.status == "corroborated" or attempted >= max_reviews:
                continue
            attempted += 1
            review = await asyncio.wait_for(
                reviewer(row.page, page_images[row.page], REVIEW_PROMPT, row),
                timeout=timeout_seconds)
            if review is not None:
                if review.source != "review" or review.page != row.page or (
                    review.source_sha256 and review.source_sha256 != hashes[row.page]
                ):
                    raise ValueError("Reviewer evidence provenance mismatch")
                row.observations.append(review)
                row.reasons.append("review_observation_requires_independent_harness_verification")
    return aligned, {
        "image_sha256_by_page": hashes, "vision_count": len(visual),
        "ocr_count": len(optical), "review_attempts": attempted,
        "all_results_require_harness_verification": True,
    }
