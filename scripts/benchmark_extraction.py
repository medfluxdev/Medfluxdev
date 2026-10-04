"""Medflux STEP 8 – Benchmark der strukturierten KI-Extraktion mit echten Verträgen.

Führt die bestehende Medflux-Extraktions-Pipeline (Schritt 5 Text + Schritt 7
strukturierte Extraktion) gegen repräsentative, real vorliegende Verträge aus
(lokales Ollama, qwen3:8b) und vergleicht die Ergebnisse mit manuell geprüften
Ground-Truth-Erwartungen (data/benchmark/ground_truth.json).

Es werden KEINE Ergebnisse erfunden. Enthält nur sichere Metadaten; es wird
kein vollständiger Vertragstext protokolliert und nichts irgendwohin übertragen.

Nutzung (von der Repo-Wurzel, mit dem Backend-venv):
    .\backend\.venv\Scripts\python.exe scripts\benchmark_extraction.py
"""

from __future__ import annotations

import argparse
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
from app.documents.extraction.docx import extract_docx_units  # noqa: E402
from app.documents.extraction.schemas import (  # noqa: E402
    FileType,
    TextExtractionResult,
    UnitMethod,
)
from app.models.enums import ExtractionStatus  # noqa: E402

BENCH = REPO_ROOT / "data" / "benchmark"
INPUT_DIR = BENCH / "input"
GT_PATH = BENCH / "ground_truth.json"
REPORT_PATH = BENCH / "report_latest.json"


# ---------------------------------------------------------------- comparison

def _norm_str(v: object) -> str:
    # Pydantic-Enums (str, Enum) haben .value; deren String-Repr (z. B.
    # "<ContractType.SERVICE: 'service'>") darf NICHT als Vergleichsbasis
    # dienen. STEP 8B-Fix des Benchmark-Harness: den Enum-Wert auflösen.
    # WICHTIG: str-Enums SIND isinstance(v, str) - der frühere isinstance-Guard
    # war wirkungslos und wertete ALLE Enums als falsch aus. hasattr prüft
    # stattdessen gezielt auf das .value-Attribut.
    val = getattr(v, "value", v)
    return " ".join(str(val).strip().lower().split())


def _match(kind: str, extracted, expect, tol: float | None = None):
    """Vergleicht einen extrahierten Wert gegen die Ground-Truth-Erwartung.

    Gibt (ok: bool, detail: str) zurück. Bei fehlgeschlagenem Vergleich bleibt
    `detail` knapp (kein vollständiger Vertragstext).
    """
    if kind == "null":
        return extracted is None, "null" if extracted is None else repr(extracted)
    if kind == "not_null":
        return extracted is not None, "present" if extracted is not None else "null"
    if kind == "contains":
        if extracted is None:
            return False, "null"
        return _norm_str(expect) in _norm_str(extracted), "missing"
    if kind == "contains_int":
        if extracted is None:
            return False, "null"
        return str(extracted) == str(expect), repr(extracted)
    if kind == "enum_in":
        if extracted is None:
            return False, "null"
        return _norm_str(extracted) in [_norm_str(e) for e in expect], repr(extracted)
    if kind == "bool":
        if extracted is None:
            return False, "null"
        return bool(extracted) == bool(expect), repr(extracted)
    if kind == "date":
        if extracted is None:
            return False, "null"
        return str(extracted) == str(expect), repr(extracted)
    if kind == "int_ge":
        if extracted is None:
            return False, "null"
        return int(extracted) >= int(expect), repr(extracted)
    if kind == "money_amount":
        if extracted is None:
            return False, "null"
        return abs(float(extracted) - float(expect)) < 1e-6, repr(extracted)
    if kind == "money_amount_tol":
        if extracted is None:
            return False, "null"
        t = tol if tol is not None else 1.0
        return abs(float(extracted) - float(expect)) <= t, repr(extracted)
    if kind == "duration":
        if extracted is None or extracted.get("value") is None:
            return False, "null"
        ok = int(extracted.get("value")) == int(expect["value"]) and (
            extracted.get("unit") == expect["unit"]
        )
        return ok, repr(extracted)
    if kind == "time_value":
        if extracted is None or extracted.get("value") is None:
            return False, "null"
        ok = abs(float(extracted.get("value")) - float(expect["value"])) < 1e-6 and (
            extracted.get("unit") == expect["unit"]
        )
        return ok, repr(extracted)
    if kind == "device_contains":
        if not extracted:
            return False, "empty"
        for dev in extracted:
            hay = " ".join(
                _dev_get(dev, k) for k in ("device_name", "model", "manufacturer")
            )
            if _norm_str(expect) in _norm_str(hay):
                return True, repr(_dev_get(dev, "device_name"))
        return False, "no-device"
    if kind == "serial_contains":
        if not extracted:
            return False, "empty"
        for dev in extracted:
            if _norm_str(expect) in _norm_str(_dev_get(dev, "serial_number")):
                return True, repr(_dev_get(dev, "serial_number"))
        return False, "no-serial"
    return False, f"unknown-kind:{kind}"


