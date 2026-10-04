"""Finanzdaten je Vertrag (H4): Finanzeintraege, Leistungskatalog,
Kostenstellen-Aufteilung und verworfene KI-Vorschlaege.

Betraege werden erfasst, wie sie im Vertrag stehen (netto oder brutto, mit
Steuersatz und Intervall). Alle Summen berechnet Code (`app/finance/calc.py`),
kalkulatorisch auf Basis ganzer Monate.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

FINANCE_DIRECTION_ALLOWED = ("expense", "income")
AMOUNT_BASIS_ALLOWED = ("net", "gross")
FINANCE_INTERVAL_ALLOWED = ("monthly", "quarterly", "semi_annual", "annual", "once")
FINANCE_ORIGIN_ALLOWED = ("manual", "ai_confirmed", "imported_legacy")


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(repr(v) for v in values)


class ContractFinanceEntry(OrgOwnedMixin, Base):
    __tablename__ = "contract_finance_entry"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False, default="expense")
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    cost_type_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    amount_basis: Mapped[str] = mapped_column(String(8), nullable=False, default="net")
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("19"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default="EUR")
    interval: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    apply_price_adjustment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    origin: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    source_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    extraction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract_extraction.id", ondelete="SET NULL"), nullable=True
    )
    created_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint(f"direction IN ({_in(FINANCE_DIRECTION_ALLOWED)})", name="direction"),
        CheckConstraint(f"amount_basis IN ({_in(AMOUNT_BASIS_ALLOWED)})", name="amount_basis"),
        CheckConstraint(f"interval IN ({_in(FINANCE_INTERVAL_ALLOWED)})", name="interval"),
        CheckConstraint(f"origin IN ({_in(FINANCE_ORIGIN_ALLOWED)})", name="origin"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("vat_rate >= 0 AND vat_rate <= 100", name="vat_rate_range"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="validity"),
        Index("ix_contract_finance_entry_contract", "contract_id"),
    )


class ContractServiceItem(OrgOwnedMixin, Base):
    """Leistungskatalog: einzelne Leistungen mit Preis und Gueltigkeit."""

    __tablename__ = "contract_service_item"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    service_kind: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    plus_vat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR", server_default="EUR")
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    origin: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    source_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    extraction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract_extraction.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(f"origin IN ({_in(FINANCE_ORIGIN_ALLOWED)})", name="origin"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="amount_non_negative"),
        CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="validity"),
        Index("ix_contract_service_item_contract", "contract_id"),
    )


class ContractCostAllocation(OrgOwnedMixin, Base):
    """Aufteilung der Vertragskosten auf Kostenstellen (Summe 100 %)."""

    __tablename__ = "contract_cost_allocation"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    cost_center_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("cost_center.id", ondelete="CASCADE"), nullable=False
    )
    share_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    recharge_mode: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("contract_id", "cost_center_id", name="uq_contract_cost_allocation_pair"),
        CheckConstraint("share_percent > 0 AND share_percent <= 100", name="share_range"),
    )


class ContractSuggestionDismissal(OrgOwnedMixin, Base):
    """Verworfene KI-Vorschlaege (Finanzen/Leistungen) je Extraktionslauf."""

    __tablename__ = "contract_suggestion_dismissal"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    suggestion_key: Mapped[str] = mapped_column(String(120), nullable=False)
    dismissed_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("contract_id", "scope", "suggestion_key", name="uq_contract_suggestion_dismissal_key"),
    )
