"""Operational lifecycle workflows for contracts and equipment.

These endpoints capture human operational decisions. They do not overwrite
accepted extraction truth or deterministic contract status.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import (
    Contract,
    ContractLifecycleDecision,
    Equipment,
    EquipmentLifecycleRecord,
)
from app.database.models.activity_log import ActivityLog
from app.database.models.lifecycle import CONTRACT_DECISIONS, DECISION_STATUS, EQUIPMENT_LIFECYCLE
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])
MANAGE_ROLES = {"admin", "contract_manager"}


class ContractDecisionCreate(BaseModel):
    decision: str
    status: str = "planned"
    effective_date: date | None = None
    note: str | None = Field(default=None, max_length=4000)


class ContractDecisionUpdate(BaseModel):
    status: str
    effective_date: date | None = None
    note: str | None = Field(default=None, max_length=4000)


class EquipmentLifecycleUpdate(BaseModel):
    status: str
    next_service_date: date | None = None
    note: str | None = Field(default=None, max_length=4000)


def _actor_or_forbid(request: Request):
    actor = getattr(request.state, "actor", None)
    if not settings.auth_enabled:
        return actor
    if actor is None:
        raise HTTPException(status_code=401, detail="Anmeldung erforderlich.")
    if not actor.is_developer and (actor.role or "").casefold() not in MANAGE_ROLES:
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Aktion.")
    return actor


def _org(session, slug: str):
    org = get_organization(session, slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    return org


def _require_contract(session, org_id: UUID, contract_id: UUID):
    row = session.get(Contract, contract_id)
    if row is None or row.organization_id != org_id or row.lifecycle_state != "active":
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    scope = current_scope_context()
    allowed = scoped_contract_ids(session, org_id, scope.hospital_id, scope.department_id)
    if allowed is not None and contract_id not in allowed:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    return row, scope


def _require_equipment(session, org_id: UUID, equipment_id: UUID):
    row = session.get(Equipment, equipment_id)
    if row is None or row.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
    scope = current_scope_context()
    if scope.department_id is not None and row.department_id != scope.department_id:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
    if scope.department_id is None and scope.hospital_id is not None and row.hospital_id != scope.hospital_id:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
    return row, scope


def _decision_payload(row: ContractLifecycleDecision) -> dict:
    return {
        "id": str(row.id),
        "contract_id": str(row.contract_id),
        "decision": row.decision,
        "status": row.status,
        "effective_date": row.effective_date,
        "note": row.note,
        "actor_display_name": row.actor_display_name,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/contracts/{contract_id}")
def contract_lifecycle(organization_slug: str, contract_id: UUID):
    session = create_session()
    try:
        org = _org(session, organization_slug)
        _require_contract(session, org.id, contract_id)
        rows = session.scalars(
            select(ContractLifecycleDecision).where(
                ContractLifecycleDecision.organization_id == org.id,
                ContractLifecycleDecision.contract_id == contract_id,
            ).order_by(ContractLifecycleDecision.created_at.desc())
        ).all()
        return {"items": [_decision_payload(row) for row in rows]}
    finally:
        session.close()


@router.post("/contracts/{contract_id}")
def create_contract_decision(request: Request, organization_slug: str, contract_id: UUID, body: ContractDecisionCreate):
    actor = _actor_or_forbid(request)
    decision = body.decision.casefold().strip()
    status = body.status.casefold().strip()
    if decision not in CONTRACT_DECISIONS or status not in DECISION_STATUS:
        raise HTTPException(status_code=422, detail="Ungültige Lifecycle-Angaben.")
    session = create_session()
    try:
        org = _org(session, organization_slug)
        _, scope = _require_contract(session, org.id, contract_id)
        display_name = getattr(actor, "display_name", None) or "local-development"
        row = ContractLifecycleDecision(
            organization_id=org.id,
            contract_id=contract_id,
            decision=decision,
            status=status,
            effective_date=body.effective_date,
            note=body.note,
            actor_account_id=getattr(actor, "account_id", None),
            actor_display_name=display_name,
        )
        session.add(row)
        if actor is not None:
            session.add(ActivityLog(
                organization_id=actor.organization_id,
                hospital_id=scope.hospital_id,
                department_id=scope.department_id,
                account_id=actor.account_id,
                display_name_snapshot=actor.display_name,
                role_snapshot="developer" if actor.is_developer else actor.role,
                event_name="contract.lifecycle_decision_created",
                object_type="contract",
                object_id=contract_id,
                context_data={"decision": decision, "status": status, "effective_date": body.effective_date.isoformat() if body.effective_date else None},
            ))
        session.commit()
        return _decision_payload(row)
    finally:
        session.close()


@router.patch("/contracts/{contract_id}/{decision_id}")
def update_contract_decision(request: Request, organization_slug: str, contract_id: UUID, decision_id: UUID, body: ContractDecisionUpdate):
    actor = _actor_or_forbid(request)
    status = body.status.casefold().strip()
    if status not in DECISION_STATUS:
        raise HTTPException(status_code=422, detail="Ungültiger Lifecycle-Status.")
    session = create_session()
    try:
        org = _org(session, organization_slug)
        _, scope = _require_contract(session, org.id, contract_id)
        row = session.get(ContractLifecycleDecision, decision_id)
        if row is None or row.organization_id != org.id or row.contract_id != contract_id:
            raise HTTPException(status_code=404, detail="Lifecycle-Entscheidung nicht gefunden.")
        previous = row.status
        row.status = status
        row.effective_date = body.effective_date
        row.note = body.note
        if actor is not None and previous != status:
            session.add(ActivityLog(
                organization_id=actor.organization_id,
                hospital_id=scope.hospital_id,
                department_id=scope.department_id,
                account_id=actor.account_id,
                display_name_snapshot=actor.display_name,
                role_snapshot="developer" if actor.is_developer else actor.role,
                event_name=f"contract.lifecycle_{status}",
                object_type="contract",
                object_id=contract_id,
                context_data={"decision_id": str(row.id), "decision": row.decision, "previous_status": previous, "status": status},
            ))
        session.commit()
        return _decision_payload(row)
    finally:
        session.close()


@router.get("/equipment/{equipment_id}")
def equipment_lifecycle(organization_slug: str, equipment_id: UUID):
    session = create_session()
    try:
        org = _org(session, organization_slug)
        _require_equipment(session, org.id, equipment_id)
        row = session.scalars(select(EquipmentLifecycleRecord).where(
            EquipmentLifecycleRecord.organization_id == org.id,
            EquipmentLifecycleRecord.equipment_id == equipment_id,
        )).first()
        if row is None:
            return {"equipment_id": str(equipment_id), "status": "active", "next_service_date": None, "note": None, "updated_by_display_name": None, "updated_at": None}
        return {"equipment_id": str(row.equipment_id), "status": row.status, "next_service_date": row.next_service_date, "note": row.note, "updated_by_display_name": row.updated_by_display_name, "updated_at": row.updated_at}
    finally:
        session.close()


@router.put("/equipment/{equipment_id}")
def update_equipment_lifecycle(request: Request, organization_slug: str, equipment_id: UUID, body: EquipmentLifecycleUpdate):
    actor = _actor_or_forbid(request)
    status = body.status.casefold().strip()
    if status not in EQUIPMENT_LIFECYCLE:
        raise HTTPException(status_code=422, detail="Ungültiger Geräte-Lifecycle-Status.")
    session = create_session()
    try:
        org = _org(session, organization_slug)
        _, scope = _require_equipment(session, org.id, equipment_id)
        row = session.scalars(select(EquipmentLifecycleRecord).where(EquipmentLifecycleRecord.equipment_id == equipment_id)).first()
        display_name = getattr(actor, "display_name", None) or "local-development"
        if row is None:
            row = EquipmentLifecycleRecord(organization_id=org.id, equipment_id=equipment_id, status=status, updated_by_account_id=getattr(actor, "account_id", None), updated_by_display_name=display_name)
            session.add(row)
            previous = None
        else:
            previous = row.status
            row.status = status
            row.updated_by_account_id = getattr(actor, "account_id", None)
            row.updated_by_display_name = display_name
        row.next_service_date = body.next_service_date
        row.note = body.note
        if actor is not None:
            session.add(ActivityLog(
                organization_id=actor.organization_id,
                hospital_id=scope.hospital_id,
                department_id=scope.department_id,
                account_id=actor.account_id,
                display_name_snapshot=actor.display_name,
                role_snapshot="developer" if actor.is_developer else actor.role,
                event_name=f"equipment.lifecycle_{status}",
                object_type="equipment",
                object_id=equipment_id,
                context_data={"previous_status": previous, "status": status, "next_service_date": body.next_service_date.isoformat() if body.next_service_date else None},
            ))
        session.commit()
        return {"equipment_id": str(row.equipment_id), "status": row.status, "next_service_date": row.next_service_date, "note": row.note, "updated_by_display_name": row.updated_by_display_name, "updated_at": row.updated_at}
    finally:
        session.close()
