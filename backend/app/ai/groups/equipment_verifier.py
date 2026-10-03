"""Deterministic field-scoped verification for equipment claims.

Equipment is a list, so the scalar semantic verifier cannot safely address it
with a simple ``section.field`` key. This module verifies every extracted item
against source text without deriving or inventing replacement values and detects
conflicting duplicate equipment identities emitted by different chunks.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable

from app.models.contract import Contract


_SERIAL_LABEL = re.compile(r"serien(?:nummer|-?nr\.?|nummer)|serial\s*(?:number|no\.?|nr\.?)", re.I)
_INVENTORY_LABEL = re.compile(r"inventar(?:nummer|-?nr\.?)|inventory\s*(?:number|no\.?|nr\.?)", re.I)
_COVERAGE_LABEL = re.compile(r"abdeckung|leistungszeitraum|vertragsbeginn|vertragsende|gültig|gueltig|coverage", re.I)
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


def _service_item_supported(text: str, item: str, *, excluded: bool) -> bool:
    low = _norm(text)
    needle = _norm(item)
    idx = low.find(needle)
    if not needle or idx < 0:
        return False
    left = 0
    right = len(low)
    for sep in ".;|\n":
        pos = low.rfind(sep, 0, idx)
        if pos >= 0:
            left = max(left, pos + 1)
        pos = low.find(sep, idx + len(needle))
        if pos >= 0:
            right = min(right, pos)
    negated = bool(_NEGATION_RE.search(low[left:right]))
    return negated if excluded else not negated


def _find_support(field: str, value: Any, source_texts: list[str]) -> bool:
    if value in (None, "", []):
        return True

    if field in {"device_name", "manufacturer", "model", "system_name", "equipment_category", "equipment_type", "location", "department", "service_scope", "sla_notes"}:
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

    if field == "included_services":
        values = list(value or [])
        return all(
            any(
                _service_item_supported(text, item, excluded=False)
                for text in source_texts
            )
            for item in values
        )

    if field == "excluded_services":
        values = list(value or [])
        return all(
            any(
                _service_item_supported(text, item, excluded=True)
                for text in source_texts
            )
            for item in values
        )

    # Unknown equipment fields are never silently accepted. If the checked
    # field set is expanded without adding a verifier rule, fail closed.
    return False


def _identity_keys(equipment: Any) -> set[tuple[str, str]]:
    """Return only identities safe enough to correlate two list items.

    Serial/inventory identifiers dominate. Device+model is used only when neither
    item carries a stronger identifier; otherwise two identical product models
    with different serials must remain distinct physical devices.
    """
    keys: set[tuple[str, str]] = set()
    serial = _norm(getattr(equipment, "serial_number", None))
    inventory = _norm(getattr(equipment, "inventory_number", None))
    device = _norm(getattr(equipment, "device_name", None))
    model = _norm(getattr(equipment, "model", None))
    if serial:
        keys.add(("serial", serial))
    if inventory:
        keys.add(("inventory", inventory))
    if not serial and not inventory and device and model:
        keys.add(("device_model", f"{device}|{model}"))
    return keys


def _value_signature(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return tuple(sorted(_norm(item) for item in value))
    return _norm(value)


def _mark_review(equipment: Any) -> None:
    ev = getattr(equipment, "evidence", None)
    if ev is not None:
        ev.requires_review = True
        if ev.confidence is None or ev.confidence > 0.5:
            ev.confidence = 0.5


def _duplicate_conflict_issues(contract: Contract) -> list[str]:
    """Flag two list items that clearly identify the same device but disagree."""
    issues: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    comparable_fields = (
        "manufacturer",
        "device_name",
        "model",
        "serial_number",
        "inventory_number",
        "system_name",
        "location",
        "department",
        "service_scope",
        "coverage_start",
        "coverage_end",
    )
    reported_pairs: set[tuple[int, int]] = set()

    for index, equipment in enumerate(contract.equipment):
        for key in _identity_keys(equipment):
            other_index = seen.get(key)
            if other_index is None:
                seen[key] = index
                continue
            pair = (other_index, index)
            if pair in reported_pairs:
                continue
            other = contract.equipment[other_index]
            conflicts: list[str] = []
            for field in comparable_fields:
                left = getattr(other, field, None)
                right = getattr(equipment, field, None)
                if left in (None, "", []) or right in (None, "", []):
                    continue
                if _value_signature(left) != _value_signature(right):
                    conflicts.append(field)
            if conflicts:
                reported_pairs.add(pair)
                _mark_review(other)
                _mark_review(equipment)
                issues.append(
                    f"Equipment[{other_index}]↔Equipment[{index}]: gleiche Geräteidentität ({key[0]}) "
                    f"mit widersprüchlichen Feldern: {', '.join(conflicts)}"
                )
    return issues


def verify_equipment_claims(contract: Contract, units: Iterable[object]) -> list[str]:
    """Return fail-closed issues for unsupported or contradictory equipment facts."""
    source_texts = _texts(units)
    issues: list[str] = []
    fields = (
        "device_name",
        "manufacturer",
        "model",
        "serial_number",
        "inventory_number",
        "system_name",
        "equipment_category",
        "equipment_type",
        "location",
        "department",
        "service_scope",
        "sla_notes",
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

        if unsupported:
            _mark_review(equipment)
            for field in unsupported:
                issues.append(
                    f"Equipment[{index}].{field}: Wert nicht feldspezifisch in der Quelle gestützt"
                )

    issues.extend(_duplicate_conflict_issues(contract))
    return issues
