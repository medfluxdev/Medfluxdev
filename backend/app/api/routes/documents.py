"""Production document-import route (STEP 4-15).

Every browser import is delegated to the single `DocumentProcessingService`
orchestrator. The old manifest-only import and standalone extract/analyze HTTP
routes are intentionally not exposed: they bypass accepted persistence state and
would form a second production processing architecture.
"""

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import (
    Contract,
    AccountMembership,
    ContractDocument,
    Department,
    DocumentFile,
    DocumentVersion,
    Hospital,
)
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session
from app.documents.persistence import DocumentPersistenceService, StorageError
from app.documents.processing import DocumentProcessingService
from app.documents.schemas import ImportBatchResponse, ImportFileResult, ImportStatus
from app.documents.source_region import resolve_narrowest_region
from app.ownership.service import OwnershipError, assign_contract_ownership

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _is_pdf_extension(value: str | None) -> bool:
    return str(value or "").strip().lstrip(".").casefold() == "pdf"

_processing_service = DocumentProcessingService()


async def _read_upload_bounded(uploaded: UploadFile) -> bytes:
    """Read one upload without allowing an oversized body to exhaust memory."""
    limit = max(1, int(settings.max_upload_size_mb)) * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        remaining = limit + 1 - total
        chunk = await uploaded.read(min(1024 * 1024, remaining))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"Datei ist groesser als das erlaubte Limit von {settings.max_upload_size_mb} MB.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


_SAFE_FALLBACK_MESSAGES = {
    "rejected": "Dokument wurde abgelehnt.",
    "failed": "Verarbeitung fehlgeschlagen.",
    "analysis_failed": "Dokumentanalyse konnte nicht abgeschlossen werden.",
    "duplicate": "Dokument wurde bereits verarbeitet.",
    "reanalyzed": "Dokument erfolgreich neu analysiert.",
}


class RetryDocumentResponse(BaseModel):
    document_id: str | None = None
    document_version_id: str | None = None
    status: str
    message: str | None = None
    analysis_status: str | None = None
    requires_review: bool = False
    contract_id: str | None = None


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Dokument nicht gefunden.")


def _parse_version_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise _not_found()


def _linked_contract_ids(session, organization_id: UUID, document_version_id: UUID) -> set[UUID]:
    return set(
        session.scalars(
            select(ContractDocument.contract_id).where(
                (ContractDocument.organization_id == organization_id)
                & (ContractDocument.document_version_id == document_version_id)
            )
        ).all()
    )


def _ensure_document_visible(session, organization_id: UUID, document_version_id: UUID) -> None:
    scope = current_scope_context()
    visible = scoped_contract_ids(
        session, organization_id, scope.hospital_id, scope.department_id
    )
    if visible is None:
        return
    linked = _linked_contract_ids(session, organization_id, document_version_id)
    if not linked or linked.isdisjoint(visible):
        raise _not_found()


def _preflight_document(organization_slug: str, document_version_id: str) -> UUID:
    vid = _parse_version_id(document_version_id)
    with create_session() as session:
        org = get_organization(session, organization_slug)
        if org is None:
            raise _not_found()
        version = session.scalars(
            select(DocumentVersion).where(
                (DocumentVersion.id == vid)
                & (DocumentVersion.organization_id == org.id)
            )
        ).first()
        if version is None:
            raise _not_found()
        _ensure_document_visible(session, org.id, vid)
    return vid


def _validate_import_scope(organization_slug: str) -> None:
    """Reject invalid/unprovisioned scoped imports before any document is processed."""
    scope = current_scope_context()
    if scope.hospital_id is None and scope.department_id is None:
        return
    with create_session() as session:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        hospital = session.get(Hospital, scope.hospital_id) if scope.hospital_id else None
        if hospital is None or hospital.organization_id != org.id or not hospital.is_active:
            raise HTTPException(
                status_code=403,
                detail="Der Benutzer hat noch keinen gültigen Krankenhaus-Arbeitsbereich.",
            )
        if scope.department_id is not None:
            department = session.get(Department, scope.department_id)
            if (
                department is None
                or department.organization_id != org.id
                or department.hospital_id != hospital.id
                or not department.is_active
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Der Benutzer hat noch keinen gültigen Abteilungs-Arbeitsbereich.",
                )


def _assign_import_scope(organization_slug: str, contract_id: str | None, status: str) -> None:
    """Persist the current hospital/department scope on newly imported contracts."""
    if not contract_id or status != "imported":
        return
    scope = current_scope_context()
    if scope.hospital_id is None and scope.department_id is None:
        return
    try:
        cid = UUID(contract_id)
    except ValueError:
        return

    with create_session() as session:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        contract = session.scalars(
            select(Contract).where(
                (Contract.id == cid) & (Contract.organization_id == org.id)
            )
        ).first()
        if contract is None:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        try:
            assign_contract_ownership(
                session,
                contract=contract,
                hospital_id=scope.hospital_id,
                department_ids=[scope.department_id] if scope.department_id else [],
                cost_center_id=None,
            )
            session.commit()
        except OwnershipError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{document_version_id}/retry", response_model=RetryDocumentResponse)
async def retry_document(
    document_version_id: str,
    organization_slug: str = Query(min_length=1),
) -> RetryDocumentResponse:
    _preflight_document(organization_slug, document_version_id)
    processed = await run_in_threadpool(
        _processing_service.resume_document,
        organization_slug=organization_slug,
        document_version_id=document_version_id,
    )
    _assign_import_scope(organization_slug, processed.contract_id, str(processed.status))
    return RetryDocumentResponse(
        document_id=processed.document_id or None,
        document_version_id=processed.document_version_id or None,
        status=str(processed.status),
        analysis_status=processed.analysis_status,
        requires_review=processed.requires_review,
        contract_id=processed.contract_id,
        message=(processed.message or _SAFE_FALLBACK_MESSAGES.get(str(processed.status), "")),
    )


