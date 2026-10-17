"""Nachweisprüfung: Ergebnis je Nachweis und Zusammenfassung einer Runde im Verlauf.

Der Wert einer Angabe wird weiter ueber die Faktpruefung gespeichert (bestaetigt/korrigiert);
hier steht nur, wie jeder Nachweis erledigt wurde – auch „abweichend, geklärt“ und
„übersprungen“, die die Faktpruefung nicht kennt.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Contract, ContractEvidenceReview
from app.database.models.register import EVIDENCE_REVIEW_STATUSES
from app.register.service import RegisterActor, RegisterError, log_activity

STATUS_LABELS = {
    "confirmed": "Bestätigt",
    "document": "Abweichend · Dokument übernommen",
    "medflux": "Abweichend · geklärt",
    "manual": "Abweichend · von Hand eingetragen",
    "skipped": "Übersprungen",
}


def _item(row: ContractEvidenceReview) -> dict:
    return {
        "evidence_id": row.evidence_id,
        "fact_key": row.fact_key,
        "status": row.status,
        "status_label": STATUS_LABELS[row.status],
        "note": row.note,
        "reviewed_by_name": row.reviewed_by_name,
        "reviewed_at": row.reviewed_at.isoformat(),
    }


def list_evidence_reviews(session: Session, contract_id) -> list[dict]:
    rows = session.scalars(
        select(ContractEvidenceReview)
        .where(ContractEvidenceReview.contract_id == contract_id)
        .order_by(ContractEvidenceReview.reviewed_at)
    ).all()
    return [_item(row) for row in rows]


def set_evidence_review(
    session: Session,
    *,
    contract: Contract,
    actor: RegisterActor,
    evidence_id: str,
    status: str,
    fact_key: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    """Ergebnis eines Nachweises setzen (ersetzt ein frueheres). Einzelne Schritte stehen nicht im
    Verlauf – dort steht die Runde (`log_evidence_round`), die Werte stehen in der Faktpruefung."""
    evidence_id = (evidence_id or "").strip()
    if not evidence_id:
        raise RegisterError(422, "Nachweis fehlt.")
    if status not in EVIDENCE_REVIEW_STATUSES:
        raise RegisterError(422, "Unbekanntes Prüfergebnis.")
    note = (note or "").strip() or None
    row = session.scalars(
        select(ContractEvidenceReview)
        .where(
            ContractEvidenceReview.contract_id == contract.id,
            ContractEvidenceReview.evidence_id == evidence_id,
        )
        .with_for_update()
    ).first()
    if row is None:
        row = ContractEvidenceReview(
            organization_id=contract.organization_id, contract_id=contract.id, evidence_id=evidence_id,
            status=status, reviewed_at=datetime.now(timezone.utc),
        )
        session.add(row)
    row.status = status
    row.fact_key = fact_key
    row.note = note
    row.reviewed_by_account_id = actor.account_id
    row.reviewed_by_name = actor.display_name
    row.reviewed_at = datetime.now(timezone.utc)
    session.flush()
    return _item(row)


def round_summary(counts: dict[str, int]) -> str:
    """„34 geprüft: 30 bestätigt · 3 abweichend (übernommen 2, geklärt 1) · 1 übersprungen“."""
    document, medflux, manual = counts.get("document", 0), counts.get("medflux", 0), counts.get("manual", 0)
    deviating = document + medflux + manual
    checked = counts.get("confirmed", 0) + deviating + counts.get("skipped", 0)
    parts = [f"{counts.get('confirmed', 0)} bestätigt"]
    if deviating:
        detail = [text for value, text in (
            (document, f"übernommen {document}"), (medflux, f"geklärt {medflux}"), (manual, f"von Hand {manual}"),
        ) if value]
        parts.append(f"{deviating} abweichend ({', '.join(detail)})")
    if counts.get("skipped", 0):
        parts.append(f"{counts['skipped']} übersprungen")
    return f"{checked} geprüft: " + " · ".join(parts)


def log_evidence_round(session: Session, *, contract: Contract, actor: RegisterActor, counts: dict[str, int]) -> str:
    clean = {key: max(0, int(counts.get(key) or 0)) for key in EVIDENCE_REVIEW_STATUSES}
    if not any(clean.values()):
        raise RegisterError(422, "In dieser Runde wurde kein Nachweis bearbeitet.")
    summary = round_summary(clean)
    log_activity(session, actor, contract.id, "contract.evidence_reviewed", {"summary": summary, "counts": clean})
    return summary
