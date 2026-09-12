from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.auth.dependencies import current_actor
from app.database.models import Account, AccountMembership, Contract, Equipment
from app.database.session import create_session
from app.ownership.service import OwnershipError, assign_contract_ownership, assign_equipment_ownership, contract_department_ids

router = APIRouter(prefix="/api/ownership", tags=["ownership"])


class ContractOwnershipUpdate(BaseModel):
    hospital_id: UUID | None = None
    department_ids: list[UUID] = Field(default_factory=list)
    cost_center_id: UUID | None = None
    responsible_account_id: UUID | None = None


class EquipmentOwnershipUpdate(BaseModel):
    hospital_id: UUID | None = None
    department_id: UUID | None = None
    cost_center_id: UUID | None = None


def _actor(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    if actor.role not in {"admin", "contract_manager"}:
        raise HTTPException(status_code=403, detail="Keine Berechtigung für Eigentumszuordnungen.")
    return actor


def _validate_responsible(session, organization_id: UUID, account_id: UUID | None) -> None:
    if account_id is None:
        return
    row = session.execute(
        select(Account, AccountMembership)
        .join(AccountMembership, AccountMembership.account_id == Account.id)
        .where(
            (Account.id == account_id)
            & (Account.is_active.is_(True))
            & (AccountMembership.organization_id == organization_id)
            & (AccountMembership.is_active.is_(True))
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=422, detail="Verantwortlicher Benutzer ist für diese Organisation nicht verfügbar.")


@router.get("/assignees")
def list_assignees(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        rows = session.execute(
            select(Account, AccountMembership)
            .join(AccountMembership, AccountMembership.account_id == Account.id)
            .where(
                (Account.is_active.is_(True))
                & (AccountMembership.organization_id == actor.organization_id)
                & (AccountMembership.is_active.is_(True))
            )
            .order_by(Account.display_name.asc(), Account.login_name.asc())
        ).all()
        return {
            "items": [
                {
                    "id": str(account.id),
                    "display_name": account.display_name,
                    "email": account.login_name,
                    "role": membership.role,
                    "hospital_id": str(membership.hospital_id) if membership.hospital_id else None,
                    "department_id": str(membership.department_id) if membership.department_id else None,
                }
                for account, membership in rows
            ]
        }
    finally:
        session.close()


@router.get("/contracts/{contract_id}")
def get_contract_ownership(contract_id: UUID, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        contract = session.get(Contract, contract_id)
        if contract is None or contract.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        responsible_id = session.execute(
            text("SELECT responsible_account_id FROM contract WHERE id = :contract_id"),
            {"contract_id": contract.id},
        ).scalar_one_or_none()
        return {
            "contract_id": str(contract.id),
            "hospital_id": str(contract.hospital_id) if contract.hospital_id else None,
            "department_ids": [str(value) for value in contract_department_ids(session, contract.id)],
            "cost_center_id": str(contract.cost_center_id) if contract.cost_center_id else None,
            "responsible_account_id": str(responsible_id) if responsible_id else None,
            "scope_type": contract.scope_type,
        }
    finally:
        session.close()


@router.patch("/contracts/{contract_id}")
def update_contract_ownership(contract_id: UUID, payload: ContractOwnershipUpdate, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        contract = session.get(Contract, contract_id)
        if contract is None or contract.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        _validate_responsible(session, actor.organization_id, payload.responsible_account_id)
        try:
            assign_contract_ownership(session, contract=contract, hospital_id=payload.hospital_id, department_ids=payload.department_ids, cost_center_id=payload.cost_center_id)
        except OwnershipError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        session.execute(
            text("UPDATE contract SET responsible_account_id = :account_id WHERE id = :contract_id"),
            {"account_id": payload.responsible_account_id, "contract_id": contract.id},
        )
        session.commit()
        return {
            "contract_id": str(contract.id),
            "hospital_id": str(contract.hospital_id) if contract.hospital_id else None,
            "department_ids": [str(value) for value in contract_department_ids(session, contract.id)],
            "cost_center_id": str(contract.cost_center_id) if contract.cost_center_id else None,
            "responsible_account_id": str(payload.responsible_account_id) if payload.responsible_account_id else None,
            "scope_type": contract.scope_type,
        }
    finally:
        session.close()


@router.patch("/equipment/{equipment_id}")
def update_equipment_ownership(equipment_id: UUID, payload: EquipmentOwnershipUpdate, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        equipment = session.get(Equipment, equipment_id)
        if equipment is None or equipment.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
        try:
            assign_equipment_ownership(session, equipment=equipment, hospital_id=payload.hospital_id, department_id=payload.department_id, cost_center_id=payload.cost_center_id)
        except OwnershipError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        session.commit()
        return {
            "equipment_id": str(equipment.id),
            "hospital_id": str(equipment.hospital_id) if equipment.hospital_id else None,
            "department_id": str(equipment.department_id) if equipment.department_id else None,
            "cost_center_id": str(equipment.cost_center_id) if equipment.cost_center_id else None,
        }
    finally:
        session.close()
