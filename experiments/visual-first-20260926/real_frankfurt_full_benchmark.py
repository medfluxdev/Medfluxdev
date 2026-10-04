from __future__ import annotations
"""Instrumented full 9-page Frankfurt read-only benchmark (Phase 3 Test C).

Runs the ACTUAL integrated experimental pipeline on the verified real original:
Docling/OCR -> Visual-First (independent vision reads + OCR) -> reviews ->
Harness V3 reconciliation -> fail-closed contract. Prints AGGREGATE/metric
lines only; never prints contract text, quotes, credentials or URLs.

Mirrors the failing baseline (real_frankfurt_readonly_benchmark.py) semantics
and additionally records: per-stage timing, per-stage model calls/successes/
retries/timeouts/token usage, an explicit overall execution deadline, and peak
VRAM. The contested EUR 12,000 classification is reported support-level only.
"""
import asyncio
import collections
import hashlib
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

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
from app.ai.harness.v3 import HarnessV3
from app.ai.harness.vision import page_image

ROOT = Path(__file__).resolve().parent
SOURCE = Path.home() / "Desktop" / "Medflux-Integrated-Test" / "backend"
MODEL = "qwen3-vl:8b-instruct"
OVERALL_BUDGET_SECONDS = 1500.0
PAGE_IMAGE_LONGEST_SIDE = 1400


class VramSampler:
    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.samples: list[int] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=3, check=True,
                ).stdout.strip()
                used = int(out.splitlines()[0].strip())
                self.samples.append(used)
            except Exception:
                pass
            self._stop.wait(self.interval)

    def aggregate(self) -> dict:
        if not self.samples:
            return {"n": 0}
        return {
            "n": len(self.samples),
            "min": min(self.samples),
            "max": max(self.samples),
            "mean": round(sum(self.samples) / len(self.samples), 1),
        }


def preflight():
    checks = {}
    try:
        ps = subprocess.run(["ollama", "ps"], capture_output=True,
                            text=True, timeout=15, check=True).stdout
        resident = [ln.split()[0] for ln in ps.splitlines()[1:]
                    if ln.strip()]
        checks["resident_models"] = resident
        checks["only_selected_model_resident"] = resident == [MODEL]
    except Exception as exc:
        checks["ollama_ps_error"] = type(exc).__name__
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.free,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True).stdout
        total, free, used = (int(v) for v in out.splitlines()[0].split(","))
        checks["gpu_total_mib"] = total
        checks["gpu_free_mib"] = free
        checks["gpu_used_mib"] = used
        checks["gpu_headroom_ok"] = total - used >= 200
    except Exception as exc:
        checks["nvidia_smi_error"] = type(exc).__name__
    for k, v in checks.items():
        print(f"PREFLIGHT {k} = {v}", flush=True)
    if checks.get("ollama_ps_error"):
        raise SystemExit(2)
    if any(m != MODEL for m in (checks.get("resident_models") or [])):
        raise SystemExit(2)
    if not checks.get("gpu_headroom_ok"):
        raise SystemExit(2)


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


class TimedProvider(OllamaProvider):
    def __init__(self, s, r):
        super().__init__(s, model_resolver=r)
        self.calls_by_stage: dict[str, list[dict]] = collections.defaultdict(list)

    async def generate_request(self, text, system_prompt, schema, max_tokens,
                               context_tokens, images=None):
        title = (schema or {}).get("title") if isinstance(schema, dict) else None
        if title == "ProposedFactBatch":
            stage = "semantic"
        elif title == "VisionClaims":
            stage = "review" if "Conflicting" in text else "vision_vf"
        elif title == "VisualPageReading":
            stage = "warmup" if "blank placeholder" in text else "vision_hybrid"
        else:
            stage = "other"
        begin = time.monotonic()
        ok, exc_type, chars = False, None, 0
        try:
            raw = await super().generate_request(
                text, system_prompt, schema, max_tokens, context_tokens, images)
            ok, chars = True, len(raw)
        except Exception as exc:
            exc_type = type(exc).__name__
        self.calls_by_stage[stage].append({
            "ok": ok, "exc": exc_type,
            "seconds": round(time.monotonic() - begin, 3),
            "done_reason": self.last_done_reason,
            "prompt_tokens": (self.last_usage or {}).get("prompt_tokens"),
            "completion_tokens": (self.last_usage or {}).get("completion_tokens"),
            "max_tokens": max_tokens, "chars": chars,
        })
        if not ok:
            raise
        return raw


