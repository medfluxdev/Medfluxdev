"""Deployment-globale Anwendungs-Einstellungen (Schritt 6B).

Nur key/value-Paare OHNE Organisations-Scope. Aktuelle Nutzung: persistierte
KI-Provider-/Modell-Auswahl, damit die Einstellungs-Oberfläche den aktiven
Provider überlebt (Refresh/Restart). Werte sind einfache Strings.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class ApplicationSetting(Base):
    """Ein globaler, schlüsselbasierter Anwendungs-Einstellungswert."""

    __tablename__ = "application_setting"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ApplicationSetting key={self.key!r}>"