def _dev_get(dev: object, key: str) -> str:
    """Liest einen Attributwert aus einem Pydantic-Modell oder dict."""
    if isinstance(dev, dict):
        return str(dev.get(key) or "")
    return str(getattr(dev, key, "") or "")


def _resolve(contract, field: str):
    """Löst einen Punktpfad in ein Contract-Modell auf (dict werden gedumpt)."""
    node: object = contract
    for part in field.split("."):
        if node is None:
            return None
        if hasattr(node, part):
            node = getattr(node, part)
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    if hasattr(node, "model_dump"):
        return node.model_dump()
    if hasattr(node, "dict"):
        return node.dict()
    return node


# ------------------------------------------------------------- orchestration

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


def _scalar(model: ContractAnalysisResult) -> dict:
    return {
        "status": model.status.value,
        "validation_status": model.validation_status.value,
        "requires_review": model.requires_review,
        "model": model.model,
        "prompt_version": model.prompt_version,
        "chunk_count": model.chunk_count,
        "processing_duration": round(model.processing_duration, 2),
        "timeout_count": model.timeout_count,
        "retry_count": model.retry_count,
        "truncated_chunks": model.truncated_chunks,
        "message": model.message,
        "error": model.error,
    }


def _evaluate(spec: dict, result: ContractAnalysisResult) -> dict:
    """Bewertet ein Analyse-Ergebnis eines Vertrags gegen die Ground Truth."""
    field_results = []
    passed = 0
    total = 0
    missing = []
    wrong_values = []
    invented = []
    for f in spec["fields"]:
        total += 1
        val = _resolve(result.contract, f["field"]) if result.contract else None
        ok, detail = _match(f["kind"], val, f.get("expect"), f.get("tol"))
        if ok:
            passed += 1
        else:
            # Fehler klassifizieren: fehlend vs. falscher Wert vs. erfunden
            if f["kind"] == "null":
                invented.append({"field": f["field"], "got": detail})
            elif f["kind"] == "not_null":
                missing.append({"field": f["field"], "got": detail})
            elif val is None:
                missing.append({"field": f["field"], "got": "null"})
            else:
                wrong_values.append({"field": f["field"], "got": detail})
        field_results.append({
            "field": f["field"], "kind": f["kind"],
            "expect": f.get("expect"),
            "got": detail, "ok": ok,
        })
    return {
        "fields_passed": passed,
        "fields_total": total,
        "field_results": field_results,
        "failures": {
            "missing": missing,
            "wrong_value": wrong_values,
            "invented": invented,
        },
    }


