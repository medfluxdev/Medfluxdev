"""equipment – kanonische Geräte-Identität (PR-4, org-gebunden).

Ergänzt das bisher flache `contract_equipment` um eine kanonische
`equipment`-Master-Tabelle: eine org-gebundene Geräte-Identität kann von
MEHREREN Verträgen abgedeckt werden („ein Gerät, mehrere Verträge"). Die
Zuordnung selbst (welcher Vertrag deckt welches Gerät) bleibt in
`contract_equipment` (n:m-Relation mit Provenienz/Qualität).

Wichtig:
- `identification_quality` wird NICHT von der KI gesetzt, sondern deterministisch
  in Code abgeleitet (exact = eindeutige Serien-/Inventarnummer; partial =
  Name+Modell ohne eindeutige Kennung; generic = generische Beschreibung;
  unknown = keine nutzbare Identität). Es werden NIE Kennungen erfunden.
- Serial-/Inventarnummern sind bewusst KEIN hartes Unique (Duplikate sind
  reale Fälle, geprüft statt abgelehnt); Org-Scoping verhindert Cross-Org-Kollision.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk


class Equipment(OrgOwnedMixin, Base):
    """Kanonische, org-gebundene Geräte-Identität."""

    __tablename__ = "equipment"

    id: Mapped[uuid.UUID] = uuid_pk()
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hospital.id", ondelete="SET NULL"), nullable=True
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("department.id", ondelete="SET NULL"), nullable=True
    )
    cost_center_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cost_center.id", ondelete="SET NULL"), nullable=True
    )
    device_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    inventory_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    equipment_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    equipment_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    identification_quality: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown"
    )

    __table_args__ = (
        Index("ix_equipment_org", "organization_id"),
        Index("ix_equipment_org_hospital", "organization_id", "hospital_id"),
        Index("ix_equipment_org_department", "organization_id", "department_id"),
        Index("ix_equipment_org_cost_center", "organization_id", "cost_center_id"),
        Index("ix_equipment_org_serial", "organization_id", "serial_number"),
        Index("ix_equipment_org_inventory", "organization_id", "inventory_number"),
        Index("ix_equipment_org_model", "organization_id", "model"),
    )
