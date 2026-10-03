"""Portfolio intelligence over accepted contract state.

This module intentionally uses deterministic filters over persisted facts.
Semantic retrieval can be layered on top later (pgvector) without making vector
similarity a source of contractual truth.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from app.contract_intelligence.models import PortfolioQuestion, PortfolioResult


_STOPWORDS = {
    "alle", "all", "bitte", "die", "find", "finde", "finden", "für", "fuer",
    "ich", "me", "mit", "show", "suche", "und", "vertraege", "vertrag", "verträge",
    "welche", "welcher", "welchen", "what", "with", "zeige", "zu",
}


def _search_terms(query: str) -> list[str]:
    cleaned = query.replace("?", " ").replace(",", " ").replace(".", " ")
    return [token for token in cleaned.split() if len(token) >= 2 and token not in _STOPWORDS]


def _row_text(row: dict) -> str:
    values = [
        row.get("contract_number"),
        row.get("contract_title"),
        row.get("supplier"),
        row.get("status"),
        row.get("risk_level"),
    ]
    values.extend(row.get("equipment_names") or [])
    values.extend(row.get("clause_summaries") or [])
    return " ".join(str(value).lower() for value in values if value)


def answer_portfolio_question(question: PortfolioQuestion, rows: Iterable[dict]) -> PortfolioResult:
    q = " ".join(question.query.lower().split())
    selected = []
    unknowns = []
    terms = _search_terms(q)
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
        elif "expire" in q or "endet" in q or "enden" in q or "ablauf" in q or "auslauf" in q:
            end = row.get("end_date")
            if isinstance(end, date) and question.as_of_date and end >= question.as_of_date:
                selected.append(row)
        elif terms:
            haystack = _row_text(row)
            if all(term in haystack for term in terms):
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
