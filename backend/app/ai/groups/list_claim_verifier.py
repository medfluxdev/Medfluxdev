"""Deterministic verification for list-valued service claims.

List claims need item-by-item evidence. Treating an entire services section as
one proof would allow a single supported line to legitimize unrelated list
entries, so every extracted service item is checked independently.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

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


def _excluded_item_supported(text: str, item: str) -> bool:
    if not _item_present(text, item):
        return False
    low = text.casefold()
    idx = low.find(_norm(item))
    start = max(0, idx - 100)
    end = min(len(text), idx + len(item) + 120)
    return bool(_NEGATION_RE.search(text[start:end]))


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
    return issues
