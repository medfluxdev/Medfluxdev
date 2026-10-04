from __future__ import annotations
"""Verify the €12,000 annual classification against ORIGINAL OCR text.
Prints count/indicator booleans only - no contract content is emitted."""
import asyncio
import os
import re
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("MEDFLUX_INSECURE_DEV", "true")

import fitz
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

from app.documents.intelligence.docling_provider import DoclingDocumentProvider
from app.documents.intelligence.provider import DocumentIntelligenceSettings

ROOT = Path(__file__).resolve().parent
SOURCE = Path.home() / "Desktop" / "Medflux-Integrated-Test" / "backend"

ANNUAL = ["jaehrlich", "ja" + "ehrlich", "jährlich", "jährl.", "pro jahr",
          "p.a.", "p. a.", "/ jahr", "/jahr", "jahr", "jeweils"]
SCHEDULED = ["monatlich", "monatl", "quartalsweise", "halbjaehrlich", "halbjährlich",
             "raten", "rate", "pro monat", "/monat", "/mon"]
ONEOFF = ["einmalig", "einmal", "einmalig"]
AMOUNT_RE = re.compile(r"12\.?000(?:\s*(?:,|\.)00)?(?:\s*EUR)?|12000")


def find_frankfurt_pdf():
    env = dotenv_values(SOURCE / ".env")
    url = env.get("DATABASE_URL")
    engine = create_engine(url, connect_args={"connect_timeout": 4})
    with engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text("SET TRANSACTION READ ONLY"))
        rows = conn.execute(text("""
          SELECT df.storage_key, dv.storage_key, dv.sha256
          FROM document_file df JOIN document_version dv
            ON dv.document_file_id = df.id AND dv.organization_id = df.organization_id
          WHERE df.original_filename ILIKE :needle
          ORDER BY dv.created_at DESC LIMIT 5
        """), {"needle": "%Frankfurt%"}).fetchall()
        trans.rollback()
    engine.dispose()
    roots = [SOURCE / "data" / "contracts", SOURCE.parent / "data" / "contracts"]
    from app.documents.storage import DocumentStorage, StorageError
    for key, other, expected in rows:
        for ref in (key, other):
            for root in roots:
                try:
                    candidate = DocumentStorage(root).safe_path(ref)
                    if not candidate.is_file() or candidate.suffix.lower() != ".pdf":
                        continue
                    import hashlib
                    if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
                        continue
                    with fitz.open(candidate) as pdf:
                        if len(pdf) == 9:
                            return candidate
                except (StorageError, OSError, RuntimeError, ValueError):
                    continue
    raise RuntimeError("Verified Frankfurt 9-page original not available")


async def main():
    pdf_path = find_frankfurt_pdf()
    provider_doc = DoclingDocumentProvider()
    canonical = await asyncio.to_thread(
        provider_doc.process, pdf_path,
        DocumentIntelligenceSettings(do_ocr=True, do_table_structure=True,
                                     ocr_lang=["de"], max_pages=9, device="auto"))
    page_texts = {}
    for page in canonical.pages:
        page_texts[int(page.page_number)] = page.text
    per_page_counts = {}
    per_page_context = {}
    for p, text in page_texts.items():
        matches = [m.start() for m in AMOUNT_RE.finditer(text or "")]
        per_page_counts[p] = len(matches)
        ctx = {"annual": 0, "scheduled": 0, "oneoff": 0}
        for start in matches:
            window = (text or "")[max(0, start - 250): start + 250].casefold()
            def hit(tokens):
                return sum(1 for t in tokens if t in window)
            ctx["annual"] += hit(ANNUAL)
            ctx["scheduled"] += hit(SCHEDULED)
            ctx["oneoff"] += hit(ONEOFF)
        per_page_context[p] = ctx
    print("VERIFY_PAGE_AMOUNT_COUNTS", per_page_counts, flush=True)
    print("VERIFY_PAGE_CONTEXT_HITS", per_page_context, flush=True)
    annual = per_page_context.get(3, {}).get("annual", 0)
    total_amount_occurrences = sum(per_page_counts.values())
    print("VERIFY_AMOUNT_TOTAL_OCCURRENCES", total_amount_occurrences, flush=True)
    print("VERIFY_PAGE3_ANNUAL_INDICATOR", bool(annual), flush=True)


if __name__ == "__main__":
    asyncio.run(main())