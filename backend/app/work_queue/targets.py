"""Direkt zur Stelle: wo eine Aufgabe in der Vertragsakte erledigt wird.

Gleiche Zuordnung wie `frontend/lib/fix-targets.ts` (`workItemTarget`). Ohne Ort bleibt es die Vertragsakte.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

_REVIEW = {"tab": "documents", "subtab": "review"}
_DEADLINES = {"tab": "deadlines", "abschnitt": "renewal"}
_WORK_ITEM_TARGETS: dict[str, Optional[dict]] = {
    "manual_review": _REVIEW,
    "missing_cost": {"tab": "finance", "abschnitt": "entries"},
    "equipment_coverage_review": {"tab": "relations"},
    "equipment_relationship_ambiguous": {"tab": "relations"},
    "cancellation_deadline": _DEADLINES,
    "contract_expiry": _DEADLINES,
    "automatic_renewal": _DEADLINES,
    "contract_expired": _DEADLINES,
    "sla_issue": None,
}


def work_item_href(contract_id, item_type: str, requires_review: bool = False) -> str:
    if not contract_id:
        return "/fristen?ansicht=aufgaben"
    target = _REVIEW if requires_review else _WORK_ITEM_TARGETS.get(item_type)
    query = urlencode(target) if target else ""
    return f"/contracts/{contract_id}{'?' + query if query else ''}"
