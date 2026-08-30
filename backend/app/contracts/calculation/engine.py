"""STEP-9-Engine: orchestrates Date + Cost Engines (pure Funktion).

Einstiegspunkt: `calculate_contract(contract, as_of_date)`.
Keine DB, kein HTTP, kein AI, kein verstecktes datetime (Zeitbezug nur über
das explizite `as_of_date`).
"""

from __future__ import annotations

from datetime import date

from app.contracts.calculation.costs import calculate_contract_costs
from app.contracts.calculation.dates import calculate_contract_dates
from app.contracts.calculation.models import ContractCalculationResult
from app.models.contract import Contract


def calculate_contract(contract: Contract, as_of_date: date) -> ContractCalculationResult:
    """Berechnet deterministisch alle STEP-9-Felder für einen Vertrag."""
    dates = calculate_contract_dates(contract, as_of_date)
    costs = calculate_contract_costs(contract)

    review_reasons: list[str] = []
    if dates.current_contract_status.status.value == "unknown":
        review_reasons.append(
            dates.current_contract_status.explanation
        )
    for field in (
        dates.calculated_end_date,
        dates.latest_cancellation_date,
        dates.next_renewal_date,
    ):
        if field.review_required:
            review_reasons.append(field.explanation)
    if costs.recurring_cost_conflict:
        review_reasons.append("Widersprüchliche wiederkehrende Kostenbeträge.")
    if costs.currency_conflict:
        review_reasons.append("Mehrere Währungen; keine Aggregation.")
    if costs.tax_basis.value == "unknown":
        review_reasons.append("Steuerbasis (netto/brutto) nicht modelliert – keine MwSt-Annahme.")

    overall_review = bool(review_reasons)
    return ContractCalculationResult(
        contract_id=contract.identity.contract_number or contract.id
        if contract.identity
        else contract.id,
        as_of_date=as_of_date,
        dates=dates,
        costs=costs,
        overall_review_required=overall_review,
        review_reasons=review_reasons,
    )
