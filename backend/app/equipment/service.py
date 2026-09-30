"""PR-4 Equipment-Lese-Services (org-scoped)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Contract, ContractEquipment, Equipment
from app.equipment.models import (
    EquipmentContractLink,
    EquipmentDetail,
    EquipmentSummary,
)


def list_equipment(
    session: Session,
    *,
    organization_id,
    search: Optional[str] = None,
    limit: int = 200,
    hospital_id=None,
    department_id=None,
) -> list[EquipmentSummary]:
    """Liste kanonischer Geräte einer Organisation mit Vertrags-Anzahl."""
    contract_count = (
        select(func.count(ContractEquipment.id))
        .join(Contract, Contract.id == ContractEquipment.contract_id)
        .where(
            (ContractEquipment.organization_id == organization_id)
            & (Contract.organization_id == organization_id)
            & (Contract.lifecycle_state == "active")
            & (Contract.is_archived.is_(False))
            & (ContractEquipment.extraction_id == Contract.accepted_extraction_id)
            & (ContractEquipment.equipment_id == Equipment.id)
        )
        .scalar_subquery()
        .label("contract_count")
    )
    stmt = (
        select(Equipment, contract_count)
        .where(Equipment.organization_id == organization_id)
        .order_by(Equipment.device_name.asc().nulls_last(), Equipment.id)
        .limit(limit)
    )
    if department_id is not None:
        stmt = stmt.where(Equipment.department_id == department_id)
    elif hospital_id is not None:
        stmt = stmt.where(Equipment.hospital_id == hospital_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            Equipment.device_name.ilike(like)
            | Equipment.model.ilike(like)
            | Equipment.manufacturer.ilike(like)
            | Equipment.serial_number.ilike(like)
            | Equipment.inventory_number.ilike(like)
        )
    out = []
    for equip, cnt in session.execute(stmt):
        out.append(
            EquipmentSummary(
                id=str(equip.id),
                device_name=equip.device_name,
                manufacturer=equip.manufacturer,
                model=equip.model,
                serial_number=equip.serial_number,
                inventory_number=equip.inventory_number,
                equipment_type=equip.equipment_type,
                equipment_category=equip.equipment_category,
                location=equip.location,
                department=equip.department,
                identification_quality=equip.identification_quality,
                contract_count=int(cnt or 0),
            )
        )
    return out


def get_equipment_detail(
    session: Session,
    *,
    organization_id,
    equipment_id,
) -> Optional[EquipmentDetail]:
    """Ein Gerät mit allen verknüpften Verträgen (n:m), strikt org-gebunden."""
    equip = session.scalars(
        select(Equipment).where(
            (Equipment.organization_id == organization_id)
            & (Equipment.id == equipment_id)
        )
    ).first()
    if equip is None:
        return None
    rows = session.execute(
        select(ContractEquipment, Contract)
        .join(Contract, Contract.id == ContractEquipment.contract_id)
        .where(
            (ContractEquipment.organization_id == organization_id)
            & (ContractEquipment.equipment_id == equip.id)
            & (Contract.organization_id == organization_id)
            & (Contract.lifecycle_state == "active")
            & (Contract.is_archived.is_(False))
            & (ContractEquipment.extraction_id == Contract.accepted_extraction_id)
        )
        .order_by(ContractEquipment.relationship_quality)
    ).all()
    links = [
        EquipmentContractLink(
            contract_id=str(ce.contract_id),
            supplier=c.supplier,
            contract_number=c.contract_number,
            relationship_quality=ce.relationship_quality,
            requires_review=ce.requires_review,
            service_scope=ce.service_scope,
        )
        for ce, c in rows
    ]
    return EquipmentDetail(
        id=str(equip.id),
        device_name=equip.device_name,
        manufacturer=equip.manufacturer,
        model=equip.model,
        serial_number=equip.serial_number,
        inventory_number=equip.inventory_number,
        equipment_type=equip.equipment_type,
        equipment_category=equip.equipment_category,
        location=equip.location,
        department=equip.department,
        identification_quality=equip.identification_quality,
        contract_count=len(links),
        contracts=links,
    )
