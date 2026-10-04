"""Opt-in read-only MedFlux -> LlamaIndex archive adapter.

The PostgreSQL accepted-extraction pointer remains the sole source of truth.
This service never writes to product tables, and every rebuild and query is
limited by an explicit organization plus caller-provided authorized contracts.
Authentication/ACL decisions must be made by the existing MedFlux API layer.
"""
from __future__ import annotations

from sqlalchemy import select

from app.database.models import Contract, ContractExtraction, DocumentVersion, ExtractionEvidence


def verified_evidence_query(*, organization_id, allowed_contract_ids):
    """Construct org-scoped evidence query. No org-wide fallback for empty ACL."""
    if organization_id is None:
        raise ValueError("Organization context required")
    if not allowed_contract_ids:
        return None
    return (
        select(
            Contract.id.label("contract_id"),
            ContractExtraction.document_version_id.label("revision"),
            DocumentVersion.sha256.label("source_sha256"),
            ExtractionEvidence.page.label("page"),
            ExtractionEvidence.field_ref.label("field"),
            ExtractionEvidence.source_text.label("source_quote"),
        )
        .select_from(Contract)
        .join(ContractExtraction, Contract.accepted_extraction_id == ContractExtraction.id)
        .join(DocumentVersion, ContractExtraction.document_version_id == DocumentVersion.id)
        .join(ExtractionEvidence, ExtractionEvidence.extraction_id == ContractExtraction.id)
        .where(
            Contract.organization_id == organization_id,
            Contract.id.in_(allowed_contract_ids),
            ContractExtraction.organization_id == organization_id,
            DocumentVersion.organization_id == organization_id,
            ExtractionEvidence.organization_id == organization_id,
            ContractExtraction.status == "success",
            ContractExtraction.validation_status == "valid",
            ContractExtraction.requires_review.is_(False),
            ExtractionEvidence.requires_review.is_(False),
            ExtractionEvidence.page.is_not(None),
            ExtractionEvidence.source_text.is_not(None),
        )
    )


def collect_indexable_evidence(session, *, organization_id, allowed_contract_ids):
    """Read-only. Return only literal accepted source quotes with PDF provenance."""
    from app.ai.harness.archive_records import VerifiedRecord

    statement = verified_evidence_query(
        organization_id=organization_id, allowed_contract_ids=allowed_contract_ids)
    if statement is None:
        return []
    records = []
    for row in session.execute(statement).all():
        if not row.source_quote or not row.source_quote.strip():
            continue
        sha = (row.source_sha256 or "").lower()
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            continue
        records.append(VerifiedRecord(
            tenant=str(organization_id),
            document_id=str(row.contract_id),
            revision=str(row.revision),
            page=row.page,
            field=row.field,
            label=row.field,
            value=row.source_quote,  # never invent or promote interpreted values
            source_quote=row.source_quote,
            source_sha256=sha,
            verified=True,
        ))
    return records


def build_readonly_archive(session, archive, *, organization_id, allowed_contract_ids):
    """Index exactly this authorized scope; use a fresh archive per scope."""
    if getattr(archive, "_stores", None):
        raise ValueError("A fresh archive is required for each permission scope")
    records = collect_indexable_evidence(
        session, organization_id=organization_id,
        allowed_contract_ids=allowed_contract_ids)
    return archive.rebuild(str(organization_id), records)


def search_readonly_archive(archive, *, organization_id, allowed_contract_ids, phrase):
    """Re-check ACL on each query even if previously built with broader scope."""
    if organization_id is None:
        raise ValueError("Organization context required")
    return archive.search(
        tenant=str(organization_id),
        allowed_documents={str(value) for value in allowed_contract_ids},
        query=phrase,
    )
