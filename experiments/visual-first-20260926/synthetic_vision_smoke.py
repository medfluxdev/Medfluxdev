from __future__ import annotations
import asyncio
import os
from pathlib import Path
import fitz

from app.core.config import Settings
from app.ai.providers.ollama import OllamaProvider
from app.ai.harness.document import DocumentModel
from app.ai.harness.source_signals import collect_source_signals
from app.ai.harness.visual_first_bridge import prepare_visual_first
from app.ai.harness.vision import page_image
from app.documents.intelligence.docling_provider import DoclingDocumentProvider
from app.documents.intelligence.provider import DocumentIntelligenceSettings

ROOT=Path.home()/"Desktop"/"Medflux-VisualFirst-Experiment"
DEST=ROOT/"synthetic-smoke"
DEST.mkdir(exist_ok=True)
PDF=DEST/"synthetic_medflux_contract.pdf"
# Fully synthetic fictional text. Never access any user contract in this smoke.
native=fitz.open()
page=native.new_page(width=595,height=842)
page.insert_text((44,70),"SYNTHETISCHER WARTUNGSVERTRAG",fontsize=17)
page.insert_text((44,140),"Geraet: DEMO OPTIS Mobile Next",fontsize=16)
page.insert_text((44,215),"Vorauszahlung: 12.000 EUR",fontsize=17)
page.insert_text((44,290),"Vertragsbeginn: 04.06.2025",fontsize=15)
page.insert_text((44,365),"Jahresgebuehr: nicht vereinbart",fontsize=15)
png=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False).tobytes("png")
scan=fitz.open()
p=scan.new_page(width=595,height=842)
p.insert_image(p.rect,stream=png)
scan.save(PDF)
native.close();scan.close()
print("SYNTHETIC_IMAGE_ONLY_PDF_CREATED")
doc=DoclingDocumentProvider()
if not doc.is_available():
    raise RuntimeError("Docling package unavailable")
canonical=doc.process(PDF,DocumentIntelligenceSettings(
    do_ocr=True,do_table_structure=True,ocr_lang=["de","en"],
    max_pages=1,device="cpu"))
signals=collect_source_signals(DocumentModel.build(canonical))
money=[s for s in signals if s["kind"]=="money"]
print("DOCLING_PAGES",len(canonical.pages),"MONEY_SIGNALS",len(money))
if len(canonical.pages)!=1 or not money:
    raise RuntimeError("Independent synthetic OCR did not deliver money evidence")
async def execute():
    settings=Settings()
    settings.ai_request_timeout_seconds=250
    provider=OllamaProvider(settings,model_resolver=lambda:"qwen3-vl:8b-instruct")
    readings,rows,meta=await prepare_visual_first(
        canonical=canonical,source_signals=signals,
        page_image_loader=lambda p:page_image(PDF,p,longest_side=1400),
        provider=provider,context=8192,output_tokens=1200,
        max_pages=1,max_reviews=0)
    print("VISUAL_FIRST_MODEL_OBSERVATIONS",meta["vision_count"])
    print("OPTICAL_OBSERVATIONS",meta["ocr_count"])
    print("RECONCILED_ITEMS",len(rows))
    print("MANUAL_REVIEW_REQUIRED",all(x.requires_review for x in rows))
    print("PERCEPTION_STATUSES",",".join(sorted(set(x.status for x in rows))))
    print("SOURCE_IMAGE_SHA256_PRESENT",len(meta["image_sha256_by_page"][1])==64)
    if not meta["vision_count"] or not rows:
        raise RuntimeError("Selected vision model produced no usable observations")
    if not all(x.requires_review for x in rows):
        raise RuntimeError("Fail-closed review invariant violated")
    print("SYNTHETIC_REAL_OCR_QWEN_E2E_PASSED")
asyncio.run(execute())
