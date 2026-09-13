"""Contract-aware billing intelligence from accepted calculation state."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.contract_intelligence.invoice import ContractCharge, InvoiceLine, reconcile_invoice, value_leakage
from app.contracts.calculation.models import CalculationStatus, ContractCalculationResult
from app.core.scope_context import current_scope_context
from app.database.models.calculation import CalculationRun
from app.database.models.contract import Contract
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/intelligence/billing", tags=["intelligence-billing"])


def _load_contract(session, organization_slug: str, contract_id: UUID):
    org = get_organization(session, organization_slug)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    contract = session.scalar(select(Contract).where(
        Contract.id == contract_id,
        Contract.organization_id == org.id,
        Contract.lifecycle_state == "active",
    ))
    if contract is None:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    scope = current_scope_context()
    visible = scoped_contract_ids(session, org.id, scope.hospital_id, scope.department_id)
    if visible is not None and contract_id not in visible:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    return org, contract


def _accepted_result(session, org_id: UUID, contract: Contract):
    if not contract.accepted_calculation_run_id:
        return None
    run = session.get(CalculationRun, contract.accepted_calculation_run_id)
    if run is None or run.organization_id != org_id or not run.result_snapshot:
        return None
    try:
        return ContractCalculationResult.model_validate(run.result_snapshot)
    except Exception:
        return None


def _charges(result: ContractCalculationResult | None) -> list[ContractCharge]:
    if result is None:
        return []
    items: list[ContractCharge] = []
    for label, money in (
        ("Jährliche wiederkehrende Kosten", result.costs.normalized_recurring.annual),
        ("Monatliche wiederkehrende Kosten", result.costs.normalized_recurring.monthly),
    ):
        if money.value is not None and money.currency and money.status in {CalculationStatus.CALCULATED, CalculationStatus.EXPLICIT}:
            items.append(ContractCharge(label=label, amount=money.value, currency=money.currency, charge_type="fixed", applicable=True))
    for category in result.costs.category_totals:
        if category.amount is not None and category.currency and category.status in {CalculationStatus.CALCULATED, CalculationStatus.EXPLICIT}:
            items.append(ContractCharge(label=category.label, amount=category.amount, currency=category.currency, charge_type="fixed", applicable=True))
    return items


@router.get("/contracts/{contract_id}/basis")
def billing_basis(organization_slug: str, contract_id: UUID):
    session = create_session()
    try:
        org, contract = _load_contract(session, organization_slug, contract_id)
        items = _charges(_accepted_result(session, org.id, contract))
        return {"contract_id": str(contract_id), "available": bool(items), "items": [item.model_dump(mode="json") for item in items]}
    finally:
        session.close()


class ReconcileRequest(BaseModel):
    lines: list[InvoiceLine] = Field(min_length=1)


@router.post("/contracts/{contract_id}/reconcile")
def reconcile_contract_invoice(payload: ReconcileRequest, organization_slug: str, contract_id: UUID):
    session = create_session()
    try:
        org, contract = _load_contract(session, organization_slug, contract_id)
        charges = _charges(_accepted_result(session, org.id, contract))
        if not charges:
            return {"contract_id": str(contract_id), "billing_basis": [], "findings": [], "value_leakage": {}, "requires_review": True, "message": "Keine eindeutig akzeptierte Abrechnungsbasis verfügbar."}
        findings = reconcile_invoice(payload.lines, charges)
        leakage = value_leakage(findings)
        return {
            "contract_id": str(contract_id),
            "billing_basis": [item.model_dump(mode="json") for item in charges],
            "findings": [item.model_dump(mode="json") for item in findings],
            "value_leakage": {currency: str(amount) for currency, amount in leakage.items()},
            "requires_review": any(item.requires_review for item in findings),
            "message": None,
        }
    finally:
        session.close()
