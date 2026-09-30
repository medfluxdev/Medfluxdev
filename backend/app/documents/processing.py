"""Single production orchestration path for document processing (STEP 4-15).

`DocumentProcessingService` is the only import/resume/reconciliation orchestrator:

    protected original -> canonical document intelligence -> local fact extraction
    -> deterministic calculation -> warning evaluation -> accepted contract truth

Expensive DI/OCR/AI work runs outside database transactions.  Short transactions
claim a version, persist immutable artifacts, and atomically persist accepted
extraction/calculation/contract/warning state.  Failed or stale runs remain
resumable; a duplicate is only considered complete when it is linked to an
accepted contract truth.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select, update

from app.ai.contract_extractor import (
    ContractAnalysisOrchestrator,
    ContractAnalysisResult,
)
from app.contracts.calculation import calculate_contract
from app.contracts.calculation.models import CalculationStatus
from app.contracts.warnings import (
    DEFAULT_POLICY_VERSION,
    WarningPolicy,
    evaluate_contract_warnings,
)
from app.core.config import settings
from app.documents.status import safe_failure_message
from app.database.models import (
    Contract,
    ContractDocument,
    ContractEquipment,
    ContractWarning,
    DocumentArtifact,
    DocumentFile,
    DocumentVersion,
    ProcessingRun,
)
from app.database.services import (
    accept_calculation,
    accept_extraction,
    add_equipment,
    create_contract,
    create_processing_run,
    finish_processing_run,
    get_organization,
    link_document,
    project_contract,
    run_warning_evaluation,
    save_calculation,
    save_extraction,
    upsert_processing_summary,
)
from app.database.session import create_session
from app.documents.extraction.schemas import (
    ExtractionUnit,
    FileType,
    SourceBox,
    SourceType,
    TextExtractionResult,
    UnitMethod,
)
from app.documents.extraction.service import TextExtractionService
from app.documents.intelligence.canonical import (
    CANONICAL_SCHEMA_VERSION,
    DocumentIntelligenceResult,
    LogicalUnit,
    Method,
    ProcessingProvenance,
)
from app.documents.intelligence.provider import (
    DocumentIntelligenceProvider,
    DocumentIntelligenceSettings,
    get_provider,
)
from app.documents.persistence import DocumentPersistenceService
from app.documents.storage import DocumentStorage, StorageError
from app.models.enums import ExtractionStatus, ValidationStatus
from app.work_queue.derive import derive_work_items
from app.work_queue.service import reconcile_work_items

logger = logging.getLogger(__name__)

# Snapshot groups whose field-bound source is projected relationally.
_EVIDENCE_GROUPS = (
    "identity",
    "dates",
    "termination",
    "costs",
    "payment",
    "services",
    "sla",
)
CALC_VERSION = "step9-1.1"
_SAFE_PROCESSING_FAILURE = "Verarbeitung fehlgeschlagen."
_SAFE_ANALYSIS_FAILURE = "Dokumentanalyse konnte nicht abgeschlossen werden."


def _map_failure_message(analysis) -> str:
    return safe_failure_message(
        message=analysis.message if analysis is not None else None,
        error=analysis.error if analysis is not None else None,
    )
_SAFE_NO_TEXT = "Text konnte nicht extrahiert werden."

# Muster für Werte, die niemals in ein persistiertes/persistentes Fehlerfeld
# gelangen dürfen (auch nicht in den technischen `error`-Spalte): absolute
# Dateisystempfade (Windows + POSIX) und mutmassliche Secrets.
_WINDOWS_ABS_PATH = re.compile(r"[A-Za-z]:[\\/][^\s'\"<>]+")
# Absoluter POSIX-Pfad/URL-Wert mit mehreren /-Segmenten (z. B. /var/lib/...,
# postgresql://user:pw@host:5432/db). Bewusst auf mehrfache Segmente
# beschraenkt, damit einfache Pfadfragmente nicht faelschlich entfernt werden.
_POSIX_ABS_PATH = re.compile(r"/[\w.\-]+(?:/[\w.\-]*)+")
# Typische Secret-Muster, die auch in der finalen Fehlermeldung nie persistiert
# werden dürfen (AWS-Zugangsschluessel, password=, api_key/token, Bearer).
# Die Werte werden ersetzt, die Label bleiben als Hinweis erhalten.
_SECRET_TOKENS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # Bearer-Token (z. B. JWT) komplett maskieren – nicht nur das Label.
    re.compile(r"\bBearer\s+\S+", re.IGNORECASE),
    re.compile(r"(password|passwd|pwd)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"(api[_-]?key|secret)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"(authorization)\s*[=:]\s*\S+", re.IGNORECASE),
)


def _sanitized_error(error: str) -> Optional[str]:
    """Normalisiert einen technischen Fehlertext für die Persistenz.

    Tracebacks werden nie persistiert – nur die eigentliche letzte Meldung
    (die vorhergehenden Frames enthalten Pfade/Quellzeilen und werden
    verworfen). Absolute Pfade und mutmassliche Secrets werden zusätzlich
    maskiert. Das Ergebnis ist einzeilig, groessenbegrenzt und enthaelt weder
    Pfade, Tracebacks noch Source-Details. ``None`` wenn leer.
    """
    if not error:
        return None
    raw = str(error)
    # Von einem Traceback nur die letzte, eigentliche Fehlerzeile behalten.
    # Diese steht bei Python-Tracebacks immer in Spalte 0; die vorhergehenden
    # eingerueckten Frame-/Quellzeilen (mit Datei- und Zeilennummern) werden so
    # verworfen, damit weder absolute noch relative Pfade eingehen.
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[0].lstrip().startswith("Traceback"):
        text = ""
        for ln in reversed(lines):
            if ln.strip() and not ln[:1].isspace():
                text = ln
                break
    else:
        text = raw
    text = text.replace("\t", " ")
    text = _WINDOWS_ABS_PATH.sub("<path>", text)
    text = _POSIX_ABS_PATH.sub("<path>", text)
    for pat in _SECRET_TOKENS:
        text = pat.sub("<secret>", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    return text[:500]



@dataclass
class ProcessedDocument:
    """Internal result of one full production processing request.

    ``error`` is protected diagnostic state and must never be rendered by an API.
    ``message`` is the only browser-safe human-readable field.
    """

    document_id: str
    document_version_id: str
    sha256: str
    original_filename: str
    status: str  # imported | reanalyzed | duplicate | rejected | failed | analysis_failed
    analysis_status: Optional[str] = None
    requires_review: bool = False
    contract_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


class DocumentProcessingService:
    """Orchestrates every production import/resume through the same path."""

    def __init__(
        self,
        persistence: Optional[DocumentPersistenceService] = None,
        extraction: Optional[TextExtractionService] = None,
        analysis: Optional[ContractAnalysisOrchestrator] = None,
        storage: Optional[DocumentStorage] = None,
        intelligence: Optional[DocumentIntelligenceProvider] = None,
    ) -> None:
        self._storage = storage or DocumentStorage(settings.contracts_dir)
        self._persistence = persistence or DocumentPersistenceService(
            storage=self._storage
        )
        self._extraction = extraction or TextExtractionService()
        self._analysis = analysis
        # Lazy in production so importing the FastAPI app does not initialise a
        # heavyweight local DI stack. Tests inject a cheap deterministic provider.
        self._intelligence = intelligence

    # ------------------------------------------------------------------
    # Public production / controlled recovery entry points
    # ------------------------------------------------------------------

    def process(
        self,
        *,
        organization_slug: str,
        original_filename: str,
        content_type: str,
        content: bytes,
        as_of_date: Optional[date] = None,
    ) -> ProcessedDocument:
        """Processes one uploaded document end-to-end."""

        stored, organization_id, storage_key = self._persist_document(
            organization_slug, original_filename, content_type, content
        )
        if stored.status in {"rejected", "failed"}:
            return stored
        return self._finalize_visibility(
            self._process_stored(
                stored=stored,
                organization_id=organization_id,
                storage_key=storage_key,
                as_of=as_of_date or date.today(),
            ),
            organization_id,
        )

    def _finalize_visibility(self, result, organization_id) -> ProcessedDocument:
        """Stellt ausschließlich die normale Produkt-Sichtbarkeit sicher.

        Fehlt `contract_id` bei einem persistierten Analysefehler, wird ein
        Platzhalter-Vertrag sichergestellt, damit Quelle und Fehlerstatus in der
        UI sichtbar bleiben. Es gibt keinen Demo-/UAT-Sonderbestand.
        """
        if result.contract_id is None and result.document_version_id:
            try:
                with create_session() as session:
                    cid = self._ensure_placeholder_contract(
                        session=session,
                        organization_id=organization_id,
                        document_version_id=uuid.UUID(result.document_version_id),
                    )
                    session.commit()
                    result = self._copy_result(result, contract_id=str(cid))
            except Exception:
                logger.exception("Failed to ensure placeholder visibility")
                return result
        return result

    def resume_document(
        self,
        *,
        organization_slug: str,
        document_version_id: str,
        as_of_date: Optional[date] = None,
    ) -> ProcessedDocument:
        """Controlled resume by opaque DB version ID without re-uploading bytes."""

        try:
            version_id = uuid.UUID(str(document_version_id))
        except (TypeError, ValueError):
            return self._not_found_result()

        try:
            with create_session() as session:
                org = get_organization(session, organization_slug)
                if org is None:
                    return self._not_found_result()
                version = session.scalars(
                    select(DocumentVersion).where(
                        (DocumentVersion.id == version_id)
                        & (DocumentVersion.organization_id == org.id)
                    )
                ).first()
                if version is None:
                    return self._not_found_result()
                doc = session.scalars(
                    select(DocumentFile).where(
                        (DocumentFile.id == version.document_file_id)
                        & (DocumentFile.organization_id == org.id)
                    )
                ).first()
                if doc is None or not self._storage.exists_reference(
                    version.storage_key
                ):
                    return self._not_found_result()
                stored = ProcessedDocument(
                    document_id=str(doc.id),
                    document_version_id=str(version.id),
                    sha256=version.sha256,
                    original_filename=doc.original_filename,
                    status="duplicate",
                )
                organization_id = org.id
                storage_key = version.storage_key
        except Exception as exc:
            logger.exception("Failed to resolve document resume request")
            return ProcessedDocument(
                document_id="",
                document_version_id=str(document_version_id),
                sha256="",
                original_filename="",
                status="failed",
                message=_SAFE_PROCESSING_FAILURE,
                error=str(exc),
            )

        return self._finalize_visibility(
            self._process_stored(
                stored=stored,
                organization_id=organization_id,
                storage_key=storage_key,
                as_of=as_of_date or date.today(),
            ),
            organization_id,
        )

    def reanalyze_document(
        self,
        *,
        organization_slug: str,
        document_version_id: str,
        as_of_date: Optional[date] = None,
    ) -> ProcessedDocument:
        """Reanalysiert einen bereits akzeptierten Vertrag ohne Re-Upload.

        Import-Idempotenz und Retry-Semantik bleiben unverändert. Die neue Analyse
        wird erst nach vollständiger Persistenz atomar als Current State akzeptiert;
        bei Fehler bleibt die bisher akzeptierte Vertragswahrheit unverändert.
        """
        try:
            version_id = uuid.UUID(str(document_version_id))
        except (TypeError, ValueError):
            return self._not_found_result()

        try:
            with create_session() as session:
                org = get_organization(session, organization_slug)
                if org is None:
                    return self._not_found_result()
                version = session.scalars(
                    select(DocumentVersion).where(
                        (DocumentVersion.id == version_id)
                        & (DocumentVersion.organization_id == org.id)
                    )
                ).first()
                if version is None:
                    return self._not_found_result()
                doc = session.scalars(
                    select(DocumentFile).where(
                        (DocumentFile.id == version.document_file_id)
                        & (DocumentFile.organization_id == org.id)
                    )
                ).first()
                if doc is None or not self._storage.exists_reference(version.storage_key):
                    return self._not_found_result()
                contract = self._accepted_contract_for_version(session, org.id, version.id)
                if contract is None:
                    return ProcessedDocument(
                        document_id=str(doc.id),
                        document_version_id=str(version.id),
                        sha256=version.sha256,
                        original_filename=doc.original_filename,
                        status="failed",
                        message="Kein akzeptierter Vertrag für Reanalyse vorhanden.",
                    )
                stored = ProcessedDocument(
                    document_id=str(doc.id),
                    document_version_id=str(version.id),
                    sha256=version.sha256,
                    original_filename=doc.original_filename,
                    status="duplicate",
                    contract_id=str(contract.id),
                )
                organization_id = org.id
                storage_key = version.storage_key
                contract_id = contract.id
        except Exception as exc:
            logger.exception("Failed to resolve document reanalysis request")
            return ProcessedDocument(
                document_id="",
                document_version_id=str(document_version_id),
                sha256="",
                original_filename="",
                status="failed",
                message=_SAFE_PROCESSING_FAILURE,
                error=str(exc),
            )

        return self._finalize_visibility(
            self._process_stored(
                stored=stored,
                organization_id=organization_id,
                storage_key=storage_key,
                as_of=as_of_date or date.today(),
                reanalysis_contract_id=contract_id,
            ),
            organization_id,
        )

    def reconcile_legacy(
        self,
        *,
        organization_slug: str,
        document_ids: Optional[list[str]] = None,
        limit: Optional[int] = None,
        as_of_date: Optional[date] = None,
    ) -> list[ProcessedDocument]:
        """Imports selected legacy-manifest originals through this orchestrator.

        The historical manifest and original contract/benchmark bytes are only
        read. They are never rewritten, moved, or deleted.
        """

        records = self._storage.legacy_records(
            document_ids=document_ids, limit=limit
        )
        results: list[ProcessedDocument] = []
        for record in records:
            document_id = str(record.get("document_id") or "")
            resolved = self._storage.resolve_document(document_id)
            if resolved is None:
                results.append(
                    ProcessedDocument(
                        document_id=document_id,
                        document_version_id="",
                        sha256=str(record.get("sha256") or ""),
                        original_filename=str(
                            record.get("original_filename") or ""
                        ),
                        status="failed",
                        message="Legacy-Dokument nicht verfügbar.",
                    )
                )
                continue
            _extension, path = resolved
            try:
                content = path.read_bytes()
            except OSError as exc:
                logger.exception("Failed to read legacy document %s", document_id)
                results.append(
                    ProcessedDocument(
                        document_id=document_id,
                        document_version_id="",
                        sha256=str(record.get("sha256") or ""),
                        original_filename=str(
                            record.get("original_filename") or ""
                        ),
                        status="failed",
                        message="Legacy-Dokument nicht verfügbar.",
                        error=str(exc),
                    )
                )
                continue
            results.append(
                self.process(
                    organization_slug=organization_slug,
                    original_filename=str(
                        record.get("original_filename") or path.name
                    ),
                    content_type=str(record.get("mime_type") or ""),
                    content=content,
                    as_of_date=as_of_date,
                )
            )
        return results

    # ------------------------------------------------------------------
    # Import and claim
    # ------------------------------------------------------------------

    def _persist_document(
        self, organization_slug, original_filename, content_type, content
    ):
        try:
            with create_session() as session:
                org = get_organization(session, organization_slug)
                if org is None:
                    return (
                        ProcessedDocument(
                            document_id="",
                            document_version_id="",
                            sha256="",
                            original_filename=original_filename,
                            status="rejected",
                            message="Organisation nicht gefunden.",
                        ),
                        None,
                        None,
                    )
                try:
                    persisted = self._persistence.store_original(
                        session,
                        organization_id=org.id,
                        original_filename=original_filename,
                        content_type=content_type,
                        content=content,
                    )
                    session.commit()
                except StorageError as exc:
                    session.rollback()
                    return (
                        ProcessedDocument(
                            document_id="",
                            document_version_id="",
                            sha256="",
                            original_filename=original_filename,
                            status="rejected",
                            message=str(exc),
                        ),
                        None,
                        None,
                    )
                status = "duplicate" if persisted.duplicate else "imported"
                return (
                    ProcessedDocument(
                        document_id=str(persisted.document_file_id),
                        document_version_id=str(persisted.document_version_id),
                        sha256=persisted.sha256,
                        original_filename=persisted.original_filename,
                        status=status,
                    ),
                    org.id,
                    persisted.storage_key,
                )
        except Exception as exc:
            logger.exception("Document import persistence failed")
            return (
                ProcessedDocument(
                    document_id="",
                    document_version_id="",
                    sha256="",
                    original_filename=original_filename,
                    status="failed",
                    message=_SAFE_PROCESSING_FAILURE,
                    error=str(exc),
                ),
                None,
                None,
            )

    def _process_stored(
        self,
        *,
        stored: ProcessedDocument,
        organization_id,
        storage_key: str,
        as_of: date,
        reanalysis_contract_id=None,
    ) -> ProcessedDocument:
        completed, run_id, expected_accepted_extraction_id = self._claim_processing(
            stored, organization_id, reanalysis_contract_id=reanalysis_contract_id
        )
        if completed is not None:
            return completed
        assert run_id is not None

        canonical: Optional[DocumentIntelligenceResult] = None
        canonical_artifact_id = None
        try:
            path = self._storage.safe_path(storage_key)
            cached = self._load_cached_canonical(stored, organization_id)
            if cached is not None:
                canonical, canonical_artifact_id = cached
                extraction = self._canonical_to_extraction(canonical)
            else:
                canonical, extraction = self._build_canonical(stored, path)
                canonical_artifact_id = self._persist_canonical_artifact(
                    stored=stored,
                    organization_id=organization_id,
                    run_id=run_id,
                    canonical=canonical,
                )

            # Text is sufficient for both engines, but it is NOT a prerequisite
            # for the production V3 visual path. A scanned PDF can legitimately
            # contain zero OCR/native text while still having trustworthy source
            # pages that Qwen-VL can read locally. Legacy/injected analyzers and
            # non-visual inputs still fail closed when no text units exist.
            selected_engine = str(settings.harness_engine or "").strip().lower()
            visual_only_pdf = (
                self._analysis is None
                and selected_engine not in {"v2-compat", "legacy-v2"}
                and Path(canonical.source_filename or "").suffix.lower() == ".pdf"
                and bool(canonical.pages)
            )
            if (
                (not extraction.text_available or not extraction.units)
                and not visual_only_pdf
            ):
                placeholder_id = self._persist_failed_analysis(
                    stored=stored,
                    organization_id=organization_id,
                    run_id=run_id,
                    canonical=canonical,
                    canonical_artifact_id=canonical_artifact_id,
                    analysis=None,
                    message=_SAFE_NO_TEXT,
                    error=extraction.error,
                    reanalysis_contract_id=reanalysis_contract_id,
                )
                return self._copy_result(
                    stored,
                    status="analysis_failed",
                    analysis_status="failed",
                    requires_review=True,
                    contract_id=str(placeholder_id),
                    message=_SAFE_NO_TEXT,
                    error=extraction.error,
                    warnings=extraction.warnings,
                )

            if self._analysis is not None:
                analysis = asyncio.run(self._analysis.analyze(extraction))
            else:
                from app.ai.harness import get_harness_class
                from app.documents.intelligence.hybrid_runtime import HybridVisionRuntime

                harness_cls = get_harness_class(settings)
                using_v3 = harness_cls.__name__ == "HarnessV3"
                hybrid_runtime = (
                    HybridVisionRuntime(
                        path,
                        canonical,
                        longest_side=settings.harness_vision_batch_scale,
                    )
                    if using_v3 and getattr(settings, "hybrid_scanned_contracts_enabled", True)
                    else None
                )
                analysis = asyncio.run(harness_cls(settings).analyze(
                    canonical,
                    image_loader=(
                        hybrid_runtime.render_region
                        if hybrid_runtime is not None
                        else None
                    ),
                    page_image_loader=(
                        hybrid_runtime.render_page
                        if hybrid_runtime is not None
                        else None
                    ),
                ))
            if analysis.contract is None:
                placeholder_id = self._persist_failed_analysis(
                    stored=stored,
                    organization_id=organization_id,
                    run_id=run_id,
                    canonical=canonical,
                    canonical_artifact_id=canonical_artifact_id,
                    analysis=analysis,
                    message=_map_failure_message(analysis),
                    error=analysis.error,
                    reanalysis_contract_id=reanalysis_contract_id,
                )
                return self._copy_result(
                    stored,
                    status="analysis_failed",
                    analysis_status=analysis.status.value,
                    requires_review=True,
                    contract_id=str(placeholder_id),
                    message=_map_failure_message(analysis),
                    error=analysis.error,
                )

            contract_model = analysis.contract
            # Deterministic code remains authoritative for dates, money, status,
            # review state, and warnings. AI only supplied source-grounded facts.
            calc_result = calculate_contract(contract_model, as_of_date=as_of)
            warn_result = evaluate_contract_warnings(
                contract_model, calc_result, WarningPolicy.default()
            )
            contract, created = self._persist_pipeline(
                stored=stored,
                organization_id=organization_id,
                run_id=run_id,
                canonical=canonical,
                canonical_artifact_id=canonical_artifact_id,
                contract_model=contract_model,
                analysis=analysis,
                calc_result=calc_result,
                warn_result=warn_result,
                as_of=as_of,
                reanalysis_contract_id=reanalysis_contract_id,
                expected_accepted_extraction_id=expected_accepted_extraction_id,
            )
            return self._copy_result(
                stored,
                status=(
                    "reanalyzed"
                    if reanalysis_contract_id is not None
                    else ("imported" if created else "duplicate")
                ),
                analysis_status=(
                    "success" if not analysis.requires_review else "partial"
                ),
                requires_review=bool(
                    analysis.requires_review
                    or calc_result.overall_review_required
                ),
                contract_id=str(contract.id),
                message=(
                    "Dokument erfolgreich neu analysiert."
                    if reanalysis_contract_id is not None
                    else (
                        "Dokument erfolgreich verarbeitet."
                        if created
                        else "Dokument wurde bereits vollständig verarbeitet."
                    )
                ),
                warnings=[item.title_de for item in warn_result.warnings[:8]],
            )
        except Exception as exc:
            logger.exception(
                "Document processing failed for version %s",
                stored.document_version_id,
            )
            placeholder_id = None
            try:
                self._finalize_run(
                    stored=stored,
                    organization_id=organization_id,
                    run_id=run_id,
                    status="failed",
                    canonical=canonical,
                    canonical_artifact_id=canonical_artifact_id,
                    success=False,
                    message=_SAFE_PROCESSING_FAILURE,
                    error=_sanitized_error(str(exc)),
                )
                if reanalysis_contract_id is not None:
                    placeholder_id = reanalysis_contract_id
                else:
                    try:
                        with create_session() as session:
                            placeholder_id = self._ensure_placeholder_contract(
                                session=session,
                                organization_id=organization_id,
                                document_version_id=uuid.UUID(stored.document_version_id),
                            )
                            session.commit()
                    except Exception:
                        logger.exception("Failed to create placeholder contract")
            except Exception:
                logger.exception("Failed to persist processing failure state")
            return self._copy_result(
                stored,
                status="failed",
                contract_id=str(placeholder_id) if placeholder_id else None,
                message=_SAFE_PROCESSING_FAILURE,
                error=str(exc),
            )

    def _claim_processing(self, stored, organization_id, *, reanalysis_contract_id=None):
        version_id = uuid.UUID(stored.document_version_id)
        with create_session() as session:
            version = session.scalars(
                select(DocumentVersion)
                .where(
                    (DocumentVersion.id == version_id)
                    & (DocumentVersion.organization_id == organization_id)
                )
                .with_for_update()
            ).first()
            if version is None:
                raise RuntimeError("document version not found")

            existing_contract = self._accepted_contract_for_version(
                session, organization_id, version.id
            )
            expected_accepted_extraction_id = None
            if reanalysis_contract_id is None and existing_contract is not None:
                session.commit()
                return (
                    self._copy_result(
                        stored,
                        status="duplicate",
                        analysis_status="success",
                        contract_id=str(existing_contract.id),
                        message="Dokument wurde bereits vollständig verarbeitet.",
                    ),
                    None,
                    None,
                )
            if reanalysis_contract_id is not None:
                if existing_contract is None or existing_contract.id != reanalysis_contract_id:
                    raise RuntimeError("accepted contract for reanalysis not found")
                expected_accepted_extraction_id = existing_contract.accepted_extraction_id

            latest = session.scalars(
                select(ProcessingRun)
                .where(
                    (ProcessingRun.document_version_id == version.id)
                    & (ProcessingRun.organization_id == organization_id)
                )
                .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
            ).first()
            if latest is not None and latest.status == "running" and self._run_is_fresh(
                latest
            ):
                session.commit()
                return (
                    self._copy_result(
                        stored,
                        status="duplicate",
                        analysis_status="processing",
                        message="Dokument wird bereits verarbeitet.",
                    ),
                    None,
                    None,
                )

            provider_name = (
                "python-docx"
                if version.storage_key.lower().endswith(".docx")
                else getattr(
                    self._intelligence,
                    "name",
                    settings.document_intelligence_provider,
                )
            )
            run = create_processing_run(
                session,
                organization_id=organization_id,
                document_version_id=version.id,
                status="running",
                schema_version=CANONICAL_SCHEMA_VERSION,
                provider=provider_name,
                do_ocr=(
                    settings.ocr_enabled
                    if version.storage_key.lower().endswith(".pdf")
                    else False
                ),
                do_table_structure=settings.document_intelligence_table_structure,
            )
            run_id = run.id
            session.commit()
            return None, run_id, expected_accepted_extraction_id

    @staticmethod
    def _accepted_contract_for_version(session, organization_id, version_id):
        return session.scalars(
            select(Contract)
            .join(ContractDocument, ContractDocument.contract_id == Contract.id)
            .where(
                (Contract.organization_id == organization_id)
                & (ContractDocument.organization_id == organization_id)
                & (ContractDocument.document_version_id == version_id)
                & (Contract.lifecycle_state == "active")
                & (Contract.accepted_extraction_id.is_not(None))
                & (Contract.accepted_calculation_run_id.is_not(None))
            )
            .order_by(Contract.created_at.asc(), Contract.id.asc())
        ).first()

    @staticmethod
    def _run_is_fresh(run: ProcessingRun) -> bool:
        created_at = run.created_at
        if created_at is None:
            return True
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        stale_after = timedelta(
            minutes=max(1, settings.document_processing_stale_minutes)
        )
        return datetime.now(timezone.utc) - created_at < stale_after

    # ------------------------------------------------------------------
    # Canonical Document Intelligence and protected artifact persistence
    # ------------------------------------------------------------------

    def _build_canonical(self, stored, path: Path):
        extension = path.suffix.lower()
        if extension == ".docx":
            extraction = self._extraction.extract_from_path(
                stored.document_id, extension, path
            )
            if extraction is None:
                extraction = TextExtractionResult(
                    document_id=stored.document_id,
                    file_type=FileType.DOCX,
                    extraction_status=ExtractionStatus.FAILED,
                    page_count=0,
                    total_characters=0,
                    text_available=False,
                    error="DOCX extraction returned no result",
                )
            canonical = self._canonical_from_docx(stored, extraction)
            return canonical, extraction

        if extension != ".pdf":
            raise StorageError("Dateityp nicht unterstützt")
        provider = self._intelligence or get_provider(
            settings.document_intelligence_provider
        )
        intelligence_settings = DocumentIntelligenceSettings(
            do_ocr=settings.ocr_enabled,
            do_table_structure=settings.document_intelligence_table_structure,
            ocr_lang=[settings.ocr_lang],
            device=settings.document_intelligence_device,
        )

        # Image-only PDFs still need a canonical OCR/layout layer.  Harness V3
        # may use the selected vision model as a second perception source, but
        # downstream grounding requires stable page/block text.  Do not bypass
        # Docling merely because the PDF has no embedded text.
        canonical = None

        try:
            canonical = provider.process(path, intelligence_settings)
        except Exception as exc:
            # If the local environment explicitly requested CUDA for Docling but
            # its Python inference stack has no CUDA backend, retry Docling once
            # with automatic accelerator selection.  This keeps the OCR/layout
            # evidence layer instead of silently collapsing a scanned contract
            # to image-only native PDF pages.  Ollama GPU offload is independent.
            canonical = None
            if (
                getattr(provider, "name", "") == "docling"
                and intelligence_settings.device == "cuda"
            ):
                try:
                    retry_settings = intelligence_settings.model_copy(
                        update={"device": "auto"}
                    )
                    canonical = provider.process(path, retry_settings)
                    canonical.warnings.append(
                        "Docling-CUDA lokal nicht verfügbar; OCR/Layout mit "
                        "automatischer Beschleunigerwahl erneut ausgeführt."
                    )
                    logger.warning(
                        "Docling CUDA failed; OCR/layout succeeded with device=auto "
                        "(original_type=%s)",
                        type(exc).__name__,
                    )
                except Exception as retry_exc:
                    logger.warning(
                        "Docling CUDA and auto retry failed; using native PDF/Vision "
                        "fallback (cuda_type=%s auto_type=%s)",
                        type(exc).__name__,
                        type(retry_exc).__name__,
                    )
            if canonical is None:
                # OCR/layout intelligence is an enhancement layer, not a single
                # point of failure for PDF vision. Fall back to local PyMuPDF page
                # discovery only after the Docling retry path has been exhausted.
                if getattr(provider, "name", "") == "native_pdf":
                    raise
                logger.warning(
                    "Primary document intelligence failed; using native PDF/Vision fallback (type=%s)",
                    type(exc).__name__,
                )
                fallback = get_provider("native_pdf")
                fallback_settings = intelligence_settings.model_copy(update={
                    "do_ocr": False,
                    "do_table_structure": False,
                    "structural_roles": False,
                })
                canonical = fallback.process(path, fallback_settings)
                canonical.warnings.append(
                    "Primärer Dokument-Intelligence-Provider fehlgeschlagen; "
                    "nativer PDF-/Vision-Fallback verwendet."
                )
        if canonical.source_sha256 != stored.sha256:
            raise RuntimeError("canonical source hash mismatch")
        # Atomic OCR/geometry (RapidOCR) is a perception/evidence helper only.
        # It must never become a mandatory semantic gateway: failure falls back
        # to canonical visual evidence without blocking analysis.
        if settings.document_intelligence_atomic_geometry and canonical.pages:
            try:
                from app.documents.intelligence.atomic_ocr import augment_with_atomic_geometry
                canonical, _ = augment_with_atomic_geometry(
                    canonical, path, dpi=settings.document_intelligence_atomic_geometry_dpi
                )
            except Exception as exc:  # pragma: no cover - defensive perception fallback
                logger.warning("atomic geometry perception failed: %s", type(exc).__name__)
        canonical = canonical.model_copy(
            update={
                "document_id": stored.document_id,
                "source_filename": stored.original_filename,
                # Artifact provenance is DB/storage-key bound; do not persist a
                # machine-specific absolute source path unnecessarily.
                "source_path": None,
            }
        )
        return canonical, self._canonical_to_extraction(canonical)

    @staticmethod
    def _canonical_from_docx(stored, extraction):
        logical_units = [
            LogicalUnit(
                source_type=unit.source_type.value,
                index=unit.index,
                text=unit.text,
                method=(Method.OCR if unit.method == UnitMethod.OCR else Method.NATIVE),
            )
            for unit in extraction.units
            if unit.source_type in {SourceType.PARAGRAPH, SourceType.TABLE}
        ]
        try:
            provider_version = metadata.version("python-docx")
        except metadata.PackageNotFoundError:
            provider_version = None
        canonical_text = "\n\n".join(unit.text for unit in logical_units)
        return DocumentIntelligenceResult(
            document_id=stored.document_id,
            source_sha256=stored.sha256,
            source_filename=stored.original_filename,
            source_path=None,
            canonical_text=canonical_text,
            pages_text=[],
            pages=[],
            logical_units=logical_units,
            provenance=ProcessingProvenance(
                provider="python-docx",
                provider_version=provider_version,
                method=Method.NATIVE,
                do_ocr=False,
                do_table_structure=True,
                geometry_provider=None,
                config={"source_addressing": "paragraph_table_indices"},
            ),
            warnings=list(extraction.warnings),
            processing_time_s=0.0,
        )

    @staticmethod
    def _canonical_to_extraction(canonical: DocumentIntelligenceResult):
        # Source structure and source file type are independent. PDFs produced
        # by Document Intelligence may legitimately contain logical units, so
        # logical_units must never be used as a DOCX detector.
        source_suffix = Path(canonical.source_filename or "").suffix.lower()
        file_type = FileType.DOCX if source_suffix == ".docx" else FileType.PDF

        if canonical.logical_units:
            units = [
                ExtractionUnit(
                    source_type=SourceType(unit.source_type),
                    index=unit.index,
                    text=unit.text,
                    method=(
                        UnitMethod.OCR
                        if unit.method == Method.OCR
                        else UnitMethod.TEXT
                    ),
                )
                for unit in canonical.logical_units
                if unit.text and unit.text.strip()
            ]
        else:
            units = [
                DocumentProcessingService._page_to_extraction_unit(page)
                for page in canonical.pages
                if page.text and page.text.strip()
            ]

        # The canonical text convenience field is not the source of truth for
        # analyzability. Providers can supply page/logical-unit text even when
        # canonical_text is empty; use the actual units consumed by analyzers.
        total_characters = sum(len(unit.text) for unit in units)
        text_available = bool(units and total_characters > 0)
        method = (
            UnitMethod.OCR
            if any(unit.method == UnitMethod.OCR for unit in units)
            else UnitMethod.TEXT
        )
        return TextExtractionResult(
            document_id=canonical.document_id or "",
            file_type=file_type,
            extraction_status=(
                ExtractionStatus.SUCCESS
                if text_available
                else ExtractionStatus.FAILED
            ),
            extraction_method=method,
            page_count=len(canonical.pages),
            total_characters=total_characters,
            text_available=text_available,
            requires_ocr=bool(canonical.provenance.do_ocr),
            units=units,
            warnings=list(canonical.warnings),
        )

    @staticmethod
    def _page_to_extraction_unit(page):
        boxes: list[SourceBox] = []
        confidences: list[float] = []
        for atomic in page.atomic_units:
            boxes.append(
                SourceBox(
                    page=page.page_number,
                    x0=atomic.bbox.x0,
                    y0=atomic.bbox.y0,
                    x1=atomic.bbox.x1,
                    y1=atomic.bbox.y1,
                    text=atomic.text,
                    confidence=atomic.confidence,
                )
            )
            if atomic.confidence is not None:
                confidences.append(atomic.confidence)
        if not boxes:
            for element in page.elements:
                for word in element.word_regions:
                    boxes.append(
                        SourceBox(
                            page=page.page_number,
                            x0=word.region.x0,
                            y0=word.region.y0,
                            x1=word.region.x1,
                            y1=word.region.y1,
                            text=word.text,
                        )
                    )

        regions = [element.region for element in page.elements if element.region]
        bbox = None
        if regions:
            bbox = SourceBox(
                page=page.page_number,
                x0=min(region.x0 for region in regions),
                y0=min(region.y0 for region in regions),
                x1=max(region.x1 for region in regions),
                y1=max(region.y1 for region in regions),
                text=page.text,
            )
        is_ocr = bool(
            page.atomic_units
            or any(element.method == Method.OCR for element in page.elements)
        )
        return ExtractionUnit(
            source_type=SourceType.PAGE,
            index=page.page_number,
            text=page.text,
            method=UnitMethod.OCR if is_ocr else UnitMethod.TEXT,
            bbox=bbox,
            boxes=boxes,
            ocr_confidence=(
                sum(confidences) / len(confidences) if confidences else None
            ),
        )

    def _load_cached_canonical(self, stored, organization_id):
        version_id = uuid.UUID(stored.document_version_id)
        with create_session() as session:
            artifacts = session.scalars(
                select(DocumentArtifact)
                .join(
                    ProcessingRun,
                    DocumentArtifact.processing_run_id == ProcessingRun.id,
                )
                .where(
                    (DocumentArtifact.organization_id == organization_id)
                    & (DocumentArtifact.document_version_id == version_id)
                    & (DocumentArtifact.artifact_type == "canonical")
                    & (DocumentArtifact.lifecycle_state == "active")
                )
                .order_by(ProcessingRun.created_at.desc(), ProcessingRun.id.desc())
            ).all()
            candidates = [
                (artifact.id, artifact.storage_key, artifact.sha256)
                for artifact in artifacts
            ]

        for artifact_id, storage_key, expected_sha in candidates:
            try:
                payload = self._storage.read_reference(storage_key)
                if hashlib.sha256(payload).hexdigest() != expected_sha:
                    logger.warning("Ignoring canonical artifact with hash mismatch")
                    continue
                canonical = DocumentIntelligenceResult.model_validate_json(payload)
                if canonical.source_sha256 != stored.sha256:
                    logger.warning("Ignoring canonical artifact for different source")
                    continue
                return canonical, artifact_id
            except Exception:
                logger.exception("Ignoring unreadable canonical artifact")
        return None

    def _persist_canonical_artifact(
        self, *, stored, organization_id, run_id, canonical
    ):
        payload = canonical.model_dump_json(
            exclude_none=True, by_alias=True
        ).encode("utf-8")
        artifact = None
        with create_session() as session:
            try:
                artifact = self._persistence.store_canonical_artifact(
                    session,
                    organization_id=organization_id,
                    document_version_id=uuid.UUID(stored.document_version_id),
                    processing_run_id=run_id,
                    content=payload,
                    format_version=(
                        canonical.provenance.canonical_schema_version
                        or CANONICAL_SCHEMA_VERSION
                    ),
                )
                artifact_id = artifact.id
                session.commit()
                return artifact_id
            except Exception:
                session.rollback()
                if artifact is not None:
                    self._storage.delete_reference(artifact.storage_key)
                raise

    # ------------------------------------------------------------------
    # Persistence of failed/full processing outcomes
    # ------------------------------------------------------------------

    def _persist_failed_analysis(
        self,
        *,
        stored,
        organization_id,
        run_id,
        canonical,
        canonical_artifact_id,
        analysis,
        message,
        error,
        reanalysis_contract_id=None,
    ):
        if analysis is not None and getattr(analysis, "diagnostics", None):
            failed_calls = [
                row
                for row in analysis.diagnostics.get("calls", [])
                if isinstance(row, dict) and row.get("failed")
            ]
            last_failure = failed_calls[-1] if failed_calls else {}
            logger.warning(
                "Harness analysis not accepted for version %s "
                "(calls=%s failures=%s purpose=%s category=%s type=%s done_reason=%s)",
                stored.document_version_id,
                analysis.diagnostics.get("call_count"),
                analysis.diagnostics.get("failure_count"),
                last_failure.get("purpose"),
                last_failure.get("error_category"),
                last_failure.get("error_type"),
                last_failure.get("done_reason"),
            )
        with create_session() as session:
            save_extraction(
                session,
                organization_id=organization_id,
                document_version_id=uuid.UUID(stored.document_version_id),
                snapshot=None,
                evidence=[],
                status=(
                    analysis.status.value
                    if analysis is not None
                    else ExtractionStatus.FAILED.value
                ),
                validation_status=(
                    analysis.validation_status.value
                    if analysis is not None
                    else ValidationStatus.UNKNOWN.value
                ),
                requires_review=True,
                model=analysis.model if analysis is not None else None,
                prompt_version=(
                    analysis.prompt_version if analysis is not None else None
                ),
                message=message,
                error=_sanitized_error(error),
                **self._analysis_diagnostics(analysis),
            )
            placeholder_id = (
                reanalysis_contract_id
                if reanalysis_contract_id is not None
                else self._ensure_placeholder_contract(
                    session=session,
                    organization_id=organization_id,
                    document_version_id=uuid.UUID(stored.document_version_id),
                )
            )
            self._finish_run_in_session(
                session=session,
                stored=stored,
                organization_id=organization_id,
                run_id=run_id,
                status="partial" if canonical is not None else "failed",
                canonical=canonical,
                canonical_artifact_id=canonical_artifact_id,
                success=False,
                message=message,
                error=_sanitized_error(error),
            )
            session.commit()
            return placeholder_id

    def _ensure_placeholder_contract(self, *, session, organization_id, document_version_id):
        """Failure-safe: Platzhalter-Vertrag, damit das Dokument SICHTBAR bleibt.

        Der Platzhalter ist ein aktiver Draft OHNE akzeptierte Analyse. Er wird
        erzeugt, damit die Quell-Dokumente und die Fehler-Lage in der UI
        zugänglich sind. Ein erfolgreicher Retry erzeugt den echten Vertrag und
        verwaist den Platzhalter (`lifecycle_state='orphan'`).
        """
        existing = session.scalars(
            select(Contract)
            .join(ContractDocument, ContractDocument.contract_id == Contract.id)
            .where(
                (Contract.organization_id == organization_id)
                & (ContractDocument.document_version_id == document_version_id)
                & (Contract.accepted_extraction_id.is_(None))
            )
            .order_by(Contract.created_at.asc(), Contract.id.asc())
        ).first()
        if existing is not None:
            return existing.id
        placeholder = create_contract(
            session,
            organization_id=organization_id,
            status="draft",
        )
        link_document(
            session,
            contract_id=placeholder.id,
            document_version_id=document_version_id,
            role="main",
        )
        session.flush()
        return placeholder.id

    def _persist_pipeline(
        self,
        *,
        stored,
        organization_id,
        run_id,
        canonical,
        canonical_artifact_id,
        contract_model,
        analysis,
        calc_result,
        warn_result,
        as_of,
        reanalysis_contract_id=None,
        expected_accepted_extraction_id=None,
    ):
        with create_session() as session:
            version_id = uuid.UUID(stored.document_version_id)
            version = session.scalars(
                select(DocumentVersion)
                .where(
                    (DocumentVersion.id == version_id)
                    & (DocumentVersion.organization_id == organization_id)
                )
                .with_for_update()
            ).first()
            if version is None:
                raise RuntimeError("document version not found")

            # Last-line race protection. Normal import remains idempotent.
            # Reanalysis instead locks the SAME accepted Contract and verifies
            # that its accepted extraction still matches the state seen at claim
            # time; a stale worker can therefore never overwrite newer truth.
            if reanalysis_contract_id is None:
                existing = self._accepted_contract_for_version(
                    session, organization_id, version.id
                )
                if existing is not None:
                    self._finish_run_in_session(
                        session=session,
                        stored=stored,
                        organization_id=organization_id,
                        run_id=run_id,
                        status="succeeded",
                        canonical=canonical,
                        canonical_artifact_id=canonical_artifact_id,
                        success=True,
                    )
                    session.commit()
                    return existing, False
                contract = None
            else:
                contract = session.scalars(
                    select(Contract)
                    .where(
                        (Contract.id == reanalysis_contract_id)
                        & (Contract.organization_id == organization_id)
                        & (Contract.lifecycle_state == "active")
                    )
                    .with_for_update()
                ).first()
                if contract is None:
                    raise RuntimeError("reanalysis contract not found")
                linked = session.scalars(
                    select(ContractDocument).where(
                        (ContractDocument.contract_id == contract.id)
                        & (ContractDocument.organization_id == organization_id)
                        & (ContractDocument.document_version_id == version.id)
                    )
                ).first()
                if linked is None:
                    raise RuntimeError("reanalysis contract/document link not found")
                if contract.accepted_extraction_id != expected_accepted_extraction_id:
                    raise RuntimeError("reanalysis superseded by newer accepted state")
                if contract.accepted_extraction_id is None or contract.accepted_calculation_run_id is None:
                    raise RuntimeError("reanalysis requires an accepted contract")

            snapshot, evidence = self._build_extraction(contract_model)
            extraction = save_extraction(
                session,
                organization_id=organization_id,
                document_version_id=version.id,
                snapshot=snapshot,
                evidence=evidence,
                status=analysis.status.value,
                validation_status=analysis.validation_status.value,
                requires_review=analysis.requires_review,
                model=analysis.model,
                prompt_version=analysis.prompt_version,
                message=analysis.message or None,
                error=analysis.error or None,
                **self._analysis_diagnostics(analysis),
            )

            calc_snapshot = calc_result.model_dump(mode="json")
            calculation = save_calculation(
                session,
                organization_id=organization_id,
                extraction_id=extraction.id,
                as_of_date=as_of,
                result_snapshot=calc_snapshot,
                calculation_version=CALC_VERSION,
                status="computed",
                overall_review_required=bool(
                    calc_result.overall_review_required
                ),
                result_rows=self._calculation_result_rows(calc_snapshot),
                review_flags=self._calculation_review_flags(calc_snapshot),
            )

            # Current-State projection must use resolved party roles and the
            # deterministic STEP-9 status, not the model's default UNKNOWN value.
            projected_supplier = _projected_supplier(contract_model.identity)
            calculated_status = getattr(
                getattr(calc_result.dates, "current_contract_status", None), "status", None
            )
            calculated_status_value = getattr(calculated_status, "value", calculated_status)
            projected_status = (
                calculated_status_value
                if calculated_status_value and str(calculated_status_value).lower() != "unknown"
                else (contract_model.status.value if contract_model.status else None)
            )

            created = contract is None
            if contract is None:
                contract = create_contract(
                    session,
                    organization_id=organization_id,
                    supplier=projected_supplier,
                    contract_number=contract_model.identity.contract_number,
                    status=projected_status,
                    risk_level=(
                        contract_model.review.risk_level.value
                        if contract_model.review
                        else None
                    ),
                )
            project_contract(
                session,
                contract=contract,
                supplier=projected_supplier,
                contract_number=contract_model.identity.contract_number,
                start_date=_flexible_date(contract_model.dates.start_date),
                end_date=_flexible_date(contract_model.dates.end_date),
                status=projected_status,
                risk_level=(
                    contract_model.review.risk_level.value
                    if contract_model.review
                    else None
                ),
                replace_missing=reanalysis_contract_id is not None,
            )
            link_document(
                session,
                contract_id=contract.id,
                document_version_id=version.id,
                role="main",
            )
            # Only persisted, navigable evidence can upgrade relationship
            # quality. An in-memory evidence object may lack a source locator
            # and be discarded by _evidence_row above.
            persisted_equipment_refs = {
                row["field_ref"] for row in evidence
                if row.get("field_ref", "").startswith("identity_equipment.evidence.")
            }
            for index, equipment in enumerate(contract_model.equipment or []):
                add_equipment(
                    session,
                    contract_id=contract.id,
                    extraction_id=extraction.id,
                    device_name=equipment.device_name,
                    manufacturer=equipment.manufacturer,
                    model=equipment.model,
                    serial_number=equipment.serial_number,
                    inventory_number=equipment.inventory_number,
                    system_name=equipment.system_name,
                    equipment_category=equipment.equipment_category,
                    equipment_type=equipment.equipment_type,
                    location=equipment.location,
                    department=equipment.department,
                    service_scope=equipment.service_scope,
                    coverage_start=(
                        _flexible_date(equipment.coverage_start)
                        if equipment.coverage_start is not None else None
                    ),
                    coverage_end=(
                        _flexible_date(equipment.coverage_end)
                        if equipment.coverage_end is not None else None
                    ),
                    included_services=equipment.included_services or [],
                    excluded_services=equipment.excluded_services or [],
                    sla_notes=equipment.sla_notes,
                    field_ref=f"identity_equipment.evidence.{index}",
                    equipment_index=index,
                    has_evidence=f"identity_equipment.evidence.{index}" in persisted_equipment_refs,
                )
            accept_extraction(
                session, contract_id=contract.id, extraction_id=extraction.id
            )
            accept_calculation(
                session,
                contract_id=contract.id,
                calculation_run_id=calculation.id,
            )
            run_warning_evaluation(
                session,
                organization_id=organization_id,
                contract_id=contract.id,
                calculation_run_id=calculation.id,
                as_of_date=as_of,
                policy_version=DEFAULT_POLICY_VERSION,
                result=warn_result,
                status="computed",
            )
            # PR-4: Arbeitsliste deterministisch aus den autoritativen Quellen
            # (aktive Warnungen + Geräte-Review) materialisieren (idempotent).
            active_warnings = list(
                session.scalars(
                    select(ContractWarning).where(
                        (ContractWarning.organization_id == organization_id)
                        & (ContractWarning.contract_id == contract.id)
                        & (ContractWarning.active.is_(True))
                    )
                )
            )
            equipment_rows = list(
                session.scalars(
                    select(ContractEquipment).where(
                        (ContractEquipment.organization_id == organization_id)
                        & (ContractEquipment.contract_id == contract.id)
                        & (ContractEquipment.extraction_id == extraction.id)
                    )
                )
            )
            derived = derive_work_items(
                contract_id=str(contract.id),
                warnings=active_warnings,
                equipment_rows=equipment_rows,
                as_of_date=as_of,
                policy_version=DEFAULT_POLICY_VERSION,
            )
            reconcile_work_items(
                session,
                organization_id=organization_id,
                contract_id=contract.id,
                derived=derived,
            )
            self._orphan_placeholders(
                session=session,
                organization_id=organization_id,
                version_id=version.id,
            )
            self._finish_run_in_session(
                session=session,
                stored=stored,
                organization_id=organization_id,
                run_id=run_id,
                status="succeeded",
                canonical=canonical,
                canonical_artifact_id=canonical_artifact_id,
                success=True,
            )
            session.commit()
            return contract, created

    def _orphan_placeholders(self, *, session, organization_id, version_id) -> None:
        """Erfolgreicher Lauf: frühere Platzhalter dieses Versions werden verwaist.

        Lebenszyklus-Platzhalter (Draft, ohne akzeptierte Analyse) sind nach
        einem erfolgreichen Retry im Portfolio irrelevant und werden von der
        Basis-Prädikaten/Dashboard-Abfrage ausgeblendet (`lifecycle_state`).
        """
        session.execute(
            update(Contract)
            .where(
                Contract.id.in_(
                    select(ContractDocument.contract_id).where(
                        (ContractDocument.organization_id == organization_id)
                        & (ContractDocument.document_version_id == version_id)
                    )
                )
                & (Contract.accepted_extraction_id.is_(None))
                & (Contract.lifecycle_state == "active")
            )
            .values(lifecycle_state="orphan")
        )

    def _finalize_run(
        self,
        *,
        stored,
        organization_id,
        run_id,
        status,
        canonical,
        canonical_artifact_id,
        success,
        message=None,
        error=None,
    ):
        with create_session() as session:
            self._finish_run_in_session(
                session=session,
                stored=stored,
                organization_id=organization_id,
                run_id=run_id,
                status=status,
                canonical=canonical,
                canonical_artifact_id=canonical_artifact_id,
                success=success,
                message=message,
                error=error,
            )
            session.commit()

    @staticmethod
    def _finish_run_in_session(
        *,
        session,
        stored,
        organization_id,
        run_id,
        status,
        canonical,
        canonical_artifact_id,
        success,
        message=None,
        error=None,
    ):
        provenance = canonical.provenance if canonical is not None else None
        finish_processing_run(
            session,
            run_id=run_id,
            status=status,
            processing_duration=(
                canonical.processing_time_s if canonical is not None else None
            ),
            canonical_artifact_id=canonical_artifact_id,
            provider=provenance.provider if provenance else None,
            provider_version=provenance.provider_version if provenance else None,
            do_ocr=provenance.do_ocr if provenance else None,
            do_table_structure=(
                provenance.do_table_structure if provenance else None
            ),
            geometry_provider=(
                provenance.geometry_provider if provenance else None
            ),
            message=message,
            error=error,
        )
        upsert_processing_summary(
            session,
            organization_id=organization_id,
            document_version_id=uuid.UUID(stored.document_version_id),
            file_key=stored.sha256,
            page_count=len(canonical.pages) if canonical is not None else 0,
            doc_type=(
                "docx"
                if (
                    canonical is not None
                    and Path(canonical.source_filename or "").suffix.lower() == ".docx"
                )
                else "pdf"
            ),
            processed_at=datetime.now(timezone.utc),
            success=1 if success else 0,
            failure=0 if success else 1,
            last_success_run_id=run_id if success else None,
        )

    @staticmethod
    def _analysis_diagnostics(analysis):
        if analysis is None:
            return {
                # NULL means "not applicable / analysis never started".  Zero used
                # to be misleading because production Harness runs do not use the
                # legacy chunk pipeline at all.
                "chunk_count": None,
                "processing_duration": 0.0,
                "timeout_count": 0,
                "retry_count": 0,
                "truncated_chunks": None,
                "ai_call_count": 0,
                "groups_processed": 0,
                "evidence_issues": 0,
                "verifier_issues": 0,
                "normalization_issues": 0,
            }
        is_harness = str(getattr(analysis, "prompt_version", "") or "").startswith(
            "harness-"
        )
        return {
            # Chunk metrics belong to StructuredContractExtractor only. Harness
            # uses DocumentModel/ContextPlanner segments instead.
            "chunk_count": None if is_harness else analysis.chunk_count,
            "processing_duration": analysis.processing_duration,
            "timeout_count": analysis.timeout_count,
            "retry_count": analysis.retry_count,
            "truncated_chunks": None if is_harness else analysis.truncated_chunks,
            "ai_call_count": analysis.ai_call_count,
            "groups_processed": analysis.groups_processed,
            "evidence_issues": analysis.evidence_issues,
            "verifier_issues": analysis.verifier_issues,
            "normalization_issues": analysis.normalization_issues,
        }

    @staticmethod
    def _evidence_row(field_ref: str, source) -> Optional[dict]:
        """Baut aus einem `SourceEvidence` eine abfragbare Evidence-Zeile (oder None)."""
        if source is None:
            return None
        if (
            source.page is None
            and source.paragraph_index is None
            and source.table_index is None
        ):
            return None
        source_type = source.source_type
        if not source_type:
            if source.paragraph_index is not None:
                source_type = "paragraph"
            elif source.table_index is not None:
                source_type = "table"
            else:
                source_type = "page"
        return {
            "field_ref": field_ref,
            "source_type": source_type,
            "page": source.page,
            "paragraph_index": source.paragraph_index,
            "table_index": source.table_index,
            "source_text": source.source_text,
            "confidence": source.confidence,
            "requires_review": source.requires_review,
            "extraction_method": source.extraction_method.value,
            "ocr_confidence": source.ocr_confidence,
            "bounding_box": _bbox_json(source),
        }

    @staticmethod
    def _build_extraction(contract_model) -> tuple[dict, list[dict]]:
        snapshot = contract_model.model_dump(mode="json")
        evidence: list[dict[str, Any]] = []
        for group in _EVIDENCE_GROUPS:
            holder = getattr(contract_model, group, None)
            source = getattr(holder, "evidence", None) if holder is not None else None
            row = DocumentProcessingService._evidence_row(f"{group}.evidence", source)
            if row is not None:
                evidence.append(row)
        # PR-4: Pro Gerät eine abfragbare Evidence-Zeile, damit
        # `contract_equipment.field_ref = identity_equipment.evidence.<index>`
        # den Quellen-Nachweis für die Quell-Navigation trägt.
        for index, eq in enumerate(contract_model.equipment or []):
            source = getattr(eq, "evidence", None)
            row = DocumentProcessingService._evidence_row(
                f"identity_equipment.evidence.{index}", source
            )
            if row is not None:
                evidence.append(row)
        # Harness evidence is version-neutral at this boundary. Do not couple
        # persistence to an exact harness version ("v2" vs "v2.1" already caused
        # valid grounded evidence to be silently dropped).
        harness_evidence = (contract_model.analysis.harness or {}).get("evidence", [])
        if harness_evidence:
            for index, entry in enumerate(harness_evidence):
                from app.models.evidence import SourceEvidence
                row = DocumentProcessingService._evidence_row(
                    f"{entry['field']}.evidence.{index}", SourceEvidence(**entry["source"]))
                if row is not None:
                    evidence.append(row)
        return snapshot, evidence

    @staticmethod
    def _calculation_result_rows(snapshot: dict) -> list[dict]:
        rows: list[dict] = []
        dates = snapshot.get("dates") or {}
        for key in (
            "calculated_end_date",
            "latest_cancellation_date",
            "next_renewal_date",
        ):
            item = dates.get(key) or {}
            rows.append(
                {
                    "field_key": f"dates.{key}",
                    "status": item.get("status", "not_calculable"),
                    "value": _iso_date(item.get("value")),
                    "detail": item.get("explanation"),
                }
            )
        for key in ("days_until_end", "days_until_latest_cancellation"):
            item = dates.get(key) or {}
            rows.append(
                {
                    "field_key": f"dates.{key}",
                    "status": item.get("status", "not_calculable"),
                    "value": item.get("value"),
                    "detail": item.get("explanation"),
                }
            )
        current_status = (dates.get("current_contract_status") or {}).get(
            "status"
        )
        if current_status:
            rows.append(
                {
                    "field_key": "dates.current_contract_status",
                    "status": "computed",
                    "value": current_status,
                }
            )

        costs = snapshot.get("costs") or {}
        normalized = costs.get("normalized_recurring") or {}
        for key in ("annual", "monthly"):
            item = normalized.get(key) or {}
            rows.append(
                {
                    "field_key": f"costs.{key}",
                    "status": item.get("status", "not_calculable"),
                    "amount": item.get("value"),
                    "currency": item.get("currency"),
                    "value": item.get("value"),
                    "detail": item.get("explanation"),
                }
            )
        total = costs.get("total_contract_value") or {}
        total_status = costs.get("total_contract_value_status") or total.get("status")
        if total_status:
            rows.append(
                {
                    "field_key": "costs.total_contract_value",
                    "status": total_status,
                    "amount": total.get("value"),
                    "currency": total.get("currency"),
                    "value": total.get("value"),
                    "detail": total.get("explanation"),
                }
            )
        return [row for row in rows if row.get("status")]

    @staticmethod
    def _calculation_review_flags(snapshot: dict) -> list[dict]:
        flags: list[dict] = []
        dates = snapshot.get("dates") or {}
        conflicts = sum(
            1
            for key in (
                "calculated_end_date",
                "latest_cancellation_date",
                "next_renewal_date",
            )
            if (dates.get(key) or {}).get("status")
            == CalculationStatus.CONFLICT.value
        )
        if conflicts:
            flags.append(
                {
                    "flag_key": "date_conflict",
                    "severity": "critical",
                    "reason": "Konkurrierende Datumsangaben",
                }
            )
        costs = snapshot.get("costs") or {}
        if costs.get("currency_conflict"):
            flags.append(
                {
                    "flag_key": "currency_conflict",
                    "severity": "warning",
                    "reason": "Mehrere Waehrungen",
                }
            )
        annual = (costs.get("normalized_recurring") or {}).get("annual") or {}
        if annual.get("status") == CalculationStatus.CONFLICT.value:
            flags.append(
                {
                    "flag_key": "recurring_cost_conflict",
                    "severity": "warning",
                    "reason": "Widerspruechliche wiederkehrende Kosten",
                }
            )
        total = costs.get("total_contract_value") or {}
        if total.get("status") == CalculationStatus.CONFLICT.value:
            flags.append(
                {
                    "flag_key": "total_contract_value_conflict",
                    "severity": "warning",
                    "reason": "Widerspruch im Gesamtvertragswert",
                    "explanation": total.get("explanation"),
                }
            )
        elif total.get("status") == CalculationStatus.REVIEW_REQUIRED.value:
            flags.append(
                {
                    "flag_key": "price_schedule_incomplete",
                    "severity": "warning",
                    "reason": "Preisplan nicht vollstaendig berechenbar",
                    "explanation": total.get("explanation"),
                }
            )
        return flags

    @staticmethod
    def _copy_result(stored, **changes):
        values = {
            "document_id": stored.document_id,
            "document_version_id": stored.document_version_id,
            "sha256": stored.sha256,
            "original_filename": stored.original_filename,
            "status": stored.status,
            "analysis_status": stored.analysis_status,
            "requires_review": stored.requires_review,
            "contract_id": stored.contract_id,
            "message": stored.message,
            "error": stored.error,
            "warnings": list(stored.warnings),
        }
        values.update(changes)
        return ProcessedDocument(**values)

    @staticmethod
    def _not_found_result():
        return ProcessedDocument(
            document_id="",
            document_version_id="",
            sha256="",
            original_filename="",
            status="rejected",
            message="Dokument nicht gefunden.",
        )


def _projected_supplier(identity) -> Optional[str]:
    """Resolve the external service-provider party without inventing a party.

    Harness role semantics define `supplier` as preferred and `contractor` as the
    service-provider fallback. A value identical to the customer is rejected.
    """
    if identity is None:
        return None
    customer = (getattr(identity, "customer", None) or "").strip()
    for value in (getattr(identity, "supplier", None), getattr(identity, "contractor", None)):
        candidate = (value or "").strip()
        if candidate and (not customer or candidate.casefold() != customer.casefold()):
            return candidate
    return None


def _flexible_date(value) -> Optional[date]:
    if value is None:
        return None
    if hasattr(value, "date") and value.date is not None:
        return value.date
    if isinstance(value, date):
        return value
    return None


def _iso_date(value) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


def _bbox_json(evidence) -> Optional[dict]:
    bounding_box = getattr(evidence, "bounding_box", None)
    if bounding_box is None:
        return None
    return {
        "x0": bounding_box.x0,
        "y0": bounding_box.y0,
        "x1": bounding_box.x1,
        "y1": bounding_box.y1,
    }
