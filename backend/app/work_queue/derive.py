"""PR-4 Arbeitsliste – deterministische Ableitung (reine Funktion, keine DB).

Konsistent zur STEP-11-Warn-Engine: Die KI/Berechnung liefert FAKTEN;
die Materialisierung einer Arbeitsliste (was ist zu TUN) wird hier in Code
aus den autoritativen Quellen abgeleitet:
  1. aktive `ContractWarning` (STEP-11 deterministische Bewertung), und
  2. `contract_equipment`-Review-Flags (PR-4 Qualität/Belegbarkeit).

Die Funktion ist PURE (kein DB, kein date.today()): `as_of_date` wird
eingegeben. So bleibt die Ableitung reproduzierbar/testbar.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Optional

from app.models.enums import WorkItemStatus, WorkItemType


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Warn-Typ -> PR-4-Arbeiten (maschinenlesbare, deterministische Zuordnung).
_WARNING_TO_WORKITEM = {
    "contract_end_approaching": WorkItemType.CONTRACT_EXPIRY,
    "contract_expired": WorkItemType.CONTRACT_EXPIRED,
    "cancellation_deadline_approaching": WorkItemType.CANCELLATION_DEADLINE,
    "cancellation_deadline_today": WorkItemType.CANCELLATION_DEADLINE,
    "cancellation_deadline_passed": WorkItemType.CANCELLATION_DEADLINE,
    "automatic_renewal_attention": WorkItemType.AUTOMATIC_RENEWAL,
    "unclear_contract_data": WorkItemType.MANUAL_REVIEW,
    "calculation_conflict": WorkItemType.MANUAL_REVIEW,
    "manual_review_required": WorkItemType.MANUAL_REVIEW,
    "missing_cost_data": WorkItemType.MISSING_COST,
    "cost_conflict": WorkItemType.MANUAL_REVIEW,
    "currency_conflict": WorkItemType.MANUAL_REVIEW,
    "sla_issue": WorkItemType.SLA_ISSUE,
}

# review-Flag (relationship_quality) bei Geräten -> PR-4-Arbeit.
_REVIEW_TO_WORKITEM = {
    "partial": WorkItemType.EQUIPMENT_COVERAGE_REVIEW,
    "generic": WorkItemType.EQUIPMENT_COVERAGE_REVIEW,
    "ambiguous": WorkItemType.EQUIPMENT_RELATIONSHIP_AMBIGUOUS,
}

_ACTIVE_STATES = {"open", "acknowledged"}

# Deutsche Anzeige für Warn-/ORM-Fälle ohne eingebetteten Text.
_WARNING_TITLES = {
    "contract_end_approaching": "Vertragsende nähert sich",
    "contract_expired": "Vertrag ausgelaufen",
    "cancellation_deadline_approaching": "Kündigungsfrist nähert sich",
    "cancellation_deadline_today": "Kündigungsfrist heute",
    "cancellation_deadline_passed": "Kündigungsfrist verstrichen",
    "automatic_renewal_attention": "Automatische Verlängerung beachten",
    "unclear_contract_data": "Vertragsdaten unklar",
    "calculation_conflict": "Berechnungskonflikt",
    "manual_review_required": "Manuelle Prüfung erforderlich",
    "missing_cost_data": "Fehlende verlässliche Kostenangabe",
    "cost_conflict": "Widersprüchliche Kostenangaben",
    "currency_conflict": "Mehrere Währungen",
    "sla_issue": "SLA-Verletzung beachten",
}


def _get(obj, key, default=None):
    """Attribute-/Dict-zugreifender Helfer (funktioniert für ORM + dict)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _prepend_domain(fp: str, prefix: str) -> str:
    return _sha(f"{prefix}:{fp}")


def derive_from_warning(warning) -> Optional[dict]:
    """Eine Warnung -> ein Arbeitselement (oder None, wenn nicht handlungsrelevant).

    Akzeptiert ORM-Objekte (fehlende Anzeige-Felder -> deutsche Titel aus
    `_WARNING_TITLES`) und dict-artige Eingaben gleichermaßen.
    """
    wtype = _get(warning, "warning_type")
    item_type = _WARNING_TO_WORKITEM.get(wtype)
    if item_type is None:
        return None
    if not (
        _get(warning, "requires_action", False)
        or _get(warning, "requires_review", False)
    ):
        return None
    calc_refs = _get(warning, "calculation_field_refs", None) or []
    source_refs = _get(warning, "source_field_refs", None) or []
    title = _get(warning, "title_de", None) or _WARNING_TITLES.get(wtype, wtype)
    return {
        "source_warning_fingerprint": _get(warning, "logical_fingerprint"),
        "item_type": item_type,
        "severity": _get(warning, "severity", "low"),
        "title_de": title,
        "why_de": _get(warning, "message_de", None),
        "action_hint_de": _get(warning, "action_hint_de", None),
        "target_date": _get(warning, "target_date", None),
        "days_remaining": _get(warning, "days_remaining", None),
        "requires_review": bool(_get(warning, "requires_review", False)),
        "calc_field_refs": list(calc_refs),
        "source_field_refs": list(source_refs),
        "source_warning_id": _get(warning, "id", None),
    }


