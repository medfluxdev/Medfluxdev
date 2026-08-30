"""DOCX-Text-Extraktion für Medflux (Schritt 5).

- Extrahiert Absätze UND Tabellen mit python-docx.
- Nutzt Absatz-/Tabellenindizes als Quellenreferenzen (keine erfundenen
  Seitennummern).
- Bewahrt Absätze und Tabellen in Dokumentreihenfolge.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.documents.extraction.schemas import ExtractionUnit, SourceType, UnitMethod


def extract_docx_units(docx_path: Path) -> list[ExtractionUnit]:
    """Extrahiert Texteinheiten (Absätze + Tabellen) aus einem DOCX.

    Wirft Exception bei korruptem DOCX (Aufrufer behandelt das).
    """
    doc = Document(str(docx_path))
    body = doc.element.body

    units: list[ExtractionUnit] = []
    para_index = 0
    table_index = 0

    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            para_index += 1
            text = Paragraph(child, doc).text.strip()
            if text:
                units.append(
                    ExtractionUnit(
                        source_type=SourceType.PARAGRAPH,
                        index=para_index,
                        text=text,
                        method=UnitMethod.TEXT,
                    )
                )
        elif child.tag == qn("w:tbl"):
            table_index += 1
            rows = []
            for row in Table(child, doc).rows:
                cells = [c.text.strip() for c in row.cells]
                rows.append(" | ".join(cells))
            table_text = "\n".join(rows).strip()
            if table_text:
                units.append(
                    ExtractionUnit(
                        source_type=SourceType.TABLE,
                        index=table_index,
                        text=table_text,
                        method=UnitMethod.TEXT,
                    )
                )

    return units
