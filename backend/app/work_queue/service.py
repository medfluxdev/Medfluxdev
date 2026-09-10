"""PR-4 Arbeitsliste – Reconcile/Lebenszyklus/Abruf (Persistenz).

Idempotente Materialisierung: `reconcile_work_items` gleicht die aus
`derive_work_items` abgeleitete autoritative Liste mit der DB ab
(upsert per `logical_fingerprint` je Vertrag; nicht mehr abgeleitete
Eintraege werden NICHT geloescht, sondern `active=False` – konsistent zum
Warn-Lifecycle von STEP 11). Status-Transitionen (open/acknowledged/resolved)
sind der menschliche Lebenszyklus.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import WorkItem
from app.database.services import PersistenceError
from app.models.enums import WorkItemStatus

WORK_ITEM_STATUS_ALLOWED = {s.value for s in WorkItemStatus}


def _references_as_dict(value) -> Optional[dict]:
    """Normiert `references` auf dict-or-None (JSONB-Typ-Invariante).

    `WorkItemSummary.references` ist `Optional[dict]`. Historische Daten
    koennen Listen-/Fremdformen enthalten (opake JSONB-Herkunft). Diese werden
    NIE still verworfen, aber der Typ darf die API-/DTO-Serialisierung nicht
    sprengen (500) – eine Liste wird opak als `legacy_refs` beibehalten.
    Nur dict (oder None) verlassen diese Schicht.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"legacy_refs": value} if value else None
    return None

# Menschlicher Lebenszyklus: Open -> In Bearbeitung -> Erledigt. "Erledigt"
# ist terminal (bewusst geschlossen); resolved-Items duerfen weder zurueck
# auf open/acknowledged gesetzt noch von reconcile wieder aktiviert werden.
WORK_ITEM_TRANSITIONS: dict[str, set[str]] = {
    WorkItemStatus.OPEN.value: {
        WorkItemStatus.ACKNOWLEDGED.value,
        WorkItemStatus.RESOLVED.value,
    },
    WorkItemStatus.ACKNOWLEDGED.value: {WorkItemStatus.RESOLVED.value},
    WorkItemStatus.RESOLVED.value: set(),
}


def _now_utc() -> datetime:
    return datetime.now()


