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

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.review.material import (
    EVIDENCE_FACT_PREFIX,
    MATERIAL_FACT_KEYS,
    evidence_base,
    SCOPE_FACTS,
    fact_is_critical,
    fact_label,
    material_report,
)
from app.database.models import Contract, ContractReview, FactReview
from app.database.models.organization import Organization

REVIEW_ACTIONS = frozenset({"confirmed", "corrected", "voided", "reopened"})

REVIEWED_ACTIONS = frozenset({"confirmed", "corrected"})
# Pruefmodus "auto_noncritical": nicht-kritische, vorliegende Angaben mit eigenem,
# nicht zu pruefendem Beleg gelten als erledigt. Abgeleiteter Lesezustand – es
# entsteht kein Pruef-Eintrag, kritische Angaben bleiben immer manuell.
AUTO_ACCEPTED_STATE = "auto_accepted"
RESOLVED_STATES = REVIEWED_ACTIONS | {AUTO_ACCEPTED_STATE}
MATERIAL_CHANGE_ACTIONS = frozenset({"corrected", "voided", "reopened"})
AUTO_COMPLETE_NOTE = "Alle Angaben geprüft."

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
    AUTO_ACCEPTED_STATE: "Automatisch übernommen",
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


class ReviewConflict(ReviewError):
    """Die Angabe wurde seit dem Laden von jemand anderem geprüft (409)."""


# Gleiche Aktion derselben Person auf denselben Fakt innerhalb dieses Fensters gilt als
# doppelt gesendet (Doppelklick, erneuter Request) und erzeugt keinen zweiten Eintrag.
DUPLICATE_WINDOW_SECONDS = 30
_NOT_GIVEN = object()


def _valid_evidence_key(fact_key: str) -> bool:
    base = fact_key[len(EVIDENCE_FACT_PREFIX):] if fact_key.startswith(EVIDENCE_FACT_PREFIX) else ""
    return bool(base) and len(fact_key) <= 120 and all(part.replace("_", "").isalnum() for part in base.split("."))


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
    expected_reviewed_at=_NOT_GIVEN,
) -> FactReview:
    """Append-only Prüf-Aktion zu einem materialen Fakt (org-gebunden).

    `system_value` ist der vom System extrahierte/angezeigte Wert (Original).
    `corrected_value` ist nur bei action='corrected' nötig und wird der neue
    wirksame Wert. Bestätigen (`confirmed`) ändert den Wert NIE.
    """
    reviewer = _require_reviewer(reviewer_display_name)
    if action not in REVIEW_ACTIONS:
        raise ReviewError(f"Unbekannte Prüf-Aktion: {action}")
    if fact_key not in MATERIAL_FACT_KEYS and not _valid_evidence_key(fact_key):
        raise ReviewError(f"Unbekannter Prüf-Fakt: {fact_key}")
    if action == "corrected" and corrected_value is None:
        raise ReviewError(
            "Manuelle Korrektur erfordert einen neuen Wert "
            "(`corrected_value`). Bestätigen ändert den Wert nicht."
        )

    # Zeilensperre: gleichzeitige Prüfungen desselben Vertrags laufen nacheinander.
    contract = session.get(Contract, contract_id, with_for_update=True)
    if contract is None or contract.organization_id != organization_id:
        raise ReviewError("Vertrag nicht gefunden.")

    latest = _latest_fact_reviews(session, contract_id).get(fact_key)
    current_stamp = latest.created_at.isoformat() if latest is not None and latest.created_at else None
    if expected_reviewed_at is not _NOT_GIVEN and (expected_reviewed_at or None) != current_stamp:
        raise ReviewConflict(
            f"Die Angabe wurde inzwischen von {latest.reviewer_display_name or 'einer anderen Person'} geprüft. "
            "Bitte neu laden und erneut entscheiden."
        )
    if latest is not None and latest.action == "corrected":  # effektiv korrigiert
        previous_effective = latest.new_effective_value
    else:
        previous_effective = _effective_write(value=system_value)

    if action == "corrected":
        new_effective = _effective_write(value=corrected_value)
    else:
        new_effective = previous_effective

    if (
        latest is not None
        and latest.action == action
        and latest.reviewer_display_name == reviewer
        and latest.new_effective_value == new_effective
        and (latest.note or None) == (note or None)
        and latest.created_at is not None
        and (datetime.now(timezone.utc) - latest.created_at).total_seconds() < DUPLICATE_WINDOW_SECONDS
    ):
        return latest

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


