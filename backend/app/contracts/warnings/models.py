"""Warn-Modelle & Statusen (STEP 11).

Drei klar getrennte Schichten:
  A) Deterministische Warn-Bewertung (dieses Paket, reine Funktion)
  B) Durable Warn-Zustand/Historie (Persistenz, `app.database`)
  C) Future Action/Ownership-Integration (dokumentiert, spaetere Schritte)

Die Warn-Engine konsumiert NUR STEP-9-Resultate (`ContractCalculationResult`);
sie berechnet KEINE Termine selbst. KEINE KI entscheidet ueber Frist, Tage,
Schweregrad, Warn-Zustand, Ablauf, Kuendigungs-/Verlaengerungs-Dringlichkeit.

Deutscher UI-Text ist NIE Quelle der Geschaeftslogik – er ist nur Anzeige.
Jede Warnung traegt maschinenlesbare, deterministische Felder.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WarningType(str, Enum):
    """Maschinenlesbare Warn-Typen (explizite, begrenzte Menge)."""

    CONTRACT_END_APPROACHING = "contract_end_approaching"
    CONTRACT_EXPIRED = "contract_expired"
    CANCELLATION_DEADLINE_APPROACHING = "cancellation_deadline_approaching"
    CANCELLATION_DEADLINE_TODAY = "cancellation_deadline_today"
    CANCELLATION_DEADLINE_PASSED = "cancellation_deadline_passed"
    AUTOMATIC_RENEWAL_ATTENTION = "automatic_renewal_attention"
    UNCLEAR_CONTRACT_DATA = "unclear_contract_data"
    CALCULATION_CONFLICT = "calculation_conflict"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    MISSING_COST_DATA = "missing_cost_data"
    COST_CONFLICT = "cost_conflict"
    CURRENCY_CONFLICT = "currency_conflict"


class WarningSeverity(str, Enum):
    """Schweregrad einer Warnung (von der Engine bestimmt, nie von der KI)."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TargetKind(str, Enum):
    """Worauf sich die Warnung bezieht (fuer Filterung/Sortierung)."""

    CONTRACT_END = "contract_end"
    CANCELLATION_DEADLINE = "cancellation_deadline"
    RENEWAL = "renewal"
    COST = "cost"
    DATA_QUALITY = "data_quality"


class ActionState(str, Enum):
    """Menschlicher Lebenszyklus einer Warnung (spaetere Schritte).

    Bewusst GETRENNT vom Evaluations-Zustand (`active`): Eine Warnung kann
    objektiv weiterhin aktiv UND vom Menschen bereits bestaetigt (acknowledged)
    sein. Uebergaenge (open -> acknowledged -> resolved/dismissed) werden in
    spaeteren Schritten (STEP 12/16) realisiert; Default ist `open`.
    """

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


_SOURCES = {
    WarningType.CONTRACT_END_APPROACHING: ("dates.end_date", "contract.dates.end_date"),
    WarningType.CONTRACT_EXPIRED: ("dates.end_date", "contract.dates.end_date"),
    WarningType.CANCELLATION_DEADLINE_APPROACHING: (
        "dates.latest_cancellation_date",
        "termination.cancellation_period",
    ),
    WarningType.CANCELLATION_DEADLINE_TODAY: (
        "dates.latest_cancellation_date",
        "termination.cancellation_period",
    ),
    WarningType.CANCELLATION_DEADLINE_PASSED: (
        "dates.latest_cancellation_date",
        "termination.cancellation_period",
    ),
    WarningType.AUTOMATIC_RENEWAL_ATTENTION: (
        "dates.next_renewal_date",
        "termination.automatic_renewal",
    ),
    WarningType.UNCLEAR_CONTRACT_DATA: ("dates.current_contract_status", "contract.dates"),
    WarningType.CALCULATION_CONFLICT: ("dates.calculated_end_date", "contract.dates"),
    WarningType.MANUAL_REVIEW_REQUIRED: ("", ""),
    WarningType.MISSING_COST_DATA: ("costs.normalized_recurring", "contract.costs"),
    WarningType.COST_CONFLICT: ("costs.normalized_recurring.annual", "contract.costs"),
    WarningType.CURRENCY_CONFLICT: ("costs.currency_conflict", "contract.costs"),
}


class ContractWarning(BaseModel):
    """Eine evaluierte, strukturierte Warnung (reines Ergebnisobjekt).

    `logical_fingerprint` ist die stabile Identitaet des zugrunde liegenden
    logischen Problems (liefert Deduplikation + Lebenszyklus-Akkumulation).
    Er enthaelt KEINE praesentations-/schweregrad-abhaengigen Teile.
    """

    warning_type: WarningType
    severity: WarningSeverity
    target_kind: TargetKind
    target_date: Optional[date] = None
    days_remaining: Optional[int] = None
    matched_threshold_days: Optional[int] = None
    as_of_date: date
    policy_version: str
    title_de: str
    message_de: str
    action_hint_de: str
    requires_action: bool = False
    requires_review: bool = False
    calculation_field_refs: list[str] = Field(default_factory=list)
    source_field_refs: list[str] = Field(default_factory=list)
    logical_fingerprint: str


class ContractWarningResult(BaseModel):
    """Ergebnis einer Warn-Evaluation (deterministisch, sortiert)."""

    contract_id: Optional[str] = None
    as_of_date: date
    policy_version: str
    warnings: list[ContractWarning] = Field(default_factory=list)

    def ordered(self) -> "ContractWarningResult":
        """Deterministische Sortierung (hoechste Schwere, naechstes Ziel erste)."""
        rank = {
            WarningSeverity.CRITICAL: 0,
            WarningSeverity.HIGH: 1,
            WarningSeverity.MEDIUM: 2,
            WarningSeverity.LOW: 3,
            WarningSeverity.INFO: 4,
        }
        type_order = {t: i for i, t in enumerate(WarningType)}
        self.warnings.sort(
            key=lambda w: (
                rank[w.severity],
                # Ziel-Datum: frueheste zuerst, None zuletzt
                (w.target_date or date.max),
                type_order[w.warning_type],
                w.logical_fingerprint,
            )
        )
        return self


def default_field_refs(warning_type: WarningType) -> tuple[list[str], list[str]]:
    """Stabile Feld-Referenzen einer Warn-Art (Berechnung + Quelle)."""
    calc, source = _SOURCES.get(warning_type, ("", ""))
    return (
        [p for p in [calc] if p],
        [p for p in [source] if p],
    )
