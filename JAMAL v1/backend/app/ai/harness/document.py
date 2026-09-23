from __future__ import annotations

from dataclasses import dataclass, field

from app.documents.intelligence.canonical import DocumentIntelligenceResult, Element, Method
from app.documents.intelligence.hybrid import visual_candidate_pages


@dataclass
class Block:
    id: str
    text: str
    kind: str
    page: int | None = None
    source_type: str = "page"
    source_index: int | None = None
    element: Element | None = None
    heading: str = ""
    needs_vision: bool = False

    def render(self) -> str:
        page = f"page={self.page}" if self.page is not None else f"{self.source_type}={self.source_index}"
        return f"[{self.id}; {self.kind}; {page}; heading={self.heading}]\n{self.text}"

    @property
    def searchable_text(self) -> str:
        return f"{self.heading}\n{self.text}".strip()


@dataclass
class DocumentModel:
    canonical: DocumentIntelligenceResult
    blocks: list[Block] = field(default_factory=list)

    @classmethod
    def build(cls, canonical: DocumentIntelligenceResult) -> "DocumentModel":
        blocks: list[Block] = []
        heading = ""

        for page in canonical.pages:
            represented_tables: set[str] = set()
            page_start = len(blocks)
            for el in sorted(page.elements, key=lambda e: e.reading_order):
                if el.type.value in {"heading", "title"} and (el.text or "").strip():
                    heading = el.text.strip()

                text = el.table.linearized_text() if el.table else (el.text or "")
                if el.table:
                    represented_tables.add(el.table.table_id)

                visual = (
                    bool(el.metadata.get("requires_vision"))
                    or el.method == Method.OCR
                    or el.type.value in {
                        "image", "figure", "checkbox", "signature", "stamp", "form"
                    }
                )
                # Empty OCR/layout artifacts waste context.  Keep an empty block only
                # when its visual region itself may contain contract meaning.
                if not text.strip() and not visual:
                    continue

                blocks.append(
                    Block(
                        f"p{page.page_number}:{el.element_id}",
                        text,
                        el.type.value,
                        page.page_number,
                        element=el,
                        heading=heading,
                        needs_vision=visual,
                    )
                )

            for table in page.tables:
                if table.table_id in represented_tables:
                    continue
                el = Element(
                    element_id=table.table_id,
                    type="table",
                    page=page.page_number,
                    reading_order=len(blocks),
                    table=table,
                    region=table.region,
                )
                text = table.linearized_text()
                if text.strip():
                    blocks.append(
                        Block(
                            f"p{page.page_number}:table:{table.table_id}",
                            text,
                            "table",
                            page.page_number,
                            element=el,
                            heading=heading,
                        )
                    )

            # Some providers can produce authoritative page.text even if structural
            # elements are empty/filtered.  Never drop that page from AI understanding.
            if len(blocks) == page_start and (page.text or "").strip():
                blocks.append(
                    Block(
                        f"p{page.page_number}:page",
                        page.text,
                        "text",
                        page.page_number,
                        heading=heading,
                    )
                )
            elif len(blocks) == page_start and not (page.text or "").strip():
                # Image-only page with no recognized structure: keep a visual page block.
                blocks.append(
                    Block(
                        f"p{page.page_number}:page",
                        "",
                        "image_page",
                        page.page_number,
                        heading=heading,
                        needs_vision=True,
                    )
                )

        # Page-based and logical-unit based representations are alternative address
        # spaces.  Avoid duplicating the same source in the model if a provider ever
        # happens to populate both.
        if not canonical.pages:
            for unit in canonical.logical_units:
                if not (unit.text or "").strip():
                    continue
                blocks.append(
                    Block(
                        f"{unit.source_type}:{unit.index}",
                        unit.text,
                        unit.source_type,
                        source_type=unit.source_type,
                        source_index=unit.index,
                    )
                )

        ids = [block.id for block in blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate document block identifiers")
        return cls(canonical, blocks)

    @property
    def index(self) -> dict[str, Block]:
        return {block.id: block for block in self.blocks}

    @property
    def pages_blocks(self) -> dict[int, list[Block]]:
        mapping: dict[int, list[Block]] = {}
        for block in self.blocks:
            if block.page is not None:
                mapping.setdefault(block.page, []).append(block)
        return mapping

    @property
    def visual_pages(self) -> list[int]:
        """Pages where visual compute can add information beyond clean native text.

        JAMAL v1 centralizes this decision in the deterministic hybrid page
        classifier so DocumentModel and Harness V3 use the same routing rule.
        """
        routed = set(visual_candidate_pages(self.canonical))
        routed.update(
            page
            for page, blocks in self.pages_blocks.items()
            if any(block.needs_vision for block in blocks)
            or not any((block.text or "").strip() for block in blocks)
        )
        return sorted(routed)

    @property
    def is_image_heavy(self) -> bool:
        """Routing signal only: visual compute is required for this document.

        It never asserts meaning; the semantic stages decide that. A document is
        image-heavy when at least one page needs vision or exposes no text.
        """
        return bool(self.visual_pages)
