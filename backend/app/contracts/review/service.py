"""Faktgenaue menschliche Verifikation + Vertragsreview (Customer-Demo-Readiness).

- `fact_review`: append-only, ein materialer Fakt je Aktion
  (BESTÄTIGT / KORRIGIERT / VERWORFEN / WIEDER GEÖFFNET). Der extrahierte
  Wert bleibt IMMER als `original_value` erhalten; `new_effective_value`
  trägt bei Korrektur den neuen wirksamen Wert. Bestätigen ändert den Wert
  NICHT – es ist KEIN manueller Override.
- `contract_review`: ein Status je Vertrag (Nicht geprüft / In Prüfung /
  Geprüft / Änderung nach Prüfung). „Geprüft" nur über explizite menschliche
  Abschluss-Aktion. Nachträgliche materiale Änderung ⇒ „Änderung nach Prüfung".
- Identität: `reviewer_display_name` selbst angegeben; `reviewer_identity_type=
  "manual_unverified"`; `authenticated_actor_id=None` (STEP 16 fehlt).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.review.material import (
    MATERIAL_FACT_KEYS,
    fact_is_critical,
    fact_label,
    material_report,
)
from app.database.models import Contract, ContractReview, FactReview

REVIEW_ACTIONS = frozenset({"confirmed", "corrected", "voided", "reopened"})

REVIEWED_ACTIONS = frozenset({"confirmed", "corrected"})
MATERIAL_CHANGE_ACTIONS = frozenset({"corrected", "voided"})

ACTION_LABELS = {
    "confirmed": "Geprüft und bestätigt",
    "corrected": "Manuell korrigiert",
    "voided": "Manuell verworfen",
    "reopened": "Wieder geöffnet",
}

FACT_STATE_LABELS = {
    "unreviewed": "Nicht geprüft",
    "needs_review": "Zu prüfen",
    "confirmed": "Geprüft und bestätigt",
    "corrected": "Manuell korrigiert",
    "voided": "Manuell verworfen",
}

CONTRACT_REVIEW_STATUS_LABELS = {
    "unreviewed": "Nicht geprüft",
    "in_review": "In manueller Prüfung",
    "reviewed": "Geprüft",
    "changed_after_review": "Änderung nach Prüfung",
    "manual_review_required": "Manuelle Prüfung erforderlich",
}


class ReviewError(Exception):
    detail_de = "Prüf-Aktion konnte nicht gespeichert werden."

    def __init__(self, message: str = ""):
        super().__init__(message)
        if message:
            self.detail_de = message


def _json_safe(value):
    """Macht DB-/Anzeige-Werte JSONB-fähig (Decimal/date → primitiv)."""
    from datetime import date as _date

    from decimal import Decimal as _Decimal

    if isinstance(value, _Decimal):
        return str(value)
    if isinstance(value, _date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _effective_write(*, value) -> dict:
    return {"value": _json_safe(value)}


def _latest_fact_reviews(session, contract_id) -> dict[str, FactReview]:
    rows = session.scalars(
        select(FactReview).where(FactReview.contract_id == contract_id)
    ).all()
    latest: dict[str, FactReview] = {}
    for row in rows:
        latest[row.fact_key] = row
    return latest


def fact_review_history(session, contract_id) -> list[FactReview]:
    return list(
        session.scalars(
            select(FactReview)
            .where(FactReview.contract_id == contract_id)
            .order_by(FactReview.created_at.desc(), FactReview.id.desc())
        ).all()
    )


def get_contract_review(
    session, *, organization_id, contract_id
) -> Optional[ContractReview]:
    contract = session.get(Contract, contract_id)
    if contract is None or contract.organization_id != organization_id:
        raise ReviewError("Vertrag nicht gefunden.")
    return session.scalars(
        select(ContractReview).where(ContractReview.contract_id == contract_id)
    ).first()


def _require_reviewer(reviewer_display_name: Optional[str]) -> str:
    name = (reviewer_display_name or "").strip()
    if not name:
        raise ReviewError("Prüfer-Name fehlt (selbst angegeben, nicht authentifiziert).")
    return name


def record_fact_action(
    session: Session,
    *,
    organization_id,
    contract_id,
    fact_key: str,
    action: str,
    reviewer_display_name: Optional[str],
    note: Optional[str] = None,
    system_value=None,
    corrected_value=None,
    evidence_ref: Optional[str] = None,
) -> FactReview:
    """Append-only Prüf-Aktion zu einem materialen Fakt (org-gebunden).

    `system_value` ist der vom System extrahierte/angezeigte Wert (Original).
    `corrected_value` ist nur bei action='corrected' nötig und wird der neue
    wirksame Wert. Bestätigen (`confirmed`) ändert den Wert NIE.
    """
    reviewer = _require_reviewer(reviewer_display_name)
    if action not in REVIEW_ACTIONS:
        raise ReviewError(f"Unbekannte Prüf-Aktion: {action}")
    if fact_key not in MATERIAL_FACT_KEYS:
        raise ReviewError(f"Unbekannter Prüf-Fakt: {fact_key}")
    if action == "corrected" and corrected_value is None:
        raise ReviewError(
            "Manuelle Korrektur erfordert einen neuen Wert "
            "(`corrected_value`). Bestätigen ändert den Wert nicht."
        )

    contract = session.get(Contract, contract_id)
    if contract is None or contract.organization_id != organization_id:
        raise ReviewError("Vertrag nicht gefunden.")

    latest = _latest_fact_reviews(session, contract_id).get(fact_key)
    if latest is not None and latest.action == "corrected":  # effektiv korrigiert
        previous_effective = latest.new_effective_value
    else:
        previous_effective = _effective_write(value=system_value)

    if action == "corrected":
        new_effective = _effective_write(value=corrected_value)
    else:
        new_effective = previous_effective

    row = FactReview(
        contract_id=contract_id,
        fact_key=fact_key,
        action=action,
        original_value=_effective_write(value=system_value),
        previous_effective_value=previous_effective,
        new_effective_value=new_effective,
        reviewer_display_name=reviewer,
        reviewer_identity_type="manual_unverified",
        authenticated_actor_id=None,
        note=note,
        evidence_ref=evidence_ref,
    )
    session.add(row)
    session.flush()

    if action in MATERIAL_CHANGE_ACTIONS:
        _flag_material_change(session, organization_id, contract_id)

    return row


def _flag_material_change(session, organization_id, contract_id) -> None:
    """Materiale Änderung nach geprüftem Abschluss ⇒ „Änderung nach Prüfung"."""
    review = get_contract_review(
        session, organization_id=organization_id, contract_id=contract_id
    )
    if review is not None and review.status == "reviewed" and review.reviewed_at is not None:
        review.status = "changed_after_review"
        review.change_noted_at = datetime.now(timezone.utc)
        session.flush()


