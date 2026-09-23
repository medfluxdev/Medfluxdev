"""PR-4 Equipment-DTOs (API-Antworten, deutsche Beschriftung nur Anzeige)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class EquipmentContractLink(BaseModel):
    """Ein Vertrag, der auf ein Gerät Bezug nimmt (aus n:m-Relation)."""

    contract_id: str
    supplier: Optional[str] = None
    contract_number: Optional[str] = None
    relationship_quality: Optional[str] = None
    requires_review: bool = False
    service_scope: Optional[str] = None


class EquipmentSummary(BaseModel):
    """Kompakte Geräte-Identität (Liste)."""

    id: str
    device_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    inventory_number: Optional[str] = None
    equipment_type: Optional[str] = None
    equipment_category: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    identification_quality: str
    contract_count: int = 0


class EquipmentDetail(EquipmentSummary):
    """Volle Geräte-Ansicht mit Verträgen."""

    contracts: list[EquipmentContractLink] = Field(default_factory=list)


class ContractEquipmentItem(BaseModel):
    """Geräte-Eintrag innerhalb der Vertrags-Detailansicht (PR-4 erweitert)."""

    id: str
    equipment_id: Optional[str] = None
    device_name: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    inventory_number: Optional[str] = None
    system_name: Optional[str] = None
    equipment_category: Optional[str] = None
    equipment_type: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    service_scope: Optional[str] = None
    coverage_start: Optional[date] = None
    coverage_end: Optional[date] = None
    included_services: list[str] = Field(default_factory=list)
    excluded_services: list[str] = Field(default_factory=list)
    sla_notes: Optional[str] = None
    identification_quality: Optional[str] = None
    relationship_quality: Optional[str] = None
    requires_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
    # Provenienz -> ExtractionEvidence (Quell-Navigation, PR-2).
    field_ref: Optional[str] = None
    page: Optional[int] = None
    source_type: Optional[str] = None
