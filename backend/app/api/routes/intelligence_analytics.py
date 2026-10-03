"""Scoped analytics facade over MedFlux contract-intelligence primitives.

The endpoints in this module deliberately reuse deterministic backend engines and
accepted persisted state. The frontend never recomputes contractual meaning.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.contract_intelligence.clauses import fingerprint_clause
from app.contract_intelligence.invoice import (
    ContractCharge,
    InvoiceLine,
    reconcile_invoice,
    value_leakage,
)
from app.contract_intelligence.models import PortfolioQuestion
from app.contract_intelligence.portfolio import answer_portfolio_question
from app.contract_intelligence.risk import RiskFinding, summarize_risk
from app.contract_intelligence.scenario import simulate_termination
from app.contract_intelligence.supplier import summarize_supplier_performance
from app.contracts.calculation.models import CalculationStatus, ContractCalculationResult
from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import (
    CalculationReviewFlag,
    CalculationRun,
    Contract,
    ContractEquipment,
    ContractObligationRecord,
    ContractRelationRecord,
    PolicyDecisionRecord,
)
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/intelligence/analytics", tags=["intelligence-analytics"])


def _org(session, slug: str, request: Request):
    org = get_organization(session, slug)
    actor = getattr(request.state, "actor", None)
    if org is None or (actor is None and settings.auth_enabled) or (actor is not None and actor.organization_id != org.id):
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    return org


def _visible_contract_ids(session, organization_id: UUID) -> set[UUID] | None:
    scope = current_scope_context()
    return scoped_contract_ids(
        session,
        organization_id,
        scope.hospital_id,
        scope.department_id,
    )


def _contract(session, organization_id: UUID, contract_id: UUID) -> Contract:
    row = session.scalar(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.organization_id == organization_id,
            Contract.lifecycle_state == "active",
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    visible = _visible_contract_ids(session, organization_id)
    if visible is not None and contract_id not in visible:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    return row


def _severity_from_policy(outcome: str, requires_review: bool) -> str | None:
    value = (outcome or "").lower()
    if value == "fail":
        return "high"
    if value == "warn":
        return "medium"
    if value == "unknown" or requires_review:
        return "medium"
    return None


@router.get("/contracts/{contract_id}/risk")
def contract_risk(request: Request, organization_slug: str, contract_id: UUID):
    """Explain the contract risk from persisted, inspectable findings."""
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        contract = _contract(session, org.id, contract_id)
        findings: list[RiskFinding] = []

        policies = session.scalars(
            select(PolicyDecisionRecord).where(
                PolicyDecisionRecord.organization_id == org.id,
                PolicyDecisionRecord.contract_id == contract_id,
            )
        ).all()
        for row in policies:
            severity = _severity_from_policy(row.outcome, bool(row.requires_review))
            if severity:
                findings.append(
                    RiskFinding(
                        key=f"policy:{row.policy_key}",
                        severity=severity,
                        explanation=row.explanation or f"Policy {row.policy_key}: {row.outcome}",
                        evidence_refs=list(row.evidence_refs or []),
                    )
                )

        obligations = session.scalars(
            select(ContractObligationRecord).where(
                ContractObligationRecord.organization_id == org.id,
                ContractObligationRecord.contract_id == contract_id,
            )
        ).all()
        for row in obligations:
            if row.status == "breached":
                findings.append(
                    RiskFinding(
                        key=f"obligation:{row.obligation_key}",
                        severity="high",
                        explanation=f"Pflicht verletzt: {row.title}",
                        evidence_refs=list(row.evidence_refs or []),
                    )
                )
            elif row.requires_review or row.status in {"proposed", "unknown"}:
                findings.append(
                    RiskFinding(
                        key=f"obligation:{row.obligation_key}",
                        severity="medium",
                        explanation=f"Pflicht muss geprüft werden: {row.title}",
                        evidence_refs=list(row.evidence_refs or []),
                    )
                )

        relations = session.scalars(
            select(ContractRelationRecord).where(
                ContractRelationRecord.organization_id == org.id,
                (
                    (ContractRelationRecord.source_contract_id == contract_id)
                    | (ContractRelationRecord.target_contract_id == contract_id)
                ),
            )
        ).all()
        for row in relations:
            if row.relation_type == "conflicts_with":
                findings.append(
                    RiskFinding(
                        key=f"relation:{row.id}",
                        severity="high",
                        explanation=row.rationale or "Widersprüchliche Vertragsbeziehung erkannt.",
                        evidence_refs=list(row.evidence_refs or []),
                    )
                )
            elif row.requires_review:
                findings.append(
                    RiskFinding(
                        key=f"relation:{row.id}",
                        severity="medium",
                        explanation=row.rationale or "Vertragsbeziehung muss geprüft werden.",
                        evidence_refs=list(row.evidence_refs or []),
                    )
                )

        if contract.accepted_calculation_run_id:
            flags = session.scalars(
                select(CalculationReviewFlag).where(
                    CalculationReviewFlag.organization_id == org.id,
                    CalculationReviewFlag.calculation_run_id == contract.accepted_calculation_run_id,
                )
            ).all()
            severity_map = {"critical": "critical", "warning": "medium", "info": "info"}
            for row in flags:
                findings.append(
                    RiskFinding(
                        key=f"calculation:{row.flag_key}",
                        severity=severity_map.get(row.severity, "medium"),
                        explanation=row.explanation or row.reason or row.flag_key,
                        evidence_refs=[],
                    )
                )

        summary = summarize_risk(findings)
        return {
            "contract_id": str(contract_id),
            "projected_risk_level": contract.risk_level,
            **summary,
            "finding_count": len(findings),
        }
    finally:
        session.close()


class TerminationScenarioRequest(BaseModel):
    termination_date: date


@router.post("/contracts/{contract_id}/termination-scenario")
def termination_scenario(
    request: Request,
    payload: TerminationScenarioRequest,
    organization_slug: str,
    contract_id: UUID,
):
    """Run the conservative deterministic termination-cost scenario."""
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        contract = _contract(session, org.id, contract_id)
        annual_cost = None
        currency = None
        annual_status = None
        annual_inputs: dict[str, Any] = {}
        calculated_end = None
        end_inputs: dict[str, Any] = {}

        if contract.accepted_calculation_run_id:
            run = session.get(CalculationRun, contract.accepted_calculation_run_id)
            if run is not None and run.organization_id == org.id and run.result_snapshot:
                result = ContractCalculationResult.model_validate(run.result_snapshot)
                annual = result.costs.normalized_recurring.annual
                annual_status = annual.status.value
                if annual.status in {CalculationStatus.CALCULATED, CalculationStatus.EXPLICIT}:
                    annual_cost = annual.value
                    currency = annual.currency
                annual_inputs = dict(annual.inputs or {})
                calculated_end = result.dates.calculated_end_date.value
                end_inputs = dict(result.dates.calculated_end_date.inputs or {})

        contract_end = contract.end_date or calculated_end
        simulated = simulate_termination(
            annual_cost=annual_cost,
            termination_date=payload.termination_date,
            contract_end=contract_end,
        )
        return {
            "contract_id": str(contract_id),
            **simulated,
            "currency": currency,
            "basis": {
                "termination_date": payload.termination_date,
                "contract_end": contract_end,
                "annual_cost": annual_cost,
                "annual_cost_status": annual_status,
                "annual_cost_inputs": annual_inputs,
                "contract_end_inputs": end_inputs,
            },
        }
    finally:
        session.close()


@router.get("/contracts/{contract_id}/authority-diagnostics")
def authority_diagnostics(request: Request, organization_slug: str, contract_id: UUID):
    """Expose evidence/precedence conflicts around a contract graph."""
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        _contract(session, org.id, contract_id)
        rows = session.scalars(
            select(ContractRelationRecord).where(
                ContractRelationRecord.organization_id == org.id,
                (
                    (ContractRelationRecord.source_contract_id == contract_id)
                    | (ContractRelationRecord.target_contract_id == contract_id)
                ),
            )
        ).all()
        issues: list[dict[str, Any]] = []
        seen: dict[tuple, set[str]] = defaultdict(set)
        for row in rows:
            key = (row.source_document_version_id, row.target_document_version_id, row.relation_type)
            seen[key].add(row.authority)
            if row.authority != "unknown" and not (row.evidence_refs or []):
                issues.append({
                    "kind": "authority_without_evidence",
                    "relation_id": str(row.id),
                    "message": f"{row.relation_type}: Autorität ohne Nachweis.",
                    "evidence_refs": [],
                })
        for key, values in seen.items():
            concrete = values - {"unknown"}
            if len(concrete) > 1:
                issues.append({
                    "kind": "authority_conflict",
                    "relation_id": None,
                    "message": f"Widersprüchliche Autorität für Beziehung {key[2]}.",
                    "evidence_refs": [],
                })
        return {
            "contract_id": str(contract_id),
            "relation_count": len(rows),
            "issue_count": len(issues),
            "issues": issues,
        }
    finally:
        session.close()


class PortfolioQueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    supplier: str | None = Field(default=None, max_length=255)
    contract_ids: list[UUID] = Field(default_factory=list)
    equipment_id: UUID | None = None
    as_of_date: date | None = None


@router.post("/portfolio/query")
def portfolio_query(request: Request, payload: PortfolioQueryRequest, organization_slug: str):
    """Query accepted portfolio state through the deterministic portfolio engine."""
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        visible = _visible_contract_ids(session, org.id)
        stmt = select(Contract).where(
            Contract.organization_id == org.id,
            Contract.lifecycle_state == "active",
        )
        if visible is not None:
            stmt = stmt.where(Contract.id.in_(visible))
        contracts = session.scalars(stmt).all()

        equipment_by_contract: dict[UUID, list[UUID]] = defaultdict(list)
        contract_ids = [row.id for row in contracts]
        if contract_ids:
            equipment_rows = session.scalars(
                select(ContractEquipment).where(
                    ContractEquipment.organization_id == org.id,
                    ContractEquipment.contract_id.in_(contract_ids),
                    ContractEquipment.equipment_id.is_not(None),
                )
            ).all()
            accepted_by_contract = {row.id: row.accepted_extraction_id for row in contracts}
            for item in equipment_rows:
                if item.extraction_id == accepted_by_contract.get(item.contract_id) and item.equipment_id:
                    equipment_by_contract[item.contract_id].append(item.equipment_id)

        rows = [
            {
                "contract_id": row.id,
                "supplier": row.supplier,
                "end_date": row.end_date,
                "status": row.status,
                "risk_level": row.risk_level,
                "equipment_ids": equipment_by_contract.get(row.id, []),
            }
            for row in contracts
        ]
        question = PortfolioQuestion(
            query=payload.query,
            supplier=payload.supplier,
            contract_ids=payload.contract_ids,
            equipment_id=payload.equipment_id,
            as_of_date=payload.as_of_date or date.today(),
        )
        result = answer_portfolio_question(question, rows)
        selected = set(result.contract_ids)
        matches = [
            {
                "contract_id": str(row.id),
                "contract_number": row.contract_number,
                "supplier": row.supplier,
                "status": row.status,
                "risk_level": row.risk_level,
                "end_date": row.end_date,
            }
            for row in contracts
            if row.id in selected
        ]
        return {
            **result.model_dump(mode="json"),
            "matches": matches,
            "source": "accepted_contract_state",
        }
    finally:
        session.close()


@router.get("/suppliers/performance")
def supplier_performance(request: Request, organization_slug: str):
    """Roll up persisted obligation performance per supplier."""
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        visible = _visible_contract_ids(session, org.id)
        stmt = select(Contract).where(
            Contract.organization_id == org.id,
            Contract.lifecycle_state == "active",
        )
        if visible is not None:
            stmt = stmt.where(Contract.id.in_(visible))
        contracts = session.scalars(stmt).all()
        by_supplier: dict[str, list[Contract]] = defaultdict(list)
        for contract in contracts:
            by_supplier[contract.supplier or "Unbekannt"].append(contract)

        items = []
        for supplier, supplier_contracts in sorted(by_supplier.items(), key=lambda item: item[0].lower()):
            ids = [row.id for row in supplier_contracts]
            obligations = session.scalars(
                select(ContractObligationRecord).where(
                    ContractObligationRecord.organization_id == org.id,
                    ContractObligationRecord.contract_id.in_(ids),
                )
            ).all() if ids else []
            summary = summarize_supplier_performance([{"status": row.status} for row in obligations])
            items.append({
                "supplier": supplier,
                "contract_count": len(supplier_contracts),
                **summary,
            })
        return {"items": items, "total": len(items)}
    finally:
        session.close()


class InvoiceReconciliationRequest(BaseModel):
    lines: list[InvoiceLine] = Field(default_factory=list)
    charges: list[ContractCharge] = Field(default_factory=list)


@router.post("/invoices/reconcile")
def reconcile_invoice_preview(request: Request, payload: InvoiceReconciliationRequest, organization_slug: str):
    """Expose the conservative invoice engine without pretending persistence."""
    session = create_session()
    try:
        _org(session, organization_slug, request)
        findings = reconcile_invoice(payload.lines, payload.charges)
        leakage = value_leakage(findings)
        return {
            "findings": [item.model_dump(mode="json") for item in findings],
            "value_leakage": {currency: str(amount) for currency, amount in leakage.items()},
            "persisted": False,
            "requires_review": any(item.requires_review for item in findings),
        }
    finally:
        session.close()


class ClauseFingerprintRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


@router.post("/clauses/fingerprint")
def clause_fingerprint(request: Request, payload: ClauseFingerprintRequest, organization_slug: str):
    """Expose the canonical clause normalizer/fingerprint for comparison tooling."""
    session = create_session()
    try:
        _org(session, organization_slug, request)
        result = fingerprint_clause(payload.text)
        return {
            "normalized_text": result.normalized_text,
            "fingerprint": result.fingerprint,
        }
    finally:
        session.close()
