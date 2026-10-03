"""Deterministic routing for hybrid scanned-contract understanding.

This module decides HOW a page should be processed, never WHAT the contract
means. It is provider-neutral and deliberately contains no contract-specific
facts.
"""
from __future__ import annotations

from enum import Enum

from app.documents.intelligence.canonical import Method, Page


class PageRoute(str, Enum):
    TEXT_NATIVE = "text_native"
    OCR_REQUIRED = "ocr_required"
    VISION_REQUIRED = "vision_required"
    HYBRID_REQUIRED = "hybrid_required"


_VISUAL_TYPES = {"image", "figure", "checkbox", "signature", "stamp", "form"}
_STRUCTURAL_TYPES = {"table", "table_cell"}


def classify_page(page: Page) -> PageRoute:
    """Choose the minimum reliable compute path for one page.

    Routing is deterministic and based only on canonical recognition/layout
    signals. It never asserts legal or commercial meaning.
    """
    text_chars = len((page.text or "").strip())
    elements = list(page.elements or [])
    has_ocr = any(getattr(el, "method", None) == Method.OCR for el in elements)
    has_visual = any(getattr(getattr(el, "type", None), "value", "") in _VISUAL_TYPES for el in elements)
    has_structure = bool(page.tables) or any(
        getattr(getattr(el, "type", None), "value", "") in _STRUCTURAL_TYPES
        for el in elements
    )
    requires_vision = any(bool((getattr(el, "metadata", None) or {}).get("requires_vision")) for el in elements)

    # A healthy native-text page should stay on the cheapest/highest-fidelity path.
    if text_chars >= 120 and not has_ocr and not has_visual and not requires_vision:
        return PageRoute.TEXT_NATIVE

    # OCR text can be semantically useful while layout/checkbox/table relationships
    # still require visual confirmation.
    if text_chars >= 80 and (has_visual or has_structure or requires_vision):
        return PageRoute.HYBRID_REQUIRED

    if text_chars >= 80 and has_ocr:
        return PageRoute.OCR_REQUIRED

    # Sparse pages with any recovered text benefit from OCR + vision rather than
    # discarding the text channel.
    if text_chars > 0:
        return PageRoute.HYBRID_REQUIRED

    return PageRoute.VISION_REQUIRED


def visual_candidate_pages(page_source) -> list[int]:
    """Return pages where vision adds information beyond clean native text."""
    pages = getattr(page_source, "pages", page_source)
    return [
        page.page_number
        for page in pages
        if classify_page(page) in {PageRoute.VISION_REQUIRED, PageRoute.HYBRID_REQUIRED}
    ]


def route_summary(page_source) -> dict[int, str]:
    pages = getattr(page_source, "pages", page_source)
    return {page.page_number: classify_page(page).value for page in pages}
