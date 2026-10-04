"""Medflux Benchmark v2 – Dokumentqualitäts-Inspektion der neuen PDF-Korpus.

Nutzung (Backend-venv):
    .\\.venv\\Scripts\\python.exe scripts\\document_quality_inspection.py [INPUT_DIR]

Prüft JEDES PDF deterministisch auf seine native Textschicht (keine KI, kein OCR):
    - Seitenzahl, pro Seite substantielle Zeichen, Bilder, Text-Blöcke
    - Abdeckung (Anteil Seiten mit sinnvollem Text) und Textdichte
    - Klassifikation: native_text / partial_text / scanned_image / unreadable
    - Empfohlener Verarbeitungspfad (native / OCR-Fallback / Voll-OCR / manuell)

Schreibt:
    - data/benchmark_v2/document_quality.json   (Maschinenreport)
    - Konsolen-Zusammenfassung (Klassen + Dateien)
Das Original-Archiv und data/benchmark/ (Legacy) bleiben unangetastet.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.documents.quality import (  # noqa: E402
    DOC_NATIVE,
    DOC_PARTIAL,
    DOC_SCANNED,
    DOC_UNREADABLE,
    classify_pages,
    page_stat_from_text,
)

INPUT_DIR = REPO_ROOT / "data" / "benchmark_v2" / "input"
OUT_JSON = REPO_ROOT / "data" / "benchmark_v2" / "document_quality.json"
LEGACY_DIR = REPO_ROOT / "data" / "benchmark" / "input"

_CLS_LABEL = {
    DOC_NATIVE: "native_text   ",
    DOC_PARTIAL: "partial_text  ",
    DOC_SCANNED: "scanned_image ",
    DOC_UNREADABLE: "unreadable/err",
}


def inspect_pdf(path: Path) -> dict:
    import fitz

    doc = fitz.open(path)
    try:
        page_stats = []
        page_count = len(doc)
        for i in range(page_count):
            page = doc.load_page(i)
            text = page.get_text("text").replace("\xa0", " ")
            blocks = page.get_text("blocks")
            images = page.get_images(full=True)
            page_stats.append(
                page_stat_from_text(
                    page_number=i + 1,
                    text=text,
                    image_count=len(images),
                    text_blocks=len(blocks),
                )
            )
    finally:
        doc.close()

    quality = classify_pages(path.name, page_stats)

    rec = {
        "filename": path.name,
        "page_count": quality.page_count,
        "native_text_char_count": quality.native_text_char_count,
        "pages_with_text": quality.meaningful_pages,
        "text_coverage_ratio": quality.coverage_ratio,
        "classification": quality.classification,
        "extraction_warnings": quality.extraction_warnings,
        "recommended_processing_path": quality.recommended_processing_path,
        "pages_needing_ocr": quality.pages_needing_ocr,
        "avg_text_blocks_per_page": round(quality.avg_text_blocks, 2),
        "avg_images_per_page": round(quality.avg_images_per_page, 2),
        "file_size_bytes": path.stat().st_size,
    }
    return rec


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.casefold())


def legacy_docx_names() -> list[str]:
    if not LEGACY_DIR.exists() or not LEGACY_DIR.is_dir():
        return []
    out = []
    for p in LEGACY_DIR.rglob("*.docx"):
        out.append(p.name)
    return sorted(out)


def match_name(pdf_name: str, legacy_names: list[str]) -> tuple[int, str | None]:
    """Einfachster PDF↔DOCX-Abgleich über normalisierte Namen (difflib nicht
    erforderlich, da die Korpora dieselben Betreffdateinamen tragen)."""
    base = Path(pdf_name).stem
    norm = normalize_name(base)
    if not norm:
        return 0, None
    best, best_score = None, 0
    for leg in legacy_names:
        ln = normalize_name(Path(leg).stem)
        if not ln:
            continue
        if ln == norm:
            score = 100
        elif norm[:-1] and (ln == norm[:-1] or norm == ln[:-1]):
            score = 60
        else:
            score = 0
        if score > best_score:
            best_score, best = score, leg
    return best_score, best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", nargs="?", default=str(INPUT_DIR))
    args = ap.parse_args()

    in_dir = Path(args.input_dir)
    pdfs = sorted(p for p in in_dir.iterdir() if p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"Keine PDFs in {in_dir}")
        return

    legacy = legacy_docx_names()
    records = []
    for p in pdfs:
        rec = inspect_pdf(p)
        score, leg = match_name(p.name, legacy)
        rec["legacy_docx_match"] = {"match": leg, "confidence": score}
        records.append(rec)
        print(
            f"{_CLS_LABEL.get(rec['classification'], '?')} "
            f"{rec['page_count']:>3} S | {rec['native_text_char_count']:>8} "
            f"Zeichen | Abdeckung {rec['text_coverage_ratio']:>5.1%} | "
            f"{p.name}"
        )

    by_class: dict[str, int] = {}
    for r in records:
        by_class[r["classification"]] = by_class.get(r["classification"], 0) + 1

    total_pages = sum(r["page_count"] for r in records)
    total_chars = sum(r["native_text_char_count"] for r in records)
    stats = {
        "total_pdfs": len(records),
        "total_pages": total_pages,
        "total_native_chars": total_chars,
        "avg_chars_per_page": round(total_chars / total_pages, 1) if total_pages else 0,
        "class_counts": by_class,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps({"stats": stats, "documents": records},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n{json.dumps(stats, ensure_ascii=False, indent=2)}")
    print(f"\nReport geschrieben: {OUT_JSON}")


if __name__ == "__main__":
    main()