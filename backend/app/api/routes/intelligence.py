"""Enterprise contract-intelligence API.

Thin read layer over persisted accepted intelligence records. Contract-bound
reads honor the active organization/hospital/department scope.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import (
    ActionProposalRecord,
    Contract,
    ContractObligationRecord,
    ContractRelationRecord,
    IntelligenceEvent,
    PolicyDecisionRecord,
)
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


def _org(session, slug, request: Request):
    org = get_organization(session, slug)
    actor = getattr(request.state, "actor", None)
    if org is None or (actor is None and settings.auth_enabled) or (actor is not None and actor.organization_id != org.id):
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    return org


def _visible_contract_ids(session, organization_id: UUID) -> set[UUID] | None:
    scope = current_scope_context()
    return scoped_contract_ids(
        session,
        organization_id,
        scope.hospital_id,
        scope.department_id,
    )


def _require_visible_contract(session, organization_id: UUID, contract_id: UUID) -> set[UUID] | None:
    exists = session.scalar(
        select(Contract.id).where(
            (Contract.id == contract_id)
            & (Contract.organization_id == organization_id)
            & (Contract.lifecycle_state == "active")
        )
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    visible = _visible_contract_ids(session, organization_id)
    if visible is not None and contract_id not in visible:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    return visible


@router.get("/contracts/{contract_id}/graph")
def contract_graph(request: Request, organization_slug: str, contract_id: UUID):
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        visible = _require_visible_contract(session, org.id, contract_id)
        rows = session.scalars(
            select(ContractRelationRecord).where(
                (ContractRelationRecord.organization_id == org.id)
                & (
                    (ContractRelationRecord.source_contract_id == contract_id)
                    | (ContractRelationRecord.target_contract_id == contract_id)
                )
            )
        ).all()
        if visible is not None:
            rows = [
                row
                for row in rows
                if (row.source_contract_id is None or row.source_contract_id in visible)
                and (row.target_contract_id is None or row.target_contract_id in visible)
            ]
        return {
            "contract_id": str(contract_id),
            "relations": [
                {
                    "id": str(row.id),
                    "relation_type": row.relation_type,
                    "source_contract_id": str(row.source_contract_id) if row.source_contract_id else None,
                    "target_contract_id": str(row.target_contract_id) if row.target_contract_id else None,
                    "authority": row.authority,
                    "rationale": row.rationale,
                    "evidence_refs": row.evidence_refs or [],
                    "requires_review": row.requires_review,
                }
                for row in rows
            ],
        }
    finally:
        session.close()


@router.get("/contracts/{contract_id}/obligations")
def contract_obligations(request: Request, organization_slug: str, contract_id: UUID):
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        _require_visible_contract(session, org.id, contract_id)
        rows = session.scalars(
            select(ContractObligationRecord).where(
                (ContractObligationRecord.organization_id == org.id)
                & (ContractObligationRecord.contract_id == contract_id)
            )
        ).all()
        return {
            "contract_id": str(contract_id),
            "items": [
                {
                    "id": str(row.id),
                    "key": row.obligation_key,
                    "title": row.title,
                    "description": row.description,
                    "owner_role": row.owner_role,
                    "status": row.status,
                    "due_date": row.due_date,
                    "recurrence": row.recurrence,
                    "conditions": row.conditions or [],
                    "source_field_refs": row.source_field_refs or [],
                    "evidence_refs": row.evidence_refs or [],
                    "requires_review": row.requires_review,
                }
                for row in rows
            ],
        }
    finally:
        session.close()


@router.get("/contracts/{contract_id}/policies")
def contract_policies(request: Request, organization_slug: str, contract_id: UUID):
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        _require_visible_contract(session, org.id, contract_id)
        rows = session.scalars(
            select(PolicyDecisionRecord).where(
                (PolicyDecisionRecord.organization_id == org.id)
                & (PolicyDecisionRecord.contract_id == contract_id)
            )
        ).all()
        return {
            "contract_id": str(contract_id),
            "items": [
                {
                    "policy_key": row.policy_key,
                    "policy_version": row.policy_version,
                    "outcome": row.outcome,
                    "explanation": row.explanation,
                    "evidence_refs": row.evidence_refs or [],
                    "requires_review": row.requires_review,
                    "evaluated_at": row.evaluated_at,
                }
                for row in rows
            ],
        }
    finally:
        session.close()


@router.get("/contracts/{contract_id}/actions")
def contract_actions(request: Request, organization_slug: str, contract_id: UUID):
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        _require_visible_contract(session, org.id, contract_id)
        rows = session.scalars(
            select(ActionProposalRecord).where(
                (ActionProposalRecord.organization_id == org.id)
                & (ActionProposalRecord.contract_id == contract_id)
            )
        ).all()
        return {
            "contract_id": str(contract_id),
            "items": [
                {
                    "id": str(row.id),
                    "kind": row.kind,
                    "reason": row.reason,
                    "status": row.status,
                    "assignee_role": row.assignee_role,
                    "payload": row.payload or {},
                    "evidence_refs": row.evidence_refs or [],
                    "requires_human_approval": row.requires_human_approval,
                }
                for row in rows
            ],
        }
    finally:
        session.close()


@router.get("/events")
def intelligence_events(request: Request, organization_slug: str, limit: int = 100):
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        visible = _visible_contract_ids(session, org.id)
        stmt = select(IntelligenceEvent).where(IntelligenceEvent.organization_id == org.id)
        if visible is not None:
            stmt = stmt.where(IntelligenceEvent.contract_id.in_(visible))
        rows = session.scalars(
            stmt.order_by(IntelligenceEvent.occurred_at.desc()).limit(max(1, min(limit, 500)))
        ).all()
        return {
            "items": [
                {
                    "id": str(row.id),
                    "contract_id": str(row.contract_id) if row.contract_id else None,
                    "event_type": row.event_type,
                    "payload": row.payload or {},
                    "occurred_at": row.occurred_at,
                    "processed_at": row.processed_at,
                }
                for row in rows
            ]
        }
    finally:
        session.close()
