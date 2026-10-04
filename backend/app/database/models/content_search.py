"""Inhaltssuche (§4A): Seitentexte der Vertragsdokumente mit deutschem Volltextindex."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Computed, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.columns import OrgOwnedMixin, uuid_pk


class ContractTextPage(OrgOwnedMixin, Base):
    """Eine Seite Dokumenttext je Vertrag/Dokument. `page_number = 0` markiert
    ein Dokument ohne lesbaren Text (damit es nicht staendig neu gelesen wird)."""

    __tablename__ = "contract_text_page"

    id: Mapped[uuid.UUID] = uuid_pk()
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contract.id", ondelete="CASCADE"), nullable=False
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("document_version.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR, Computed("to_tsvector('german', regexp_replace(text, '[/–-]+', ' ', 'g'))", persisted=True), nullable=False
    )
    embedding: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    __table_args__ = (
        UniqueConstraint("contract_id", "document_version_id", "page_number", name="uq_contract_text_page"),
        Index("ix_contract_text_page_search", "search_vector", postgresql_using="gin"),
        Index("ix_contract_text_page_org", "organization_id"),
        Index("ix_contract_text_page_document", "document_version_id"),
    )
