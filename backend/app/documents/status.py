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
    ContractExtraction,
    ProcessingRun,
)

STATE_LABELS = {
    "uploaded": "Hochgeladen",
    "processing": "Verarbeitung läuft",
    "analysis_ok": "Analyse erfolgreich",
    "analysis_partial": "Teilanalyse – Prüfung erforderlich",
    "analysis_failed": "Analyse fehlgeschlagen",
}

_KNOWN_AI_ERRORS = {
    "nicht verfügbar": "Lokale KI nicht verfügbar.",
    "nicht installiert": "Das lokale KI-Modell ist nicht installiert.",
    "zeitüberschreitung": "Die lokale KI hat nicht rechtzeitig geantwortet.",
    "invalid_schema": "Die lokale KI konnte das Ausgabeformat nicht verarbeiten.",
    "insufficient_memory": "Für die Analyse war nicht genügend Arbeitsspeicher verfügbar.",
    "model_runner_stopped": "Das KI-Modell wurde während der Analyse beendet.",
    "timeout": "Die lokale KI hat nicht rechtzeitig geantwortet.",
    "aitimeouterror": "Die lokale KI hat nicht rechtzeitig geantwortet.",
    "aiunavailableerror": "Lokale KI nicht verfügbar.",
    "aimodelmissingerror": "Das lokale KI-Modell ist nicht installiert.",
}


def safe_failure_message(*, message: str | None, error: str | None) -> str:
    """Sichere deutsche Kurzbegründung für einen Fehlschlag.

    Bekannte KI-Fehler (z. B. Modell nicht verfügbar) werden auf eine
    verständliche Ursache abgebildet; interne Fehler-Payloads werden nie
    ausgegeben.
    """
    if error:
        lowered = error.casefold()
        for needle, text in _KNOWN_AI_ERRORS.items():
            if needle in lowered:
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
    extraction = None
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
        extraction = session.scalars(
            select(ContractExtraction)
            .where(
                (ContractExtraction.document_version_id == version_id)
                & (ContractExtraction.organization_id == organization_id)
            )
            .order_by(ContractExtraction.created_at.desc(), ContractExtraction.id.desc())
            .limit(1)
        ).first()

    state = "analysis_ok" if accepted else "uploaded"
    can_retry = False
    message: str | None = None
    analysis_status: str | None = None

    run_status = getattr(run, "status", None)
    extraction_status = getattr(extraction, "status", None)
    if run_status == "running":
        state = "processing"
        analysis_status = "processing"
    elif run_status == "failed":
        state = "analysis_failed"
        analysis_status = "failed"
        can_retry = True
        message = _fail_reason(run)
    elif run_status == "partial":
        state = "analysis_partial"
        analysis_status = "partial"
        message = _fail_reason(run)
    elif extraction_status == "partial":
        # PDF/OCR processing can succeed while semantic extraction is partial.
        # The UI state must follow the latest AI extraction, not the OCR run.
        state = "analysis_partial"
        analysis_status = "partial"
        message = _fail_reason(extraction)
    elif extraction_status == "failed":
        state = "analysis_failed"
        analysis_status = "failed"
        can_retry = True
        message = _fail_reason(extraction)
    elif extraction_status == "success" and accepted:
        state = "analysis_ok"
        analysis_status = "success"
    elif run_status in {"success", "succeeded"}:
        # Some older callers used "success"; ProcessingRun currently stores
        # "succeeded". Neither implies that an extraction was accepted.
        analysis_status = "success"
        state = "analysis_ok" if accepted else "analysis_failed"
        can_retry = not accepted
        if not accepted:
            message = "Analyseergebnis wurde nicht sicher übernommen; bitte erneut verarbeiten."
    elif extraction_status is not None:
        state = "analysis_failed"
        analysis_status = "failed"
        can_retry = True
        message = _fail_reason(extraction)

    review_section = detail.get("review") or {}
    requires_review = bool(
        state in {"analysis_failed", "analysis_partial"}
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
