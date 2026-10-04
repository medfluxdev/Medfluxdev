from __future__ import annotations
import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.core.config import Settings
from app.ai.providers.ollama import OllamaProvider
from app.ai.harness.v3 import HarnessV3
from app.ai.harness.vision import page_image
from app.documents.intelligence.docling_provider import DoclingDocumentProvider
from app.documents.intelligence.provider import DocumentIntelligenceSettings

ROOT=Path.home()/"Desktop"/"Medflux-VisualFirst-Experiment"
PDF=ROOT/"synthetic-smoke"/"synthetic_medflux_contract.pdf"
if not PDF.is_file():
    raise RuntimeError("Synthetic-only test PDF missing")
docling=DoclingDocumentProvider()
canonical=docling.process(PDF, DocumentIntelligenceSettings(
    do_ocr=True,ocr_lang=["de"],do_table_structure=True,device="cpu",max_pages=1))
settings=Settings()
settings.visual_first_experiment_enabled=True
settings.visual_first_max_pages=1
settings.visual_first_max_reviews=0
settings.harness_context_tokens=8192
settings.harness_output_tokens=1400
settings.ai_request_timeout_seconds=240
model="qwen3-vl:8b-instruct"
provider=OllamaProvider(settings,model_resolver=lambda:model)
descriptor=SimpleNamespace(provider_id="ollama",model_id=model,context_length=8192,
                           capabilities=SimpleNamespace(text=True,vision=True))
class PinnedSyntheticRuntime:
    async def harness_runtime(self):
        return provider,descriptor
async def execute():
    result=await HarnessV3(settings,ai=PinnedSyntheticRuntime()).analyze(
        canonical,original_page_loader=lambda p:page_image(PDF,p,longest_side=1400))
    print("HARNESS_STATUS",result.status.value)
    print("HARNESS_REVIEW",result.requires_review)
    print("HARNESS_AI_CALL_COUNT",result.ai_call_count)
    print("HARNESS_ERROR_CATEGORY",result.error or "none")
    diag=result.diagnostics or {}
    print("HARNESS_ACCEPTED_COUNT",len(diag.get("accepted_facts",[])))
    print("HARNESS_REJECTED_REASONS",
        sorted({item.get("reason") for item in diag.get("rejected_facts",[])}))
    print("VISUAL_FIRST_DIAGNOSTICS_PRESENT",
        isinstance(diag.get("visual_first"),dict))
    if result.contract is None:
        raise RuntimeError("No grounded contract object produced by complete synthetic path")
    eq=result.contract.equipment or []
    print("SYNTHETIC_EQUIPMENT_COUNT",len(eq))
    cost=result.contract.costs.annual_cost
    if cost is not None and cost.amount is not None and abs(float(cost.amount)-12000)<0.01:
        raise RuntimeError("Prepayment incorrectly classified as annual recurring cost")
    if not result.requires_review:
        raise RuntimeError("Visual-only observations must trigger human review")
    if not diag.get("visual_first"):
        raise RuntimeError("Visual-First opt-in was bypassed")
    print("FULL_SYNTHETIC_V3_VISUAL_FIRST_PATH_PASSED")
asyncio.run(execute())
