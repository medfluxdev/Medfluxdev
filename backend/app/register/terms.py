"""Deterministische Laufzeit-/Kuendigungslogik fuer Registervertraege (H1.3).

Fuenf Laufzeitmodelle (Vertragsart):
- fixed_term: feste Laufzeit, endet ohne Kuendigung.
- terminable: kuendbar mit Frist zu einem Kalenderstichtag (Monats-,
  Quartals-, Halbjahres-, Jahresende) oder jederzeit.
- terminable_min_term: wie terminable, aber fruehestens zum Ende einer
  Mindestlaufzeit.
- auto_renewal: Erstlaufzeit, verlaengert sich automatisch um die
  Verlaengerungsperiode, kuendbar mit Frist zum jeweiligen Periodenende.
- perpetual: unbefristet ohne Vertragsende (keine Fristen).

Regeln:
- Eine Kuendigung kann fruehestens ab Vertragsbeginn und nicht in der
  Vergangenheit erklaert werden (`floor = max(as_of, Beginn)`).
- Ende einer Laufzeit ist inklusiv: Beginn + Dauer - 1 Tag.
- "kuendbar bis" = moegliches Ende minus Kuendigungsfrist (kalenderbewusst).
- Erinnerung = "kuendbar bis" (bzw. Vertragsende bei fester Laufzeit) minus
  Vorlauf in Monaten.
- Fehlende Pflichtangaben fuehren zu `incomplete` mit Feldliste, nie zu
  geratenen Werten.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from app.contracts.calculation.calendar_ import add_duration, month_add, subtract_duration
from app.contracts.calculation.models import CalcDuration

_BOUNDARY_MONTHS = {
    "month_end": frozenset(range(1, 13)),
    "quarter_end": frozenset({3, 6, 9, 12}),
    "half_year_end": frozenset({6, 12}),
    "year_end": frozenset({12}),
}
_MAX_ITERATIONS = 2000


@dataclass(frozen=True)
class Period:
    value: int
    unit: str

    def as_calc(self) -> CalcDuration:
        if self.unit == "days":
            return CalcDuration(days=self.value)
        if self.unit == "weeks":
            return CalcDuration(weeks=self.value)
        if self.unit == "months":
            return CalcDuration(months=self.value)
        if self.unit == "years":
            return CalcDuration(years=self.value)
        raise ValueError(f"unknown unit {self.unit!r}")

    def label(self) -> str:
        names = {
            "days": ("Tag", "Tage"),
            "weeks": ("Woche", "Wochen"),
            "months": ("Monat", "Monate"),
            "years": ("Jahr", "Jahre"),
        }[self.unit]
        return f"{self.value} {names[0] if self.value == 1 else names[1]}"


def period(value: Optional[int], unit: Optional[str]) -> Optional[Period]:
    if value is None or unit is None or value < 0:
        return None
    if unit not in ("days", "weeks", "months", "years"):
        return None
    return Period(int(value), unit)


@dataclass(frozen=True)
class TermInputs:
    term_model: Optional[str] = None
    start_date: Optional[date] = None
    fixed_end_date: Optional[date] = None
    initial_term: Optional[Period] = None
    minimum_term: Optional[Period] = None
    notice_period: Optional[Period] = None
    notice_to: Optional[str] = None
    renewal_period: Optional[Period] = None
    reminder_lead_months: Optional[int] = None
    terminated_effective: Optional[date] = None
    ended_on: Optional[date] = None


@dataclass
class TermResult:
    status: str
    earliest_end: Optional[date] = None
    cancel_by: Optional[date] = None
    possible_end: Optional[date] = None
    actual_end: Optional[date] = None
    reminder_date: Optional[date] = None
    missing: list[str] = field(default_factory=list)
    explanation: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        def iso(value: Optional[date]) -> Optional[str]:
            return value.isoformat() if value else None

        return {
            "status": self.status,
            "earliest_end": iso(self.earliest_end),
            "cancel_by": iso(self.cancel_by),
            "possible_end": iso(self.possible_end),
            "actual_end": iso(self.actual_end),
            "reminder_date": iso(self.reminder_date),
            "missing": list(self.missing),
            "explanation": list(self.explanation),
        }


def _de(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _end_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def first_boundary_on_or_after(day: date, target: str) -> date:
    """Erster Kalenderstichtag (Monats-/Quartals-/Halbjahres-/Jahresende) >= day."""
    allowed = _BOUNDARY_MONTHS.get(target)
    if allowed is None:
        raise ValueError(f"unknown notice target {target!r}")
    year, month = day.year, day.month
    for _ in range(13):
        if month in allowed:
            candidate = _end_of_month(year, month)
            if candidate >= day:
                return candidate
        month += 1
        if month == 13:
            year, month = year + 1, 1
    raise AssertionError("unreachable")


def next_boundary(boundary: date, target: str) -> date:
    return first_boundary_on_or_after(boundary + timedelta(days=1), target)


def term_end(start: date, length: Period) -> date:
    """Inklusives Ende: Beginn + Dauer - 1 Tag."""
    return add_duration(start, length.as_calc()) - timedelta(days=1)


def _following_period_end(previous_end: date, length: Period) -> date:
    return term_end(previous_end + timedelta(days=1), length)


def _reminder(anchor: Optional[date], lead_months: Optional[int]) -> Optional[date]:
    if anchor is None or lead_months is None or lead_months < 0:
        return None
    return month_add(anchor, -lead_months)


def _calendar_end(
    *, floor: date, lower_bound: date, notice: Period, target: str
) -> tuple[date, date]:
    """Erster Stichtag >= lower_bound, dessen Kuendigungstermin >= floor liegt."""
    boundary = first_boundary_on_or_after(lower_bound, target)
    for _ in range(_MAX_ITERATIONS):
        cancel_by = subtract_duration(boundary, notice.as_calc())
        if cancel_by >= floor:
            return boundary, cancel_by
        boundary = next_boundary(boundary, target)
    raise ValueError("no boundary found")


def _anytime_end(*, floor: date, lower_bound: date, notice: Period) -> tuple[date, date]:
    candidate = max(add_duration(floor, notice.as_calc()), lower_bound)
    return candidate, subtract_duration(candidate, notice.as_calc())


TERM_MODEL_LABELS = {
    "fixed_term": "Feste Laufzeit",
    "terminable": "Kündbarer Vertrag",
    "terminable_min_term": "Kündbarer Vertrag mit Mindestlaufzeit",
    "auto_renewal": "Automatische Verlängerung",
    "perpetual": "Unbefristet (ohne Ende)",
}


def compute_terms(inputs: TermInputs, as_of: date) -> TermResult:
    if inputs.terminated_effective is not None:
        return TermResult(
            status="complete",
            possible_end=inputs.terminated_effective,
            actual_end=inputs.terminated_effective,
            explanation=[f"Gekündigt zum {_de(inputs.terminated_effective)}."],
        )
    if inputs.ended_on is not None:
        return TermResult(
            status="complete",
            possible_end=inputs.ended_on,
            actual_end=inputs.ended_on,
            explanation=[f"Beendet am {_de(inputs.ended_on)}."],
        )

    model = inputs.term_model
    if model is None:
        return TermResult(status="incomplete", missing=["term_model"], explanation=["Vertragsart fehlt."])
    if model == "perpetual":
        return TermResult(
            status="not_applicable",
            explanation=["Unbefristeter Vertrag ohne Vertragsende: keine Kündigungsfrist berechnet."],
        )
    if inputs.start_date is None:
        return TermResult(status="incomplete", missing=["term_start_date"], explanation=["Vertragsbeginn fehlt."])

    start = inputs.start_date
    floor = max(as_of, start)

    if model in ("fixed_term", "auto_renewal"):
        if inputs.fixed_end_date is not None:
            initial_end = inputs.fixed_end_date
            source = f"festes Vertragsende {_de(initial_end)}"
        elif inputs.initial_term is not None:
            initial_end = term_end(start, inputs.initial_term)
            source = f"Beginn {_de(start)} + Laufzeit {inputs.initial_term.label()}"
        else:
            return TermResult(
                status="incomplete",
                missing=["term_fixed_end_date", "initial_term_value"],
                explanation=["Vertragsende oder Laufzeit fehlt."],
            )
        if initial_end < start:
            return TermResult(
                status="incomplete",
                missing=["term_fixed_end_date"],
                explanation=["Vertragsende liegt vor dem Vertragsbeginn."],
            )

        if model == "fixed_term":
            lines = [f"Feste Laufzeit: Ende = {source}."]
            if initial_end < as_of:
                lines.append("Das Vertragsende ist überschritten.")
            return TermResult(
                status="complete",
                earliest_end=initial_end,
                possible_end=initial_end,
                reminder_date=_reminder(initial_end, inputs.reminder_lead_months),
                explanation=lines,
            )

        missing = []
        if inputs.notice_period is None:
            missing.append("notice_period_value")
        if missing:
            return TermResult(
                status="incomplete",
                earliest_end=initial_end,
                missing=missing,
                explanation=["Kündigungsfrist fehlt."],
            )
        notice = inputs.notice_period
        end = initial_end
        cancel_by = subtract_duration(end, notice.as_calc())
        periods = 0
        while cancel_by < floor:
            if inputs.renewal_period is None:
                return TermResult(
                    status="incomplete",
                    earliest_end=initial_end,
                    missing=["renewal_period_value"],
                    explanation=[
                        f"Kündigungstermin zum {_de(end)} ist verstrichen; Verlängerungsperiode fehlt."
                    ],
                )
            end = _following_period_end(end, inputs.renewal_period)
            cancel_by = subtract_duration(end, notice.as_calc())
            periods += 1
            if periods > _MAX_ITERATIONS:
                raise ValueError("renewal iteration overflow")
        lines = [
            f"Erstlaufzeit endet am {_de(initial_end)} ({source}).",
            f"Kündigungsfrist {notice.label()} zum Periodenende.",
        ]
        if periods:
            lines.append(
                f"Verlängert sich um {inputs.renewal_period.label()}; nächstmögliches Ende nach {periods} Verlängerung(en)."
            )
        if inputs.notice_to not in (None, "contract_end"):
            lines.append("Hinweis: Bei automatischer Verlängerung gilt die Frist zum Periodenende.")
        return TermResult(
            status="complete",
            earliest_end=initial_end,
            cancel_by=cancel_by,
            possible_end=end,
            reminder_date=_reminder(cancel_by, inputs.reminder_lead_months),
            explanation=lines,
        )

    if model in ("terminable", "terminable_min_term"):
        missing = []
        if inputs.notice_period is None:
            missing.append("notice_period_value")
        if inputs.notice_to is None or inputs.notice_to == "contract_end":
            missing.append("notice_to")
        min_end: Optional[date] = None
        if model == "terminable_min_term":
            if inputs.minimum_term is None:
                missing.append("minimum_term_value")
            else:
                min_end = term_end(start, inputs.minimum_term)
        if missing:
            explanation = ["Angaben zur Kündigung fehlen."]
            if inputs.notice_to == "contract_end":
                explanation = ["Ein kündbarer Vertrag braucht einen Kündigungsstichtag (z. B. Quartalsende)."]
            return TermResult(status="incomplete", earliest_end=min_end, missing=missing, explanation=explanation)

        notice = inputs.notice_period
        lower_bound = min_end if min_end is not None else start
        if inputs.notice_to == "anytime":
            possible_end, cancel_by = _anytime_end(floor=floor, lower_bound=lower_bound, notice=notice)
            earliest_end, _ = _anytime_end(floor=start, lower_bound=lower_bound, notice=notice)
            target_label = "jederzeit"
        else:
            possible_end, cancel_by = _calendar_end(
                floor=floor, lower_bound=lower_bound, notice=notice, target=inputs.notice_to
            )
            earliest_end, _ = _calendar_end(
                floor=start, lower_bound=lower_bound, notice=notice, target=inputs.notice_to
            )
            target_label = {
                "month_end": "zum Monatsende",
                "quarter_end": "zum Quartalsende",
                "half_year_end": "zum Halbjahresende",
                "year_end": "zum Jahresende",
            }[inputs.notice_to]
        lines = [f"Kündbar mit Frist {notice.label()} {target_label}."]
        if min_end is not None:
            lines.append(f"Mindestlaufzeit bis {_de(min_end)}.")
        return TermResult(
            status="complete",
            earliest_end=earliest_end,
            cancel_by=cancel_by,
            possible_end=possible_end,
            reminder_date=_reminder(cancel_by, inputs.reminder_lead_months),
            explanation=lines,
        )

    return TermResult(status="incomplete", missing=["term_model"], explanation=["Unbekannte Vertragsart."])