def stage_aggregate(records):
    okc = sum(1 for r in records if r["ok"])
    return {
        "calls": len(records),
        "ok": okc,
        "failed": len(records) - okc,
        "errors": sorted({r["exc"] for r in records if r["exc"]}),
        "seconds_sum": round(sum(r["seconds"] for r in records), 1),
        "seconds_mean": round(sum(r["seconds"] for r in records) / max(1, len(records)), 1),
        "seconds_max": round(max((r["seconds"] for r in records), default=0), 1),
        "truncated": sum(1 for r in records if r["done_reason"] in {"length", "max_tokens"}),
        "timeouts": sum(1 for r in records if r["exc"] == "AITimeoutError"),
        "prompt_tokens": sum(r["prompt_tokens"] for r in records if r["prompt_tokens"]),
        "completion_tokens": sum(r["completion_tokens"] for r in records if r["completion_tokens"]),
    }


async def main():
    preflight()
    pdf_path = find_frankfurt_pdf()
    print("VALIDATED_REAL_ORIGINAL_NINE_PAGES True", flush=True)

    t0 = time.monotonic()
    provider_doc = DoclingDocumentProvider()
    if not provider_doc.is_available():
        raise RuntimeError("Docling provider unavailable")
    canonical = provider_doc.process(pdf_path, DocumentIntelligenceSettings(
        do_ocr=True, do_table_structure=True, ocr_lang=["de"],
        max_pages=9, device="auto"))
    docling_seconds = time.monotonic() - t0
    print("ORIGINAL_DOCLING_PAGE_COUNT", len(canonical.pages), flush=True)
    print("ORIGINAL_DOCLING_SECONDS", round(docling_seconds, 1), flush=True)
    if len(canonical.pages) != 9:
        raise RuntimeError("Unexpected canonical page count")

    t_img = time.monotonic()
    images = {p: page_image(pdf_path, p, longest_side=PAGE_IMAGE_LONGEST_SIDE)
              for p in range(1, 10)}
    print("IMAGE_PREP_PAGES", len(images), flush=True)
    print("IMAGE_PREP_TOTAL_SECONDS", round(time.monotonic() - t_img, 3), flush=True)
    print("IMAGE_PREP_MEAN_B64_KB", round(sum(len(b) for b in images.values()) / len(images) / 1024, 1), flush=True)

    settings = Settings()
    settings.visual_first_experiment_enabled = True
    settings.visual_first_max_pages = 9
    settings.visual_first_max_reviews = 2
    settings.harness_context_tokens = 8192
    settings.harness_output_tokens = 1800
    settings.harness_vision_output_tokens = 600
    settings.ai_request_timeout_seconds = 300
    provider = TimedProvider(settings, lambda: MODEL)
    descriptor = SimpleNamespace(provider_id="ollama", model_id=MODEL,
                                 context_length=8192,
                                 capabilities=SimpleNamespace(text=True, vision=True))

    class Pinned:
        async def harness_runtime(self):
            return provider, descriptor

    sample = VramSampler(0.5)
    sample.start()
    started = time.monotonic()
    overall_timeout = False
    try:
        result = await asyncio.wait_for(
            HarnessV3(settings, ai=Pinned()).analyze(
                canonical, original_page_loader=lambda p: images[p]),
            timeout=OVERALL_BUDGET_SECONDS)
    except asyncio.TimeoutError:
        overall_timeout = True
        print("FULL_REAL_OVERALL_DEADLINE_TRIGGERED True", flush=True)
        print(f"FULL_REAL_OVERALL_DEADLINE_SECONDS {OVERALL_BUDGET_SECONDS}", flush=True)
    sample.stop()

    diagnostics = result.diagnostics or {}
    statuses = collections.Counter(row["status"] for row
                                   in diagnostics.get("visual_first_evidence_statuses", []))
    reasons = collections.Counter(row["reason"] for row
                                  in diagnostics.get("rejected_facts", []))
    calls_metrics = [c for c in diagnostics.get("calls", [])
                     if isinstance(c.get("latency_seconds"), (int, float))]
    if calls_metrics:
        print("FULL_REAL_AI_CALL_LATENCY_MIN", round(min(c["latency_seconds"] for c in calls_metrics), 1), flush=True)
        print("FULL_REAL_AI_CALL_LATENCY_MAX", round(max(c["latency_seconds"] for c in calls_metrics), 1), flush=True)
        print("FULL_REAL_AI_CALL_LATENCY_MEAN",
              round(sum(c["latency_seconds"] for c in calls_metrics) / len(calls_metrics), 1), flush=True)
    trunc = sum(1 for c in diagnostics.get("calls", []) if c.get("truncation_count"))
    print("FULL_REAL_TRUNCATION_CALLS", trunc, flush=True)
    print("FULL_REAL_RETRIED_CALLS",
          sum(1 for c in diagnostics.get("calls", []) if c.get("retried_with_output_tokens")), flush=True)

    if overall_timeout:
        for stage in ("warmup", "vision_vf", "vision_hybrid", "review", "semantic"):
            print(f"STAGE {stage} = {stage_aggregate(provider.calls_by_stage[stage])}", flush=True)
        print("FULL_REAL_OVERALL_TIMEOUT True", flush=True)
        raise SystemExit(3)

    print("FULL_REAL_ANALYSIS_STATUS", result.status.value, flush=True)
    print("FULL_REAL_REQUIRES_REVIEW", result.requires_review, flush=True)
    print("FULL_REAL_AI_CALLS", result.ai_call_count, flush=True)
    print("FULL_REAL_ELAPSED_SECONDS", round(time.monotonic() - started, 1), flush=True)
    print("FULL_REAL_ACCEPTED_FIELD_COUNT", len(diagnostics.get("accepted_facts", [])), flush=True)
    print("FULL_REAL_REJECT_REASONS_AGG", dict(reasons), flush=True)
    print("FULL_REAL_RECONCILIATION_AGG", dict(statuses), flush=True)
    vf = diagnostics.get("visual_first") or {}
    print("FULL_REAL_VISUAL_OBS", vf.get("vision_count"), flush=True)
    vf_calls = vf.get("calls") or []
    vf_obs_by_page = {}
    vf_rejected_counts = collections.Counter()
    for item in vf_calls:
        pg = item.get("page")
        if item.get("observation_count") is not None:
            vf_obs_by_page[pg] = vf_obs_by_page.get(pg, 0) + (item.get("observation_count") or 0)
        for key in ("rejected_page_error", "rejected_page_mismatch",
                    "rejected_malformed_claim", "rejected_review_error"):
            if item.get(key):
                vf_rejected_counts[key] += 1
        if item.get("rejected_invalid_region") and item.get("region_dropped"):
            vf_rejected_counts["region_dropped"] += 1
    print("FULL_REAL_VISUAL_OBS_BY_PAGE", vf_obs_by_page, flush=True)
    print("FULL_REAL_VISUAL_REJECTED", dict(vf_rejected_counts), flush=True)
    print("FULL_REAL_OPTICAL_OBS", vf.get("ocr_count"), flush=True)
    print("FULL_REAL_REVIEW_ATTEMPTS", vf.get("review_attempts"), flush=True)
    print("FULL_REAL_VISUAL_FIRST_PRESENT", bool(vf), flush=True)

    page_coverage: dict[int, int] = collections.Counter()
    domain_covered: collections.Counter = collections.Counter()
    for fact in diagnostics.get("accepted_facts", []):
        if isinstance(fact, dict):
            page = fact.get("page")
            if isinstance(page, int) and page >= 1:
                page_coverage[page] += 1
            field = fact.get("field") or ""
            domain_covered[field.split(".")[0]] += 1
    print("FULL_REAL_ACCEPTED_ORIGINAL_PAGE_REFERENCES", dict(sorted(page_coverage.items())), flush=True)
    print("FULL_REAL_DOMAIN_COVERAGE", dict(domain_covered), flush=True)

    for stage in ("warmup", "vision_vf", "vision_hybrid", "review", "semantic"):
        print(f"STAGE {stage} = {stage_aggregate(provider.calls_by_stage[stage])}", flush=True)

    vram = sample.aggregate()
    print("FULL_REAL_VRAM_USED_MIB", vram, flush=True)
    print("FULL_REAL_TOKEN_TOTALS",
          {"prompt": sum(s["prompt_tokens"] for s in
                         (stage_aggregate(provider.calls_by_stage[st]) for st in
                          ("warmup", "vision_vf", "vision_hybrid", "review", "semantic"))),
           "completion": sum(s["completion_tokens"] for s in
                             (stage_aggregate(provider.calls_by_stage[st]) for st in
                              ("warmup", "vision_vf", "vision_hybrid", "review", "semantic")))}, flush=True)

    if result.contract is None:
        raise RuntimeError("No grounded contract returned for real nine-page document")

    eq = result.contract.equipment or []
    print("FULL_REAL_EQUIPMENT_COUNT", len(eq), flush=True)
    included = getattr(result.contract.services, "included_services", []) or []
    excluded = getattr(result.contract.services, "excluded_services", []) or []
    print("FULL_REAL_INCLUDED_SERVICE_COUNT", len(included), flush=True)
    print("FULL_REAL_EXCLUDED_SERVICE_COUNT", len(excluded), flush=True)
    sla = result.contract.sla
    print("FULL_REAL_SLA_PRESENT",
          bool(getattr(sla, "service_hours", None)
               or getattr(sla, "response_time", None)
               or getattr(sla, "availability_24_7", None)), flush=True)
    termination = result.contract.termination
    print("FULL_REAL_CANCELLATION_PERIOD_UNIT",
          termination.cancellation_period.unit.value if termination.cancellation_period else None, flush=True)
    print("FULL_REAL_AUTOMATIC_RENEWAL",
          termination.automatic_renewal, flush=True)

    annual = result.contract.costs.annual_cost
    annual_amount = float(annual.amount) if annual and annual.amount is not None else None
    assigned_annual = annual_amount is not None and abs(annual_amount - 12000) < 0.01
    print("FULL_REAL_CONTESTED_AMOUNT_ASSIGNED_ANNUAL", assigned_annual, flush=True)
    annual_facts = [f for f in diagnostics.get("accepted_facts", [])
                    if isinstance(f, dict) and f.get("field") == "costs.annual_cost"]
    evidence_supported = any(
        isinstance(f.get("page"), int) and (f.get("quote") or f.get("source"))
        for f in annual_facts)
    annual_page = next((f.get("page") for f in annual_facts
                        if isinstance(f.get("page"), int)), None)
    print("FULL_REAL_CONTESTED_ANNUAL_EVIDENCE_ANCHORED", evidence_supported, flush=True)
    print("FULL_REAL_ANNUAL_COST_PAGE_REFERENCE", annual_page, flush=True)
    print("FULL_REAL_ANNUAL_COST_PRESENT", annual is not None, flush=True)
    # Gate-1 acceptance path diagnostics (aggregate booleans/counts only; never
    # contract text): whether the accepted annual fact's quote carries a
    # period anchor and whether any page-3 row was OCR+Vision corroborated.
    period_anchor = re.compile(
        r"j[äa]hrlich|jaehrlich|pro\s+jahr|jahres(?:preis|geb[\u00fc]hr|gebuehr)|(?<!semi[- ])\bannual\b", re.I)
    first_annual = next((f for f in annual_facts
                         if isinstance(f, dict)), None)
    quote = (first_annual.get("quote") or "") if first_annual else ""
    print("FULL_REAL_ANNUAL_FACT_QUOTE_HAS_ANCHOR",
          bool(quote and period_anchor.search(quote[:400])), flush=True)
    flows = diagnostics.get("visual_first_evidence_statuses", []) or []
    print("FULL_REAL_ANNUAL_PAGE_CORROBORATED_ROWS",
          sum(1 for row in flows
              if row.get("page") == annual_page
              and row.get("status") == "corroborated"), flush=True)
    # Aggregate page/status distribution of the reconciliation rows.
    by_page: dict[int, dict[str, int]] = {}
    for row in flows:
        page = row.get("page")
        bucket = by_page.setdefault(page, {})
        bucket[row.get("status")] = bucket.get(row.get("status"), 0) + 1
    print("FULL_REAL_EVIDENCE_STATUSES_BY_PAGE", dict(sorted(by_page.items())), flush=True)
    annual_row_statuses = sorted({r.get("status") for r in flows
                                  if r.get("page") == annual_page})
    print("FULL_REAL_ANNUAL_PAGE_ROW_STATUSES", annual_row_statuses, flush=True)
    # Deterministic document-text branch: does the annual page text itself
    # carry a period anchor (aggregate boolean, no text emitted)?
    annual_page_text = next(
        (p.text or "" for p in canonical.pages
         if int(p.page_number) == annual_page), "")
    print("FULL_REAL_ANNUAL_PAGE_TEXT_HAS_ANCHOR",
          bool(annual_page_text and period_anchor.search(annual_page_text[:4000])),
          flush=True)

    if not vf or vf.get("vision_count", 0) < 1:
        raise RuntimeError("Real original-image Visual-First produced no observations")
    if not result.requires_review:
        raise RuntimeError("Insufficiently reconciled original must require review")
    print("FULL_REAL_NO_PUBLIC_UPLOAD True", flush=True)
    print("REAL_FRANKFURT_READONLY_EXPERIMENT_COMPLETED True", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("BENCHMARK_INTERRUPTED", True, flush=True)
        raise SystemExit(130)