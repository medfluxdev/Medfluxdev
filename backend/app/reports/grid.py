"""H7.1 Vertragsregister-Raster: Spaltenauswahl, Spaltenfilter, Gruppierung mit Summen.

Alle Werte werden deterministisch aus den Stammdaten berechnet (Fristen ueber
die Laufzeit-Engine, Kosten ueber die Finanz-Engine). Die Daten werden je Anfrage
gebuendelt geladen (keine N+1-Abfragen); die Sichtbarkeit bestimmt der Aufrufer.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable, Iterable, Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database.models import Account, Contract
from app.database.models.contract import ContractDocument
from app.contracts.search.service import _primary_warning
from app.database.models.deadlines import ContractDeadline
from app.database.models.fact_review import ContractReview
from app.database.models.warning import ContractWarning
from app.database.models.finance import ContractCostAllocation, ContractFinanceEntry
from app.database.models.organization_structure import ContractDepartment, CostCenter, Department, Hospital
from app.database.models.register import (
    CatalogContractCategory,
    CatalogContractType,
    ContractPartner,
    LookupValue,
)
from app.finance.calc import FinanceSummary, monthly_values, month_index, summarize
from app.finance.service import entry_inputs, price_adjustment
from app.register.service import retention_dates, term_inputs
from app.register.status import STATUS_LABELS
from app.register.terms import TERM_MODEL_LABELS, compute_terms
from app.rules.service import active_rules, evaluate_all as evaluate_rules, summary_status as rules_summary


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    type: str  # text | date | money | number | bool | status | enum | account
    default: bool = False
    groupable: bool = False


COLUMNS: tuple[Column, ...] = (
    Column("register_number", "Nr.", "text", default=True),
    Column("short_description", "Kurzbeschreibung", "text", default=True),
    Column("partner", "Vertragspartner", "enum", default=True, groupable=True),
    Column("contract_type", "Vertragstyp", "enum", default=True, groupable=True),
    Column("business_status", "Status", "status", default=True, groupable=True),
    Column("contract_category", "Kategorie", "enum", groupable=True),
    Column("internal_number", "Interne Nummer", "text"),
    Column("term_model", "Vertragsart", "enum", groupable=True),
    Column("term_status", "Laufzeitangaben", "enum", groupable=True),
    Column("term_start_date", "Vertragsbeginn", "date"),
    Column("earliest_end", "Frühestes Ende", "date"),
    Column("cancel_by", "Kündbar bis", "date", default=True),
    Column("possible_end", "Mögliches Ende", "date"),
    Column("terminated_on", "Gekündigt am", "date"),
    Column("terminated_effective", "Gekündigt zum", "date"),
    Column("reminder_date", "Erinnerung am", "date"),
    Column("reminder_recipient", "Erinnerung an", "account", groupable=True),
    Column("escalation_recipient", "Eskalation an", "account", groupable=True),
    Column("responsible", "Verantwortlich", "account", groupable=True),
    Column("next_deadline", "Nächster Termin", "date"),
    Column("hospital", "Krankenhaus", "enum", groupable=True),
    Column("department", "Abteilung", "enum", groupable=True),
    Column("cost_center", "Kostenstelle", "enum", groupable=True),
    Column("cost_allocation", "Kostenstellen-Aufteilung", "text"),
    Column("annual_cost", "Jährliche Kosten (netto)", "money", default=True),
    Column("cost_current_year", "Kosten lfd. Jahr (netto)", "money"),
    Column("cost_total_term", "Kosten Laufzeit (netto)", "money"),
    Column("income_current_year", "Einnahmen lfd. Jahr (netto)", "money"),
    Column("is_framework", "Rahmenvertrag", "bool", groupable=True),
    Column("data_protection_relevant", "Datenschutzrelevant", "bool", groupable=True),
    Column("is_confidential", "Vertraulich", "bool", groupable=True),
    Column("risk", "Risiko (KI)", "enum", groupable=True),
    Column("review_pending", "KI-Prüfung offen", "bool", groupable=True),
    Column("warning", "Warnung", "text"),
    Column("attachments", "Anhänge", "number"),
    Column("storage_location", "Lagerort", "enum", groupable=True),
    Column("deletion_from", "Löschen ab", "date"),
    Column("archived_at", "Archiviert am", "date"),
    Column("rules_status", "Vertragsregeln", "enum", groupable=True),
    Column("rules_violated", "Regelverstöße", "text"),
)
COLUMN_BY_KEY = {column.key: column for column in COLUMNS}
MONEY_KEYS = tuple(column.key for column in COLUMNS if column.type == "money")
DEFAULT_COLUMNS = [column.key for column in COLUMNS if column.default]
FILTER_OPS = {"empty", "not_empty", "in", "contains", "range", "within_days", "due_within_days", "overdue", "me", "is"}
MAX_GROUP_LEVELS = 2
RISK_LABELS = {"high": "Hoch", "medium": "Mittel", "low": "Niedrig"}
TERM_STATUS_LABELS = {"complete": "Vollständig", "incomplete": "Unvollständig", "not_applicable": "Unbefristet"}
# Summen werden je Waehrung gebildet; die Hauptwaehrung steht in `sums`.
MAIN_CURRENCY = "EUR"


class GridError(ValueError):
    pass


@dataclass
class GridSpec:
    columns: list[str] = field(default_factory=lambda: list(DEFAULT_COLUMNS))
    filters: list[dict] = field(default_factory=list)
    sort: Optional[dict] = None
    group_by: list[str] = field(default_factory=list)
    q: Optional[str] = None
    include_deleted: bool = False
    # Archiv-Ansicht: nur archivierte Vertraege (sonst sind sie ausgeblendet).
    archived: bool = False

    @classmethod
    def parse(cls, raw: Optional[dict]) -> "GridSpec":
        raw = raw or {}
        if not isinstance(raw, dict):
            raise GridError("Ungültige Ansicht.")
        columns = [key for key in raw.get("columns") or DEFAULT_COLUMNS if key in COLUMN_BY_KEY] or list(DEFAULT_COLUMNS)
        filters = []
        for item in raw.get("filters") or []:
            if not isinstance(item, dict) or item.get("column") not in COLUMN_BY_KEY or item.get("op") not in FILTER_OPS:
                raise GridError("Ungültiger Filter.")
            filters.append({"column": item["column"], "op": item["op"], "value": item.get("value")})
        sort = raw.get("sort")
        if sort is not None:
            if not isinstance(sort, dict) or sort.get("column") not in COLUMN_BY_KEY:
                raise GridError("Ungültige Sortierung.")
            sort = {"column": sort["column"], "dir": "desc" if sort.get("dir") == "desc" else "asc"}
        group_by = [key for key in raw.get("group_by") or [] if key in COLUMN_BY_KEY][:MAX_GROUP_LEVELS]
        if any(not COLUMN_BY_KEY[key].groupable for key in group_by):
            raise GridError("Nach dieser Spalte kann nicht gruppiert werden.")
        q = raw.get("q")
        return cls(
            columns=columns, filters=filters, sort=sort, group_by=group_by,
            q=str(q).strip() or None if q else None, include_deleted=bool(raw.get("include_deleted")),
            archived=raw.get("archived") is True,
        )

    def as_dict(self) -> dict:
        return {
            "columns": self.columns, "filters": self.filters, "sort": self.sort,
            "group_by": self.group_by, "q": self.q, "include_deleted": self.include_deleted,
            "archived": self.archived,
        }


@dataclass
class GridRow:
    contract_id: uuid.UUID
    values: dict[str, Any]
    ids: dict[str, Optional[uuid.UUID]]
    yearly: dict[int, dict[str, Decimal]] = field(default_factory=dict)
    allocations: list[tuple[str, Decimal]] = field(default_factory=list)
    upcoming: list[tuple[date, str]] = field(default_factory=list)


def _main_summary(summaries: list[FinanceSummary]) -> Optional[FinanceSummary]:
    if not summaries:
        return None
    for summary in summaries:
        if summary.currency == "EUR":
            return summary
    return summaries[0]


def _yearly(entries, adjustment, end: Optional[date], years: range) -> dict[int, dict[str, Decimal]]:
    first, last = years.start * 12, (years.stop - 1) * 12 + 11
    if end is not None:
        last = min(last, month_index(end))
    out: dict[int, dict[str, Decimal]] = defaultdict(lambda: {"expense": Decimal("0"), "income": Decimal("0")})
    for entry in entries:
        if (entry.currency or "EUR") != "EUR":
            continue
        for index, (net, _gross) in monthly_values(entry, first, last, adjustment).items():
            out[index // 12][entry.direction] += net
    return dict(out)


def build_rows(
    session: Session,
    organization_id: uuid.UUID,
    visible: Optional[set[uuid.UUID]],
    as_of: date,
    *,
    include_deleted: bool = True,
    years: Optional[range] = None,
    archived: bool = False,
) -> list[GridRow]:
    stmt = select(Contract).where(
        Contract.organization_id == organization_id,
        Contract.lifecycle_state == "active",
        Contract.is_archived.is_(archived),
    )
    if visible is not None:
        stmt = stmt.where(Contract.id.in_(visible))
    if not include_deleted:
        stmt = stmt.where(Contract.business_status != "geloescht")
    contracts = list(session.scalars(stmt).all())
    if not contracts:
        return []
    ids = [contract.id for contract in contracts]

    def names(model, key="name") -> dict[uuid.UUID, str]:
        return dict(session.execute(select(model.id, getattr(model, key)).where(model.organization_id == organization_id)).all())

    partners = dict(session.execute(
        select(ContractPartner.id, ContractPartner.short_name).where(ContractPartner.organization_id == organization_id)
    ).all())
    types = {
        row.id: row for row in session.scalars(
            select(CatalogContractType).where(CatalogContractType.organization_id == organization_id)
        ).all()
    }
    categories = names(CatalogContractCategory, "label")
    hospitals = names(Hospital)
    departments = names(Department)
    cost_centers = names(CostCenter)
    storage = dict(session.execute(
        select(LookupValue.code, LookupValue.label).where(
            LookupValue.organization_id == organization_id, LookupValue.field_key == "storage_location"
        )
    ).all())
    account_ids = {
        value for contract in contracts
        for value in (contract.responsible_account_id, contract.reminder_recipient_account_id, contract.escalation_recipient_account_id)
        if value
    }
    accounts = dict(session.execute(select(Account.id, Account.display_name).where(Account.id.in_(account_ids))).all()) if account_ids else {}

    department_links: dict[uuid.UUID, list[tuple[Optional[str], uuid.UUID]]] = defaultdict(list)
    for contract_id, department_id, role in session.execute(
        select(ContractDepartment.contract_id, ContractDepartment.department_id, ContractDepartment.relation_role)
        .where(ContractDepartment.contract_id.in_(ids))
    ).all():
        department_links[contract_id].append((role, department_id))

    allocations: dict[uuid.UUID, list[tuple[str, Decimal]]] = defaultdict(list)
    for contract_id, cost_center_id, share in session.execute(
        select(ContractCostAllocation.contract_id, ContractCostAllocation.cost_center_id, ContractCostAllocation.share_percent)
        .where(ContractCostAllocation.contract_id.in_(ids))
        .order_by(ContractCostAllocation.share_percent.desc())
    ).all():
        allocations[contract_id].append((cost_centers.get(cost_center_id, "?"), Decimal(share)))

    contract_rules = active_rules(session, organization_id)
    warnings_by_contract: dict[uuid.UUID, list] = defaultdict(list)
    for warning in session.scalars(
        select(ContractWarning).where(ContractWarning.contract_id.in_(ids), ContractWarning.active.is_(True))
    ).all():
        warnings_by_contract[warning.contract_id].append(warning)
    review_status = dict(session.execute(
        select(ContractReview.contract_id, ContractReview.status).where(ContractReview.contract_id.in_(ids))
    ).all())

    attachments = dict(session.execute(
        select(ContractDocument.contract_id, func.count()).where(ContractDocument.contract_id.in_(ids)).group_by(ContractDocument.contract_id)
    ).all())
    next_deadline = dict(session.execute(
        select(ContractDeadline.contract_id, func.min(ContractDeadline.due_date))
        .where(ContractDeadline.contract_id.in_(ids), ContractDeadline.status == "open")
        .group_by(ContractDeadline.contract_id)
    ).all())
    open_deadlines: dict[uuid.UUID, list[tuple[date, str]]] = defaultdict(list)
    if years is not None:
        for contract_id, due, title in session.execute(
            select(ContractDeadline.contract_id, ContractDeadline.due_date, ContractDeadline.title)
            .where(ContractDeadline.contract_id.in_(ids), ContractDeadline.status == "open")
        ).all():
            open_deadlines[contract_id].append((due, title))
    entries: dict[uuid.UUID, list[ContractFinanceEntry]] = defaultdict(list)
    for entry in session.scalars(
        select(ContractFinanceEntry).where(ContractFinanceEntry.contract_id.in_(ids))
        .order_by(ContractFinanceEntry.valid_from, ContractFinanceEntry.created_at)
    ).all():
        entries[entry.contract_id].append(entry)

    rows: list[GridRow] = []
    for contract in contracts:
        terms = compute_terms(term_inputs(contract), as_of)
        end = terms.actual_end or terms.possible_end
        contract_type = types.get(contract.contract_type_id) if contract.contract_type_id else None
        years_kept = contract.retention_years_after_end
        if years_kept is None and contract_type is not None:
            years_kept = contract_type.retention_years
        _, deletion_from = retention_dates(contract, terms, years_kept)

        links = department_links.get(contract.id, [])
        responsible_department = next((dep for role, dep in links if role == "responsible"), None)
        department_id = responsible_department or (links[0][1] if links else None)

        inputs = entry_inputs(entries.get(contract.id, []))
        adjustment, _ = price_adjustment(contract, as_of)
        summary = _main_summary(summarize(inputs, as_of=as_of, contract_end=end, adjustment=adjustment)) if inputs else None

        def money(bucket) -> Optional[Decimal]:
            return None if bucket is None else bucket.net.quantize(Decimal("0.01"))

        values: dict[str, Any] = {
            "register_number": contract.register_number,
            "short_description": contract.short_description or contract.supplier,
            "business_status": contract.business_status,
            "partner": partners.get(contract.partner_id) if contract.partner_id else contract.supplier,
            "contract_type": contract_type.label if contract_type else None,
            "contract_category": categories.get(contract.contract_category_id) if contract.contract_category_id else None,
            "internal_number": contract.internal_number,
            "term_model": TERM_MODEL_LABELS.get(contract.term_model) if contract.term_model else None,
            "term_status": TERM_STATUS_LABELS.get(terms.status, terms.status),
            "term_start_date": contract.term_start_date,
            "earliest_end": terms.earliest_end,
            "cancel_by": terms.cancel_by,
            "possible_end": terms.actual_end or terms.possible_end,
            "terminated_on": contract.terminated_on,
            "terminated_effective": contract.terminated_effective,
            "reminder_date": terms.reminder_date,
            "reminder_recipient": accounts.get(contract.reminder_recipient_account_id),
            "escalation_recipient": accounts.get(contract.escalation_recipient_account_id),
            "responsible": accounts.get(contract.responsible_account_id),
            "next_deadline": next_deadline.get(contract.id),
            "hospital": hospitals.get(contract.hospital_id) if contract.hospital_id else None,
            "department": departments.get(department_id) if department_id else None,
            "cost_center": cost_centers.get(contract.cost_center_id) if contract.cost_center_id else None,
            "cost_allocation": ", ".join(
                f"{name} {format(share.normalize(), 'f').replace('.', ',')} %" for name, share in allocations.get(contract.id, [])
            ) or None,
            "annual_cost": money(summary.expense.annual_run_rate) if summary else None,
            "cost_current_year": money(summary.expense.current_year) if summary else None,
            "cost_total_term": money(summary.expense.total_term) if summary else None,
            "income_current_year": money(summary.income.current_year) if summary else None,
            "is_framework": bool(contract.is_framework),
            "data_protection_relevant": contract.data_protection_relevant,
            "is_confidential": bool(contract.is_confidential or (contract_type.is_confidential if contract_type else False)),
            "risk": RISK_LABELS.get(contract.risk_level or "", None),
            "review_pending": contract.accepted_extraction_id is not None and review_status.get(contract.id) != "reviewed",
            "warning": (_primary_warning(warnings_by_contract[contract.id]) or {}).get("title_de") if warnings_by_contract.get(contract.id) else None,
            "attachments": int(attachments.get(contract.id, 0)),
            "storage_location": storage.get(contract.storage_location_code, contract.storage_location_code) if contract.storage_location_code else None,
            "archived_at": contract.archived_at.date() if contract.archived_at else None,
            "deletion_from": deletion_from,
            # Nicht als Spalte sichtbar: Waehrung der Betraege dieser Zeile.
            "_currency": summary.currency if summary else None,
        }
        rule_results = evaluate_rules(contract_rules, contract, values.get("annual_cost"))
        failed = [item for item in rule_results if item.outcome == "fail"]
        values["rules_status"] = rules_summary(rule_results)
        values["rules_violated"] = ", ".join(item.label for item in failed) or None
        # Nicht als Spalte sichtbar: fuer die Zaehlung je Regel (Stammdaten).
        values["_rule_failures"] = [str(item.rule_id) for item in failed]
        row = GridRow(
            contract_id=contract.id,
            values=values,
            ids={
                "responsible": contract.responsible_account_id,
                "reminder_recipient": contract.reminder_recipient_account_id,
                "escalation_recipient": contract.escalation_recipient_account_id,
            },
            allocations=allocations.get(contract.id, []),
        )
        if years is not None:
            row.yearly = _yearly(inputs, adjustment, end, years)
            row.upcoming = list(open_deadlines.get(contract.id, []))
            if terms.cancel_by and contract.business_status in ("in_arbeit", "gueltig"):
                row.upcoming.append((terms.cancel_by, "Kündigungsfrist"))
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- row cache

# Zwischenspeicher je Organisation/Stichtag. Gueltig nur, solange der
# Daten-Fingerabdruck gleich bleibt (jede Aenderung an Vertraegen, Finanzen,
# Terminen, Dokumenten, Katalogen, Organisation oder Kontonamen baut neu).
_CACHE_TTL_SECONDS = 300
_CACHE_MAX = 16
_cache: "OrderedDict[tuple, tuple[str, float, list[GridRow]]]" = OrderedDict()
_cache_lock = threading.Lock()

_FINGERPRINT_SQL = text("""
SELECT concat_ws('|',
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') || ':' || coalesce(max(created_at)::text, '')
     FROM contract WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM contract_finance_entry WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM contract_cost_allocation WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM contract_document WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM contract_deadline WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM contract_partner WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM catalog_contract_type WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM catalog_contract_category WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM lookup_value WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') FROM contract_rule WHERE organization_id = :org),
  (SELECT count(*) || ':' || coalesce(max(updated_at)::text, '') || ':' || coalesce(max(last_seen_at)::text, '')
     FROM contract_warning WHERE organization_id = :org AND active),
  (SELECT count(*) || ':' || coalesce(max(r.updated_at)::text, '')
     FROM contract_review r JOIN contract c ON c.id = r.contract_id WHERE c.organization_id = :org),
  (SELECT md5(coalesce(string_agg(contract_id::text || department_id::text || coalesce(relation_role, ''), ',' ORDER BY id), ''))
     FROM contract_department WHERE organization_id = :org),
  (SELECT md5(coalesce(string_agg(id::text || name, ',' ORDER BY id), '')) FROM hospital WHERE organization_id = :org),
  (SELECT md5(coalesce(string_agg(id::text || name, ',' ORDER BY id), '')) FROM department WHERE organization_id = :org),
  (SELECT md5(coalesce(string_agg(id::text || name, ',' ORDER BY id), '')) FROM cost_center WHERE organization_id = :org),
  (SELECT md5(coalesce(string_agg(a.id::text || a.display_name, ',' ORDER BY a.id), ''))
     FROM account a JOIN account_membership m ON m.account_id = a.id WHERE m.organization_id = :org)
)
""")


def data_fingerprint(session: Session, organization_id: uuid.UUID) -> str:
    return str(session.execute(_FINGERPRINT_SQL, {"org": organization_id}).scalar())


def cached_rows(
    session: Session, organization_id: uuid.UUID, as_of: date, *, years: Optional[range] = None, archived: bool = False
) -> list[GridRow]:
    """Alle Registerzeilen der Organisation (inkl. geloeschter); Sichtbarkeit filtert der Aufrufer.

    `archived=True` liefert stattdessen nur die archivierten Vertraege (Archiv-Ansicht).
    """
    key = (organization_id, as_of, (years.start, years.stop) if years else None, archived)
    fingerprint = data_fingerprint(session, organization_id)
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] == fingerprint and now - hit[1] < _CACHE_TTL_SECONDS:
            _cache.move_to_end(key)
            return hit[2]
    rows = build_rows(session, organization_id, None, as_of, years=years, archived=archived)
    with _cache_lock:
        _cache[key] = (fingerprint, now, rows)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return rows


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def visible_rows(rows: list[GridRow], visible: Optional[set[uuid.UUID]]) -> list[GridRow]:
    return rows if visible is None else [row for row in rows if row.contract_id in visible]


# --------------------------------------------------------------------------- filtering / sorting / grouping

def _as_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise GridError("Ungültiges Datum im Filter.")


def _as_number(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except Exception:
        raise GridError("Ungültige Zahl im Filter.")


def _predicate(item: dict, as_of: date, account_id: Optional[uuid.UUID]) -> Callable[[GridRow], bool]:
    column = COLUMN_BY_KEY[item["column"]]
    key, op, value = column.key, item["op"], item.get("value")

    if op == "empty":
        return lambda row: row.values[key] in (None, "")
    if op == "not_empty":
        return lambda row: row.values[key] not in (None, "")
    if op == "me":
        if column.type != "account":
            raise GridError("„Ich“ gilt nur für Personen-Spalten.")
        return lambda row: account_id is not None and row.ids.get(key) == account_id
    if op == "is":
        wanted = bool(value)
        return lambda row: bool(row.values[key]) is wanted
    if op == "in":
        allowed = {str(entry) for entry in (value if isinstance(value, list) else [value])}
        return lambda row: str(row.values[key]) in allowed if row.values[key] is not None else "" in allowed
    if op == "contains":
        needle = str(value or "").casefold()
        return lambda row: needle in str(row.values[key] or "").casefold()
    if op == "within_days":
        if column.type != "date":
            raise GridError("„In den nächsten Tagen“ gilt nur für Datumsspalten.")
        days = int(_as_number(value) or 0)
        until = as_of + timedelta(days=days)
        return lambda row: row.values[key] is not None and as_of <= row.values[key] <= until
    if op == "due_within_days":
        if column.type != "date":
            raise GridError("„Fällig in den nächsten Tagen“ gilt nur für Datumsspalten.")
        until = as_of + timedelta(days=int(_as_number(value) or 0))
        return lambda row: row.values[key] is not None and row.values[key] <= until
    if op == "overdue":
        if column.type != "date":
            raise GridError("„Fällig“ gilt nur für Datumsspalten.")
        return lambda row: row.values[key] is not None and row.values[key] <= as_of
    if op == "range":
        bounds = value if isinstance(value, dict) else {}
        if column.type == "date":
            low, high = _as_date(bounds.get("from")), _as_date(bounds.get("to"))
        elif column.type in ("money", "number"):
            low, high = _as_number(bounds.get("from")), _as_number(bounds.get("to"))
        else:
            raise GridError("Bereichsfilter gilt nur für Datum und Zahlen.")
        return lambda row: row.values[key] is not None and (low is None or row.values[key] >= low) and (high is None or row.values[key] <= high)
    raise GridError("Ungültiger Filter.")


def apply_filters(rows: Iterable[GridRow], spec: GridSpec, as_of: date, account_id: Optional[uuid.UUID]) -> list[GridRow]:
    predicates = [_predicate(item, as_of, account_id) for item in spec.filters]
    status_filtered = any(item["column"] == "business_status" for item in spec.filters)
    needle = spec.q.casefold() if spec.q else None
    out = []
    for row in rows:
        if not spec.include_deleted and not status_filtered and row.values["business_status"] == "geloescht":
            continue
        if needle and not any(
            needle in str(row.values[key] or "").casefold()
            for key in ("register_number", "short_description", "partner", "internal_number", "contract_type")
        ):
            continue
        if all(predicate(row) for predicate in predicates):
            out.append(row)
    return out


def _sort_value(value: Any) -> tuple:
    if value is None or value == "":
        return (1, "")
    if isinstance(value, str):
        return (0, value.casefold())
    return (0, value)


def sort_rows(rows: list[GridRow], spec: GridSpec) -> list[GridRow]:
    ordered = sorted(rows, key=lambda row: _sort_value(row.values["register_number"]))
    if spec.sort:
        key = spec.sort["column"]
        present = [row for row in ordered if row.values[key] not in (None, "")]
        missing = [row for row in ordered if row.values[key] in (None, "")]
        present.sort(key=lambda row: _sort_value(row.values[key]), reverse=spec.sort["dir"] == "desc")
        ordered = present + missing
    for key in reversed(spec.group_by):
        ordered.sort(key=lambda row: _sort_value(row.values[key]))
    return ordered


def display(column: Column, value: Any) -> Any:
    if value is None:
        return None
    if column.type == "status":
        return STATUS_LABELS.get(value, value)
    if column.type == "date":
        return value.isoformat()
    if column.type == "money":
        return str(value)
    if column.type == "bool":
        return bool(value)
    return value


class MoneyTotals:
    """Summe je Betragsspalte mit Abdeckung: unbekannte Werte werden nie zu 0.

    `sums[key]` ist die Summe der bekannten Werte in der Hauptwaehrung (None, wenn
    dort keiner bekannt ist), `coverage` zaehlt Zeilen mit bzw. ohne Wert (alle
    Waehrungen), `other_currencies` haelt Summen anderer Waehrungen getrennt
    (keine Umrechnung).
    """

    def __init__(self) -> None:
        self.count = 0
        self.sums = {key: Decimal("0") for key in MONEY_KEYS}
        self.main_known = {key: 0 for key in MONEY_KEYS}
        self.known = {key: 0 for key in MONEY_KEYS}
        self.missing = {key: 0 for key in MONEY_KEYS}
        self.other: dict[str, dict[str, Decimal]] = {key: {} for key in MONEY_KEYS}

    def add(self, row: "GridRow", share: Decimal = Decimal("1")) -> None:
        self.count += 1
        currency = row.values.get("_currency") or MAIN_CURRENCY
        for key in MONEY_KEYS:
            value = row.values[key]
            if value is None:
                self.missing[key] += 1
                continue
            self.known[key] += 1
            if currency == MAIN_CURRENCY:
                self.main_known[key] += 1
                self.sums[key] += value * share
            else:
                bucket = self.other[key]
                bucket[currency] = bucket.get(currency, Decimal("0")) + value * share

    def sum(self, key: str) -> Optional[Decimal]:
        return self.sums[key].quantize(Decimal("0.01")) if self.main_known[key] else None

    def payload(self) -> dict:
        return {
            "count": self.count,
            "currency": MAIN_CURRENCY,
            "sums": {key: (str(value) if (value := self.sum(key)) is not None else None) for key in MONEY_KEYS},
            "coverage": {key: {"known": self.known[key], "missing": self.missing[key]} for key in MONEY_KEYS},
            "other_currencies": {
                key: {currency: str(amount.quantize(Decimal("0.01"))) for currency, amount in sorted(self.other[key].items())}
                for key in MONEY_KEYS if self.other[key]
            },
        }


def money_totals(rows: Iterable["GridRow"]) -> MoneyTotals:
    result = MoneyTotals()
    for row in rows:
        result.add(row)
    return result


def groups(rows: list[GridRow], spec: GridSpec) -> list[dict]:
    if not spec.group_by:
        return []
    buckets: dict[tuple, MoneyTotals] = {}
    for row in rows:
        for depth in range(1, len(spec.group_by) + 1):
            path = tuple(row.values[key] for key in spec.group_by[:depth])
            buckets.setdefault(path, MoneyTotals()).add(row)
    out = []
    for path in sorted(buckets, key=lambda item: (len(item), [_sort_value(value) for value in item])):
        out.append({
            "path": [display(COLUMN_BY_KEY[spec.group_by[index]], value) for index, value in enumerate(path)],
            "labels": [
                display(COLUMN_BY_KEY[spec.group_by[index]], value) if value not in (None, "") else "(ohne)"
                for index, value in enumerate(path)
            ],
            **buckets[path].payload(),
        })
    return out


def totals(rows: list[GridRow]) -> dict:
    return money_totals(rows).payload()


def row_payload(row: GridRow, columns: list[str]) -> dict:
    keys = set(columns) | {"register_number", "business_status"}
    return {
        "contract_id": str(row.contract_id),
        "values": {key: display(COLUMN_BY_KEY[key], row.values[key]) for key in keys},
    }


def columns_payload(*, with_deleted: bool = True) -> list[dict]:
    statuses = [(code, label) for code, label in STATUS_LABELS.items() if with_deleted or code != "geloescht"]
    return [
        {
            "key": column.key, "label": column.label, "type": column.type, "default": column.default,
            "groupable": column.groupable,
            **({"options": [{"value": code, "label": label} for code, label in statuses]} if column.type == "status" else {}),
        }
        for column in COLUMNS
    ]


def distinct_values(rows: list[GridRow], key: str) -> list[dict]:
    column = COLUMN_BY_KEY[key]
    counts: dict[Any, int] = defaultdict(int)
    for row in rows:
        counts[row.values[key]] += 1
    ordered = sorted(counts, key=_sort_value)
    return [
        {"value": "" if value is None else str(display(column, value)) if column.type != "status" else value,
         "label": "(ohne)" if value in (None, "") else str(display(column, value)),
         "count": counts[value]}
        for value in ordered
    ]


def tree(rows: list[GridRow]) -> list[dict]:
    hospitals: dict[Optional[str], dict[Optional[str], int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        hospitals[row.values["hospital"]][row.values["department"]] += 1
    out = []
    for hospital in sorted(hospitals, key=_sort_value):
        departments = hospitals[hospital]
        out.append({
            "hospital": hospital,
            "label": hospital or "(ohne Krankenhaus)",
            "count": sum(departments.values()),
            "departments": [
                {"department": department, "label": department or "(ohne Abteilung)", "count": departments[department]}
                for department in sorted(departments, key=_sort_value)
            ],
        })
    return out
