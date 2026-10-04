"""Docling-Dokument-Intelligence-Provider (STEP 8B).

Konvertiert ein Original-PDF lokal mit Docling (Layout-Analyse + TableFormer
Tabellenstruktur + RapidOCR) und bildet das Docling-eigene Modell 1:1 auf die
Medflux-kanonische Repraesentation (canonical.py) ab. Es verlassen KEINE
Docling-Objekte diese Datei.

Lizenz-/Reproduzierbarkeitshinweise:
- Docling-Code: MIT; offizielle Docling-Modelle (docling-project Hub):
  Apache-2.0 + CDLA-Permissive-2.0; OCR-Backend RapidOCR: Apache-2.0.
- `HF_HUB_DISABLE_SYMLINKS=1`: Dokument klassischer Windows-Symlink-Probleme
  im HuggingFace-Modellcache (WinError 1314), erzwingt Kopien statt Symlinks.
- Volle Offline-Fähigkeit nach erstem Modell-Download (HF_HUB_OFFLINE=1).
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any, Optional

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

from app.documents.intelligence.canonical import (
    BoundingRegion,
    Cell,
    DocumentIntelligenceResult,
    Element,
    ElementType,
    Method,
    Page,
    ProcessingProvenance,
    TableStructure,
    TextSpan,
    WordRegion,
    build_canonical_text,
)
from app.documents.intelligence.provider import (
    DocumentIntelligenceProvider,
    DocumentIntelligenceSettings,
    IntelligenceProviderError,
    IntelligenceProviderUnavailableError,
    ProviderCapabilities,
)

_PAGE_SEP = "\n"

# Mapping aus Tesseract-/ISO-639-3-Sprachcodes (wie sie global in
# Settings.ocr_lang bzw. app/core/config.py konfiguriert sind) auf den
# Sprachcode, den Doclings RapidOCR-Backend erwartet. RapidOCR akzeptiert
# kurze ISO-639-1-Codes (z. B. "de") bzw. eigene Aliase ("german"), aber NICHT
# die ISO-639-3-Codes (z. B. "deu"), die Tesseract verwendet. Ohne Normierung
# wirft `RapidOcrOptions(lang=["deu"])` einen ValueError und jeder PDF-Import
# schlaegt fehl – auch bei nativen (nicht gescannten) PDFs.
_RAPIDOCR_LANG_MAP = {
    "deu": "de",
    "ger": "de",
    "deutsch": "de",
    "german": "de",
    "de": "de",
    "eng": "en",
    "en": "en",
    "english": "en",
    "fra": "fr",
    "fre": "fr",
    "french": "fr",
    "fr": "fr",
    "ara": "arabic",
    "arabic": "arabic",
    "spa": "es",
    "es": "es",
    "ita": "it",
    "it": "it",
    "nld": "nl",
    "dut": "nl",
    "nl": "nl",
    "por": "pt",
    "pt": "pt",
    "pol": "pl",
    "pl": "pl",
    "ces": "cs",
    "cze": "cs",
    "cs": "cs",
    "rus": "cyrillic",
    "ru": "cyrillic",
    "ukr": "cyrillic",
    "uk": "cyrillic",
    "tur": "tr",
    "tr": "tr",
    "ell": "el",
    "gre": "el",
    "el": "el",
    "hin": "devanagari",
    "hi": "devanagari",
    "jpn": "japan",
    "ja": "japan",
    "kor": "korean",
    "ko": "korean",
    "chi_sim": "ch",
    "chi_tra": "chinese_cht",
    "ch": "ch",
    "la": "latin",
    "lat": "latin",
    "swe": "sv",
    "sv": "sv",
    "dan": "da",
    "da": "da",
    "nor": "no",
    "no": "no",
    "fin": "fi",
    "fi": "fi",
}


def _rapidocr_lang_code(lang: str) -> str:
    """Normiert einen (global konfigurierten) Sprachcode auf RapidOCR-Syntax.

    Unbekannte Codes werden unveraendert durchgereicht, damit neue/weitere
    Sprachen nicht stillschweigend verworfen werden; RapidOCR validiert sie
    anschliessend selbst und meldet es als verarbeitbaren Fehler.
    """
    key = (lang or "").strip().lower()
    return _RAPIDOCR_LANG_MAP.get(key, lang)


class DoclingDocumentProvider(DocumentIntelligenceProvider):
    """Provider fuer Docling (Layout, Tables, OCR)."""

    name = "docling"

    def __init__(self) -> None:
        self._docling_version: Optional[str] = None
        self._rapidocr_version: Optional[str] = None
        self._converter: Any = None
        self._pipeline_hash: Optional[str] = None
        self._ready = False
        self._availability_reason: Optional[str] = None
        try:
            from docling.document_converter import DocumentConverter  # noqa: F401
            import docling  # noqa: F401
            import rapidocr  # noqa: F401

            self._ready = True
        except Exception as exc:
            self._availability_reason = f"Docling nicht lauffaehig: {exc}"

    # ------------------------------------------------------------- Basis

    def is_available(self) -> bool:
        return self._ready

    def capabilities(self) -> ProviderCapabilities:
        version = self._package_version("docling")
        return ProviderCapabilities(
            name=self.name,
            version=version,
            available=self.is_available(),
            availability_reason=self._availability_reason,
            supports_pdf=True,
            supports_ocr=True,
            supports_tables=True,
            supports_layout=True,
            supports_reading_order=True,
            offline_after_setup=True,
            ocr_lang=["de", "en"],
        )

    @staticmethod
    def _package_version(name: str) -> Optional[str]:
        try:
            from importlib.metadata import version

            return version(name)
        except Exception:
            return None

    # ------------------------------------------------------------- API

    def process(
        self,
        path: Path,
        settings: Optional[DocumentIntelligenceSettings] = None,
    ) -> DocumentIntelligenceResult:
        path = Path(path)
        if not path.is_file():
            raise IntelligenceProviderError(f"Datei nicht gefunden: {path}")
        if not self.is_available():
            raise IntelligenceProviderUnavailableError(
                self._availability_reason or "Docling ist nicht installiert."
            )

        settings = settings or DocumentIntelligenceSettings()
        converter = self._get_converter(settings)
        sha256 = _sha256(path)
        warnings: list[str] = []
        start = time.monotonic()

        try:
            result = converter.convert(str(path), raises_on_error=True)
        except Exception as exc:
            raise IntelligenceProviderError(f"Docling-Verarbeitung fehlgeschlagen: {exc}")

        errors = getattr(result, "errors", None) or []
        for err in errors:
            msg = getattr(err, "error_message", None) or str(err)
            warnings.append(msg)

        doc = result.document
        pages, skip_warnings = self._map_pages(doc, _read_original_page_sizes(path))
        warnings.extend(skip_warnings)

        if settings.structural_roles:
            from app.documents.intelligence.structure import apply_structural_roles

            roles = apply_structural_roles(pages)
            warnings.append(
                f"Strukturrollen: {roles.count} Elemente markiert "
                f"(Seitenzahlen={roles.roles_seen.get('page_number', 0)}, "
                f"Kopf={roles.roles_seen.get('header', 0)}, "
                f"Fuss={roles.roles_seen.get('footer', 0)})"
            )

        if settings.max_pages is not None and settings.max_pages > 0:
            pages = pages[: settings.max_pages]

        return DocumentIntelligenceResult(
            document_id=None,
            source_sha256=sha256,
            source_filename=path.name,
            source_path=str(path),
            canonical_text=build_canonical_text(pages),
            pages_text=[p.text for p in pages],
            pages=pages,
            provenance=self._provenance(settings, start),
            warnings=warnings,
            processing_time_s=round(time.monotonic() - start, 3),
        )

    # ------------------------------------------------------------- Pipeline

    def _get_converter(self, settings: DocumentIntelligenceSettings):
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            AcceleratorDevice,
            AcceleratorOptions,
            PdfPipelineOptions,
            RapidOcrOptions,
            TableFormerMode,
            TableStructureOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.utils.pipeline_cache import create_pipeline_options_hash

        opts = PdfPipelineOptions()
        opts.do_ocr = bool(settings.do_ocr)
        opts.do_table_structure = bool(settings.do_table_structure)
        if settings.do_ocr:
            opts.ocr_options = RapidOcrOptions(
                lang=[_rapidocr_lang_code(lang) for lang in settings.ocr_lang]
            )
        if settings.do_table_structure:
            opts.table_structure_options = TableStructureOptions(
                do_cell_matching=True,
                mode=(
                    TableFormerMode.ACCURATE
                    if settings.table_mode == "accurate"
                    else TableFormerMode.FAST
                ),
            )
        accelerator = {
            "auto": AcceleratorDevice.AUTO,
            "cuda": AcceleratorDevice.CUDA,
            "cpu": AcceleratorDevice.CPU,
        }[settings.device]
        opts.accelerator_options = AcceleratorOptions(
            num_threads=settings.num_threads or 4,
            device=accelerator,
        )

        options_hash = create_pipeline_options_hash(opts)
        if self._converter is not None and self._pipeline_hash == options_hash:
            return self._converter

        self._converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
        )
        self._pipeline_hash = options_hash
        self._docling_version = self._package_version("docling")
        self._rapidocr_version = self._package_version("rapidocr")
        return self._converter

    def _provenance(self, settings: DocumentIntelligenceSettings, start: float) -> ProcessingProvenance:
        return ProcessingProvenance(
            provider=self.name,
            provider_version=self._docling_version,
            method=Method.OCR if settings.do_ocr else Method.NATIVE,
            ocr_engine="rapidocr" if settings.do_ocr else None,
            ocr_engine_version=self._rapidocr_version,
            ocr_lang=",".join(settings.ocr_lang) if settings.ocr_lang else None,
            do_ocr=bool(settings.do_ocr),
            do_table_structure=bool(settings.do_table_structure),
            table_mode=settings.table_mode,
            device=settings.device,
            preprocessing="structural_roles_v1" if settings.structural_roles else None,
            config={
                "pipeline_hash": self._pipeline_hash,
                "hf_symlinks": "disabled",
                "structural_roles": bool(settings.structural_roles),
                "accelerator_device": settings.device,
            },
        )

    # ------------------------------------------------------------- Mapping

    def _map_pages(self, doc, original_sizes: Optional[dict[int, dict]] = None) -> tuple[list[Page], list[str]]:
        warnings: list[str] = []
        items = [it for it, _level in doc.iterate_items()]
        page_numbers = sorted(int(pn) for pn in doc.pages.keys())

        pages: dict[int, Page] = {}
        for pn in page_numbers:
            size = doc.pages[pn].size
            orig = (original_sizes or {}).get(pn, {})
            pages[pn] = Page(
                page_number=pn,
                width_pt=float(size.width),
                height_pt=float(size.height),
                rotation=int(getattr(doc.pages[pn], "rotation", 0) or 0),
                original_width_pt=orig.get("width_pt"),
                original_height_pt=orig.get("height_pt"),
                pdf_rotation=int(orig.get("rotation") or 0),
                text="",
                elements=[],
                tables=[],
            )

        # Sammle je Seite die Items in Lesereihenfolge des Dokuments.
        # Dedup: Docling liefert manche Items (Tabellen, OCR-Zeilen) mehrfach
        # (z.B. in Body UND Floats); identische Exemplace nur einmal uebernehmen.
        seen: set[tuple] = set()
        segment_sources: dict[str, list[tuple[int, int, "Any"]]] = {}
        for item in items:
            item_type = type(item).__name__.lower()
            if "pagebreak" in item_type:
                continue
            prov = _first_prov(item)
            if prov is None:
                warnings.append(f"{item_type}: ohne Seiten-/Box-Provenienz uebersprungen")
                continue
            pn = int(prov.page_no)
            page = pages.get(pn)
            if page is None:
                warnings.append(f"Item@Seite {pn} ohne Seitenmodell uebersprungen")
                continue
            box = getattr(prov, "bbox", None)
            coords = tuple(round(float(v), 1) for v in (getattr(box, "l", 0), getattr(box, "t", 0),
                                                        getattr(box, "r", 0), getattr(box, "b", 0))) if box else ()
            dedup_key = (pn, item_type, coords, len(str(getattr(item, "text", "") or "")))
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            element = self._map_element(item, prov, page, len(page.elements))
            if element is None:
                continue
            page.elements.append(element)
            if element.table is not None:
                page.tables.append(element.table)
            if element.text.strip():
                segment_sources[element.element_id] = _segments_of(item, page.height_pt)

        # Kanonischer Seiten-Text + Spans deterministisch in Lesereihenfolge.
        for pn, page in pages.items():
            _assign_page_text(page)
            warnings.extend(_assign_word_regions(page, segment_sources))

        return [pages[pn] for pn in page_numbers], warnings

    def _map_element(self, item, prov, page: Page, reading_order: int) -> Optional[Element]:
        element_type = _element_type(item)
        text = str(getattr(item, "text", "") or "")
        region = _region(prov, page.height_pt)
        confidence = _confidence(prov)

        if element_type == ElementType.TABLE:
            return self._map_table(item, prov, page, reading_order, region)
        # Bild/Figur als Element ohne Text erhalten (Kanten fuer Abbildungs-Erkennung).
        if element_type in (ElementType.IMAGE, ElementType.FIGURE):
            return Element(
                element_id=_elem_id(page.page_number, reading_order),
                type=element_type,
                text=text,
                page=page.page_number,
                region=region,
                reading_order=reading_order,
                method=_method(item),
                confidence=confidence,
                metadata={"label": getattr(item, "label", None) and str(getattr(item, "label", None))},
            )

        return Element(
            element_id=_elem_id(page.page_number, reading_order),
            type=element_type,
            text=text.strip(),
            page=page.page_number,
            region=region,
            reading_order=reading_order,
            method=_method(item),
            confidence=confidence,
            metadata={"label": getattr(item, "label", None) and str(getattr(item, "label", None))},
        )

    def _map_table(self, item, prov, page: Page, reading_order: int, region) -> Element:
        data = getattr(item, "data", None)
        cells: list[Cell] = []
        num_rows = 0
        num_cols = 0
        headers: list[str] = []
        if data is not None:
            raw_cells = getattr(data, "table_cells", None) or []
            for rc in raw_cells:
                c = _map_cell(rc, page.page_number, page.height_pt)
                if c is not None:
                    cells.append(c)
                    num_rows = max(num_rows, getattr(rc, "end_row_offset_idx", 0) or 0)
                    num_cols = max(num_cols, getattr(rc, "end_col_offset_idx", 0) or 0)
                    if getattr(rc, "column_header", False):
                        if c.text.strip() not in headers:
                            headers.append(c.text.strip())
        table = TableStructure(
            table_id=f"table_p{page.page_number}_{reading_order}",
            page=page.page_number,
            region=region,
            num_rows=num_rows,
            num_cols=num_cols,
            cells=cells,
            headers=headers,
            confidence=_confidence(prov),
        )
        element = Element(
            element_id=_elem_id(page.page_number, reading_order),
            type=ElementType.TABLE,
            text=table.linearized_text(),
            page=page.page_number,
            region=region,
            reading_order=reading_order,
            method=_method(item),
            confidence=table.confidence,
            table=table,
            children=[f"cell_{table.table_id}_{c.row_index}_{c.column_index}" for c in cells],
        )
        return element


# ------------------------------------------------------------- Mapping-Helfer

def _element_type(item) -> ElementType:
    label = str(getattr(item, "label", None) or "").upper()
    mapping = {
        "TEXT": ElementType.PARAGRAPH,
        "PARAGRAPH": ElementType.PARAGRAPH,
        "TITLE": ElementType.TITLE,
        "SECTION_HEADER": ElementType.HEADING,
        "PAGE_HEADER": ElementType.HEADER,
        "PAGE_FOOTER": ElementType.FOOTER,
        "PAGE_NUMBER": ElementType.PAGE_NUMBER,
        "LIST_ITEM": ElementType.LIST_ITEM,
        "LIST": ElementType.LIST,
        "CAPTION": ElementType.CAPTION,
        "FOOTNOTE": ElementType.FOOTNOTE,
        "FORMULA": ElementType.FORMULA,
        "TABLE": ElementType.TABLE,
        "PICTURE": ElementType.IMAGE,
        "FIGURE": ElementType.FIGURE,
        "CODE": ElementType.OTHER,
    }
    return mapping.get(label, ElementType.OTHER)


def _method(item) -> Method:
    layer = str(getattr(item, "content_layer", "") or "").lower()
    if "ocr" in layer:
        return Method.OCR
    return Method.UNKNOWN if layer == "" else Method.NATIVE


def _first_prov(item):
    prov = getattr(item, "prov", None)
    if isinstance(prov, (list, tuple)) and prov:
        return prov[0]
    return prov


def _all_prov(item) -> list:
    prov = getattr(item, "prov", None)
    if isinstance(prov, (list, tuple)) and prov:
        return list(prov)
    if prov is None:
        return []
    return [prov]


def _segments_of(item, height_pt: float) -> list[tuple[str, "BoundingRegion"]]:
    """Segment-/Zeilen-Boxen aus docling ProvenanceItem (charspan + bbox).

    Granularitaet: Provider-exakt "segment" (eine OCR-Zeile/ein Segment).
    Kein Erfinden von Wort-Boxen, wenn docling sie nicht liefert – die
    granularity bleibt ehrlich "segment".
    """
    item_text = str(getattr(item, "text", "") or "")
    out: list[tuple[str, BoundingRegion]] = []
    for prov in _all_prov(item):
        charspan = getattr(prov, "charspan", None)
        if not charspan or len(charspan) != 2:
            continue
        start, end = int(charspan[0]), int(charspan[1])
        if start < 0 or end < start or start >= len(item_text):
            continue
        raw = item_text[start:end].strip()
        if not raw:
            continue
        region = _region(prov, height_pt)
        if region is None:
            continue
        out.append((raw, region))
    return out


def _assign_word_regions(page: Page, sources: dict[str, list[tuple[str, BoundingRegion]]]) -> list[str]:
    """Loest Segment-Offsets in den kanonischen Seiten-Text auf (exakt, kein Raten).

    Fallback, NUR wenn kein Segment im Seiten-Text auffindbar ist: ein
    Element-Box mit granularity="element" – explizit markiert, nie still.
    """
    warnings: list[str] = []
    for elem in page.elements:
        text = (elem.text or "").strip()
        if not text or not elem.spans:
            continue
        sp = elem.spans[0]
        slice_text = page.text[sp.offset:sp.to()]
        seen: set[tuple] = set()
        for seg_text, region in sources.get(elem.element_id, []):
            key = (seg_text, region.x0, region.y0, region.x1, region.y1)
            if key in seen:
                continue
            seen.add(key)
            rel = slice_text.find(seg_text)
            if rel < 0:
                warnings.append(
                    f"{elem.element_id}: Segment '{seg_text[:40]}' nicht im Seiten-Text lokalisierbar"
                )
                continue
            elem.word_regions.append(
                WordRegion(
                    text=seg_text,
                    offset=sp.offset + rel,
                    length=len(seg_text),
                    region=region,
                    granularity="segment",
                )
            )
        if not elem.word_regions and elem.region is not None:
            elem.word_regions.append(
                WordRegion(
                    text=text,
                    offset=sp.offset,
                    length=len(text),
                    region=elem.region,
                    granularity="element",
                )
            )
    return warnings


def _read_original_page_sizes(path: Path) -> dict[int, dict]:
    """Liest die ORIGINALEN PDF-Seiten (view = rotationsbereinigte Groesse + rotation)."""
    try:
        import fitz
    except Exception:
        return {}
    out: dict[int, dict] = {}
    try:
        doc = fitz.open(path)
        try:
            for i in range(doc.page_count):
                pg = doc.load_page(i)
                out[int(i + 1)] = {
                    "width_pt": float(pg.rect.width),
                    "height_pt": float(pg.rect.height),
                    "rotation": int(pg.rotation or 0),
                }
        finally:
            doc.close()
    except Exception:
        return {}
    return out


def _coord_boxes(prov, height_pt: float) -> tuple:
    """Liest das BoundingBox (l,t,r,b) und normalisiert in PDF-Punkte
    (Ursprung oben links, y nach unten)."""
    bb = getattr(prov, "bbox", None)
    if bb is None:
        return None
    origin = str(getattr(bb, "coord_origin", "") or "").upper()
    l = float(getattr(bb, "l", 0) or 0)
    r = float(getattr(bb, "r", 0) or 0)
    if origin == "BOTTOMLEFT":
        t = float(getattr(bb, "t", height_pt) or height_pt)
        b = float(getattr(bb, "b", 0) or 0)
        x0, y0, x1, y1 = l, height_pt - t, r, height_pt - b
    else:
        t = float(getattr(bb, "t", 0) or 0)
        b = float(getattr(bb, "b", 0) or 0)
        x0, y0, x1, y1 = l, t, r, b
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return max(0.0, x0), max(0.0, y0), max(0.0, x1), max(0.0, y1)


def _region(prov, height_pt: float) -> Optional[BoundingRegion]:
    box = _coord_boxes(prov, height_pt)
    if box is None:
        return None
    return BoundingRegion(page=int(prov.page_no), x0=box[0], y0=box[1], x1=box[2], y1=box[3])


def _confidence(prov) -> Optional[float]:
    vals = []
    target = prov if not isinstance(prov, (list, tuple)) else prov
    ocr_conf = getattr(target, "ocr_confidence", None)
    if isinstance(ocr_conf, (int, float)):
        vals.append(float(ocr_conf))
    if not vals:
        return None
    conf = sum(vals) / len(vals)
    return round(max(0.0, min(1.0, conf)), 3)


def _map_cell(raw_cell, page_no: int, height_pt: float) -> Optional[Cell]:
    try:
        row = int(getattr(raw_cell, "start_row_offset_idx", 0) or 0)
        col = int(getattr(raw_cell, "start_col_offset_idx", 0) or 0)
        row_span = int(getattr(raw_cell, "row_span", 1) or 1)
        col_span = int(getattr(raw_cell, "col_span", 1) or 1)
    except (TypeError, ValueError):
        return None
    text = str(getattr(raw_cell, "text", "") or "")
    bb = getattr(raw_cell, "bbox", None)
    region = None
    if bb is not None:
        origin = str(getattr(bb, "coord_origin", "") or "").upper()
        l = float(getattr(bb, "l", 0) or 0)
        r = float(getattr(bb, "r", 0) or 0)
        if origin == "BOTTOMLEFT":
            t = float(getattr(bb, "t", height_pt) or height_pt)
            b = float(getattr(bb, "b", 0) or 0)
            region = BoundingRegion(page=page_no, x0=l, y0=height_pt - t, x1=r, y1=height_pt - b)
        else:
            t = float(getattr(bb, "t", 0) or 0)
            b = float(getattr(bb, "b", 0) or 0)
            region = BoundingRegion(page=page_no, x0=l, y0=t, x1=r, y1=b)
    return Cell(
        row_index=row,
        column_index=col,
        row_span=row_span,
        column_span=col_span,
        text=text,
        region=region,
    )


def _elem_id(page: int, reading_order: int) -> str:
    return f"el_p{page}_{reading_order}"


def _assign_page_text(page: Page) -> None:
    """Baut den kanonischen Seiten-Text (Lesereihenfolge) + Spans je Element.

    Der Cursor zaehlt fuer JEDES Element (auch leere wie Bilder) seinen
    Trenner mit, damit sp.offset exakt in page.text zeigt.
    """
    cursor = 0
    pieces: list[str] = []
    for element in page.elements:
        text = element.text
        pieces.append(text)
        if text:
            element.spans = [TextSpan(offset=cursor, length=len(text))]
        cursor += len(text) + len(_PAGE_SEP)
    page.text = _PAGE_SEP.join(pieces)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()