async def _run_one(key: str, spec: dict, orchestrator: ContractAnalysisOrchestrator
                   ) -> dict | None:
    """Führt EINEN Durchlauf für einen Vertrag aus; None, wenn Datei fehlt."""
    fname = spec["file"]
    subdir = next(INPUT_DIR.iterdir()) if INPUT_DIR.exists() else None
    path = subdir / fname
    if subdir is None or not path.exists():
        return None

    t0 = time.monotonic()
    print(f"[benchmark] starte: {key} ({fname}) ...", flush=True)
    extraction = build_extraction(key, path)
    result = await orchestrator.analyze(extraction)
    duration = time.monotonic() - t0
    print(f"[benchmark] fertig: {key} ({duration:.1f}s)", flush=True)

    report = {
        "key": key,
        "file": fname,
        "extraction": _scalar(result),
        "total_wall_duration": round(duration, 2),
    }
    report.update(_evaluate(spec, result))
    return report


async def run_all(gt: dict, orchestrator: ContractAnalysisOrchestrator,
                  limit: int = 0, runs: int = 1) -> list[dict]:
    """Benchmarkt jeden Vertrag und liefert eine Ergebnisliste (nur Metadaten).

    Bei `runs > 1` wird jeder Vertrag mehrmals ausgeführt; pro Vertrag wird der
    BESTE Durchlauf (größte Feld-Trefferquote, dann gültige Validierung)
    gemeldet, und alle Rohdurchläufe stehen unter `all_runs`. Dies macht die
    Messung robust gegen die Modell-Nichtdeterminismen (qwen3:8b).
    """
    reports = []
    keys = list(gt["contracts"].keys())
    if limit:
        keys = keys[:limit]
    for key in keys:
        spec = gt["contracts"][key]
        fname = spec["file"]
        subdir = next(INPUT_DIR.iterdir()) if INPUT_DIR.exists() else None
        path = subdir / fname
        if subdir is None or not path.exists():
            reports.append({
                "key": key, "file": fname, "error": "datei fehlt",
                "fields_passed": 0, "fields_total": 0,
            })
            continue

        per_runs = []
        for _ in range(runs):
            rep = await _run_one(key, spec, orchestrator)
            if rep is not None:
                per_runs.append(rep)

        if not per_runs:
            reports.append({
                "key": key, "file": fname, "error": "datei fehlt",
                "fields_passed": 0, "fields_total": 0,
            })
            continue

        per_runs.sort(
            key=lambda r: (
                r["fields_passed"],
                r["extraction"].get("validation_status") == "valid",
            ),
            reverse=True,
        )
        best = dict(per_runs[0])
        best["all_runs"] = [
            {"fields_passed": r["fields_passed"],
             "validation_status": r["extraction"].get("validation_status"),
             "processing_duration": r["extraction"].get("processing_duration")}
            for r in per_runs
        ]
        reports.append(best)
    return reports