REEXTRACTION_REOPEN_NOTE = "Neuer Wert aus der erneuten Erfassung – bitte erneut prüfen."


def reopen_after_reextraction(
    session: Session, *, organization_id, contract_id, values: dict[str, object], reviewer_display_name: Optional[str],
) -> list[str]:
    """Bereits gepruefte Angaben, deren Wert eine erneute Erfassung geaendert hat, wieder oeffnen.

    Der neue Wert wird Original- und wirksamer Wert; eine fruehere Bestaetigung oder Korrektur
    gilt nicht fuer ihn. Angaben ohne Pruef-Historie sind ohnehin offen. Gibt die geoeffneten
    Angaben zurueck.
    """
    reviewer = (reviewer_display_name or "").strip() or "Erneute Erfassung"
    latest = _latest_fact_reviews(session, contract_id)
    reopened: list[str] = []
    for fact_key, value in values.items():
        row = latest.get(fact_key)
        if fact_key not in MATERIAL_FACT_KEYS or row is None or row.action == "reopened":
            continue
        session.add(FactReview(
            contract_id=contract_id,
            fact_key=fact_key,
            action="reopened",
            original_value=_effective_write(value=value),
            previous_effective_value=row.new_effective_value,
            new_effective_value=_effective_write(value=value),
            reviewer_display_name=reviewer,
            reviewer_identity_type="manual_unverified",
            authenticated_actor_id=None,
            note=REEXTRACTION_REOPEN_NOTE,
        ))
        reopened.append(fact_key)
    if reopened:
        session.flush()
        _flag_material_change(session, organization_id, contract_id)
    return reopened


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


# UAT Defect Batch F (generisch): materiale Fakten tragen ihre Evidenz unter
# unterschiedlichen, deterministischen field_ref-Formen:
#   - exakt: `identity.contract_number` (recovered:...-Belege)
#   - Harness-Zeilen: `identity.contract_number.evidence.0`
#   - Aliase (Harness-Feldname != Material-Key): `termination.automatic_renewal`
#     fuer `termination.auto_renewal`, `costs.annual_cost` fuer `costs.annual`
#   - gewachsene Praefixe: `identity_equipment.evidence.0` fuer equipment.*,
#     `services.<key>` fuer `scope.<key>` (Leistungsumfang)
# Gruppen-Zeilen (`dates.evidence`, `costs.evidence`, ...) dienen als
# Rueckfall, damit ein vorliegender Fakt nie grundlos „Kein Quellen-Beleg"
# zeigt – sie zaehlen aber nicht, wenn ein feldspezifischer Beleg existiert.
_FACT_EVIDENCE_ALIASES: dict[str, tuple[str, ...]] = {
    "termination.auto_renewal": ("termination.automatic_renewal",),
    "costs.annual": ("costs.annual_cost",),
    "costs.monthly_recurring": (
        "costs.monthly_cost",
        "costs.quarterly_cost",
        "costs.semi_annual_cost",
    ),
    "costs.monthly_net": ("costs.tax_table.net",),
    "costs.vat_rate": ("costs.tax_table.vat",),
    "costs.vat_amount": ("costs.tax_table.vat",),
    "costs.monthly_gross": ("costs.tax_table.gross",),
    # Leistungsumfang je Leistung: Belege aus `services.<key>` (Harness) oder `scope.<key>`.
    **{f"scope.{key}": (f"services.{key}",) for key, _ in SCOPE_FACTS},
    "scope.other_included": ("services.included_services", "scope.included_services"),
    "scope.other_excluded": ("services.excluded_services", "scope.excluded_services"),
}

