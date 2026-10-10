"""Vertragsregeln ("Playbooks"): pflegen (Administration) und je Vertrag pruefen (alle)."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.core.clock import today_local
from app.auth.dependencies import current_actor
from app.auth.permissions import is_admin, require
from app.core.scope_context import current_scope_context
from app.database.models import ActivityLog, Contract
from app.database.models.register import ContractRule
from app.database.scope_queries import scoped_contract_ids
from app.database.session import create_session
from app.reports.grid import build_rows
from app.rules import service
from app.rules.service import RuleError

router = APIRouter(tags=["rules"])


class RuleValues(BaseModel):
    values: dict[str, Any]


def _log(session, actor, event_name: str, row: ContractRule, context: dict) -> None:
    scope = current_scope_context()
    session.add(ActivityLog(
        organization_id=actor.organization_id, hospital_id=scope.hospital_id, department_id=scope.department_id,
        account_id=actor.account_id, display_name_snapshot=actor.display_name,
        role_snapshot="developer" if getattr(actor, "is_developer", False) else actor.role,
        event_name=event_name, object_type="contract_rule", object_id=row.id, context_data=context,
    ))


def _http(exc: RuleError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail_de)


@router.get("/api/rules")
def list_rules(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        rows = session.scalars(
            select(ContractRule).where(ContractRule.organization_id == actor.organization_id)
            .order_by(ContractRule.sort_order, ContractRule.label)
        ).all()
        return {"items": [service.rule_payload(row) for row in rows], **service.kinds_payload()}
    finally:
        session.close()


@router.post("/api/rules")
def create_rule(payload: RuleValues, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    require(actor, "catalog.admin", "Nur Administratoren können Vertragsregeln pflegen.")
    session = create_session()
    try:
        try:
            row = service.create_rule(session, actor.organization_id, payload.values)
        except RuleError as exc:
            session.rollback()
            raise _http(exc)
        _log(session, actor, "catalog.rule_created", row, {"label": row.label, "rule_kind": row.rule_kind})
        session.commit()
        return service.rule_payload(row)
    finally:
        session.close()


@router.patch("/api/rules/{rule_id}")
def update_rule(rule_id: UUID, payload: RuleValues, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    require(actor, "catalog.admin", "Nur Administratoren können Vertragsregeln pflegen.")
    session = create_session()
    try:
        row = session.get(ContractRule, rule_id)
        if row is None or row.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Regel nicht gefunden.")
        before = service.rule_payload(row)
        try:
            service.update_rule(session, row, payload.values)
        except RuleError as exc:
            session.rollback()
            raise _http(exc)
        after = service.rule_payload(row)
        changed = {key: {"before": before[key], "after": after[key]} for key in after if key != "updated_at" and before.get(key) != after[key]}
        _log(session, actor, "catalog.rule_updated", row, {"fields": changed})
        session.commit()
        return service.rule_payload(row)
    finally:
        session.close()


@router.get("/api/contracts/{contract_id}/rules")
def contract_rules(contract_id: UUID, request: Request, organization_slug: str):
    """Ergebnis aller aktiven Regeln fuer einen Vertrag (nur sichtbare Vertraege)."""
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        contract = session.scalars(
            select(Contract).where(Contract.id == contract_id, Contract.organization_id == actor.organization_id)
        ).first()
        if contract is None:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        if not is_admin(actor):
            scope = current_scope_context()
            allowed = scoped_contract_ids(session, actor.organization_id, scope.hospital_id, scope.department_id)
            if allowed is not None and contract.id not in allowed:
                raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
        rows = build_rows(session, actor.organization_id, {contract.id}, today_local(), archived=bool(contract.is_archived))
        annual_cost = rows[0].values.get("annual_cost") if rows else None
        results = service.evaluate_all(service.active_rules(session, actor.organization_id), contract, annual_cost)
        return {
            "status": service.summary_status(results),
            "items": [item.payload() for item in results],
        }
    finally:
        session.close()
