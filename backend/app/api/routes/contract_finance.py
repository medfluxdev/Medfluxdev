"""Finanzdaten eines Vertrags (H4)."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.routes.contract_register import _contract, _register_actor, _require_write
from app.database.session import create_session
from app.register.service import log_activity
from app.finance.service import (
    FinanceError,
    accept_suggestion,
    create_entry,
    create_service,
    delete_entry,
    delete_service,
    dismiss_suggestion,
    export_csv,
    finance_payload,
    set_allocations,
    update_entry,
    update_service,
)

router = APIRouter(prefix="/api/contracts", tags=["contract-finance"])


class Values(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class Allocations(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)


def _http(exc: FinanceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail_de)


def _write(request: Request, organization_slug: str, contract_id: UUID, action) -> dict:
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            action(session, contract, actor)
        except FinanceError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return finance_payload(session, contract)
    finally:
        session.close()


@router.get("/{contract_id}/finance")
def get_finance(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        return finance_payload(session, _contract(session, actor, contract_id))
    finally:
        session.close()


@router.post("/{contract_id}/finance/entries")
def post_entry(contract_id: UUID, payload: Values, request: Request, organization_slug: str):
    return _write(request, organization_slug, contract_id,
                  lambda s, c, a: create_entry(s, contract=c, actor=a, values=payload.values))


@router.patch("/{contract_id}/finance/entries/{entry_id}")
def patch_entry(contract_id: UUID, entry_id: UUID, payload: Values, request: Request, organization_slug: str):
    return _write(request, organization_slug, contract_id,
                  lambda s, c, a: update_entry(s, contract=c, actor=a, entry_id=entry_id, values=payload.values))


@router.delete("/{contract_id}/finance/entries/{entry_id}")
def remove_entry(contract_id: UUID, entry_id: UUID, request: Request, organization_slug: str):
    return _write(request, organization_slug, contract_id,
                  lambda s, c, a: delete_entry(s, contract=c, actor=a, entry_id=entry_id))


@router.post("/{contract_id}/finance/services")
def post_service(contract_id: UUID, payload: Values, request: Request, organization_slug: str):
    return _write(request, organization_slug, contract_id,
                  lambda s, c, a: create_service(s, contract=c, actor=a, values=payload.values))


@router.patch("/{contract_id}/finance/services/{service_id}")
def patch_service(contract_id: UUID, service_id: UUID, payload: Values, request: Request, organization_slug: str):
    return _write(request, organization_slug, contract_id,
                  lambda s, c, a: update_service(s, contract=c, actor=a, service_id=service_id, values=payload.values))


@router.delete("/{contract_id}/finance/services/{service_id}")
def remove_service(contract_id: UUID, service_id: UUID, request: Request, organization_slug: str):
    return _write(request, organization_slug, contract_id,
                  lambda s, c, a: delete_service(s, contract=c, actor=a, service_id=service_id))


@router.put("/{contract_id}/finance/allocations")
def put_allocations(contract_id: UUID, payload: Allocations, request: Request, organization_slug: str):
    return _write(request, organization_slug, contract_id,
                  lambda s, c, a: set_allocations(s, contract=c, actor=a, items=payload.items))


@router.post("/{contract_id}/finance/suggestions/{scope}/{key}/accept")
def accept(contract_id: UUID, scope: str, key: str, payload: Values, request: Request, organization_slug: str):
    return _write(request, organization_slug, contract_id,
                  lambda s, c, a: accept_suggestion(s, contract=c, actor=a, scope=scope, key=key, overrides=payload.values))


@router.post("/{contract_id}/finance/suggestions/{scope}/{key}/dismiss")
def dismiss(contract_id: UUID, scope: str, key: str, request: Request, organization_slug: str):
    return _write(request, organization_slug, contract_id,
                  lambda s, c, a: dismiss_suggestion(s, contract=c, actor=a, scope=scope, key=key))


@router.get("/{contract_id}/finance/export.csv")
def export(
    contract_id: UUID,
    request: Request,
    organization_slug: str,
    expenses: bool = Query(default=True),
    income: bool = Query(default=True),
):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        directions = {name for name, wanted in (("expense", expenses), ("income", income)) if wanted}
        content = "﻿" + export_csv(session, contract, directions)
        filename = f"finanzdaten-{contract.register_number or contract.id}-{date.today().isoformat()}.csv"
        log_activity(session, actor, contract.id, "finance.exported", {"directions": sorted(directions)})
        session.commit()
        return Response(
            content=content.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        session.close()
