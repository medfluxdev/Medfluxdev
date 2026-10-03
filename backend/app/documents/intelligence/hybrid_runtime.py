"""Runtime bridge for scanned-contract OCR + vision processing.

This is part of the JAMAL v1 project copy.  It wires the canonical OCR/layout
result to bounded local page/region rendering used by Harness V3.

It does not make semantic decisions and never talks to cloud services.
"""
from __future__ import annotations

from pathlib import Path

from app.ai.harness.vision import page_image, region_image
from app.documents.intelligence.hybrid import PageRoute, classify_page


class HybridVisionRuntime:
    """Bounded render access for pages that actually need visual compute."""

    def __init__(self, source_path: Path, canonical, *, longest_side: int = 1800):
        self.source_path = Path(source_path)
        self.canonical = canonical
        self.longest_side = max(800, min(int(longest_side), 2400))
        self._routes = {
            page.page_number: classify_page(page)
            for page in getattr(canonical, "pages", [])
        }

    @property
    def routes(self) -> dict[int, str]:
        return {page: route.value for page, route in self._routes.items()}

    @property
    def visual_pages(self) -> list[int]:
        return [
            page
            for page, route in self._routes.items()
            if route in {PageRoute.VISION_REQUIRED, PageRoute.HYBRID_REQUIRED}
        ]

    def render_page(self, page_number: int) -> str:
        route = self._routes.get(page_number)
        if route not in {PageRoute.VISION_REQUIRED, PageRoute.HYBRID_REQUIRED}:
            raise ValueError("Page does not require visual compute")
        return page_image(
            self.source_path,
            page_number,
            longest_side=self.longest_side,
        )

    def render_region(self, block) -> str:
        return region_image(self.source_path, block)
