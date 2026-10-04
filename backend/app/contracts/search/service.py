"""Vertrags-Portfolio-Suche/-Filter (STEP 13) – READ-ONLY, org-gebunden, deterministisch.

PostgreSQL bleibt die autoritative Suchplattform (kein separater Suchdienst):
- strukturierte Filter ueber die `contract`-Projektion (org-gebunden),
- Warning-Filter ueber EXISTS (keine Joins -> keine Duplikatreihen),
- finanzielle/datums-/titel- Felder aus den AKZEPTIERTEN Lauefen via
  jsonb_extract_path_text (immer Current-/Accepted-Wahrheit, nie superseded),
- Volltext via stored generated `contract.search_vector` (GIN) + pg_trgm fuzzy.

Regeln:
- Keine KI, keine Neuberechnung von Warnungen/Fristen; STEP-11-Semantik autoritativ.
- Kein N+1: gebundene Queries (Seite, Warnungen IN-ids, akzeptierte Runs IN-ids,
  akzeptierte Extractions IN-ids, Equipment IN-ids, eine Aggregat-Query fuer Zaehler).
- Exakt/Praefix raengt vor FTS; FTS raengt vor konservativem fuzzy (min. Laenge).
- Identifikatoren (contract_number) werden NIE gestemmt ('simple'-TS-Nutzung bzw.
  exakte/trigram-Matching); Waehrungen nie gemischt; fehlend != 0.
- Organisation-Isolation auf Query-Ebene; kein globales Filtern in Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, Numeric, and_, case, cast, exists, func, or_, select
from sqlalchemy.orm import Session

from app.contracts.calculation.models import ContractCalculationResult
from app.database.models.contract import BUSINESS_STATUS_ALLOWED
from app.database.models import (
    CalculationRun,
    Contract,
    CostCenter,
    ContractEquipment,
    ContractExtraction,
    ContractPartner,
    ContractWarning,
    WarningEvaluationRun,
)

# ---------------------------------------------------------------------------
# Konstanten / Allowlists
# ---------------------------------------------------------------------------

MAX_QUERY_LENGTH = 200
PAGE_SIZES = [25, 50, 100]
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_OFFSET = 10000
FUZZY_MIN_LENGTH = 3
SIMILARITY_THRESHOLD = 0.3

STATUS_ALLOWLIST = {
    "active", "expiring_soon", "expired", "terminated", "unknown",
}
RISK_ALLOWLIST = {"low", "medium", "high", "unknown"}
WARNING_TYPE_ALLOWLIST = {
    "contract_end_approaching",
    "contract_expired",
    "cancellation_deadline_approaching",
    "cancellation_deadline_today",
    "cancellation_deadline_passed",
    "automatic_renewal_attention",
    "unclear_contract_data",
    "calculation_conflict",
    "manual_review_required",
    "missing_cost_data",
    "cost_conflict",
    "currency_conflict",
}
SORT_ALLOWLIST = {
    "operational", "relevance", "title", "supplier", "end_date", "cancellation_date",
    "annual_cost", "risk", "updated_at",
}
VALID_DIRECTIONS = {"asc", "desc"}

_SEVERITY_RANK = {
    "critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4,
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
_CRITICAL_CANCEL_TYPES = {
    "cancellation_deadline_today",
    "cancellation_deadline_passed",
}
_WARNING_TITLE = {
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
}

_ESCAPE_LIKE = re.compile(r"[%_\\]")


def _escape_like(s: str) -> str:
    return _ESCAPE_LIKE.sub(lambda m: "\\" + m.group(0), s)


@dataclass
class SearchParams:
    """Typisierte, validierte Such-/Filterparameter (Roh-Werte aus der Route)."""

    organization_id: object
    q: Optional[str] = None
    status: list[str] = field(default_factory=list)
    business_status: list[str] = field(default_factory=list)
    risk: list[str] = field(default_factory=list)
    warning_type: list[str] = field(default_factory=list)
    requires_action: Optional[bool] = None
    requires_review: Optional[bool] = None
    critical_cancellation: Optional[bool] = None
    automatic_renewal: Optional[bool] = None
    archived: Optional[bool] = None
    supplier: Optional[str] = None
    contract_number: Optional[str] = None
    cost_center_code: Optional[str] = None
    currency: Optional[str] = None
    annual_cost_min: Optional[Decimal] = None
    annual_cost_max: Optional[Decimal] = None
    start_date_from: Optional[date] = None
    start_date_to: Optional[date] = None
    end_date_from: Optional[date] = None
    end_date_to: Optional[date] = None
    cancellation_from: Optional[date] = None
    cancellation_to: Optional[date] = None
    sort: str = "operational"
    direction: str = "asc"
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class SearchError(Exception):
    """Fehler beim Suchen (generischer deutscher Client-Text)."""

    detail_de = "Vertragsliste konnte nicht geladen werden."


def normalize_q(q: Optional[str]) -> str:
    if q is None:
        return ""
    value = re.sub(r"\s+", " ", q).strip()
    if len(value) > MAX_QUERY_LENGTH:
        raise ValueError("Suchanfrage zu lang")
    return value


# ---------------------------------------------------------------------------
# Scalar-JSONB-Ableitungen aus AKZEPTIERTEN Laeufen (Current-/Accepted-Wahrheit)
# ---------------------------------------------------------------------------

def _extract_text(column, *keys: str):
    return func.jsonb_extract_path_text(column, *keys)


def _accepted_calc_value(keys: tuple[str, ...]):
    """Scalar-TEXT aus result_snapshot des akzeptierten Berechnungslaufs."""
    return (
        select(
            _extract_text(CalculationRun.result_snapshot, *keys)
        )
        .where(CalculationRun.id == Contract.accepted_calculation_run_id)
        .scalar_subquery()
    )


def _accepted_extr_value(keys: tuple[str, ...]):
    """Scalar-TEXT aus contract_snapshot der akzeptierten Extraktion."""
    return (
        select(
            _extract_text(ContractExtraction.contract_snapshot, *keys)
        )
        .where(ContractExtraction.id == Contract.accepted_extraction_id)
        .scalar_subquery()
    )


# ---------------------------------------------------------------------------
# JSONB-Feld-Ableitungen
# ---------------------------------------------------------------------------

def _annual_value() -> "object":
    return cast(_accepted_calc_value(("costs", "normalized_recurring", "annual", "value")), Numeric)


def _annual_currency():
    return _accepted_calc_value(("costs", "normalized_recurring", "annual", "currency"))


def _annual_status():
    return _accepted_calc_value(("costs", "normalized_recurring", "annual", "status"))


def _currency_conflict():
    return _accepted_calc_value(("costs", "currency_conflict"))


def _calc_end_date():
    return cast(_accepted_calc_value(("dates", "calculated_end_date", "value")), Date)


def _cancellation_date():
    return cast(_accepted_calc_value(("dates", "latest_cancellation_date", "value")), Date)


def _start_date():
    return cast(_accepted_extr_value(("dates", "start_date", "date")), Date)


def _auto_renewal():
    return _accepted_extr_value(("termination", "automatic_renewal"))


def _title():
    return _accepted_extr_value(("identity", "contract_title"))


# ---------------------------------------------------------------------------
# Base + Filter-Praedikate
# ---------------------------------------------------------------------------

def _base_predicates(org_id, archived: Optional[bool] = None):
    preds = [
        Contract.organization_id == org_id,
        Contract.lifecycle_state == "active",
    ]
    if archived is True:
        preds.append(Contract.is_archived.is_(True))
    else:
        # Default (Normal-Portfolio, archiv=NULL) und archiviert=Falsch:
        # nie archivierte Verträge im aktiven Bestand anzeigen.
        preds.append(Contract.is_archived.is_(False))
    return preds


def _warning_exists(org_id, *extra_conds):
    conds = [
        ContractWarning.organization_id == org_id,
        ContractWarning.contract_id == Contract.id,
        ContractWarning.active.is_(True),
    ]
    conds.extend(extra_conds)
    return exists(select(1).where(and_(*conds)))


def _action_exists(org_id) -> bool:
    return _warning_exists(org_id, ContractWarning.requires_action.is_(True))


def _review_exists(org_id) -> bool:
    return _warning_exists(org_id, ContractWarning.requires_review.is_(True))


def _critical_cancel_exists(org_id) -> bool:
    return _warning_exists(
        org_id,
        or_(
            ContractWarning.warning_type.in_(_CRITICAL_CANCEL_TYPES),
            and_(
                ContractWarning.warning_type == "cancellation_deadline_approaching",
                ContractWarning.severity == "critical",
            ),
        ),
    )


def _equipment_exists(q: str, fuzzy: bool):
    expr = func.lower(
        func.coalesce(ContractEquipment.device_name, "")
        + " "
        + func.coalesce(ContractEquipment.system_name, "")
        + " "
        + func.coalesce(ContractEquipment.model, "")
        + " "
        + func.coalesce(ContractEquipment.manufacturer, "")
        + " "
        + func.coalesce(ContractEquipment.serial_number, "")
    )
    conds = [
        ContractEquipment.contract_id == Contract.id,
        ContractEquipment.organization_id == Contract.organization_id,
        ContractEquipment.extraction_id == Contract.accepted_extraction_id,
    ]
    if fuzzy:
        conds.append(func.similarity(expr, q.lower()) >= SIMILARITY_THRESHOLD)
    else:
        conds.append(expr.contains(q.lower()))
    return exists(select(1).where(and_(*conds)))


def _build_filters(params: SearchParams, org_id, q: str):
    """Liefert [Praedikate] fuer die Consumption/Count-Abfragen (org-gebunden)."""
    preds = list(_base_predicates(org_id, archived=params.archived))

    if params.status:
        st = [s for s in params.status if s in STATUS_ALLOWLIST]
        if st:
            preds.append(Contract.status.in_(st))
    if params.business_status:
        bs = [s for s in params.business_status if s in BUSINESS_STATUS_ALLOWED]
        if bs:
            preds.append(Contract.business_status.in_(bs))
    if params.risk:
        rk = [r for r in params.risk if r in RISK_ALLOWLIST]
        if rk:
            preds.append(Contract.risk_level.in_(rk))
    if params.warning_type:
        wt = [w for w in params.warning_type if w in WARNING_TYPE_ALLOWLIST]
        if wt:
            preds.append(
                _warning_exists(org_id, ContractWarning.warning_type.in_(wt))
            )
    if params.requires_action is True:
        preds.append(_action_exists(org_id))
    elif params.requires_action is False:
        preds.append(~_action_exists(org_id))
    if params.requires_review is True:
        preds.append(_review_exists(org_id))
    elif params.requires_review is False:
        preds.append(~_review_exists(org_id))
    if params.critical_cancellation is True:
        preds.append(_critical_cancel_exists(org_id))
    elif params.critical_cancellation is False:
        preds.append(~_critical_cancel_exists(org_id))

    if params.automatic_renewal is True:
        preds.append(_auto_renewal() == "true")
    elif params.automatic_renewal is False:
        preds.append(_auto_renewal() == "false")

    if params.supplier:
        preds.append(func.lower(Contract.supplier) == params.supplier.strip().lower())

    # An exact code lookup remains org-scoped and never expands user visibility.
    # Workspace contract authorization is applied to the same final query.
    if params.cost_center_code is not None:
        code = params.cost_center_code.strip()
        preds.append(
            exists(
                select(1).where(
                    CostCenter.id == Contract.cost_center_id,
                    CostCenter.organization_id == Contract.organization_id,
                    CostCenter.code == code,
                )
            )
        )

    # Finanz-Filter: NUR verlaessliche (akzeptierte) Jahreskosten, Waehrung respektiert.
    annual_reliable = and_(
        _annual_value().is_not(None),
        _annual_currency().is_not(None),
        _annual_status().in_(("calculated", "explicit")),
        or_(
            _currency_conflict().is_(None),
            _currency_conflict() != "true",
        ),
    )
    if params.currency:
        preds.append(
            and_(
                annual_reliable,
                func.upper(_annual_currency()) == params.currency.upper(),
            )
        )
    if params.annual_cost_min is not None or params.annual_cost_max is not None:
        range_cond = and_(annual_reliable)
        if params.annual_cost_min is not None:
            range_cond = and_(range_cond, _annual_value() >= params.annual_cost_min)
        if params.annual_cost_max is not None:
            range_cond = and_(range_cond, _annual_value() <= params.annual_cost_max)
        preds.append(range_cond)

    # Datumsbereiche (autoritativ: akzeptierte STEP-9-/STEP-7-Werte).
    if params.start_date_from is not None:
        preds.append(_start_date() >= params.start_date_from)
    if params.start_date_to is not None:
        preds.append(_start_date() <= params.start_date_to)
    if params.end_date_from is not None:
        preds.append(_calc_end_date() >= params.end_date_from)
    if params.end_date_to is not None:
        preds.append(_calc_end_date() <= params.end_date_to)
    if params.cancellation_from is not None:
        preds.append(_cancellation_date() >= params.cancellation_from)
    if params.cancellation_to is not None:
        preds.append(_cancellation_date() <= params.cancellation_to)

    # Vertragsnummer (separates, eindeutiges Filterfeld – exakt oder Praefix).
    if params.contract_number:
        esc = _escape_like(params.contract_number.lower())
        cnum = func.lower(Contract.contract_number)
        preds.append(
            or_(cnum == params.contract_number.lower(), cnum.like(esc + "\\%", escape="\\"))
        )

    # Freitext q
    if q:
        preds.append(_text_match(params, org_id, q))

    return preds


def _text_match(params: SearchParams, org_id, q: str):
    lq = q.lower()
    esc = _escape_like(q.lower())
    fuzzy = len(q) >= FUZZY_MIN_LENGTH
    parts = [
        func.lower(Contract.contract_number) == lq,
        func.lower(Contract.contract_number).like(esc + "\\%", escape="\\"),
        func.lower(Contract.supplier) == lq,
        func.lower(Contract.supplier).like(esc + "\\%", escape="\\"),
        func.lower(_title()).contains(lq),
        Contract.search_vector.op("@@")(
            func.plainto_tsquery("german", q)
        ),
        _equipment_exists(q, fuzzy=False),
    ]
    if fuzzy:
        parts.append(
            func.similarity(Contract.contract_number, q) >= SIMILARITY_THRESHOLD
        )
        parts.append(
            func.similarity(Contract.supplier, q) >= SIMILARITY_THRESHOLD
        )
        parts.append(func.similarity(_title(), q) >= SIMILARITY_THRESHOLD)
        parts.append(_equipment_exists(q, fuzzy=True))
    return or_(*parts)


def _text_rank(params: SearchParams, org_id, q: str):
    """Deterministischer Relevanz-Rang (niedriger = besser). Exakt raengt vor fuzzy."""
    lq = q.lower()
    esc = _escape_like(q.lower())
    fuzzy = len(q) >= FUZZY_MIN_LENGTH
    equipment_hit = _equipment_exists(q, fuzzy=False)
    cases = [
        (func.lower(Contract.contract_number) == lq, 0),
        (func.lower(Contract.contract_number).like(esc + "\\%", escape="\\"), 1),
        (func.lower(_title()) == lq, 2),
        (func.lower(Contract.supplier) == lq, 3),
        (func.lower(_title()).contains(lq), 4),
        (func.lower(Contract.supplier).like(esc + "\\%", escape="\\"), 5),
        (equipment_hit, 6),
        (
            Contract.search_vector.op("@@")(
                func.plainto_tsquery("german", q)
            ),
            7,
        ),
    ]
    if fuzzy:
        cases.append(
            (
                or_(
                    func.similarity(Contract.contract_number, q) >= SIMILARITY_THRESHOLD,
                    func.similarity(Contract.supplier, q) >= SIMILARITY_THRESHOLD,
                    func.similarity(_title(), q) >= SIMILARITY_THRESHOLD,
                    _equipment_exists(q, fuzzy=True),
                ),
                8,
            )
        )
    else:
        cases.append((True, 99))
    return case(*cases, else_=99)


# ---------------------------------------------------------------------------
# Sortierung
# ---------------------------------------------------------------------------

def _urgency(org_id):
    return (
        select(
            func.min(
                case(
                    (ContractWarning.severity == "critical", 0),
                    (ContractWarning.severity == "high", 1),
                    (ContractWarning.severity == "medium", 2),
                    (ContractWarning.severity == "low", 3),
                    else_=4,
                )
            )
        )
        .where(
            (ContractWarning.organization_id == org_id)
            & (ContractWarning.contract_id == Contract.id)
            & (ContractWarning.active.is_(True))
        )
        .scalar_subquery()
    )


def _nearest_deadline():
    cancellation = _cancellation_date()
    end = _calc_end_date()
    return func.least(
        func.coalesce(cancellation, date.max),
        func.coalesce(end, date.max),
    )


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "unknown": 3, None: 3}


def _apply_order(stmt, params: SearchParams, org_id, q: str, urgency_expr):
    sort = params.sort
    direction = params.direction if params.direction in VALID_DIRECTIONS else "asc"
    asc = direction == "asc"

    if sort == "relevance" and q:
        rank = _text_rank(params, org_id, q)
        if asc:
            stmt = stmt.order_by(rank.asc(), Contract.contract_number.asc(), Contract.id.asc())
        else:
            stmt = stmt.order_by(rank.desc(), Contract.contract_number.desc(), Contract.id.desc())
        return stmt

    if sort == "title":
        col = func.lower(func.coalesce(Contract.contract_number, ""))
    elif sort == "supplier":
        col = func.lower(func.coalesce(Contract.supplier, ""))
    elif sort == "end_date":
        col = _calc_end_date()
    elif sort == "cancellation_date":
        col = _cancellation_date()
    elif sort == "annual_cost":
        col = _annual_value()
    elif sort == "risk":
        col = case(
            (Contract.risk_level == "low", 0),
            (Contract.risk_level == "medium", 1),
            (Contract.risk_level == "high", 2),
            else_=3,
        )
    elif sort == "updated_at":
        col = Contract.updated_at
    else:
        # Operationaler Default (kein expliziter Sort oder 'operational'):
        # Dringlichkeit -> naechstes relevantes Datum -> Titel -> id.
        deadline = _nearest_deadline()
        return (
            stmt.order_by(
                func.coalesce(urgency_expr, 99).asc(),
                (deadline == date.max).asc(),
                deadline.asc(),
                func.lower(func.coalesce(Contract.contract_number, "")).asc(),
                Contract.id.asc(),
            )
        )

    # Null-Werte deterministisch ans definierte Ende.
    if asc:
        return stmt.order_by(
            col.is_(None).asc(), col.asc(), Contract.id.asc()
        )
    return stmt.order_by(
        col.is_(None).asc(), col.desc(), Contract.id.desc()
    )


# ---------------------------------------------------------------------------
# Haupt-Lesefunktion
# ---------------------------------------------------------------------------

def build_contract_search(session: Session, params: SearchParams, *, organization_id, request_as_of: date, workspace_contract_ids=None) -> dict:
    q = normalize_q(params.q)
    preds = _build_filters(params, organization_id, q)
    if workspace_contract_ids is not None:
        preds = [*preds, Contract.id.in_(workspace_contract_ids)]
    urgency_expr = _urgency(organization_id)

    base = select(Contract).where(and_(*preds))

    # Aggregat-Zaehler (eine Query, FILTER-Aggregation) – org-gebunden.
    action_pred = _action_exists(organization_id)
    review_pred = _review_exists(organization_id)
    critical_pred = _critical_cancel_exists(organization_id)
    count_stmt = (
        select(
            func.count(Contract.id),
            func.count(Contract.id).filter(action_pred).label("requires_action"),
            func.count(Contract.id).filter(review_pred).label("requires_review"),
            func.count(Contract.id).filter(critical_pred).label("critical"),
            *[
                func.count(Contract.id).filter(Contract.status == st).label(f"st_{st}")
                for st in sorted(STATUS_ALLOWLIST)
            ],
        )
        .where(and_(*preds))
    )
    counts = session.execute(count_stmt).one()
    total = int(counts[0])
    status_counts = {
        st: int(getattr(counts, f"st_{st}") or 0) for st in sorted(STATUS_ALLOWLIST)
    }

    page_size = params.page_size if params.page_size in PAGE_SIZES else DEFAULT_PAGE_SIZE
    page = max(params.page, 1)
    offset = (page - 1) * page_size
    if offset > MAX_PAGE_OFFSET:
        raise SearchError("Seitenbereich zu tief.")

    stmt = _apply_order(base, params, organization_id, q, urgency_expr)
    stmt = stmt.offset(offset).limit(page_size)
    contracts = session.scalars(stmt).all()

    # Gebundene Folge-Abfragen (kein N+1).
    contract_ids = [c.id for c in contracts]
    warnings_by_contract = {}
    if contract_ids:
        active_warnings = session.scalars(
            select(ContractWarning).where(
                (ContractWarning.organization_id == organization_id)
                & (ContractWarning.active.is_(True))
                & (ContractWarning.contract_id.in_(contract_ids))
            )
        ).all()
        for w in active_warnings:
            warnings_by_contract.setdefault(w.contract_id, []).append(w)

    calc_by_id = {}
    calc_ids = [c.accepted_calculation_run_id for c in contracts if c.accepted_calculation_run_id]
    if calc_ids:
        for run in session.scalars(
            select(CalculationRun).where(CalculationRun.id.in_(calc_ids))
        ).all():
            calc_by_id[run.id] = run

    ext_by_id = {}
    ext_ids = [c.accepted_extraction_id for c in contracts if c.accepted_extraction_id]
    if ext_ids:
        for ext in session.scalars(
            select(ContractExtraction).where(ContractExtraction.id.in_(ext_ids))
        ).all():
            ext_by_id[ext.id] = ext

    equipment_by_contract = {}
    if contract_ids:
        rows = session.scalars(
            select(ContractEquipment).where(
                (ContractEquipment.organization_id == organization_id)
                & (ContractEquipment.contract_id.in_(contract_ids))
                & (ContractEquipment.extraction_id.in_(ext_ids))
            )
        ).all()
        for eq in rows:
            equipment_by_contract.setdefault(eq.contract_id, []).append(eq)

    eval_as_of = session.execute(
        select(func.max(WarningEvaluationRun.as_of_date)).where(
            WarningEvaluationRun.organization_id == organization_id
        )
    ).scalar()

    partner_ids = {c.partner_id for c in contracts if c.partner_id is not None}
    partner_names = dict(
        session.execute(
            select(ContractPartner.id, ContractPartner.short_name).where(ContractPartner.id.in_(partner_ids))
        ).all()
    ) if partner_ids else {}

    items = [
        _list_item(
            session, c,
            warnings_by_contract.get(c.id, []),
            calc_by_id.get(c.accepted_calculation_run_id),
            ext_by_id.get(c.accepted_extraction_id),
            equipment_by_contract.get(c.id, []),
            partner_names.get(c.partner_id),
        )
        for c in contracts
    ]

    freshness = "current"
    if eval_as_of is None:
        freshness = "none"
    elif eval_as_of < request_as_of:
        freshness = "stale"

    return {
        "organization_slug": _org_lookup(session, organization_id),
        "freshness": {
            "request_as_of_date": request_as_of,
            "warning_evaluation_as_of_date": eval_as_of,
            "data_freshness": freshness,
        },
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "has_more": (page * page_size) < total,
        "facets": {
            "status_counts": status_counts,
            "requires_action": int(counts.requires_action or 0),
            "requires_review": int(counts.requires_review or 0),
            "critical_cancellation": int(counts.critical or 0),
        },
        "items": items,
    }


def _org_lookup(session: Session, organization_id) -> str:
    from app.database.models import Organization
    slug = session.execute(
        select(Organization.slug).where(Organization.id == organization_id)
    ).scalar()
    return slug or ""


# ---------------------------------------------------------------------------
# DTO-Aufbau
# ---------------------------------------------------------------------------

def _list_item(session, contract, warnings, calc_run, ext, equipment, partner_name=None) -> dict:
    calc = None
    if calc_run is not None and calc_run.result_snapshot:
        try:
            calc = ContractCalculationResult.model_validate(calc_run.result_snapshot)
        except Exception:
            calc = None

    annual = _extract_annual(calc)

    title = None
    auto_renewal = None
    if ext is not None and ext.contract_snapshot:
        snap = ext.contract_snapshot
        title = (snap.get("identity") or {}).get("contract_title")
        auto_raw = (snap.get("termination") or {}).get("automatic_renewal")
        if isinstance(auto_raw, bool):
            auto_renewal = auto_raw
        elif auto_raw in ("true", True):
            auto_renewal = True
        elif auto_raw in ("false", False):
            auto_renewal = False

    primary = _primary_warning(warnings)
    has_action = any(w.requires_action for w in warnings)
    has_review = any(w.requires_review for w in warnings)

    row = {
        "contract_id": contract.id,
        "contract_number": contract.contract_number,
        "contract_title": contract.short_description or title,
        "supplier": partner_name or contract.supplier,
        "register_number": contract.register_number,
        "business_status": contract.business_status,
        "equipment_summary": _equipment_summary(equipment),
        "status": contract.status,
        "risk_level": contract.risk_level,
        "automatic_renewal": auto_renewal,
        "contract_end_date": _calc_date(calc, "calculated_end_date"),
        "latest_cancellation_date": _calc_date(calc, "latest_cancellation_date"),
        "annual_cost": annual,
        "primary_warning": primary,
        "requires_action": has_action,
        "requires_review": has_review,
        "is_archived": bool(contract.is_archived),
        "archived_at": contract.archived_at,
    }
    return row


def _extract_annual(calc) -> Optional[dict]:
    if calc is None:
        return {"currency": None, "amount": None, "unreliable": True}
    annual = calc.costs.normalized_recurring.annual
    reliable = (
        annual.value is not None
        and annual.currency is not None
        and annual.status.value in ("calculated", "explicit")
        and not calc.costs.currency_conflict
        and annual.status.value != "conflict"
    )
    if reliable:
        return {"currency": annual.currency.upper(), "amount": annual.value, "unreliable": False}
    return {"currency": None, "amount": None, "unreliable": True}


def _calc_date(calc, key) -> Optional[date]:
    if calc is None:
        return None
    field = getattr(calc.dates, key, None)
    if field is None:
        return None
    return field.value


def _equipment_summary(equipment, limit: int = 3, max_chars: int = 160) -> Optional[str]:
    if not equipment:
        return None
    names = []
    for eq in equipment:
        name = eq.device_name or eq.system_name or eq.model or eq.manufacturer
        if name and name not in names:
            names.append(name)
    summary = ", ".join(names[:limit])
    if len(summary) > max_chars:
        summary = summary[: max_chars - 1] + "…"
    return summary or None


def _primary_warning(warnings):
    if not warnings:
        return None
    best = min(
        warnings,
        key=lambda w: (
            _SEVERITY_RANK.get(w.severity, 4),
            _WARNING_TYPE_PRIORITY.get(w.warning_type, 99),
            w.target_date or date.max,
            w.logical_fingerprint,
        ),
    )
    return {
        "warning_type": best.warning_type,
        "severity": best.severity,
        "title_de": _WARNING_TITLE.get(best.warning_type, best.warning_type),
        "target_date": best.target_date,
    }
