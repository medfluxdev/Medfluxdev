"""Stand der Feldprüfung aus dem Ereignisprotokoll (`contract_review_event`).

Das Protokoll wird nur ergänzt. Der aktuelle Stand eines Felds oder Nachweises ist das jeweils letzte passende
Ereignis; frühere bleiben als Verlauf erhalten. Reiner Lesecode plus ein Schreibweg (`add_event`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ContractReviewEvent

EXCLUSION_REASONS: dict[str, str] = {
    "wrong_place": "Falsche Stelle im Dokument",
    "other_meaning": "Gemeint ist etwas anderes",
    "outdated": "Überholt (z. B. durch einen Nachtrag)",
    "unreadable": "Schlecht lesbar oder abgeschnitten",
    "other": "Sonstiges",
}

FINDING_KINDS = ("finding_linked", "finding_note", "finding_dismissed", "finding_restored")


@dataclass
class Exclusion:
    reason: str
    note: Optional[str]
    by: Optional[str]
    at: datetime


@dataclass
class ReviewEvents:
    """Aus dem Protokoll abgeleiteter Stand."""

    #: ausgeschlossene Nachweise (je Nachweis; Wiederherstellen hebt den Ausschluss auf)
    excluded: dict[str, Exclusion] = field(default_factory=dict)
    #: gewählter Hauptnachweis je Feld
    primary: dict[str, str] = field(default_factory=dict)
    #: zurückgestellte Felder -> Zeitpunkt
    deferred: dict[str, datetime] = field(default_factory=dict)
    #: „im Dokument nicht vorhanden“ je Feld -> Zeitpunkt
    absent: dict[str, datetime] = field(default_factory=dict)
    #: Umgang mit Weiteren Informationen je Fund: letztes Ereignis
    findings: dict[str, ContractReviewEvent] = field(default_factory=dict)
    #: letzter Zeitpunkt je Feld (Stand für gleichzeitige Änderungen)
    touched: dict[str, datetime] = field(default_factory=dict)
    #: alle Ereignisse je Feld in zeitlicher Folge (Verlauf)
    history: dict[str, list[ContractReviewEvent]] = field(default_factory=dict)


def load_events(session: Session, contract_id) -> ReviewEvents:
    rows = session.execute(
        select(ContractReviewEvent)
        .where(ContractReviewEvent.contract_id == contract_id)
        .order_by(ContractReviewEvent.created_at, ContractReviewEvent.id)
    ).scalars().all()
    state = ReviewEvents()
    for row in rows:
        key = row.fact_key
        if key:
            state.touched[key] = row.created_at
            state.history.setdefault(key, []).append(row)
        if row.kind == "evidence_excluded" and row.evidence_id:
            state.excluded[row.evidence_id] = Exclusion(
                str((row.payload or {}).get("reason") or "other"), row.note, row.actor_name, row.created_at
            )
            # Ein ausgeschlossener Hauptnachweis ist keiner mehr.
            if key and state.primary.get(key) == row.evidence_id:
                state.primary.pop(key, None)
        elif row.kind == "evidence_restored" and row.evidence_id:
            state.excluded.pop(row.evidence_id, None)
        elif row.kind == "primary_selected" and key and row.evidence_id:
            state.primary[key] = row.evidence_id
        elif row.kind == "deferred" and key:
            state.deferred[key] = row.created_at
        elif row.kind == "not_in_document" and key:
            state.absent[key] = row.created_at
        elif row.kind == "decision" and key:
            # Eine Entscheidung beendet das Zurückstellen und die Angabe „nicht im Dokument“.
            state.deferred.pop(key, None)
            state.absent.pop(key, None)
        elif row.kind in FINDING_KINDS and key:
            state.findings[key] = row
    return state


def add_event(
    session: Session, *, organization_id, contract_id, kind: str, fact_key: Optional[str] = None,
    evidence_id: Optional[str] = None, note: Optional[str] = None, payload: Optional[dict] = None,
    actor_account_id=None, actor_name: Optional[str] = None,
) -> ContractReviewEvent:
    event = ContractReviewEvent(
        organization_id=organization_id, contract_id=contract_id, kind=kind, fact_key=fact_key,
        evidence_id=evidence_id, note=(note or "").strip() or None, payload=payload or {},
        actor_account_id=actor_account_id, actor_name=actor_name,
    )
    session.add(event)
    session.flush()
    return event