_FACT_EVIDENCE_PREFIXES: dict[str, tuple[str, ...]] = {
    "equipment.identity": (
        "identity_equipment.evidence",
        "equipment.evidence",
        "identity.system_identity",
    ),
    "equipment.serial": (
        "identity_equipment.evidence",
        "equipment.evidence",
        "identity.system_identity",
    ),
}


def _link_fact_evidence(fact_key: str, evidence_by_ref: dict[str, list[dict]]):
    """Ordnet einem materialen Fakt deterministisch seine Belege zu.

    Liefert (specific, group_fallback). specific enthaelt alle wörtlich
    passenden Belege (exakt, Harness-Zeile, Alias, Praefix); group_fallback
    enthaelt die Gruppen-Zeile (z. B. `costs.evidence`) nur, wenn es keinen
    spezifischen Beleg gibt.
    """
    specific: list[dict] = []
    group_fallback: list[dict] = []
    group = fact_key.split(".", 1)[0]
    aliases = _FACT_EVIDENCE_ALIASES.get(fact_key, ())
    prefixes = _FACT_EVIDENCE_PREFIXES.get(fact_key, ())
    for ref, matches in evidence_by_ref.items():
        if not ref:
            continue
        if (
            ref == fact_key
            or ref.startswith(fact_key + ".evidence")
            or any(
                ref == alias or ref.startswith(alias + ".evidence")
                for alias in aliases
            )
            or any(ref.startswith(pre) for pre in prefixes)
        ):
            specific.extend(matches)
        elif ref == f"{group}.evidence":
            group_fallback.extend(matches)
    return specific, ([] if specific else group_fallback)


def review_mode(session, organization_id) -> str:
    organization = session.get(Organization, organization_id) if organization_id is not None else None
    return getattr(organization, "review_mode", None) or "manual"


def auto_accept_allowed(session, organization_id, contract_id) -> bool:
    """Organisation erlaubt die automatische Übernahme UND der Vertrag wurde nicht ausdrücklich
    mit „KI-gestützt mit manueller Prüfung“ importiert (NULL = vor dem Import-Assistenten)."""
    if review_mode(session, organization_id) != "auto_noncritical":
        return False
    contract = session.get(Contract, contract_id) if contract_id is not None else None
    return getattr(contract, "intake_mode", None) in (None, "ai_direct")


