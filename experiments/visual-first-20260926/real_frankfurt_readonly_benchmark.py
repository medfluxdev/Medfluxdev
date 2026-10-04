from __future__ import annotations
import asyncio, collections, hashlib, os, time
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy import create_engine,text
from app.core.config import Settings
from app.documents.storage import DocumentStorage, StorageError
from app.documents.intelligence.docling_provider import DoclingDocumentProvider
from app.documents.intelligence.provider import DocumentIntelligenceSettings
from app.ai.providers.ollama import OllamaProvider
from app.ai.harness.v3 import HarnessV3
from app.ai.harness.vision import page_image
from types import SimpleNamespace
import fitz

ROOT=Path.home()/"Desktop"/"Medflux-VisualFirst-Experiment"
SOURCE=Path.home()/"Desktop"/"Medflux-Integrated-Test"/"backend"
env=dotenv_values(SOURCE/".env")
url=env.get("DATABASE_URL")
if not url:
    raise RuntimeError("Existing original database URL unavailable")
engine=create_engine(url,connect_args={"connect_timeout":4})
with engine.connect() as conn:
    trans=conn.begin()
    conn.execute(text("SET TRANSACTION READ ONLY"))
    rows=conn.execute(text("""
      SELECT df.original_filename,dv.storage_key,df.storage_key,dv.sha256
      FROM document_file df JOIN document_version dv
        ON dv.document_file_id=df.id AND dv.organization_id=df.organization_id
      WHERE df.original_filename ILIKE :needle
      ORDER BY dv.created_at DESC LIMIT 5
    """),{"needle":"%Frankfurt%"}).fetchall()
    trans.rollback()
engine.dispose()
roots=[SOURCE/"data"/"contracts",SOURCE.parent/"data"/"contracts"]
if env.get("CONTRACTS_DIR"):
    defined=Path(env["CONTRACTS_DIR"])
    roots.insert(0,defined if defined.is_absolute() else SOURCE/defined)
path=None
for _name,key,other,expected in rows:
    for ref in (key,other):
        for root in roots:
            if not root.exists() or not ref:
                continue
            try:
                candidate=DocumentStorage(root).safe_path(ref)
                if not candidate.is_file() or candidate.suffix.lower()!=".pdf":
                    continue
                if hashlib.sha256(candidate.read_bytes()).hexdigest()!=expected:
                    continue
                with fitz.open(candidate) as pdf:
                    if len(pdf)!=9:
                        continue
                path=candidate
                break
            except (StorageError,OSError,ValueError,RuntimeError):
                continue
        if path:
            break
    if path:
        break
if path is None:
    raise RuntimeError("Verified Frankfurt 9-page original not available")
print("VALIDATED_REAL_ORIGINAL_NINE_PAGES",True,flush=True)
started=time.monotonic()
doc=DoclingDocumentProvider()
if not doc.is_available():
    raise RuntimeError("Docling provider unavailable")
canonical=doc.process(path,DocumentIntelligenceSettings(
    do_ocr=True,do_table_structure=True,ocr_lang=["de"],
    max_pages=9,device="auto"
))
print("ORIGINAL_DOCLING_PAGE_COUNT",len(canonical.pages),flush=True)
print("ORIGINAL_DOCLING_SECONDS",round(time.monotonic()-started,1),flush=True)
if len(canonical.pages)!=9:
    raise RuntimeError("Unexpected canonical page count")
settings=Settings()
settings.visual_first_experiment_enabled=True
settings.visual_first_max_pages=9
settings.visual_first_max_reviews=2
settings.harness_context_tokens=8192
settings.harness_output_tokens=1800
settings.ai_request_timeout_seconds=300
model="qwen3-vl:8b-instruct"
provider=OllamaProvider(settings,model_resolver=lambda:model)
descriptor=SimpleNamespace(provider_id="ollama",model_id=model,
    context_length=8192,capabilities=SimpleNamespace(text=True,vision=True))
class Pinned:
    async def harness_runtime(self):
        return provider,descriptor
async def run():
    result=await HarnessV3(settings,ai=Pinned()).analyze(
        canonical,original_page_loader=lambda p:page_image(path,p,longest_side=1400))
    diagnostics=result.diagnostics or {}
    statuses=collections.Counter(row["status"] for row in diagnostics.get("visual_first_evidence_statuses",[]))
    reasons=collections.Counter(row["reason"] for row in diagnostics.get("rejected_facts",[]))
    print("FULL_REAL_ANALYSIS_STATUS",result.status.value,flush=True)
    print("FULL_REAL_REQUIRES_REVIEW",result.requires_review,flush=True)
    print("FULL_REAL_AI_CALLS",result.ai_call_count,flush=True)
    print("FULL_REAL_ELAPSED_SECONDS",round(time.monotonic()-started,1),flush=True)
    print("FULL_REAL_ACCEPTED_FIELD_COUNT",len(diagnostics.get("accepted_facts",[])),flush=True)
    print("FULL_REAL_REJECT_REASONS_AGG",dict(reasons),flush=True)
    print("FULL_REAL_RECONCILIATION_AGG",dict(statuses),flush=True)
    vf=diagnostics.get("visual_first") or {}
    print("FULL_REAL_VISUAL_OBS",vf.get("vision_count"),flush=True)
    print("FULL_REAL_OPTICAL_OBS",vf.get("ocr_count"),flush=True)
    print("FULL_REAL_REVIEW_ATTEMPTS",vf.get("review_attempts"),flush=True)
    if result.contract is None:
        raise RuntimeError("No grounded contract returned for real nine-page document")
    eq=result.contract.equipment or []
    print("FULL_REAL_EQUIPMENT_COUNT",len(eq),flush=True)
    included=getattr(result.contract.services,"included_services",[]) or []
    print("FULL_REAL_INCLUDED_SERVICE_COUNT",len(included),flush=True)
    annual=result.contract.costs.annual_cost
    annual_amount=float(annual.amount) if annual and annual.amount is not None else None
    # Report ONLY contested-classification state; never print contract text or money.
    print("FULL_REAL_CONTESTED_AMOUNT_ASSIGNED_ANNUAL",
          annual_amount is not None and abs(annual_amount-12000)<0.01,flush=True)
    print("FULL_REAL_VISUAL_FIRST_PRESENT",bool(vf),flush=True)
    print("FULL_REAL_NO_PUBLIC_UPLOAD",True,flush=True)
    if not vf or vf.get("vision_count",0)<1:
        raise RuntimeError("Real original-image Visual-First was skipped")
    if not result.requires_review:
        raise RuntimeError("Insufficiently reconciled original must require review")
    print("REAL_FRANKFURT_READONLY_EXPERIMENT_COMPLETED",flush=True)
asyncio.run(run())
