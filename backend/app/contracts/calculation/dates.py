"""Deterministische Date Engine (STEP 9) – nach Korrektheits-Härtung.

Pure Funktionen: (contract, as_of_date) → berechnete Datumsfelder.
Keine DB, kein HTTP, kein AI, keine versteckte aktuelle Zeit – aller
Zeitbezug laeuft ueber das explizite `as_of_date`.

Wichtige Härtungs-Prinzipien (siehe STEP_9_CHECKPOINT.md §„STEP-9-Härtung"):

A) Kündigungs-Relation – KEINE Default-Annahme
   Eine definitive Kündigungsfrist wird NUR berechnet, wenn die Relation der
   Frist zu einer Grenze POSITIV durch strukturierte extrahierte Daten belegt
   ist (cancellation_to_contract_end == to_contract_end wurde explizit
   gesetzt). Fehlende Relation, explizit „andere" Relation oder freie
   Formulierung erzeugen KEINE definitive Frist (NOT_CALCULABLE /
   REVIEW_REQUIRED). Keyword-Absenz ist KEIN Beweis.

B) Wiederholte automatische Verlängerungen
   Ermittelt die aktuell relevante Vertragsperiode relativ zu `as_of_date`
   (arithmetisch, begrenzt, kalenderbewusst).

   BOUNDARY-KONVENTION (durchgängig, für alle Datumsableitungen):
   Eine Vertragsgrenze `B` beendet eine Periode „inklusive"; `as_of_date == B`
   gehört zur ENDENDEN Periode (die nächste Periode beginnt am Folgetag B+1).
   - aktuelle/ relevante Periode: jene Periode p mit start_p < as_of <= end_p.
   - next_renewal_date = schliessende Grenze der aktuellen Periode (kann auf
     einer Grenze == as_of liegen).
   - Kündigungsgrenze: schliessende Grenze der (ggf. vorgeschobenen) aktuellen
     Periode.
   - days_until_x = countdown bis zur jeweiligen Grenze (negativ = vergangen),
     Grenze selbst zählt als erreicht (0).

   Diese Konvention wird deshalb überall gleich angewendet und NICHT je nach
   Kontext permutiert.

C) Konflikt-Propagation – keine falsche Sicherheit
   Ein CONFLICT/REVIEW_REQUIRED des Enddatums wird an abhängige Ergebnisse
   (Verlängerung, Kündigung) weitergetragen: sie bleiben mit Wert sichtbar,
   aber tragen Status REVIEW_REQUIRED + review_required=True. Der explizite
   Endwert wird NICHT verworfen, der Konflikt aber auch nicht gelöscht.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from app.contracts.calculation.calendar_ import add_duration, subtract_duration
from app.contracts.calculation.models import (
    CalcDuration,
    ContractStatusDerivation,
    DifferenceResult,
    CalculationStatus,
    DateCalculationKind,
    DateTimeResult,
    RenewalBoundary,
)
from app.models.contract import Contract
from app.models.enums import ContractStatus, TimeUnit
from app.models.values import Duration, FlexibleDate

# Obergrenze für die (bounded) relative Suche der aktuellen Verlängerungsperiode.
# Verhindert Endlosschleifen/riesige Iterationen bei malformed Daten. In der
# Praxis erreichen reale Verträge die relevante Periode nach wenigen Schritten.
MAX_SCAN_PERIODS = 1200

# Positive strukturierte Evidenz für Relation „zum Vertragsende".
_POSITIVE_TO_END_KEYS = frozenset(
    {"1", "true", "yes", "ja", "to_contract_end", "zum_vertragsende", "contract_end"}
)
_NEGATIVE_RELATION_KEYS = frozenset({"0", "false", "no", "nein"})


# ------------------------------------------------------------- Dauer -> CalcDuration


def _to_calc_duration(d: Optional[Duration]) -> Optional[CalcDuration]:
    """Wandelt eine extrahierte Duration in eine kanonische CalcDuration um.

    None, wenn value/unit fehlen oder die Einheit nicht unterstützt ist.
    Nicht-positive Werte werden abgelehnt (kein 0-Tage-Verlängerungsloop).
    """
    if d is None or d.value is None or d.unit is None:
        return None
    try:
        value = int(d.value)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    unit = d.unit
    if unit == TimeUnit.DAYS:
        return CalcDuration(days=value)
    if unit == TimeUnit.WEEKS:
        return CalcDuration(weeks=value)
    if unit == TimeUnit.MONTHS:
        return CalcDuration(months=value)
    if unit == TimeUnit.YEARS:
        return CalcDuration(years=value)
    return None


def _flexible_date_to_date(fd: Optional[FlexibleDate]) -> Optional[date]:
    """Nur ein EXPLIZITES Datum liefern; bei ereignisbasiert/unbekannt None."""
    if fd is None or fd.date is None:
        return None
    return fd.date


def _is_event_based(fd: Optional[FlexibleDate]) -> bool:
    return fd is not None and fd.date is None


# ------------------------------------------------------------- Enddatum


def calculate_contract_end_date(contract: Contract) -> DateTimeResult:
    """Berechnet das Vertragsende (nur bei deterministischer Grundlage).

    A) expliziter end_date → EXPLICIT (autoritativ).
    B) start_date + duration → DERIVED (kalenderbewusst).
    C) start ereignisbasiert ohne Termin → NOT_CALCULABLE (event_based).
    D) expliziter end vs. abgeleitet → Konflikt-Check -> CONFLICT/Review.
    """
    dates = contract.dates
    explicit_end = _flexible_date_to_date(dates.end_date)
    start = _flexible_date_to_date(dates.start_date)
    duration = _to_calc_duration(dates.duration)

    derived = None
    if start is not None and duration is not None:
        derived = add_duration(start, duration)

    if explicit_end is None:
        if derived is not None:
            return DateTimeResult(
                value=derived,
                status=CalculationStatus.CALCULATED,
                kind=DateCalculationKind.DERIVED_START_PLUS_DURATION,
                explanation=(
                    f"Kein explizites Ende; aus start_date={start} und duration="
                    f"{_duration_str(dates.duration)} kalenderbewusst abgeleitet."
                ),
                inputs={
                    "start_date": str(start),
                    "duration": _duration_str(dates.duration),
                },
            )
        if _is_event_based(dates.start_date):
            return DateTimeResult(
                value=None,
                status=CalculationStatus.NOT_CALCULABLE,
                explanation=(
                    "Start ist ereignisbasiert ('%s') ohne aufgeloesten Termin; "
                    "kein deterministisches Ende." % (dates.start_date.condition or "")
                ),
                inputs={"start_condition": dates.start_date.condition or ""},
                review_required=True,
            )
        if start is None:
            return DateTimeResult(
                value=None,
                status=CalculationStatus.NOT_CALCULABLE,
                explanation="Weder explizites Ende noch (start_date+duration) vorhanden.",
                inputs={},
            )
        return DateTimeResult(
            value=None,
            status=CalculationStatus.NOT_CALCULABLE,
            explanation="Start vorhanden, aber keine Laufzeit-Dauer extrahiert.",
            inputs={"start_date": str(start)},
        )

    # Explizites Ende vorhanden
    if derived is not None and derived != explicit_end:
        # Inklusive Vertragslaufzeit (UAT Re-Test Defect 1): Eine kalenderbasierte
        # Laufzeit (Jahre/Monate, ohne Wochen-/Tage-Komponente) umfasst laut
        # deutscher Vertragskonvention den letzten Tag VOR dem abgeleiteten
        # Jahrestag: „beginnt am 01.04.2025, Laufzeit 4 Jahre" endet am
        # 31.03.2029 (= 01.04.2029 minus 1 Tag). Ein explizites Ende genau auf
        # diesem inklusiven letzten Laufzeittag ist KEIN Konflikt, sondern
        # Korroboration – es erzeugt weder Warning noch Review-Flag.
        inclusive_end = (
            derived - timedelta(days=1)
            if (
                duration is not None
                and duration.weeks == 0
                and duration.days == 0
            )
            else None
        )
        if inclusive_end is not None and explicit_end == inclusive_end:
            return DateTimeResult(
                value=explicit_end,  # explizit bleibt autoritativ
                status=CalculationStatus.EXPLICIT,
                kind=DateCalculationKind.EXPLICIT,
                explanation=(
                    "Explizites Ende stimmt mit der kalenderbasierten inklusiven "
                    "Laufzeit ueberein: start+duration ergibt den Jahrestag "
                    f"{derived}; der inklusive letzte Laufzeittag ist {inclusive_end}. "
                    "Kein Konflikt; expliziter Wert massgeblich."
                ),
                inputs={
                    "end_date": str(explicit_end),
                    "derived_end_date": str(derived),
                    "inclusive_end_date": str(inclusive_end),
                    "start_date": str(start) if start else "-",
                    "duration": _duration_str(dates.duration),
                },
            )
        return DateTimeResult(
            value=explicit_end,  # explizit bleibt autoritativ, aber als Konflikt markiert
            status=CalculationStatus.CONFLICT,
            kind=DateCalculationKind.EXPLICIT,
            explanation=(
                "Explizites Ende und aus start_date+duration abgeleitetes Ende "
                "weichen ab (%s vs. %s). Explizit als Basis markiert; "
                "Differenz verlangt Pruefung." % (explicit_end, derived)
            ),
            inputs={
                "end_date": str(explicit_end),
                "derived_end_date": str(derived),
                "start_date": str(start) if start else "-",
                "duration": _duration_str(dates.duration),
            },
            review_required=True,
        )
    if derived is not None:
        return DateTimeResult(
            value=explicit_end,
            status=CalculationStatus.EXPLICIT,
            kind=DateCalculationKind.EXPLICIT,
            explanation=(
                "Explizites Ende; aus start+duration abgeleitetes Ende stimmt "
                "ueberein (Korroboration)."
            ),
            inputs={"end_date": str(explicit_end), "duration": _duration_str(dates.duration)},
        )
    return DateTimeResult(
        value=explicit_end,
        status=CalculationStatus.EXPLICIT,
        kind=DateCalculationKind.EXPLICIT,
        explanation="Explizites Vertragsende aus der Extraktion.",
        inputs={"end_date": str(explicit_end)},
    )


# ------------------------------------------------------------- Kündigungs-Relation (A)


def group_cancellation_relation(contract: Contract) -> str:
    """Klassifiziert die Relation der Kundigungsfrist zur Grenze, STRENG.

    Returns eine der Konstanten:
      "to_contract_end"   -> positive strukturierte Evidenz, Berechnung erlaubt
      "other"             -> explizit andere Relation -> nicht berechenbar (STEP 9)
      "missing"           -> keine Relation -> keine definitive Frist
      "ambiguous"         -> freie Formulierung/unbekannter Wert -> REVIEW_REQUIRED

    Absenz eines konkurrierenden Keywords ist KEIN Beweis für „zum Vertragsende".
    Nur ein explizit gesetzter {cancellation_to_contract_end} mit einem
    to-contract-end-Wert zählt als positive Evidenz.
    """
    t = contract.termination
    marker = t.cancellation_to_contract_end
    if marker is not None:
        s = str(marker).strip().lower()
        if s in _POSITIVE_TO_END_KEYS:
            return "to_contract_end"
        if s in _NEGATIVE_RELATION_KEYS:
            return "other"
        # erkannter, aber nicht unterstützter Marker-Wert -> mehrdeutig
        return "ambiguous"
    # marker nicht gesetzt
    if t.cancellation_condition and str(t.cancellation_condition).strip():
        return "ambiguous"  # freie Formulierung -> REVIEW_REQUIRED
    return "missing"


def _is_to_contract_end(contract: Contract) -> bool:
    return group_cancellation_relation(contract) == "to_contract_end"


# ------------------------------------------------------------- Auto-Verlängerung (B)


def _renewal_duration(contract: Contract) -> Optional[CalcDuration]:
    return _to_calc_duration(contract.termination.renewal_period)


def _locate_current_period(
    initial_end: date,
    renew: CalcDuration,
    as_of_date: date,
) -> Optional[tuple[int, Optional[date], date, date]]:
    """Ermittelt die relevante Periode relativ zu `as_of_date`.

    Returns (period_index, cur_start, cur_end, next_end) oder None,
    wenn die Obergrenze (MAX_SCAN_PERIODS) überschritten wird (= unberechenbar).

    Konvention: Eine Grenze endet eine Periode; as_of_date == Grenze gehört zur
    ENDENDEN Periode (nächste beginnt am Folgetag).
    - period_index 0 = initiale Laufzeit (Ende = initial_end).
    - period_index k>=1 = k-te automatische Verlängerung.
    """
    if as_of_date <= initial_end:
        next_end = add_duration(initial_end, renew)
        return (0, None, initial_end, next_end)  # cur_start aus contract.start_date
    prev_end = initial_end
    k = 1
    while k <= MAX_SCAN_PERIODS:
        cur_end = add_duration(prev_end, renew)
        next_end = add_duration(cur_end, renew)
        cur_start = add_duration(prev_end, CalcDuration(days=1))
        if as_of_date <= cur_end:
            return (k, cur_start, cur_end, next_end)
        prev_end = cur_end
        k += 1
    return None


def _boundary(
    period_index: int,
    start_date: Optional[date],
    end_date: date,
    *,
    is_initial: bool,
    review: bool,
) -> RenewalBoundary:
    return RenewalBoundary(
        period_index=period_index,
        start_date=start_date if start_date is not None else end_date,
        end_date=end_date,
        kind=(
            DateCalculationKind.DERIVED_START_PLUS_DURATION
            if is_initial
            else DateCalculationKind.RENEWAL_SHIFT
        ),
        explanation=(
            "Initiale Laufzeit (start bis Ende)."
            if is_initial
            else f"{period_index}. automatische Verlaengerung (kalenderbewusst)."
        ),
        review_required=review,
    )


def calculate_renewal_info(
    contract: Contract,
    initial_end: Optional[date],
    as_of_date: date,
    *,
    boundary_conflicted: bool,
) -> tuple[list[RenewalBoundary], DateTimeResult]:
    """Berechnet die aktuell/als Nächstes relevante Verlängerungsperiode.

    Returns (bounded_boundaries, next_renewal_result).
    - bounded_boundaries: nur die aktuell relevante + die nächste Periode
      (keine unbegrenzte Historien-Erzeugung).
    - next_renewal_result: die nächste anstehende Verlängerungsgrenze.
    """
    t = contract.termination
    if not t.automatic_renewal:
        return [], DateTimeResult(
            value=None,
            status=CalculationStatus.NOT_CALCULABLE,
            explanation="Keine automatische Verlaengerung.",
            inputs={"automatic_renewal": str(t.automatic_renewal)},
        )
    renew = _renewal_duration(contract)
    if renew is None:
        return [], DateTimeResult(
            value=None,
            status=CalculationStatus.NOT_CALCULABLE,
            explanation="Automatische Verlaengerung, aber kein renewal_period extrahiert.",
            inputs={},
            review_required=True,
        )
    if initial_end is None:
        return [], DateTimeResult(
            value=None,
            status=CalculationStatus.NOT_CALCULABLE,
            explanation="Automatische Verlaengerung, aber keine Grenze (Ende) bekannt.",
            inputs={},
        )

    loc = _locate_current_period(initial_end, renew, as_of_date)
    if loc is None:
        return [], DateTimeResult(
            value=None,
            status=CalculationStatus.NOT_CALCULABLE,
            explanation=(
                "Automatische Verlaengerung: relevante Periode nicht innerhalb der "
                "begrenzten Suche (MAX_SCAN_PERIODS); keine unbegrenzte Berechnung."
            ),
            inputs={},
            review_required=True,
        )

    k, cur_start, cur_end, next_end = loc
    start0 = _flexible_date_to_date(contract.dates.start_date)
    boundaries: list[RenewalBoundary] = []

    if k == 0:
        # aktuelle Periode = initiale Laufzeit
        boundaries.append(
            _boundary(0, start0, initial_end, is_initial=True, review=boundary_conflicted)
        )
        boundaries.append(
            _boundary(
                1,
                add_duration(initial_end, CalcDuration(days=1)),
                next_end,
                is_initial=False,
                review=boundary_conflicted,
            )
        )
        next_renewal_value = next_end
        next_explanation = (
            f"Naechste Verlaengerungsgrenze: {initial_end} + "
            f"{_duration_str(t.renewal_period)}."
        )
    else:
        boundaries.append(
            _boundary(k, cur_start, cur_end, is_initial=False, review=boundary_conflicted)
        )
        boundaries.append(
            _boundary(
                k + 1,
                add_duration(cur_end, CalcDuration(days=1)),
                next_end,
                is_initial=False,
                review=boundary_conflicted,
            )
        )
        next_renewal_value = cur_end
        next_explanation = (
            f"Anstehende Verlaengerungsgrenze der aktuell relevanten Periode {k}: "
            f"{cur_end}."
        )

    status = (
        CalculationStatus.REVIEW_REQUIRED
        if boundary_conflicted
        else CalculationStatus.CALCULATED
    )
    return boundaries, DateTimeResult(
        value=next_renewal_value,
        status=status,
        kind=DateCalculationKind.RENEWAL_SHIFT,
        explanation=next_explanation,
        inputs={
            "initial_end": str(initial_end),
            "renewal_period": _duration_str(t.renewal_period),
            "automatic_renewal": "true",
            "as_of_date": str(as_of_date),
        },
        review_required=boundary_conflicted,
    )


# ------------------------------------------------------------- Kündigungsfrist (A + C)


def calculate_latest_cancellation_date(
    contract: Contract,
    initial_end: Optional[date],
    as_of_date: date,
    *,
    boundary_conflicted: bool,
) -> DateTimeResult:
    """Berechnet den spätesten Kündigungstermin – nur bei positiver Evidenz.

    Voraussetzungen:
    1. Relation ist positiv „zum Vertragsende" (group_cancellation_relation).
    2. Frist (cancellation_period) vorhanden.
    3. Grenze vorhanden.

    Bei automatischer Verlängerung wird die für die aktuell relevante Periode
    gültige Grenze verwendet; ist deren Frist bereits abgelaufen (> as_of),
    wird auf die nächste Verlängerungsgrenze vorgeschoben (bounded).

    Bei einem Konflikt/Review des Enddatums (boundary_conflicted) trägt das
    Ergebnis Status REVIEW_REQUIRED (Wert bleibt sichtbar, keine falsche
    Gewissheit).
    """
    t = contract.termination
    period = _to_calc_duration(t.cancellation_period)
    relation = group_cancellation_relation(contract)

    if relation == "ambiguous":
        return DateTimeResult(
            value=None,
            status=CalculationStatus.REVIEW_REQUIRED,
            explanation=(
                "Kundigungsfrist-Voraussetzung ist Freitext/eine nicht unterstuetzte "
                "Relation ('%s'); keine definitive Frist berechnet."
                % (t.cancellation_condition or t.cancellation_to_contract_end or "")
            ),
            inputs={"cancellation_condition": t.cancellation_condition or ""},
            review_required=True,
        )
    if relation in ("other", "missing"):
        what = (
            "Relation ist explizit eine andere als zum Vertragsende"
            if relation == "other"
            else "keine Relation vom Kündigungstermin zum Vertragsende extrahiert"
        )
        return DateTimeResult(
            value=None,
            status=CalculationStatus.NOT_CALCULABLE,
            explanation=(
                "Kundigungsfrist-Attribut vorhanden, aber " + what + ". Keine "
                "definitive Frist (STEP 9)."
            ),
            inputs={"cancellation_to_contract_end": str(t.cancellation_to_contract_end)},
            review_required=bool(t.cancellation_condition),
        )
    # relation == "to_contract_end"
    if period is None:
        return DateTimeResult(
            value=None,
            status=CalculationStatus.NOT_CALCULABLE,
            explanation="Kundigungsfrist (cancellation_period) unbekannt.",
            inputs={},
            review_required=bool(t.cancellation_condition),
        )
    if initial_end is None:
        return DateTimeResult(
            value=None,
            status=CalculationStatus.NOT_CALCULABLE,
            explanation="Kundigungsfrist, aber keine zuverlaessige Grenze (Ende) bekannt.",
            inputs={},
            review_required=True,
        )

    boundary = initial_end
    # Bei Verlängerung: relevante Grenze = aktuelle Periode; Frist abgelaufen ->
    # auf nächste Verlängerungsgrenze vorschieben (bounded).
    renew = _renewal_duration(contract)
    if t.automatic_renewal and renew is not None:
        guard = 0
        while subtract_duration(boundary, period) < as_of_date and guard < MAX_SCAN_PERIODS:
            boundary = add_duration(boundary, renew)
            guard += 1

    deadline = subtract_duration(boundary, period)
    status = (
        CalculationStatus.REVIEW_REQUIRED
        if boundary_conflicted
        else CalculationStatus.CALCULATED
    )
    return DateTimeResult(
        value=deadline,
        status=status,
        kind=DateCalculationKind.CALENDAR_SUBTRACTION,
        explanation=(
            f"Spätester Kundigungstermin = relevante Grenze {boundary} minus Frist "
            f"{_duration_str(t.cancellation_period)} (kalenderbewusst)."
            + (" [Grenze aus konflikthaftem Enddatum – Pruefung erforderlich]" if boundary_conflicted else "")
        ),
        inputs={
            "boundary_date": str(boundary),
            "cancellation_period": _duration_str(t.cancellation_period),
        },
        review_required=boundary_conflicted,
    )


def compute_days_until(
    as_of_date: date,
    target_date: Optional[date],
    what: str,
    *,
    target_status: CalculationStatus = CalculationStatus.NOT_CALCULABLE,
    review_required: bool = False,
) -> DifferenceResult:
    """Tage bis zum Ziel relativ zu `as_of_date` (negativ = bereits vergangen)."""
    if target_date is None:
        return DifferenceResult(
            value=None,
            status=target_status,
            target_date=None,
            as_of_date=as_of_date,
            explanation=f"{what}: Ziel nicht berechenbar.",
            inputs={},
            review_required=review_required,
        )
    days = (target_date - as_of_date).days
    return DifferenceResult(
        value=days,
        status=target_status if target_status != CalculationStatus.NOT_CALCULABLE else CalculationStatus.CALCULATED,
        target_date=target_date,
        as_of_date=as_of_date,
        explanation=f"{what}: {days} Tage ab {as_of_date} (negativ = vergangen).",
        inputs={"as_of_date": str(as_of_date), "target": str(target_date)},
        review_required=review_required,
    )


def derive_contract_status(
    contract: Contract,
    end_date_result: DateTimeResult,
    as_of_date: date,
) -> ContractStatusDerivation:
    """Objektiver Vertragsstatus (ACTIVE / EXPIRED / UNKNOWN / TERMINATED).

    TERMINATED wird NUR gemeldet, wenn der Vertrag explizit als terminated
    markiert ist (structured field Contract.status). Es wird NIEMALS allein aus
    einem abgelaufenen Enddatum auf TERMINATED geschlossen (-> EXPIRED).
    Kein separates Terminierungs-Evidence-Feld im Schema; konservativ.
    """
    if contract.status == ContractStatus.TERMINATED:
        return ContractStatusDerivation(
            status=ContractStatus.TERMINATED,
            used_as_of_date=as_of_date,
            explanation="Vertrag ist explizit als beendet (terminated) markiert.",
            inputs={"contract.status": "terminated"},
        )

    end = end_date_result.value
    if end is None:
        what = ""
        if end_date_result.status == CalculationStatus.CONFLICT:
            what = " (Ende: Konflikt erfordert Pruefung)"
        return ContractStatusDerivation(
            status=ContractStatus.UNKNOWN,
            used_as_of_date=as_of_date,
            explanation=f"Kein deterministisches Ende{what}. Status unbekannt.",
            inputs={},
        )
    if as_of_date < end:
        return ContractStatusDerivation(
            status=ContractStatus.ACTIVE,
            used_as_of_date=as_of_date,
            explanation=f"as_of_date {as_of_date} liegt vor dem Ende {end}.",
            inputs={"as_of_date": str(as_of_date), "end_date": str(end)},
        )
    return ContractStatusDerivation(
        status=ContractStatus.EXPIRED,
        used_as_of_date=as_of_date,
        explanation=f"as_of_date {as_of_date} liegt nach dem Ende {end}.",
        inputs={"as_of_date": str(as_of_date), "end_date": str(end)},
    )


# ------------------------------------------------------------- Helfer


def _duration_str(d: Optional[Duration]) -> str:
    if d is None:
        return "-"
    return f"{d.value or '?'} {d.unit.value if d.unit else '?'}"


def calculate_contract_dates(contract: Contract, as_of_date: date) -> "CalculatedDateField":
    """Orchestriert die Datumsfelder eines Vertrags (pure Funktion)."""
    from app.contracts.calculation.models import CalculatedDateField

    end_result = calculate_contract_end_date(contract)
    boundary_conflicted = end_result.status in (
        CalculationStatus.CONFLICT,
        CalculationStatus.REVIEW_REQUIRED,
    )
    boundary = end_result.value

    # Verlängerung / nächste relevante Periode
    boundaries, next_renewal = calculate_renewal_info(
        contract,
        boundary,
        as_of_date,
        boundary_conflicted=boundary_conflicted,
    )

    # Kündigung: relevante Grenze (aktuelle Periode, bei Verlängerung
    # ggf. vorgeschoben) – mit Konflikt-Propagation.
    cancellation_result = calculate_latest_cancellation_date(
        contract,
        boundary,
        as_of_date,
        boundary_conflicted=boundary_conflicted,
    )

    days_end_status = (
        end_result.status
        if boundary_conflicted
        else CalculationStatus.CALCULATED
    )
    days_end = compute_days_until(
        as_of_date,
        end_result.value,
        "days_until_end",
        target_status=days_end_status,
        review_required=boundary_conflicted,
    )
    days_cancel = compute_days_until(
        as_of_date,
        cancellation_result.value,
        "days_until_latest_cancellation",
        target_status=cancellation_result.status,
        review_required=cancellation_result.review_required,
    )

    status = derive_contract_status(contract, end_result, as_of_date)

    return CalculatedDateField(
        calculated_end_date=end_result,
        latest_cancellation_date=cancellation_result,
        next_renewal_date=next_renewal,
        days_until_end=days_end,
        days_until_latest_cancellation=days_cancel,
        current_contract_status=status,
        renewal_boundaries=boundaries,
    )