def build_fact_review_states(
    session, *, organization_id, contract_id, data: dict
) -> list[dict]:
    """Je materialen Fakt: Präsenz, Zustand, Original-/effektiver Wert, Prüfer."""
    report = material_report(data)
    latest = _latest_fact_reviews(session, contract_id)
    auto_mode = auto_accept_allowed(session, organization_id, contract_id)

    evidence_by_ref: dict[str, list[dict]] = {}
    for ev in data.get("evidence") or []:
        evidence_by_ref.setdefault(ev.get("field_ref"), []).append(ev)

    # Jeder Nachweis gehoert zu genau einer Pruef-Angabe: Belege, die keiner festen Angabe
    # zugeordnet sind, werden je Quellfeld eine eigene Angabe („evidence.<feld>“).
    used: set[int] = set()
    for fact_key, info in report.items():
        if info.get("present"):
            specific, group_fallback = _link_fact_evidence(fact_key, evidence_by_ref)
            used.update(id(ev) for ev in (specific or group_fallback))
    evidence_groups: dict[str, list[dict]] = {}
    for ev in data.get("evidence") or []:
        if id(ev) not in used and ev.get("field_ref"):
            evidence_groups.setdefault(EVIDENCE_FACT_PREFIX + evidence_base(ev["field_ref"]), []).append(ev)
    items = list(report.items()) + [
        (key, {"present": True, "value": _evidence_value(evs), "critical": False})
        for key, evs in evidence_groups.items()
    ]

    states: list[dict] = []
    for fact_key, info in items:
        row = latest.get(fact_key)
        # Von Hand eingetragener Wert (z. B. im Dokument nicht gefunden) zählt wie ein vorliegender.
        if row is not None and row.action == "corrected" and not info.get("present"):
            info = {**info, "present": True}
        state = row.action if row is not None else "unreviewed"
        if row is not None and row.action == "reopened":
            state = "unreviewed"

        if fact_key in evidence_groups:
            specific, group_fallback = list(evidence_groups[fact_key]), []
        else:
            specific, group_fallback = _link_fact_evidence(fact_key, evidence_by_ref)
        evidence_list = specific or group_fallback
        ai_confidence = max(
            (float(ev["confidence"]) for ev in evidence_list if ev.get("confidence") is not None),
            default=None,
        )
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
        # Nur ohne menschliche Pruef-Historie: ein wieder geoeffneter Fakt bleibt beim Menschen.
        if (
            auto_mode
            and row is None
            and state == "unreviewed"
            and bool(info.get("present"))
            and not info.get("critical")
            and specific
            and not any_requires_review
        ):
            state = AUTO_ACCEPTED_STATE

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
                # Warum eine Angabe wieder offen ist (z. B. neuer Wert aus erneuter Erfassung).
                "reopen_note": row.note if row is not None and row.action == "reopened" else None,
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
                # Sicherheit der KI zu ihrem Vorschlag (bester Beleg, 0..1); None = keine Angabe.
                "ai_confidence": ai_confidence,
                "is_evidence_item": fact_key in evidence_groups,
                "found_by_rule": ai_confidence is None
                and bool(evidence_list)
                and all(ev.get("extraction_method") == "programmatic" for ev in evidence_list),
            }
        )
    return states


def _evidence_value(evidence: list[dict]) -> Optional[str]:
    """Wert einer Nachweis-Angabe: das Zitat des Belegs (wiederhergestellte Quellen zuerst)."""
    ordered = sorted(evidence, key=lambda ev: 0 if str(ev.get("evidence_id") or "").startswith("recovered:") else 1)
    for ev in ordered:
        text = " ".join(str(ev.get("snippet") or "").split())
        if text:
            return text if len(text) <= 240 else text[:239] + "…"
    return None


def _unwrap(payload) -> object:
    if isinstance(payload, dict) and "value" in payload:
        return payload.get("value")
    return payload


def build_review_summary(states: list[dict]) -> dict:
    relevant = [s for s in states if s["present"] and s["state"] != "voided"]
    reviewed = [s for s in relevant if s["state"] in RESOLVED_STATES]
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
        "authenticated_actor_id": (
            str(review.authenticated_actor_id) if review and review.authenticated_actor_id else None
        ),
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


def complete_if_all_reviewed(
    session, *, organization_id, contract_id, data: dict, reviewer_display_name: Optional[str]
) -> bool:
    """Prüfung des Vertrags abschließen, sobald eine Person die letzte offene Angabe geprüft hat.

    Faktprüfung, Vertragsliste („Zu prüfen“) und Hinweise zählen damit dasselbe. Kritische Angaben
    zählen nur mit menschlicher Prüfung; ohne relevante Angaben bleibt der Status unverändert.
    """
    summary = build_review_summary(
        build_fact_review_states(session, organization_id=organization_id, contract_id=contract_id, data=data)
    )
    if not summary["relevant_count"] or summary["unresolved_count"] or summary["critical_unreviewed_count"]:
        return False
    review = get_contract_review(session, organization_id=organization_id, contract_id=contract_id)
    if review is not None and review.status == "reviewed":
        return False
    complete_review(
        session,
        organization_id=organization_id,
        contract_id=contract_id,
        reviewer_display_name=reviewer_display_name,
        note=AUTO_COMPLETE_NOTE,
        relevant_count=summary["relevant_count"],
        reviewed_count=summary["reviewed_count"],
    )
    return True


