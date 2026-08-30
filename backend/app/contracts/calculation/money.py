"""Geld/Decimal-Grenzschicht (STEP 9).

Financial-Zahlen dürfen NICHT mit Binär-Float gerechnet werden. Dieses Modul
übernimmt akzeptierte numerische Eingaben SICHER an der Berechnungsgrenze:
- float/str/int/Decimal → Decimal über STRING-basierte Konvertierung
  (`Decimal(str(x))`), damit 0.1 + 0.2 nicht 0.30000000000000004 ergibt.
- Der bestehende Money.amount (float) wird NICHT geändert (Rückwärtskompatibilität);
  erst BEI Berechnung wird stringbasiert konvertiert.

Rundung nur dort, wo echte Währungsrundung nötig ist. Keine Zwischenwerte
unnötig runden.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, Union

Numeric = Union[int, float, str, Decimal]


def to_decimal(value: Optional[Numeric]) -> Optional[Decimal]:
    """Konvertiert einen Zahlenwert stringbasiert exakt nach Decimal.

    Returns None bei None oder nicht konvertierbaren Werten (NaN, Inf, okkult).
    """
    if value is None:
        return None
    try:
        if isinstance(value, float):
            # str(float) liefert die kürzeste exakte Darstellung (z. B. 0.1),
            # NICHT die Binär-Approximation.
            return Decimal(str(value))
        return Decimal(value)
    except (InvalidOperation, ValueError, TypeError):
        return None


def round_currency(value: Decimal, cents: int = 2) -> Decimal:
    """Währungsrundung (nur an echten Ausgabegrenzen verwenden)."""
    q = Decimal(1).scaleb(-cents)
    return value.quantize(q, rounding=ROUND_HALF_UP)


def scaling_factor(period: str) -> Optional[Decimal]:
    """Faktor zur Annualisierung einer wiederkehrenden Periode.

    Returns None für Perioden, aus denen NICHT deterministisch annualisiert
    werden darf (once/hourly/unknown/other/conditional).
    """
    p = (period or "").strip().lower()
    mapping = {
        "monthly": Decimal(12),
        "quarterly": Decimal(4),
        "semi_annual": Decimal(2),
        "semiannual": Decimal(2),
        "half_year": Decimal(2),
        "annual": Decimal(1),
        "yearly": Decimal(1),
    }
    return mapping.get(p)
