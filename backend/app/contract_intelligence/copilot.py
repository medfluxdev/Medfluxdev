"""Contract copilot response guardrails.

A copilot answer is only publishable as grounded when citations/evidence exist.
"""

from __future__ import annotations


def copilot_response(*, answer: str, evidence: list[dict], unknowns: list[str] | None = None) -> dict:
    unknowns = list(unknowns or [])
    grounded = bool(evidence)
    if not grounded and not unknowns:
        unknowns.append("Answer has no source evidence.")
    return {
        "answer": answer,
        "evidence": evidence,
        "unknowns": unknowns,
        "grounded": grounded,
        "requires_review": not grounded or bool(unknowns),
    }
