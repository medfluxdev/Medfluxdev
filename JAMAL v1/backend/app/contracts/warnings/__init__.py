"""Medflux-Warn-Paket (STEP 11 – deterministische Warn-Engine).

Drei Schichten:
  A) `engine.evaluate_contract_warnings` – reine, deterministische Bewertung.
  B) Durable Warn-Zustand/Historie – Persistenz in `app.database`.
  C) Future Action/Ownership-Integration – dokumentierter Erweiterungspunkt.

Die Engine konsumiert STEP-9-`ContractCalculationResult`; sie rechnet KEINE
Termine selbst. Keine KI/kein Netz/kein verstecktes Datum.
"""

from app.contracts.warnings.engine import evaluate_contract_warnings
from app.contracts.warnings.models import (
    ActionState,
    ContractWarning,
    ContractWarningResult,
    TargetKind,
    WarningSeverity,
    WarningType,
)
from app.contracts.warnings.policy import (
    DEFAULT_MEDFLUX_THRESHOLDS,
    DEFAULT_POLICY_VERSION,
    WarningPolicy,
    severity_for_days,
    severity_to_risk,
)

__all__ = [
    "ActionState",
    "ContractWarning",
    "ContractWarningResult",
    "DEFAULT_MEDFLUX_THRESHOLDS",
    "DEFAULT_POLICY_VERSION",
    "TargetKind",
    "WarningPolicy",
    "WarningSeverity",
    "WarningType",
    "evaluate_contract_warnings",
    "severity_for_days",
    "severity_to_risk",
]