def start_review(
    session,
    *,
    organization_id,
    contract_id,
    reviewer_display_name: Optional[str],
    note: Optional[str] = None,
) -> ContractReview:
    reviewer = _require_reviewer(reviewer_display_name)
    review = get_contract_review(
        session, organization_id=organization_id, contract_id=contract_id
    )
    if review is None:
        review = ContractReview(
            contract_id=contract_id,
            status="in_review",
            reviewer_display_name=reviewer,
            reviewer_identity_type="manual_unverified",
            authenticated_actor_id=None,
        )
        session.add(review)
    else:
        review.status = "in_review"
        review.reviewer_display_name = reviewer
    session.flush()
    return review


def complete_review(
    session,
    *,
    organization_id,
    contract_id,
    reviewer_display_name: Optional[str],
    note: Optional[str] = None,
    acknowledge_unreviewed: bool = False,
    relevant_count: int = 0,
    reviewed_count: int = 0,
    critical_unreviewed_count: int = 0,
) -> ContractReview:
    reviewer = _require_reviewer(reviewer_display_name)
    if critical_unreviewed_count > 0:
        raise ReviewError(
            f"Es gibt noch {critical_unreviewed_count} kritische ungeprüfte Angabe(n). "
            "Kritische Vertragsfakten müssen bestätigt, korrigiert oder verworfen werden; "
            "eine pauschale Quittierung ist nicht zulässig."
        )
    unresolved = max(0, relevant_count - reviewed_count)
    if unresolved > 0 and not acknowledge_unreviewed:
        raise ReviewError(
            f"Es gibt noch {unresolved} ungeprüfte Angabe(n). Zum Abschluss bitte "
            "„Geprüft"": alle prüfen oder die ungeprüften Angaben ausdrücklich "
            "akzeptieren (Notiz erforderlich)."
        )
    if unresolved > 0 and not (note or "").strip():
        raise ReviewError(
            "Für ungeprüfte Angaben ist eine ausdrückliche Notiz erforderlich."
        )

    review = get_contract_review(
        session, organization_id=organization_id, contract_id=contract_id
    )
    if review is None:
        review = ContractReview(
            contract_id=contract_id,
            status="reviewed",
            reviewer_display_name=reviewer,
            reviewer_identity_type="manual_unverified",
            authenticated_actor_id=None,
        )
        session.add(review)
    else:
        review.status = "reviewed"
        review.reviewer_display_name = reviewer
    review.reviewed_at = datetime.now(timezone.utc)
    review.completed_note = note
    session.flush()
    return review


