"""Deterministic field-scoped verification for equipment claims.

Equipment is a list, so the scalar semantic verifier cannot safely address it
with a simple ``section.field`` key. This module verifies every extracted item
against source text without deriving or inventing replacement values.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable

from app.models.contract import Contract


_SERIAL_LABEL = re.compile(r"serien(?:nummer|-?nr\.?|nummer)|serial\s*(?:number|no\.?|nr\.?)", re.I)
_INVENTORY_LABEL = re.compile(r"inventar(?:nummer|-?nr\.?)|inventory\s*(?:number|no\.?|nr\.?)", re.I)
_COVERAGE_LABEL = re.compile(r"abdeckung|leistungszeitraum|vertragsbeginn|vertragsende|gültig|gueltig|coverage", re.I)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _texts(units: Iterable[object]) -> list[str]:
    return [
        text
        for unit in units
        if (text := str(getattr(unit, "text", "") or "").strip())
    ]


def _contains_exactish(text: str, value: Any) -> bool:
    needle = _norm(value)
    return bool(needle) and needle in _norm(text)


def _flexible_date_supported(text: str, value: Any) -> bool:
    if value is None:
        return True
    raw_date = getattr(value, "date", None)
    condition = getattr(value, "condition", None)
    if raw_date is not None and isinstance(raw_date, date):
        candidates = {
            raw_date.isoformat(),
            raw_date.strftime("%d.%m.%Y"),
            f"{raw_date.day}.{raw_date.month}.{raw_date.year}",
        }
        return any(candidate in text for candidate in candidates)
    if condition:
        return _contains_exactish(text, condition)
    return False


def _find_support(field: str, value: Any, source_texts: list[str]) -> bool:
    if value in (None, "", []):
        return True

    if field in {"device_name", "manufacturer", "model", "system_name", "service_scope"}:
        return any(_contains_exactish(text, value) for text in source_texts)

    if field == "serial_number":
        return any(
            _contains_exactish(text, value) and _SERIAL_LABEL.search(text)
            for text in source_texts
        )

    if field == "inventory_number":
        return any(
            _contains_exactish(text, value) and _INVENTORY_LABEL.search(text)
            for text in source_texts
        )

    if field in {"coverage_start", "coverage_end"}:
        return any(
            _COVERAGE_LABEL.search(text) and _flexible_date_supported(text, value)
            for text in source_texts
        )

    if field in {"included_services", "excluded_services"}:
        values = list(value or [])
        return all(any(_contains_exactish(text, item) for text in source_texts) for item in values)

    return True


def verify_equipment_claims(contract: Contract, units: Iterable[object]) -> list[str]:
    """Return fail-closed issues for unsupported equipment fields.

    The function never changes the extracted fact. If an item has SourceEvidence,
    unsupported item fields mark that evidence as review-required; absence of an
    evidence object is already handled by GroupPipeline and remains an issue.
    """
    source_texts = _texts(units)
    issues: list[str] = []
    fields = (
        "device_name",
        "manufacturer",
        "model",
        "serial_number",
        "inventory_number",
        "system_name",
        "service_scope",
        "included_services",
        "excluded_services",
        "coverage_start",
        "coverage_end",
    )

    for index, equipment in enumerate(contract.equipment):
        unsupported: list[str] = []
        for field in fields:
            value = getattr(equipment, field, None)
            if value in (None, "", []):
                continue
            if not _find_support(field, value, source_texts):
                unsupported.append(field)

        if not unsupported:
            continue

        ev = getattr(equipment, "evidence", None)
        if ev is not None:
            ev.requires_review = True
            if ev.confidence is None or ev.confidence > 0.5:
                ev.confidence = 0.5
        for field in unsupported:
            issues.append(
                f"Equipment[{index}].{field}: Wert nicht feldspezifisch in der Quelle gestützt"
            )
    return issues
