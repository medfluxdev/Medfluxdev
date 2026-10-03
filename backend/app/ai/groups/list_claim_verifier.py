"""Deterministic verification for list-valued and residual critical claims.

Every extracted service-list item is checked independently. The same production
hook also invokes the residual deterministic gate for critical claim shapes that
cannot safely use the scalar semantic verifier (price schedules, variable
charges, remaining tri-state services, service hours and exact-text clauses).
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from app.ai.groups.residual_claim_verifier import verify_residual_critical_claims
from app.models.contract import Contract


_NEGATION_RE = re.compile(
    r"\b(?:nicht|kein(?:e|en|er)?|ohne|ausgeschlossen|nicht\s+enthalten|nicht\s+inklusive)\b",
    re.I,
)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _texts(units: Iterable[object]) -> list[str]:
    return [
        text
        for unit in units
        if (text := str(getattr(unit, "text", "") or "").strip())
    ]


def _item_present(text: str, item: str) -> bool:
    needle = _norm(item)
    return bool(needle) and needle in _norm(text)


def _local_clause(text: str, start: int, end: int) -> str:
    separators = ".;|\n"
    left = 0
    for sep in separators:
        pos = text.rfind(sep, 0, start)
        if pos >= 0:
            left = max(left, pos + 1)
    right = len(text)
    for sep in separators:
        pos = text.find(sep, end)
        if pos >= 0:
            right = min(right, pos)
    return text[left:right]


def _excluded_item_supported(text: str, item: str) -> bool:
    if not _item_present(text, item):
        return False
    low = text.casefold()
    needle = _norm(item)
    idx = low.find(needle)
    clause = _local_clause(text, idx, idx + len(needle))
    return bool(_NEGATION_RE.search(clause))


def verify_service_list_claims(contract: Contract, units: Iterable[object]) -> list[str]:
    texts = _texts(units)
    issues: list[str] = []

    for item in contract.services.included_services:
        if any(_item_present(text, item) for text in texts):
            continue
        issues.append(
            f"services.included_services[{item!r}]: Eintrag nicht wörtlich in der Quelle gestützt"
        )

    for item in contract.services.excluded_services:
        if any(_excluded_item_supported(text, item) for text in texts):
            continue
        issues.append(
            f"services.excluded_services[{item!r}]: Ausschluss nicht explizit in der Quelle gestützt"
        )

    if issues:
        ev = contract.services.evidence
        if ev is not None:
            ev.requires_review = True
            if ev.confidence is None or ev.confidence > 0.5:
                ev.confidence = 0.5

    issues.extend(verify_residual_critical_claims(contract, units))
    return issues
