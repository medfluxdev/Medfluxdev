"""Contract-aware invoice/PO reconciliation.

The engine is conservative: it only compares explicitly normalized contractual
charges. It never invents taxes, quantities or event applicability.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class InvoiceLine(BaseModel):
    label: str
    amount: Decimal
    currency: str
    quantity: Optional[Decimal] = Field(default=None, gt=0)
    unit: Optional[str] = None


class ContractCharge(BaseModel):
    label: str
    amount: Decimal
    currency: str
    charge_type: str  # fixed | scheduled | variable
    condition: Optional[str] = None
    applicable: Optional[bool] = None


class ReconciliationFinding(BaseModel):
    outcome: str  # matched | overbilled | underbilled | unknown
    invoice_label: str
    invoice_amount: Decimal
    contract_amount: Optional[Decimal] = None
    currency: str
    explanation: str
    requires_review: bool = False


def reconcile_invoice(lines: list[InvoiceLine], charges: list[ContractCharge]) -> list[ReconciliationFinding]:
    findings: list[ReconciliationFinding] = []
    by_currency: dict[str, list[ContractCharge]] = {}
    for charge in charges:
        by_currency.setdefault(charge.currency.upper(), []).append(charge)
    for line in lines:
        candidates = [
            charge for charge in by_currency.get(line.currency.upper(), [])
            if charge.label.strip().lower() == line.label.strip().lower()
            and charge.applicable is not False
        ]
        if len(candidates) != 1:
            findings.append(ReconciliationFinding(
                outcome="unknown",
                invoice_label=line.label,
                invoice_amount=line.amount,
                currency=line.currency.upper(),
                explanation="No single applicable contractual charge can be proven.",
                requires_review=True,
            ))
            continue
        contract = candidates[0]
        # A normalized contract charge is not proof of a per-unit rate.
        # Comparing a multi-unit invoice total against it would fabricate
        # an overbilling finding and inflate value leakage.
        if line.quantity is not None and line.quantity != Decimal("1"):
            findings.append(ReconciliationFinding(
                outcome="unknown",
                invoice_label=line.label,
                invoice_amount=line.amount,
                currency=line.currency.upper(),
                explanation=(
                    "Invoice quantity differs from one; no proven unit-rate "
                    "or quantity basis is available for this contract charge."
                ),
                requires_review=True,
            ))
            continue
        outcome = "matched"
        if line.amount > contract.amount:
            outcome = "overbilled"
        elif line.amount < contract.amount:
            outcome = "underbilled"
        findings.append(ReconciliationFinding(
            outcome=outcome,
            invoice_label=line.label,
            invoice_amount=line.amount,
            contract_amount=contract.amount,
            currency=line.currency.upper(),
            explanation="Compared against one explicitly applicable normalized contractual charge.",
            requires_review=outcome != "matched",
        ))
    return findings


def value_leakage(findings: list[ReconciliationFinding]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for finding in findings:
        if finding.outcome != "overbilled" or finding.contract_amount is None:
            continue
        totals[finding.currency] = totals.get(finding.currency, Decimal("0")) + (
            finding.invoice_amount - finding.contract_amount
        )
    return totals
