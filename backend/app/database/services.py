"""Persistenz-Services (STEP 10B) – einziger Schreib-Pfad.

Provenienz-/Integritaets- und Transaktions-Disziplin nach STEP 10A:
- §10 Evidence-Ownership: `contract_extraction.contract_snapshot` (immutabler
  Snapshot = Lauf-Wahrheit) und `extraction_evidence` (relationale,
  abfragbare Quell-Navigations-Projektion) werden IM SELBEN LAUF atomar in
  einer Transaktion geschrieben, gebunden ueber `field_ref`.
- §14 Transaktionsgrenzen: Import/Processing, Extraktion (Run+Snapshot+Evidence),
  Berechnung (Run+Result+Flags), Akzeptanz (Zeiger+Projektion) – jeweils atomar.
  Teure Verarbeitung laeuft AUSSERHALB offener DB-Transaktionen; Ergebnis wird
  in kurzer Transaktion persistiert.
- Idempotenz/Duplikate: SHA-256 ist die Duplikat-Identitaet (`document_file.sha256`
  UNIQUE). Retry erzeugt keine Duplikat-Historie.
- Money/Decimal an der Persistenz-Grenze (relationale Betraege als
  NUMERIC(18,2)), Waehrung separat; kein Binary-FLOAT fuer relationale Betraege.
  Der immutablable JSONB-Snapshot haelt die urspruengliche Extraktions-
  Repraesentation (Lauf-Wahrheit).
- `storage_key` ist IMMER ein relativer Schlüssel (nie maschinenabhaengiger
  absoluter Pfad).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    CalculationResult,
    CalculationReviewFlag,
    CalculationRun,
    Contract,
    ContractDocument,
    ContractEquipment,
    ContractExtraction,
    ContractWarning,
    DocumentArtifact,
    DocumentFile,
    DocumentVersion,
    Equipment,
    ExtractionEvidence,
    Organization,
    ProcessingRun,
    ProcessingSummary,
    WarningEvaluationRun,
    WorkItem,
)
from app.database.models.document import IMPORT_STATUS_ALLOWED
from app.database.models.warning import WARNING_RUN_STATUS_ALLOWED


class PersistenceError(Exception):
    """Fehler bei einer Persistenz-Operation."""


def _assert_status(status: str, allowed: set[str], field: str) -> None:
    if status not in allowed:
        raise PersistenceError(f"ungueltiger {field}: {status!r}")


# ---------------------------------------------------------------------------
# Organisation (STEP 10A §15 Foundation)
# ---------------------------------------------------------------------------

def create_organization(session: Session, *, name: str, slug: str) -> Organization:
    existing = session.scalars(
        select(Organization).where(Organization.slug == slug)
    ).first()
    if existing is not None:
        return existing  # idempotent
    org = Organization(name=name, slug=slug)
    session.add(org)
    session.flush()
    return org


def get_organization(session: Session, slug: str) -> Optional[Organization]:
    return session.scalars(select(Organization).where(Organization.slug == slug)).first()


# ---------------------------------------------------------------------------
# Document / DocumentVersion (Idempotenz via SHA-256)
# ---------------------------------------------------------------------------

def save_document_file(
    session: Session,
    *,
    organization_id,
    sha256: str,
    original_filename: str,
    stored_filename: str,
    file_extension: str,
    file_size_bytes: int,
    storage_key: str,
    import_status: str = "imported",
    mime_type: Optional[str] = None,
    external_id: Optional[str] = None,
) -> DocumentFile:
    """Legt eine `document_file`-Zeile an; erkennt Duplikate ueber SHA-256.

    Idempotenz: gleiche Bytes (gleicher sha256) -> kein zweiter Datensatz mit
    Duplikat-Historie; `duplicate_detected` wird nur gesetzt, wenn ueber eine
    separate Logik ein vorheriger Eintrag existiert.
    """
    _assert_status(import_status, IMPORT_STATUS_ALLOWED, "import_status")
    existing = session.scalars(
        select(DocumentFile).where(DocumentFile.sha256 == sha256)
    ).first()
    if existing is not None:
        existing.duplicate_detected = True
        return existing
    doc = DocumentFile(
        organization_id=organization_id,
        external_id=external_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_extension=file_extension,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        sha256=sha256,
        storage_key=storage_key,
        import_status=import_status,
        duplicate_detected=False,
    )
    session.add(doc)
    session.flush()
    return doc


def create_document_version(
    session: Session,
    *,
    organization_id,
    document_file_id,
    version_no: int,
    sha256: str,
    storage_key: str,
) -> DocumentVersion:
    existing = session.scalars(
        select(DocumentVersion).where(DocumentVersion.sha256 == sha256)
    ).first()
    if existing is not None:
        return existing  # same bytes -> already a version
    ver = DocumentVersion(
        organization_id=organization_id,
        document_file_id=document_file_id,
        version_no=version_no,
        sha256=sha256,
        storage_key=storage_key,
    )
    session.add(ver)
    session.flush()
    return ver


def save_artifact(
    session: Session,
    *,
    organization_id,
    document_version_id,
    artifact_type: str,
    storage_key: str,
    sha256: str,
    size_bytes: int,
    format_version: Optional[str] = None,
    media_type: Optional[str] = None,
    processing_run_id=None,
    lifecycle_state: str = "active",
) -> DocumentArtifact:
    from app.database.models.artifact import ARTIFACT_TYPE_ALLOWED, LIFECYCLE_STATE_ALLOWED

    _assert_status(artifact_type, ARTIFACT_TYPE_ALLOWED, "artifact_type")
    _assert_status(lifecycle_state, LIFECYCLE_STATE_ALLOWED, "lifecycle_state")
    art = DocumentArtifact(
        organization_id=organization_id,
        document_version_id=document_version_id,
        processing_run_id=processing_run_id,
        artifact_type=artifact_type,
        storage_key=storage_key,
        sha256=sha256,
        size_bytes=size_bytes,
        format_version=format_version,
        media_type=media_type,
        lifecycle_state=lifecycle_state,
    )
    session.add(art)
    session.flush()
    return art


# ---------------------------------------------------------------------------
# Processing (STEP 10A §9/§14)
# ---------------------------------------------------------------------------

def create_processing_run(
    session: Session,
    *,
    organization_id,
    document_version_id,
    status: str = "running",
    schema_version: Optional[str] = None,
    provider: Optional[str] = None,
    provider_version: Optional[str] = None,
    ocr_engine: Optional[str] = None,
    ocr_engine_version: Optional[str] = None,
    do_ocr: bool = False,
    do_table_structure: bool = False,
    dpi: Optional[int] = None,
    geometry_provider: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
) -> ProcessingRun:
    from app.database.models.processing import PROCESSING_STATUS_ALLOWED

    _assert_status(status, PROCESSING_STATUS_ALLOWED, "processing status")
    run = ProcessingRun(
        organization_id=organization_id,
        document_version_id=document_version_id,
        schema_version=schema_version,
        provider=provider,
        provider_version=provider_version,
        ocr_engine=ocr_engine,
        ocr_engine_version=ocr_engine_version,
        do_ocr=do_ocr,
        do_table_structure=do_table_structure,
        dpi=dpi,
        geometry_provider=geometry_provider,
        status=status,
        message=message,
        error=error,
    )
    session.add(run)
    session.flush()
    return run


def finish_processing_run(
    session: Session,
    *,
    run_id,
    status: str,
    processing_duration: Optional[float] = None,
    canonical_artifact_id=None,
    provider: Optional[str] = None,
    provider_version: Optional[str] = None,
    do_ocr: Optional[bool] = None,
    do_table_structure: Optional[bool] = None,
    geometry_provider: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
) -> ProcessingRun:
    from app.database.models.processing import PROCESSING_STATUS_ALLOWED

    _assert_status(status, PROCESSING_STATUS_ALLOWED, "processing status")
    run = session.get(ProcessingRun, run_id)
    if run is None:
        raise PersistenceError("processing run nicht gefunden")
    run.status = status
    run.processing_duration = processing_duration
    if message is not None:
        run.message = message
    if error is not None:
        run.error = error
    if canonical_artifact_id is not None:
        run.canonical_artifact_id = canonical_artifact_id
    if provider is not None:
        run.provider = provider
    if provider_version is not None:
        run.provider_version = provider_version
    if do_ocr is not None:
        run.do_ocr = do_ocr
    if do_table_structure is not None:
        run.do_table_structure = do_table_structure
    if geometry_provider is not None:
        run.geometry_provider = geometry_provider
    session.flush()
    return run


def upsert_processing_summary(
    session: Session,
    *,
    organization_id,
    document_version_id,
    file_key: str,
    page_count: int = 0,
    doc_type: Optional[str] = None,
    processed_at=None,
    success: int = 1,
    failure: int = 0,
    last_success_run_id=None,
) -> ProcessingSummary:
    summary = session.scalars(
        select(ProcessingSummary).where(
            ProcessingSummary.document_version_id == document_version_id
        )
    ).first()
    if summary is None:
        summary = ProcessingSummary(
            organization_id=organization_id,
            document_version_id=document_version_id,
            file_key=file_key,
            page_count=page_count,
            doc_type=doc_type,
            processed_at=processed_at,
            success_count=success,
            failure_count=failure,
            last_success_run_id=last_success_run_id,
        )
        session.add(summary)
    else:
        summary.success_count += success
        summary.failure_count += failure
        summary.page_count = page_count
        if doc_type is not None:
            summary.doc_type = doc_type
        if processed_at is not None:
            summary.processed_at = processed_at
        if last_success_run_id is not None:
            summary.last_success_run_id = last_success_run_id
    session.flush()
    return summary


# ---------------------------------------------------------------------------
# Extraktion (Run + Snapshot + Evidence – atomar, §10/§14)
# ---------------------------------------------------------------------------

def _snapshot_sha256(snapshot_json: Optional[dict]) -> Optional[str]:
    if snapshot_json is None:
        return None
    import json

    canonical = json.dumps(
        snapshot_json, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def save_extraction(
    session: Session,
    *,
    organization_id,
    document_version_id,
    snapshot: Optional[dict],
    evidence: Iterable[dict],
    status: str = "success",
    validation_status: str = "unknown",
    requires_review: bool = False,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    chunk_count: int = 0,
    processing_duration: float = 0.0,
    timeout_count: int = 0,
    retry_count: int = 0,
    truncated_chunks: int = 0,
    ai_call_count: int = 0,
    groups_processed: int = 0,
    evidence_issues: int = 0,
    verifier_issues: int = 0,
    normalization_issues: int = 0,
) -> ContractExtraction:
    from app.database.models.extraction import (
        EXTRACTION_STATUS_ALLOWED,
        VALIDATION_STATUS_ALLOWED,
    )

    _assert_status(status, EXTRACTION_STATUS_ALLOWED, "extraction status")
    _assert_status(validation_status, VALIDATION_STATUS_ALLOWED, "validation_status")

    snapshot_sha = _snapshot_sha256(snapshot)
    run = ContractExtraction(
        organization_id=organization_id,
        document_version_id=document_version_id,
        status=status,
        validation_status=validation_status,
        requires_review=requires_review,
        message=message,
        error=error,
        model=model,
        prompt_version=prompt_version,
        chunk_count=chunk_count,
        processing_duration=processing_duration,
        timeout_count=timeout_count,
        retry_count=retry_count,
        truncated_chunks=truncated_chunks,
        ai_call_count=ai_call_count,
        groups_processed=groups_processed,
        evidence_issues=evidence_issues,
        verifier_issues=verifier_issues,
        normalization_issues=normalization_issues,
        contract_snapshot=snapshot,
        snapshot_sha256=snapshot_sha,
    )
    session.add(run)
    session.flush()

    for ev in evidence:
        row = ExtractionEvidence(
            organization_id=organization_id,
            extraction_id=run.id,
            field_ref=ev["field_ref"],
            source_type=ev.get("source_type", "page"),
            # DOCX has no authoritative physical pages.  Keep page NULL and
            # persist its paragraph/table index instead of manufacturing page 1.
            page=ev.get("page"),
            paragraph_index=ev.get("paragraph_index"),
            table_index=ev.get("table_index"),
            source_text=ev.get("source_text"),
            bounding_box=ev.get("bounding_box"),
            ocr_confidence=_to_decimal(ev.get("ocr_confidence")),
            confidence=_to_decimal(ev.get("confidence")),
            requires_review=bool(ev.get("requires_review", False)),
            extraction_method=ev.get("extraction_method", "ai"),
        )
        session.add(row)
    session.flush()
    return run


def _to_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (TypeError, ValueError):
        return None


def verify_extraction_integrity(session: Session, extraction_id) -> dict:
    """STEP 10A §10-Schnelltest: relationale Evidence vs. Shot-Index im Snapshot."""
    run = session.get(ContractExtraction, extraction_id)
    if run is None:
        raise PersistenceError("extraction run nicht gefunden")
    snapshot = run.contract_snapshot or {}

    index: dict[str, dict] = {}
    # Felder im Snapshot mit überall vorhandener Evidence: field_ref -> Quelle
    for group_name, group in snapshot.items():
        if not isinstance(group, dict):
            continue
        ev = group.get("evidence") or {}
        ref = f"{group_name}.evidence"
        if ev:
            index[ref] = {"source_type": ev.get("source_type"), "page": ev.get("page")}

    mismatches: list[str] = []
    matched_refs: set[str] = set()
    for row in run.evidence_rows:
        key = row.field_ref
        # Im Snapshot-Schema werden Evidence-Blöcke als <group>.evidence geführt.
        if any(row.field_ref.startswith(base + ".") for base in index):
            matched_refs.add(row.field_ref.split(".", 1)[0] + ".evidence")
            continue
        if key not in index:
            mismatches.append(f"evidence {key!r} fehlt im Snapshot-Index")

    return {
        "snapshot_sha256": run.snapshot_sha256,
        "evidence_count": len(run.evidence_rows),
        "mismatches": mismatches,
        "matched_snapshot_refs": sorted(matched_refs),
    }


# ---------------------------------------------------------------------------
# Berechnung (Run + Result + Flags – atomar, §14)
# ---------------------------------------------------------------------------

def save_calculation(
    session: Session,
    *,
    organization_id,
    extraction_id,
    as_of_date: date,
    result_snapshot: Optional[dict],
    calculation_version: Optional[str] = None,
    status: str = "computed",
    overall_review_required: bool = False,
    result_rows: Optional[list[dict]] = None,
    review_flags: Optional[list[dict]] = None,
) -> CalculationRun:
    from app.database.models.calculation import CALCULATION_STATUS_ALLOWED

    _assert_status(status, CALCULATION_STATUS_ALLOWED, "calculation status")
    run = CalculationRun(
        organization_id=organization_id,
        extraction_id=extraction_id,
        as_of_date=as_of_date,
        calculation_version=calculation_version,
        overall_review_required=overall_review_required,
        status=status,
        result_snapshot=result_snapshot,
    )
    session.add(run)
    session.flush()

    for r in result_rows or []:
        session.add(
            CalculationResult(
                organization_id=organization_id,
                run_id=run.id,
                field_key=r["field_key"],
                status=r.get("status"),
                amount=_to_decimal(r.get("amount")),
                currency=r.get("currency"),
                value=r.get("value"),
                detail=r.get("detail"),
            )
        )
    for f in review_flags or []:
        session.add(
            CalculationReviewFlag(
                organization_id=organization_id,
                calculation_run_id=run.id,
                flag_key=f["flag_key"],
                severity=f["severity"],
                reason=f.get("reason"),
                explanation=f.get("explanation"),
                inputs=f.get("inputs"),
            )
        )
    session.flush()
    return run


# ---------------------------------------------------------------------------
# Contract current/acceptance + Projektion (§11/§12/§14)
# ---------------------------------------------------------------------------

def create_contract(
    session: Session,
    *,
    organization_id,
    supplier: Optional[str] = None,
    contract_number: Optional[str] = None,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
) -> Contract:
    contract = Contract(
        organization_id=organization_id,
        supplier=supplier,
        contract_number=contract_number,
        status=status,
        risk_level=risk_level,
    )
    session.add(contract)
    session.flush()
    return contract


def _resolve_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if hasattr(value, "date") and value.date is not None:
        return value.date
    return None


def project_contract(
    session: Session,
    *,
    contract,
    supplier: Optional[str] = None,
    contract_number: Optional[str] = None,
    start_date=None,
    end_date=None,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    replace_missing: bool = False,
) -> Contract:
    """Befuellt Projektions-/Current-Felder aus einem akzeptierten Lauf.

    Nur deterministisch uebernommene Werte; `status` folgt der TERMINATED-Regel
    (§11): TERMINATED wird nur uebernommen, wenn das Extraktionsmodell ihn
    explizit liefert (STEP 9-Verhalten beibehalten). Keine Werterfindung.
    """
    if replace_missing or supplier is not None:
        contract.supplier = supplier
    if replace_missing or contract_number is not None:
        contract.contract_number = contract_number
    if replace_missing or status is not None:
        contract.status = status.lower() if status is not None else None
    if replace_missing or risk_level is not None:
        contract.risk_level = risk_level.lower() if risk_level is not None else None
    start = _resolve_date(start_date)
    end = _resolve_date(end_date)
    if replace_missing or start is not None:
        contract.start_date = start
    if replace_missing or end is not None:
        contract.end_date = end
    session.flush()
    return contract


def accept_extraction(
    session: Session, *, contract_id, extraction_id
) -> Contract:
    contract = session.get(Contract, contract_id)
    if contract is None:
        raise PersistenceError("contract nicht gefunden")
    run = session.get(ContractExtraction, extraction_id)
    if run is None:
        raise PersistenceError("extraction run nicht gefunden")
    contract.accepted_extraction_id = extraction_id
    session.flush()
    return contract


def accept_calculation(
    session: Session, *, contract_id, calculation_run_id
) -> Contract:
    contract = session.get(Contract, contract_id)
    if contract is None:
        raise PersistenceError("contract nicht gefunden")
    run = session.get(CalculationRun, calculation_run_id)
    if run is None:
        raise PersistenceError("calculation run nicht gefunden")
    contract.accepted_calculation_run_id = calculation_run_id
    session.flush()
    return contract


def link_document(
    session: Session,
    *,
    contract_id,
    document_version_id,
    role: Optional[str] = None,
) -> ContractDocument:
    from app.database.models.contract import CONTRACT_DOCUMENT_ROLE_ALLOWED

    if role is not None:
        _assert_status(role, CONTRACT_DOCUMENT_ROLE_ALLOWED, "role")
    existing = session.scalars(
        select(ContractDocument).where(
            (ContractDocument.contract_id == contract_id)
            & (ContractDocument.document_version_id == document_version_id)
        )
    ).first()
    if existing is not None:
        return existing  # idempotent
    link = ContractDocument(
        organization_id=session.get(Contract, contract_id).organization_id,
        contract_id=contract_id,
        document_version_id=document_version_id,
        role=role,
    )
    session.add(link)
    session.flush()
    return link


def _equipment_fingerprint(contract_id, *, device_name, model, manufacturer,
                           serial_number, inventory_number, system_name) -> str:
    """Stabiler, inhaltlicher Fingerprint einer Geräte-Zeile (Idempotenz je Vertrag)."""
    def _norm(v):
        return (v or "").strip().lower()
    payload = "|".join(
        _norm(v) for v in (
            device_name, model, manufacturer, serial_number,
            inventory_number, system_name,
        )
    )
    return hashlib.sha256(f"{contract_id}|{payload}".encode("utf-8")).hexdigest()


def resolve_equipment_master(
    session: Session,
    *,
    organization_id,
    serial_number: Optional[str] = None,
    inventory_number: Optional[str] = None,
    device_name: Optional[str] = None,
    manufacturer: Optional[str] = None,
    model: Optional[str] = None,
    equipment_type: Optional[str] = None,
    equipment_category: Optional[str] = None,
    location: Optional[str] = None,
    department: Optional[str] = None,
    identification_quality: str = "unknown",
) -> Optional["Equipment"]:
    """Find-or-create einer kanonischen `equipment`-Master-Identität.

    Nur bei EINDEUTIGER Kennung (Serien- oder Inventarnummer) wird eine
    vorhandene Master-Identität derselben Organisation wiederverwendet
    („ein Gerät, mehrere Verträge"). Ohne eindeutige Kennung wird KEINE
    trügerische Zuordnung gemergt – es wird eine eigene Master-Zeile mit
    gesetzter Qualität angelegt (manuell später zuordenbar). Liefert None,
    wenn keine nutzbare Identität vorliegt.
    """
    from app.equipment.identity import identification_quality as _calc_quality

    # A whitespace-only identifier must never count as an exact identity.
    # Normalize leading/trailing whitespace before matching an existing master.
    serial_number = serial_number.strip() or None if serial_number is not None else None
    inventory_number = inventory_number.strip() or None if inventory_number is not None else None

    if not (serial_number or inventory_number or device_name or model
            or manufacturer or equipment_category):
        return None
    quality = identification_quality or _calc_quality(
        serial_number=serial_number, inventory_number=inventory_number,
        device_name=device_name, model=model, manufacturer=manufacturer,
        equipment_category=equipment_category,
    ).value

    if quality == "exact" and serial_number:
        exists = session.scalars(
            select(Equipment).where(
                (Equipment.organization_id == organization_id)
                & (Equipment.serial_number == serial_number)
            )
        ).first()
        if exists is not None:
            return exists
    if quality == "exact" and inventory_number:
        exists = session.scalars(
            select(Equipment).where(
                (Equipment.organization_id == organization_id)
                & (Equipment.inventory_number == inventory_number)
            )
        ).first()
        if exists is not None:
            return exists

    m = Equipment(
        organization_id=organization_id,
        device_name=device_name,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        inventory_number=inventory_number,
        equipment_type=equipment_type,
        equipment_category=equipment_category,
        location=location,
        department=department,
        identification_quality=quality,
    )
    session.add(m)
    session.flush()
    return m


def add_equipment(
    session: Session,
    *,
    contract_id,
    extraction_id=None,
    device_name: Optional[str] = None,
    manufacturer: Optional[str] = None,
    model: Optional[str] = None,
    serial_number: Optional[str] = None,
    inventory_number: Optional[str] = None,
    system_name: Optional[str] = None,
    equipment_category: Optional[str] = None,
    equipment_type: Optional[str] = None,
    location: Optional[str] = None,
    department: Optional[str] = None,
    service_scope: Optional[str] = None,
    coverage_start: Optional[object] = None,
    coverage_end: Optional[object] = None,
    included_services: Optional[list] = None,
    excluded_services: Optional[list] = None,
    sla_notes: Optional[str] = None,
    field_ref: Optional[str] = None,
    equipment_index: Optional[int] = None,
    has_evidence: bool = False,
) -> ContractEquipment:
    """Erzeugt eine Geräte-Relation eines akzeptierten Vertrags (PR-4).

    Deterministisch:
    - `identification_quality`/`relationship_quality` werden in Code abgeleitet
      (KEINE erfundenen Kennungen). `requires_review` für partial/generic/
      ambiguous.
    - Es wird eine kanonische `equipment`-Master-Identität aufgelöst/angelegt
      (nur seriös bei eindeutiger Kennung) und per `equipment_id` verknüpft.
    - Jede Zeile gehört unveränderlich zu genau einem Extraktionslauf.
    - Idempotenz gilt innerhalb `(contract_id, extraction_id)`; der semantische
      Fingerprint selbst bleibt über Reanalysen stabil.
    """
    from app.equipment.identity import (
        identification_quality as _quality,
        relationship_quality as _rel,
        requires_manual_review as _needs_review,
        review_reason_de as _reason_de,
    )

    # Keep extraction identifiers, fingerprint and canonical master consistent:
    # whitespace-only serial/inventory fields are missing, not exact IDs.
    serial_number = serial_number.strip() or None if serial_number is not None else None
    inventory_number = inventory_number.strip() or None if inventory_number is not None else None

    contract = session.get(Contract, contract_id)
    if contract is None:
        raise PersistenceError("contract nicht gefunden")
    if extraction_id is None:
        extraction_id = contract.accepted_extraction_id
    if extraction_id is None:
        raise PersistenceError("equipment requires an extraction run")
    extraction = session.get(ContractExtraction, extraction_id)
    if extraction is None:
        raise PersistenceError("extraction run nicht gefunden")
    if extraction.organization_id != contract.organization_id:
        raise PersistenceError("extraction/contract organisation mismatch")

    # Idempotenz innerhalb eines Extraktions-Snapshots. Der Fingerprint bleibt
    # absichtlich unabhängig von extraction_id (stabile logische Work-Item-ID).
    fp = _equipment_fingerprint(
        contract_id,
        device_name=device_name, model=model, manufacturer=manufacturer,
        serial_number=serial_number, inventory_number=inventory_number,
        system_name=system_name,
    )
    existing = session.scalars(
        select(ContractEquipment).where(
            (ContractEquipment.contract_id == contract_id)
            & (ContractEquipment.extraction_id == extraction_id)
            & (ContractEquipment.logical_fingerprint == fp)
        )
    ).first() if hasattr(ContractEquipment, "logical_fingerprint") else None
    if existing is not None:
        return existing

    # A source-backed system name is a usable canonical equipment identity even
    # when the extractor did not supply a separate device_name. Preserve the
    # original contract fields; only the master identity uses this fallback.
    master_name = device_name or system_name
    ident = _quality(
        serial_number=serial_number, inventory_number=inventory_number,
        device_name=master_name, model=model, manufacturer=manufacturer,
        equipment_category=equipment_category,
    )
    rel = _rel(ident, has_evidence=has_evidence)
    needs_review = _needs_review(rel)
    reason = _reason_de(rel)

    master = resolve_equipment_master(
        session,
        organization_id=contract.organization_id,
        serial_number=serial_number,
        inventory_number=inventory_number,
        device_name=master_name,
        manufacturer=manufacturer,
        model=model,
        equipment_type=equipment_type,
        equipment_category=equipment_category,
        location=location,
        department=department,
        identification_quality=ident.value,
    )

    eq = ContractEquipment(
        organization_id=contract.organization_id,
        contract_id=contract_id,
        extraction_id=extraction_id,
        equipment_id=master.id if master is not None else None,
        device_name=device_name,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        inventory_number=inventory_number,
        system_name=system_name,
        equipment_category=equipment_category,
        equipment_type=equipment_type,
        location=location,
        department=department,
        service_scope=service_scope,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        included_services=included_services,
        excluded_services=excluded_services,
        sla_notes=sla_notes,
        identification_quality=ident.value,
        relationship_quality=rel.value,
        requires_review=needs_review,
        review_reasons=[reason] if reason else None,
        field_ref=field_ref,
        equipment_index=equipment_index,
        logical_fingerprint=fp,
    )
    session.add(eq)
    session.flush()
    return eq


# ---------------------------------------------------------------------------
# Quell-Navigation (STEP 8B 6/6, persistierte Kette)
# ---------------------------------------------------------------------------

@dataclass
class SourceNavigation:
    field_ref: str
    page: Optional[int]
    paragraph_index: Optional[int]
    table_index: Optional[int]
    source_type: str
    source_text: Optional[str]
    bounding_box: Optional[dict]
    confidence: Optional[Decimal]
    storage_key: Optional[str]
    document_file_id: Optional[str]
    original_filename: Optional[str]


def resolve_source_navigation(
    session: Session, *, contract_id, field_ref: str
) -> Optional[SourceNavigation]:
    """Contract -> evidence -> extraction -> document_version -> storage_key.

    Baut die Quell-Navigation-Kette für ein Feld auf. Liefert None, wenn keins
    der Belege gefunden wird oder keine exakte Geometrie existiert (kein Erfinden).
    """
    contract = session.get(Contract, contract_id)
    if contract is None or contract.accepted_extraction_id is None:
        return None
    row = session.scalars(
        select(ExtractionEvidence)
        .where(
            (ExtractionEvidence.extraction_id == contract.accepted_extraction_id)
            & (ExtractionEvidence.field_ref == field_ref)
        )
        .order_by(ExtractionEvidence.id)
    ).first()
    if row is None:
        return None
    # Evidence hat kein direktes document_version_id; es laeuft ueber den
    # zugehoerigen Extraction-Lauf.
    extraction = session.get(ContractExtraction, row.extraction_id)
    if extraction is None:
        return None
    version = session.get(DocumentVersion, extraction.document_version_id)
    doc_file_id = version.document_file_id if version else None
    doc = session.get(DocumentFile, doc_file_id) if doc_file_id else None
    return SourceNavigation(
        field_ref=row.field_ref,
        page=row.page,
        paragraph_index=row.paragraph_index,
        table_index=row.table_index,
        source_type=row.source_type,
        source_text=row.source_text,
        bounding_box=row.bounding_box,
        confidence=row.confidence,
        storage_key=version.storage_key if version else None,
        document_file_id=str(doc.id) if doc else None,
        original_filename=doc.original_filename if doc else None,
    )


# ---------------------------------------------------------------------------
# Warnungen (STEP 11) – durable Warn-Zustand/Historie + Current-Projektion
# ---------------------------------------------------------------------------

_WARNING_APPROACHING_TYPES = {
    "contract_end_approaching",
    "cancellation_deadline_approaching",
    "cancellation_deadline_today",
    "cancellation_deadline_passed",
}
_SEVERITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}


def _project_current_status(contract: Contract, result, calc_status) -> str:
    """Deterministische Current-State-Präzedenz (STEP 11 §18).

    1. explizit TERMINATED bleibt TERMINATED
    2. sonst autoritatives STEP-9 EXPIRED -> EXPIRED
    3. sonst aktiver Vertrag mit anstehender, relevanter Aktion -> EXPIRING_SOON
    4. sonst ACTIVE/UNKNOWN entsprechend STEP-9-Zustand
    """
    if contract.status == "terminated":
        return "terminated"
    if calc_status == "expired":
        return "expired"
    if any(w.warning_type in _WARNING_APPROACHING_TYPES for w in result.warnings):
        return "expiring_soon"
    if calc_status == "active":
        return "active"
    return "unknown"


def _project_risk_level(result) -> str:
    """Hoechster aktiver Schweregrad -> bestehendes RiskLevel-Enum (deterministisch)."""
    worst = None
    for w in result.warnings:
        rank = _SEVERITY_RANK.get(w.severity.value, 4)
        if worst is None or rank < worst[0]:
            worst = (rank, w.severity.value)
    if worst is None or worst[1] in ("info", None):
        return "unknown"
    if worst[1] in ("critical", "high"):
        return "high"
    if worst[1] == "medium":
        return "medium"
    return "low"


def run_warning_evaluation(
    session: Session,
    *,
    organization_id,
    contract_id,
    calculation_run_id,
    as_of_date: date,
    policy_version: str,
    result,
    status: str = "computed",
) -> dict:
    """Persistiert einen Warn-Evaluationslauf + akkumulierte Warn-Zustaende.

    Idempotent je `calculation_run_id`: Ein Wiederholungslauf desselben
    Rechenlaufs erzeugt KEINE Duplikat-Run-Zeile, sondern gleicht nur die
    `contract_warning`-Zustaende ab. `active=False` statt Loeschung (Historie/
    menschlicher action_state bleiben erhalten; §13/§14).
    """
    from app.contracts.warnings import WarningPolicy

    _assert_status(status, WARNING_RUN_STATUS_ALLOWED, "warning run status")

    run = session.scalars(
        select(WarningEvaluationRun).where(
            WarningEvaluationRun.calculation_run_id == calculation_run_id
        )
    ).first()
    if run is None:
        run = WarningEvaluationRun(
            organization_id=organization_id,
            contract_id=contract_id,
            calculation_run_id=calculation_run_id,
            as_of_date=as_of_date,
            policy_version=policy_version,
            status=status,
            result_snapshot=result.model_dump(mode="json"),
        )
        session.add(run)
        session.flush()

    # Gegenwaertiger Satz von problem-Ids aus diesem Lauf.
    current: dict[str, object] = {
        w.logical_fingerprint: w for w in result.warnings if w.logical_fingerprint
    }
    now = datetime.now(timezone.utc)

    # Bestehende Warn-Zeilen dieses Vertrags abgleichen.
    existing = session.scalars(
        select(ContractWarning).where(ContractWarning.contract_id == contract_id)
    ).all()
    seen = set()
    for row in existing:
        if row.logical_fingerprint in current:
            w = current[row.logical_fingerprint]
            row.active = True
            row.last_seen_at = now
            row.last_evaluation_run_id = run.id
            row.warning_type = w.warning_type.value
            row.severity = w.severity.value
            row.target_kind = w.target_kind.value
            row.target_date = w.target_date
            row.days_remaining = w.days_remaining
            row.threshold = w.matched_threshold_days
            row.requires_action = w.requires_action
            row.requires_review = w.requires_review
            row.calculation_field_refs = w.calculation_field_refs
            row.source_field_refs = w.source_field_refs
            seen.add(row.logical_fingerprint)
        else:
            # Nicht mehr aktiv -> Historie behalten, Evaluations-Zustand inaktiv.
            row.active = False
            # action_state (menschlicher Lebenszyklus) wird NICHT automatisch geloescht.

    # Neue Probleme einfuegen.
    for fp, w in current.items():
        if fp in seen:
            continue
        session.add(
            ContractWarning(
                organization_id=organization_id,
                contract_id=contract_id,
                last_evaluation_run_id=run.id,
                warning_type=w.warning_type.value,
                severity=w.severity.value,
                target_kind=w.target_kind.value,
                target_date=w.target_date,
                days_remaining=w.days_remaining,
                threshold=w.matched_threshold_days,
                logical_fingerprint=fp,
                active=True,
                requires_action=w.requires_action,
                requires_review=w.requires_review,
                action_state="open",
                calculation_field_refs=w.calculation_field_refs,
                source_field_refs=w.source_field_refs,
            )
        )
    session.flush()

    # Current-State-Projektion (Status + Risiko) auf dem Vertrag aktualisieren.
    calc = session.get(CalculationRun, calculation_run_id)
    calc_status = "unknown"
    if calc is not None and calc.result_snapshot:
        calc_status = (
            calc.result_snapshot.get("dates", {}).get("current_contract_status", {}).get("status")
            or "unknown"
        )
    contract = session.get(Contract, contract_id)
    if contract is not None:
        contract.status = _project_current_status(contract, result, calc_status)
        contract.risk_level = _project_risk_level(result)

    session.flush()
    active_count = sum(1 for row in existing if row.active)
    return {
        "run_id": str(run.id),
        "current_count": len(current),
        "active_rows": active_count,
    }

