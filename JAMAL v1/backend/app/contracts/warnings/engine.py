"""Reine Warn-Engine (STEP 11) – deterministische BewertungSchicht A.

`evaluate_contract_warnings(contract, calculation, policy)` ist eine PURE
Funktion: keine DB, kein Netz, keine KI, kein verstecktes datetime.now()/
date.today(). Gleiche Eingaben + gleiche Policy => identisches Ergebnis.

Konsumiert Ausschliesslich STEP-9-`ContractCalculationResult`-Felder
(calculate_termine wird NICHT neu berechnet, nur ausgewertet).
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Optional

from app.contracts.calculation.models import (
    CalculationStatus,
    ContractCalculationResult,
)
from app.contracts.warnings.models import (
    ContractWarning,
    ContractWarningResult,
    TargetKind,
    WarningSeverity,
    WarningType,
    default_field_refs,
)
from app.contracts.warnings.policy import (
    WarningPolicy,
    severity_for_days,
)
from app.models.contract import Contract
from app.models.enums import ContractStatus

# Konflikt-/Review-Status, die KEINE defzfinitiven Termine liefern duerfen.
_NON_DEFINITIVE = {
    CalculationStatus.NOT_CALCULABLE,
    CalculationStatus.REVIEW_REQUIRED,
    CalculationStatus.CONFLICT,
}


def _fingerprint(*parts: object) -> str:
    """Deterministischer SHA-256-Fingerprint stabiler, semantischer Teile.

    Enthaelt NIE kuratierten UI-Text und NIE den Schweregrad/Bucket – so bleibt
    die Identitaet eines logischen Problems stabil, wenn sich nur die
    Dringlichkeit (z. B. 30-Tage -> 14-Tage) aendert.
    """
    joined = "|".join(
        p if isinstance(p, str) else (p.isoformat() if isinstance(p, date) else str(p))
        for p in parts
    )
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _mk(
    *,
    warning_type: WarningType,
    severity: WarningSeverity,
    target_kind: TargetKind,
    as_of_date: date,
    policy: WarningPolicy,
    target_date: Optional[date] = None,
    days_remaining: Optional[int] = None,
    matched_threshold_days: Optional[int] = None,
    title_de: str,
    message_de: str,
    action_hint_de: str,
    requires_action: bool = False,
    requires_review: bool = False,
    identity: tuple[object, ...],
    calc_ref: str = "",
    source_ref: str = "",
) -> ContractWarning:
    calc_refs, source_refs = default_field_refs(warning_type)
    if calc_ref:
        calc_refs = [calc_ref]
    if source_ref:
        source_refs = [source_ref]
    fp = _fingerprint(identity[0], warning_type.value, target_kind.value, *identity[1:])
    return ContractWarning(
        warning_type=warning_type,
        severity=severity,
        target_kind=target_kind,
        target_date=target_date,
        days_remaining=days_remaining,
        matched_threshold_days=matched_threshold_days,
        as_of_date=as_of_date,
        policy_version=policy.version,
        title_de=title_de,
        message_de=message_de,
        action_hint_de=action_hint_de,
        requires_action=requires_action,
        requires_review=requires_review,
        calculation_field_refs=calc_refs,
        source_field_refs=source_refs,
        logical_fingerprint=fp,
    )


def _is_terminated(contract: Contract) -> bool:
    """Explizier TERMINATED-Status (einzige privilegierte Quelle, Invariante)."""
    return contract.status == ContractStatus.TERMINATED


def evaluate_contract_warnings(
    contract: Contract,
    calculation: ContractCalculationResult,
    policy: WarningPolicy | None = None,
) -> ContractWarningResult:
    """Bewertet alle Warnungen eines Vertrags (deterministisch, reine Funktion)."""
    policy = policy or WarningPolicy.default()
    as_of = calculation.as_of_date
    warnings: list[ContractWarning] = []
    identity_root = contract.identity.contract_number or contract.id
    dates = calculation.dates
    costs = calculation.costs

    terminated = _is_terminated(contract)

    # ------------------------------------------------------------------
    # Kündigung = PRIMÄRER HANDLUNGS-TERMIN (Kapitel 7)
    # ------------------------------------------------------------------
    cancel_days = dates.days_until_latest_cancellation
    cancel = dates.latest_cancellation_date
    if not terminated:
        if cancel_days.value is not None and cancel.status in (
            CalculationStatus.CALCULATED,
            CalculationStatus.EXPLICIT,
        ):
            days = cancel_days.value
            threshold = policy.match_threshold(days)
            if days > 0 and threshold is not None:
                severity = severity_for_days(days) or WarningSeverity.LOW
                warnings.append(
                    _mk(
                        warning_type=WarningType.CANCELLATION_DEADLINE_APPROACHING,
                        severity=severity,
                        target_kind=TargetKind.CANCELLATION_DEADLINE,
                        as_of_date=as_of,
                        policy=policy,
                        target_date=cancel.value,
                        days_remaining=days,
                        matched_threshold_days=threshold,
                        title_de=f"Kündigungsfrist in {days} Tagen",
                        message_de=(
                            f"Der späteste Kündigungstermin ist {cancel.value}. "
                            f"Noch {days} Kalendertage."
                        ),
                        action_hint_de="Prüfung der Kündigungsoptionen empfohlen.",
                        requires_action=True,
                        identity=(identity_root, cancel.value),
                        calc_ref="dates.latest_cancellation_date",
                        source_ref="termination.cancellation_period",
                    )
                )
            elif days == 0:
                warnings.append(
                    _mk(
                        warning_type=WarningType.CANCELLATION_DEADLINE_TODAY,
                        severity=WarningSeverity.CRITICAL,
                        target_kind=TargetKind.CANCELLATION_DEADLINE,
                        as_of_date=as_of,
                        policy=policy,
                        target_date=cancel.value,
                        days_remaining=0,
                        matched_threshold_days=0,
                        title_de="Kündigungsfrist heute",
                        message_de=f"Der späteste Kündigungstermin ist heute ({cancel.value}).",
                        action_hint_de="Heute entscheiden, falls gekündigt werden soll.",
                        requires_action=True,
                        identity=(identity_root, cancel.value),
                        calc_ref="dates.latest_cancellation_date",
                        source_ref="termination.cancellation_period",
                    )
                )
            elif days < 0:
                warnings.append(
                    _mk(
                        warning_type=WarningType.CANCELLATION_DEADLINE_PASSED,
                        severity=WarningSeverity.CRITICAL,
                        target_kind=TargetKind.CANCELLATION_DEADLINE,
                        as_of_date=as_of,
                        policy=policy,
                        target_date=cancel.value,
                        days_remaining=days,
                        matched_threshold_days=None,
                        title_de="Kündigungsfrist bereits verstrichen – Prüfung erforderlich",
                        message_de=(
                            f"Der Kündigungstermin {cancel.value} ist seit {abs(days)} "
                            "Tagen überschritten. Das bedeutet NICHT automatisch "
                            "gekündigt/terminiert/auto-verlängert."
                        ),
                        action_hint_de="Prüfung der vertraglichen Konsequenzen empfohlen.",
                        requires_action=True,
                        identity=(identity_root, cancel.value),
                        calc_ref="dates.latest_cancellation_date",
                        source_ref="termination.cancellation_period",
                    )
                )
        elif cancel.status in _NON_DEFINITIVE:
            # Keine erfundene Frist -> Review-/Konflikt-Warnung (siehe unten).
            if cancel.status == CalculationStatus.CONFLICT:
                warnings.append(
                    _mk(
                        warning_type=WarningType.CALCULATION_CONFLICT,
                        severity=WarningSeverity.HIGH,
                        target_kind=TargetKind.CANCELLATION_DEADLINE,
                        as_of_date=as_of,
                        policy=policy,
                        title_de="Kündigungstermin widersprüchlich",
                        message_de=(
                            "Der Kündigungstermin kann nicht zuverlässig bestimmt "
                            "werden (konkurrierende Angaben). Kein erfundenes Datum."
                        ),
                        action_hint_de="Manuelle Prüfung der Kündigungsregel erforderlich.",
                        requires_review=True,
                        identity=(identity_root, cancel.value, "conflict"),
                        calc_ref="dates.latest_cancellation_date",
                        source_ref="termination.cancellation_period",
                    )
                )
            elif cancel.review_required or cancel.status == CalculationStatus.REVIEW_REQUIRED:
                warnings.append(
                    _mk(
                        warning_type=WarningType.MANUAL_REVIEW_REQUIRED,
                        severity=WarningSeverity.MEDIUM,
                        target_kind=TargetKind.CANCELLATION_DEADLINE,
                        as_of_date=as_of,
                        policy=policy,
                        title_de="Kündigungsfrist nicht eindeutig – manuelle Prüfung erforderlich",
                        message_de=(
                            "Die Kündigungsregel ist unklar bzw. die Daten reichen "
                            "für einen definitiven Termin nicht aus."
                        ),
                        action_hint_de="Manuelle Prüfung der Kündigungsbedingungen empfohlen.",
                        requires_review=True,
                        identity=(identity_root, "cancellation", "review"),
                        calc_ref="dates.latest_cancellation_date",
                        source_ref="termination.cancellation_period",
                    )
                )

    # ------------------------------------------------------------------
    # Vertrags-Ende (Kapitel 8)
    # ------------------------------------------------------------------
    if not terminated:
        end_date = dates.calculated_end_date.value
        days_end = dates.days_until_end.value
        status_derived = dates.current_contract_status.status
        if status_derived == ContractStatus.EXPIRED:
            warnings.append(
                _mk(
                    warning_type=WarningType.CONTRACT_EXPIRED,
                    severity=WarningSeverity.HIGH,
                    target_kind=TargetKind.CONTRACT_END,
                    as_of_date=as_of,
                    policy=policy,
                    target_date=end_date,
                    days_remaining=days_end,
                    matched_threshold_days=None,
                    title_de="Vertrag ist ausgelaufen",
                    message_de=(
                        f"Das Vertragsende ({end_date}) liegt am/vor dem Stichtag "
                        f"{as_of}. Abgelaufenes Ende bedeutet keine Terminierung."
                    ),
                    action_hint_de="Prüfung der Weiterführung/Verlängerung empfohlen.",
                    requires_action=True,
                    identity=(identity_root, end_date, "expired"),
                    calc_ref="dates.calculated_end_date",
                    source_ref="dates.end_date",
                )
            )
        elif days_end is not None and end_date is not None:
            threshold = policy.match_threshold(days_end)
            if days_end > 0 and threshold is not None:
                severity = severity_for_days(days_end) or WarningSeverity.LOW
                warnings.append(
                    _mk(
                        warning_type=WarningType.CONTRACT_END_APPROACHING,
                        severity=severity,
                        target_kind=TargetKind.CONTRACT_END,
                        as_of_date=as_of,
                        policy=policy,
                        target_date=end_date,
                        days_remaining=days_end,
                        matched_threshold_days=threshold,
                        title_de=f"Vertragsende in {days_end} Tagen",
                        message_de=(
                            f"Das Vertragsende ist am {end_date} – noch {days_end} "
                            "Kalendertage."
                        ),
                        action_hint_de="Vorbereitung der Verlängerung/Nachfolge empfohlen.",
                        requires_action=True,
                        identity=(identity_root, end_date),
                        calc_ref="dates.calculated_end_date",
                        source_ref="dates.end_date",
                    )
                )

    # ------------------------------------------------------------------
    # Automatische Verlängerung (Kapitel 9)
    # ------------------------------------------------------------------
    if not terminated and contract.termination.automatic_renewal:
        renewal_date = dates.next_renewal_date.value
        renewal_status = dates.next_renewal_date.status
        # Nur wenn eine der anstehenden Grenzen als Handlungstermin relevant ist
        # ODER eine starke Kündigungs-Warnung vorliegt, das „Verlängerungs-Risiko"
        # zusätzlich zu kommunizieren (§19: nur mit Zusatz-Information).
        has_action_deadline = any(
            w.warning_type
            in (
                WarningType.CANCELLATION_DEADLINE_APPROACHING,
                WarningType.CANCELLATION_DEADLINE_TODAY,
                WarningType.CANCELLATION_DEADLINE_PASSED,
            )
            for w in warnings
        )
        renewal_actionable = (
            renewal_date is not None
            and renewal_status in (CalculationStatus.CALCULATED, CalculationStatus.EXPLICIT)
        )
        if has_action_deadline:
            warnings.append(
                _mk(
                    warning_type=WarningType.AUTOMATIC_RENEWAL_ATTENTION,
                    severity=WarningSeverity.MEDIUM,
                    target_kind=TargetKind.RENEWAL,
                    as_of_date=as_of,
                    policy=policy,
                    target_date=renewal_date,
                    days_remaining=(
                        (renewal_date - as_of).days if renewal_date is not None else None
                    ),
                    matched_threshold_days=(
                        policy.match_threshold((renewal_date - as_of).days)
                        if renewal_date is not None
                        else None
                    ),
                    title_de="Automatische Verlängerung – Kündigungsfrist prüfen",
                    message_de=(
                        "Ohne Kündigung verlängert sich der Vertrag automatisch "
                        + (
                            f"(nächste Grenze {renewal_date})."
                            if renewal_date is not None
                            else "(nächste Grenze unklar)."
                        )
                    ),
                    action_hint_de="Prüfung, ob trotz Fristüberschreitung noch gekündigt werden kann.",
                    requires_action=True,
                    identity=(identity_root, "auto_renewal"),
                    calc_ref="dates.next_renewal_date",
                    source_ref="termination.automatic_renewal",
                )
            )
        elif renewal_actionable:
            # Bekannte, anstehende Verlängerungsgrenze = zusätzlicher Handlungstermin.
            days_r = (renewal_date - as_of).days
            threshold = policy.match_threshold(days_r)
            warnings.append(
                _mk(
                    warning_type=WarningType.AUTOMATIC_RENEWAL_ATTENTION,
                    severity=WarningSeverity.MEDIUM,
                    target_kind=TargetKind.RENEWAL,
                    as_of_date=as_of,
                    policy=policy,
                    target_date=renewal_date,
                    days_remaining=days_r,
                    matched_threshold_days=threshold,
                    title_de="Automatische Verlängerung anstehend",
                    message_de=(
                        f"Der Vertrag verlängert sich automatisch zur Grenze "
                        f"{renewal_date}, sofern nicht gekündigt wird."
                    ),
                    action_hint_de="Kündigungsfenster vor der Verlängerung prüfen.",
                    requires_action=True,
                    identity=(identity_root, renewal_date),
                    calc_ref="dates.next_renewal_date",
                    source_ref="termination.automatic_renewal",
                )
            )
        elif renewal_status in _NON_DEFINITIVE and renewal_status != CalculationStatus.CALCULATED:
            # Auto-Verlängerung explizit, aber Termin unklar -> Review-orientiert.
            warnings.append(
                _mk(
                    warning_type=WarningType.MANUAL_REVIEW_REQUIRED,
                    severity=WarningSeverity.MEDIUM,
                    target_kind=TargetKind.RENEWAL,
                    as_of_date=as_of,
                    policy=policy,
                    title_de="Automatische Verlängerung – Daten unklar",
                    message_de=(
                        "Automatische Verlängerung ist explizit, aber die zugehörige "
                        "Grenze ist nicht zuverlässig bestimmbar."
                    ),
                    action_hint_de="Manuelle Prüfung der Verlängerungsbedingungen empfohlen.",
                    requires_review=True,
                    identity=(identity_root, "auto_renewal", "review"),
                    calc_ref="dates.next_renewal_date",
                    source_ref="termination.automatic_renewal",
                )
            )

    # ------------------------------------------------------------------
    # Unklare Daten / Konflikt / Review (Kapitel 10)
    # ------------------------------------------------------------------
    # Enddatum-Konflikt -> CALCULATION_CONFLICT (kritischer Datum-Konflikt).
    if dates.calculated_end_date.status == CalculationStatus.CONFLICT:
        warnings.append(
            _mk(
                warning_type=WarningType.CALCULATION_CONFLICT,
                severity=WarningSeverity.HIGH,
                target_kind=TargetKind.CONTRACT_END,
                as_of_date=as_of,
                policy=policy,
                target_date=dates.calculated_end_date.value,
                title_de="Vertragsdaten widersprüchlich (Endtermin)",
                message_de=(
                    "Das Vertragsende lässt sich nicht eindeutig bestimmen "
                    "(explizit vs. abgeleitet weichen ab)."
                ),
                action_hint_de="Manuelle Prüfung des Vertragsendes erforderlich.",
                requires_review=True,
                identity=(identity_root, "end", "conflict"),
                calc_ref="dates.calculated_end_date",
                source_ref="dates.end_date",
            )
        )

    # Allgemeine Unklarheit (Status UNKNOWN / overall review ohne konkrete Warnung).
    if dates.current_contract_status.status == ContractStatus.UNKNOWN:
        warnings.append(
            _mk(
                warning_type=WarningType.UNCLEAR_CONTRACT_DATA,
                severity=WarningSeverity.MEDIUM,
                target_kind=TargetKind.DATA_QUALITY,
                as_of_date=as_of,
                policy=policy,
                title_de="Vertragsdaten nicht eindeutig – manuelle Prüfung erforderlich",
                message_de=(
                    "Der Vertragsstatus ist nicht eindeutig bestimmbar (kein "
                    "deterministisches Ende / unklare Daten)."
                ),
                action_hint_de="Manuelle Prüfung der Vertragsdaten empfohlen.",
                requires_review=True,
                identity=(identity_root, "unknown_status"),
                calc_ref="dates.current_contract_status",
                source_ref="contract.dates",
            )
        )
    elif calculation.overall_review_required and warnings:
        # Nur, wenn noch KEINE konkrete Review-/Konflikt-Warnung erzeugt wurde:
        # konsolidierte Review-Warnung (Deduplikation äquivalenter Gründe).
        has_review_warning = any(
            w.warning_type
            in (
                WarningType.MANUAL_REVIEW_REQUIRED,
                WarningType.CALCULATION_CONFLICT,
                WarningType.UNCLEAR_CONTRACT_DATA,
            )
            for w in warnings
        )
        if not has_review_warning:
            warnings.append(
                _mk(
                    warning_type=WarningType.MANUAL_REVIEW_REQUIRED,
                    severity=WarningSeverity.INFO,
                    target_kind=TargetKind.DATA_QUALITY,
                    as_of_date=as_of,
                    policy=policy,
                    title_de="Manuelle Prüfung empfohlen",
                    message_de="; ".join(sorted(set(calculation.review_reasons))) or
                    "Einige Vertragsdaten benötigen eine Prüfung.",
                    action_hint_de="Manuelle Prüfung der betroffenen Daten empfohlen.",
                    requires_review=True,
                    identity=(identity_root, "overall_review"),
                    calc_ref="overall_review_required",
                    source_ref="contract.review",
                )
            )

    # ------------------------------------------------------------------
    # Kosten (Kapitel 11)
    # ------------------------------------------------------------------
    annual = costs.normalized_recurring.annual
    if costs.currency_conflict:
        warnings.append(
            _mk(
                warning_type=WarningType.CURRENCY_CONFLICT,
                severity=WarningSeverity.HIGH,
                target_kind=TargetKind.COST,
                as_of_date=as_of,
                policy=policy,
                title_de="Mehrere Währungen – keine verlässliche Aggregation",
                message_de=(
                    "Es liegen Beträge in mehreren Währungen vor; es wird kein "
                    "Währungsumtausch durchgeführt."
                ),
                action_hint_de="Manuelle Prüfung der Kosten in einheitlicher Währung erforderlich.",
                requires_review=True,
                identity=(identity_root, "currency_conflict"),
                calc_ref="costs.currency_conflict",
                source_ref="contract.costs",
            )
        )
    if costs.recurring_cost_conflict:
        warnings.append(
            _mk(
                warning_type=WarningType.COST_CONFLICT,
                severity=WarningSeverity.HIGH,
                target_kind=TargetKind.COST,
                as_of_date=as_of,
                policy=policy,
                title_de="Widersprüchliche Kostenangaben",
                message_de=(
                    "Monatliche und jährliche Kosten widersprechen sich; keine "
                    "verlässliche jährliche Kostenangabe."
                ),
                action_hint_de="Manuelle Prüfung der Kostenangaben erforderlich.",
                requires_review=True,
                identity=(identity_root, "cost_conflict"),
                calc_ref="costs.normalized_recurring.annual",
                source_ref="contract.costs",
            )
        )
    elif annual.status == CalculationStatus.NOT_CALCULABLE and annual.value is None:
        # Keine verlässliche jährliche Kostenangabe (kein „0"-Annehmen).
        warnings.append(
            _mk(
                warning_type=WarningType.MISSING_COST_DATA,
                severity=WarningSeverity.MEDIUM,
                target_kind=TargetKind.COST,
                as_of_date=as_of,
                policy=policy,
                title_de="Keine verlässliche jährliche Kostenangabe vorhanden",
                message_de=(
                    "Es gibt keine ausreichend verwertbare wiederkehrende/jährliche "
                    "Kostenangabe für die spätere Berichterstattung."
                ),
                action_hint_de="Kostenangabe ergänzen/prüfen empfohlen.",
                requires_review=True,
                identity=(identity_root, "missing_cost"),
                calc_ref="costs.normalized_recurring.annual",
                source_ref="contract.costs",
            )
        )

    result = ContractWarningResult(
        contract_id=calculation.contract_id,
        as_of_date=as_of,
        policy_version=policy.version,
        warnings=warnings,
    )
    return result.ordered()