@router.post("/{document_version_id}/reanalyze", response_model=RetryDocumentResponse)
async def reanalyze_document(
    document_version_id: str,
    organization_slug: str = Query(min_length=1),
) -> RetryDocumentResponse:
    _preflight_document(organization_slug, document_version_id)
    processed = await run_in_threadpool(
        _processing_service.reanalyze_document,
        organization_slug=organization_slug,
        document_version_id=document_version_id,
    )
    return RetryDocumentResponse(
        document_id=processed.document_id or None,
        document_version_id=processed.document_version_id or None,
        status=str(processed.status),
        analysis_status=processed.analysis_status,
        requires_review=processed.requires_review,
        contract_id=processed.contract_id,
        message=(processed.message or _SAFE_FALLBACK_MESSAGES.get(str(processed.status), "")),
    )


@router.post("/import", response_model=ImportBatchResponse)
async def import_documents(
    files: list[UploadFile] = File(default=[]),
    organization_slug: str = Query(min_length=1),
) -> ImportBatchResponse:
    if not files:
        return ImportBatchResponse(total=0, successful=0, failed=0, duplicates=0, documents=[])

    _validate_import_scope(organization_slug)

    results: list[ImportFileResult] = []
    for uploaded in files:
        raw = await _read_upload_bounded(uploaded)
        processed = await run_in_threadpool(
            _processing_service.process,
            organization_slug=organization_slug,
            original_filename=uploaded.filename or "",
            content_type=uploaded.content_type or "",
            content=raw,
        )
        processed_status = str(processed.status)
        _assign_import_scope(organization_slug, processed.contract_id, processed_status)
        results.append(
            ImportFileResult(
                document_id=processed.document_id or None,
                document_version_id=processed.document_version_id or None,
                original_filename=processed.original_filename,
                status=ImportStatus(processed.status),
                size=len(raw),
                sha256=processed.sha256 or None,
                message=(processed.message or _SAFE_FALLBACK_MESSAGES.get(processed.status)),
                analysis_status=processed.analysis_status,
                requires_review=processed.requires_review,
                contract_id=processed.contract_id,
            )
        )

    successful = sum(1 for result in results if result.status == ImportStatus.IMPORTED)
    duplicates = sum(1 for result in results if result.status == ImportStatus.DUPLICATE)
    failed = sum(
        1
        for result in results
        if result.status in {ImportStatus.FAILED, ImportStatus.REJECTED, ImportStatus.ANALYSIS_FAILED}
    )
    return ImportBatchResponse(
        total=len(results),
        successful=successful,
        failed=failed,
        duplicates=duplicates,
        documents=results,
    )


@router.get("/{document_version_id}/source-region")
def document_source_region(
    document_version_id: str,
    request: Request,
    organization_slug: str = Query(min_length=1),
    snippet: str = Query(min_length=2, max_length=500),
    page: int | None = Query(default=None, ge=1),
) -> dict:
    vid = _parse_version_id(document_version_id)

    with create_session() as session:
        org = get_organization(session, organization_slug)
        actor = getattr(request.state, "actor", None)
        if org is None or (settings.auth_enabled and (
            actor is None or actor.organization_id != org.id
        )):
            raise _not_found()
        version = session.scalars(
            select(DocumentVersion).where(
                (DocumentVersion.id == vid)
                & (DocumentVersion.organization_id == org.id)
            )
        ).first()
        if version is None:
            raise _not_found()
        _ensure_document_visible(session, org.id, vid)
        # Do not rely solely on request-entry scope for a source lookup:
        # re-read the account's current hospital/department assignment.
        if settings.auth_enabled and actor is not None and not (
            actor.role == "admin" or getattr(actor, "is_developer", False)
        ):
            membership = session.scalar(select(AccountMembership).where(
                AccountMembership.account_id == actor.account_id,
                AccountMembership.organization_id == org.id,
                AccountMembership.is_active.is_(True),
            ))
            if membership is None:
                raise _not_found()
            assigned = scoped_contract_ids(
                session, org.id, membership.hospital_id or UUID(int=0),
                membership.department_id,
            )
            linked = _linked_contract_ids(session, org.id, vid)
            if assigned is None or not linked or assigned.isdisjoint(linked):
                raise _not_found()

        doc_file = session.get(DocumentFile, version.document_file_id) if version.document_file_id is not None else None
        if not _is_pdf_extension(doc_file.file_extension if doc_file else None):
            raise HTTPException(status_code=415, detail="Quell-Geometrie nur für PDF verfügbar.")

        svc = DocumentPersistenceService()
        try:
            content = svc.resolve_bytes_for_version(
                session,
                organization_id=org.id,
                document_version_id=vid,
            )
        except StorageError:
            raise _not_found()
        canonical = svc.resolve_canonical_for_version(
            session,
            organization_id=org.id,
            document_version_id=vid,
        )

    region = resolve_narrowest_region(
        snippet,
        pdf_bytes=content,
        canonical=canonical,
        page_hint=page,
    )
    region["document_version_id"] = str(vid)
    region["snippet"] = snippet
    region["message_de"] = _source_region_message(region["status"])
    return region


def _source_region_message(status: str) -> str:
    if status == "exact":
        return "Exakte Fundstelle im Originaldokument."
    if status == "coarse":
        return "Fundstelle nur grob bestimmbar (ungefähre Lage)."
    return "Fundstelle im Originaldokument nicht auffindbar."
