"""Scoped processing-job facade over the canonical ProcessingRun records.

This deliberately does not introduce a second processing architecture. It exposes
JAMAL's persisted processing runs as stable job/status resources so the frontend
can show progress/history and operators can diagnose failed runs.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from app.auth.dependencies import current_actor
from app.auth.permissions import is_admin
from app.core.scope_context import current_scope_context
from app.database.models import ContractDocument, DocumentFile, DocumentVersion, ProcessingRun, ProcessingSummary
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session
from app.documents.status import safe_failure_message

router = APIRouter(prefix="/api/processing-jobs", tags=["processing-jobs"])


_STATUS_LABELS_DE = {
    "queued": "Warteschlange",
    "running": "Wird verarbeitet",
    "succeeded": "Erfolgreich",
    "partial": "Teilweise (prüfen)",
    "failed": "Fehlgeschlagen",
    "reanalyzed": "Neu analysiert",
}

_KNOWN_KI_ERRORS = [
    ("AIUnavailableError", "Lokale KI nicht verfügbar."),
    ("AIUnavailable", "Lokale KI nicht verfügbar."),
    ("nicht verf", "Lokale KI nicht verfügbar."),
    ("RuntimeError", "Verarbeitung fehlgeschlagen."),
    ("Timeout", "Die lokale KI hat nicht rechtzeitig geantwortet."),
    ("Zeitüberschreitung", "Die lokale KI hat nicht rechtzeitig geantwortet."),
    ("HarnessFailure", "KI-Analyse konnte nicht abgeschlossen werden."),
    ("AIError", "KI-Analyse konnte nicht abgeschlossen werden."),
    ("ExtractionError", "KI-Analyse konnte nicht abgeschlossen werden."),
]


def _status_label_de(status: str) -> str:
    return _STATUS_LABELS_DE.get(status, status.replace("_", " ").title())


def _result_label_de(row: ProcessingRun, summary: ProcessingSummary | None) -> str:
    """Sichere deutsche Ergebnisbeschreibung – nie rohe interne Fehlertexte."""
    ok = summary.success_count if summary else None
    fail = summary.failure_count if summary else None
    if row.status == "succeeded":
        return f"{ok or 0} erfolgreich / {fail or 0} fehlgeschlagen"
    if row.status == "partial" and ok:
        return f"Teilweise analysiert – {ok} erfolgreich / {fail or 0} fehlgeschlagen"
    error = row.error or ""
    for needle, text in _KNOWN_KI_ERRORS:
        if needle in error:
            return text
    return safe_failure_message(message=row.message, error=row.error)


def _serialize(
    row: ProcessingRun,
    summary: ProcessingSummary | None = None,
    *,
    diagnostics: bool = True,
    origin: tuple[str | None, str | None] = (None, None),
) -> dict:
    return {
        "id": str(row.id),
        "document_version_id": str(row.document_version_id),
        "status": row.status,
        "provider": row.provider,
        "provider_version": row.provider_version,
        "schema_version": row.schema_version,
        "ocr_engine": row.ocr_engine,
        "ocr_engine_version": row.ocr_engine_version,
        "do_ocr": row.do_ocr,
        "do_table_structure": row.do_table_structure,
        "geometry_provider": row.geometry_provider,
        "processing_duration": row.processing_duration,
        # Technische Rohtexte nur fuer Administration/Entwicklung; sonst gilt result_label_de.
        "message": row.message if diagnostics else None,
        "error": row.error if diagnostics else None,
        "created_at": row.created_at,
        "contract_id": origin[0],
        "original_filename": origin[1],
        "page_count": summary.page_count if summary else None,
        "doc_type": summary.doc_type if summary else None,
        "processed_at": summary.processed_at if summary else None,
        "success_count": summary.success_count if summary else None,
        "failure_count": summary.failure_count if summary else None,
        "status_label_de": _status_label_de(row.status),
        "result_label_de": _result_label_de(row, summary),
    }


def _diagnostics_allowed(request: Request, organization_slug: str) -> bool:
    try:
        actor = current_actor(request, organization_slug)
    except HTTPException:
        return False
    return bool(getattr(actor, "is_developer", False)) or is_admin(actor)


def _origins(session, organization_id: UUID, version_ids: list[UUID]) -> dict[UUID, tuple[str | None, str | None]]:
    """Vertrag und Dateiname je Dokumentversion (fuer „Fehlgeschlagene Importe“)."""
    if not version_ids:
        return {}
    contracts: dict[UUID, str] = {}
    for version_id, contract_id in session.execute(
        select(ContractDocument.document_version_id, ContractDocument.contract_id).where(
            ContractDocument.organization_id == organization_id,
            ContractDocument.document_version_id.in_(version_ids),
        )
    ).all():
        contracts.setdefault(version_id, str(contract_id))
    names = dict(session.execute(
        select(DocumentVersion.id, DocumentFile.original_filename)
        .join(DocumentFile, DocumentFile.id == DocumentVersion.document_file_id)
        .where(DocumentVersion.organization_id == organization_id, DocumentVersion.id.in_(version_ids))
    ).all())
    return {version_id: (contracts.get(version_id), names.get(version_id)) for version_id in version_ids}


def _allowed_document_versions(session, organization_id: UUID) -> set[UUID] | None:
    scope = current_scope_context()
    allowed_contracts = scoped_contract_ids(
        session, organization_id, scope.hospital_id, scope.department_id
    )
    if allowed_contracts is None:
        return None
    if not allowed_contracts:
        return set()
    return set(
        session.scalars(
            select(ContractDocument.document_version_id).where(
                ContractDocument.organization_id == organization_id,
                ContractDocument.contract_id.in_(allowed_contracts),
            )
        ).all()
    )


@router.get("")
def list_processing_jobs(
    request: Request,
    organization_slug: str,
    status: list[str] = Query(default=[]),
    limit: int = Query(default=100, ge=1, le=500),
):
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        stmt = select(ProcessingRun).where(ProcessingRun.organization_id == org.id)
        if status:
            stmt = stmt.where(ProcessingRun.status.in_(status))
        allowed_versions = _allowed_document_versions(session, org.id)
        if allowed_versions is not None:
            stmt = stmt.where(ProcessingRun.document_version_id.in_(allowed_versions))
        rows = session.scalars(stmt.order_by(ProcessingRun.created_at.desc()).limit(limit)).all()
        summaries = {
            row.document_version_id: row
            for row in session.scalars(
                select(ProcessingSummary).where(
                    ProcessingSummary.organization_id == org.id,
                    ProcessingSummary.document_version_id.in_([r.document_version_id for r in rows]),
                )
            ).all()
        } if rows else {}
        diagnostics = _diagnostics_allowed(request, organization_slug)
        origins = _origins(session, org.id, list({row.document_version_id for row in rows}))
        return {
            "items": [
                _serialize(row, summaries.get(row.document_version_id), diagnostics=diagnostics,
                           origin=origins.get(row.document_version_id, (None, None)))
                for row in rows
            ],
            "total": len(rows),
        }
    finally:
        session.close()


@router.get("/{job_id}")
def get_processing_job(request: Request, organization_slug: str, job_id: UUID):
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        row = session.get(ProcessingRun, job_id)
        if row is None or row.organization_id != org.id:
            raise HTTPException(status_code=404, detail="Verarbeitungslauf nicht gefunden.")
        allowed_versions = _allowed_document_versions(session, org.id)
        if allowed_versions is not None and row.document_version_id not in allowed_versions:
            raise HTTPException(status_code=404, detail="Verarbeitungslauf nicht gefunden.")
        summary = session.scalars(
            select(ProcessingSummary).where(
                ProcessingSummary.organization_id == org.id,
                ProcessingSummary.document_version_id == row.document_version_id,
            )
        ).first()
        return _serialize(
            row, summary, diagnostics=_diagnostics_allowed(request, organization_slug),
            origin=_origins(session, org.id, [row.document_version_id]).get(row.document_version_id, (None, None)),
        )
    finally:
        session.close()
