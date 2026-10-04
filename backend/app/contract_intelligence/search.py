"""Evidence-first portfolio search/citation helpers.

Semantic search adapters may retrieve candidate contracts, but final answers must
be assembled from accepted facts and evidence references.
"""

from __future__ import annotations


def build_search_document(contract: dict) -> str:
    parts = [
        contract.get("contract_number"),
        contract.get("supplier"),
        contract.get("contract_title"),
        contract.get("status"),
        contract.get("risk_level"),
    ]
    parts.extend(contract.get("equipment_names") or [])
    parts.extend(contract.get("clause_summaries") or [])
    return " | ".join(str(p) for p in parts if p)


def evidence_first_answer(answer: str, evidence: list[dict]) -> dict:
    return {
        "answer": answer,
        "evidence": evidence,
        "grounded": bool(evidence),
        "requires_review": not bool(evidence),
    }
