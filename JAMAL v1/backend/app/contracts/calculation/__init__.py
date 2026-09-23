"""Medflux-Calculations-Paket (STEP 9 – deterministische Date & Cost Engine).

Enthält ausschließlich BEREICHNETE Resultate und die Engine – getrennt von
den extrahierten/source-of-truth Vertragsmodellen (`app/models/contract.py`).

Ansicht: EXTRACTED → deterministische Validierung/Normalisierung →
berechnetes Resultat → Erklärung + Eingabe-Provenienz/Review-Status.
"""

from app.contracts.calculation.calendar_ import (
    add_duration,
    days_between,
    month_add,
    month_sub,
    subtract_duration,
)
from app.contracts.calculation.costs import calculate_contract_costs
from app.contracts.calculation.dates import (
    calculate_contract_dates,
    calculate_contract_end_date,
    calculate_latest_cancellation_date,
    calculate_renewal_info,
    compute_days_until,
    group_cancellation_relation,
)
from app.contracts.calculation.engine import calculate_contract
from app.contracts.calculation.models import (
    CalcDuration,
    CalculateContractCosts,
    CalculatedDateField,
    CalculationStatus,
    ContractCalculationResult,
    ContractStatusDerivation,
    CostCategory,
    DateCalculationKind,
    DateTimeResult,
    DifferenceResult,
    MoneyFieldResult,
    RecurringCostNormalized,
    TaxBasis,
)

__all__ = [
    "CalcDuration",
    "CalculateContractCosts",
    "CalculatedDateField",
    "CalculationStatus",
    "ContractCalculationResult",
    "ContractStatusDerivation",
    "CostCategory",
    "DateCalculationKind",
    "DateTimeResult",
    "DifferenceResult",
    "MoneyFieldResult",
    "RecurringCostNormalized",
    "TaxBasis",
    "add_duration",
    "calculate_contract",
    "calculate_contract_costs",
    "calculate_contract_dates",
    "calculate_contract_end_date",
    "calculate_latest_cancellation_date",
    "calculate_renewal_info",
    "compute_days_until",
    "days_between",
    "group_cancellation_relation",
    "month_add",
    "month_sub",
    "subtract_duration",
]
