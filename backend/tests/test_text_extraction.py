"""Tests für die Medflux-Textextraktion (Schritt 5).

Alle Testdokumente werden innerhalb der Tests erzeugt (PyMuPDF, python-docx).
Keine externen Dateien, kein Internet.
"""

import io

import fitz
import pytest
from docx import Document

from app.documents.extraction.ocr import OCRProvider
from app.documents.extraction.schemas import SourceType, UnitMethod
from app.documents.extraction.service import TextExtractionService
from app.documents.storage import DocumentStorage
from app.models.enums import ExtractionStatus


_ARIAL = r"C:\Windows\Fonts\arial.ttf"


def make_pdf_bytes(pages_text: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text:
            page.insert_font(fontname="arial", fontfile=_ARIAL)
            page.insert_text((72, 72), text, fontsize=11, fontname="arial")
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def make_docx_bytes(paragraphs, table_rows=None) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    if table_rows:
        rows = len(table_rows)
        cols = len(table_rows[0])
        table = doc.add_table(rows=rows, cols=cols)
        for i, row in enumerate(table_rows):
            for j, val in enumerate(row):
                table.cell(i, j).text = val
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def save_document(storage, filename, content):
    ext = ".pdf" if filename.lower().endswith(".pdf") else ".docx"
    record = storage.save(filename, ext, "application/octet-stream", content, "x" * 64)
    return record["document_id"]


@pytest.fixture
def extraction_env(tmp_path):
    base = tmp_path / "contracts"
    base.mkdir()
    storage = DocumentStorage(base)
    service = TextExtractionService(storage=storage, ocr=OCRProvider(enabled=False))
    return storage, service


def test_normal_pdf(extraction_env):
    storage, service = extraction_env
    data = make_pdf_bytes(
        ["Im Folgenden wird der vollständige Wartungsvertrag zwischen "
         "Auftraggeber und Dienstleister für die medizinischen Geräte dargestellt."]
    )
    doc_id = save_document(storage, "vertrag.pdf", data)
    result = service.extract(doc_id)
    assert result.file_type.value == "pdf"
    assert result.extraction_status == ExtractionStatus.SUCCESS
    assert result.page_count == 1
    assert result.text_available is True
    assert result.total_characters > 0


def test_multipage_pdf_and_page_numbers(extraction_env):
    storage, service = extraction_env
    data = make_pdf_bytes(
        [
            "Dies ist der vollständige Inhalt der ersten Seite des Vertragsdokuments.",
            "Dies ist der vollständige Inhalt der zweiten Seite des Vertragsdokuments.",
        ]
    )
    doc_id = save_document(storage, "mehr.pdf", data)
    result = service.extract(doc_id)
    assert result.page_count == 2
    page_idx = [u.index for u in result.units if u.source_type == SourceType.PAGE]
    assert page_idx == [1, 2]
    assert all(u.method == UnitMethod.TEXT for u in result.units)


def test_text_poor_pdf_requires_ocr(extraction_env):
    storage, service = extraction_env
    data = make_pdf_bytes([""])  # leere/gescannte Seite
    doc_id = save_document(storage, "scan.pdf", data)
    result = service.extract(doc_id)
    assert result.requires_ocr is True
    assert result.extraction_status == ExtractionStatus.PARTIAL
    assert any("OCR" in w for w in result.warnings)


def test_ocr_unavailable_does_not_crash(extraction_env):
    storage, service = extraction_env
    data2 = make_pdf_bytes([""])
    doc_id = save_document(storage, "scan2.pdf", data2)
    result = service.extract(doc_id)
    # Kein Absturz, strukturierte Antwort mit Warnung
    assert result is not None
    assert result.extraction_status == ExtractionStatus.PARTIAL
    assert any("OCR" in w for w in result.warnings)


def test_docx_paragraphs(extraction_env):
    storage, service = extraction_env
    data = make_docx_bytes(["Erster Absatz", "Zweiter Absatz"])
    doc_id = save_document(storage, "vertrag.docx", data)
    result = service.extract(doc_id)
    assert result.file_type.value == "docx"
    assert result.extraction_status == ExtractionStatus.SUCCESS
    paras = [u for u in result.units if u.source_type == SourceType.PARAGRAPH]
    assert [u.index for u in paras] == [1, 2]
    assert result.page_count == 0


def test_docx_tables(extraction_env):
    storage, service = extraction_env
    data = make_docx_bytes(
        ["Vor der Tabelle"],
        table_rows=[["Dienst", "Preis"], ["Wartung", "1.200,00 €"]],
    )
    doc_id = save_document(storage, "mit_tabelle.docx", data)
    result = service.extract(doc_id)
    tables = [u for u in result.units if u.source_type == SourceType.TABLE]
    assert len(tables) == 1
    assert "Wartung" in tables[0].text
    assert "1.200,00 €" in tables[0].text


def test_docx_source_indexes(extraction_env):
    storage, service = extraction_env
    data = make_docx_bytes(["Absatz Eins"], table_rows=[["a", "b"], ["c", "d"]])
    doc_id = save_document(storage, "quellen.docx", data)
    result = service.extract(doc_id)
    idx = [(u.source_type.value, u.index) for u in result.units]
    assert (SourceType.PARAGRAPH.value, 1) in idx
    assert (SourceType.TABLE.value, 1) in idx


def test_german_characters_preserved(extraction_env):
    storage, service = extraction_env
    sample = "Der Vertrag gilt für die neue Größe der Straße und enthält alle Umlaute: Ä Ö Ü ä ö ü ß."
    doc_id = save_document(storage, "umlaut.pdf", make_pdf_bytes([sample]))
    result = service.extract(doc_id)
    assert "Größe" in result.units[0].text
    assert "Ä Ö Ü ä ö ü ß" in result.units[0].text


def test_euro_symbol_preserved(extraction_env):
    storage, service = extraction_env
    sample = "Die jährliche Gebühr für den Wartungsservice beträgt insgesamt 1.200 € zuzüglich Mehrwertsteuer."
    doc_id = save_document(storage, "euro.pdf", make_pdf_bytes([sample]))
    result = service.extract(doc_id)
    assert "1.200 €" in result.units[0].text


def test_german_price_format_preserved(extraction_env):
    storage, service = extraction_env
    sample = "Die jährlichen Gesamtkosten belaufen sich auf 5.916,67 € pro Jahr gemäß Preisanhang."
    doc_id = save_document(storage, "preis.pdf", make_pdf_bytes([sample]))
    result = service.extract(doc_id)
    assert "5.916,67 €" in result.units[0].text


def test_date_format_preserved(extraction_env):
    storage, service = extraction_env
    sample = "Der Vertrag endet automatisch am 31.12.2027, sofern keine Kündigung erfolgt."
    doc_id = save_document(storage, "datum.pdf", make_pdf_bytes([sample]))
    result = service.extract(doc_id)
    assert "31.12.2027" in result.units[0].text


def test_corrupted_pdf_graceful(extraction_env):
    storage, service = extraction_env
    doc_id = save_document(storage, "kaputt.pdf", b"%PDF-1.7 totally broken garbage")
    result = service.extract(doc_id)
    assert result.extraction_status == ExtractionStatus.FAILED
    assert result.error is not None
    assert "beschädigt" in result.error


def test_corrupted_docx_graceful(extraction_env):
    storage, service = extraction_env
    doc_id = save_document(storage, "kaputt.docx", b"\x00\x01\x02 broken docx")
    result = service.extract(doc_id)
    assert result.extraction_status == ExtractionStatus.FAILED
    assert result.error is not None
    assert "beschädigt" in result.error


def test_unknown_document_id(extraction_env):
    _, service = extraction_env
    assert service.extract("0" * 32) is None


def test_source_traceability(extraction_env):
    storage, service = extraction_env
    data = make_pdf_bytes(
        [
            "Vollständiger Vertragstext auf der ersten Dokumentseite zu Prüfung.",
            "Weiterer vollständiger Vertragstext auf der zweiten Dokumentseite.",
        ]
    )
    doc_id = save_document(storage, "trace.pdf", data)
    result = service.extract(doc_id)
    for unit in result.units:
        assert unit.source_type == SourceType.PAGE
        assert unit.index >= 1
        assert unit.method == UnitMethod.TEXT


def test_original_file_unchanged(extraction_env):
    storage, service = extraction_env
    original = make_pdf_bytes(["Unveränderter Vertragstext bleibt nach der Extraktion unverändert erhalten."])
    doc_id = save_document(storage, "original.pdf", original)
    service.extract(doc_id)
    _, path = storage.resolve_document(doc_id)
    assert path.read_bytes() == original


# Hinweis: Der fruehere Produktions-Endpunkt "/api/documents/{id}/extract" wurde
# im Zuge der Integrations-Reparatur durch den Import-Endpunkt
# "/api/documents/import" abgeloest (einziger Produktions-Einstiegspunkt).
# Die zugehoerigen API-Tests wurden deshalb entfernt; die Textextraktion selbst
# wird weiterhin ueber die Service- und Storage-Tests oben abgedeckt.
