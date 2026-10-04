from __future__ import annotations
"""Instrumented single-original-page diagnostic (Test A). READ-ONLY.

Prints AGGREGATE metrics only. Never prints contract text, quotes or amounts.
Uses the original production database read-only and the experiment backend app.
"""
import asyncio
import collections
import os
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("MEDFLUX_INSECURE_DEV", "true")

import psutil
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.documents.storage import DocumentStorage, StorageError
from app.documents.intelligence.docling_provider import DoclingDocumentProvider
from app.documents.intelligence.provider import DocumentIntelligenceSettings
from app.ai.providers.ollama import OllamaProvider
from app.ai.harness.v3 import HarnessV3
from app.ai.harness.vision import page_image
import fitz

ROOT = Path(__file__).resolve().parent
SOURCE = Path.home() / "Desktop" / "Medflux-Integrated-Test" / "backend"
MODEL = "qwen3-vl:8b-instruct"


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
                    if __import__("hashlib").sha256(candidate.read_bytes()).hexdigest() != expected:
                        continue
                    with fitz.open(candidate) as pdf:
                        if len(pdf) != 9:
                            continue
                    return candidate
                except (StorageError, OSError, ValueError, RuntimeError):
                    continue
    raise RuntimeError("Verified Frankfurt 9-page original not available")


async def direct_calls(provider, descriptor, page_image_b64, pdf_path, out):
    settings = provider.settings

    async def one(label, prompt, schema, max_tokens, context, images=None):
        begin = time.monotonic()
        ok = False
        try:
            raw = await provider.generate_request(
                prompt, "Return JSON matching the schema.",
                schema, max_tokens, context, images)
            ok = True
        except Exception as exc:
            out[f"direct:{label}:error"] = type(exc).__name__
        out[f"direct:{label}:ok"] = ok
        out[f"direct:{label}:seconds"] = round(time.monotonic() - begin, 1)
        out[f"direct:{label}:done_reason"] = provider.last_done_reason
        usage = provider.last_usage or {}
        for k, v in usage.items():
            if isinstance(v, int):
                out[f"direct:{label}:{k}"] = v

    # 1) Cold tiny text ping (also serves as deterministic model warm-up).
    ping_schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
                   "required": ["ok"]}
    await one("cold_ping", "Say ok.", ping_schema, 8, 512)
    # 2) Warm vision read, bounded output.
    await one("vision_warm", "Read this page image. List visible literal labels only.", ping_schema, 400, 8192,
              [page_image_b64])
    # 3) Worst-case vision read at readonly-benchmark output budget (1800).
    await one("vision_max", "Read this page image. List visible literal labels only.", ping_schema, 1800, 8192,
              [page_image_b64])


