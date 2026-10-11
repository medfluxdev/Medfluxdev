"""Regeln für den Aufbau der Abteilungsstruktur (Entscheidung 2026-10-11).

Klinik nur direkt unter dem Krankenhaus; Abteilung unter einer Klinik oder direkt unter dem
Krankenhaus (z. B. IT, Haustechnik); Station und Funktionsbereich unter einer Klinik oder Abteilung.
Bereich, Einheit und Einheiten ohne Typ haben keine Regel; ein übergeordneter Eintrag ohne Typ wird
nicht beurteilt (nichts wird geraten). Rein: keine DB.
"""

from __future__ import annotations

from typing import Iterable, Optional

TOP = None  # direkt unter dem Krankenhaus

ALLOWED_PARENTS: dict[str, frozenset] = {
    "klinik": frozenset({TOP}),
    "abteilung": frozenset({TOP, "klinik"}),
    "station": frozenset({"klinik", "abteilung"}),
    "funktionsbereich": frozenset({"klinik", "abteilung"}),
}

RULE_TEXT: dict[str, str] = {
    "klinik": "Eine Klinik steht direkt unter dem Krankenhaus.",
    "abteilung": "Eine Abteilung steht unter einer Klinik oder direkt unter dem Krankenhaus.",
    "station": "Eine Station steht unter einer Klinik oder Abteilung.",
    "funktionsbereich": "Ein Funktionsbereich steht unter einer Klinik oder Abteilung.",
}


def placement_issue(unit_type: Optional[str], has_parent: bool, parent_type: Optional[str]) -> Optional[str]:
    """Grund, warum die Einordnung nicht passt, sonst None."""
    allowed = ALLOWED_PARENTS.get(unit_type or "")
    if allowed is None:
        return None
    if not has_parent:
        return None if TOP in allowed else RULE_TEXT[unit_type]
    if parent_type is None:
        return None
    return None if parent_type in allowed else RULE_TEXT[unit_type]


def rules_payload() -> dict:
    """Für die Oberfläche: erlaubte übergeordnete Typen je Typ (`null` = direkt unter dem Krankenhaus)."""
    return {
        unit_type: {"parents": sorted(allowed, key=lambda value: (value is not None, value or "")), "text": RULE_TEXT[unit_type]}
        for unit_type, allowed in ALLOWED_PARENTS.items()
    }


def child_issues(parent_type: Optional[str], children: Iterable[tuple[str, Optional[str]]]) -> list[str]:
    """Namen der Untereinheiten, die mit dem (neuen) Typ des übergeordneten Eintrags nicht mehr passen."""
    return [name for name, child_type in children if placement_issue(child_type, True, parent_type)]
