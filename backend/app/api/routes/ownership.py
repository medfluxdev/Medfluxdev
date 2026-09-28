from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from app.auth.dependencies import current_actor
from app.core.scope_context import current_scope_context
from app.database.models import Account, AccountMembership, Contract, ContractDepartment, Department, Equipment
from app.database.models.activity_log import ActivityLog
from app.database.scope_queries import scoped_contract_ids
from app.database.session import create_session
from app.ownership.service import (
    OwnershipError,
    assign_contract_ownership,
    assign_equipment_ownership,
    contract_department_ids,
)

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
    if actor.role not in {"admin", "contract_manager"} and not actor.is_developer:
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


def _ensure_contract_visible(session, actor, contract: Contract) -> None:
    if actor.role == "admin" or actor.is_developer:
        return
    scope = current_scope_context()
    allowed = scoped_contract_ids(
        session,
        actor.organization_id,
        scope.hospital_id,
        scope.department_id,
    )
    if allowed is not None and contract.id not in allowed:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")


def _ensure_equipment_visible(actor, equipment: Equipment) -> None:
    if actor.role == "admin" or actor.is_developer:
        return
    scope = current_scope_context()
    if scope.department_id is not None and equipment.department_id != scope.department_id:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
    if scope.department_id is None and scope.hospital_id is not None and equipment.hospital_id != scope.hospital_id:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")


def _log(session, actor, *, event_name: str, object_type: str, object_id: UUID, context_data: dict | None = None) -> None:
    scope = current_scope_context()
    session.add(
        ActivityLog(
            organization_id=actor.organization_id,
            hospital_id=scope.hospital_id,
            department_id=scope.department_id,
            account_id=actor.account_id,
            display_name_snapshot=actor.display_name,
            role_snapshot="developer" if actor.is_developer else actor.role,
            event_name=event_name,
            object_type=object_type,
            object_id=object_id,
            context_data=context_data,
        )
    )