def build_fact_review_states(
    session, *, organization_id, contract_id, data: dict
) -> list[dict]:
    """Je materialen Fakt: Präsenz, Zustand, Original-/effektiver Wert, Prüfer."""
    report = material_report(data)
    latest = _latest_fact_reviews(session, contract_id)

    evidence_by_ref: dict[str, list[dict]] = {}
    for ev in data.get("evidence") or []:
        evidence_by_ref.setdefault(ev.get("field_ref"), []).append(ev)

    # UAT Defect Batch F: einige materiale Fakten tragen ihre Evidenz unter
    # gewachsenen field_ref-Praefixen (z. B. `identity_equipment.evidence.0`
    # fuer `equipment.identity`, `sla.*`/`scope.*` fuer `services.coverage`).
    _FACT_EVIDENCE_PREFIXES = {
        "equipment.identity": ("identity_equipment.evidence",),
        "equipment.serial": ("identity_equipment.evidence",),
        "services.coverage": ("sla.", "scope."),
    }

    states: list[dict] = []
    for fact_key, info in report.items():
        row = latest.get(fact_key)
        state = row.action if row is not None else "unreviewed"
        if row is not None and row.action == "reopened":
            state = "unreviewed"

        exact = evidence_by_ref.get(fact_key, [])
        prefixes = _FACT_EVIDENCE_PREFIXES.get(fact_key, ())
        prefixed = [
            ev
            for ref, matches in evidence_by_ref.items()
            for ev in matches
            if any(ref.startswith(pre) for pre in prefixes)
        ] if prefixes else []
        evidence_list = exact + prefixed
        # UAT Re-Test (Defect 1): wiederhergestellte, wörtlich belegte Quellen
        # (evidence_id "recovered:...") vor dekorativen Sammel-/Extraktions-
        # Refs – so zeigt der "Seite N"-Beleg des Reviews die kanonische Seite.
        evidence_list.sort(
            key=lambda ev: (
                0 if str(ev.get("evidence_id") or "").startswith("recovered:") else 1
            )
        )
        any_requires_review = any(
            ev.get("requires_review") for ev in evidence_list
        )
        # UAT Defect Batch E/F: ein VORLIEGENDER, noch ungeprüfter Fakt ohne
        # evidence-getragenen Beleg (oder mit zu prüfender Evidenz) bleibt
        # „Zu prüfen" – er wird NICHT stillschweigend als belegt gezählt.
        # Nicht vorliegende Fakten gelten nicht als „zu prüfen" (kein Inhalt).
        if (
            state in ("unreviewed",)
            and bool(info.get("present"))
            and (not evidence_list or any_requires_review)
        ):
            state = "needs_review"

        original_value = row.original_value if row is not None else _effective_write(value=info.get("value"))

        # Effektiver Wert: bei letzter Korrektur der korrigierte Wert, sonst Original.
        effective_value = original_value
        if row is not None and row.action == "corrected":
            effective_value = row.new_effective_value
        elif row is not None:
            effective_value = row.new_effective_value or original_value

        reviewed_at = row.created_at.isoformat() if row is not None and row.created_at else None
        states.append(
            {
                "fact_key": fact_key,
                "label_de": fact_label(fact_key),
                "present": bool(info.get("present")),
                "state": state,
                "state_label_de": FACT_STATE_LABELS.get(state, state),
                "original_value": info.get("value") if row is None else _unwrap(row.original_value),
                "effective_value": _unwrap(effective_value),
                "reviewer_display_name": row.reviewer_display_name if row is not None else None,
                "reviewer_identity_type": row.reviewer_identity_type if row is not None else None,
                "reviewed_at": reviewed_at,
                "evidence_ref": row.evidence_ref if row is not None else None,
                "has_history": fact_key in latest,
                # UAT Defect Batch F: Fakten-getragene Evidenz sichtbar machen.
                "evidence_count": len(evidence_list),
                "linked_evidence": [
                    {
                        "evidence_id": ev.get("evidence_id"),
                        "page": ev.get("page"),
                        "snippet": ev.get("snippet"),
                        "requires_review": bool(ev.get("requires_review")),
                        "supports_exact_navigation": bool(
                            ev.get("supports_exact_navigation")
                        ),
                    }
                    for ev in evidence_list
                ],
                "linked_evidence_refs": [ev.get("evidence_id") for ev in evidence_list],
                "needs_evidence": bool(info.get("present"))
                and state in ("unreviewed", "needs_review")
                and not evidence_list,
                "is_critical": bool(info.get("critical")),
            }
        )
    return states


