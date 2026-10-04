"""Explainable risk aggregation.

Risk is derived from explicit findings, never from an opaque confidence score.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskFinding(BaseModel):
    key: str
    severity: str
    explanation: str
    evidence_refs: list[str] = Field(default_factory=list)


_WEIGHTS = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def summarize_risk(findings: list[RiskFinding]) -> dict:
    if not findings:
        return {"level": "unknown", "score": None, "reasons": []}
    max_weight = max(_WEIGHTS.get(item.severity, 0) for item in findings)
    level = {0: "info", 1: "low", 2: "medium", 3: "high", 4: "critical"}[max_weight]
    score = round(sum(_WEIGHTS.get(item.severity, 0) for item in findings) / (4 * len(findings)), 3)
    return {"level": level, "score": score, "reasons": [item.model_dump() for item in findings]}
