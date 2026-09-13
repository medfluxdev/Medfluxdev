"""Scoped processing-job facade over the canonical ProcessingRun records.

This deliberately does not introduce a second processing architecture. It exposes
JAMAL's persisted processing runs as stable job/status resources so the frontend
can show progress/history and operators can diagnose failed runs.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.scope_context import current_scope_context
from app.database.models import ContractDocument, ProcessingRun, ProcessingSummary
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/processing-jobs", tags=["processing-jobs"])


def _serialize(row: ProcessingRun, summary: ProcessingSummary | None = None) -> dict:
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
        "message": row.message,
        "error": row.error,
        "created_at": row.created_at,
        "page_count": summary.page_count if summary else None,
        "doc_type": summary.doc_type if summary else None,
        "processed_at": summary.processed_at if summary else None,
        "success_count": summary.success_count if summary else None,
        "failure_count": summary.failure_count if summary else None,
    }


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
        return {"items": [_serialize(row, summaries.get(row.document_version_id)) for row in rows], "total": len(rows)}
    finally:
        session.close()


@router.get("/{job_id}")
def get_processing_job(organization_slug: str, job_id: UUID):
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
        return _serialize(row, summary)
    finally:
        session.close()
