"""Wiederverwendbare, stark typisierte Werte für das Medflux-Vertragsdatenmodell.

Diese Typen kapseln gängige Fachkonzepte (Geld, Dauer, Zeitangabe, Datum)
und erlauben sowohl explizite als auch unbekannte/ereignisbasierte Werte,
ohne Platzhalterstrings wie "unknown" zu verwenden.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.enums import TimeUnit


class Money(BaseModel):
    """Strukturierte Geldangabe.

    amount ist optional: Ein unbekannter Betrag wird als `None` dargestellt,
    niemals als Platzhalterstring. currency ist ebenfalls optional und
    kann auf Vertragsebene angegeben werden.
    """

    amount: Optional[float] = Field(
        default=None, ge=0, description="Betrag (>= 0), None wenn unbekannt"
    )
    currency: Optional[str] = Field(
        default=None, max_length=3, description="Währungscode, z. B. EUR"
    )
    period: Optional[str] = Field(
        default=None, description="Bezugszeitraum, z. B. annual/monthly"
    )

    @field_validator("amount")
    @classmethod
    def _amount_not_nan(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v != v:  # NaN-Check
            raise ValueError("amount darf nicht NaN sein")
        return v

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.upper()
        return v


class Duration(BaseModel):
    """Dauer/Frist mit Wert und Einheit.

    Bei unbekannter Dauer bleibt value = None (unit dann ebenfalls None).
    Ein negativer Wert ist nicht zulässig.
    """

    value: Optional[int] = Field(
        default=None, ge=0, description="Dauer in der Einheit, >= 0"
    )
    unit: Optional[TimeUnit] = Field(default=None, description="Zeiteinheit")


class TimeValue(BaseModel):
    """Zeitangabe für SLA-Werte (Reaktionszeit usw.).

    Liefert einen numerischen Wert mit Einheit sowie den ursprünglichen
    Text aus dem Vertrag für Nachweis/zweite Prüfung.
    """

    value: Optional[float] = Field(
        default=None, ge=0, description="Numerischer Wert, >= 0"
    )
    unit: Optional[TimeUnit] = Field(default=None, description="Zeiteinheit")
    original_text: Optional[str] = Field(
        default=None, description="Originaltext aus dem Vertrag"
    )


class FlexibleDate(BaseModel):
    """Datum, das explizit, unbekannt oder ereignisbasiert sein kann.

    Beispiele:
    - explizit: date = date(2025, 1, 1)
    - ereignisbasiert: condition = "Übergabedatum", date = None
    - unbekannt: date = None, condition = None
    """

    date: Optional[Date] = Field(default=None, description="Explizites Datum")
    condition: Optional[str] = Field(
        default=None, description="Textbedingung, z. B. 'Übergabedatum'"
    )
    requires_review: bool = Field(
        default=False, description="Ist eine manuelle Prüfung nötig?"
    )