@router.get("/assignees")
def list_assignees(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        stmt = (
            select(Account, AccountMembership)
            .join(AccountMembership, AccountMembership.account_id == Account.id)
            .where(
                (Account.is_active.is_(True))
                & (AccountMembership.organization_id == actor.organization_id)
                & (AccountMembership.is_active.is_(True))
            )
        )
        if actor.role != "admin" and not actor.is_developer:
            scope = current_scope_context()
            if scope.hospital_id is not None:
                stmt = stmt.where(AccountMembership.hospital_id == scope.hospital_id)
            if scope.department_id is not None:
                stmt = stmt.where(AccountMembership.department_id == scope.department_id)
        rows = session.execute(stmt.order_by(Account.display_name.asc(), Account.login_name.asc())).all()
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
        _ensure_contract_visible(session, actor, contract)
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
        _ensure_contract_visible(session, actor, contract)
        # The legacy endpoint replaces every link. Once roles are classified,
        # fail closed instead of silently destroying explicit responsibility.
        if session.scalar(select(ContractDepartment.id).where(
            ContractDepartment.contract_id == contract.id,
            ContractDepartment.organization_id == actor.organization_id,
            ContractDepartment.relation_role.is_not(None),
        ).limit(1)) is not None:
            raise HTTPException(status_code=409, detail="Explizite Abteilungsrollen vorhanden; Rollen zuerst gesondert verwalten.")
        _validate_responsible(session, actor.organization_id, payload.responsible_account_id)
        before = {
            "hospital_id": str(contract.hospital_id) if contract.hospital_id else None,
            "department_ids": [str(value) for value in contract_department_ids(session, contract.id)],
            "cost_center_id": str(contract.cost_center_id) if contract.cost_center_id else None,
            "responsible_account_id": str(contract.responsible_account_id) if contract.responsible_account_id else None,
        }
        try:
            assign_contract_ownership(
                session,
                contract=contract,
                hospital_id=payload.hospital_id,
                department_ids=payload.department_ids,
                cost_center_id=payload.cost_center_id,
            )
        except OwnershipError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        session.execute(
            text("UPDATE contract SET responsible_account_id = :account_id WHERE id = :contract_id"),
            {"account_id": payload.responsible_account_id, "contract_id": contract.id},
        )
        after = {
            "hospital_id": str(contract.hospital_id) if contract.hospital_id else None,
            "department_ids": [str(value) for value in contract_department_ids(session, contract.id)],
            "cost_center_id": str(contract.cost_center_id) if contract.cost_center_id else None,
            "responsible_account_id": str(payload.responsible_account_id) if payload.responsible_account_id else None,
        }
        _log(
            session,
            actor,
            event_name="contract.ownership_updated",
            object_type="contract",
            object_id=contract.id,
            context_data={"before": before, "after": after},
        )
        session.commit()
        return {"contract_id": str(contract.id), **after, "scope_type": contract.scope_type}
    finally:
        session.close()




class ContractDepartmentRolesUpdate(BaseModel):
    """Explicit role assignment. Historical unclassified links remain until selected."""
    responsible_department_id: UUID
    beneficiary_department_ids: list[UUID] = Field(default_factory=list)


@router.get("/contracts/{contract_id}/department-roles")
def get_contract_department_roles(contract_id: UUID, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        contract = session.get(Contract, contract_id)
        if contract is None or contract.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        _ensure_contract_visible(session, actor, contract)
        links = session.scalars(select(ContractDepartment).where(
            ContractDepartment.organization_id == actor.organization_id,
            ContractDepartment.contract_id == contract.id,
        )).all()
        return {
            "contract_id": str(contract.id),
            "responsible_department_id": next((str(x.department_id) for x in links if x.relation_role == "responsible"), None),
            "beneficiary_department_ids": sorted(str(x.department_id) for x in links if x.relation_role == "beneficiary"),
            "unclassified_department_ids": sorted(str(x.department_id) for x in links if x.relation_role is None),
        }
    finally:
        session.close()


@router.put("/contracts/{contract_id}/department-roles")
def put_contract_department_roles(contract_id: UUID, payload: ContractDepartmentRolesUpdate, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        # Lock the contract row so competing role edits serialize. A role change
        # cannot silently change the contract's hospital or historic links.
        contract = session.scalar(select(Contract).where(
            Contract.id == contract_id, Contract.organization_id == actor.organization_id,
        ).with_for_update())
        if contract is None:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        _ensure_contract_visible(session, actor, contract)
        if contract.hospital_id is None:
            raise HTTPException(status_code=422, detail="Vertrag benötigt zuerst ein Krankenhaus.")
        beneficiaries = payload.beneficiary_department_ids
        requested = [payload.responsible_department_id, *beneficiaries]
        if len(set(requested)) != len(requested):
            raise HTTPException(status_code=422, detail="Abteilungen dürfen keine doppelten Rollen erhalten.")
        departments = session.scalars(select(Department).where(
            Department.id.in_(requested),
            Department.organization_id == actor.organization_id,
            Department.hospital_id == contract.hospital_id,
            Department.is_active.is_(True),
        )).all()
        if len(departments) != len(requested):
            raise HTTPException(status_code=422, detail="Alle Abteilungen müssen aktiv und im selben Krankenhaus sein.")
        links = session.scalars(select(ContractDepartment).where(
            ContractDepartment.contract_id == contract.id,
            ContractDepartment.organization_id == actor.organization_id,
        )).all()
        # Keep historic unclassified associations, except those explicitly selected.
        by_department = {link.department_id: link for link in links}
        # Explicitly deselected classified links are removed. Historical NULL
        # links are never guessed or deleted by this role-specific endpoint.
        for link in links:
            if link.relation_role is not None:
                if link.department_id not in requested:
                    session.delete(link)
                else:
                    link.relation_role = None
        session.flush()  # Release partial-unique responsible slot before reassigning.
        for department_id in requested:
            link = by_department.get(department_id)
            if link is None:
                link = ContractDepartment(
                    organization_id=actor.organization_id,
                    contract_id=contract.id,
                    department_id=department_id,
                )
                session.add(link)
            link.relation_role = "responsible" if department_id == payload.responsible_department_id else "beneficiary"
        _log(session, actor, event_name="contract.department_roles_updated",
             object_type="contract", object_id=contract.id,
             context_data={"responsible_department_id": str(payload.responsible_department_id),
                           "beneficiary_department_ids": [str(x) for x in beneficiaries]})
        response = get_contract_department_roles_payload(payload, contract.id, links)
        session.commit()
        return response
    finally:
        session.close()


def get_contract_department_roles_payload(payload: ContractDepartmentRolesUpdate, contract_id: UUID, old_links: list[ContractDepartment]):
    chosen = {payload.responsible_department_id, *payload.beneficiary_department_ids}
    return {
        "contract_id": str(contract_id),
        "responsible_department_id": str(payload.responsible_department_id),
        "beneficiary_department_ids": sorted(str(x) for x in payload.beneficiary_department_ids),
        "unclassified_department_ids": sorted(str(x.department_id) for x in old_links if x.relation_role is None and x.department_id not in chosen),
    }

@router.patch("/equipment/{equipment_id}")
def update_equipment_ownership(equipment_id: UUID, payload: EquipmentOwnershipUpdate, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        equipment = session.get(Equipment, equipment_id)
        if equipment is None or equipment.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
        _ensure_equipment_visible(actor, equipment)
        before = {
            "hospital_id": str(equipment.hospital_id) if equipment.hospital_id else None,
            "department_id": str(equipment.department_id) if equipment.department_id else None,
            "cost_center_id": str(equipment.cost_center_id) if equipment.cost_center_id else None,
        }
        try:
            assign_equipment_ownership(
                session,
                equipment=equipment,
                hospital_id=payload.hospital_id,
                department_id=payload.department_id,
                cost_center_id=payload.cost_center_id,
            )
        except OwnershipError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        after = {
            "hospital_id": str(equipment.hospital_id) if equipment.hospital_id else None,
            "department_id": str(equipment.department_id) if equipment.department_id else None,
            "cost_center_id": str(equipment.cost_center_id) if equipment.cost_center_id else None,
        }
        _log(
            session,
            actor,
            event_name="equipment.ownership_updated",
            object_type="equipment",
            object_id=equipment.id,
            context_data={"before": before, "after": after},
        )
        session.commit()
        return {"equipment_id": str(equipment.id), **after}
    finally:
        session.close()
