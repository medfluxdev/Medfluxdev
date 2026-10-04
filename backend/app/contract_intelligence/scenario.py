"""Conservative contract scenario simulation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal


def simulate_termination(*, annual_cost: Decimal | None, termination_date: date | None, contract_end: date | None) -> dict:
    if annual_cost is None or termination_date is None or contract_end is None:
        return {"known": False, "estimated_avoided_cost": None, "reason": "Required explicit inputs are missing."}
    if termination_date >= contract_end:
        return {"known": True, "estimated_avoided_cost": Decimal("0"), "reason": "Termination is not earlier than contract end."}
    days = (contract_end - termination_date).days
    estimate = (annual_cost * Decimal(days) / Decimal("365")).quantize(Decimal("0.01"))
    return {
        "known": True,
        "estimated_avoided_cost": estimate,
        "reason": "Prorated deterministic scenario estimate from explicit annual cost and dates.",
    }