def _unwrap(payload) -> object:
    if isinstance(payload, dict) and "value" in payload:
        return payload.get("value")
    return payload


def build_review_summary(states: list[dict]) -> dict:
    relevant = [s for s in states if s["present"] and s["state"] != "voided"]
    reviewed = [s for s in relevant if s["state"] in REVIEWED_ACTIONS]
    critical = [s for s in relevant if s.get("is_critical")]
    critical_reviewed = [s for s in critical if s["state"] in REVIEWED_ACTIONS]
    return {
        "relevant_count": len(relevant),
        "reviewed_count": len(reviewed),
        "unresolved_count": len(relevant) - len(reviewed),
        # UAT Defect Batch E: kritische (material-relevante) Angaben prominent.
        "critical_count": len(critical),
        "critical_reviewed_count": len(critical_reviewed),
        "critical_unreviewed_count": len(critical) - len(critical_reviewed),
    }


def build_contract_review_dto(session, *, organization_id, contract_id) -> dict:
    review = get_contract_review(
        session, organization_id=organization_id, contract_id=contract_id
    )
    status = "unreviewed" if review is None else review.status
    return {
        "status": status,
        "status_label_de": CONTRACT_REVIEW_STATUS_LABELS.get(status, status),
        "reviewer_display_name": review.reviewer_display_name if review else None,
        "reviewer_identity_type": review.reviewer_identity_type if review else "manual_unverified",
        "authenticated_actor_id": review.authenticated_actor_id if review else None,
        "reviewed_at": review.reviewed_at.isoformat() if review and review.reviewed_at else None,
        "changed_noted_at": (
            review.change_noted_at.isoformat() if review and review.change_noted_at else None
        ),
        "completion_note": review.completed_note if review else None,
    }


def build_fact_review_history(session, *, contract_id) -> list[dict]:
    rows = fact_review_history(session, contract_id)
    out = []
    for r in rows:
        out.append(
            {
                "id": str(r.id),
                "fact_key": r.fact_key,
                "fact_label_de": fact_label(r.fact_key),
                "is_critical": fact_is_critical(r.fact_key),
                "action": r.action,
                "action_label_de": ACTION_LABELS.get(r.action, r.action),
                "original_value": _unwrap(r.original_value),
                "previous_effective_value": _unwrap(r.previous_effective_value),
                "new_effective_value": _unwrap(r.new_effective_value),
                "reviewer_display_name": r.reviewer_display_name,
                "reviewer_identity_type": r.reviewer_identity_type,
                "authenticated_actor_id": (
                    str(r.authenticated_actor_id) if r.authenticated_actor_id else None
                ),
                "note": r.note,
                "evidence_ref": r.evidence_ref,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return out


def review_detail_response(session, *, organization_id, contract_id, data: dict) -> dict:
    states = build_fact_review_states(
        session, organization_id=organization_id, contract_id=contract_id, data=data
    )
    summary = build_review_summary(states)
    cr_dto = build_contract_review_dto(
        session, organization_id=organization_id, contract_id=contract_id
    )
    data["fact_review_states"] = states
    data["fact_reviews"] = build_fact_review_history(session, contract_id=contract_id)
    data["contract_review"] = {**cr_dto, **summary}
    return data