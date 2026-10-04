"""Dashboard-Lesedienst (STEP 12) – READ-ONLY, deterministisch, org-gebunden.

Aggregiert die aktuell akzeptierte Sicht:

  Vertrags-Projektion  (contract.status / risk_level – TERMINATED/EXPIRED/...)
  akzeptierte STEP-9-Berechnung (calculation_run.result_snapshot)
  akzeptierte Extraktion        (contract_extraction.contract_snapshot, fuer
                                 Totalvertragswert, da STEP 9 nur den Status traegt)
  aktive STEP-11-Warnungen      (contract_warning, active=True)

Regeln:
- Read-only. Diese Funktion fuehrt KEINE Schreiboperationen / Mutationen aus.
- Nur akzeptierte/aktuelle Lauefe; nie failed/rejected/superseded.
- KEINE KI. KEINE Berechnung von Terminen/Warnungen hier – Warn-Semantik kommt
  ausschliesslich von der materialisierten STEP-11-Projektion.
- Frische wird EXPLIZIT ausgewiesen (as_of / warning_evaluation_as_of / stale),
  nie still als aktuell dargestellt.
- Missing/unklar wird nie als 0/falsch ausgewiesen; Summaries fuehren
  ausgeschlossene Vertraege explizit.
- Kein N+1: wenige, gebundene Queries; Ergebnis bleibt bounded.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts.calculation.models import (
    CalculationStatus,
    ContractCalculationResult,
)
from app.database.models import (
    CalculationRun,
    Contract,
    ContractExtraction,
    ContractWarning,
    WarningEvaluationRun,
)

ACTION_QUEUE_LIMIT = 12

ACTIVE_STATES = {"active", "expiring_soon"}

_SEVERITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}
_WARNING_TYPE_PRIORITY = {
    "cancellation_deadline_passed": 0,
    "cancellation_deadline_today": 1,
    "cancellation_deadline_approaching": 2,
    "automatic_renewal_attention": 3,
    "contract_end_approaching": 4,
    "contract_expired": 5,
    "calculation_conflict": 6,
    "currency_conflict": 7,
    "cost_conflict": 8,
    "manual_review_required": 9,
    "unclear_contract_data": 10,
    "missing_cost_data": 11,
}
_APPROACHING_END = {"contract_end_approaching"}
_APPROACHING_CANCEL = {"cancellation_deadline_approaching"}
_CRITICAL_CANCEL = {
    "cancellation_deadline_today",
    "cancellation_deadline_passed",
}

# Kategorien, die im Fristen-Bucket nach 'threshold' gruppiert werden.
# 0 = heute faellig, None = verstrichen.
_BUCKET_ORDER: list[Optional[int]] = [None, 0, 7, 14, 30, 60, 90, 180]
_BUCKET_LABEL = {
    None: "Verstrichen",
    0: "Heute",
    7: "7 Tage",
    14: "14 Tage",
    30: "30 Tage",
    60: "60 Tage",
    90: "90 Tage",
    180: "180 Tage",
}


class DashboardError(Exception):
    """Fehler beim Zusammenstellen der Dashboard-Uebersicht."""

    detail_de = "Dashboard konnte nicht geladen werden."


def _severity_rank(severity: Optional[str]) -> int:
    return _SEVERITY_RANK.get(severity or "info", 4)


def _calc_snapshot(run: Optional[CalculationRun]) -> Optional[ContractCalculationResult]:
    if run is None or not run.result_snapshot:
        return None
    try:
        return ContractCalculationResult.model_validate(run.result_snapshot)
    except Exception:
        return None


def _money_total(currency: str, amount, count: int = 1) -> dict:
    if currency is None:
        return None
    try:
        dec = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    except (TypeError, ValueError):
        return None
    return {"currency": currency.upper(), "amount": dec, "contract_count": count or 1}


def _merge_total(bucket: dict, currency: str, amount, count: int = 1) -> None:
    entry = _money_total(currency, amount, count)
    if entry is None:
        return
    cur = entry["currency"]
    existing = next((t for t in bucket if t["currency"] == cur), None)
    if existing is None:
        bucket.append(entry)
    else:
        existing["amount"] = existing["amount"] + entry["amount"]
        existing["contract_count"] += entry["contract_count"]


def build_dashboard_overview(
    session: Session,
    *,
    organization_id,
    as_of_date: date,
    workspace_contract_ids=None,
) -> dict:
    contracts = session.scalars(
        select(Contract).where(
            (Contract.organization_id == organization_id)
            & (Contract.lifecycle_state == "active")
            & (Contract.is_archived.is_(False))
            & (
                Contract.id.in_(workspace_contract_ids)
                if workspace_contract_ids is not None
                else True
            )
        )
    ).all()

    contract_by_id = {c.id: c for c in contracts}
    if not contracts:
        return _empty_overview(as_of_date)

    # Gebundene, kompakte Abfragen statt N+1.
    active_warnings = session.scalars(
        select(ContractWarning).where(
            (ContractWarning.organization_id == organization_id)
            & (ContractWarning.active.is_(True))
            & (ContractWarning.contract_id.in_(list(contract_by_id)))
        )
    ).all()

    calc_ids = [c.accepted_calculation_run_id for c in contracts if c.accepted_calculation_run_id]
    calc_runs = {}
    if calc_ids:
        for run in session.scalars(
            select(CalculationRun).where(CalculationRun.id.in_(calc_ids))
        ).all():
            calc_runs[run.id] = run

    ext_ids = [c.accepted_extraction_id for c in contracts if c.accepted_extraction_id]
    ext_snapshots = {}
    if ext_ids:
        for ext in session.scalars(
            select(ContractExtraction).where(ContractExtraction.id.in_(ext_ids))
        ).all():
            ext_snapshots[ext.id] = ext.contract_snapshot or {}

    eval_as_of = session.execute(
        select(func.max(WarningEvaluationRun.as_of_date)).where(
            WarningEvaluationRun.organization_id == organization_id
        )
    ).scalar()
    last_calc_at = max(
        (calc_runs[c.accepted_calculation_run_id].as_of_date
         for c in contracts if c.accepted_calculation_run_id in calc_runs),
        default=None,
    )

    # ---------------- KPIs ----------------
    active_count = 0
    expiring_soon_count = 0
    active_set: set = set()
    for c in contracts:
        st = (c.status or "").lower()
        if st == "active":
            active_count += 1
            active_set.add(c.id)
        elif st == "expiring_soon":
            expiring_soon_count += 1
            active_set.add(c.id)

    end_warnings = {w.contract_id for w in active_warnings if w.warning_type in _APPROACHING_END}
    critical_cancel = {
        w.contract_id
        for w in active_warnings
        if w.warning_type in _CRITICAL_CANCEL
        or (
            w.warning_type in _APPROACHING_CANCEL
            and _severity_rank(w.severity) == 0
        )
    }

    # ---------------- Finanzen ----------------
    annual_bucket: list[dict] = []
    total_value_bucket: list[dict] = []
    without_annual = 0
    without_total = 0
    multi_currency = False

    for c in contracts:
        run = calc_runs.get(c.accepted_calculation_run_id)
        calc = _calc_snapshot(run) if run is not None else None
        if calc is not None:
            annual = calc.costs.normalized_recurring.annual
            reliable = (
                annual.value is not None
                and annual.currency is not None
                and annual.status
                in (CalculationStatus.CALCULATED, CalculationStatus.EXPLICIT)
                and not calc.costs.recurring_cost_conflict
                and not calc.costs.currency_conflict
            )
            if reliable:
                _merge_total(annual_bucket, annual.currency, annual.value)
            else:
                without_annual += 1
            if calc.costs.currency_conflict:
                multi_currency = True
        else:
            without_annual += 1

        # Totalvertragswert: nur wenn STEP 9 ihn als verlaesslich markiert hat.
        ext = ext_snapshots.get(c.accepted_extraction_id, {})
        costs_snap = ext.get("costs") or {}
        tcv = costs_snap.get("total_contract_value") or {}
        if calc is not None and calc.costs.total_contract_value_status == CalculationStatus.CALCULATED:
            tcv_amount = tcv.get("amount")
            tcv_currency = tcv.get("currency")
            if tcv_amount is not None and tcv_currency is not None:
                _merge_total(total_value_bucket, tcv_currency, tcv_amount)
            else:
                without_total += 1
        else:
            without_total += 1

    all_currencies = {
        t["currency"] for t in annual_bucket + total_value_bucket
    }
    if len(all_currencies) > 1:
        multi_currency = True

    # ---------------- Fristen-Buckets ----------------
    bucket_map: dict[Optional[int], dict] = {}
    for t in _BUCKET_ORDER:
        bucket_map[t] = {"threshold_days": t, "label_de": _BUCKET_LABEL[t], "contract_count": 0, "cancellation": 0, "contract_end": 0}

    for w in active_warnings:
        if w.warning_type in _APPROACHING_CANCEL or w.warning_type in _APPROACHING_END:
            key = w.threshold if w.threshold is not None else None
            b = bucket_map.get(key)
            if b is None:
                continue
            b["contract_count"] += 1
            if w.warning_type in _APPROACHING_CANCEL:
                b["cancellation"] += 1
            else:
                b["contract_end"] += 1
        elif w.warning_type in {"cancellation_deadline_today", "cancellation_deadline_passed"}:
            key = 0 if w.warning_type == "cancellation_deadline_today" else None
            b = bucket_map.get(key)
            if b is not None:
                b["contract_count"] += 1
                b["cancellation"] += 1

    deadlines = [_clean_bucket(bucket_map[t]) for t in _BUCKET_ORDER]

    # ---------------- Handlungsbedarf ----------------
    actionable = [
        w for w in active_warnings if (w.requires_action or w.requires_review)
    ]
    actionable.sort(
        key=lambda w: (
            _severity_rank(w.severity),
            _WARNING_TYPE_PRIORITY.get(w.warning_type, 99),
            w.target_date or date.max,
            w.logical_fingerprint,
        )
    )
    total_action_items = len(actionable)
    action_items = [_action_item(session, w, contract_by_id.get(w.contract_id), calc_runs) for w in actionable[:ACTION_QUEUE_LIMIT]]

    # ---------------- Datenqualitaet ----------------
    dq = _collect_data_quality(active_warnings)

    kpis = {
        "active_contracts": {
            "label_de": "Aktive Verträge",
            "value": len(active_set),
            "secondary_de": (
                f"{active_count} aktiv · {expiring_soon_count} bald auslaufend"
            ),
            "status_de": (
                "Operatives Portfolio (aktiv + bald auslaufend). "
                "Gekündigte und abgelaufene Verträge zählen nicht dazu."
            ),
        },
        "expiring_soon": {
            "label_de": "Bald auslaufende Verträge",
            "value": len(end_warnings),
            "secondary_de": "aktive Ende-Annäherungs-Warnungen",
            "status_de": "Verträge mit aktiver Vertragsende-Annäherung.",
        },
        "critical_cancellation": {
            "label_de": "Kritische Kündigungsfristen",
            "value": len(critical_cancel),
            "secondary_de": "kritisch / heute / verstrichen",
            "status_de": (
                "Kündigungsfristen mit kritischem Schweregrad, heute fällig oder "
                "bereits verstrichen. Keine automatische Kündigungs-Annahme."
            ),
        },
        "annual_costs": {
            "label_de": "Jährliche Gesamtkosten",
            "value": len(annual_bucket),
            "secondary_de": _kpis_currency_hint(annual_bucket),
            "status_de": "Anzahl Währungen mit verlässlichen jährlichen Kosten.",
        },
        "total_contract_value": {
            "label_de": "Gesamtvertragswert",
            "value": len(total_value_bucket),
            "secondary_de": _kpis_currency_hint(total_value_bucket),
            "status_de": "Anzahl Währungen mit verlässlich erfasstem Gesamtwert.",
        },
    }

    freshness_status = "current"
    if eval_as_of is None:
        freshness_status = "none"
    elif eval_as_of < as_of_date:
        freshness_status = "stale"

    return {
        "as_of_date": as_of_date,
        "freshness": {
            "requested_as_of_date": as_of_date,
            "warning_evaluation_as_of_date": eval_as_of,
            "data_freshness": freshness_status,
            "last_calculation_at": last_calc_at,
        },
        "kpis": kpis,
        "deadlines": deadlines,
        "action_items": action_items,
        "total_action_items": total_action_items,
        "financial": {
            "annual_recurring": annual_bucket,
            "total_contract_value": total_value_bucket,
            "contracts_without_reliable_annual_cost": without_annual,
            "contracts_without_reliable_total_value": without_total,
            "multi_currency": multi_currency,
        },
        "data_quality": dq,
    }


def _clean_bucket(b: dict) -> dict:
    return {
        "threshold_days": b["threshold_days"],
        "label_de": b["label_de"],
        "contract_count": b["contract_count"],
        "cancellation": b["cancellation"],
        "contract_end": b["contract_end"],
    }


def _kpis_currency_hint(bucket: list[dict]) -> Optional[str]:
    if not bucket:
        return None
    parts = [t["currency"] for t in bucket]
    return "· ".join(sorted(set(parts))) if len(parts) > 1 else parts[0]


def _action_item(session: Session, w: ContractWarning, contract, calc_runs) -> dict:
    calc = None
    annual = None
    cost_unreliable = False
    if contract is not None and contract.accepted_calculation_run_id in calc_runs:
        calc = _calc_snapshot(calc_runs[contract.accepted_calculation_run_id])
    if calc is not None:
        annual_field = calc.costs.normalized_recurring.annual
        reliable = (
            annual_field.value is not None
            and annual_field.currency is not None
            and annual_field.status
            in (CalculationStatus.CALCULATED, CalculationStatus.EXPLICIT)
            and not calc.costs.recurring_cost_conflict
            and not calc.costs.currency_conflict
        )
        if reliable:
            annual = _money_total(annual_field.currency, annual_field.value, 1)
        else:
            cost_unreliable = True

    return {
        "severity": w.severity,
        "warning_type": w.warning_type,
        "title_de": _action_title(w),
        "contract_title": _contract_title(contract),
        "supplier": contract.supplier if contract is not None else None,
        "target_date": w.target_date,
        "days_remaining": w.days_remaining,
        "requires_review": w.requires_review,
        "requires_action": w.requires_action,
        "annual_cost": annual,
        "cost_unreliable": cost_unreliable,
    }


def _action_title(w: ContractWarning) -> str:
    # Stabile, deutsche Kurzbezeichnung je Warn-Typ (keine Geschaeftslogik-Quelle).
    return {
        "contract_end_approaching": "Vertragsende nähert sich",
        "contract_expired": "Vertrag ausgelaufen",
        "cancellation_deadline_approaching": "Kündigungsfrist nähert sich",
        "cancellation_deadline_today": "Kündigungsfrist heute",
        "cancellation_deadline_passed": "Kündigungsfrist verstrichen",
        "automatic_renewal_attention": "Automatische Verlängerung beachten",
        "unclear_contract_data": "Vertragsdaten unklar",
        "calculation_conflict": "Berechnungskonflikt",
        "manual_review_required": "Manuelle Prüfung erforderlich",
        "missing_cost_data": "Fehlende verlässliche Kostenangabe",
        "cost_conflict": "Widersprüchliche Kostenangaben",
        "currency_conflict": "Mehrere Währungen",
    }.get(w.warning_type, w.warning_type)


def _contract_title(contract) -> Optional[str]:
    if contract is None:
        return None
    return contract.contract_number or contract.supplier or None


def _collect_data_quality(active_warnings) -> list[dict]:
    counts: dict[str, int] = {}
    severities: dict[str, str] = {}
    for w in active_warnings:
        key, label, sev = _dq_category(w)
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1
        cur = severities.get(key)
        if cur is None or _severity_rank(sev) < _severity_rank(cur):
            severities[key] = sev
    return [
        {"label_de": label, "count": counts[k], "severity": severities[k]}
        for k, label, _sev in _DQ_LABELS
        if k in counts
    ]


_DQ_LABELS = [
    ("unclear", "Unklare Vertragsdaten", "medium"),
    ("calc_conflict", "Berechnungskonflikte", "high"),
    ("cost_conflict", "Kostenkonflikte", "high"),
    ("missing_cost", "Fehlende Kostenangaben", "medium"),
    ("currency_conflict", "Währungskonflikte", "high"),
]


def _dq_category(w: ContractWarning):
    t = w.warning_type
    if t == "unclear_contract_data":
        return "unclear", "Unklare Vertragsdaten", "medium"
    if t == "manual_review_required":
        return None, None, None
    if t in ("calculation_conflict",):
        return "calc_conflict", "Berechnungskonflikte", "high"
    if t == "cost_conflict":
        return "cost_conflict", "Kostenkonflikte", "high"
    if t == "missing_cost_data":
        return "missing_cost", "Fehlende Kostenangaben", "medium"
    if t == "currency_conflict":
        return "currency_conflict", "Währungskonflikte", "high"
    return None, None, None


def _empty_overview(as_of_date: date) -> dict:
    return {
        "as_of_date": as_of_date,
        "freshness": {
            "requested_as_of_date": as_of_date,
            "warning_evaluation_as_of_date": None,
            "data_freshness": "none",
            "last_calculation_at": None,
        },
        "kpis": {
            "active_contracts": {
                "label_de": "Aktive Verträge", "value": 0,
                "secondary_de": None,
                "status_de": "Operatives Portfolio (aktiv + bald auslaufend).",
            },
            "expiring_soon": {
                "label_de": "Bald auslaufende Verträge", "value": 0,
                "secondary_de": None,
                "status_de": "Verträge mit aktiver Vertragsende-Annäherung.",
            },
            "critical_cancellation": {
                "label_de": "Kritische Kündigungsfristen", "value": 0,
                "secondary_de": None,
                "status_de": ("Kündigungsfristen kritisch / heute / verstrichen."),
            },
            "annual_costs": {
                "label_de": "Jährliche Gesamtkosten", "value": 0,
                "secondary_de": None,
                "status_de": "Anzahl Währungen mit verlässlichen jährlichen Kosten.",
            },
            "total_contract_value": {
                "label_de": "Gesamtvertragswert", "value": 0,
                "secondary_de": None,
                "status_de": "Anzahl Währungen mit verlässlich erfasstem Gesamtwert.",
            },
        },
        "deadlines": [
            {"threshold_days": t, "label_de": _BUCKET_LABEL[t], "contract_count": 0, "cancellation": 0, "contract_end": 0}
            for t in _BUCKET_ORDER
        ],
        "action_items": [],
        "total_action_items": 0,
        "financial": {
            "annual_recurring": [],
            "total_contract_value": [],
            "contracts_without_reliable_annual_cost": 0,
            "contracts_without_reliable_total_value": 0,
            "multi_currency": False,
        },
        "data_quality": [],
    }
