"""Abschnitte je Vertragstyp (Plan VERTRAGSPROFIL_ABSCHNITTE_PLAN_20261011).

Nur Darstellung: welche typspezifischen Abschnitte ein Vertrag zeigt. Fristen, Kosten
und Warnungen bleiben unberührt. Ohne Vertragstyp gelten alle Abschnitte.
"""

from __future__ import annotations

from typing import Any, Optional

SECTION_KEYS: tuple[str, ...] = ("scope", "sla", "maintenance", "equipment")
SECTION_LABELS: dict[str, str] = {
    "scope": "Leistungsumfang",
    "sla": "SLA",
    "maintenance": "Wartung",
    "equipment": "Geräte",
}

_SERVICE = ("scope", "sla", "maintenance", "equipment")
_PERFORMANCE = ("scope", "sla")
_OBJECT = ("equipment",)

DEFAULT_SECTIONS: dict[str, tuple[str, ...]] = {
    "wartung": _SERVICE, "service": _SERVICE,
    "dienstleistung": _PERFORMANCE, "dienstvertrag": _PERFORMANCE, "werkvertrag": _PERFORMANCE,
    "versorgung": _PERFORMANCE, "med_versorgung": _PERFORMANCE, "kooperation": _PERFORMANCE, "lizenz": _PERFORMANCE,
    "miete": _OBJECT, "leasing": _OBJECT, "nutzung": _OBJECT, "leihe": _OBJECT, "kauf": _OBJECT,
    **{code: () for code in (
        "versicherung", "mitgliedschaft", "darlehen", "erbbaurecht", "sponsoring", "drittmittel",
        "avv", "vertraulichkeit", "vertraulich_gf", "zulassung", "sonstige",
    )},
}


def normalize(value: Any) -> Optional[list[str]]:
    """Eingabe aus der API: Liste bekannter Schlüssel (Reihenfolge fest) oder None (= Standard)."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or any(item not in SECTION_KEYS for item in value):
        raise ValueError("Unbekannter Abschnitt.")
    return [key for key in SECTION_KEYS if key in value]


def default_sections(code: Optional[str]) -> list[str]:
    """Standardprofil nach Code; eigene Typen ohne bekannten Code zeigen alles."""
    return list(DEFAULT_SECTIONS.get(code or "", SECTION_KEYS))


def sections_for_type(row) -> list[str]:
    if row is None:
        return list(SECTION_KEYS)
    stored = getattr(row, "sections", None)
    return [key for key in SECTION_KEYS if key in stored] if stored is not None else default_sections(row.code)


def contract_sections(row) -> Optional[dict[str, Any]]:
    """Lesemodell der Vertragsakte; None ohne Vertragstyp (dann alle Abschnitte)."""
    if row is None:
        return None
    active = set(sections_for_type(row))
    return {"type_label": row.label, **{key: key in active for key in SECTION_KEYS}}