def reconcile_work_items(
    session: Session,
    *,
    organization_id,
    contract_id,
    derived: Iterable[dict],
    now: Optional[datetime] = None,
) -> None:
    """Gleicht abgeleitete Arbeitselemente idempotent mit der DB ab."""
    now = now or _now_utc()
    existing = {
        wi.logical_fingerprint: wi
        for wi in session.scalars(
            select(WorkItem).where(
                (WorkItem.organization_id == organization_id)
                & (WorkItem.contract_id == contract_id)
            )
        )
    }
    wanted_fps: set[str] = set()
    for d in derived:
        fp = d["logical_fingerprint"]
        wanted_fps.add(fp)
        wi = existing.get(fp)
        if wi is None:
            wi = WorkItem(
                organization_id=organization_id,
                contract_id=contract_id,
                logical_fingerprint=fp,
                item_type=d["item_type"].value
                if hasattr(d["item_type"], "value") else d["item_type"],
                severity=d.get("severity", "low"),
                status=WorkItemStatus.OPEN.value,
                title_de=d["title_de"],
                why_de=d.get("why_de"),
                action_hint_de=d.get("action_hint_de"),
                target_date=d.get("target_date"),
                days_remaining=d.get("days_remaining"),
                requires_review=bool(d.get("requires_review")),
                active=True,
                source_warning_id=d.get("source_warning_id"),
                contract_equipment_id=d.get("contract_equipment_id"),
                equipment_id=d.get("equipment_id"),
                calc_field_refs=d.get("calc_field_refs") or None,
                source_field_refs=d.get("source_field_refs") or None,
                references=_references_as_dict(d.get("references")),
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(wi)
            existing[fp] = wi
            continue
        # Update des evaluierten Zustands (Identitaet/Fingerprint bleibt).
        wi.contract_equipment_id = d.get("contract_equipment_id") or wi.contract_equipment_id
        wi.equipment_id = d.get("equipment_id") or wi.equipment_id
        wi.source_warning_id = d.get("source_warning_id") or wi.source_warning_id
        wi.severity = d.get("severity", wi.severity)
        wi.title_de = d["title_de"]
        wi.why_de = d.get("why_de")
        wi.action_hint_de = d.get("action_hint_de")
        wi.target_date = d.get("target_date")
        wi.days_remaining = d.get("days_remaining")
        wi.requires_review = bool(d.get("requires_review"))
        wi.calc_field_refs = d.get("calc_field_refs") or None
        wi.source_field_refs = d.get("source_field_refs") or None
        wi.references = _references_as_dict(d.get("references"))
        # Bewusst geschlossene (resolved) Arbeit bleibt hinter aktiv-Liste zurueck:
        # reconcile darf kein erledigtes Item wieder aktivieren (kein "Auferstehen").
        if not wi.active and wi.status != WorkItemStatus.RESOLVED.value:
            wi.active = True
        wi.last_seen_at = now
    # Staaleness: nicht mehr abgeleitete Arbeitselemente objektiv inaktiv.
    for fp, wi in existing.items():
        if fp not in wanted_fps and wi.active:
            wi.active = False
            wi.last_seen_at = now
    _collapse_sibling_duplicates(session, organization_id=organization_id,
                                 contract_id=contract_id, now=now)
    session.flush()


def _collapse_sibling_duplicates(
    session: Session, *, organization_id, contract_id, now: datetime
) -> None:
    """Eine Geräte-Familie darf nur EIN aktives Arbeitselement je item_type haben.

    Symptom PR-5 Defect B: Pro `contract_equipment`-Evidence-Zeile wird ein
    Abdeckungs-Review abgeleitet – zwei Evidence-Zeilen fuer dasselbe Geraet
    erzeugten daher zwei scheinbar identische "Geräte-Zuordnung prüfen"-Items
    (nur Fingerprint verschieden). Es wird NICHTS geloescht: Der Verlierer
    wird inaktiv (active=False) und seine Referenzen/Quellverweise gehen an
    das aelteste aktive Element der Familie ueber (append-only, idempotent).
    """
    from app.database.models import WorkItem

    actives = session.scalars(
        select(WorkItem).where(
            (WorkItem.organization_id == organization_id)
            & (WorkItem.contract_id == contract_id)
            & (WorkItem.active.is_(True))
        )
    ).all()
    families: dict[tuple, list[WorkItem]] = {}
    for wi in actives:
        if wi.equipment_id is not None:
            key = (wi.equipment_id, wi.item_type)
        elif wi.contract_equipment_id is not None:
            key = (wi.contract_equipment_id, wi.item_type)
        else:
            continue
        families.setdefault(key, []).append(wi)
    for siblings in families.values():
        if len(siblings) <= 1:
            continue
        siblings.sort(key=lambda w: (w.first_seen_at or datetime.min, str(w.id)))
        keeper, *losers = siblings
        merged_source: list = list(keeper.source_field_refs or [])
        for loser in losers:
            for sref in (loser.source_field_refs or []):
                if sref not in merged_source:
                    merged_source.append(sref)
            loser.active = False
            loser.last_seen_at = now
        # references bleiben beim Keeper unveraendert (opake JSONB-Herkunft,
        # Typ darf nicht verschoben werden - siehe WorkItemSummary.references).
        keeper.source_field_refs = merged_source


def set_work_item_status(
    session: Session,
    *,
    organization_id,
    work_item_id,
    status: str,
    now: Optional[datetime] = None,
) -> WorkItem:
    """Menschlicher Lebenszyklus eines Arbeitselements (open/acknowledged/resolved)."""
    if status not in WORK_ITEM_STATUS_ALLOWED:
        raise PersistenceError(f"ungueltiger work_item.status: {status!r}")
    wi = session.scalars(
        select(WorkItem).where(
            (WorkItem.organization_id == organization_id)
            & (WorkItem.id == work_item_id)
        )
    ).first()
    if wi is None:
        raise PersistenceError("work_item nicht gefunden")
    allowed = WORK_ITEM_TRANSITIONS.get(wi.status, set())
    if status not in WORK_ITEM_STATUS_ALLOWED:
        raise PersistenceError(f"ungueltiger work_item.status: {status!r}")
    if status != wi.status and status not in allowed:
        raise PersistenceError(
            f"Work-Item-State-Machine: {wi.status!r} -> {status!r} nicht erlaubt. "
            "Reihenfolge: open -> acknowledged -> resolved (resolved ist terminal)."
        )
    wi.status = status
    wi.status_updated_at = now or _now_utc()
    if status == WorkItemStatus.RESOLVED.value:
        # Gelöste Arbeit objektiv nicht mehr aktiv.
        wi.active = False
    session.flush()
    return wi


def list_work_items(
    session: Session,
    *,
    organization_id,
    active_only: bool = True,
    statuses: Optional[Iterable[str]] = None,
    severities: Optional[Iterable[str]] = None,
    item_types: Optional[Iterable[str]] = None,
    limit: int = 200,
):
    from app.database.models import Contract

    # Archivierte Verträge tauchen nicht in der aktiven Arbeitsliste auf.
    stmt = (
        select(WorkItem)
        .join(Contract, Contract.id == WorkItem.contract_id)
        .where(
            (WorkItem.organization_id == organization_id)
            & (Contract.organization_id == organization_id)
            & (Contract.lifecycle_state == "active")
            & (Contract.is_archived.is_(False))
        )
    )
    if active_only:
        stmt = stmt.where(WorkItem.active.is_(True))
    if statuses:
        stmt = stmt.where(WorkItem.status.in_(list(statuses)))
    if severities:
        stmt = stmt.where(WorkItem.severity.in_(list(severities)))
    if item_types:
        stmt = stmt.where(WorkItem.item_type.in_(list(item_types)))
    stmt = stmt.order_by(
        WorkItem.severity.asc(), WorkItem.target_date.asc().nulls_last()
    ).limit(limit)
    return list(session.scalars(stmt))


def list_contract_work_items(
    session: Session,
    *,
    organization_id,
    contract_id,
    active_only: bool = True,
):
    stmt = select(WorkItem).where(
        (WorkItem.organization_id == organization_id)
        & (WorkItem.contract_id == contract_id)
    )
    if active_only:
        stmt = stmt.where(WorkItem.active.is_(True))
    stmt = stmt.order_by(WorkItem.severity.asc(), WorkItem.target_date.asc().nulls_last())
    return list(session.scalars(stmt))


# Enriched DTO (Vertragsinfo eingebettet) für die Arbeitsliste
def _to_dto(wi: WorkItem, contract=None, equipment=None) -> dict:
    return {
        "id": str(wi.id),
        "contract_id": str(wi.contract_id),
        "contract_number": getattr(contract, "contract_number", None) if contract else None,
        "supplier": getattr(contract, "supplier", None) if contract else None,
        "equipment_id": str(wi.equipment_id) if wi.equipment_id else None,
        "contract_equipment_id": str(wi.contract_equipment_id) if wi.contract_equipment_id else None,
        "source_warning_id": str(wi.source_warning_id) if wi.source_warning_id else None,
        "item_type": wi.item_type,
        "severity": wi.severity,
        "status": wi.status,
        "title_de": wi.title_de,
        "why_de": wi.why_de,
        "action_hint_de": wi.action_hint_de,
        "target_date": wi.target_date.isoformat() if wi.target_date else None,
        "days_remaining": wi.days_remaining,
        "requires_review": wi.requires_review,
        "active": wi.active,
        "references": _references_as_dict(wi.references),
        "first_seen_at": wi.first_seen_at.isoformat() if wi.first_seen_at else None,
        "last_seen_at": wi.last_seen_at.isoformat() if wi.last_seen_at else None,
        "equipment_device_name": getattr(equipment, "device_name", None) if equipment else None,
        "equipment_manufacturer": getattr(equipment, "manufacturer", None) if equipment else None,
        "equipment_model": getattr(equipment, "model", None) if equipment else None,
        "equipment_serial_number": getattr(equipment, "serial_number", None) if equipment else None,
    }


def list_work_items_dto(
    session: Session,
    *,
    organization_id,
    active_only: bool = True,
    statuses: Optional[Iterable[str]] = None,
    severities: Optional[Iterable[str]] = None,
    item_types: Optional[Iterable[str]] = None,
    limit: int = 200,
) -> list[dict]:
    from app.database.models import Contract, Equipment

    items = list_work_items(
        session,
        organization_id=organization_id,
        active_only=active_only,
        statuses=statuses,
        severities=severities,
        item_types=item_types,
        limit=limit,
    )
    contracts = {
        c.id: c
        for c in session.scalars(
            select(Contract).where(
                (Contract.organization_id == organization_id)
                & (Contract.id.in_([w.contract_id for w in items]))
            )
        )
    } if items else {}
    equipment_ids = {w.equipment_id for w in items if w.equipment_id}
    equipment = {
        e.id: e
        for e in session.scalars(
            select(Equipment).where(
                (Equipment.organization_id == organization_id)
                & (Equipment.id.in_(equipment_ids))
            )
        )
    } if equipment_ids else {}
    return [_to_dto(w, contracts.get(w.contract_id), equipment.get(w.equipment_id)) for w in items]


def get_work_item_dto(
    session: Session,
    *,
    organization_id,
    work_item_id,
) -> Optional[dict]:
    from app.database.models import Contract

    wi = session.scalars(
        select(WorkItem).where(
            (WorkItem.organization_id == organization_id)
            & (WorkItem.id == work_item_id)
        )
    ).first()
    if wi is None:
        return None
    contract = session.get(Contract, wi.contract_id)
    return _to_dto(wi, contract)
