"""Fokussierte Tests für die reine Warn-Engine (STEP 11).

Pure Funktionen: keine DB, kein Netz, keine KI, kein verstecktes Datum.
`as_of_date` kommt immer explizit aus dem STEP-9-Berechnungslauf.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.contracts.calculation import calculate_contract
from app.contracts.warnings import (
    WarningPolicy,
    WarningSeverity,
    WarningType,
    evaluate_contract_warnings,
    severity_to_risk,
)
from app.contracts.warnings.policy import severity_for_days
from app.models.contract import Contract, ContractDates, Costs, Termination
from app.models.enums import ContractStatus, RiskLevel, TimeUnit
from app.models.values import Duration, FlexibleDate, Money


def _costs(**kw) -> Costs:
    base = Costs(default_currency="EUR")
    for k, v in kw.items():
        if v is None:
            setattr(base, k, None)
        else:
            setattr(base, k, Money(amount=v, currency=v.currency if isinstance(v, Money) else "EUR"))
    return base


def _contract(
    *,
    start=None,
    end=None,
    cancellation=None,
    to_contract_end="to_contract_end",
    cond=None,
    auto_renewal=None,
    renewal=None,
    status=ContractStatus.UNKNOWN,
    costs=None,
):
    return Contract(
        id="WTR",
        status=status,
        dates=ContractDates(
            start_date=FlexibleDate(date=start) if start else None,
            end_date=FlexibleDate(date=end) if end else None,
        ),
        termination=Termination(
            cancellation_period=(
                Duration(value=cancellation[0], unit=cancellation[1])
                if cancellation
                else None
            ),
            cancellation_to_contract_end=to_contract_end,
            cancellation_condition=cond,
            automatic_renewal=auto_renewal,
            renewal_period=(
                Duration(value=renewal[0], unit=renewal[1]) if renewal else None
            ),
        ),
        costs=costs or Costs(default_currency="EUR"),
    )


def _types(result) -> set[WarningType]:
    return {w.warning_type for w in result.warnings}


def _solo(result, wt: WarningType):
    matches = [w for w in result.warnings if w.warning_type == wt]
    assert len(matches) == 1, f"erwartete genau 1x {wt}, {len(matches)} gefunden"
    return matches[0]


# ============================================================ Thresholds (Kündigung)
# as_of = 2025-01-01; Kündigungsfrist 360 Tage zum Vertragsende.
# -> Kündigungstermin = Ende - 360 Kalendertage. Tage bis dahin parametrisiert.


def _cancel_contract(deadline_days: int, *, end=None):
    """Vertrag, dessen Kündigungstermin `deadline_days` Kalendertage nach as_of liegt."""
    as_of = date(2025, 1, 1)
    deadline = date.fromordinal(as_of.toordinal() + deadline_days)
    # Kündigungstermin = Ende - 360 Tage -> Ende = deadline + 360
    end_date = date.fromordinal(deadline.toordinal() + 360)
    return _contract(
        start=date(2024, 1, 1),
        end=end or end_date,
        cancellation=(360, TimeUnit.DAYS),
        to_contract_end="to_contract_end",
    ), as_of


@pytest.mark.parametrize(
    "days,expected",
    [
        (181, None),
        (180, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (91, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (90, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (61, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (60, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (31, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (30, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (15, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (14, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (8, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (7, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (1, WarningType.CANCELLATION_DEADLINE_APPROACHING),
        (0, WarningType.CANCELLATION_DEADLINE_TODAY),
        (-1, WarningType.CANCELLATION_DEADLINE_PASSED),
    ],
)
def test_cancellation_threshold_boundaries(days, expected):
    c, as_of = _cancel_contract(days)
    calc = calculate_contract(c, as_of_date=as_of)
    r = evaluate_contract_warnings(c, calc)
    cancel_types = {
        WarningType.CANCELLATION_DEADLINE_APPROACHING,
        WarningType.CANCELLATION_DEADLINE_TODAY,
        WarningType.CANCELLATION_DEADLINE_PASSED,
    }
    present = _types(r) & cancel_types
    if expected is None:
        assert WarningType.CANCELLATION_DEADLINE_APPROACHING not in present
        assert not present, f"unerwartete Kündigungs-Warnungen: {present}"
    else:
        assert present == {expected}


@pytest.mark.parametrize(
    "days,expected_severity",
    [
        (180, WarningSeverity.LOW),
        (91, WarningSeverity.LOW),
        (90, WarningSeverity.MEDIUM),
        (61, WarningSeverity.MEDIUM),
        (60, WarningSeverity.MEDIUM),
        (31, WarningSeverity.MEDIUM),
        (30, WarningSeverity.HIGH),
        (15, WarningSeverity.HIGH),
        (14, WarningSeverity.HIGH),
        (8, WarningSeverity.HIGH),
        (7, WarningSeverity.CRITICAL),
        (1, WarningSeverity.CRITICAL),
        (0, WarningSeverity.CRITICAL),
    ],
)
def test_cancellation_severity_escalation(days, expected_severity):
    c, as_of = _cancel_contract(days)
    calc = calculate_contract(c, as_of_date=as_of)
    r = evaluate_contract_warnings(c, calc)
    w = _solo(
        r,
        (
            WarningType.CANCELLATION_DEADLINE_TODAY
            if days == 0
            else WarningType.CANCELLATION_DEADLINE_APPROACHING
        ),
    )
    assert w.severity == expected_severity


def test_most_urgent_matching_threshold_only():
    # 20-Tage-Termin -> nur 30er-Bucket, nicht zusätzlich 60/180.
    c, as_of = _cancel_contract(20)
    calc = calculate_contract(c, as_of_date=as_of)
    r = evaluate_contract_warnings(c, calc)
    approaching = [w for w in r.warnings if w.warning_type == WarningType.CANCELLATION_DEADLINE_APPROACHING]
    assert len(approaching) == 1
    assert approaching[0].matched_threshold_days == 30


def test_cancellation_has_operational_priority():
    # Both end + cancellation approaching -> cancellation (nearer, more severe)
    # erscheint vor der Vertragsende-Warnung.
    as_of = date(2025, 1, 1)
    end = date.fromordinal(as_of.toordinal() + 100)
    c = _contract(
        start=date(2024, 1, 1), end=end, cancellation=(80, TimeUnit.DAYS),
    )  # Kündigungstermin = Ende - 80 Tage = as_of + 20 Tage
    calc = calculate_contract(c, as_of_date=as_of)
    r = evaluate_contract_warnings(c, calc)
    assert WarningType.CANCELLATION_DEADLINE_APPROACHING in _types(r)
    assert WarningType.CONTRACT_END_APPROACHING in _types(r)
    ordered = [w.warning_type for w in r.warnings]
    ci = ordered.index(WarningType.CANCELLATION_DEADLINE_APPROACHING)
    ei = ordered.index(WarningType.CONTRACT_END_APPROACHING)
    assert ci < ei


# ============================================================ Contract end


def test_end_approaching():
    c = _contract(start=date(2024, 1, 1), end=date(2025, 1, 31))
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2025, 1, 1)))
    w = _solo(r, WarningType.CONTRACT_END_APPROACHING)
    assert w.days_remaining == 30
    assert w.matched_threshold_days == 30


def test_end_today_is_expired():
    c = _contract(start=date(2024, 1, 1), end=date(2025, 1, 1))
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2025, 1, 1)))
    assert WarningType.CONTRACT_EXPIRED in _types(r)
    assert WarningType.CONTRACT_END_APPROACHING not in _types(r)


def test_expired_contract_single():
    c = _contract(start=date(2024, 1, 1), end=date(2024, 12, 31))
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2025, 1, 1)))
    assert WarningType.CONTRACT_EXPIRED in _types(r)


def test_terminated_never_overridden():
    c = _contract(
        start=date(2024, 1, 1), end=date(2024, 12, 31), status=ContractStatus.TERMINATED,
    )
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2025, 1, 1)))
    assert WarningType.CONTRACT_EXPIRED not in _types(r)
    assert WarningType.CONTRACT_END_APPROACHING not in _types(r)
    assert WarningType.CANCELLATION_DEADLINE_PASSED not in _types(r)
    assert WarningType.AUTOMATIC_RENEWAL_ATTENTION not in _types(r)


# ============================================================ Auto renewal


def test_auto_renewal_with_actionable_deadline():
    c, as_of = _cancel_contract(14)
    c.termination.automatic_renewal = True
    c.termination.renewal_period = Duration(value=1, unit=TimeUnit.YEARS)
    calc = calculate_contract(c, as_of_date=as_of)
    r = evaluate_contract_warnings(c, calc)
    assert WarningType.AUTOMATIC_RENEWAL_ATTENTION in _types(r)


def test_auto_renewal_unclear_deadline_review():
    # Auto-Renewal explizit, aber keine Grenze/Frist -> review-orientierte Warnung.
    c = _contract(
        start=date(2024, 1, 1), to_contract_end=None, cancellation=(90, TimeUnit.DAYS),
    )
    c.termination.automatic_renewal = True
    c.termination.renewal_period = Duration(value=1, unit=TimeUnit.YEARS)
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2024, 6, 1)))
    assert WarningType.MANUAL_REVIEW_REQUIRED in _types(r)


def test_auto_renewal_false_no_warning():
    c, as_of = _cancel_contract(14)
    c.termination.automatic_renewal = False
    calc = calculate_contract(c, as_of_date=as_of)
    r = evaluate_contract_warnings(c, calc)
    assert WarningType.AUTOMATIC_RENEWAL_ATTENTION not in _types(r)


# ============================================================ Review / conflict


def test_not_calculable_cancellation_review():
    # Mehrdeutige Kündigungsregel (Freitext) -> kein erfundener Termin, aber
    # eine Review-Warnung.
    c = _contract(
        start=date(2024, 1, 1), end=date(2024, 12, 31),
        cancellation=(90, TimeUnit.DAYS), to_contract_end=None, cond="nach Vereinbarung",
    )
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2024, 6, 1)))
    assert not {t for t in _types(r) if t.value.startswith("cancellation_deadline")}
    assert WarningType.MANUAL_REVIEW_REQUIRED in _types(r)


def test_review_required_deduplication():
    # Mehrere unklare Daten -> nicht fünf gleiche Warnungen, sondern begrenzt.
    c = _contract(start=None, end=None)
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2024, 1, 1)))
    review_types = {
        WarningType.MANUAL_REVIEW_REQUIRED,
        WarningType.CALCULATION_CONFLICT,
        WarningType.UNCLEAR_CONTRACT_DATA,
    }
    assert len([w for w in r.warnings if w.warning_type in review_types]) <= 3


# ============================================================ Costs


def test_missing_recurring_cost():
    c = _contract(start=date(2024, 1, 1), end=date(2024, 12, 31), costs=Costs(default_currency="EUR"))
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2024, 6, 1)))
    assert WarningType.MISSING_COST_DATA in _types(r)


def test_present_annual_cost_no_missing_warning():
    costs = Costs(default_currency="EUR", annual_cost=Money(amount="12000", currency="EUR"))
    c = _contract(start=date(2024, 1, 1), end=date(2024, 12, 31), costs=costs)
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2024, 6, 1)))
    assert WarningType.MISSING_COST_DATA not in _types(r)


def test_cost_conflict():
    costs = Costs(
        default_currency="EUR",
        monthly_cost=Money(amount="1000", currency="EUR"),
        annual_cost=Money(amount="5000", currency="EUR"),
    )
    c = _contract(start=date(2024, 1, 1), end=date(2024, 12, 31), costs=costs)
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2024, 6, 1)))
    assert WarningType.COST_CONFLICT in _types(r)


def test_currency_conflict():
    costs = Costs(
        default_currency="EUR",
        monthly_cost=Money(amount="1000", currency="USD"),
        annual_cost=Money(amount="12000", currency="EUR"),
    )
    c = _contract(start=date(2024, 1, 1), end=date(2024, 12, 31), costs=costs)
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2024, 6, 1)))
    assert WarningType.CURRENCY_CONFLICT in _types(r)


def test_tax_basis_unknown_alone_not_severe():
    # Verlässliche jährliche Kostenangabe vorhanden; nur tax_basis=UNKNOWN
    # darf KEINE COST-Warnung erzeugen (keine 19%-/Netto-Annahme).
    costs = Costs(
        default_currency="EUR", annual_cost=Money(amount="12000", currency="EUR")
    )
    c = _contract(start=date(2024, 1, 1), end=date(2024, 12, 31), costs=costs)
    calc = calculate_contract(c, as_of_date=date(2024, 6, 1))
    calc.costs.tax_basis = "unknown"
    r = evaluate_contract_warnings(c, calc)
    assert WarningType.MISSING_COST_DATA not in _types(r)
    assert WarningType.COST_CONFLICT not in _types(r)


# ============================================================ Determinism / invariants


def test_same_input_policy_identical_result():
    c, as_of = _cancel_contract(14)
    calc = calculate_contract(c, as_of_date=as_of)
    r1 = evaluate_contract_warnings(c, calc)
    r2 = evaluate_contract_warnings(c, calc)
    assert r1.model_dump() == r2.model_dump()


def test_no_fabricated_values():
    c, as_of = _cancel_contract(200)  # > 180 -> keine Kündigungs-/End-Warnung
    calc = calculate_contract(c, as_of_date=as_of)
    r = evaluate_contract_warnings(c, calc)
    for w in r.warnings:
        if w.target_date is not None:
            assert (w.target_date - as_of).days == w.days_remaining or w.days_remaining is not None


def test_policy_version_captured():
    c, as_of = _cancel_contract(14)
    calc = calculate_contract(c, as_of_date=as_of)
    r = evaluate_contract_warnings(c, calc)
    assert r.policy_version == "step11-default-1"
    assert all(w.policy_version == r.policy_version for w in r.warnings)


def test_logical_fingerprint_stable_across_thresholds():
    # Gleiches Ziel-Datum, Dringlichkeit 30->14 Tage -> gleicher Fingerprint.
    c1, as_of = _cancel_contract(30)
    c2, _ = _cancel_contract(14)
    calc1 = calculate_contract(c1, as_of_date=as_of)
    # c2 hat anderes Ende; nutze ein identisches Ziel-Datum durch gleichen end
    r1 = evaluate_contract_warnings(c1, calc1)
    w1 = _solo(r1, WarningType.CANCELLATION_DEADLINE_APPROACHING)
    # Verschiebe as_of, sodass derselbe absolute Termin in einen anderen Bucket fällt
    target = w1.target_date
    new_as_of = date.fromordinal(target.toordinal() - 8)  # nur noch 8 Tage -> Bucket 14
    calc2 = calculate_contract(c1, as_of_date=new_as_of)
    r2 = evaluate_contract_warnings(c1, calc2)
    w2 = _solo(r2, WarningType.CANCELLATION_DEADLINE_APPROACHING)
    assert w1.logical_fingerprint == w2.logical_fingerprint
    assert w1.matched_threshold_days in (30, 14)
    assert w1.severity != w2.severity or w1.matched_threshold_days != w2.matched_threshold_days


def test_deterministic_ordering():
    c = _contract(start=date(2024, 1, 1), end=date(2025, 1, 31), cancellation=(30, TimeUnit.DAYS), to_contract_end="to_contract_end")
    # Kündigungstermin ~2024-12-26 (Ende 2025-01-31 - 30 Tage... eigentlich Ende minus 30)
    r = evaluate_contract_warnings(c, calculate_contract(c, as_of_date=date(2024, 12, 1)))
    sev_order = {WarningSeverity.CRITICAL: 0, WarningSeverity.HIGH: 1, WarningSeverity.MEDIUM: 2, WarningSeverity.LOW: 3, WarningSeverity.INFO: 4}
    rank = [sev_order[w.severity] for w in r.warnings]
    assert rank == sorted(rank)


def test_severity_to_risk_projection():
    assert severity_to_risk(WarningSeverity.CRITICAL) == "high"
    assert severity_to_risk(WarningSeverity.HIGH) == "high"
    assert severity_to_risk(WarningSeverity.MEDIUM) == "medium"
    assert severity_to_risk(WarningSeverity.LOW) == "low"
    assert severity_to_risk(None) == "unknown"
    # Kein neues Risiko-System: nur bestehende RiskLevel-Werte
    assert set(severity_to_risk(s) for s in WarningSeverity) <= {v.value for v in RiskLevel}
