"""Deterministische Finanzberechnung (H4), kalkulatorisch auf Basis ganzer Monate.

- Ein Eintrag gilt fuer jeden Monat von `valid_from` bis `valid_to`
  (einschliesslich der angebrochenen Monate). Offene Eintraege gelten bis zum
  Vertragsende.
- Monatswert: monatlich = Betrag, quartalsweise = Betrag/3, halbjaehrlich =
  Betrag/6, jaehrlich = Betrag/12; einmalig = voller Betrag im ersten Monat.
- Netto/Brutto werden aus Erfassungsbasis und Steuersatz abgeleitet.
- Prozentuale Preisanpassung erhoeht alle wiederkehrenden Betraege (auch
  Preisstaffeln) ab jedem Anpassungsdatum; Index-Anpassungen sind nicht
  vorhersagbar und werden nur als Hinweis ausgewiesen.
- Ohne bekanntes Vertragsende sind „bis Vertragsende" und „Gesamtlaufzeit"
  nicht berechenbar (None) – es wird nichts geraten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from app.contracts.calculation.calendar_ import month_add

CENT = Decimal("0.01")
_PER_MONTH_DIVISOR = {"monthly": 1, "quarterly": 3, "semi_annual": 6, "annual": 12}


@dataclass(frozen=True)
class EntryInput:
    direction: str
    amount: Decimal
    amount_basis: str
    vat_rate: Decimal
    interval: str
    valid_from: date
    valid_to: Optional[date] = None
    currency: str = "EUR"
    ref: Optional[str] = None


@dataclass(frozen=True)
class PriceAdjustment:
    kind: Optional[str] = None
    percent: Optional[Decimal] = None
    next_date: Optional[date] = None
    interval_months: int = 12


@dataclass
class Bucket:
    net: Decimal = Decimal("0")
    gross: Decimal = Decimal("0")

    def add(self, net: Decimal, gross: Decimal) -> None:
        self.net += net
        self.gross += gross

    def as_dict(self) -> dict[str, str]:
        return {"net": str(self.net.quantize(CENT, ROUND_HALF_UP)), "gross": str(self.gross.quantize(CENT, ROUND_HALF_UP))}


@dataclass
class DirectionSummary:
    current_year: Bucket = field(default_factory=Bucket)
    to_date: Bucket = field(default_factory=Bucket)
    remaining_to_end: Optional[Bucket] = field(default_factory=Bucket)
    total_term: Optional[Bucket] = field(default_factory=Bucket)
    annual_run_rate: Bucket = field(default_factory=Bucket)

    def as_dict(self) -> dict:
        return {
            "current_year": self.current_year.as_dict(),
            "to_date": self.to_date.as_dict(),
            "remaining_to_end": self.remaining_to_end.as_dict() if self.remaining_to_end is not None else None,
            "total_term": self.total_term.as_dict() if self.total_term is not None else None,
            "annual_run_rate": self.annual_run_rate.as_dict(),
        }


def month_index(day: date) -> int:
    return day.year * 12 + day.month - 1


def _month_start(index: int) -> date:
    return date(index // 12, index % 12 + 1, 1)


def net_gross(amount: Decimal, basis: str, vat_rate: Decimal) -> tuple[Decimal, Decimal]:
    factor = Decimal("1") + vat_rate / Decimal("100")
    if basis == "gross":
        return amount / factor, amount
    return amount, amount * factor


def adjustment_factor(adjustment: PriceAdjustment, month_start: date) -> Decimal:
    if adjustment.kind != "percent" or adjustment.percent is None or adjustment.next_date is None:
        return Decimal("1")
    step = max(1, adjustment.interval_months or 12)
    count = 0
    when = adjustment.next_date
    while when <= month_start and count < 600:
        count += 1
        when = month_add(adjustment.next_date, step * count)
    return (Decimal("1") + adjustment.percent / Decimal("100")) ** count


def monthly_values(
    entry: EntryInput, first_month: int, last_month: int, adjustment: PriceAdjustment
) -> dict[int, tuple[Decimal, Decimal]]:
    """Netto/Brutto je Monatsindex im Bereich [first_month, last_month]."""
    net, gross = net_gross(entry.amount, entry.amount_basis, entry.vat_rate)
    start = month_index(entry.valid_from)
    if entry.interval == "once":
        return {start: (net, gross)} if first_month <= start <= last_month else {}
    divisor = Decimal(_PER_MONTH_DIVISOR[entry.interval])
    end = month_index(entry.valid_to) if entry.valid_to else last_month
    out: dict[int, tuple[Decimal, Decimal]] = {}
    for index in range(max(start, first_month), min(end, last_month) + 1):
        factor = adjustment_factor(adjustment, _month_start(index))
        out[index] = (net / divisor * factor, gross / divisor * factor)
    return out


@dataclass
class ContractYear:
    """Ausgaben eines Vertragsjahrs (ab Vertragsbeginn je 12 Monate), mit und ohne Preisanpassung."""

    index: int
    start: date
    end: date
    months: int
    with_adjustment: Bucket
    without_adjustment: Bucket
    # Faktor der prozentualen Preisanpassung zu Beginn des Jahres (1 = keine Erhoehung).
    factor: Decimal

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "months": self.months,
            "partial": self.months < 12,
            "amount": self.with_adjustment.as_dict(),
            "without_adjustment": self.without_adjustment.as_dict(),
            "factor": str(self.factor.quantize(Decimal("0.000001"), ROUND_HALF_UP)),
        }


MAX_CONTRACT_YEARS = 60


def contract_years(
    entries: list[EntryInput],
    *,
    start: date,
    end: date,
    adjustment: PriceAdjustment,
) -> list[ContractYear]:
    """Ausgaben je Vertragsjahr von `start` bis `end` (letztes Jahr ggf. angebrochen); nur bei bekanntem Ende."""
    first, last = month_index(start), month_index(end)
    if last < first:
        return []
    years: list[ContractYear] = []
    for number in range(1, MAX_CONTRACT_YEARS + 1):
        year_first = first + 12 * (number - 1)
        if year_first > last:
            break
        year_last = min(year_first + 11, last)
        with_adj, without_adj = Bucket(), Bucket()
        for entry in entries:
            if entry.direction != "expense":
                continue
            for _index, (net, gross) in monthly_values(entry, year_first, year_last, adjustment).items():
                with_adj.add(net, gross)
            for _index, (net, gross) in monthly_values(entry, year_first, year_last, PriceAdjustment()).items():
                without_adj.add(net, gross)
        year_start = month_add(start, 12 * (number - 1))
        year_end = min(month_add(start, 12 * number) - timedelta(days=1), end)
        years.append(ContractYear(
            index=number, start=year_start, end=year_end, months=year_last - year_first + 1,
            with_adjustment=with_adj, without_adjustment=without_adj,
            factor=adjustment_factor(adjustment, _month_start(year_first)),
        ))
    return years


# Laufzeitangaben in „Vertragsdaten“ (Ziel für „Kein Vertragsende bekannt“).
TERM_TARGET = {"tab": "register", "section": "term"}


@dataclass
class FinanceSummary:
    currency: str
    expense: DirectionSummary
    income: DirectionSummary
    contract_end: Optional[date]
    projected_adjustment: bool
    notes: list[str]
    # Ziel je Hinweis (gleiche Reihenfolge wie `notes`): wo die fehlende Angabe gepflegt wird, sonst None.
    note_targets: list[Optional[dict]] = field(default_factory=list)
    # Letzter laufender Ausgaben-Eintrag endet nicht am Vertragsende (Luecke oder Kosten danach), sonst None.
    period_mismatch: Optional[dict] = None
    # Ausgaben je Vertragsjahr (nur mit bekanntem Beginn und Ende) und Gesamtlaufzeit ohne Preisanpassung.
    years: list[ContractYear] = field(default_factory=list)
    total_without_adjustment: Optional[Bucket] = None

    def as_dict(self) -> dict:
        return {
            "currency": self.currency,
            "expense": self.expense.as_dict(),
            "income": self.income.as_dict(),
            "contract_end": self.contract_end.isoformat() if self.contract_end else None,
            "projected_adjustment": self.projected_adjustment,
            "notes": list(self.notes),
            "note_items": [
                {"text": text, "target": self.note_targets[index] if index < len(self.note_targets) else None}
                for index, text in enumerate(self.notes)
            ],
            "period_mismatch": self.period_mismatch,
            "contract_years": [year.as_dict() for year in self.years],
            "total_without_adjustment": self.total_without_adjustment.as_dict() if self.total_without_adjustment is not None else None,
        }


def summarize(
    entries: list[EntryInput],
    *,
    as_of: date,
    contract_end: Optional[date],
    adjustment: PriceAdjustment = PriceAdjustment(),
    contract_start: Optional[date] = None,
    with_years: bool = False,
) -> list[FinanceSummary]:
    """Eine Zusammenfassung je Waehrung (keine Umrechnung).

    `with_years`: zusaetzlich Ausgaben je Vertragsjahr (ab `contract_start`, sonst ab dem ersten
    Ausgaben-Eintrag) und die Gesamtlaufzeit ohne Preisanpassung – nur bei bekanntem Vertragsende.
    """
    by_currency: dict[str, list[EntryInput]] = {}
    for entry in entries:
        by_currency.setdefault(entry.currency or "EUR", []).append(entry)
    as_of_month = month_index(as_of)
    year_first, year_last = as_of.year * 12, as_of.year * 12 + 11
    end_month = month_index(contract_end) if contract_end else None
    results = []
    for currency in sorted(by_currency):
        group = by_currency[currency]
        open_recurring = any(e.valid_to is None and e.interval != "once" for e in group)
        term_known = end_month is not None or not open_recurring
        if end_month is not None:
            horizon = end_month
        else:
            horizon = max([year_last, as_of_month] + [month_index(e.valid_to) for e in group if e.valid_to])
        notes: list[str] = []
        targets: list[Optional[dict]] = []
        if not term_known:
            notes.append("Kein Vertragsende bekannt: Beträge bis Vertragsende und für die Gesamtlaufzeit sind nicht berechenbar.")
            targets.append(TERM_TARGET)
        if adjustment.kind == "index":
            notes.append("Preisanpassung nach Index: künftige Beträge können nicht vorausberechnet werden.")
            targets.append(None)
        elif adjustment.kind == "negotiation":
            notes.append("Preisanpassung nach Verhandlung: künftige Beträge können nicht vorausberechnet werden.")
            targets.append(None)
        summaries = {"expense": DirectionSummary(), "income": DirectionSummary()}
        projected = False
        for entry in group:
            target = summaries.get(entry.direction)
            if target is None:
                continue
            for index, (net, gross) in monthly_values(entry, month_index(entry.valid_from), horizon, adjustment).items():
                if year_first <= index <= year_last:
                    target.current_year.add(net, gross)
                if index <= as_of_month:
                    target.to_date.add(net, gross)
                else:
                    target.remaining_to_end.add(net, gross)
                    if entry.interval != "once" and adjustment_factor(adjustment, _month_start(index)) != 1:
                        projected = True
                target.total_term.add(net, gross)
            current = monthly_values(entry, as_of_month, as_of_month, adjustment).get(as_of_month)
            if current is not None and entry.interval != "once":
                target.annual_run_rate.add(current[0] * 12, current[1] * 12)
        if not term_known:
            for summary in summaries.values():
                summary.remaining_to_end = None
                summary.total_term = None
        if projected:
            notes.append("Künftige Beträge enthalten die vereinbarte prozentuale Preisanpassung (Projektion).")
            targets.append(None)
        years: list[ContractYear] = []
        without: Optional[Bucket] = None
        expenses = [e for e in group if e.direction == "expense"]
        if with_years and contract_end is not None and expenses:
            start = contract_start or min(e.valid_from for e in expenses)
            years = contract_years(group, start=start, end=contract_end, adjustment=adjustment)
            without = Bucket()
            for entry in expenses:
                for _index, (net, gross) in monthly_values(entry, month_index(entry.valid_from), end_month, PriceAdjustment()).items():
                    without.add(net, gross)
        results.append(FinanceSummary(
            years=years,
            total_without_adjustment=without,
            period_mismatch=period_mismatch(group, contract_end),
            currency=currency,
            expense=summaries["expense"],
            income=summaries["income"],
            contract_end=contract_end,
            projected_adjustment=projected,
            notes=notes,
            note_targets=targets,
        ))
    return results


def period_mismatch(entries: list[EntryInput], contract_end: Optional[date]) -> Optional[dict]:
    """Vergleicht das Ende der laufenden Ausgaben mit dem Vertragsende (nur wenn beide bekannt sind).

    Offene Eintraege (ohne Ende) laufen bis zum Vertragsende und loesen nichts aus; Einmalbetraege zaehlen nicht.
    """
    recurring = [e for e in entries if e.direction == "expense" and e.interval != "once"]
    if contract_end is None or not recurring or any(e.valid_to is None for e in recurring):
        return None
    last_end = max(e.valid_to for e in recurring if e.valid_to is not None)
    if last_end == contract_end:
        return None
    return {
        "last_entry_end": last_end.isoformat(),
        "contract_end": contract_end.isoformat(),
        "kind": "after_end" if last_end > contract_end else "before_end",
    }


def allocate(amount: Decimal, shares: list[tuple[str, Decimal]]) -> list[tuple[str, Decimal]]:
    """Verteilt einen Betrag nach Prozentanteilen; Rundungsrest auf den groessten Anteil."""
    if not shares:
        return []
    parts = [(key, (amount * share / Decimal("100")).quantize(CENT, ROUND_HALF_UP)) for key, share in shares]
    remainder = amount.quantize(CENT, ROUND_HALF_UP) - sum(value for _, value in parts)
    if remainder:
        largest = max(range(len(shares)), key=lambda index: shares[index][1])
        key, value = parts[largest]
        parts[largest] = (key, value + remainder)
    return parts
