from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import current_actor
from app.database.models import Contract, Equipment
from app.database.session import create_session
from app.ownership.service import OwnershipError, assign_contract_ownership, assign_equipment_ownership, contract_department_ids

router = APIRouter(prefix="/api/ownership", tags=["ownership"])


class ContractOwnershipUpdate(BaseModel):
    hospital_id: UUID | None = None
    department_ids: list[UUID] = []
    cost_center_id: UUID | None = None


class EquipmentOwnershipUpdate(BaseModel):
    hospital_id: UUID | None = None
    department_id: UUID | None = None
    cost_center_id: UUID | None = None


def _actor(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    if actor.role not in {"admin", "contract_manager"}:
        raise HTTPException(status_code=403, detail="Keine Berechtigung für Eigentumszuordnungen.")
    return actor


@router.patch("/contracts/{contract_id}")
def update_contract_ownership(contract_id: UUID, payload: ContractOwnershipUpdate, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        contract = session.get(Contract, contract_id)
        if contract is None or contract.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        try:
            assign_contract_ownership(session, contract=contract, hospital_id=payload.hospital_id, department_ids=payload.department_ids, cost_center_id=payload.cost_center_id)
        except OwnershipError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        session.commit()
        return {
            "contract_id": str(contract.id),
            "hospital_id": str(contract.hospital_id) if contract.hospital_id else None,
            "department_ids": [str(value) for value in contract_department_ids(session, contract.id)],
            "cost_center_id": str(contract.cost_center_id) if contract.cost_center_id else None,
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
