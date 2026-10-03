"""Fokussierte Tests für die deterministische Date & Cost Engine (STEP 9).

Deckt die vertraglich geforderten Edge-Cases ab:
- Kalenderbewusste Datum-Arithmetik (Monat Ende des Monats, Schaltjahr,
  Kündigung in Tagen/Wochen/Monaten/Jahren, Deadline bereits vergangen,
  automatische Verlängerung mit bekannter Frist, mehrfache historische
  Verlängerungen, fehlende Verlängerungsfrist, as_of exakt auf Grenze,
  ereignisbasiert, mehrdeutige Kündigung).
- Geld: monthly→annual, quarterly→annual, semiannual→annual, annual×1,
  einmalig ausgeschlossen, Decimal-Präzision (0.1+0.2), annual+monthly
  korroborierend/konflikt, unbekannte Periode/fehlender Betrag/unbekannte
  Währung/Währungsmismatch, Stundensatz/Reise/Material nicht blind-addiert,
  Steuerbasis unbekannt, zero vs None.

Wichtig: as_of_date wird IMMER explizit übergeben (kein Maschinen-Datum).
Negative Tageswerte sind gültig (wurden nicht auf 0 geklemmt).
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.contracts.calculation import calculate_contract
from app.contracts.calculation.calendar_ import add_duration, month_add
from app.contracts.calculation.money import round_currency, scaling_factor
from app.contracts.calculation.models import (
    CalcDuration,
    CalculationStatus as CS,
)
from app.models.contract import (
    Contract,
    ContractDates,
    Costs,
    ScheduledPrice,
    VariableCharge,
    Termination,
)
from app.models.enums import ContractStatus, TimeUnit
from app.models.values import Duration, FlexibleDate, Money


def make_contract(
    *,
    start: date | None = None,
    end: date | None = None,
    duration: tuple[int, TimeUnit] | None = None,
    cancellation: tuple[int, TimeUnit] | None = None,
    to_contract_end: str | None = "to_contract_end",
    cond: str | None = None,
    auto_renewal: bool | None = None,
    renewal: tuple[int, TimeUnit] | None = None,
    status: ContractStatus = ContractStatus.UNKNOWN,
    costs: Costs | None = None,
) -> Contract:
    return Contract(
        id="TEST",
        status=status,
        dates=ContractDates(
            start_date=FlexibleDate(date=start) if start else None,
            end_date=FlexibleDate(date=end) if end else None,
            duration=Duration(value=duration[0], unit=duration[1]) if duration else None,
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


# ============================================================ Calendar arithmetic


class TestCalendarArithmetic:
    def test_month_add_eom_leap(self):
        assert month_add(date(2024, 1, 31), 1) == date(2024, 2, 29)

    def test_month_add_eom_non_leap(self):
        assert month_add(date(2023, 1, 31), 1) == date(2023, 2, 28)

    def test_month_add_eom_two_months(self):
        assert month_add(date(2024, 1, 31), 2) == date(2024, 3, 31)

    def test_month_add_jan30_plus1(self):
        assert month_add(date(2024, 1, 30), 1) == date(2024, 2, 29)

    def test_month_negative_subtract(self):
        assert month_add(date(2024, 3, 31), -1) == date(2024, 2, 29)


# ============================================================ End date


class TestEndDate:
    def test_explicit_end(self):
        c = make_contract(start=date(2024, 1, 1), end=date(2024, 12, 31))
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.calculated_end_date.value == date(2024, 12, 31)
        assert r.dates.calculated_end_date.status == CS.EXPLICIT

    def test_derived_start_plus_duration(self):
        c = make_contract(
            start=date(2024, 1, 31), duration=(11, TimeUnit.MONTHS)
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        # 31.01.2024 + 11 Monate (EOM-klemmend) -> 31.12.2024
        assert r.dates.calculated_end_date.value == date(2024, 12, 31)
        assert r.dates.calculated_end_date.status == CS.CALCULATED

    def test_derived_duration_years_leap(self):
        # 29.02.2024 + 1 Jahr
        c = make_contract(start=date(2024, 2, 29), duration=(1, TimeUnit.YEARS))
        r = calculate_contract(c, as_of_date=date(2025, 1, 1))
        assert r.dates.calculated_end_date.value == date(2025, 2, 28)

    def test_no_end_event_based(self):
        c = Contract(
            id="T",
            dates=ContractDates(start_date=FlexibleDate(condition="nach Inbetriebnahme")),
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.dates.calculated_end_date.value is None
        assert r.dates.calculated_end_date.status == CS.NOT_CALCULABLE
        assert r.dates.calculated_end_date.review_required is True

    def test_no_termination_at_all(self):
        c = Contract(id="T")
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.dates.calculated_end_date.value is None
        assert r.dates.calculated_end_date.status == CS.NOT_CALCULABLE

    def test_explicit_vs_derived_conflict(self):
        c = make_contract(
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            duration=(6, TimeUnit.MONTHS),  # would end 2024-07-01
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.dates.calculated_end_date.status == CS.CONFLICT
        assert r.dates.calculated_end_date.review_required is True

    def test_explicit_matches_derived(self):
        c = make_contract(
            start=date(2024, 1, 1),
            end=date(2025, 1, 1),
            duration=(12, TimeUnit.MONTHS),
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        # 01.01.2024 + 12 Monate = 01.01.2025 == explizites Ende -> Korroboration
        assert r.dates.calculated_end_date.status in (CS.EXPLICIT, CS.CALCULATED)

    def test_inclusive_year_term_no_conflict_uat(self):
        # UAT Re-Test Defect 1: 01.04.2025 + 4 Vertragsjahre -> 31.03.2029
        # (inklusive Vertragslaufzeit = letzter Tag vor dem Jahrestag 01.04.2029).
        # Das ist KEIN Konflikt: kein Review-Flag, kein Warning, kein Risiko.
        c = make_contract(
            start=date(2025, 4, 1),
            end=date(2029, 3, 31),
            duration=(4, TimeUnit.YEARS),
        )
        r = calculate_contract(c, as_of_date=date(2026, 6, 1))
        end = r.dates.calculated_end_date
        assert end.status == CS.EXPLICIT
        assert end.value == date(2029, 3, 31)
        assert end.review_required is False
        assert not any("weichen ab" in reason for reason in r.review_reasons)
        assert r.dates.days_until_end.status == CS.CALCULATED
        assert r.dates.current_contract_status.status == ContractStatus.ACTIVE

    def test_inclusive_months_term_no_conflict(self):
        # Monatsbasierte inklusive Laufzeit: 01.04.2025 + 3 Monate -> 30.06.2025.
        c = make_contract(
            start=date(2025, 4, 1),
            end=date(2025, 6, 30),
            duration=(3, TimeUnit.MONTHS),
        )
        r = calculate_contract(c, as_of_date=date(2025, 5, 1))
        end = r.dates.calculated_end_date
        assert end.status == CS.EXPLICIT
        assert end.value == date(2025, 6, 30)
        assert end.review_required is False

    def test_one_day_after_derived_still_conflict(self):
        # Explizites Ende EINEN Tag NACH dem Jahrestag ist KEIN inklusiver
        # Laufzeittag, sondern ein echter Konflikt.
        c = make_contract(
            start=date(2025, 4, 1),
            end=date(2029, 4, 2),
            duration=(4, TimeUnit.YEARS),
        )
        r = calculate_contract(c, as_of_date=date(2026, 1, 1))
        assert r.dates.calculated_end_date.status == CS.CONFLICT
        assert r.dates.calculated_end_date.review_required is True

    def test_days_based_duration_no_inclusive_tolerance(self):
        # Tagesbasierte Dauer (Wochen/Tage) kennt die inklusive Jahrestags-Regel
        # NICHT: 2024-01-01 + 365 Tage (Schaltjahr) = 2024-12-31; explizit
        # 2025-01-01 (= 366 Tage) bleibt ein echter Konflikt, kein stiller
        # Ein-Tages-Spielraum.
        c = make_contract(
            start=date(2024, 1, 1),
            end=date(2025, 1, 1),
            duration=(365, TimeUnit.DAYS),
        )
        r = calculate_contract(c, as_of_date=date(2024, 3, 1))
        assert r.dates.calculated_end_date.status == CS.CONFLICT
        assert r.dates.calculated_end_date.review_required is True


# ============================================================ Status / days


class TestStatusAndDays:
    def test_active_before_end(self):
        c = make_contract(end=date(2024, 12, 31))
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.current_contract_status.status == ContractStatus.ACTIVE
        assert r.dates.days_until_end.value == (date(2024, 12, 31) - date(2024, 6, 1)).days

    def test_expired_after_end_negative_days_not_clamped(self):
        c = make_contract(end=date(2024, 1, 1))
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.current_contract_status.status == ContractStatus.EXPIRED
        assert r.dates.days_until_end.value < 0  # negatives, nicht auf 0 geklemmt

    def test_as_of_exactly_on_boundary(self):
        # as_of == end_date -> gilt als EXPIRED (liegt NICHT davor)
        c = make_contract(end=date(2024, 12, 31))
        r = calculate_contract(c, as_of_date=date(2024, 12, 31))
        assert r.dates.current_contract_status.status == ContractStatus.EXPIRED

    def test_terminated_if_explicit(self):
        c = make_contract(end=date(2024, 12, 31), status=ContractStatus.TERMINATED)
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.current_contract_status.status == ContractStatus.TERMINATED

    def test_unknown_without_data(self):
        c = Contract(id="T")
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.dates.current_contract_status.status == ContractStatus.UNKNOWN


# ============================================================ Cancellation


class TestCancellation:
    def test_cancellation_months(self):
        c = make_contract(
            end=date(2024, 12, 31), cancellation=(3, TimeUnit.MONTHS)
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.status == CS.CALCULATED
        assert r.dates.latest_cancellation_date.value == date(2024, 9, 30)

    def test_cancellation_days_weeks_years(self):
        c = make_contract(end=date(2024, 12, 31), cancellation=(2, TimeUnit.WEEKS))
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.value == date(2024, 12, 17)

    def test_cancellation_deadline_passed_negative(self):
        c = make_contract(end=date(2024, 12, 31), cancellation=(12, TimeUnit.MONTHS))
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        # letzter Kündigungstermin 31.12.2023, lange vergangen
        assert r.dates.days_until_latest_cancellation.value < 0

    def test_cancellation_missing_period(self):
        c = make_contract(end=date(2024, 12, 31))
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.status == CS.NOT_CALCULABLE

    def test_cancellation_ambiguous_relation(self):
        # freie Formulierung ohne klare Relation -> REVIEW_REQUIRED, nicht still gerechnet
        c = make_contract(
            end=date(2024, 12, 31),
            cancellation=(3, TimeUnit.MONTHS),
            to_contract_end=None,
            cond="schriftlich 3 Monate zum Halbjahresende",
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.status == CS.REVIEW_REQUIRED
        assert r.dates.latest_cancellation_date.value is None


# ============================================================ Auto renewal


class TestAutomaticRenewal:
    def test_renewal_known_future(self):
        c = make_contract(
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            auto_renewal=True,
            renewal=(12, TimeUnit.MONTHS),
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.next_renewal_date.status == CS.CALCULATED
        assert r.dates.next_renewal_date.value == date(2025, 12, 31)
        # boundaries enthält initiale Phase (0) + erste Verlängerung (1)
        assert [b.period_index for b in r.dates.renewal_boundaries] == [0, 1]

    def test_renewal_boundaries_start_unknown(self):
        # Ohne start_date wird die aktuelle Periode (Index 0, Ende = known end)
        # trotzdem als relevante Periode mitgeführt; die nächste folgt als Index 1.
        c = make_contract(
            end=date(2024, 12, 31),
            auto_renewal=True,
            renewal=(12, TimeUnit.MONTHS),
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert [b.period_index for b in r.dates.renewal_boundaries] == [0, 1]
        assert r.dates.renewal_boundaries[0].end_date == date(2024, 12, 31)
        assert r.dates.renewal_boundaries[1].end_date == date(2025, 12, 31)

    def test_renewal_requires_period(self):
        c = make_contract(end=date(2024, 12, 31), auto_renewal=True, renewal=None)
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.next_renewal_date.status == CS.NOT_CALCULABLE
        assert r.dates.next_renewal_date.review_required is True

    def test_no_auto_renewal(self):
        c = make_contract(end=date(2024, 12, 31), auto_renewal=False, renewal=(12, TimeUnit.MONTHS))
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.next_renewal_date.status == CS.NOT_CALCULABLE

    def test_renewal_without_end(self):
        c = make_contract(auto_renewal=True, renewal=(12, TimeUnit.MONTHS))
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.next_renewal_date.status == CS.NOT_CALCULABLE

    def test_renewal_eom(self):
        c = make_contract(
            end=date(2024, 1, 31),
            auto_renewal=True,
            renewal=(1, TimeUnit.MONTHS),
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        # 31.01 + 1 Monat -> 29.02.2024 (Schaltjahr, EOM-klemmend)
        assert r.dates.next_renewal_date.value == date(2024, 2, 29)


# ============================================================ A. Kündigungs-Relation (streng)


class TestCancellationRelationStrict:
    """A – keine Default-Annahme: Absenz von Evidenz ist KEIN Beweis für
    „zum Vertragsende". Nur explizite strukturierte Markierung erlaubt Frist."""

    def test_no_relation_no_definitive_deadline(self):
        # 3-Monats-Frist + KEINE Relation -> keine definitive Frist
        c = make_contract(
            end=date(2024, 12, 31),
            cancellation=(3, TimeUnit.MONTHS),
            to_contract_end=None,
            cond=None,
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.status == CS.NOT_CALCULABLE
        assert r.dates.latest_cancellation_date.value is None

    def test_explicit_to_contract_end_calculated(self):
        # explizite, strukturierte „zum Vertragsende"-Markierung -> berechenbar
        c = make_contract(
            end=date(2024, 12, 31),
            cancellation=(3, TimeUnit.MONTHS),
            to_contract_end="to_contract_end",
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.status == CS.CALCULATED
        assert r.dates.latest_cancellation_date.value == date(2024, 9, 30)

    def test_explicit_other_relation_no_deadline(self):
        # explizit „andere" Relation -> nicht berechenbar
        c = make_contract(
            end=date(2024, 12, 31),
            cancellation=(3, TimeUnit.MONTHS),
            to_contract_end="false",
            cond=None,
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.status == CS.NOT_CALCULABLE
        assert r.dates.latest_cancellation_date.value is None

    def test_ambiguous_free_text_no_deadline(self):
        # freie Formulierung, keine strukturierte Markierung -> REVIEW_REQUIRED
        c = make_contract(
            end=date(2024, 12, 31),
            cancellation=(3, TimeUnit.MONTHS),
            to_contract_end=None,
            cond="spätestens drei Monate vor Fristablauf in Textform",
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.status == CS.REVIEW_REQUIRED
        assert r.dates.latest_cancellation_date.value is None

    def test_quarter_reference_no_deadline(self):
        # Quartal-/Halbjahresbezug ohne positive Markierung -> keine Frist
        c = make_contract(
            end=date(2024, 12, 31),
            cancellation=(3, TimeUnit.MONTHS),
            to_contract_end=None,
            cond="3 Monate zum Halbjahresende",
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.status == CS.REVIEW_REQUIRED
        assert r.dates.latest_cancellation_date.value is None

    def test_positive_marker_without_condition_calculated(self):
        # positive Markierung, keine Bedingung -> berechenbar
        c = make_contract(
            end=date(2024, 12, 31),
            cancellation=(1, TimeUnit.MONTHS),
            to_contract_end="true",
            cond=None,
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.latest_cancellation_date.status == CS.CALCULATED


# ============================================================ B. Wiederholte Verlängerungen


class TestRepeatedRenewals:
    """B – as_of-abhängige, begrenzte, arithmetische Verlängerungslogik.
    Konvention: as_of_date == Grenze gehört zur ENDENDEN Periode.
    next_renewal_value = E_1 (vor erstem Verlängerungs-Switch) bzw.
    E_current (innerhalb einer Verlängerungsperiode)."""

    def test_before_initial_end(self):
        c = make_contract(
            end=date(2020, 12, 31),
            auto_renewal=True,
            renewal=(1, TimeUnit.YEARS),
        )
        r = calculate_contract(c, as_of_date=date(2020, 6, 30))
        assert r.dates.next_renewal_date.value == date(2021, 12, 31)
        # relevante Periode = initiale Laufzeit (Index 0), nächste = Index 1
        assert [b.period_index for b in r.dates.renewal_boundaries] == [0, 1]

    def test_first_renewal_approaching(self):
        c = make_contract(
            end=date(2020, 12, 31),
            auto_renewal=True,
            renewal=(1, TimeUnit.YEARS),
        )
        # direkt vor dem ersten Switch
        r = calculate_contract(c, as_of_date=date(2020, 12, 31))
        # as_of == initial_end -> endende Periode 0; next = E_1
        assert r.dates.next_renewal_date.value == date(2021, 12, 31)

    def test_many_historical_annual_renewals(self):
        # initial 2020-12-31, 1 Jahr -> E_6 = 2026-12-31 für as_of 2026-08-30
        c = make_contract(
            end=date(2020, 12, 31),
            auto_renewal=True,
            renewal=(1, TimeUnit.YEARS),
        )
        r = calculate_contract(c, as_of_date=date(2026, 8, 30))
        assert r.dates.next_renewal_date.value == date(2026, 12, 31)
        # begrenzte Boundary-Liste: nur relevante + nächste (keine 6-Einträge-Historie)
        assert [b.period_index for b in r.dates.renewal_boundaries] == [6, 7]
        assert r.dates.renewal_boundaries[0].end_date == date(2026, 12, 31)
        assert r.dates.renewal_boundaries[1].end_date == date(2027, 12, 31)

    def test_monthly_renewals_across_years(self):
        # Monatliche Verlaengerung (EOM-klemmend nach calendar_.py-Monatsregel).
        # NICHT naiv "Index 24 / 2026-01-31": die EOM-Klemmung verschiebt den
        # Ankertag nach einem Februar-Ueberlauf, daher ist der aktuelle Index
        # exakt durch die Verkettung zu bestimmen (kein hart kodierter Wert).
        c = make_contract(
            end=date(2024, 1, 31),
            auto_renewal=True,
            renewal=(1, TimeUnit.MONTHS),
        )
        r = calculate_contract(c, as_of_date=date(2026, 1, 30))
        nr = r.dates.next_renewal_date
        assert nr.status == CS.CALCULATED

        # Semantisches Invariant (inklusive Ende): die relevanten Grenzen und
        # dass as_of innerhalb der aktuell relevanten Periode liegt.
        # 1) aktuelle Periode (deren schliessende Grenze = next_renewal).
        current = r.dates.renewal_boundaries[0]
        nxt = r.dates.renewal_boundaries[1]
        # 2) previous boundary < as_of <= current boundary (ending-period convention)
        assert current.start_date < date(2026, 1, 30) <= current.end_date
        # 3) next_renewal_date == aktueller Periode schliessende Grenze
        assert nr.value == current.end_date
        # 4) naechste Periode folgt direkt nach der aktuellen (Start = Ende+1)
        assert nxt.start_date == add_duration(current.end_date, CalcDuration(days=1))
        assert nxt.period_index == current.period_index + 1

    def test_as_of_exactly_on_boundary(self):
        # Konvention: as_of == Grenze gehoert zur ENDENDEN Periode, d.h.
        # aktuelle relevante Periode schliesst GENAU an diesem Tag.
        # next_renewal_date ist die schliessende Grenze der aktuellen Periode
        # und kann daher == as_of_date sein (hier E_6 = 2026-12-31).
        c = make_contract(
            end=date(2020, 12, 31),
            auto_renewal=True,
            renewal=(1, TimeUnit.YEARS),
        )
        r = calculate_contract(c, as_of_date=date(2026, 12, 31))
        assert r.dates.next_renewal_date.value == date(2026, 12, 31)
        current = r.dates.renewal_boundaries[0]
        # aktuelle Periode endet exakt an der Grenze == as_of
        assert current.end_date == date(2026, 12, 31)
        assert current.start_date < date(2026, 12, 31) <= current.end_date
        assert r.dates.renewal_boundaries[1].end_date == date(2027, 12, 31)

    def test_leap_year_eom(self):
        # initial 2024-01-31 + 1 Monat = 2024-02-29 (Schaltjahr, EOM-klemmend)
        c = make_contract(
            end=date(2024, 1, 31),
            auto_renewal=True,
            renewal=(1, TimeUnit.MONTHS),
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 31))
        assert r.dates.next_renewal_date.value == date(2024, 2, 29)

    def test_missing_renewal_period(self):
        c = make_contract(
            end=date(2024, 12, 31), auto_renewal=True, renewal=None
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.next_renewal_date.status == CS.NOT_CALCULABLE
        assert r.dates.next_renewal_date.review_required is True

    def test_invalid_nonpositive_renewal_period(self):
        # renewal_period 0 ist nicht-positiv -> nicht berechenbar (kein Loop-Risiko)
        c = make_contract(
            end=date(2024, 12, 31),
            auto_renewal=True,
            renewal=(0, TimeUnit.MONTHS),
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.next_renewal_date.status == CS.NOT_CALCULABLE
        assert r.dates.renewal_boundaries == []

    def test_cancellation_uses_relevant_renewal_boundary(self):
        # as_of nach abgelaufener Frist der aktuellen Periode -> nächste
        # Verlängerungsgrenze relevant (nicht nur erste historische Verlängerung).
        # initial end 2020-12-31, 1 Jahr; as_of 2026-08-30.
        # relevante Grenze E_6 = 2026-12-31, Frist 3 Monate -> 2026-09-30 (Zukunft)
        c = make_contract(
            end=date(2020, 12, 31),
            cancellation=(3, TimeUnit.MONTHS),
            to_contract_end="to_contract_end",
            auto_renewal=True,
            renewal=(1, TimeUnit.YEARS),
        )
        r = calculate_contract(c, as_of_date=date(2026, 8, 30))
        assert r.dates.latest_cancellation_date.status == CS.CALCULATED
        assert r.dates.latest_cancellation_date.value == date(2026, 9, 30)


# ============================================================ C. Konflikt-Propagation


class TestConflictPropagation:
    """C – ein CONFLICT des Enddatums darf NICHT als sichere Frist/Verlängerung
    durchrutschen; abhängige Ergebnisse werden REVIEW_REQUIRED, ohne den
    (expliziten) Wert zu verwerfen."""

    def _conflicted_contract(self):
        # explizites Ende 2024-12-31 vs. abgeleitetes 2024-07-01 -> CONFLICT
        return make_contract(
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
            duration=(6, TimeUnit.MONTHS),
            cancellation=(3, TimeUnit.MONTHS),
            to_contract_end="to_contract_end",
            auto_renewal=True,
            renewal=(12, TimeUnit.MONTHS),
        )

    def test_end_conflict_remains_visible(self):
        r = calculate_contract(self._conflicted_contract(), as_of_date=date(2024, 6, 1))
        assert r.dates.calculated_end_date.status == CS.CONFLICT
        assert r.dates.calculated_end_date.value == date(2024, 12, 31)

    def test_downstream_cancellation_not_unqualified_calculated(self):
        r = calculate_contract(self._conflicted_contract(), as_of_date=date(2024, 6, 1))
        res = r.dates.latest_cancellation_date
        assert res.status == CS.REVIEW_REQUIRED
        assert res.review_required is True
        # Wert bleibt sichtbar, aber NIE unqualifiziert CALCULATED
        assert res.value is not None

    def test_downstream_renewal_not_unqualified_calculated(self):
        r = calculate_contract(self._conflicted_contract(), as_of_date=date(2024, 6, 1))
        res = r.dates.next_renewal_date
        assert res.status == CS.REVIEW_REQUIRED
        assert res.review_required is True

    def test_boundary_entries_marked_review(self):
        r = calculate_contract(self._conflicted_contract(), as_of_date=date(2024, 6, 1))
        assert all(b.review_required for b in r.dates.renewal_boundaries)

    def test_unrelated_cost_calculation_unaffected(self):
        # gültige Kosten eines Konflikt-Vertrags bleiben valide berechnet
        c = self._conflicted_contract()
        c.costs = Costs(
            default_currency="EUR",
            monthly_cost=Money(amount=100, currency="EUR"),
            annual_cost=Money(amount=1200, currency="EUR"),
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        ann = r.costs.normalized_recurring.annual
        assert ann.value == Decimal("1200")
        assert ann.status == CS.CALCULATED
        assert r.dates.calculated_end_date.status == CS.CONFLICT  # Datums-Konflikt bleibt


# ============================================================ D. Safety-Invarianten


class TestSTEP9SafetyInvariants:
    """D – Verifikation bestehender Sicherheits-Invarianten."""

    def test_terminated_not_inferred_from_past_end(self):
        # abgelaufenes Ende -> EXPIRED, NICHT TERMINATED (ohne explizite Markierung)
        c = make_contract(end=date(2020, 1, 1), status=ContractStatus.UNKNOWN)
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.current_contract_status.status == ContractStatus.EXPIRED

    def test_terminated_only_when_explicit(self):
        c = make_contract(end=date(2020, 1, 1), status=ContractStatus.TERMINATED)
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.dates.current_contract_status.status == ContractStatus.TERMINATED

    def test_annual_monthly_never_added(self):
        # annual+monthly werden korroboriert, nie als separate Summe addiert
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                monthly_cost=Money(amount=100, currency="EUR"),
                annual_cost=Money(amount=1200, currency="EUR"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.normalized_recurring.annual.value == Decimal("1200")

    def test_total_value_not_added_to_recurring(self):
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                monthly_cost=Money(amount=100, currency="EUR"),
                total_contract_value=Money(amount=9999, currency="EUR"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.normalized_recurring.annual.value == Decimal("1200")

    def test_currency_never_aggregated(self):
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                monthly_cost=Money(amount=100, currency="EUR"),
                annual_cost=Money(amount=1200, currency="USD"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.currency_conflict is True

    def test_no_default_vat(self):
        c = make_contract()
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.tax_basis.value == "unknown"

    def test_field_failure_does_not_invalidate_others(self):
        # ein Konflikt invalidisiert nicht unabhängige, gültige Felder
        c = make_contract(
            end=date(2024, 12, 31),
            costs=Costs(
                default_currency="EUR",
                monthly_cost=Money(amount=100, currency="EUR"),
                annual_cost=Money(amount=1200, currency="USD"),
            ),
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.costs.currency_conflict is True
        assert r.dates.calculated_end_date.value == date(2024, 12, 31)
        assert r.dates.latest_cancellation_date.status in (
            CS.CALCULATED, CS.NOT_CALCULABLE, CS.REVIEW_REQUIRED,
        )


# ============================================================ Costs
class TestCostNormalization:
    def test_monthly_to_annual(self):
        c = make_contract(costs=Costs(default_currency="EUR", monthly_cost=Money(amount=100, currency="EUR")))
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        ann = r.costs.normalized_recurring.annual
        assert ann.status == CS.CALCULATED
        assert ann.value == Decimal("1200")

    def test_annual_explicit(self):
        c = make_contract(costs=Costs(default_currency="EUR", annual_cost=Money(amount=2400, currency="EUR")))
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.normalized_recurring.annual.value == Decimal("2400")

    def test_annual_plus_monthly_corroborate(self):
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                monthly_cost=Money(amount=100, currency="EUR"),
                annual_cost=Money(amount=1200, currency="EUR"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        ann = r.costs.normalized_recurring.annual
        assert ann.value == Decimal("1200")
        assert ann.status == CS.CALCULATED
        assert not r.costs.recurring_cost_conflict

    def test_annual_monthly_conflict(self):
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                monthly_cost=Money(amount=100, currency="EUR"),
                annual_cost=Money(amount=9999, currency="EUR"),  # stark abweichend
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        ann = r.costs.normalized_recurring.annual
        assert ann.status == CS.CONFLICT
        assert r.costs.recurring_cost_conflict is True

    def test_decimal_precision_0_1_plus_0_2(self):
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                monthly_cost=Money(amount=0.1, currency="EUR"),
                annual_cost=Money(amount=1.2, currency="EUR"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.normalized_recurring.annual.value == Decimal("1.2")

    def test_once_not_annualized(self):
        # einmalig wird nicht in wiederkehrenden Total addiert
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                one_time_cost=Money(amount=5000, currency="EUR"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.normalized_recurring.annual.value is None
        assert r.costs.normalized_recurring.annual.status == CS.NOT_CALCULABLE

    def test_hourly_not_ann_total(self):
        # Stundensatz wird nicht blind in einen jährlichen Total geschoben
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                hourly_rate=Money(amount=150, currency="EUR"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        keys = [cat.key for cat in r.costs.category_totals]
        assert "hourly_rate" in keys
        # kein normalisiertes annual
        assert r.costs.normalized_recurring.annual.value is None

    def test_currency_mismatch_no_aggregation(self):
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                monthly_cost=Money(amount=100, currency="EUR"),
                annual_cost=Money(amount=1200, currency="USD"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.currency_conflict is True

    def test_tax_basis_unknown(self):
        c = make_contract()
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.tax_basis.value == "unknown"

    def test_zero_vs_none(self):
        # amount=0 ist ein gültiger, nicht-None Betrag; amount=None fehlt.
        zero = make_contract(
            costs=Costs(default_currency="EUR", annual_cost=Money(amount=0, currency="EUR"))
        )
        none = make_contract(costs=Costs(default_currency="EUR"))
        rz = calculate_contract(zero, as_of_date=date(2024, 1, 1))
        rn = calculate_contract(none, as_of_date=date(2024, 1, 1))
        assert rz.costs.normalized_recurring.annual.value == Decimal("0")
        assert rn.costs.normalized_recurring.annual.value is None


class TestMoneyScalingPrimitive:
    """Annualisierungs-Primitive (scaling_factor) für alle Wiederkehr-Perioden.

    Hinweis: Das Extraktionsmodell `Costs` besitzt Betragsfelder für
    monthly/annual/weekly; quarterly/semiannual wird über `scaling_factor`
    zentral bereitgestellt (dokumentiert in STEP_9_CHECKPOINT §6) und hier
    direkt verifiziert.
    """

    def test_scaling_factors(self):
        assert scaling_factor("monthly") == Decimal(12)
        assert scaling_factor("quarterly") == Decimal(4)
        assert scaling_factor("semi_annual") == Decimal(2)
        assert scaling_factor("semiannual") == Decimal(2)
        assert scaling_factor("annual") == Decimal(1)
        assert scaling_factor("yearly") == Decimal(1)

    def test_scaling_factors_excluded(self):
        # once/hourly/unknown/other/conditional -> nicht annualisierbar
        for p in ("once", "hourly", "unknown", "other", "conditional", "weird"):
            assert scaling_factor(p) is None

    def test_quarterly_and_semiannual_yield_annual(self):
        q = Decimal("100") * scaling_factor("quarterly")
        s = Decimal("100") * scaling_factor("semi_annual")
        assert q == Decimal("400")
        assert s == Decimal("200")

    def test_round_currency_half_up(self):
        assert round_currency(Decimal("1.005")) == Decimal("1.01")
        assert round_currency(Decimal("1.004")) == Decimal("1.00")
        assert round_currency(Decimal("2")) == Decimal("2.00")


# ============================================================ Determinism / review


class TestEngineContract:
    def test_pure_no_hidden_datetime(self):
        import inspect
        import app.contracts.calculation.engine as eng
        src = inspect.getsource(eng)
        assert "datetime.now" not in src and "date.today" not in src

    def test_field_failure_does_not_invalidate_others(self):
        # Währungs-Konflikt bei Kosten darf Datumsfelder nicht zerstören
        c = make_contract(
            end=date(2024, 12, 31),
            costs=Costs(
                monthly_cost=Money(amount=100, currency="EUR"),
                annual_cost=Money(amount=1200, currency="USD"),
            ),
        )
        r = calculate_contract(c, as_of_date=date(2024, 6, 1))
        assert r.costs.currency_conflict is True
        assert r.dates.calculated_end_date.value == date(2024, 12, 31)

    def test_review_reasons_surface_ambiguity(self):
        c = Contract(id="T")  # keine Daten
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.overall_review_required is True
        assert any("unbekannt" in reason.lower() for reason in r.review_reasons)


# ============================================================ PR-3 Financial

class TestPR3FinancialIntelligence:
    """PR-3: Financial Intelligence – deterministisch, konzeptgetrennt, ehrlich.

    Kernregeln:
    - Annualisierung zentral über `scaling_factor`, Bezugsperiode aus
      `Money.period` (kein hartkodiertes x12 an separater Stelle).
    - `maintenance_fee` ist eine EIGENSTÄNDIGE Charge: sie wird nur dann als
      wiederkehrendes annualisiertes Jahr geführt, wenn sie die EINZIGE
      wiederkehrende Quelle ist UND eine annualisierbare Periode besitzt.
      Fehlt die Periode -> NOT_CALCULABLE (review, nie geraten). Sie wird
      NIE blind zur Hauptgebühr addiert.
    - quarterly/semi_annual werden (wie monthly/annual) als wiederkehrende
      Hauptgebühr erkannt und annualisiert.
    - Steuerbasis wird nur explizit übernommen (net/gross), nie erfunden.
    """

    def test_quarterly_cost_annualized(self):
        c = make_contract(
            costs=Costs(default_currency="EUR", quarterly_cost=Money(amount=100, currency="EUR"))
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        ann = r.costs.normalized_recurring.annual
        assert ann.status == CS.CALCULATED
        assert ann.value == Decimal("400")
        assert r.costs.normalized_recurring.source_period == "quarterly"

    def test_semi_annual_cost_annualized(self):
        c = make_contract(
            costs=Costs(default_currency="EUR", semi_annual_cost=Money(amount=100, currency="EUR"))
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        ann = r.costs.normalized_recurring.annual
        assert ann.value == Decimal("200")
        assert r.costs.normalized_recurring.source_period == "semi_annual"

    def test_maintenance_fee_with_period_sole_source_annualized(self):
        # Benchmark-ähnlich: Wartungsgebühr MIT vierteljährlicher Periode
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                maintenance_fee=Money(amount=100, currency="EUR", period="quarterly"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        ann = r.costs.normalized_recurring.annual
        assert ann.status == CS.CALCULATED
        assert ann.value == Decimal("400")
        assert r.costs.normalized_recurring.source_period == "quarterly"

    def test_maintenance_fee_no_period_stays_not_calculable(self):
        c = make_contract(
            costs=Costs(default_currency="EUR", maintenance_fee=Money(amount=35, currency="EUR"))
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        ann = r.costs.normalized_recurring.annual
        assert ann.value is None
        assert ann.status == CS.NOT_CALCULABLE
        assert ann.review_required is True

    def test_maintenance_fee_not_added_to_recurring(self):
        # maintenance_fee und monthly_cost sind getrennte Charges -> NICHT addiert,
        # NICHT als Konflikt erzeugt; monthly bleibt Quelle des normalized annual.
        c = make_contract(
            costs=Costs(
                default_currency="EUR",
                monthly_cost=Money(amount=100, currency="EUR"),
                maintenance_fee=Money(amount=50, currency="EUR", period="monthly"),
            )
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        ann = r.costs.normalized_recurring.annual
        assert ann.value == Decimal("1200")   # nur monthly, maintenance separat
        assert ann.status == CS.CALCULATED
        assert not r.costs.recurring_cost_conflict

    def test_tax_basis_explicit_net(self):
        c = make_contract(costs=Costs(default_currency="EUR",
                                      monthly_cost=Money(amount=100, currency="EUR"),
                                      tax_basis="net"))
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.tax_basis.value == "net"

    def test_tax_basis_explicit_gross(self):
        c = make_contract(costs=Costs(tax_basis="gross"))
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.tax_basis.value == "gross"

    def test_tax_basis_unknown_not_invented(self):
        c = make_contract(costs=Costs(tax_basis="foo"))
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.tax_basis.value == "unknown"

    def test_setup_installation_cost_is_one_time_category(self):
        c = make_contract(
            costs=Costs(default_currency="EUR", setup_installation_cost=Money(amount=999, currency="EUR"))
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        assert r.costs.normalized_recurring.annual.value is None
        keys = [cat.key for cat in r.costs.category_totals]
        assert "setup_installation_cost" in keys

    def test_monthly_rounding_is_currency_half_up(self):
        # annual/12 wird an der Ausgabegrenze auf 2 Nachkommastellen gerundet.
        c = make_contract(
            costs=Costs(default_currency="EUR", annual_cost=Money(amount=100, currency="EUR"))
        )
        r = calculate_contract(c, as_of_date=date(2024, 1, 1))
        m = r.costs.normalized_recurring.monthly
        assert m.value == Decimal("8.33")
        assert m.status == CS.CALCULATED



# ============================================================ Staged pricing / variable charges

class TestStagedPricing:
    def test_complete_four_year_schedule_calculates_total_without_fake_annual(self):
        costs = Costs(
            default_currency="EUR",
            scheduled_prices=[
                ScheduledPrice(period_index=1, period_label="1.Jahr", amount=Money(amount="0", currency="EUR", period="annual")),
                ScheduledPrice(period_index=2, period_label="2.Jahr", amount=Money(amount="8000", currency="EUR", period="annual")),
                ScheduledPrice(period_index=3, period_label="3.Jahr", amount=Money(amount="8000", currency="EUR", period="annual")),
                ScheduledPrice(period_index=4, period_label="4.Jahr", amount=Money(amount="8000", currency="EUR", period="annual")),
            ],
        )
        c = make_contract(duration=(4, TimeUnit.YEARS), costs=costs)
        r = calculate_contract(c, as_of_date=date(2026, 1, 1))
        assert r.costs.total_contract_value.value == Decimal("24000.00")
        assert r.costs.total_contract_value.currency == "EUR"
        assert r.costs.total_contract_value.status == CS.CALCULATED
        # Varying yearly prices are not misrepresented as one recurring annual price.
        assert r.costs.normalized_recurring.annual.value is None

    def test_variable_per_call_charge_is_visible_but_never_added_to_fixed_total(self):
        costs = Costs(
            default_currency="EUR",
            scheduled_prices=[
                ScheduledPrice(period_index=1, amount=Money(amount="0", currency="EUR", period="annual")),
                ScheduledPrice(period_index=2, amount=Money(amount="8000", currency="EUR", period="annual")),
                ScheduledPrice(period_index=3, amount=Money(amount="8000", currency="EUR", period="annual")),
                ScheduledPrice(period_index=4, amount=Money(amount="8000", currency="EUR", period="annual")),
            ],
            variable_charges=[
                VariableCharge(
                    label="Fixed per call",
                    amount=Money(amount="2226", currency="EUR", period="once"),
                    unit="per_call",
                )
            ],
        )
        c = make_contract(duration=(4, TimeUnit.YEARS), costs=costs)
        r = calculate_contract(c, as_of_date=date(2026, 1, 1))
        assert r.costs.total_contract_value.value == Decimal("24000.00")
        variable = [x for x in r.costs.category_totals if x.key.startswith("variable_charges.")]
        assert len(variable) == 1
        assert variable[0].amount == Decimal("2226")
        assert "nicht" in variable[0].explanation.lower()

    def test_incomplete_schedule_never_becomes_total(self):
        costs = Costs(
            default_currency="EUR",
            scheduled_prices=[
                ScheduledPrice(period_index=1, amount=Money(amount="0", currency="EUR", period="annual")),
                ScheduledPrice(period_index=2, amount=Money(amount="8000", currency="EUR", period="annual")),
                ScheduledPrice(period_index=4, amount=Money(amount="8000", currency="EUR", period="annual")),
            ],
        )
        c = make_contract(duration=(4, TimeUnit.YEARS), costs=costs)
        r = calculate_contract(c, as_of_date=date(2026, 1, 1))
        assert r.costs.total_contract_value.value is None
        assert r.costs.total_contract_value.status == CS.REVIEW_REQUIRED
        assert r.overall_review_required is True