async def harness_onepage(canonical, pdf_path, out):
    settings = Settings()
    settings.visual_first_experiment_enabled = True
    settings.visual_first_max_pages = 1
    settings.visual_first_max_reviews = 0
    settings.harness_context_tokens = 8192
    settings.harness_output_tokens = 450
    settings.ai_request_timeout_seconds = 150

    class Instrumented(OllamaProvider):
        def __init__(self, s, r, client=None):
            super().__init__(s, model_resolver=r, client=client)
            self.latencies = []

        async def generate_request(self, text, system_prompt, schema, max_tokens,
                                   context_tokens, images=None):
            begin = time.monotonic()
            try:
                return await super().generate_request(
                    text, system_prompt, schema, max_tokens, context_tokens, images)
            finally:
                self.latencies.append(round(time.monotonic() - begin, 1))

    provider = Instrumented(settings, lambda: MODEL)
    descriptor = SimpleNamespace(provider_id="ollama", model_id=MODEL,
                                 context_length=8192,
                                 capabilities=SimpleNamespace(text=True, vision=True))

    class Pinned:
        async def harness_runtime(self):
            return provider, descriptor

    started = time.monotonic()
    result = await HarnessV3(settings, ai=Pinned()).analyze(
        canonical, original_page_loader=lambda p: page_image(pdf_path, p, longest_side=1050))
    out["harness:elapsed_seconds"] = round(time.monotonic() - started, 1)
    out["harness:status"] = result.status.value
    out["harness:requires_review"] = result.requires_review
    out["harness:ai_calls"] = result.ai_call_count
    out["harness:provider_latencies"] = provider.latencies
    diag = result.diagnostics or {}
    calls = diag.get("calls", [])
    ok_calls = [c for c in calls if c.get("succeeded") is True]
    fail_calls = [c for c in calls if c.get("failed")]
    out["harness:call_total"] = len(calls)
    out["harness:call_succeeded"] = len(ok_calls)
    out["harness:call_failed"] = len(fail_calls)
    out["harness:call_failure_reasons"] = sorted(
        {c.get("error_type") for c in fail_calls if c.get("error_type")})
    out["harness:stage_counts"] = diag.get("stage_call_counts", {})
    lat = [c.get("latency_seconds") for c in ok_calls if isinstance(c.get("latency_seconds"), (int, float))]
    if lat:
        out["harness:latency_min"] = round(min(lat), 1)
        out["harness:latency_max"] = round(max(lat), 1)
        out["harness:latency_mean"] = round(sum(lat) / len(lat), 1)
    out["harness:accepted_fields"] = len(diag.get("accepted_facts", []))
    out["harness:rejected_by_reason"] = dict(collections.Counter(
        i.get("reason") for i in diag.get("rejected_facts", [])))
    vf = diag.get("visual_first") or {}
    out["harness:vf_vision_count"] = vf.get("vision_count")
    out["harness:vf_ocr_count"] = vf.get("ocr_count")
    out["harness:vf_review_attempts"] = vf.get("review_attempts")
    out["harness:issues_count"] = len(diag.get("issues", []))
    out["harness:truncation_calls"] = sum(
        1 for c in calls if c.get("truncation_count"))


async def main():
    out: dict = {}
    pdf_path = find_frankfurt_pdf()
    out["test:pdf_pages"] = 9
    out["test:pdf_bytes_kb"] = round(pdf_path.stat().st_size / 1024, 1)

    docling = DoclingDocumentProvider()
    if not docling.is_available():
        raise RuntimeError("Docling provider unavailable")
    t0 = time.monotonic()
    canonical = docling.process(pdf_path, DocumentIntelligenceSettings(
        do_ocr=True, do_table_structure=True, ocr_lang=["de"], max_pages=1, device="auto"))
    out["test:docling_pages"] = len(canonical.pages)
    out["test:docling_seconds"] = round(time.monotonic() - t0, 1)
    if len(canonical.pages) != 1:
        raise RuntimeError("Expected single canonical page")

    sample = VramSampler(0.5)
    sample.start()
    t0 = time.monotonic()
    image_b64 = page_image(pdf_path, 1, longest_side=1400)
    out["test:image_prep_seconds"] = round(time.monotonic() - t0, 3)
    out["test:image_b64_kb"] = round(len(image_b64) / 1024, 1)
    out["test:cpu_percent"] = psutil.cpu_percent(interval=0.5)
    out["test:ram_used_gb"] = round(psutil.virtual_memory().used / 1024 ** 3, 1)

    settings = Settings()
    settings.ai_request_timeout_seconds = 300
    settings.harness_context_tokens = 8192
    provider = OllamaProvider(settings, model_resolver=lambda: MODEL)
    descriptor = SimpleNamespace(provider_id="ollama", model_id=MODEL,
                                 context_length=8192,
                                 capabilities=SimpleNamespace(text=True, vision=True))
    await direct_calls(provider, descriptor, image_b64, pdf_path, out)

    # Re-pin with the onepage budget for the harness run.
    await harness_onepage(canonical, pdf_path, out)
    sample.stop()
    out["test:vram_used_mib"] = sample.aggregate()

    for k, v in sorted(out.items()):
        print(f"METRIC {k} = {v}", flush=True)
    if not out.get("direct:vision_max:ok"):
        raise SystemExit(3)


if __name__ == "__main__":
    asyncio.run(main())