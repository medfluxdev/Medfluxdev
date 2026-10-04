from __future__ import annotations
"""Real-bridge vision probe: runs prepare_visual_first exactly as v3 does.
Vision-only (source_signals=[], max_reviews=0). Aggregates only, no content."""
import asyncio
import collections
import hashlib
import os
from functools import partial
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("MEDFLUX_INSECURE_DEV", "true")

import fitz
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.documents.storage import DocumentStorage, StorageError
from app.documents.intelligence.docling_provider import DoclingDocumentProvider
from app.documents.intelligence.provider import DocumentIntelligenceSettings
from app.ai.providers.ollama import OllamaProvider
from app.ai.harness.visual_first_bridge import prepare_visual_first
from app.ai.harness.vision import page_image

ROOT = Path(__file__).resolve().parent
SOURCE = Path.home() / "Desktop" / "Medflux-Integrated-Test" / "backend"
MODEL = "qwen3-vl:8b-instruct"


def find_frankfurt_pdf():
    env = dotenv_values(SOURCE / ".env")
    url = env.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Existing original database URL unavailable")
    engine = create_engine(url, connect_args={"connect_timeout": 4})
    with engine.connect() as conn:
        trans = conn.begin()
        conn.execute(text("SET TRANSACTION READ ONLY"))
        rows = conn.execute(text("""
          SELECT df.original_filename, dv.storage_key, df.storage_key, dv.sha256
          FROM document_file df JOIN document_version dv
            ON dv.document_file_id = df.id AND dv.organization_id = df.organization_id
          WHERE df.original_filename ILIKE :needle
          ORDER BY dv.created_at DESC LIMIT 5
        """), {"needle": "%Frankfurt%"}).fetchall()
        trans.rollback()
    engine.dispose()
    roots = [SOURCE / "data" / "contracts", SOURCE.parent / "data" / "contracts"]
    if env.get("CONTRACTS_DIR"):
        defined = Path(env["CONTRACTS_DIR"])
        roots.insert(0, defined if defined.is_absolute() else SOURCE / defined)
    for _name, key, other, expected in rows:
        for ref in (key, other):
            for root in roots:
                if not root.exists() or not ref:
                    continue
                try:
                    candidate = DocumentStorage(root).safe_path(ref)
                    if not candidate.is_file() or candidate.suffix.lower() != ".pdf":
                        continue
                    if hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
                        continue
                    with fitz.open(candidate) as pdf:
                        if len(pdf) != 9:
                            continue
                    return candidate
                except (StorageError, OSError, ValueError, RuntimeError):
                    continue
    raise RuntimeError("Verified Frankfurt 9-page original not available")


async def main():
    pdf_path = find_frankfurt_pdf()
    settings = Settings()
    settings.ai_request_timeout_seconds = 300
    settings.harness_vision_output_tokens = 600
    provider = OllamaProvider(settings, model_resolver=lambda: MODEL)
    provider_doc = DoclingDocumentProvider()
    if not provider_doc.is_available():
        raise RuntimeError("Docling provider unavailable")
    canonical = await asyncio.to_thread(
        provider_doc.process,
        pdf_path,
        DocumentIntelligenceSettings(do_ocr=True, do_table_structure=True,
                                     ocr_lang=["de"], max_pages=9, device="auto"))
    readings, rows, meta = await prepare_visual_first(
        canonical=canonical,
        source_signals=[],
        page_image_loader=partial(page_image, pdf_path, longest_side=1400),
        provider=provider,
        context=8192,
        output_tokens=600,
        max_pages=12,
        max_reviews=0,
    )
    per_page = collections.defaultdict(collections.Counter)
    obs_per_page = collections.Counter()
    for item in meta["calls"]:
        page = item["page"]
        for key in ("rejected_page_mismatch", "rejected_malformed_claim",
                    "rejected_invalid_region", "rejected_page_error",
                    "rejected_review_error", "provenance_quote_on_other_page",
                    "provenance_unverified_by_ocr", "observation_count"):
            if key in item:
                per_page[page][key] += 1
        if "observation_count" in item:
            obs_per_page[page] += item["observation_count"]
    print("REAL_BRIDGE_VISION_COUNT", meta.get("vision_count"), flush=True)
    print("REAL_BRIDGE_CALLS", len(meta["calls"]), flush=True)
    for page in sorted(per_page):
        print(f"REAL_BRIDGE page={page} aggregated={dict(per_page[page])}",
              flush=True)
    print("REAL_BRIDGE_OBSERVATIONS_BY_PAGE",
          {p: obs_per_page[p] for p in sorted(obs_per_page)}, flush=True)
    statuses = collections.Counter(r.status for r in rows)
    print("REAL_BRIDGE_ROW_STATUSES", dict(statuses), flush=True)
    print("REAL_BRIDGE_READING_COUNTS",
          {p: len(readings[p].visible_text) for p in sorted(readings)}, flush=True)
    unresolved = collections.Counter(
        len(readings[p].unresolved) for p in readings)
    print("REAL_BRIDGE_UNRESOLVED_LISTS", dict(unresolved), flush=True)


if __name__ == "__main__":
    asyncio.run(main())