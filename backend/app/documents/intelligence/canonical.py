"""Medflux-eigenes kanonisches Dokumentmodell (STEP 8B, Dokument-Intelligence).

Provider-neutral: Dieses Paket darf NICHT direkt von Docling/einem konkreten
Anbieter abhaengen. Jeder Dokument-Intelligence-Provider (Docling, PaddleOCR/
PP-StructureV3, nativer PDF-Provider, Tesseract-Fallback) liefert seine
Ergebnisse in DIESER kanonischen Darstellung – Downstream-Code (Suche,
Quell-Navigation, KI-Extraktion) kennt nur dieses Modell.

Designziele (klein, erweiterbar, verlustfrei):
- Seiten/Elemente in Lesereihenfolge mit echten Koordinaten (PDF-Punkte,
  Ursprung oben links, y nach unten – identisch zu PyMuPDF `page.rect`).
- Tabellen sind first class: Zeilen/Spalten/Spans/Zellen mit Beleg (Text,
  Region). Text wird NIE permanent zu reinem Fliesstext plattgebuegelt, damit
  Label->Wert-Beziehungen (z. B. "Full Service | 5.916,67 EUR | monatlich")
  erhalten bleiben.
- Deterministischer kanonischer Seiten-Text + Span-Offsets: Element.Text ist
  ueber (offset, length) auf den Seiten-Text abbildbar; darueber laeuft die
  spaetere Kette Suche -> Span -> Element -> Seite -> Region -> Original-PDF.
- Provenienz: Quell-Hash, Provider, Provider-Version, OCR-/Layout-Konfiguration
  – getrennt von jeder KI-Konfidenz (KI-Fakten-Konfidenz bleibt downstream).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.documents.geometry import PdfRect

# Version des kanonischen Modells (Manifest/Reproduzierbarkeit).
CANONICAL_SCHEMA_VERSION = "1.3.0"


class GeometryPrecision(str, Enum):
    """Wie exakt eine Quell-Position die HERKUNFT eines Texts belegt.

    Rangfolge (feinste = klarste Belegung):
    - WORD:             echtes atomares Wort-Box (OCR-Wort-Erkennung)
    - LINE:             volle OCR-Zeilen-Box (Wort nicht feiner verfuegbar)
    - TABLE_CELL:       validierte Tabellenzelle (Zell-Struktur + OCR-Inhalt)
    - COARSE_ELEMENT:   nur Element-Box (Paragraph/Zeile auf Elementebene)
    - ESTIMATED:        räumlich geschaetzt (z. B. proportional geteilt), NIE exakt
    """

    WORD = "word"
    LINE = "line"
    TABLE_CELL = "table_cell"
    COARSE_ELEMENT = "coarse_element"
    ESTIMATED = "estimated"


class ElementType(str, Enum):
    """Rollen eines Layout-Elements; bewusst erweiterbar (Provider-agnostisch)."""

    PARAGRAPH = "paragraph"
    TEXT = "text"
    HEADING = "heading"
    TITLE = "title"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_NUMBER = "page_number"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_CELL = "table_cell"
    IMAGE = "image"
    FIGURE = "figure"
    CAPTION = "caption"
    FOOTNOTE = "footnote"
    FORMULA = "formula"
    OTHER = "other"
    CHECKBOX = "checkbox"
    FORM = "form"
    SIGNATURE = "signature"
    STAMP = "stamp"


class BoundingRegion(BaseModel):
    """Begrenzungsrechteck auf EINER Original-PDF-Seite (Punkte, 1-basiert)."""

    page: int = Field(ge=1)
    x0: float = Field(ge=0.0)
    y0: float = Field(ge=0.0)
    x1: float = Field(ge=0.0)
    y1: float = Field(ge=0.0)

    @classmethod
    def from_pdf_rect(cls, page: int, rect: PdfRect) -> "BoundingRegion":
        return cls(page=page, x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1)

    def as_pdf_rect(self) -> PdfRect:
        return PdfRect(x0=self.x0, y0=self.y0, x1=self.x1, y1=self.y1)

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)


class TextSpan(BaseModel):
    """Stabiler Zeiger in den kanonischen Seiten-Text (offset, length)."""

    offset: int = Field(ge=0)
    length: int = Field(ge=1)

    def to(self) -> int:
        return self.offset + self.length


class WordRegion(BaseModel):
    """EIN exaktes Wort-/Segment-Box auf der Original-PDF-Seite.

    `granularity` benennt ehrlich, wie fein die Geometrie ist:
    - "word": echtes Wort-Box (Provider liefert es)
    - "segment": Zeilen-/Segment-Box (Docling ProvenanceItem charspan + bbox)
    - "line": ganze Zeile (kein Segment feiner aufgeloest)
    - "element": nur Element-Box verfuegbar (Fallback, nie still)
    `offset/length` zeigen in den kanonischen Seiten-Text (page.text).
    """

    text: str = ""
    offset: int = Field(ge=0)
    length: int = Field(ge=1)
    region: BoundingRegion
    granularity: Literal["word", "segment", "line", "element"] = "segment"

    def to(self) -> int:
        return self.offset + self.length


class AtomicUnit(BaseModel):
    """Atomare Geometrie-Einheit fuer exakte Quell-Navigation.

    Geometrie-EIGENTUEMER ist der atomare OCR-/Struktur-Provider (RapidOCR,
    Docling-Tabellenstruktur) – NICHT die Docling-Paragraph-Provenienz. Die
    Invariante fuer "exakt" lautet: der ZIEL-Text ist vollstaendig im
    `text` dieser Einheit enthalten UND deren `bbox` liegt auf der
    Original-PDF-Seite. Grobe Element-Boxen werden hier NIEMALS als exakt
    markiert (precision != COARSE_ELEMENT).

    - kind "ocr_word": Wort aus atomarer OCR (RapidOCR word_results)
    - kind "ocr_line": Zeile aus atomarer OCR (volles Zeilenresultat)
    - kind "docling_cell": validierte Tabellenzelle (Zell-BBox + OCR-Inhalt)
    `canonical_offset/canonical_length` (falls belegt) zeigen deterministisch
    in `page.text`; `aligned=True` heisst: `text` ist per Text-Matching an
    diesen kanonischen Ausschnitt gebunden (Containment-bewiesen).
    """

    unit_id: str
    kind: Literal["ocr_word", "ocr_line", "docling_cell"]
    text: str
    page: int = Field(ge=1)
    bbox: BoundingRegion
    precision: GeometryPrecision = GeometryPrecision.LINE
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    provider: str = "rapidocr"
    parent_line_id: Optional[str] = None
    canonical_offset: Optional[int] = Field(default=None, ge=0)
    canonical_length: Optional[int] = Field(default=None, ge=1)
    aligned: bool = False
    source_ref: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)

    def to(self) -> Optional[int]:
        if self.canonical_offset is None or self.canonical_length is None:
            return None
        return self.canonical_offset + self.canonical_length


class Method(str, Enum):
    """Woher stammt der Inhalt eines Elements (Recognition-, nicht KI-Ebene)."""

    NATIVE = "native"  # eingebettete PDF-Textschicht
    OCR = "ocr"
    LAYOUT = "layout"
    STRUCTURE = "structure"
    UNKNOWN = "unknown"


class Element(BaseModel):
    """Ein Layout-/Textelement einer Seite in Lesereihenfolge."""

    element_id: str
    type: ElementType = ElementType.TEXT
    text: str = ""
    page: int = Field(ge=1)
    region: Optional[BoundingRegion] = None
    spans: list[TextSpan] = Field(default_factory=list)
    reading_order: int = Field(ge=0)
    method: Method = Method.UNKNOWN
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    table: Optional["TableStructure"] = None
    children: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    word_regions: list[WordRegion] = Field(default_factory=list)


class Cell(BaseModel):
    """Eine Tabellenzelle mit Position, Span und Beleg."""

    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    row_span: int = Field(default=1, ge=1)
    column_span: int = Field(default=1, ge=1)
    text: str = ""
    region: Optional[BoundingRegion] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    element_refs: list[str] = Field(default_factory=list)


class TableStructure(BaseModel):
    """First-class Tabellenrepräsentation (auch ohne Fliesstext-Persistenz)."""

    table_id: str
    page: int = Field(ge=1)
    region: Optional[BoundingRegion] = None
    num_rows: int = Field(default=0, ge=0)
    num_cols: int = Field(default=0, ge=0)
    cells: list[Cell] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    headers: list[str] = Field(default_factory=list)

    def cell(self, row: int, col: int) -> Optional[Cell]:
        """Liefert die (erste) Zelle an Position (row, col) oder None."""
        for c in self.cells:
            if c.row_index == row and c.column_index == col:
                return c
        return None

    def row_texts(self) -> list[list[str]]:
        """Zeilenweise Zelltexte (ohne Spans); best-effort fuers Rendering/Debug."""
        rows: list[list[str]] = []
        for row in range(self.num_rows):
            texts: list[str] = []
            for col in range(self.num_cols):
                c = self.cell(row, col)
                texts.append(c.text if c else "")
            rows.append(texts)
        return rows

    def linearized_text(self) -> str:
        """Deterministische, strukturierte Textdarstellung (Label|Wert je Zelle).

        Behaelt die Label->Wert-Zuordnung bei; dient als `text` des
        Tabellen-Elements und damit der Volltextsuche.
        """
        return "\n".join(" | ".join(cells) for cells in self.row_texts())


class Page(BaseModel):
    """Eine Seite mit kanonischem Text und Elementen in Lesereihenfolge.

    `width_pt/height_pt` sind die Abmessungen des kanonischen (Recognition-)
    Seitenraums – bei Docling die (rotationsbereinigte) Pipeline-Seite.
    `original_width_pt/original_height_pt/pdf_rotation` beschreiben das
    ORIGINALE PDF-Dreh-CropSystem, damit Quell-Navigation exakt auf dem
    Original gerendert werden kann (keine Koordinaten-Annahme).
    """

    page_number: int = Field(ge=1)
    width_pt: float = Field(ge=0.0)
    height_pt: float = Field(ge=0.0)
    rotation: Optional[int] = None  # deprecated: PDF-Rotation hier NICHT mehr nutzen
    original_width_pt: Optional[float] = Field(default=None, ge=0.0)
    original_height_pt: Optional[float] = Field(default=None, ge=0.0)
    pdf_rotation: Optional[int] = Field(
        default=0,
        ge=0,
        le=359,
        description="Rotationswert des Original-PDF (fitz page.rotation)",
    )
    text: str = ""
    elements: list[Element] = Field(default_factory=list)
    tables: list[TableStructure] = Field(default_factory=list)
    atomic_units: list[AtomicUnit] = Field(default_factory=list)

    def elements_of(self, *types: ElementType) -> list[Element]:
        return [e for e in self.elements if e.type in types]

    @property
    def scale_to_original(self) -> tuple[float, float]:
        """Skalierung kanonischer -> Original-PDF-Abmessungen (kein Raten)."""
        sx = (self.original_width_pt or self.width_pt) / self.width_pt if self.width_pt else 1.0
        sy = (self.original_height_pt or self.height_pt) / self.height_pt if self.height_pt else 1.0
        return sx, sy


class ProcessingProvenance(BaseModel):
    """Reproduzierbare Herkunft einer Verarbeitung (Recognition-Ebene).

    Fuer Audit/Reproduzierbarkeit/Cache-Invalidierung: Quelle (Hash), Provider,
    OCR-Engine/-Version, Sprachen, DPI, Preprocessing-Identitaet und die
    Schema-Version der kanonischen Darstellung. Bewusst OHNE KI-Konfidenz –
    diese bleibt im SourceEvidence/Contract-Modell getrennt.
    """

    provider: str
    provider_version: Optional[str] = None
    method: Method = Method.UNKNOWN
    ocr_engine: Optional[str] = None
    ocr_engine_version: Optional[str] = None
    ocr_lang: Optional[str] = None
    do_ocr: Optional[bool] = None
    do_table_structure: Optional[bool] = None
    table_mode: Optional[str] = None
    device: Optional[str] = None
    dpi: Optional[int] = Field(
        default=None, ge=1,
        description="OCR-Rasterdichte in dpi, falls vom Provider verwendet",
    )
    preprocessing: Optional[str] = Field(
        default=None,
        description="Identitaet/Variante einer Vorverarbeitung (z. B. "
        "'structural_roles_v1') – nur falls angewendet",
    )
    geometry_provider: Optional[str] = Field(
        default=None,
        description="Provider der atomaren Geometrie-Einheiten "
        "(z. B. 'rapidocr'); None = keine atomaren Einheiten erfasst",
    )
    geometry_provider_version: Optional[str] = Field(
        default=None,
        description="Version/Identitaet des Geometrie-Providers, falls angeboten",
    )
    canonical_schema_version: Optional[str] = CANONICAL_SCHEMA_VERSION
    config: dict[str, Any] = Field(default_factory=dict)


class LogicalUnit(BaseModel):
    """Page-less source unit for formats such as DOCX.

    DOCX has no authoritative physical page numbers.  Paragraph/table indexes
    therefore remain first-class canonical addresses instead of being mapped to
    invented pages.  Geometry is intentionally absent because python-docx does
    not provide a trustworthy original-page coordinate system.
    """

    source_type: Literal["paragraph", "table"]
    index: int = Field(ge=1)
    text: str
    method: Method = Method.NATIVE


class DocumentIntelligenceResult(BaseModel):
    """Kanonisches Ergebnis eines Dokument-Intelligence-Providers."""

    document_id: Optional[str] = None
    source_sha256: str
    source_filename: Optional[str] = None
    source_path: Optional[str] = None
    canonical_text: str = ""
    pages_text: list[str] = Field(default_factory=list)
    pages: list[Page] = Field(default_factory=list)
    logical_units: list[LogicalUnit] = Field(default_factory=list)
    provenance: ProcessingProvenance
    warnings: list[str] = Field(default_factory=list)
    processing_time_s: float = Field(default=0.0, ge=0.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def page(self, page_number: int) -> Optional[Page]:
        for p in self.pages:
            if p.page_number == page_number:
                return p
        return None

    def all_tables(self) -> list[TableStructure]:
        return [t for p in self.pages for t in p.tables]

    def find_text(self, needle: str, *, case_sensitive: bool = False) -> list[tuple[Page, TextSpan]]:
        """Best-effort Suche nach `needle` im kanonischen Seiten-Text.

        Dient der Quell-Navigation/Diagnose; KEIN Produktions-Suchindex.
        Vorwärts-Offset wird als maximaler Startpunkt gehandhabt.
        """
        if not needle:
            return []
        needle = needle if case_sensitive else needle.lower()
        hits: list[tuple[Page, TextSpan]] = []
        for p in self.pages:
            text = p.text if case_sensitive else p.text.lower()
            start = 0
            while True:
                idx = text.find(needle, start)
                if idx < 0:
                    break
                hits.append((p, TextSpan(offset=idx, length=len(needle))))
                start = idx + len(needle)
        return hits


def build_canonical_text(pages: list[Page]) -> str:
    """Deterministischer Gesamttext: Seiten durch Form-Feed getrennt."""
    return "\f".join(p.text for p in pages)