REGISTER_CONFIRM_NOTE = "In den Vertragsdaten bestätigt."


def confirm_facts_from_register(
    session, *, organization_id, contract_id, register_keys, reviewer_display_name: Optional[str]
) -> list[str]:
    """In den Vertragsdaten bestätigte KI-Werte gelten auch in der Faktprüfung als bestätigt.

    Gegenstück zu `apply_review_to_register`; nur offene, vorliegende Angaben. Danach wird die
    Prüfung abgeschlossen, falls nichts mehr offen ist. Gibt die bestätigten Angaben zurück.
    """
    from app.contracts.detail.service import build_contract_detail
    from app.reextract.facts import REVIEW_TO_REGISTER

    if not (reviewer_display_name or "").strip():
        return []
    bases = {key.removesuffix("_value").removesuffix("_unit") for key in register_keys}
    facts = [fact for fact, base in REVIEW_TO_REGISTER.items() if base in bases]
    if not facts:
        return []
    data = build_contract_detail(session, organization_id=organization_id, contract_id=contract_id)
    if data is None:
        return []
    states = {
        state["fact_key"]: state
        for state in build_fact_review_states(session, organization_id=organization_id, contract_id=contract_id, data=data)
    }
    confirmed: list[str] = []
    for fact in facts:
        state = states.get(fact)
        if state is None or not state["present"] or state["state"] not in ("unreviewed", "needs_review"):
            continue
        record_fact_action(
            session,
            organization_id=organization_id,
            contract_id=contract_id,
            fact_key=fact,
            action="confirmed",
            reviewer_display_name=reviewer_display_name,
            note=REGISTER_CONFIRM_NOTE,
            system_value=state["original_value"],
        )
        confirmed.append(fact)
    if confirmed:
        sync_review_links(
            session, organization_id=organization_id, contract_id=contract_id, data=data,
            reviewer_display_name=reviewer_display_name,
        )
    return confirmed


# Ziel einer Warnung -> Pruef-Angabe, falls die Quellfelder keine nennen.
_WARNING_TARGET_FACTS = {
    "contract_end": ("dates.end_date",),
    "cancellation_deadline": ("dates.latest_cancellation",),
    "renewal": ("termination.auto_renewal",),
}


def _warning_facts(warning: dict) -> set[str]:
    aliases = {alias: fact for fact, names in _FACT_EVIDENCE_ALIASES.items() for alias in names}
    facts = set()
    for ref in warning.get("source_refs") or []:
        base = str(ref).split(".evidence", 1)[0]
        fact = base if base in MATERIAL_FACT_KEYS else aliases.get(base)
        if fact:
            facts.add(fact)
    if not facts:
        facts.update(_WARNING_TARGET_FACTS.get(str(warning.get("target_kind") or ""), ()))
    return facts & MATERIAL_FACT_KEYS


_UNIT_DE = {"years": "Jahre", "year": "Jahr", "months": "Monate", "month": "Monat", "weeks": "Wochen", "days": "Tage"}
_INPUT_LABELS_DE = {
    "end_date": "Vertragsende laut Dokument",
    "derived_end_date": "Aus Beginn + Laufzeit",
    "start_date": "Vertragsbeginn",
    "duration": "Laufzeit",
    "cancellation_period": "Kündigungsfrist",
    "notice_period": "Kündigungsfrist",
}
CONFLICT_RESOLVED_NOTE = "Widerspruch geklärt"


def _date_de(value) -> Optional[str]:
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return None


def _duration_de(value) -> Optional[str]:
    parts = str(value or "").split()
    if len(parts) != 2 or parts[0] in ("?", "-"):
        return None
    number = parts[0][:-2] if parts[0].endswith(".0") else parts[0]
    return f"{number} {_UNIT_DE.get(parts[1], parts[1])}"


