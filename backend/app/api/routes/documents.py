"""Production document-import route (STEP 4-15).

Every browser import is delegated to the single `DocumentProcessingService`
orchestrator.  The old manifest-only import and standalone extract/analyze HTTP
routes are intentionally not exposed: they bypass accepted persistence state and
would form a second production processing architecture.
"""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select

from app.database.models import DocumentFile, DocumentVersion
from app.core.config import settings
from app.documents.persistence import DocumentPersistenceService, StorageError
from app.documents.processing import DocumentProcessingService
from app.documents.schemas import ImportBatchResponse, ImportFileResult, ImportStatus
from app.documents.source_region import resolve_narrowest_region
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/documents", tags=["documents"])

_processing_service = DocumentProcessingService()


async def _read_upload_bounded(uploaded: UploadFile) -> bytes:
    """Read one upload without allowing an oversized body to exhaust memory."""
    limit = max(1, int(settings.max_upload_size_mb)) * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await uploaded.read(min(1024 * 1024, limit + 1 - total))
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


@router.post("/{document_version_id}/retry", response_model=RetryDocumentResponse)
async def retry_document(
    document_version_id: str,
    organization_slug: str = Query(min_length=1),
) -> RetryDocumentResponse:
    """Fehlgeschlagene/nicht abgeschlossene Verarbeitung erneut ausfuehren.

    Resume by opaque DocumentVersion-ID (kein erneuter Upload). Die Original-
    Bytes und der Storage-Key werden serverseitig aufgeloest.
    """
    processed = await run_in_threadpool(
        _processing_service.resume_document,
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
        message=(
            processed.message
            or _SAFE_FALLBACK_MESSAGES.get(str(processed.status), "")
        ),
    )


@router.post("/{document_version_id}/reanalyze", response_model=RetryDocumentResponse)
async def reanalyze_document(
    document_version_id: str,
    organization_slug: str = Query(min_length=1),
) -> RetryDocumentResponse:
    """Explizite Reanalyse eines bereits akzeptierten Vertrags.

    Anders als `/retry` wird der vorhandene Accepted Contract bewusst erneut durch
    Harness/Qwen analysiert. Die bisherige akzeptierte Wahrheit bleibt bei Fehlern
    unverändert und wird nur nach vollständigem Erfolg atomar ersetzt.
    """
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
        message=(
            processed.message
            or _SAFE_FALLBACK_MESSAGES.get(str(processed.status), "")
        ),
    )


@router.post("/import", response_model=ImportBatchResponse)
async def import_documents(
    files: list[UploadFile] = File(default=[]),
    organization_slug: str = Query(min_length=1),
) -> ImportBatchResponse:
    """Imports PDF/DOCX files through the persisted production orchestrator."""

    if not files:
        return ImportBatchResponse(
            total=0, successful=0, failed=0, duplicates=0, documents=[]
        )

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
        results.append(
            ImportFileResult(
                document_id=processed.document_id or None,
                document_version_id=processed.document_version_id or None,
                original_filename=processed.original_filename,
                status=ImportStatus(processed.status),
                size=len(raw),
                sha256=processed.sha256 or None,
                # Never fall back to ProcessedDocument.error: it intentionally
                # contains protected provider/DB/exception diagnostics.
                message=(
                    processed.message
                    or _SAFE_FALLBACK_MESSAGES.get(processed.status)
                ),
                analysis_status=processed.analysis_status,
                requires_review=processed.requires_review,
                contract_id=processed.contract_id,
            )
        )

    successful = sum(
        1 for result in results if result.status == ImportStatus.IMPORTED
    )
    duplicates = sum(
        1 for result in results if result.status == ImportStatus.DUPLICATE
    )
    failed = sum(
        1
        for result in results
        if result.status
        in {
            ImportStatus.FAILED,
            ImportStatus.REJECTED,
            ImportStatus.ANALYSIS_FAILED,
        }
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
    organization_slug: str = Query(min_length=1),
    snippet: str = Query(min_length=2, max_length=500),
    page: int | None = Query(default=None, ge=1),
) -> dict:
    """Narrowest trustworthy PDF region for a fact snippet (PR-5 UAT D).

    Ehrlich: nur Regionen, in denen der Text nachweisbar steht (Text-Layer
    bzw. validierte atomare Zellen). `status` ist `exact`, `coarse` oder
    `none` – nie erfundene Koordinaten. Auch `page` ist facetten-co,
    damit der PdfViewer nur nachladen kann, wenn er bereits dieselbe Seite
    zeigt.
    """
    import uuid

    try:
        vid = uuid.UUID(document_version_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")

    with create_session() as session:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
        version = session.scalars(
            select(DocumentVersion).where(
                (DocumentVersion.id == vid)
                & (DocumentVersion.organization_id == org.id)
            )
        ).first()
        if version is None:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")

        doc_file = None
        if version.document_file_id is not None:
            doc_file = session.get(DocumentFile, version.document_file_id)
        ext = (doc_file.file_extension or "").lower() if doc_file else ""
        if ext != "pdf":
            raise HTTPException(
                status_code=415, detail="Quell-Geometrie nur für PDF verfügbar."
            )

        svc = DocumentPersistenceService()
        try:
            content = svc.resolve_bytes_for_version(
                session,
                organization_id=org.id,
                document_version_id=vid,
            )
        except StorageError:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
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
