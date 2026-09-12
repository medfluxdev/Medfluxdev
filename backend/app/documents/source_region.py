"""Narrowest trustworthy source geometry for fact snippets (PR-5 UAT D).

Deterministic, non-AI resolution of a fact snippet to the smallest region of
the ORIGINAL PDF in which the text provably exists:

- Primary: PyMuPDF text-layer search (exact, PDF-point coordinates that the
  frontend PdfViewer already transforms). Honest: a hit proves the characters
  are at exactly that place.
- Fallback: canonical atomic units (validated OCR word / table cell / line)
  projected back into the mediabox via page_view_to_mediabox.
- Oversize guard: any region covering > 50% of the page is reported
  `coarse`, never `exact`.

Never invents a region: `none` is the honest result when nothing resolveable.
"""

from __future__ import annotations

import re
from typing import Optional

import fitz

from app.documents.intelligence.canonical import BoundingRegion, DocumentIntelligenceResult
from app.documents.intelligence.highlight import page_view_to_mediabox, resolve_target_atomic

_WORD_TOKEN = re.compile(r"[^\W\d_]{3,}", re.UNICODE)
_NUMERIC_TOKEN = re.compile(r"\d{2,}")

_OVERSIZE_RATIO = 0.5


def _robust_token(snippet: str) -> Optional[str]:
    words = _WORD_TOKEN.findall(snippet)
    if not words:
        numbers = _NUMERIC_TOKEN.findall(snippet)
        return max(numbers, key=len) if numbers else None
    return max(words, key=len)


def _union_rects(rects) -> Optional["fitz.Rect"]:
    union = None
    for r in rects:
        union = fitz.Rect(r) if union is None else union | r
    return union


def _search_region(page: "fitz.Page", snippet: str) -> Optional["fitz.Rect"]:
    """Exact text-layer hits in the original PDF (deterministic)."""
    rects = page.search_for(snippet)
    if not rects:
        token = _robust_token(snippet)
        if token and len(token) >= 3:
            rects = page.search_for(token)
    return _union_rects(rects)


def _to_pdf_bbox(r: BoundingRegion) -> list[float]:
    return [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]


def _union_regions(boxes: list[BoundingRegion]) -> BoundingRegion:
    return BoundingRegion(
        page=boxes[0].page,
        x0=min(b.x0 for b in boxes),
        y0=min(b.y0 for b in boxes),
        x1=max(b.x1 for b in boxes),
        y1=max(b.y1 for b in boxes),
    )


def _resolve_canonical(
    snippet: str, canonical: DocumentIntelligenceResult, doc: "fitz.Document", page_hint
) -> Optional[dict]:
    """Atomic canonical fallback (OCR word / table cell / line)."""
    for page in canonical.pages:
        if page_hint is not None and page.page_number != page_hint:
            continue
        text = page.text or ""
        offset = text.find(snippet)
        length = len(snippet)
        if offset < 0:
            folded = snippet.casefold()
            if len(folded) == length:
                offset = text.casefold().find(folded)
        if offset < 0:
            token = _robust_token(snippet)
            if token:
                offset = text.find(token)
                length = len(token)
        if offset < 0:
            continue
        resolution = resolve_target_atomic(page, offset, length)
        status = None
        if resolution.status in ("EXACT_WORD", "VALIDATED_TABLE_CELL", "EXACT_LINE"):
            status = "exact"
        elif resolution.status == "COARSE_FALLBACK":
            status = "coarse"
        else:
            continue
        if not resolution.boxes:
            continue
        try:
            pdf_page = doc.load_page(page.page_number - 1)
            rotation = pdf_page.rotation or 0
            med_w, med_h = pdf_page.rect.width, pdf_page.rect.height
            mapped = [
                page_view_to_mediabox(b, rotation, med_w=med_w, med_h=med_h)
                for b in resolution.boxes
                if b is not None
            ]
        except Exception:
            continue
        if not mapped:
            continue
        return {
            "status": status,
            "page": page.page_number,
            "bbox": _to_pdf_bbox(_union_regions(mapped)),
            "bbox_space": "pdf_points",
            "method": "canonical_atomic",
        }
    return None


def resolve_narrowest_region(
    snippet: str,
    *,
    pdf_bytes: bytes,
    canonical: Optional[DocumentIntelligenceResult] = None,
    page_hint: Optional[int] = None,
) -> dict:
    """Resolve a fact snippet to its narrowest trustworthy PDF region."""
    if not snippet or not pdf_bytes:
        return _none()
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return _none()

    if page_hint is not None and 1 <= page_hint <= doc.page_count:
        candidates = [page_hint - 1]
    else:
        candidates = list(range(doc.page_count))

    for idx in candidates:
        page = doc.load_page(idx)
        union = _search_region(page, snippet)
        if union is None:
            continue
        page_area = page.rect.width * page.rect.height
        status = "exact"
        if page_area > 0 and (union.width * union.height) > _OVERSIZE_RATIO * page_area:
            status = "coarse"
        return {
            "status": status,
            "page": idx + 1,
            "bbox": [
                round(union.x0, 2),
                round(union.y0, 2),
                round(union.x1, 2),
                round(union.y1, 2),
            ],
            "bbox_space": "pdf_points",
            "method": "pdf_text_layer",
        }

    if canonical is not None:
        region = _resolve_canonical(snippet, canonical, doc, page_hint)
        if region is not None:
            return region
    return _none()


def _none() -> dict:
    return {
        "status": "none",
        "page": None,
        "bbox": None,
        "bbox_space": "pdf_points",
        "method": None,
    }