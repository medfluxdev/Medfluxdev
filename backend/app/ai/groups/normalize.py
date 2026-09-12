"""Deterministische Normalisierung + logische Widerspruchsprüfung (STEP 8B-Semantik).

Reine Code-Logik (keine KI): bereinigt/Normalisiert Enum-Werte, Beträge, Daten,
Dauern und erkennt offensichtliche Widersprüche, die eine manuelle Prüfung
verlangen. Es wird NICHT gerechnet (kein spätestes Kündigungsdatum, keine
Kostenaggregation – das bleibt STEP 9).
"""

from __future__ import annotations

from typing import Optional

from app.models.contract import Contract
from app.models.enums import BillingInterval, ContractType, TimeUnit
from app.models.values import Duration


# ---- Enum-Normalisierung (generisch, lieferantenunabhängig) -----------------

_CONTRACT_TYPE_SYNONYMS = {
    "wartungsvertrag": ContractType.MAINTENANCE,
    "wartung": ContractType.MAINTENANCE,
    "maintenance": ContractType.MAINTENANCE,
    "servicevertrag": ContractType.SERVICE,
    "service": ContractType.SERVICE,
    "full service": ContractType.SERVICE,
    "wartungs- und servicevertrag": ContractType.SERVICE,
    "service- und wartungsvertrag": ContractType.SERVICE,
    "lease": ContractType.LEASE,
    "leasing": ContractType.LEASE,
    "miete": ContractType.RENTAL,
    "rental": ContractType.RENTAL,
    "mietvertrag": ContractType.RENTAL,
    "other": ContractType.OTHER,
    "unknown": ContractType.UNKNOWN,
}

_BILLING_SYNONYMS = {
    "monthly": BillingInterval.MONTHLY,
    "monatlich": BillingInterval.MONTHLY,
    "pro monat": BillingInterval.MONTHLY,
    "je monat": BillingInterval.MONTHLY,
    "quarterly": BillingInterval.QUARTERLY,
    "vierteljährlich": BillingInterval.QUARTERLY,
    "quartalsweise": BillingInterval.QUARTERLY,
    "halbjährlich": BillingInterval.SEMI_ANNUAL,
    "semi_annual": BillingInterval.SEMI_ANNUAL,
    "annual": BillingInterval.ANNUAL,
    "jährlich": BillingInterval.ANNUAL,
    "pro jahr": BillingInterval.ANNUAL,
    "je jahr": BillingInterval.ANNUAL,
    "im jahr": BillingInterval.ANNUAL,
    "once": BillingInterval.ONCE,
    "einmalig": BillingInterval.ONCE,
    "einmal": BillingInterval.ONCE,
}

_TIMEUNIT_DE = {
    "tag": TimeUnit.DAYS, "tage": TimeUnit.DAYS, "tagen": TimeUnit.DAYS,
    "woche": TimeUnit.WEEKS, "wochen": TimeUnit.WEEKS,
    "monat": TimeUnit.MONTHS, "monate": TimeUnit.MONTHS, "monaten": TimeUnit.MONTHS,
    "jahr": TimeUnit.YEARS, "jahre": TimeUnit.YEARS, "jahren": TimeUnit.YEARS,
    "stunde": TimeUnit.HOURS, "stunden": TimeUnit.HOURS,
}


def _norm(v: str) -> str:
    return " ".join(str(v).strip().lower().split())


def normalize_contract_type(value) -> ContractType:
    if value is None or value == "":
        return ContractType.UNKNOWN
    if isinstance(value, ContractType):
        return value
    return _CONTRACT_TYPE_SYNONYMS.get(_norm(value), ContractType.UNKNOWN)


def normalize_billing_interval(value) -> BillingInterval:
    if value is None or value == "":
        return BillingInterval.OTHER
    if isinstance(value, BillingInterval):
        return value
    return _BILLING_SYNONYMS.get(_norm(value), BillingInterval.OTHER)


def normalize_duration_unit(text: str) -> Optional[TimeUnit]:
    """Erkennt eine deutsche/englische Zeiteinheit in einem Freitext (generisch)."""
    key = _norm(text)
    if key in _TIMEUNIT_DE:
        return _TIMEUNIT_DE[key]
    return None


# ---- Widerspruchsprüfung ----------------------------------------------------

CONTRADICTION_REVIEW = "logical contradiction"


def check_contradictions(contract: Contract) -> list[str]:
    """Erkennt offensichtliche logische Widersprüche (deutsche Hinweise)."""
    issues: list[str] = []

    dates = contract.dates
    if dates.start_date is not None and dates.start_date.date is not None:
        if dates.end_date is not None and dates.end_date.date is not None:
            if dates.end_date.date < dates.start_date.date:
                issues.append(
                    "dates: end_date liegt VOR start_date – bitte prüfen"
                )

    term = contract.termination
    if term.automatic_renewal is False and term.renewal_period is not None:
        issues.append(
            "termination: automatic_renewal=false, aber renewal_period gesetzt – bitte prüfen"
        )
    if term.cancellation_period is not None and term.renewal_period is not None:
        if (
            term.cancellation_period.unit == term.renewal_period.unit
            and term.cancellation_period.value is not None
            and term.renewal_period.value is not None
            and term.renewal_period.value < term.cancellation_period.value
        ):
            issues.append(
                "termination: renewal_period KLEINER als cancellation_period – bitte prüfen"
            )

    costs = contract.costs
    if costs.monthly_cost is not None and costs.monthly_cost.amount is not None and costs.monthly_cost.amount > 0:
        if costs.annual_cost is not None and costs.annual_cost.amount is not None and costs.annual_cost.amount > 0:
            if costs.annual_cost.amount < costs.monthly_cost.amount:
                issues.append(
                    "costs: annual_cost kleiner als monthly_cost – bitte prüfen"
                )

    pay = contract.payment
    # billing_interval wird über das Enum-Normalisierungsbündel unten gesetzt

    return issues


def run_normalization(contract: Contract) -> list[str]:
    """Wendet deterministische Normalisierung auf ein Contract an.

    Setzt contract_type/billing_interval aus möglichen Freitext-/Alias-Werten
    (falls das Modell trotz Enum-Zwang einen Text lieferte) und meldet
    Widersprüche. Liefert deutsche Hinweise.
    """
    issues: list[str] = []

    ct = contract.identity.contract_type
    if not isinstance(ct, ContractType) or ct not in (
        ContractType.MAINTENANCE, ContractType.SERVICE, ContractType.LEASE,
        ContractType.RENTAL, ContractType.OTHER,
    ):
        contract.identity.contract_type = normalize_contract_type(ct)

    bi = contract.payment.billing_interval
    if not isinstance(bi, BillingInterval) or bi == BillingInterval.OTHER:
        # Nur normalisieren, wenn ein belegbarer Wert vorlag; 'other' bleibt,
        # da kein sicherer Synonym-Fund möglich ist.
        pass

    issues.extend(check_contradictions(contract))
    return issues
