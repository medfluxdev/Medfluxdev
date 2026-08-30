"""Deterministische Cost Engine (STEP 9).

Decimal-exakte Geldarithmetik (stringbasiert konvertiert, kein Binär-Float).
Konzepte werden getrennt gehalten; NICHT vergleichbare Felder werden nicht
addiert. Normalisierte wiederkehrende Kosten nur aus explizit wiederkehrenden
Eingaben. Währungen werden nie gemischt; kein FX. Steuerbasis wird nur
gesetzt, wenn explizit bekannt (sonst UNKNOWN; keine 19 %-Annahme).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.contracts.calculation.models import (
    CalculateContractCosts,
    CostCategory,
    CalculationStatus,
    MoneyFieldResult,
    RecurringCostNormalized,
    TaxBasis,
)
from app.contracts.calculation.money import to_decimal
from app.models.contract import Contract, Costs
from app.models.values import Money


def _amount(m: Optional[Money]) -> Optional[Decimal]:
    if m is None or m.amount is None:
        return None
    return to_decimal(m.amount)


def _currency(m: Optional[Money], fallback: Optional[str]) -> Optional[str]:
    if m is not None and m.currency:
        return m.currency
    return fallback


def _mk(
    value: Optional[Decimal],
    status: CalculationStatus,
    currency: Optional[str],
    explanation: str,
    inputs: dict,
    review: bool = False,
) -> MoneyFieldResult:
    return MoneyFieldResult(
        value=value,
        currency=currency,
        status=status,
        explanation=explanation,
        inputs=inputs,
        review_required=review,
    )


_CHARGE_LABELS = {
    "monthly_cost": "monatlich",
    "quarterly_cost": "quartalsweise",
    "semi_annual_cost": "halbjährlich",
    "annual_cost": "jährlich",
    "maintenance_fee": "Wartung/e (wiederkehrend, Periode unbekannt)",
}


def _recurring_source_period(c: Costs) -> Optional[str]:
    """Bestimmt die explizit wiederkehrende Quelle in fester Priorität."""
    for key, period in (
        ("monthly_cost", "monthly"),
        ("annual_cost", "annual"),
    ):
        m = getattr(c, key, None)
        if m is not None and m.amount is not None and m.amount > 0:
            return key
    return None


def _coherence(annual_amount: Decimal, base_annual: Decimal, currency: str) -> Optional[str]:
    """Prüft Übereinstimmung zweier annualisierter Werte (kleine exakte Toleranz)."""
    if annual_amount is None or base_annual is None:
        return None
    if annual_amount == base_annual:
        return "exact"
    # Toleranz: Unterschied <= 0.5 % des grösseren Werts (dokumentiert).
    larger = max(abs(annual_amount), abs(base_annual))
    if larger == 0:
        return "exact"
    tol = (abs(annual_amount - base_annual) / larger)
    if tol <= Decimal("0.005"):
        return "within_tolerance"
    return None


def calculate_contract_costs(contract: Contract) -> CalculateContractCosts:
    """Berechnet die Kostenfelder eines Vertrags (pure Funktion)."""
    c: Costs = contract.costs
    default_currency = c.default_currency
    result = CalculateContractCosts()
    notes = result.notes

    # Steuerbasis: NUR wenn explizit modelliert. Das aktuelle Modell besitzt
    # kein Netto/Brutto-Feld -> immer UNKNOWN (keine 19 %-Annahme).
    result.tax_basis = TaxBasis.UNKNOWN

    # -------- Normalisierte wiederkehrende Kosten (annual + monthly) --------
    # Quelle: monatlicher oder jährlicher Betrag. Nicht doppelt zählen; bei
    # beidem vergleichen und ggf. Conflict melden.
    annual = _mk(None, CalculationStatus.NOT_CALCULABLE, default_currency, "Nicht bestimmt.", {})

    monthly_value = _amount(c.monthly_cost)
    annual_value = _amount(c.annual_cost)
    weekly_value = _amount(getattr(c, "weekly_cost", None))

    if monthly_value is not None:
        currency = _currency(c.monthly_cost, default_currency)
        annual_from_monthly = monthly_value * Decimal(12)
        if annual_value is not None:
            corr = _coherence(annual_value, annual_from_monthly, currency)
            if corr in ("exact", "within_tolerance"):
                annual = _mk(
                    annual_from_monthly,
                    CalculationStatus.CALCULATED,
                    currency,
                    f"Monatlich {monthly_value} x 12 = {annual_from_monthly} (jährlich "
                    f"korroboriert: {corr}).",
                    {"monthly_cost": str(monthly_value), "annual_cost": str(annual_value)},
                )
            else:
                annual = _mk(
                    None,
                    CalculationStatus.CONFLICT,
                    currency,
                    f"Monatlicher Betrag ({monthly_value}x12={annual_from_monthly}) "
                    f"und jährlicher Betrag ({annual_value}) widersprechen sich; "
                    f"kein normalisierter Wert.",
                    {"monthly_cost": str(monthly_value), "annual_cost": str(annual_value)},
                    review=True,
                )
        else:
            annual = _mk(
                annual_from_monthly,
                CalculationStatus.CALCULATED,
                currency,
                f"Monatlich {monthly_value} x 12 = {annual_from_monthly}.",
                {"monthly_cost": str(monthly_value)},
            )
    elif annual_value is not None:
        currency = _currency(c.annual_cost, default_currency)
        annual = _mk(
            annual_value,
            CalculationStatus.CALCULATED if True else CalculationStatus.EXPLICIT,
            currency,
            "Expliziter jährlicher Betrag.",
            {"annual_cost": str(annual_value)},
        )
    elif weekly_value is not None:
        currency = _currency(getattr(c, "weekly_cost", None), default_currency)
        weekly_annual = weekly_value * Decimal(52)
        annual = _mk(
            weekly_annual,
            CalculationStatus.CALCULATED,
            currency,
            f"Wöchentlich {weekly_value} x 52 = {weekly_annual}.",
            {"weekly_cost": str(weekly_value)},
        )
    else:
        # Keine explizit rekursive Zahl: maintenance_fee als wiederkehrende
        # Wartung, aber Periode unbekannt -> nicht annualisierbar, separat.
        mf = _amount(c.maintenance_fee)
        if mf is not None:
            mf_currency = _currency(c.maintenance_fee, default_currency)
            annual = _mk(
                None,
                CalculationStatus.NOT_CALCULABLE,
                mf_currency,
                "Wartungsgebühr vorhanden, aber wiederkehrende Periode unbekannt "
                "(nicht annualisierbar).",
                {"maintenance_fee": str(mf)},
                review=True,
            )

    monthly_result = None
    if annual.value is not None and annual.currency == default_currency:
        monthly_result = _mk(
            _round_if_currency(annual.value / Decimal(12), 2),
            CalculationStatus.CALCULATED,
            annual.currency,
            f"Jährlich {annual.value} / 12 = monatlich.",
            {"annual": str(annual.value)},
        )

    result.normalized_recurring = RecurringCostNormalized(
        annual=annual,
        monthly=monthly_result or MoneyFieldResult(),
        source_period=_recurring_source_period(c) or "unknown",
    )

    # -------- Währungs-Konflikt-Erkennung (aggregierbar nur bei gleicher Währung) --------
    currencies = {
        cur
        for m in (
            c.monthly_cost,
            c.annual_cost,
            c.maintenance_fee,
            c.total_contract_value,
            c.one_time_cost,
            c.hourly_rate,
            c.travel_cost,
            c.material_cost,
            c.additional_costs,
        )
        for cur in [m.currency if m is not None and m.currency else None]
        if cur
    }
    if len(currencies) > 1:
        result.currency_conflict = True
        notes.append(
            "Mehrere Währungen vorhanden; keine Rechnerische Aggregation über "
            "Währungsgrenzen hinweg (kein FX)."
        )

    # -------- Kategorie-Totale (nur gleiche Währung + vergleichbare Einheit) --------
    category_totals = []
    for key, label in (
        ("one_time_cost", "Einmalig"),
        ("hourly_rate", "Stundensatz"),
        ("travel_cost", "Reisekosten"),
        ("material_cost", "Material"),
        ("spare_parts_cost", "Ersatzteile"),
        ("additional_costs", "Zusatzkosten (bedingt)"),
        ("maintenance_fee", "Wartungsgebühr"),
    ):
        m = getattr(c, key, None)
        if m is None or m.amount is None:
            continue
        value = to_decimal(m.amount)
        cur = m.currency or default_currency
        if len(currencies) > 1:
            comp = MoneyFieldResult(
                value=value,
                currency=cur,
                status=CalculationStatus.NOT_CALCULABLE,
                explanation=(
                    f"{label}: eigene Währung ({cur}); nicht in einen gemeinsamen "
                    "Total überführbar (kein FX)."
                ),
                inputs={key: str(value) + " " + (cur or "")},
            )
            category_totals.append(
                CostCategory(
                    key=key,
                    label=label,
                    currency=cur,
                    amount=None,
                    status=CalculationStatus.NOT_CALCULABLE,
                    explanation=comp.explanation,
                    inputs=[key],
                    components=[comp],
                )
            )
            continue
        comp = MoneyFieldResult(
            value=value,
            currency=cur,
            status=CalculationStatus.CALCULATED,
            explanation=f"{label}: extrahierter Betrag {value} {cur or ''}.",
            inputs={key: str(value)},
        )
        category_totals.append(
            CostCategory(
                key=key,
                label=label,
                currency=cur,
                amount=value,
                status=CalculationStatus.CALCULATED,
                explanation=comp.explanation,
                inputs=[key],
                components=[comp],
            )
        )
    result.category_totals = category_totals

    # -------- Total-Vertragswert (nur vorhandener Wert, keine Addition) --------
    tcv = _amount(c.total_contract_value)
    if tcv is not None:
        result.total_contract_value_status = CalculationStatus.CALCULATED
        notes.append(
            f"total_contract_value={tcv} {c.total_contract_value.currency or default_currency or ''} "
            "(bewusst NICHT automatisch zu wiederkehrenden Kosten addiert)."
        )
    else:
        result.total_contract_value_status = CalculationStatus.NOT_CALCULABLE

    return result


def _round_if_currency(value: Decimal, cents: int) -> Decimal:
    return value
