"""Deterministic obligation lifecycle helpers."""

from __future__ import annotations

from datetime import date

from app.contract_intelligence.models import Obligation, ObligationInstance


def instantiate_obligation(obligation: Obligation, *, as_of: date) -> ObligationInstance:
    """Create the current occurrence shell without inventing a due date.

    Recurrence expansion remains deterministic and may be added once the
    recurrence expression is explicitly normalized and validated.
    """
    occurrence = obligation.due_date.isoformat() if obligation.due_date else as_of.isoformat()
    return ObligationInstance(
        obligation_key=obligation.key,
        occurrence_key=f"{obligation.key}:{occurrence}",
        due_date=obligation.due_date,
        status="active" if obligation.status in {"proposed", "active"} else obligation.status,
        evidence=list(obligation.evidence),
    )


def obligation_is_actionable(obligation: Obligation) -> bool:
    return obligation.status in {"proposed", "active", "breached"} and bool(
        obligation.due_date or obligation.conditions
    )
