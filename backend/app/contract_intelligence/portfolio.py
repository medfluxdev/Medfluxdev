"""Portfolio intelligence over accepted contract state.

This module intentionally uses deterministic filters over persisted facts.
Semantic retrieval can be layered on top later (pgvector) without making vector
similarity a source of contractual truth.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from app.contract_intelligence.models import PortfolioQuestion, PortfolioResult


def answer_portfolio_question(question: PortfolioQuestion, rows: Iterable[dict]) -> PortfolioResult:
    q = " ".join(question.query.lower().split())
    selected = []
    unknowns = []
    for row in rows:
        supplier = str(row.get("supplier") or "").lower()
        contract_id = row.get("contract_id")
        if question.supplier and question.supplier.lower() not in supplier:
            continue
        if question.contract_ids and contract_id not in question.contract_ids:
            continue
        if question.equipment_id and question.equipment_id not in set(row.get("equipment_ids") or []):
            continue
        if "uncovered" in q or "nicht abgedeckt" in q:
            if row.get("equipment_coverage") == "uncovered":
                selected.append(row)
        elif "expire" in q or "endet" in q or "ablauf" in q:
            end = row.get("end_date")
            if isinstance(end, date) and question.as_of_date and end >= question.as_of_date:
                selected.append(row)
        else:
            selected.append(row)
    ids = [row.get("contract_id") for row in selected if row.get("contract_id") is not None]
    if not selected:
        unknowns.append("No persisted contract facts matched the query.")
    return PortfolioResult(
        answer=f"{len(selected)} matching contract(s) from persisted accepted state.",
        contract_ids=ids,
        unknowns=unknowns,
    )
