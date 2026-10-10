"""Stammdaten-Uebersicht: Bestand je Datenart und Verwendung in Vertraegen.

Rein lesend. Die Verwendung zaehlt nur Vertraege, die der Benutzer sehen darf
(Bereich und Vertraulichkeit ueber `scoped_contract_ids`), und nie geloeschte.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from typing import Iterable, Optional

from sqlalchemy import func, select, union
from sqlalchemy.orm import Session

from app.core.clock import today_local
from app.database.models import ActivityLog, Contract
from app.database.models.finance import ContractCostAllocation
from app.database.models.organization_structure import ContractDepartment, CostCenter, Department, Hospital
from app.database.models.register import (
    CatalogContractCategory,
    CatalogContractType,
    ContractHospital,
    ContractPartner,
    ContractRule,
    LookupValue,
)
from app.register import catalogs

KINDS = ("partner", "hospital", "department", "cost_center", "contract_type", "contract_category", "lookup", "rule")

# Ereignisse im Aktivitaetsprotokoll je Datenart (fuer "zuletzt geaendert").
_EVENT_PREFIXES: dict[str, tuple[str, ...]] = {
    "partner": ("partner.",),
    "hospital": ("hospital.",),
    "department": ("department.",),
    "cost_center": ("cost_center.",),
    "contract_type": ("catalog.contract_type_",),
    "contract_category": ("catalog.contract_category_",),
    "lookup": ("catalog.lookup_",),
    "rule": ("catalog.rule_",),
}

# Auswahllisten, deren Wert direkt am Vertrag gespeichert ist (Code).
_LOOKUP_CONTRACT_COLUMNS = {"storage_location": Contract.storage_location_code}


class Scope:
    """Sichtbarer Ausschnitt der Organisationsstruktur fuer Nicht-Administratoren."""

    def __init__(self, restricted: bool, hospital_id: Optional[uuid.UUID], department_id: Optional[uuid.UUID]):
        self.restricted = restricted
        self.hospital_id = hospital_id
        self.department_id = department_id


def _structure_filters(scope: Scope):
    """Gleiche Einschraenkung wie die Lese-Endpunkte der Organisationsstruktur."""
    hospital, department, cost_center = [], [], []
    if not scope.restricted:
        return hospital, department, cost_center
    if scope.hospital_id is None:
        never = Hospital.id.is_(None)
        return [never], [Department.id.is_(None)], [CostCenter.id.is_(None)]
    hospital.append(Hospital.id == scope.hospital_id)
    department.append(Department.hospital_id == scope.hospital_id)
    cost_center.append(CostCenter.hospital_id == scope.hospital_id)
    if scope.department_id is not None:
        department.append(Department.id == scope.department_id)
        cost_center.append((CostCenter.department_id.is_(None)) | (CostCenter.department_id == scope.department_id))
    return hospital, department, cost_center


def _counts(session: Session, model, organization_id: uuid.UUID, extra: Iterable = ()) -> dict:
    rows = session.execute(
        select(model.is_active, func.count(model.id))
        .where(model.organization_id == organization_id, *extra)
        .group_by(model.is_active)
    ).all()
    active = sum(count for flag, count in rows if flag)
    inactive = sum(count for flag, count in rows if not flag)
    return {"total": active + inactive, "active": active, "inactive": inactive}


def _last_changes(session: Session, organization_id: uuid.UUID) -> dict[str, Optional[str]]:
    result: dict[str, Optional[str]] = {}
    for kind, prefixes in _EVENT_PREFIXES.items():
        clauses = [ActivityLog.event_name.startswith(prefix) for prefix in prefixes]
        value = session.scalar(
            select(func.max(ActivityLog.created_at)).where(ActivityLog.organization_id == organization_id, *clauses)
        )
        result[kind] = value.isoformat() if value else None
    return result


def summary(session: Session, organization_id: uuid.UUID, scope: Scope, visible: Optional[set[uuid.UUID]]) -> dict:
    hospital_filter, department_filter, cost_center_filter = _structure_filters(scope)
    kinds = {
        "partner": _counts(session, ContractPartner, organization_id),
        "hospital": _counts(session, Hospital, organization_id, hospital_filter),
        "department": _counts(session, Department, organization_id, department_filter),
        "cost_center": _counts(session, CostCenter, organization_id, cost_center_filter),
        "contract_type": _counts(session, CatalogContractType, organization_id),
        "contract_category": _counts(session, CatalogContractCategory, organization_id),
        "lookup": _counts(session, LookupValue, organization_id),
        "rule": _counts(session, ContractRule, organization_id),
    }
    changed = _last_changes(session, organization_id)
    for kind, data in kinds.items():
        data["last_change"] = changed.get(kind)

    lookup_rows = session.execute(
        select(LookupValue.field_key, LookupValue.is_active, func.count(LookupValue.id))
        .where(LookupValue.organization_id == organization_id)
        .group_by(LookupValue.field_key, LookupValue.is_active)
    ).all()
    lists: dict[str, dict[str, int]] = {key: {"active": 0, "inactive": 0} for key in catalogs.LOOKUP_FIELD_KEYS}
    for field_key, flag, count in lookup_rows:
        bucket = lists.setdefault(field_key, {"active": 0, "inactive": 0})
        bucket["active" if flag else "inactive"] += count

    # Nur mit Blick auf alle Vertraege aussagekraeftig; eingeschraenkte Benutzer sehen keinen Wert.
    unused_partners: Optional[int] = None
    if visible is None:
        partner_usage = usage(session, organization_id, "partner", None)
        active_partner_ids = session.scalars(
            select(ContractPartner.id).where(ContractPartner.organization_id == organization_id, ContractPartner.is_active.is_(True))
        ).all()
        unused_partners = sum(1 for partner_id in active_partner_ids if not partner_usage.get(str(partner_id)))
    duplicate_groups = len(catalogs.duplicate_groups(session, organization_id))
    return {
        "kinds": kinds,
        "lookup_lists": [{"field_key": key, **value} for key, value in lists.items()],
        "hints": {"partner_duplicate_groups": duplicate_groups, "partners_without_contracts": unused_partners},
    }


def _live_contracts(organization_id: uuid.UUID, visible: Optional[set[uuid.UUID]]):
    clauses = [Contract.organization_id == organization_id, Contract.deleted_at.is_(None)]
    if visible is not None:
        clauses.append(Contract.id.in_(visible or {uuid.UUID(int=0)}))
    return clauses


def _grouped(session: Session, pairs_stmt) -> dict[str, int]:
    """Zaehlt verschiedene Vertraege je Stammdatum aus (stammdatum_id, vertrag_id)-Paaren."""
    pairs = pairs_stmt.subquery()
    rows = session.execute(
        select(pairs.c.ref_id, func.count(func.distinct(pairs.c.contract_id)))
        .where(pairs.c.ref_id.is_not(None))
        .group_by(pairs.c.ref_id)
    ).all()
    return {str(ref_id): int(count) for ref_id, count in rows}


def usage(session: Session, organization_id: uuid.UUID, kind: str, visible: Optional[set[uuid.UUID]]) -> dict[str, int]:
    """Anzahl sichtbarer, nicht geloeschter Vertraege je Eintrag (nur Eintraege mit Treffern)."""
    live = _live_contracts(organization_id, visible)
    if kind == "partner":
        return _grouped(session, select(Contract.partner_id.label("ref_id"), Contract.id.label("contract_id")).where(*live))
    if kind == "contract_type":
        return _grouped(session, select(Contract.contract_type_id.label("ref_id"), Contract.id.label("contract_id")).where(*live))
    if kind == "contract_category":
        return _grouped(session, select(Contract.contract_category_id.label("ref_id"), Contract.id.label("contract_id")).where(*live))
    if kind == "hospital":
        return _grouped(session, union(
            select(Contract.hospital_id.label("ref_id"), Contract.id.label("contract_id")).where(*live),
            select(ContractHospital.hospital_id.label("ref_id"), ContractHospital.contract_id.label("contract_id"))
            .join(Contract, Contract.id == ContractHospital.contract_id).where(*live),
        ))
    if kind == "department":
        return _grouped(session, select(ContractDepartment.department_id.label("ref_id"), ContractDepartment.contract_id.label("contract_id"))
                        .join(Contract, Contract.id == ContractDepartment.contract_id).where(*live))
    if kind == "cost_center":
        return _grouped(session, union(
            select(Contract.cost_center_id.label("ref_id"), Contract.id.label("contract_id")).where(*live),
            select(ContractCostAllocation.cost_center_id.label("ref_id"), ContractCostAllocation.contract_id.label("contract_id"))
            .join(Contract, Contract.id == ContractCostAllocation.contract_id).where(*live),
        ))
    if kind == "rule":
        # Verstoesse je Regel ueber dieselben Zeilen wie die Vertragsliste (gleiche Auswertung).
        from app.reports.grid import cached_rows, visible_rows

        violations: dict[str, int] = defaultdict(int)
        for row in visible_rows(cached_rows(session, organization_id, today_local()), visible):
            if row.values.get("business_status") == "geloescht":
                continue
            for rule_id in row.values.get("_rule_failures") or []:
                violations[rule_id] += 1
        return dict(violations)
    if kind == "lookup":
        counts: dict[str, int] = defaultdict(int)
        for field_key, column in _LOOKUP_CONTRACT_COLUMNS.items():
            ids_by_code = dict(session.execute(
                select(LookupValue.code, LookupValue.id).where(
                    LookupValue.organization_id == organization_id, LookupValue.field_key == field_key
                )
            ).all())
            for code, count in session.execute(
                select(column, func.count(Contract.id)).where(*live, column.is_not(None)).group_by(column)
            ).all():
                if code in ids_by_code:
                    counts[str(ids_by_code[code])] += int(count)
        return dict(counts)
    raise ValueError(f"unknown kind {kind!r}")


def tracked_lookup_fields() -> list[str]:
    """Auswahllisten, deren Verwendung in Vertraegen gezaehlt werden kann."""
    return list(_LOOKUP_CONTRACT_COLUMNS)
