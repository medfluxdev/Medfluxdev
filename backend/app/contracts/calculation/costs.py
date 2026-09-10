"""Deterministische Cost Engine (STEP 9 + PR-3 Financial Intelligence).

Decimal-exakte Geldarithmetik (stringbasiert konvertiert, kein Binär-Float).
Konzepte werden getrennt gehalten; NICHT vergleichbare Felder werden nicht
addiert. Normalisierte wiederkehrende Kosten nur aus explizit wiederkehrenden
Eingaben. Währungen werden nie gemischt; kein FX. Steuerbasis wird nur
gesetzt, wenn explizit bekannt (sonst UNKNOWN; keine 19 %-Annahme).

PR-3: Annualisierung erfolgt zentral über `scaling_factor` und respektiert die
explizite Bezugsperiode (`Money.period`). Damit werden auch `quarterly_cost`,
`semi_annual_cost` und eine `maintenance_fee` MIT wiederkehrender Periode
korrekt annualisiert (bis PR-3 blieb z. B. eine monatliche Wartungsgebühr ohne
Jahreswert – echter Benchmark-Befund BD). Eine `maintenance_fee` OHNE Periode
bleibt nicht-annualisierbar (review).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.contracts.calculation.models import (
    CalculateContractCosts,
    CostCategory,
    CostTaxBreakdown,
    CalculationStatus,
    MoneyFieldResult,
    PriceDevelopmentItem,
    RecurringCostNormalized,
    TaxBasis,
)
from app.contracts.calculation.money import round_currency, scaling_factor, to_decimal
from app.models.contract import Contract, Costs
from app.models.values import Money


def derive_tax_breakdown(
    *,
    annual: Optional[Decimal],
    monthly: Optional[Decimal],
    tax_basis: TaxBasis,
    tax_rate_percent: Optional[float],
    currency: Optional[str] = None,
    recovered_vat_rate: Optional[float] = None,
    recovered_monthly_vat: Optional[Decimal] = None,
    recovered_monthly_gross: Optional[Decimal] = None,
    recovered_monthly_net: Optional[Decimal] = None,
) -> CostTaxBreakdown:
    """Leitet die Netto/Brutto-Werte der wiederkehrenden Kosten exakt ab.

    Deterministisch, Decimal-exakt, KEINE Annahme einer Steuerbasis oder eines
    Steuersatzes. `computed=False`, sobald Basis oder Satz fehlen bzw. der Satz
    nicht nutzbar ist. Der kanonische recurring-Wert (`annual`/`monthly`) liegt
    in der Basis `tax_basis` vor; die Gegen-Basis wird ueber den Satz abgeleitet.

    UAT Re-Test – vertraglich direkt belegte Betraege (Recovery aus dem
    persistierten Dokumenttext) haben Vorrang:
    - `recovered_vat_rate` setzt einen sonst fehlenden Steuersatz (z. B. 19 %),
    - `recovered_monthly_gross`/`recovered_monthly_net` sind die DIREKT im
      Vertrag benannten Monatsbetraege (keine Rechnung),
    - die Jahres-Gegen-Basis wird bei direkt belegtem Monats-Gegenwert aus
      Monat x 12 abgeleitet, damit die Vertragsrundung erhalten bleibt
      (z. B. 7.040,84 x 12 = 84.490,08 statt annual x 1,19 = 84.490,05).

    Wird sowohl in der Cost-Engine (aus extrahiertem `tax_basis` + `tax_rate_percent`)
    als auch in der Detail-Ansicht (nach manuellem Override der Basis/Satz oder
    nach Recovery) genutzt – eine konsistente, single-source-of-truth-Rechnung.
    """
    # Fehlt ein eigener Monatswert, wird er aus dem Jahreswert abgeleitet
    # (Jahresbetrag / 12). Deterministische Code-Rechnung, keine Erfindung;
    # die Provenienz wird in der Erklärung ehrlich gekennzeichnet.
    derived_monthly = False
    if monthly is None and annual is not None:
        monthly = _round_if_currency(annual / Decimal(12), 2)
        derived_monthly = True

    # Ohne verlässliche Basis kann weder Netto noch Brutto als solches benannt
    # werden (keine 19 %-Annahme).
    if tax_basis == TaxBasis.UNKNOWN:
        return CostTaxBreakdown(
            explanation=(
                "Keine verlaessliche Steuer-Basis dokumentiert. Netto/Brutto "
                "nicht benannt; keine Annahme (z. B. 19 %) getroffen."
            )
        )

    # Basis-Beträge (netto bei Basis=net, brutto bei Basis=gross) sind die
    # direkt belegten/übernommenen Werte und werden IMMER ausgewiesen.
    # Die Gegen-Basis (brutto bei netto) braucht einen gültigen Steuersatz.
    if tax_basis == TaxBasis.NET:
        monthly_net, annual_net = monthly, annual
        monthly_gross = annual_gross = None
    else:  # GROSS
        monthly_gross, annual_gross = monthly, annual
        monthly_net = annual_net = None

    recovered = any(
        v is not None
        for v in (
            recovered_vat_rate,
            recovered_monthly_vat,
            recovered_monthly_gross,
            recovered_monthly_net,
        )
    )

    if tax_rate_percent is None and recovered_vat_rate is not None:
        try:
            tax_rate_percent = float(recovered_vat_rate)
        except (TypeError, ValueError):
            tax_rate_percent = None

    rate: Optional[Decimal] = None
    if tax_rate_percent is not None:
        try:
            rate = Decimal(str(tax_rate_percent)) / Decimal(100)
        except Exception:
            rate = None

    if rate is None:
        return CostTaxBreakdown(
            base_tax_basis=tax_basis,
            rate_percent=tax_rate_percent,
            currency=currency,
            monthly_net=monthly_net,
            monthly_gross=monthly_gross,
            annual_net=annual_net,
            annual_gross=annual_gross,
            explanation=(
                f"Basis={tax_basis.value}; Oppositions-Basis offen, weil kein "
                "Steuersatz dokumentiert/bestaetigt ist (manuelle Pruefung)."
                + (" Monatswert aus Jahreswert / 12 abgeleitet." if derived_monthly else "")
            ),
        )

    if tax_basis == TaxBasis.NET:
        if recovered_monthly_gross is not None:
            # Direkt belegter Brutto-Monatswert (Vertrag): Jahres-Brutto aus
            # Monat x 12, damit die Vertragsrundung erhalten bleibt.
            monthly_gross = _round_if_currency(recovered_monthly_gross, 2)
            if annual is not None:
                annual_gross = _round_if_currency(recovered_monthly_gross * Decimal(12), 2)
            elif monthly is not None:
                annual_gross = _round_if_currency(monthly * Decimal(12), 2)
        else:
            if annual is not None:
                annual_gross = _round_if_currency(annual * (Decimal(1) + rate), 2)
            if monthly is not None:
                monthly_gross = _round_if_currency(monthly * (Decimal(1) + rate), 2)
        if recovered_monthly_net is not None and monthly_net is None:
            monthly_net = _round_if_currency(recovered_monthly_net, 2)
    else:  # GROSS
        if recovered_monthly_net is not None:
            # Direkt belegter Netto-Monatswert (Vertrag): Jahres-Netto aus
            # Monat x 12, damit die Vertragsrundung erhalten bleibt.
            monthly_net = _round_if_currency(recovered_monthly_net, 2)
            if annual is not None:
                annual_net = _round_if_currency(recovered_monthly_net * Decimal(12), 2)
            elif monthly is not None:
                annual_net = _round_if_currency(monthly * Decimal(12), 2)
        else:
            if annual is not None:
                annual_net = _round_if_currency(annual / (Decimal(1) + rate), 2)
            if monthly is not None:
                monthly_net = _round_if_currency(monthly / (Decimal(1) + rate), 2)
        if recovered_monthly_gross is not None and monthly_gross is None:
            monthly_gross = _round_if_currency(recovered_monthly_gross, 2)

    if recovered_monthly_vat is not None and monthly_gross is not None and monthly_net is not None:
        monthly_tax = _round_if_currency(recovered_monthly_vat, 2)
    elif monthly_gross is not None and monthly_net is not None:
        monthly_tax = _round_if_currency(monthly_gross - monthly_net, 2)
    else:
        monthly_tax = None

    if recovered_monthly_vat is not None and annual_gross is not None and annual_net is not None:
        annual_tax = _round_if_currency(recovered_monthly_vat * Decimal(12), 2)
    elif annual_gross is not None and annual_net is not None:
        annual_tax = _round_if_currency(annual_gross - annual_net, 2)
    else:
        annual_tax = None

    recovered_note = (
        " Zahlen direkt aus dem Vertragstext belegt (Netto/MwSt/Brutto), "
        "nicht durch die KI errechnet."
        if recovered
        else ""
    )

    return CostTaxBreakdown(
        computed=True,
        base_tax_basis=tax_basis,
        rate_percent=tax_rate_percent,
        currency=currency,
        monthly_net=monthly_net,
        monthly_gross=monthly_gross,
        annual_net=annual_net,
        annual_gross=annual_gross,
        monthly_tax=monthly_tax,
        annual_tax=annual_tax,
        explanation=(
            f"Basis={tax_basis.value}, Satz={tax_rate_percent:g} %. "
            "Gegen-Basis exakt ueber den Satz abgeleitet."
            + (" Monatswert aus Jahreswert / 12 abgeleitet." if derived_monthly else "")
            + recovered_note
        ),
    )


def collect_price_development(c: Costs) -> list[PriceDevelopmentItem]:
    """Sammelt Preisfixierungs-/Preisentwicklungs-Angaben aus den EXTRAHIERTEN Feldern.

    Reine Extraktions-Sicht; nichts wird neu interpretiert. Mehrere Quellen
    (Preisklausel + Indexierung) werden als separate, evidence-getragene Fakten
    geliefert.
    """
    items: list[PriceDevelopmentItem] = []
    if c.price_adjustment_clause:
        items.append(
            PriceDevelopmentItem(
                key="price_adjustment_clause",
                label="Preisklausel",
                text=c.price_adjustment_clause,
                evidence_field_ref="costs.price_adjustment_clause",
                status=CalculationStatus.EXPLICIT,
            )
        )
    if c.price_indexation:
        items.append(
            PriceDevelopmentItem(
                key="price_indexation",
                label="Preisindexierung",
                text=c.price_indexation,
                evidence_field_ref="costs.price_indexation",
                status=CalculationStatus.EXPLICIT,
            )
        )
    return items


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


# ------------------------------------------------ Rekurrente Quellen (PR-3)

# Stabile Priorität (für source_period/Label), nicht für die Mathematik.
# Gibt an, welche Quelle als „primär" zitiert wird, wenn mehrere korroborieren.
_RECURRING_ORDER = [
    ("monthly_cost", "monthly"),
    ("quarterly_cost", "quarterly"),
    ("semi_annual_cost", "semi_annual"),
    ("annual_cost", "annual"),
]


def _source_period(m: Optional[Money]) -> Optional[str]:
    """Bezugsperiode einer wiederkehrenden Geldangabe (explizit oder Default)."""
    if m is not None and m.period:
        return (m.period or "").strip().lower()
    return None


def _collect_recurring_sources(c: Costs, default_currency: str):
    """Sammelt die PRIMÄREN wiederkehrenden Quellen (primärer Recurring-Charge).

    Returns (sources, mf):
    - sources: monthly/quarterly/semi_annual/annual (und defensiv weekly) mit
      annualisierter Größe. Diese Feldgruppen werden als MEHRERE SICHTEN EINER
      wiederkehrenden Hauptgebühr korroboriert (nie addiert) – siehe
      `test_annual_monthly_never_added`.
    - mf: die Foundation-/Wartungsgebühr ALS EIGENSTÄNDIGE CHARGE (separat,
      nicht in die Korroboration gemischt; nie blind zur Hauptgebühr addiert).
    """
    sources = []

    for key, default_period in _RECURRING_ORDER:
        m = getattr(c, key, None)
        if m is None or m.amount is None:
            continue
        period = _source_period(m) or default_period
        factor = scaling_factor(period)
        if factor is None:
            # z. B. monthly_cost überraschend als 'once' klassifiziert -> nicht
            # deterministisch annualisierbar; als Einzelposten belassen, nicht recap.
            continue
        sources.append({
            "key": key,
            "period": period,
            "amount": _amount(m),
            "annual": _amount(m) * factor,
            "currency": _currency(m, default_currency),
        })

    # Wochenbetrag (defensiv; das Modell deklariert weekly_cost nicht, aber
    # bestehende Daten können es tragen).
    weekly = getattr(c, "weekly_cost", None)
    if weekly is not None and weekly.amount is not None:
        sources.append({
            "key": "weekly_cost",
            "period": "weekly",
            "amount": _amount(weekly),
            "annual": _amount(weekly) * Decimal(52),
            "currency": _currency(weekly, default_currency),
        })

    mf = c.maintenance_fee
    return sources, mf


def _coherence(a: Optional[Decimal], b: Optional[Decimal], currency: str) -> Optional[str]:
    """Korrobation zweier annualisierter Werte (kleine exakte Toleranz)."""
    if a is None or b is None:
        return None
    if a == b:
        return "exact"
    larger = max(abs(a), abs(b))
    if larger == 0:
        return "exact"
    if abs(a - b) / larger <= Decimal("0.005"):
        return "within_tolerance"
    return None


def _annual_result(
    sources: list[dict],
    mf: Optional[Money],
    default_currency: Optional[str],
) -> MoneyFieldResult:
    """Leitet das normalisierte Jahreswiederkehrende ab.

    Reihenfolge der Quellen:
    1. Primäre wiederkehrende Hauptgebühr (monthly/quarterly/.../weekly),
       ggf. korroboriert über mehrere Sichten – nie addiert.
    2. Falls KEINE primäre Quelle: eine Wartungsgebühr MIT wiederkehrender
       Periode wird als alleinige wiederkehrende Charge annualisiert.
    3. Eine Wartungsgebühr OHNE Periode bleibt nicht-annualisierbar (review).
    """
    if sources:
        primary = sources[0]
        annual_value = primary["annual"]
        currency = primary["currency"]
        if len(sources) == 1:
            return _mk(
                annual_value,
                CalculationStatus.CALCULATED,
                currency,
                (f"{_label(primary['key'])} {primary['amount']} "
                 f"({primary['period']}) => jährlich {annual_value}{((' ' + currency) if currency else '')}."),
                {primary["key"]: str(primary["amount"])},
            )
        # Mehrere Sichten einer Hauptgebühr -> alle annualisierten Werte korroborieren.
        for s in sources:
            if _coherence(annual_value, s["annual"], "x") is None:
                return _mk(
                    None,
                    CalculationStatus.CONFLICT,
                    currency,
                    "Mehrere wiederkehrende Beträge widersprechen sich nach "
                    f"Annualisierung ({_fmt_sources(sources, currency)}); kein "
                    "normalisierter Wert.",
                    {s2["key"]: str(s2["annual"]) for s2 in sources},
                    review=True,
                )
        return _mk(
            annual_value,
            CalculationStatus.CALCULATED,
            currency,
            f"Mehrere wiederkehrende Quellen annualisiert und korroboriert: {_fmt_sources(sources, currency)}.",
            {s["key"]: str(s["annual"]) for s in sources},
        )

    # Keine primäre Quelle -> Wartungsgebühr als alleinige Charge prüfen.
    if mf is not None and mf.amount is not None:
        period = _source_period(mf)
        factor = scaling_factor(period) if period else None
        if factor is not None:
            val = _amount(mf) * factor
            return _mk(
                val,
                CalculationStatus.CALCULATED,
                _currency(mf, default_currency),
                (f"Wartungsgebühr {_amount(mf)} ({period}) => jährlich {val} "
                 f"{((' ' + (_currency(mf, default_currency) or '')) if _currency(mf, default_currency) else '')}."),
                {"maintenance_fee": str(_amount(mf)), "period": period},
            )
        return _mk(
            None,
            CalculationStatus.NOT_CALCULABLE,
            _currency(mf, default_currency),
            "Wartungsgebühr vorhanden, aber wiederkehrende Periode unbekannt "
            "(nicht annualisierbar).",
            {"maintenance_fee": str(_amount(mf))},
            review=True,
        )

    return _mk(None, CalculationStatus.NOT_CALCULABLE, default_currency, "Nicht bestimmt.", {})


def _label(key: str) -> str:
    return _CHARGE_LABELS.get(key, key)


_CHARGE_LABELS = {
    "monthly_cost": "Monatlich",
    "quarterly_cost": "Quartalsweise",
    "semi_annual_cost": "Halbjährlich",
    "annual_cost": "Jährlich",
    "weekly_cost": "Wöchentlich",
    "maintenance_fee": "Wartungsgebühr",
}


def _fmt_sources(sources: list[dict], currency: str) -> str:
    parts = []
    for s in sources:
        parts.append(f"{_label(s['key'])} {s['annual']}{(' ' + (s['currency'] or currency)) if currency else ''}")
    return "; ".join(parts)



def _explicit_duration_years(contract: Contract) -> Optional[int]:
    """Return an explicitly modelled whole-year duration, otherwise None.

    A staged price schedule is summed only when its coverage can be proven against
    an extracted duration.  We intentionally do not infer a year count from dates.
    """
    duration = getattr(getattr(contract, "dates", None), "duration", None)
    if duration is None or duration.value is None or duration.unit is None:
        return None
    unit = getattr(duration.unit, "value", duration.unit)
    if str(unit).lower() != "years":
        return None
    try:
        value = int(duration.value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _scheduled_total(contract: Contract, c: Costs, default_currency: Optional[str]) -> MoneyFieldResult:
    """Sum a complete, explicit per-period price schedule conservatively.

    Safety invariants:
    - every item must have amount, currency and unique 1-based period_index;
    - the contract must explicitly state a whole-year duration;
    - period indexes must cover exactly 1..duration_years;
    - all currencies must match;
    - variable/conditional charges are deliberately excluded.
    """
    schedule = list(getattr(c, "scheduled_prices", None) or [])
    if not schedule:
        return MoneyFieldResult(
            status=CalculationStatus.NOT_CALCULABLE,
            explanation="Kein expliziter, vollständiger Preisplan modelliert.",
        )

    years = _explicit_duration_years(contract)
    if years is None:
        return MoneyFieldResult(
            status=CalculationStatus.REVIEW_REQUIRED,
            explanation=(
                "Preisplan vorhanden, aber keine explizite Vertragsdauer in ganzen Jahren; "
                "Vollständigkeit des Preisplans ist nicht beweisbar."
            ),
            review_required=True,
            inputs={"scheduled_prices": str(len(schedule))},
        )

    by_index: dict[int, tuple[Decimal, str]] = {}
    currencies: set[str] = set()
    for item in schedule:
        idx = getattr(item, "period_index", None)
        money = getattr(item, "amount", None)
        amount = _amount(money)
        currency = _currency(money, default_currency)
        if idx is None or amount is None or not currency:
            return MoneyFieldResult(
                status=CalculationStatus.REVIEW_REQUIRED,
                explanation=(
                    "Preisplan unvollständig: mindestens eine Preisstufe hat keinen "
                    "eindeutigen Periodenindex, Betrag oder Währung."
                ),
                review_required=True,
                inputs={"scheduled_prices": str(len(schedule))},
            )
        idx = int(idx)
        if idx in by_index:
            return MoneyFieldResult(
                status=CalculationStatus.CONFLICT,
                explanation=f"Mehrere Preisstufen für Vertragsperiode {idx}.",
                review_required=True,
                inputs={"duplicate_period_index": str(idx)},
            )
        cur = str(currency).upper()
        currencies.add(cur)
        by_index[idx] = (amount, cur)

    if len(currencies) != 1:
        return MoneyFieldResult(
            status=CalculationStatus.CONFLICT,
            explanation="Preisplan enthält mehrere Währungen; kein FX und keine Aggregation.",
            review_required=True,
            inputs={"currencies": ",".join(sorted(currencies))},
        )

    expected = set(range(1, years + 1))
    actual = set(by_index)
    if actual != expected:
        return MoneyFieldResult(
            status=CalculationStatus.REVIEW_REQUIRED,
            explanation=(
                f"Preisplan deckt Vertragsperioden {sorted(actual)} ab; erwartet sind "
                f"vollständig {sorted(expected)}. Kein Teilplan wird als Gesamtwert ausgegeben."
            ),
            review_required=True,
            inputs={"duration_years": str(years), "period_indexes": ",".join(map(str, sorted(actual)))},
        )

    total = sum((by_index[i][0] for i in range(1, years + 1)), Decimal("0"))
    currency = next(iter(currencies))
    expression = " + ".join(str(by_index[i][0]) for i in range(1, years + 1))
    variable_count = len(getattr(c, "variable_charges", None) or [])
    suffix = (
        f" {variable_count} bedingte/verbrauchsabhängige Zusatzposition(en) sind bewusst nicht enthalten."
        if variable_count
        else ""
    )
    return MoneyFieldResult(
        value=_round_if_currency(total, 2),
        currency=currency,
        status=CalculationStatus.CALCULATED,
        explanation=(
            f"Vollständiger expliziter Preisplan für {years} Vertragsjahre: "
            f"{expression} = {total} {currency}.{suffix}"
        ),
        inputs={f"scheduled_prices.{i}.amount": str(by_index[i][0]) for i in range(1, years + 1)},
    )


def calculate_contract_costs(contract: Contract) -> CalculateContractCosts:
    """Berechnet die Kostenfelder eines Vertrags (pure Funktion)."""
    c: Costs = contract.costs
    default_currency = c.default_currency
    result = CalculateContractCosts()
    notes = result.notes

    # -------- Steuerbasis: NUR explizit modelliert (keine MwSt-Annahme) --------
    raw_tax = (c.tax_basis or "").strip().lower()
    if raw_tax == "net":
        result.tax_basis = TaxBasis.NET
    elif raw_tax == "gross":
        result.tax_basis = TaxBasis.GROSS
    else:
        result.tax_basis = TaxBasis.UNKNOWN
    result.tax_rate_percent = c.tax_rate_percent

    # -------- Normalisierte wiederkehrende Kosten (annual + monthly) --------
    sources, mf = _collect_recurring_sources(c, default_currency)
    annual = _annual_result(sources, mf, default_currency)

    monthly_result = None
    # Kanonische Monatsebene: ein DIREKT belegter Monatsbetrag (Quelle mit
    # Bezugsperiode 'monthly', z. B. monthly_cost 5916.67) gewinnt – er wird als
    # evidence-getragener Fakt (status=explicit) übernommen, NICHT aus dem
    # Jahreswert / 12 abgeleitet (Provenienz!). Nur wenn gar kein Monatsfakt
    # vorliegt, wird der Monatswert deterministisch aus dem Jahreswert abgeleitet.
    monthly_sources = [s for s in sources if s["period"] == "monthly"]
    if monthly_sources:
        src = monthly_sources[0]
        currency = src["currency"] or default_currency
        monthly_val = _round_if_currency(src["amount"], 2)
        monthly_result = _mk(
            monthly_val,
            CalculationStatus.EXPLICIT,
            currency,
            (f"{_label(src['key'])} {src['amount']} ({src['period']}) => "
             f"monatlich {monthly_val}. Jährlich = {monthly_val} x 12 = "
             f"{_round_if_currency(monthly_val * Decimal(12), 2)}."),
            {src["key"]: str(src["amount"])},
        )
    elif annual.value is not None and annual.currency == default_currency:
        monthly_result = _mk(
            _round_if_currency(annual.value / Decimal(12), 2),
            CalculationStatus.CALCULATED,
            annual.currency,
            f"Jährlich {annual.value} / 12 = monatlich.",
            {"annual": str(annual.value)},
        )

    corroboration = None
    if len(sources) >= 2:
        corroboration = _coherence(sources[0]["annual"], sources[1]["annual"], "x")
    source_period = "unknown"
    if sources:
        source_period = sources[0]["period"]
    elif mf is not None and mf.amount is not None:
        sp = _source_period(mf)
        source_period = sp if scaling_factor(sp) is not None else "unknown"
    result.normalized_recurring = RecurringCostNormalized(
        annual=annual,
        monthly=monthly_result or MoneyFieldResult(),
        source_period=source_period,
        corroboration=corroboration,
    )

    # -------- Netto/Brutto-Aufteilung (nur mit verlaesslicher Basis + Satz) --------
    result.tax_breakdown = derive_tax_breakdown(
        annual=annual.value,
        monthly=monthly_result.value if monthly_result is not None else None,
        tax_basis=result.tax_basis,
        tax_rate_percent=result.tax_rate_percent,
        currency=default_currency,
    )

    # -------- Preisfixierung/-entwicklung (evidence-getragene Extraktions-Sicht) --------
    result.price_development = collect_price_development(c)

    if mf is not None and mf.amount is not None and annual.value is None:
        notes.append("Wartungsgebühr ohne wiederkehrende Periode – nicht annualisiert (manuelle Prüfung).")

    # -------- Währungs-Konflikt-Erkennung (aggregierbar nur bei gleicher Währung) --------
    currencies = {
        cur
        for m in (
            c.monthly_cost,
            c.quarterly_cost,
            c.semi_annual_cost,
            c.annual_cost,
            c.maintenance_fee,
            c.total_contract_value,
            c.one_time_cost,
            c.setup_installation_cost,
            c.hourly_rate,
            c.travel_cost,
            c.material_cost,
            c.additional_costs,
            getattr(c, "weekly_cost", None),
            *[item.amount for item in (getattr(c, "scheduled_prices", None) or [])],
            *[item.amount for item in (getattr(c, "variable_charges", None) or [])],
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
        ("setup_installation_cost", "Einmalig (Aufbau/Installation)"),
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
    # Bedingte/verbrauchsabhängige Positionen bleiben einzeln sichtbar und werden
    # niemals in einen Fix-/Gesamtwert addiert.
    for index, charge in enumerate(getattr(c, "variable_charges", None) or []):
        amount = _amount(charge.amount)
        cur = _currency(charge.amount, default_currency)
        category_totals.append(
            CostCategory(
                key=f"variable_charges.{index}",
                label=charge.label or charge.unit or "Variable Zusatzkosten",
                currency=cur,
                amount=amount,
                status=(CalculationStatus.EXPLICIT if amount is not None and cur else CalculationStatus.NOT_CALCULABLE),
                explanation=(
                    f"Bedingte Position: {amount} {cur or ''} je {charge.unit or 'definierter Einheit'}; "
                    "nicht in Fix-/Gesamtwert addiert."
                    if amount is not None
                    else "Bedingte Position ohne berechenbaren Betrag."
                ),
                inputs=[f"variable_charges.{index}"],
                components=[
                    MoneyFieldResult(
                        value=amount,
                        currency=cur,
                        status=(CalculationStatus.EXPLICIT if amount is not None and cur else CalculationStatus.NOT_CALCULABLE),
                        explanation="Direkt extrahierte bedingte Preisposition; keine automatische Aggregation.",
                        inputs={f"variable_charges.{index}": str(amount) if amount is not None else ""},
                    )
                ],
            )
        )
    result.category_totals = category_totals

    # -------- Total-Vertragswert: expliziter Wert ODER vollständig belegter Preisplan --------
    explicit_tcv = _amount(c.total_contract_value)
    scheduled = _scheduled_total(contract, c, default_currency)
    if explicit_tcv is not None:
        explicit_currency = _currency(c.total_contract_value, default_currency)
        result.total_contract_value = MoneyFieldResult(
            value=explicit_tcv,
            currency=explicit_currency,
            status=CalculationStatus.EXPLICIT,
            explanation="Gesamtvertragswert explizit im Vertrag angegeben.",
            inputs={"total_contract_value": str(explicit_tcv)},
        )
        # Wenn zusätzlich ein vollständig berechenbarer Plan existiert, muss er
        # den expliziten Gesamtwert bestätigen; sonst ist das ein echter Konflikt.
        if scheduled.value is not None and scheduled.status == CalculationStatus.CALCULATED:
            if (scheduled.currency or "").upper() == (explicit_currency or "").upper() and scheduled.value != explicit_tcv:
                result.total_contract_value = MoneyFieldResult(
                    value=None,
                    currency=explicit_currency,
                    status=CalculationStatus.CONFLICT,
                    explanation=(
                        f"Expliziter Gesamtwert {explicit_tcv} {explicit_currency or ''} widerspricht "
                        f"vollständigem Preisplan {scheduled.value} {scheduled.currency or ''}."
                    ),
                    review_required=True,
                    inputs={"total_contract_value": str(explicit_tcv), "scheduled_total": str(scheduled.value)},
                )
        notes.append(
            f"total_contract_value={explicit_tcv} {explicit_currency or ''} "
            "(bewusst NICHT um variable/bedingte Kosten erhöht)."
        )
    else:
        result.total_contract_value = scheduled

    # Backward-compatible aggregate status: historically every reliable total
    # was exposed as CALCULATED, even when it was directly explicit. Detailed
    # provenance now lives in `total_contract_value.status`.
    if (
        result.total_contract_value.value is not None
        and result.total_contract_value.status in {CalculationStatus.EXPLICIT, CalculationStatus.CALCULATED}
    ):
        result.total_contract_value_status = CalculationStatus.CALCULATED
    else:
        result.total_contract_value_status = result.total_contract_value.status

    return result


def _round_if_currency(value: Decimal, cents: int) -> Decimal:
    """Währungsrundung an Ausgabegrenzen (Dezimal-Rundung, halb auf)."""
    if value is None:
        return value
    try:
        return round_currency(value, cents)
    except Exception:
        return value