def build_conflict(warning: dict, data: dict, states_by_key: dict[str, dict]) -> Optional[dict]:
    """Widerspruch verständlich machen: was weicht ab, welche Werte stehen zur Wahl, woher stammen sie.

    Nur aus der gespeicherten Berechnung (keine erfundenen Werte). Das Vertragsende hat zwei Optionen
    zur Entscheidung; andere Widersprüche zeigen Erklärung und Eingangswerte.
    """
    if warning.get("warning_type") != "calculation_conflict":
        return None
    dates = data.get("dates") or {}
    target = str(warning.get("target_kind") or "")
    if target == "contract_end":
        inputs = (dates.get("calculated_end_basis") or {}).get("inputs") or {}
        documented, derived = inputs.get("end_date"), inputs.get("derived_end_date")
        if _date_de(documented) and _date_de(derived):
            start, duration = _date_de(inputs.get("start_date")), _duration_de(inputs.get("duration"))
            days = abs((date.fromisoformat(str(documented)[:10]) - date.fromisoformat(str(derived)[:10])).days)
            fact = states_by_key.get("dates.end_date") or {}
            return {
                "topic": "contract_end",
                "title_de": "Widerspruch beim Vertragsende",
                "question_de": "Welches Vertragsende gilt?",
                "explanation_de": (
                    f"Im Dokument steht als Vertragsende der {_date_de(documented)}. Aus Vertragsbeginn und Laufzeit "
                    f"ergibt sich der {_date_de(derived)} – {days} Tage Unterschied."
                ),
                "fact_key": "dates.end_date",
                "options": [
                    {"key": "document", "label_de": "Laut Dokument", "value": str(documented)[:10],
                     "detail_de": "Ausdrücklich im Vertrag genannt", "fact_keys": ["dates.end_date"]},
                    {"key": "calculated", "label_de": "Aus Beginn + Laufzeit", "value": str(derived)[:10],
                     "detail_de": f"{start} + {duration}" if start and duration else "Aus Vertragsbeginn und Laufzeit berechnet",
                     "fact_keys": ["dates.start_date", "dates.duration"]},
                ],
                "decided_value": fact.get("effective_value") if fact.get("state") in REVIEWED_ACTIONS else None,
                "decided_by": fact.get("reviewer_display_name") if fact.get("state") in REVIEWED_ACTIONS else None,
            }
    basis_key = {"cancellation_deadline": "latest_cancellation_basis"}.get(target)
    basis = (dates.get(basis_key) or {}) if basis_key else {}
    shown = [
        {"label_de": _INPUT_LABELS_DE.get(key, key.replace("_", " ")), "value": _date_de(value) or _duration_de(value) or str(value)}
        for key, value in (basis.get("inputs") or {}).items()
        if value not in (None, "", "-")
    ]
    topic_de = {"cancellation_deadline": "beim Kündigungstermin"}.get(target, "in den Vertragsdaten")
    return {
        "topic": target or "data",
        "title_de": f"Widerspruch {topic_de}",
        "question_de": "Die Angaben aus dem Dokument passen nicht zusammen.",
        "explanation_de": "Die Werte unten widersprechen sich. Bitte die Angaben in den Vertragsdaten prüfen und richtigstellen.",
        "fact_key": {"cancellation_deadline": "termination.cancellation_period"}.get(target),
        "options": [],
        "inputs": shown,
        "decided_value": None,
        "decided_by": None,
    }


