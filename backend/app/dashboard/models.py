"""Dashboard-Response-DTOs (STEP 12).

Getrennte, explizit getypte Pydantic-Modelle fuer den Uebersichts-Read-Model.
Der READ-Vektor aggregiert aus:
- akzeptiertem/aktuellem Contract-Projektionszustand (`contract`)
- akzeptierten STEP-9-Berechnungsergebnissen (`calculation_run.result_snapshot`)
- aktuell-aktiven STEP-11-Warnungen (`contract_warning`, active=True)

KEINE KI in Dashboard-Berechnungen. Missing/unklar wird nie als 0/falsch
dargestellt. Es werden keine internen DB-IDs preisgegeben, die die UI nicht
braucht (minimale DTOs).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class DataFreshness(BaseModel):
    """Frische-/Stichtags-Metadaten (verhindert stille Verarbeitung als aktuell)."""

    requested_as_of_date: date
    # Stichtag, an dem die persistierten Warn-/Projektions-Zustaende zuletzt
    # determinstisch evaluiert wurden (aus `warning_evaluation_run`).
    warning_evaluation_as_of_date: Optional[date] = None
    # "current": Warn-Staende decken den angefragten Stichtag ab.
    # "stale": persistierte Warn-Staende sind aelter als angefragt (explizit).
    # "none": noch keine Warn-Evaluation vorhanden.
    data_freshness: str = "none"
    last_calculation_at: Optional[date] = None


class KpiCard(BaseModel):
    """Eine KPI-Karte (Wert + Belegung + accessible Beschreibung)."""

    label_de: str
    value: int
    secondary_de: Optional[str] = None
    status_de: Optional[str] = None


class MoneyTotal(BaseModel):
    """Eine aggregierte Geldsumme pro Waehrung (Decimal-exakt)."""

    currency: str
    amount: Decimal
    contract_count: int = 0


class FinancialSummary(BaseModel):
    """Kosten-/Finanzuebersicht (Waehrungen getrennt, nie gemischt)."""

    annual_recurring: list[MoneyTotal] = Field(default_factory=list)
    total_contract_value: list[MoneyTotal] = Field(default_factory=list)
    # Vertraege, deren Jahre-/Totalwert nicht verlaesslich (fehlend/Konflikt)
    # -> explizit ausgewiesen, nie stillschweigend als 0.
    contracts_without_reliable_annual_cost: int = 0
    contracts_without_reliable_total_value: int = 0
    multi_currency: bool = False


class ActionItem(BaseModel):
    """Ein priorisiertes Handlungsbedarf-Element (STEP-11-Warnsemantik)."""

    severity: str
    warning_type: str
    title_de: str
    contract_title: Optional[str] = None
    supplier: Optional[str] = None
    target_date: Optional[date] = None
    days_remaining: Optional[int] = None
    requires_review: bool = False
    requires_action: bool = False
    # Finanzieller Kontext NUR wenn verlaesslich; sonst None (niemals erfunden).
    annual_cost: Optional[MoneyTotal] = None
    cost_unreliable: bool = False


class DataQualityItem(BaseModel):
    """Ein Datenqualitaets-/Review-Zaehler."""

    label_de: str
    count: int
    severity: str


class DeadlineBucket(BaseModel):
    """Ein Fristen-Bucket der STEP-11-Policy (Kalendertage)."""

    threshold_days: Optional[int]  # None = verstrichen/passed
    label_de: str
    contract_count: int
    # Unterscheidung Kündigungsfrist vs. reines Vertragsende.
    cancellation: int = 0
    contract_end: int = 0


class DashboardOverview(BaseModel):
    """Vollstaendiges Uebersichts-Read-Model (bounded; nie alle Vertraege)."""

    as_of_date: date
    freshness: DataFreshness
    kpis: dict[str, KpiCard]
    deadlines: list[DeadlineBucket] = Field(default_factory=list)
    deadlines_multiple_warnings: list[DeadlineBucket] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    total_action_items: int = 0
    financial: FinancialSummary = Field(default_factory=FinancialSummary)
    data_quality: list[DataQualityItem] = Field(default_factory=list)
