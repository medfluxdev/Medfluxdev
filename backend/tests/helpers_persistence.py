"""Persistence test helpers that honor accepted-extraction invariants."""

from __future__ import annotations

from app.database.services import save_extraction


def attach_minimal_accepted_extraction(session, *, contract, document_version_id):
    """Create a minimal successful extraction and bind it as accepted.

    Tests that exercise equipment persistence must respect the production
    invariant introduced by reanalysis-safe equipment snapshots: every
    ContractEquipment row belongs to an accepted ContractExtraction.
    """
    extraction = save_extraction(
        session,
        organization_id=contract.organization_id,
        document_version_id=document_version_id,
        snapshot={},
        evidence=[],
        status="success",
        validation_status="unknown",
        requires_review=False,
        model="test",
        prompt_version="test",
    )
    contract.accepted_extraction_id = extraction.id
    session.flush()
    return extraction