def derive_from_equipment(row) -> Optional[dict]:
    """Eine `contract_equipment`-Review-Zeile -> ein Arbeitselement (oder None)."""
    rel = _get(row, "relationship_quality")
    item_type = _REVIEW_TO_WORKITEM.get(rel)
    if item_type is None:
        return None
    if not _get(row, "requires_review", False):
        return None
    device = (
        _get(row, "device_name") or _get(row, "system_name")
        or _get(row, "model") or _get(row, "manufacturer")
        or (_get(row, "equipment_category") or "Gerät")
    )
    if item_type == WorkItemType.EQUIPMENT_COVERAGE_REVIEW:
        title = f"Geräte-Zuordnung prüfen: {device}"
        why = (
            f"Gerät '{device}': Identität oder Quellenbeleg für die "
            "Vertrags-Zuordnung unvollständig; manuelle Prüfung erforderlich."
        )
    else:
        title = f"Geräte-Zuordnung mehrdeutig: {device}"
        why = (
            f"Gerät '{device}' ist nicht eindeutig identifizierbar – die "
            "Vertrags-Zuordnung ist unklar."
        )
    fp = _get(row, "logical_fingerprint")
    return {
        "source_warning_fingerprint": None,
        "item_type": item_type,
        "severity": "low",
        "title_de": title,
        "why_de": why,
        "action_hint_de": "Geräte-Identität prüfen und Zuordnung bestätigen oder überarbeiten.",
        "target_date": None,
        "days_remaining": None,
        "requires_review": True,
        "calc_field_refs": [],
        "source_field_refs": [_get(row, "field_ref")] if _get(row, "field_ref") else [],
        "source_warning_id": None,
        "contract_equipment_id": _get(row, "id"),
        "equipment_id": _get(row, "equipment_id"),
        "_fp_source": fp,
        "_occurrence_fp": _get(row, "occurrence_fingerprint"),
        "_has_unique_id": bool(
            _get(row, "serial_number") or _get(row, "inventory_number")
        ),
        "_coverage_scope": "|".join(str(_get(row, key) or "").strip().casefold()
            for key in ("service_scope", "coverage_start", "coverage_end")),
    }


def compute_fingerprint(item: dict) -> str:
    """Stabiler logischer Fingerprint einer Arbeit (Idempotenz-Lebenszyklus)."""
    if item.get("source_warning_fingerprint"):
        return _prepend_domain("w", item["source_warning_fingerprint"])
    src = item.get("_fp_source")
    if src:
        # Preserve historical semantic lineage for a known single scope;
        # independent scopes and anonymous sourced units need separate tasks.
        scope = item.get("_coverage_scope") or ""
        if item.get("_has_unique_id"):
            return _prepend_domain("eq", src + ("|scope:" + scope if scope.strip("|") else ""))
        occurrence = item.get("_occurrence_fp")
        return _prepend_domain("eq-occ", occurrence or src)
    # Fallback: deterministisch aus Typ + refs + Ziel.
    payload = "|".join([
        str(item["item_type"].value if hasattr(item["item_type"], "value") else item["item_type"]),
        str(item.get("contract_equipment_id") or ""),
        str(item.get("target_date") or ""),
    ])
    return _prepend_domain("m", payload)


def derive_work_items(
    *,
    contract_id: str,
    warnings,
    equipment_rows,
    as_of_date: date,
    policy_version: str,
) -> list[dict]:
    """Leitet die autoritative Arbeitsliste eines Vertrags in Code ab.

    `warnings`/`equipment_rows` sind ORM-Objekte (oder dict-artige) aus den
    autoritativen Quellen. Rückgabe: Liste von zu persistierenden Merkmalen.
    """
    out: list[dict] = []
    for w in warnings:
        item = derive_from_warning(w)
        if item is not None:
            item["contract_id"] = contract_id
            item["as_of_date"] = as_of_date
            item["policy_version"] = policy_version
            item["logical_fingerprint"] = compute_fingerprint(item)
            out.append(item)
    for row in equipment_rows:
        item = derive_from_equipment(row)
        if item is not None:
            item["contract_id"] = contract_id
            item["as_of_date"] = as_of_date
            item["policy_version"] = policy_version
            item["logical_fingerprint"] = compute_fingerprint(item)
            out.append(item)
    return out
