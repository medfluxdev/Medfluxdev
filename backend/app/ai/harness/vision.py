"""Selective, bounded region rendering from the already resolved protected source."""
import base64
from pathlib import Path

import fitz


def region_image(path: Path, block) -> str:
    if path.suffix.lower() != ".pdf" or block.page is None:
        raise ValueError("No trustworthy PDF page for visual region")
    with fitz.open(path) as pdf:
        page = pdf[block.page - 1]
        region = block.element.region if block.element else None
        clip = fitz.Rect(region.x0, region.y0, region.x1, region.y1) if region else page.rect
        clip = clip & page.rect
        if clip.is_empty:
            raise ValueError("Invalid visual region")
        # Selective regions are few, so preserve enough resolution for small legal
        # text, stamps and checkboxes.  Cap both dimensions to avoid uncontrolled
        # multimodal token/memory growth on full-page scans.
        longest = max(clip.width, clip.height)
        scale = min(2.5, 1800 / longest) if longest else 1.0
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, alpha=False)
        return base64.b64encode(pixmap.tobytes("png")).decode("ascii")


def page_image(path: Path, page_number: int, *, longest_side: int = 1600) -> str:
    """Bounded full-page render for V3 page-batch visual compute (sections).

    Section understanding is VISUAL COMPUTE only and stays provisional; the
    global reasoning stage remains the authority. Long-side capping keeps
    multimodal token/memory growth bounded across the whole batch.
    """
    if path.suffix.lower() != ".pdf":
        raise ValueError("No trustworthy PDF page for page-batch rendering")
    with fitz.open(path) as pdf:
        page = pdf[page_number - 1]
        longest = max(page.rect.width, page.rect.height)
        scale = min(2.0, longest_side / longest) if longest else 1.0
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=page.rect, alpha=False)
        return base64.b64encode(pixmap.tobytes("png")).decode("ascii")