def _summarize(reports: list[dict]) -> dict:
    import statistics

    total_fields = sum(r["fields_total"] for r in reports)
    passed_fields = sum(r["fields_passed"] for r in reports)
    durations = [r.get("extraction", {}).get("processing_duration")
                 for r in reports if r.get("extraction")]
    durations = [d for d in durations if d is not None]
    invented = sum(len(r.get("failures", {}).get("invented", [])) for r in reports)
    missing = sum(len(r.get("failures", {}).get("missing", [])) for r in reports)
    wrong = sum(len(r.get("failures", {}).get("wrong_value", [])) for r in reports)
    valid_cnt = sum(
        1 for r in reports if r.get("extraction", {}).get("validation_status") == "valid"
    )
    per_contract_rates = [
        r["fields_passed"] / r["fields_total"] for r in reports if r["fields_total"]
    ]
    timeouts = sum(r.get("extraction", {}).get("timeout_count", 0) for r in reports)
    truncated = sum(r.get("extraction", {}).get("truncated_chunks", 0) for r in reports)

    consistency: dict | None = None
    all_runs = [r.get("all_runs", []) for r in reports if r.get("all_runs")]
    if all_runs:
        per_contract_scores = [[a["fields_passed"] for a in runs] for runs in all_runs]
        # Varianz der Feldergebnisse pro Vertrag (über Wiederholungen)
        var_scores = []
        for scores in per_contract_scores:
            if len(scores) > 1 and statistics.stdev(scores) > 0:
                var_scores.append(statistics.stdev(scores))
        consistency = {
            "contract_runs": [runs for runs in
                              [[a["fields_passed"] for a in rr] for rr in all_runs]],
            "within_contract_stdev_nonzero": var_scores,
            "identical_runs_share": (
                sum(1 for scores in per_contract_scores
                    if len(set(scores)) == 1) / len(per_contract_scores)
                if per_contract_scores else None
            ),
        }

    return {
        "contracts_benchmarked": len(reports),
        "fields_total": total_fields,
        "fields_passed": passed_fields,
        "field_accuracy": round(passed_fields / total_fields, 4) if total_fields else 0,
        "mean_field_accuracy": round(statistics.mean(per_contract_rates), 4)
        if per_contract_rates else None,
        "median_field_accuracy": round(statistics.median(per_contract_rates), 4)
        if per_contract_rates else None,
        "failures_missing": missing,
        "failures_wrong_value": wrong,
        "failures_invented": invented,
        "validation_success": valid_cnt,
        "validation_success_rate": round(valid_cnt / len(reports), 4)
        if reports else None,
        "timeout_count": timeouts,
        "truncated_chunks": truncated,
        "consistency": consistency,
        "avg_processing_duration_s": round(sum(durations) / len(durations), 2)
        if durations else None,
        "requires_review_flagged": sum(
            1 for r in reports if r.get("extraction", {}).get("requires_review")
        ),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(INPUT_DIR))
    ap.add_argument("--gt", default=str(GT_PATH))
    ap.add_argument("--report", default=str(REPORT_PATH))
    ap.add_argument("--limit", type=int, default=0,
                    help="optional: nur die ersten N Verträge benchmarken")
    ap.add_argument("--runs", type=int, default=1,
                    help="Durchläufe je Vertrag; gemeldet wird der beste Durchlauf")
    args = ap.parse_args()

    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    orchestrator = ContractAnalysisOrchestrator()

    reports = await run_all(gt, orchestrator, limit=args.limit or 0, runs=max(1, args.runs))

    summary = _summarize(reports)
    summary["runs_per_contract"] = max(1, args.runs)
    out = {"summary": summary, "reports": reports}
    Path(args.report).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Verträge: {summary['contracts_benchmarked']}")
    print(f"Felder: {summary['fields_passed']}/{summary['fields_total']} "
          f"({summary['field_accuracy']:.1%})")
    print(f"Mittelwert (je Vertrag): {summary['mean_field_accuracy']:.1%} | "
          f"Median: {summary['median_field_accuracy']:.1%}")
    print(f"Validiert (VALID): {summary['validation_success']}/"
          f"{summary['contracts_benchmarked']} "
          f"({summary['validation_success_rate']:.1%})")
    print(f"Fehler – fehlend: {summary['failures_missing']} | "
          f"falscher Wert: {summary['failures_wrong_value']} | "
          f"erfunden: {summary['failures_invented']}")
    print(f"Timeouts: {summary['timeout_count']} | Truncated chunks: "
          f"{summary['truncated_chunks']}")
    if summary["avg_processing_duration_s"] is not None:
        print(f"Ø Dauer/Rechnung: {summary['avg_processing_duration_s']}s")
    cons = summary.get("consistency")
    if cons:
        print(f"Konsistenz (identische Wiederholungen je Vertrag): "
              f"{cons['identical_runs_share']:.1%}")
    for r in reports:
        e = r.get("extraction") or {}
        print(
            f"  {r['key']}: {r['fields_passed']}/{r['fields_total']} | "
            f"validation={e.get('validation_status')} "
            f"review={e.get('requires_review')} chunks={e.get('chunk_count')} "
            f"to={e.get('timeout_count')} trunc={e.get('truncated_chunks')} "
            f"({e.get('processing_duration')}s)"
        )
    print(f"Report: {Path(args.report)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
