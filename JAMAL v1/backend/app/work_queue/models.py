"""PR-4 Arbeitslisten-DTOs (API-Antworten/-Anfragen)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class WorkItemSummary(BaseModel):
    """Ein Arbeitselement in der Arbeitsliste."""

    id: str
    contract_id: str
    contract_number: Optional[str] = None
    supplier: Optional[str] = None
    equipment_id: Optional[str] = None
    contract_equipment_id: Optional[str] = None
    source_warning_id: Optional[str] = None
    item_type: str
    severity: str
    status: str
    title_de: str
    why_de: Optional[str] = None
    action_hint_de: Optional[str] = None
    target_date: Optional[date] = None
    days_remaining: Optional[int] = None
    requires_review: bool = False
    active: bool = True
    references: Optional[dict] = None
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    equipment_device_name: Optional[str] = None
    equipment_manufacturer: Optional[str] = None
    equipment_model: Optional[str] = None
    equipment_serial_number: Optional[str] = None


class WorkItemList(BaseModel):
    items: list[WorkItemSummary] = Field(default_factory=list)
    total: int = 0


class WorkItemStatusUpdate(BaseModel):
    status: str
