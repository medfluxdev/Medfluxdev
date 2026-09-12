"""contract, contract_document & contract_equipment – Vertrags-Aggregat (Current State)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Computed, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

LIFECYCLE_STATE_ALLOWED = {"active", "orphan", "pending_deletion", "deleted"}
CONTRACT_DOCUMENT_ROLE_ALLOWED = {"main", "amendment", "appendix", "renewal_letter", "price_adjustment", "sla_attachment", "unknown"}
CONTRACT_SCOPE_ALLOWED = {"organization", "hospital", "department"}


class Contract(OrgOwnedMixin, Base):
    """Aktueller akzeptierter Vertrag mit explizitem organisatorischem Besitz."""

    __tablename__ = "contract"

    id: Mapped[uuid.UUID] = uuid_pk()
    hospital_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hospital.id", ondelete="SET NULL"), nullable=True
    )
    cost_center_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cost_center.id", ondelete="SET NULL"), nullable=True
    )
    scope_type: Mapped[str] = mapped_column(String(24), nullable=False, default="organization", server_default="organization")
    accepted_extraction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract_extraction.id", ondelete="SET NULL"), nullable=True
    )
    accepted_calculation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("calculation_run.id", ondelete="SET NULL"), nullable=True
    )
    supplier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contract_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR,
        Computed(
            "(setweight(to_tsvector('simple', coalesce(contract_number, '')), 'A') || ' ' || "
            "setweight(to_tsvector('german', coalesce(supplier, '')), 'B') || ' ' || "
            "setweight(to_tsvector('simple', coalesce(status, '')), 'C'))",
            persisted=True,
        ),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    lifecycle_state: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    deletion_owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    document_links: Mapped[list["ContractDocument"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan", order_by="ContractDocument.role"
    )

    __table_args__ = (
        CheckConstraint(f"lifecycle_state IN ({', '.join(repr(v) for v in sorted(LIFECYCLE_STATE_ALLOWED))})", name="lifecycle_state"),
        CheckConstraint(f"scope_type IN ({', '.join(repr(v) for v in sorted(CONTRACT_SCOPE_ALLOWED))})", name="scope_type"),
        Index("ix_contract_status", "status"),
        Index("ix_contract_risk_level", "risk_level"),
        Index("ix_contract_accepted_extraction_id", "accepted_extraction_id"),
        Index("ix_contract_org_is_archived", "organization_id", "is_archived"),
        Index("ix_contract_org_hospital", "organization_id", "hospital_id"),
        Index("ix_contract_org_cost_center", "organization_id", "cost_center_id"),
    )


class ContractDocument(OrgOwnedMixin, Base):
    __tablename__ = "contract_document"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("document_version.id", ondelete="RESTRICT"), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    contract: Mapped["Contract"] = relationship(back_populates="document_links")

    __table_args__ = (
        CheckConstraint(f"role IS NULL OR role IN ({', '.join(repr(v) for v in sorted(CONTRACT_DOCUMENT_ROLE_ALLOWED))})", name="role"),
        UniqueConstraint("contract_id", "document_version_id", name="uq_contract_document_pair"),
        Index("ix_contract_document_contract_id", "contract_id"),
        Index("ix_contract_document_version_id", "document_version_id"),
    )


class ContractEquipment(OrgOwnedMixin, Base):
    __tablename__ = "contract_equipment"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False)
    extraction_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contract_extraction.id", ondelete="RESTRICT"), nullable=False)
    equipment_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    inventory_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    system_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    equipment_category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    equipment_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    service_scope: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    coverage_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    coverage_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    included_services: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    excluded_services: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    sla_notes: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    identification_quality: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    relationship_quality: Mapped[str] = mapped_column(String(16), nullable=False, default="ambiguous")
    requires_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    review_reasons: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    field_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    equipment_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logical_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("contract_id", "extraction_id", "logical_fingerprint", name="uq_contract_equipment_contract_extraction_fingerprint"),
        Index("ix_contract_equipment_contract_id", "contract_id"),
        Index("ix_contract_equipment_extraction_id", "extraction_id"),
        Index("ix_contract_equipment_equipment_id", "equipment_id"),
        Index("ix_contract_equipment_org_requires_review", "organization_id", "requires_review"),
    )
