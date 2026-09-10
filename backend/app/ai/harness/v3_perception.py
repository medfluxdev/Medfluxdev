"""Provider-neutral perception helpers for Contract Intelligence Harness V3.

Perception records EVIDENCE only. It explicitly never decides legal/commercial
meaning: whether an option is selected, which option is applicable, how a
number is used, or which document is authoritative is decided by Qwen in the
semantic stages. These helpers may fail or return empty results silently; they
are never a mandatory semantic gateway and never block vision/global stages.
"""
from __future__ import annotations

import re

from app.ai.harness.document import DocumentModel
from app.ai.harness.models import OptionCluster, OptionItem, VisualRegionReference
from app.documents.intelligence.canonical import DocumentIntelligenceResult, Element

# Lines like "Guard TOP ............... 1.650,00 EUR" or "Service 350 EUR/Jahr".
_PRICE_RE = re.compile(
    r"(?P<amount>\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+)\s*(?:EUR|€)(?:\s*/\s*(?:Jahr|Monat|jahr|monat|call|Stunde|Einheit))?",
    re.IGNORECASE,
)
_LABEL_STRIP_RE = re.compile(r"^[\s\-.:•·,;|()]+")
_SELECTION_MARKERS = ("[x]", "[✓]", "☑", "(x)", "(m)", "✓", "✔", "x ", "X ")
_SMALL_CONTROL_KINDS = {"checkbox", "form", "stamp", "signature", "image", "figure"}


def _region_of(element: Element, block_id: str) -> VisualRegionReference | None:
    region = element.region if element else None
    page = element.page if element is not None and element.page is not None else None
    if region is None or page is None:
        return None
    return VisualRegionReference(
        page=page,
        x0=region.x0,
        y0=region.y0,
        x1=region.x1,
        y1=region.y1,
        block_id=block_id,
    )


def _option_item(line: str, amount: re.Match, block, nearby: list[str], page_model) -> OptionItem:
    start = amount.start()
    head = line[:start]
    head = _LABEL_STRIP_RE.sub("", head).strip()
    tokens = head.split()
    meaningful = [
        token
        for token in tokens
        if token.strip("()[]*•·") and token.strip("()[]*•·").lower() not in {"x", "m", "✓", "✔", "☑"}
    ]
    label = " ".join(meaningful[:8]).strip()
    label = re.sub(r"[\s.\-–:;|·]+$", "", label).strip()
    if not label or label.isdigit():
        label = "Betrag"
    lower = line.lower()
    hint = any(marker in lower for marker in _SELECTION_MARKERS)

    element = block.element
    region = _region_of(element, block.id) if element else None
    control_region = None
    if region is not None and element is not None and page_model is not None:
        for candidate in page_model.elements:
            if candidate.type.value not in _SMALL_CONTROL_KINDS:
                continue
            if candidate is element:
                continue
            candidate_region = candidate.region
            if candidate_region is None:
                continue
            within_y = abs((candidate_region.y0 + candidate_region.y1) / 2 - (region.y0 + region.y1) / 2) <= 45
            small = candidate_region.x1 - candidate_region.x0 <= 45 and candidate_region.y1 - candidate_region.y0 <= 45
            if within_y and small:
                control_region = VisualRegionReference(
                    page=block.page,
                    x0=candidate_region.x0,
                    y0=candidate_region.y0,
                    x1=candidate_region.x1,
                    y1=candidate_region.y1,
                    block_id=candidate.element_id,
                )
                break
    return OptionItem(
        label=label,
        price_text=amount.group(0),
        block_id=block.id,
        region=region,
        control_region=control_region,
        nearby_text=[fragment[:400] for fragment in nearby if fragment],
        selection_hint=True if hint else None,
    )


def perceive_option_clusters(
    canonical: DocumentIntelligenceResult, document: DocumentModel
) -> list[OptionCluster]:
    """Trace observed option/price clusters and candidate selection controls.

    Deterministic, out-of-context evidence capture. The result is a hint map for
    Qwen's semantic stages only. Never raises and never asserts applicability.
    """
    clusters: dict[tuple[str, int], OptionCluster] = {}
    order: list[tuple[str, int]] = []
    try:
        cluster_label = ""
        pages = {page.page_number: page for page in canonical.pages}
        for block in document.blocks:
            if block.kind in {"heading", "title"} and (block.text or "").strip():
                cluster_label = block.text.strip()[:120]
            lines = (block.text or "").splitlines()
            for line_index, line in enumerate(lines):
                match = _PRICE_RE.search(line)
                if match is None:
                    continue
                nearby = []
                if line_index > 0:
                    nearby.append(lines[line_index - 1])
                if line_index + 1 < len(lines):
                    nearby.append(lines[line_index + 1])
                nearby.append((block.text or "")[:240])
                page_key = block.page if block.page is not None else 0
                item = _option_item(line, match, block, nearby, pages.get(block.page))
                key = (cluster_label, page_key)
                if key not in clusters:
                    clusters[key] = OptionCluster(cluster_label=cluster_label)
                    order.append(key)
                clusters[key].options.append(item)
    except Exception:
        return []
    return [clusters[key] for key in order if clusters[key].options]