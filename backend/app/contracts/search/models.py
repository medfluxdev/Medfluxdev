"""Search/Liste-DTOs (STEP 13) – minimale, getrennt getypte Response-Modelle.

Liefert NUR die fuer die Vertrags-Portfolio-Liste noetigen Felder. KEINE raw-OCR,
KEIN Vertragskoerper/Evidence-Payload, KEINE internen Pfade/Credentials/Metadata.
`contract_id` ist der stabile opaque Bezeichner fuer spaetere STEP-14-Navigation
(wird nie visuell gerendert). Alle Abfragen org-gebunden (Query-Ebene).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class SearchFreshness(BaseModel):
    """Frische-/Stichtags-Metadaten (verhindert stille Darstellung als aktuell)."""

    request_as_of_date: date
    warning_evaluation_as_of_date: Optional[date] = None
    # "current" / "stale" / "none" – wie STEP 12, auf Warn-Projektion bezogen.
    data_freshness: str = "none"


class ContractFinance(BaseModel):
    """Verlaesslicher Jahreskosten-Anzeigewert (keine erfundenen 0)."""

    currency: Optional[str] = None
    amount: Optional[Decimal] = None
    # True, wenn Kosten zwar angezeigt, aber NICHT verlaesslich sind.
    unreliable: bool = False


class ContractWarningSummary(BaseModel):
    """Wichtigste aktive Warnung eines Vertrags (Zusammenfassung)."""

    warning_type: Optional[str] = None
    severity: Optional[str] = None
    title_de: Optional[str] = None
    target_date: Optional[date] = None


class ContractListItem(BaseModel):
    """Eine Zeile der Vertrags-Portfolio-Liste (minimal, sicher)."""

    contract_id: uuid.UUID
    contract_number: Optional[str] = None
    contract_title: Optional[str] = None
    supplier: Optional[str] = None
    equipment_summary: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    automatic_renewal: Optional[bool] = None
    contract_end_date: Optional[date] = None
    latest_cancellation_date: Optional[date] = None
    annual_cost: Optional[ContractFinance] = None
    primary_warning: Optional[ContractWarningSummary] = None
    requires_action: bool = False
    requires_review: bool = False
    is_archived: bool = False
    archived_at: Optional[datetime] = None


class ContractFacets(BaseModel):
    """Kompakte, org-gebundene Zaehler (kein BI-Engine)."""

    status_counts: dict[str, int] = Field(default_factory=dict)
    requires_action: int = 0
    requires_review: int = 0
    critical_cancellation: int = 0


class ContractListResponse(BaseModel):
    """Geteilte, bounded Portfolio-Antwort."""

    organization_slug: str
    freshness: SearchFreshness
    total_count: int
    page: int
    page_size: int
    has_more: bool
    facets: ContractFacets
    items: list[ContractListItem] = Field(default_factory=list)
