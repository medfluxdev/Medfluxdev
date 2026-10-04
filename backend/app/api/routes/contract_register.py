"""Vertragsregister-API (H1/H6): Stammdaten lesen/bearbeiten, KI-Vorschlaege
uebernehmen, manuell anlegen, Statuswechsel, Bemerkungen."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.dependencies import current_actor
from app.core.scope_context import current_scope_context
from app.database.models import Contract, Department, Hospital
from app.database.scope_queries import scoped_contract_ids
from app.database.session import create_session
from app.register import catalogs
from app.register.service import (
    RegisterActor,
    RegisterError,
    accept_ai_proposal,
    add_remark,
    build_register,
    contract_hospitals,
    create_manual_contract,
    ensure_synced,
    list_remarks,
    load_extracted,
    set_contract_hospitals,
    transition_status,
    update_register,
)

router = APIRouter(prefix="/api/contracts", tags=["contract-register"])

WRITE_ROLES = frozenset({"admin", "contract_manager"})


class RegisterUpdate(BaseModel):
    changes: dict[str, Any] = Field(default_factory=dict)
    confirm: list[str] = Field(default_factory=list)


class ContractCreate(BaseModel):
    hospital_id: Optional[UUID] = None
    values: dict[str, Any] = Field(default_factory=dict)


class StatusTransition(BaseModel):
    target: str
    effective_date: Optional[date] = None
    terminated_on: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)
    acknowledge_unreviewed: bool = False


class HospitalAssignment(BaseModel):
    hospital_ids: list[UUID] = Field(default_factory=list)
    primary_hospital_id: Optional[UUID] = None


class RemarkCreate(BaseModel):
    body: str = Field(max_length=10000)


def _register_actor(request: Request, organization_slug: str) -> RegisterActor:
    actor = current_actor(request, organization_slug)
    scope = current_scope_context()
    return RegisterActor(
        organization_id=actor.organization_id,
        account_id=actor.account_id,
        display_name=actor.display_name,
        role=actor.role,
        is_developer=bool(getattr(actor, "is_developer", False)),
        hospital_id=scope.hospital_id,
        department_id=scope.department_id,
    )


def _require_write(actor: RegisterActor) -> None:
    if actor.role not in WRITE_ROLES and not actor.is_developer:
        raise HTTPException(status_code=403, detail="Keine Berechtigung zum Bearbeiten von Verträgen.")


def _contract(session, actor: RegisterActor, contract_id: UUID, *, for_update: bool = False) -> Contract:
    stmt = select(Contract).where(Contract.id == contract_id, Contract.organization_id == actor.organization_id)
    if for_update:
        stmt = stmt.with_for_update()
    contract = session.scalars(stmt).first()
    if contract is None:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    if actor.role != "admin" and not actor.is_developer:
        scope = current_scope_context()
        allowed = scoped_contract_ids(session, actor.organization_id, scope.hospital_id, scope.department_id)
        if allowed is not None and contract.id not in allowed:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    return contract


def _http(exc: RegisterError) -> HTTPException:
    detail: Any = exc.detail_de
    if exc.field_key or exc.missing:
        detail = {"message": exc.detail_de, "field": exc.field_key, "missing": exc.missing}
    return HTTPException(status_code=exc.status_code, detail=detail)


def _register_payload(session, contract: Contract, actor: RegisterActor) -> dict:
    data = build_register(session, contract, actor)
    if contract.partner_id is None and contract.supplier:
        data["partner_suggestions"] = catalogs.similar_partners(session, actor.organization_id, contract.supplier, limit=3)
    else:
        data["partner_suggestions"] = []
    data["type_suggestion"] = None
    if contract.contract_type_id is None:
        ai_type = None
        if contract.accepted_extraction_id is not None:
            extracted = load_extracted(session, contract.accepted_extraction_id)
            ai_type = extracted.identity.contract_type.value if extracted else None
        data["type_suggestion"] = catalogs.type_suggestion(
            session, actor.organization_id, ai_type, contract.short_description
        )
    data["storage_location_label"] = catalogs.lookup_label(
        session, actor.organization_id, "storage_location", contract.storage_location_code
    )
    return data


@router.post("")
def create_contract(payload: ContractCreate, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        hospital_id = payload.hospital_id or (actor.hospital_id if actor.role != "admin" else None)
        department_id = actor.department_id if actor.role != "admin" and not actor.is_developer else None
        if department_id is not None:
            department = session.get(Department, department_id)
            if department is None or department.organization_id != actor.organization_id:
                raise HTTPException(status_code=403, detail="Abteilung ist nicht verfügbar.")
            hospital_id = department.hospital_id
        if hospital_id is not None:
            hospital = session.get(Hospital, hospital_id)
            if hospital is None or hospital.organization_id != actor.organization_id:
                raise HTTPException(status_code=422, detail="Krankenhaus ist nicht verfügbar.")
            if actor.role != "admin" and not actor.is_developer and actor.hospital_id not in (None, hospital_id):
                raise HTTPException(status_code=403, detail="Keine Berechtigung für dieses Krankenhaus.")
        try:
            contract = create_manual_contract(
                session, actor=actor, values=payload.values, hospital_id=hospital_id, department_id=department_id
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.get("/{contract_id}/register")
def get_register(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        if ensure_synced(session, contract):
            session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.patch("/{contract_id}/register")
def patch_register(contract_id: UUID, payload: RegisterUpdate, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            update_register(session, contract=contract, actor=actor, changes=payload.changes, confirm=payload.confirm)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.post("/{contract_id}/register/proposals/{field_key}/accept")
def accept_proposal(contract_id: UUID, field_key: str, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            accept_ai_proposal(session, contract=contract, actor=actor, field_key=field_key)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.post("/{contract_id}/status")
def change_status(contract_id: UUID, payload: StatusTransition, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            transition_status(
                session,
                contract=contract,
                actor=actor,
                target=payload.target,
                effective_date=payload.effective_date,
                terminated_on=payload.terminated_on,
                note=payload.note,
                acknowledge_unreviewed=payload.acknowledge_unreviewed,
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.get("/{contract_id}/remarks")
def get_remarks(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        return {"items": list_remarks(session, contract.id)}
    finally:
        session.close()


@router.post("/{contract_id}/remarks")
def post_remark(contract_id: UUID, payload: RemarkCreate, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        try:
            add_remark(session, contract=contract, actor=actor, body=payload.body)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": list_remarks(session, contract.id)}
    finally:
        session.close()


@router.get("/{contract_id}/hospitals")
def get_hospitals(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        return {"items": contract_hospitals(session, contract.id)}
    finally:
        session.close()


@router.put("/{contract_id}/hospitals")
def put_hospitals(contract_id: UUID, payload: HospitalAssignment, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        if actor.role != "admin" and not actor.is_developer and actor.hospital_id is not None:
            requested = set(payload.hospital_ids) | ({payload.primary_hospital_id} - {None})
            if requested - {actor.hospital_id}:
                raise HTTPException(status_code=403, detail="Nur Administratoren können weitere Gesellschaften zuordnen.")
        try:
            set_contract_hospitals(
                session,
                contract=contract,
                actor=actor,
                hospital_ids=payload.hospital_ids,
                primary_hospital_id=payload.primary_hospital_id,
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": contract_hospitals(session, contract.id)}
    finally:
        session.close()
