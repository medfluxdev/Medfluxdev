"""Import-/Verarbeitungszustand eines Vertrags für die UI (failure-safe).

Unterscheidet ehrlich: Hochgeladen / Verarbeitung läuft / Analyse erfolgreich /
Analyse fehlgeschlagen. „Analyse erfolgreich" wird NUR angezeigt, wenn wirklich
eine akzeptierte Analyse vorliegt. Bei Fehlschlag bleibt der Vertrag sichtbar
(Platzhalter), `can_retry` ermöglicht einen erneuten Verarbeitungslauf.

Als `import_error` werden NUR sichere deutsche Kurztexte ausgegeben (nie
interne Fehler-Payloads). Bekannte KI-Fehler werden auf eine verständliche
Ursache abgebildet, z. B. „Lokale KI nicht verfügbar.".
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    Contract,
    ContractDocument,
    ProcessingRun,
)

STATE_LABELS = {
    "uploaded": "Hochgeladen",
    "processing": "Verarbeitung läuft",
    "analysis_ok": "Analyse erfolgreich",
    "analysis_failed": "Analyse fehlgeschlagen",
}

_KNOWN_AI_ERRORS = [
    ("nicht verfügbar", "Lokale KI nicht verfügbar."),
    ("nicht installiert", "Das lokale KI-Modell ist nicht installiert."),
    ("Zeitüberschreitung", "Die lokale KI hat nicht rechtzeitig geantwortet."),
]


def safe_failure_message(*, message: str | None, error: str | None) -> str:
    """Sichere deutsche Kurzbegründung für einen Fehlschlag.

    Bekannte KI-Fehler (z. B. Modell nicht verfügbar) werden auf eine
    verständliche Ursache abgebildet; interne Fehler-Payloads werden nie
    ausgegeben.
    """
    if error:
        for needle, text in _KNOWN_AI_ERRORS:
            if needle in error:
                return text
    return message or "Verarbeitung konnte nicht abgeschlossen werden."


def _fail_reason(run) -> str:
    return safe_failure_message(message=run.message, error=run.error)


def build_import_state(session: Session, *, organization_id, contract_id, detail: dict) -> dict:
    contract = session.get(Contract, contract_id)
    accepted = bool(contract and contract.accepted_extraction_id is not None)

    version_id = session.scalars(
        select(ContractDocument.document_version_id)
        .where(
            (ContractDocument.contract_id == contract_id)
            & (ContractDocument.role == "main")
        )
        .limit(1)
    ).first()

    run = None
    if version_id is not None:
        run = session.scalars(
            select(ProcessingRun)
            .where(
                (ProcessingRun.document_version_id == version_id)
                & (ProcessingRun.organization_id == organization_id)
            )
            .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
            .limit(1)
        ).first()

    state = "analysis_ok"
    can_retry = False
    message: str | None = None
    analysis_status: str | None = None

    if not accepted:
        if run is None:
            state = "uploaded"
        elif run.status == "running":
            state = "processing"
        else:  # failed | partial
            state = "analysis_failed"
            can_retry = True
            analysis_status = run.status
            message = _fail_reason(run)

    if run is not None and analysis_status is None:
        analysis_status = run.status if run.status in ("success", "partial") else None

    review_section = detail.get("review") or {}
    requires_review = bool(
        state == "analysis_failed"
        or review_section.get("requires_manual_review", False)
    )

    return {
        "import_state": state,
        "state_label_de": STATE_LABELS.get(state, state),
        "document_version_id": str(version_id) if version_id is not None else None,
        "can_retry": can_retry,
        "message": message,
        "analysis_status": analysis_status,
        "requires_review": requires_review,
    }