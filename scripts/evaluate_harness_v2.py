"""Offline comparison of manually supplied expectations and a v2 snapshot; no inference."""
import argparse
import json
from pathlib import Path


def evaluate(snapshot, expected):
    if snapshot.get("analysis", {}).get("harness_version") != "v2":
        raise ValueError("Expected a Harness v2 contract snapshot")
    candidates = snapshot["analysis"]["harness"].get("candidates", [])
    result = []
    for entry in expected:
        field = entry["field"]
        matches = [c for c in candidates if c["field"] == field]
        supported = [c for c in matches if c["status"] == "supported"]
        if not matches or all(c["status"] == "missing" for c in matches):
            verdict = "missing"
        elif not supported:
            verdict = "ambiguous/abstained"
        elif entry.get("supported_by_document") is False:
            verdict = "unsupported hallucination"
        else:
            values = [c.get("normalized_value") if c.get("normalized_value") is not None else c.get("value") for c in supported]
            verdict = "correct" if values and all(v == entry["value"] for v in values) else "incorrect"
        result.append({"field": field, "category": entry.get("category", field.split(".")[0]),
                       "verdict": verdict, "evidence": entry.get("evidence_verdict", "not reviewed")})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("expectations", type=Path)
    args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(args.snapshot.read_text(encoding="utf-8")),
                              json.loads(args.expectations.read_text(encoding="utf-8"))), indent=2))
