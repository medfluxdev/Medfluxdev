"""Medflux STEP 8B-Semantik – Benchmark der FELDGRUPPEN-Pipeline mit echten Verträgen.

Nutzung (von der Repo-Wurzel, mit dem Backend-venv, Ollama muss laufen):
    .\backend\.venv\Scripts\python.exe scripts\benchmark_groups.py [--limit N] [--runs N]

Gleiche 6 Verträge & gleiche ground_truth.json wie STEP 8/8B; Vergleich über den
KORRIGIERTEN Matcher (Enum-.value-Fix) aus benchmark_extraction._match/_evaluate.
Die Pipeline ist die neue Feldgruppen-Extraktion (GroupPipeline hinter
ContractAnalysisOrchestrator). Der Verifier wird per Wrapper beobachtet, ohne
seine Logik zu verändern (er erfindet keinen Wert; Recording = reine Metadaten).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ai.contract_extractor import (  # noqa: E402
    ContractAnalysisOrchestrator,
    ContractAnalysisResult,
)
from app.ai.groups import extractor as groups_extractor  # noqa: E402
from app.ai.groups.evidence import verify_evidence  # noqa: E402
from app.documents.extraction.docx import extract_docx_units  # noqa: E402
from app.documents.extraction.schemas import (  # noqa: E402
    FileType,
    TextExtractionResult,
    UnitMethod,
)
from app.models.enums import ExtractionStatus  # noqa: E402

# Bewertung (korrigierter Matcher) aus dem bestehenden STEP-8B-Skript wiederverwenden
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from benchmark_extraction import _evaluate  # noqa: E402

BENCH = REPO_ROOT / "data" / "benchmark"
INPUT_DIR = BENCH / "input"
GT_PATH = BENCH / "ground_truth.json"


def build_extraction(document_id: str, docx_path: Path) -> TextExtractionResult:
    units = extract_docx_units(docx_path)
    total = sum(len(u.text) for u in units)
    text_available = any(bool(u.text) for u in units)
    return TextExtractionResult(
        document_id=document_id,
        file_type=FileType.DOCX,
        extraction_status=(
            ExtractionStatus.SUCCESS if text_available else ExtractionStatus.PARTIAL
        ),
        extraction_method=UnitMethod.TEXT,
        page_count=0,
        total_characters=total,
        text_available=text_available,
        requires_ocr=False,
        units=units,
        warnings=[],
    )


def _scalar(r: ContractAnalysisResult) -> dict:
    return {
        "status": r.status.value,
        "validation_status": r.validation_status.value,
        "requires_review": r.requires_review,
        "model": r.model,
        "prompt_version": r.prompt_version,
        "chunk_count": r.chunk_count,
        "processing_duration": round(r.processing_duration, 2),
        "timeout_count": r.timeout_count,
        "retry_count": r.retry_count,
        "truncated_chunks": r.truncated_chunks,
        "ai_call_count": r.ai_call_count,
        "groups_processed": r.groups_processed,
        "evidence_issues": r.evidence_issues,
        "verifier_issues": r.verifier_issues,
        "normalization_issues": r.normalization_issues,
        "message": r.message,
        "error": r.error,
    }


def evidence_support_report(contract, units) -> dict:
    """Deterministische Evidence-Verifikation des FINALEN Vertrags gegen die
    echten Texteinheiten (gleiche Logik wie die Pipeline, erneut angewendet,
    damit ein Feld nicht nur wegen eines vorhandenen Evidence-Objekts zählt)."""
    sections = [
        ("identity", contract.identity), ("dates", contract.dates),
        ("termination", contract.termination), ("costs", contract.costs),
        ("payment", contract.payment), ("services", contract.services),
        ("sla", contract.sla),
    ]
    out = {"sections_with_evidence": 0, "supported": 0, "unsupported": 0, "details": []}
    for name, sec in sections:
        ev = getattr(sec, "evidence", None)
        if ev is None:
            continue
        out["sections_with_evidence"] += 1
        verified, issues = verify_evidence(ev, units)
        if verified is not None and not issues:
            out["supported"] += 1
            out["details"].append({"section": name, "supported": True, "issues": []})
        else:
            out["unsupported"] += 1
            out["details"].append({"section": name, "supported": False, "issues": issues})
    return out


def _verifier_recorder():
    """Wrapper, der die Verifier-Entscheidungen je Feld aufzeichnet (kein Eingriff)."""
    captured = {"calls": 0, "decisions": None}
    original = groups_extractor.run_verifier

    async def wrapped(ai_service, contract, context, max_tokens=2200, units=None):
        res, calls = await original(
            ai_service, contract, context, max_tokens=max_tokens, units=units
        )
        captured["calls"] += 1
        captured["decisions"] = [
            {"field": d.field, "supported": d.supported, "reason": d.reason}
            for d in res.decisions
        ]
        return res, calls

    return original, wrapped, captured


def run_verifier_report(contract, units, captured) -> dict:
    decisions = captured.get("decisions") or []
    supported = [d for d in decisions if d["supported"]]
    unsupported = [d for d in decisions if not d["supported"]]
    return {
        "verifier_calls": captured.get("calls", 0),
        "fields_verified": len(decisions),
        "supported_fields": [d["field"] for d in supported],
        "unsupported_fields": [d["field"] for d in unsupported],
    }


async def run_one(key: str, spec: dict, orchestrator, original_verifier, wrapped_verifier,
                  captured) -> dict | None:
    fname = spec["file"]
    subdir = next(INPUT_DIR.iterdir()) if INPUT_DIR.exists() else None
    path = subdir / fname
    if subdir is None or not path.exists():
        return {"key": key, "error": "datei fehlt"}

    t0 = time.monotonic()
    print(f"[benchmark_groups] starte: {key} ({fname}) ...", flush=True)
    extraction = build_extraction(key, path)

    groups_extractor.run_verifier = wrapped_verifier  # nur Record (Testharness)
    try:
        result = await orchestrator.analyze(extraction)
    finally:
        groups_extractor.run_verifier = original_verifier
    duration = time.monotonic() - t0
    print(f"[benchmark_groups] fertig: {key} ({duration:.1f}s)", flush=True)

    report = {
        "key": key,
        "file": fname,
        "extraction": _scalar(result),
        "total_wall_duration": round(duration, 2),
    }
    report.update(_evaluate(spec, result))
    report["evidence"] = (
        evidence_support_report(result.contract, extraction.units)
        if result.contract else {"sections_with_evidence": 0, "supported": 0,
                                 "unsupported": 0, "details": []}
    )
    report["verifier"] = (
        run_verifier_report(result.contract, extraction.units, captured)
        if result.contract else {"verifier_calls": 0}
    )
    return report


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default=str(GT_PATH))
    ap.add_argument("--report", default=str(BENCH / "report_groups.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()

    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    orchestrator = ContractAnalysisOrchestrator()

    keys = list(gt["contracts"].keys())
    if args.limit:
        keys = keys[: args.limit]

    reports = []
    for key in keys:
        spec = gt["contracts"][key]
        original_verifier, wrapped_verifier, captured = _verifier_recorder()
        for _ in range(args.runs):
            rep = await run_one(key, spec, orchestrator,
                                original_verifier, wrapped_verifier, captured)
            if rep is not None:
                reports.append(rep)

    if args.runs > 1:
        best = set()
        for r in reports:
            k = (r["key"], r["fields_passed"])
        summary_extra = {"runs_per_contract": args.runs}
    else:
        summary_extra = {"runs_per_contract": 1}

    out = {"reports": reports, "summary": summary_extra}
    Path(args.report).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for r in reports:
        e = r.get("extraction") or {}
        v = r.get("verifier") or {}
        if "error" in r:
            print(f"  {r['key']}: FEHLER {r['error']}")
            continue
        print(
            f"  {r['key']}: {r['fields_passed']}/{r['fields_total']} | "
            f"validation={e.get('validation_status')} review={e.get('requires_review')} "
            f"chunks={e.get('chunk_count')} ai_calls={e.get('ai_call_count')} "
            f"groups={e.get('groups_processed')} to={e.get('timeout_count')} "
            f"retries={e.get('retry_count')} trunc={e.get('truncated_chunks')} "
            f"ev_issues={e.get('evidence_issues')} verif_fields={v.get('fields_verified')} "
            f"verif_calls={v.get('verifier_calls')} ({e.get('processing_duration')}s)"
        )
    print(f"Report: {Path(args.report)}")


if __name__ == "__main__":
    asyncio.run(main())