def resolve_review_warnings(data: dict, states: list[dict], review_status: str) -> None:
    """Prüf-Warnungen gelten als erledigt, sobald ihre Angaben in der Faktprüfung geprüft sind.

    Ohne zuordenbare Angabe: erledigt, wenn die Prüfung des Vertrags abgeschlossen ist. So zeigen
    „Offene Punkte“, KI-Prüfung und Faktprüfung denselben Stand.
    """
    by_key = {state["fact_key"]: state for state in states}
    for warning in data.get("warnings") or []:
        conflict = build_conflict(warning, data, by_key)
        if conflict is not None:
            warning["conflict"] = conflict
    all_done = review_status == "reviewed" and not any(
        state["present"] and state["state"] not in RESOLVED_STATES and state["state"] != "voided" for state in states
    )
    for warning in data.get("warnings") or []:
        if not warning.get("requires_review"):
            continue
        facts = [by_key[key] for key in _warning_facts(warning) if key in by_key]
        resolved = all(state["state"] in RESOLVED_STATES for state in facts) if facts else all_done
        if resolved:
            warning["requires_review"] = False
            warning["review_resolved"] = True
    _refresh_risk(data)
    review = data.get("review")
    if isinstance(review, dict):
        open_reviews = [w for w in data.get("warnings") or [] if w.get("requires_review")]
        review["requires_manual_review"] = bool(open_reviews)
        review["review_reasons"] = [w.get("title_de") for w in open_reviews if w.get("title_de")]


_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _refresh_risk(data: dict) -> None:
    """Berechnetes Risiko ohne geklärte Prüf-Warnungen (gleiche Regel wie `_project_risk_level`)."""
    warnings = data.get("warnings") or []
    risk = data.get("risk")
    if not isinstance(risk, dict) or not any(w.get("review_resolved") for w in warnings):
        return
    worst = min((_SEVERITY_ORDER.get(str(w.get("severity")), 4) for w in warnings if not w.get("review_resolved")), default=4)
    level = "high" if worst <= 1 else "medium" if worst == 2 else "low" if worst == 3 else "unknown"
    if level == risk.get("computed"):
        return
    risk["computed"] = level
    risk["confirmed"] = None
    if not risk.get("override"):
        risk["effective"] = level
        data["risk_level"] = level


def resolve_review_work_items(session, *, organization_id, contract_id, data: dict) -> int:
    """Prüf-Aufgaben (Arbeitsvorrat) schließen, deren Angaben in der Faktprüfung geprüft sind.

    Gleiche Regel wie `resolve_review_warnings`; geschlossene Aufgaben lebt `reconcile_work_items`
    nicht wieder auf. Gibt die Zahl geschlossener Aufgaben zurück.
    """
    from app.database.models.warning import ContractWarning
    from app.database.models.work_item import WorkItem

    states = build_fact_review_states(session, organization_id=organization_id, contract_id=contract_id, data=data)
    review = get_contract_review(session, organization_id=organization_id, contract_id=contract_id)
    probe = {"warnings": [], "review": None}
    items = session.scalars(
        select(WorkItem).where(
            (WorkItem.organization_id == organization_id)
            & (WorkItem.contract_id == contract_id)
            & (WorkItem.active.is_(True))
            & (WorkItem.requires_review.is_(True))
            & (WorkItem.status != "resolved")
        )
    ).all()
    for item in items:
        warning = session.get(ContractWarning, item.source_warning_id) if item.source_warning_id else None
        probe["warnings"].append({
            "requires_review": True,
            "source_refs": [str(ref) for ref in (item.source_field_refs or []) if ref],
            "target_kind": warning.target_kind if warning is not None else None,
            "_item": item,
        })
    resolve_review_warnings(probe, states, review.status if review is not None else "unreviewed")
    now = datetime.now(timezone.utc)
    closed = 0
    for entry in probe["warnings"]:
        if entry.get("review_resolved"):
            item = entry["_item"]
            item.status = "resolved"
            item.status_updated_at = now
            item.active = False
            closed += 1
    if closed:
        session.flush()
    return closed


def sync_review_links(session, *, organization_id, contract_id, data: dict, reviewer_display_name: Optional[str]) -> None:
    """Nach einer menschlichen Prüfung: Vertragsprüfung abschließen (wenn nichts offen) und Prüf-Aufgaben schließen."""
    complete_if_all_reviewed(
        session, organization_id=organization_id, contract_id=contract_id, data=data,
        reviewer_display_name=reviewer_display_name,
    )
    resolve_review_work_items(session, organization_id=organization_id, contract_id=contract_id, data=data)


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
    resolve_review_warnings(data, states, cr_dto["status"])
    return data