"""Vertragsregister (H1/H2/H6): Feld-Herkunft, Nummernkreise, Bemerkungen,
Vertragspartner, Kataloge und Mehrfach-Gesellschaften.

Grundsatz: Das Register funktioniert vollstaendig ohne KI. KI-Werte sind
Vorschlaege mit Herkunft (`contract_field_provenance`); manuell gesetzte oder
bestaetigte Werte werden von einer Reanalyse nie ueberschrieben.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk

FIELD_ORIGIN_ALLOWED = ("ai", "manual", "ai_confirmed", "ai_corrected", "imported_legacy", "system")
NUMBER_ALLOCATION_STATE_ALLOWED = ("used", "reserved", "free")


class ContractFieldProvenance(OrgOwnedMixin, Base):
    """Herkunft und Bestaetigung eines Registerfelds (eine Zeile je Vertrag+Feld)."""

    __tablename__ = "contract_field_provenance"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    field_key: Mapped[str] = mapped_column(String(64), nullable=False)
    origin: Mapped[str] = mapped_column(String(24), nullable=False)
    extraction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract_extraction.id", ondelete="SET NULL"), nullable=True
    )
    source_field: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    ai_proposed_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confirmed_by_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("contract_id", "field_key", name="uq_contract_field_provenance_contract_field"),
        CheckConstraint(
            f"origin IN ({', '.join(repr(v) for v in FIELD_ORIGIN_ALLOWED)})",
            name="origin",
        ),
        Index("ix_contract_field_provenance_contract_id", "contract_id"),
    )


class NumberRange(OrgOwnedMixin, Base):
    """Nummernkreis je Organisation und Zweck (z. B. Vertragsnummer)."""

    __tablename__ = "number_range"

    id: Mapped[uuid.UUID] = uuid_pk()
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, default="", server_default="")
    padding: Mapped[int] = mapped_column(Integer, nullable=False, default=6, server_default="6")
    next_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1, server_default="1")

    __table_args__ = (
        UniqueConstraint("organization_id", "purpose", name="uq_number_range_org_purpose"),
        CheckConstraint("next_value >= 1", name="next_value_positive"),
        CheckConstraint("padding BETWEEN 1 AND 12", name="padding_range"),
    )


class NumberAllocation(OrgOwnedMixin, Base):
    """Vergebene/reservierte Nummer (luecken- und doppelvergabesicher)."""

    __tablename__ = "number_allocation"

    id: Mapped[uuid.UUID] = uuid_pk()
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    formatted: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="used")
    contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="SET NULL"), nullable=True
    )
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "purpose", "value", name="uq_number_allocation_org_purpose_value"),
        CheckConstraint(
            f"state IN ({', '.join(repr(v) for v in NUMBER_ALLOCATION_STATE_ALLOWED)})",
            name="state",
        ),
    )


class ContractRemark(OrgOwnedMixin, Base):
    """Bemerkungs-Journal je Vertrag (append-only, keine Bearbeitung/Loeschung)."""

    __tablename__ = "contract_remark"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="SET NULL"), nullable=True
    )
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("length(btrim(body)) > 0", name="body_not_blank"),
        Index("ix_contract_remark_contract_created", "contract_id", "created_at"),
    )


class ContractPartner(OrgOwnedMixin, Base):
    """Vertragspartner-Stammdaten (Lieferant, Dienstleister, Kooperationspartner)."""

    __tablename__ = "contract_partner"

    id: Mapped[uuid.UUID] = uuid_pk()
    short_name: Mapped[str] = mapped_column(String(120), nullable=False)
    name1: Mapped[str] = mapped_column(String(255), nullable=False)
    name2: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    street: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    po_box: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    po_box_postal_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    fax: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vat_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    industry_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    partner_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        Index(
            "uq_contract_partner_org_short_name",
            "organization_id",
            text("lower(short_name)"),
            unique=True,
        ),
        Index("ix_contract_partner_org_active", "organization_id", "is_active"),
    )


class CatalogContractType(OrgOwnedMixin, Base):
    """Vertragstyp (konfigurierbar je Organisation)."""

    __tablename__ = "catalog_contract_type"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_confidential: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # H9: Standard-Aufbewahrung nach Vertragsende (Jahre), falls am Vertrag leer.
    retention_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_catalog_contract_type_org_code"),
    )


class ContractAccessGrant(OrgOwnedMixin, Base):
    """H8.2: Freigabe eines vertraulichen Vertrags fuer ein Konto."""

    __tablename__ = "contract_access_grant"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    granted_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("contract_id", "account_id", name="uq_contract_access_grant_pair"),
        Index("ix_contract_access_grant_account", "account_id"),
    )


class CatalogContractCategory(OrgOwnedMixin, Base):
    """Vertragskategorie; Zuordnung zu Typen n:m."""

    __tablename__ = "catalog_contract_category"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_catalog_contract_category_org_code"),
    )


class CatalogContractTypeCategory(Base):
    """n:m Vertragstyp <-> Kategorie."""

    __tablename__ = "catalog_contract_type_category"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_type_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("catalog_contract_type.id", ondelete="CASCADE", name="fk_cctc_contract_type_id"), nullable=False
    )
    contract_category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("catalog_contract_category.id", ondelete="CASCADE", name="fk_cctc_contract_category_id"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "contract_type_id", "contract_category_id", name="uq_catalog_contract_type_category_pair"
        ),
    )


class LookupValue(OrgOwnedMixin, Base):
    """Generische Auswahllisten (Lagerort, Anlagentyp, ToDo-Vorlagen, ...)."""

    __tablename__ = "lookup_value"

    id: Mapped[uuid.UUID] = uuid_pk()
    field_key: Mapped[str] = mapped_column(String(48), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    __table_args__ = (
        UniqueConstraint("organization_id", "field_key", "code", name="uq_lookup_value_org_field_code"),
        Index("ix_lookup_value_org_field", "organization_id", "field_key"),
    )


class ContractHospital(OrgOwnedMixin, Base):
    """D3: Ein Vertrag kann mehreren Gesellschaften/Krankenhaeusern gehoeren."""

    __tablename__ = "contract_hospital"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hospital.id", ondelete="CASCADE"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    __table_args__ = (
        UniqueConstraint("contract_id", "hospital_id", name="uq_contract_hospital_pair"),
        Index("ix_contract_hospital_hospital_id", "hospital_id"),
    )


SAVED_VIEW_KINDS = ("register", "contracts")


class SavedView(OrgOwnedMixin, Base):
    """H7.2: gespeicherte Ansicht des Vertragsregisters (persoenlich oder global)."""

    __tablename__ = "saved_view"

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("account.id", ondelete="CASCADE"), nullable=True
    )
    view_kind: Mapped[str] = mapped_column(String(24), nullable=False, default="register", server_default="register")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    system_key: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint("view_kind IN ('register', 'contracts')", name="view_kind"),
        Index("ix_saved_view_org_owner", "organization_id", "owner_account_id"),
        Index(
            "uq_saved_view_org_system_key", "organization_id", "system_key",
            unique=True, postgresql_where=text("system_key IS NOT NULL"),
        ),
    )
