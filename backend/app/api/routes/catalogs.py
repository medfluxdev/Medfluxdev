"""Kataloge-API (H2): Vertragspartner, Vertragstypen/-kategorien,
Auswahllisten, Standardkatalog und Nummernkreis."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.auth.dependencies import current_actor
from app.auth.permissions import is_admin, require
from app.database.scope_queries import scoped_contract_ids
from app.core.scope_context import current_scope_context
from app.database.models import ActivityLog, Contract
from app.database.models.register import (
    CatalogContractCategory,
    CatalogContractType,
    ContractPartner,
    LookupValue,
    NumberAllocation,
    NumberRange,
)
from app.database.session import create_session
from app.register import catalogs
from app.register.catalogs import CatalogError
from app.register.service import (
    CONTRACT_NUMBER_PURPOSE,
    RegisterError,
    format_number,
    locked_number_range,
    reserve_contract_numbers,
)

router = APIRouter(prefix="/api/catalogs", tags=["catalogs"])



class PartnerCreate(BaseModel):
    values: dict[str, Any]
    allow_similar: bool = False


class CatalogEntry(BaseModel):
    values: dict[str, Any]


class NumberReservation(BaseModel):
    values: list[int] = Field(min_length=1, max_length=500)
    note: Optional[str] = Field(default=None, max_length=255)


class NumberRangeUpdate(BaseModel):
    prefix: Optional[str] = Field(default=None, max_length=16)
    padding: Optional[int] = Field(default=None, ge=1, le=12)
    next_value: Optional[int] = Field(default=None, ge=1)


def _actor(request: Request, organization_slug: str):
    return current_actor(request, organization_slug)


def _require_admin(actor) -> None:
    require(actor, "catalog.admin", "Nur Administratoren können Kataloge pflegen.")


def _require_partner_write(actor) -> None:
    require(actor, "partner.edit", "Keine Berechtigung zum Pflegen von Vertragspartnern.")


def _log(session, actor, event_name: str, object_type: str, object_id, context: Optional[dict] = None) -> None:
    scope = current_scope_context()
    session.add(
        ActivityLog(
            organization_id=actor.organization_id,
            hospital_id=scope.hospital_id,
            department_id=scope.department_id,
            account_id=actor.account_id,
            display_name_snapshot=actor.display_name,
            role_snapshot="developer" if getattr(actor, "is_developer", False) else actor.role,
            event_name=event_name,
            object_type=object_type,
            object_id=object_id,
            context_data=context,
        )
    )


_SNAPSHOT_FIELDS = ("code", "label", "description", "is_active", "is_confidential", "sort_order", "retention_years", "field_key")


def _snapshot(row) -> dict:
    return {key: getattr(row, key) for key in _SNAPSHOT_FIELDS if hasattr(row, key)}


def _diff(before: dict, after: dict) -> dict:
    return {key: {"before": before.get(key), "after": value} for key, value in after.items() if before.get(key) != value}


def _own(session, model, row_id: UUID, organization_id: UUID):
    row = session.get(model, row_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    return row


def _http(exc: CatalogError | RegisterError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail_de)


# --------------------------------------------------------------------------- defaults


@router.post("/defaults")
def load_defaults(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        created = catalogs.ensure_defaults(session, actor.organization_id)
        _log(session, actor, "catalog.defaults_loaded", "organization", actor.organization_id, created)
        session.commit()
        return {"created": created}
    finally:
        session.close()


def _ensure_seeded(session, organization_id) -> None:
    """Standardkatalog anlegen bzw. neu eingefuehrte Auswahllisten ergaenzen."""
    has_types = session.scalar(
        select(func.count(CatalogContractType.id)).where(CatalogContractType.organization_id == organization_id)
    )
    present = set(session.scalars(
        select(LookupValue.field_key).where(LookupValue.organization_id == organization_id).distinct()
    ).all())
    if not has_types or set(catalogs.LOOKUP_FIELD_KEYS) - present:
        catalogs.ensure_defaults(session, organization_id)
        session.commit()


# --------------------------------------------------------------------------- partners


@router.get("/partners")
def list_partners(
    request: Request,
    organization_slug: str,
    q: Optional[str] = Query(default=None, max_length=200),
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        stmt = select(ContractPartner).where(ContractPartner.organization_id == actor.organization_id)
        if not include_inactive:
            stmt = stmt.where(ContractPartner.is_active.is_(True))
        if q and q.strip():
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    ContractPartner.short_name.ilike(pattern),
                    ContractPartner.name1.ilike(pattern),
                    ContractPartner.name2.ilike(pattern),
                    ContractPartner.city.ilike(pattern),
                )
            )
        total = session.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = session.scalars(stmt.order_by(func.lower(ContractPartner.short_name)).offset(offset).limit(limit)).all()
        counts = dict(
            session.execute(
                select(Contract.partner_id, func.count(Contract.id))
                .where(Contract.partner_id.in_([row.id for row in rows]))
                .group_by(Contract.partner_id)
            ).all()
        ) if rows else {}
        return {
            "total": total,
            "items": [{**catalogs.partner_payload(row), "contract_count": counts.get(row.id, 0)} for row in rows],
        }
    finally:
        session.close()


@router.get("/partners/duplicates")
def partner_duplicates(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        return {"groups": catalogs.duplicate_groups(session, actor.organization_id)}
    finally:
        session.close()


@router.get("/partners/similar")
def partner_similar(request: Request, organization_slug: str, name: str = Query(min_length=1, max_length=255)):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        return {"items": catalogs.similar_partners(session, actor.organization_id, name)}
    finally:
        session.close()


@router.post("/partners")
def create_partner(payload: PartnerCreate, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_partner_write(actor)
    session = create_session()
    try:
        try:
            row, similar = catalogs.create_partner(
                session, actor.organization_id, payload.values, allow_similar=payload.allow_similar
            )
        except CatalogError as exc:
            session.rollback()
            if exc.similar:
                raise HTTPException(status_code=409, detail={"message": exc.detail_de, "similar": exc.similar})
            raise _http(exc)
        _log(session, actor, "partner.created", "contract_partner", row.id, {"short_name": row.short_name})
        session.commit()
        return {**catalogs.partner_payload(row), "similar": similar}
    finally:
        session.close()


@router.get("/partners/{partner_id}")
def get_partner(partner_id: UUID, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        row = _own(session, ContractPartner, partner_id, actor.organization_id)
        stmt = (
            select(Contract.id, Contract.register_number, Contract.short_description, Contract.business_status)
            .where(Contract.partner_id == row.id, Contract.organization_id == actor.organization_id)
            .order_by(Contract.register_number)
        )
        if not is_admin(actor):
            scope = current_scope_context()
            allowed = scoped_contract_ids(session, actor.organization_id, scope.hospital_id, scope.department_id)
            if allowed is not None:
                stmt = stmt.where(Contract.id.in_(allowed))
        contracts = session.execute(stmt).all()
        return {
            **catalogs.partner_payload(row),
            "contracts": [
                {"id": str(cid), "register_number": number, "short_description": text, "business_status": status}
                for cid, number, text, status in contracts
            ],
        }
    finally:
        session.close()


@router.patch("/partners/{partner_id}")
def patch_partner(partner_id: UUID, payload: CatalogEntry, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_partner_write(actor)
    session = create_session()
    try:
        row = _own(session, ContractPartner, partner_id, actor.organization_id)
        before = catalogs.partner_payload(row)
        try:
            catalogs.update_partner(session, row, payload.values)
        except CatalogError as exc:
            session.rollback()
            raise _http(exc)
        after = catalogs.partner_payload(row)
        changed = {key: {"before": before[key], "after": after[key]} for key in after if before.get(key) != after[key] and key != "updated_at"}
        _log(session, actor, "partner.updated", "contract_partner", row.id, {"fields": changed})
        session.commit()
        return catalogs.partner_payload(row)
    finally:
        session.close()


# --------------------------------------------------------------------------- types / categories


@router.get("/contract-types")
def list_contract_types(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        _ensure_seeded(session, actor.organization_id)
        return catalogs.list_types_and_categories(session, actor.organization_id)
    finally:
        session.close()


@router.post("/contract-types")
def create_contract_type(payload: CatalogEntry, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        try:
            row = catalogs.upsert_type(session, actor.organization_id, payload.values)
        except CatalogError as exc:
            session.rollback()
            raise _http(exc)
        _log(session, actor, "catalog.contract_type_created", "catalog_contract_type", row.id, {"label": row.label})
        session.commit()
        return catalogs.type_payload(row)
    finally:
        session.close()


@router.patch("/contract-types/{type_id}")
def patch_contract_type(type_id: UUID, payload: CatalogEntry, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        row = _own(session, CatalogContractType, type_id, actor.organization_id)
        before = _snapshot(row)
        try:
            catalogs.upsert_type(session, actor.organization_id, payload.values, row)
        except CatalogError as exc:
            session.rollback()
            raise _http(exc)
        _log(session, actor, "catalog.contract_type_updated", "catalog_contract_type", row.id, {"fields": _diff(before, _snapshot(row))})
        session.commit()
        return catalogs.type_payload(row)
    finally:
        session.close()


@router.post("/contract-categories")
def create_contract_category(payload: CatalogEntry, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        try:
            row = catalogs.upsert_category(session, actor.organization_id, payload.values)
        except CatalogError as exc:
            session.rollback()
            raise _http(exc)
        _log(session, actor, "catalog.contract_category_created", "catalog_contract_category", row.id, {"label": row.label})
        session.commit()
        return catalogs.list_types_and_categories(session, actor.organization_id)
    finally:
        session.close()


@router.patch("/contract-categories/{category_id}")
def patch_contract_category(category_id: UUID, payload: CatalogEntry, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        row = _own(session, CatalogContractCategory, category_id, actor.organization_id)
        before = _snapshot(row)
        try:
            catalogs.upsert_category(session, actor.organization_id, payload.values, row)
        except CatalogError as exc:
            session.rollback()
            raise _http(exc)
        _log(session, actor, "catalog.contract_category_updated", "catalog_contract_category", row.id, {"fields": _diff(before, _snapshot(row))})
        session.commit()
        return catalogs.list_types_and_categories(session, actor.organization_id)
    finally:
        session.close()


# --------------------------------------------------------------------------- lookups


@router.get("/lookups")
def list_lookups(
    request: Request,
    organization_slug: str,
    field_key: Optional[str] = Query(default=None, max_length=48),
    include_inactive: bool = False,
):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        _ensure_seeded(session, actor.organization_id)
        stmt = select(LookupValue).where(LookupValue.organization_id == actor.organization_id)
        if field_key:
            stmt = stmt.where(LookupValue.field_key == field_key)
        if not include_inactive:
            stmt = stmt.where(LookupValue.is_active.is_(True))
        rows = session.scalars(stmt.order_by(LookupValue.field_key, LookupValue.sort_order, LookupValue.label)).all()
        return {"field_keys": list(catalogs.LOOKUP_FIELD_KEYS), "items": [catalogs.lookup_payload(row) for row in rows]}
    finally:
        session.close()


@router.post("/lookups")
def create_lookup(payload: CatalogEntry, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        try:
            row = catalogs.upsert_lookup(session, actor.organization_id, payload.values)
        except CatalogError as exc:
            session.rollback()
            raise _http(exc)
        _log(session, actor, "catalog.lookup_created", "lookup_value", row.id, {"field_key": row.field_key, "label": row.label})
        session.commit()
        return catalogs.lookup_payload(row)
    finally:
        session.close()


@router.patch("/lookups/{lookup_id}")
def patch_lookup(lookup_id: UUID, payload: CatalogEntry, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        row = _own(session, LookupValue, lookup_id, actor.organization_id)
        before = _snapshot(row)
        try:
            catalogs.upsert_lookup(session, actor.organization_id, payload.values, row)
        except CatalogError as exc:
            session.rollback()
            raise _http(exc)
        _log(session, actor, "catalog.lookup_updated", "lookup_value", row.id, {"fields": _diff(before, _snapshot(row))})
        session.commit()
        return catalogs.lookup_payload(row)
    finally:
        session.close()


# --------------------------------------------------------------------------- number range


def _range_payload(session, organization_id) -> dict:
    row = session.scalars(
        select(NumberRange).where(
            NumberRange.organization_id == organization_id, NumberRange.purpose == CONTRACT_NUMBER_PURPOSE
        )
    ).first()
    reserved = session.scalars(
        select(NumberAllocation)
        .where(
            NumberAllocation.organization_id == organization_id,
            NumberAllocation.purpose == CONTRACT_NUMBER_PURPOSE,
            NumberAllocation.state == "reserved",
        )
        .order_by(NumberAllocation.value)
    ).all()
    used = session.scalar(
        select(func.count(NumberAllocation.id)).where(
            NumberAllocation.organization_id == organization_id,
            NumberAllocation.purpose == CONTRACT_NUMBER_PURPOSE,
            NumberAllocation.state == "used",
        )
    )
    return {
        "purpose": CONTRACT_NUMBER_PURPOSE,
        "prefix": row.prefix if row else "",
        "padding": row.padding if row else 6,
        "next_value": row.next_value if row else 1,
        "next_formatted": format_number(row, row.next_value) if row else "000001",
        "used_count": used,
        "reserved": [{"value": item.value, "formatted": item.formatted, "note": item.note} for item in reserved],
    }


@router.get("/number-range")
def get_number_range(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        return _range_payload(session, actor.organization_id)
    finally:
        session.close()


@router.patch("/number-range")
def patch_number_range(payload: NumberRangeUpdate, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        row = locked_number_range(session, actor.organization_id)
        before = {"prefix": row.prefix, "padding": row.padding, "next_value": row.next_value}
        if payload.next_value is not None:
            highest = session.scalar(
                select(func.max(NumberAllocation.value)).where(
                    NumberAllocation.organization_id == actor.organization_id,
                    NumberAllocation.purpose == CONTRACT_NUMBER_PURPOSE,
                    NumberAllocation.state == "used",
                )
            ) or 0
            if payload.next_value <= highest:
                raise HTTPException(status_code=422, detail=f"Die nächste Nummer muss größer als {highest} sein.")
            row.next_value = payload.next_value
        if payload.prefix is not None:
            row.prefix = payload.prefix.strip()
        if payload.padding is not None:
            row.padding = payload.padding
        _log(session, actor, "number_range.updated", "number_range", row.id, {"before": before, "after": {
            "prefix": row.prefix, "padding": row.padding, "next_value": row.next_value,
        }})
        session.commit()
        return _range_payload(session, actor.organization_id)
    finally:
        session.close()


@router.post("/number-range/reserve")
def reserve_numbers(payload: NumberReservation, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_admin(actor)
    session = create_session()
    try:
        try:
            reserved = reserve_contract_numbers(
                session, organization_id=actor.organization_id, values=payload.values,
                account_id=actor.account_id, note=payload.note,
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        _log(session, actor, "number_range.reserved", "organization", actor.organization_id, {"values": reserved})
        session.commit()
        return _range_payload(session, actor.organization_id)
    finally:
        session.close()
