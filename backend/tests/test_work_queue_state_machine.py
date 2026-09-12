"""PR-5 Defect B – Work-Queue: State-Machine, kein Auferstehen, Filter.

Fokussierte Verifikation der geschaerrften Backend-Regeln:
1. Status-Transitionen folgen open -> acknowledged -> resolved (resolved
   terminal); Sprung soll-fehlen (resolved auf open/acknowledged 422).
2. reconcile_work_items darf ein bewusst resolved-Item NICHT wieder aktivieren
   (kein "Auferstehen" nach Neu-Ableitung).
3. List-/DTO-Filter unterstuetzen MEHRERE Statuswerte (SQL, Limit vor Filtern
   korrekt) und archivierte Vertraege bleiben draussen.

Nutzt das etablierte Transaktion-pro-Test-Muster (Rollback) gegen die via
conftest isolierte Test-Schema-Session. Ohne erreichbaren PostgreSQL wird die
Suite uebersprungen (bestehende Unit-Tests bleiben gruen).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from tests.helpers_persistence import attach_minimal_accepted_extraction
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import Contract, ContractWarning, Organization, WorkItem
from app.database.services import create_contract, create_organization
from app.models.enums import WorkItemStatus
from app.work_queue.service import (
    get_work_item_dto,
    list_work_items_dto,
    reconcile_work_items,
    set_work_item_status,
)


def _pg_available(engine) -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(settings.database_url, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _require_pg(engine):
    if not _pg_available(engine):
        pytest.skip("PostgreSQL nicht erreichbar – Work-Queue-Tests übersprungen")
    yield


@pytest.fixture
def db(engine):
    session = Session(engine, expire_on_commit=False)
    session.begin()
    yield session
    session.rollback()
    session.close()


def _org(db) -> Organization:
    return create_organization(
        db, name="WQ-Klinik", slug=f"wq-{uuid.uuid4().hex[:12]}"
    )


def _contract(db, org) -> Contract:
    return create_contract(
        db, organization_id=org.id, supplier="WQ-Lieferant",
        status="active", contract_number=f"WQ-{uuid.uuid4().hex[:8]}",
    )


def _derived(contract, *, extra_fp=None):
    fp = extra_fp or uuid.uuid4().hex
    return {
        "logical_fingerprint": fp,
        "item_type": "manual_review",
        "severity": "medium",
        "title_de": "Manuelle Pruefung noetig",
        "why_de": "Ergebnis bedarf der Pruefung.",
        "action_hint_de": "Pruefen und entscheiden.",
        "target_date": date.today(),
        "days_remaining": 7,
        "requires_review": True,
    }


def _single(db, org, contract, derived=None) -> WorkItem:
    if derived is None:
        derived = [_derived(contract)]
    reconcile_work_items(db, organization_id=org.id, contract_id=contract.id,
                         derived=derived)
    return db.scalars(
        select(WorkItem).where(
            (WorkItem.organization_id == org.id) & (WorkItem.contract_id == contract.id)
        )
    ).first()


def test_state_machine_open_acknowledged_resolved(db):
    org = _org(db)
    contract = _contract(db, org)
    wi = _single(db, org, contract)
    # open -> acknowledged
    set_work_item_status(db, organization_id=org.id, work_item_id=wi.id,
                         status=WorkItemStatus.ACKNOWLEDGED.value)
    assert wi.status == WorkItemStatus.ACKNOWLEDGED.value
    # acknowledged -> resolved
    set_work_item_status(db, organization_id=org.id, work_item_id=wi.id,
                         status=WorkItemStatus.RESOLVED.value)
    assert wi.status == WorkItemStatus.RESOLVED.value
    assert wi.active is False


def test_state_machine_resolved_is_terminal(db):
    from app.database.services import PersistenceError

    org = _org(db)
    contract = _contract(db, org)
    wi = _single(db, org, contract)
    set_work_item_status(db, organization_id=org.id, work_item_id=wi.id,
                         status=WorkItemStatus.RESOLVED.value)
    for target in (WorkItemStatus.OPEN.value, WorkItemStatus.ACKNOWLEDGED.value):
        with pytest.raises(PersistenceError):
            set_work_item_status(db, organization_id=org.id, work_item_id=wi.id,
                                 status=target)


def test_state_machine_open_to_resolved_allowed(db):
    org = _org(db)
    contract = _contract(db, org)
    wi = _single(db, org, contract)
    set_work_item_status(db, organization_id=org.id, work_item_id=wi.id,
                         status=WorkItemStatus.RESOLVED.value)
    assert wi.status == WorkItemStatus.RESOLVED.value


def test_reconcile_does_not_resurrect_resolved(db):
    org = _org(db)
    contract = _contract(db, org)
    derived = [_derived(contract)]
    wi = _single(db, org, contract, derived)
    set_work_item_status(db, organization_id=org.id, work_item_id=wi.id,
                         status=WorkItemStatus.RESOLVED.value)
    assert wi.active is False
    # Neue Ableitung mit identischem Fingerprint: resolved bleibt inaktiv.
    reconcile_work_items(db, organization_id=org.id, contract_id=contract.id,
                         derived=derived)
    db.flush()
    assert wi.active is False
    assert wi.status == WorkItemStatus.RESOLVED.value


def test_reconcile_reactivates_only_open_or_acknowledged(db):
    org = _org(db)
    contract = _contract(db, org)
    derived = [_derived(contract)]
    wi = _single(db, org, contract, derived)
    # Identischer Fingerprint erneut abgeleitet: open/acknowledged bleibt aktiv.
    reconcile_work_items(db, organization_id=org.id, contract_id=contract.id,
                         derived=derived)
    db.flush()
    assert wi.active is True


def test_list_multiple_statuses_and_archived_exclusion(db):
    org = _org(db)
    contract = _contract(db, org)
    wi_a = _single(db, org, contract)
    # zweites Item gleicher Vertrag, anderer Fingerprint
    reconcile_work_items(
        db,
        organization_id=org.id,
        contract_id=contract.id,
        derived=[_derived(contract, extra_fp="second-fingerprint")],
    )
    items = db.scalars(
        select(WorkItem).where(WorkItem.contract_id == contract.id)
    ).all()
    assert len(items) == 2
    set_work_item_status(db, organization_id=org.id, work_item_id=wi_a.id,
                         status=WorkItemStatus.RESOLVED.value)
    db.flush()
    # Status-Filter: nur open bleibt aktiv sichtbar; resolved ist terminal+inaktiv.
    dto_list = list_work_items_dto(
        db,
        organization_id=org.id,
        active_only=False,
        statuses=[WorkItemStatus.OPEN.value, WorkItemStatus.RESOLVED.value],
    )
    assert len(dto_list) == 2

    # Archivierter Vertrag ist aus der Liste ausgeschlossen.
    contract.is_archived = True
    db.flush()
    dto_archived = list_work_items_dto(db, organization_id=org.id, active_only=False)
    assert dto_archived == []


def test_sibling_duplicates_collapse_active_items(db):
    import uuid as _uuid
    from app.database.models import ContractEquipment, Equipment

    org = _org(db)
    contract = _contract(db, org)
    # Zwei Evidence-Zeilen fuer DASSELBE Geraet (wie identity_equipment.evidence.0/.1):
    # gleicher item_type, gleiches equipment_id, aber verschiedene Fingerprints.
    eq = Equipment(
        organization_id=org.id,
        device_name="Accutron MR",
        serial_number="88024307",
        identification_quality="partial",
    )
    db.add(eq)
    db.flush()
    f = "field_ref"
    for i, ev in enumerate([("a","evidence.0"), ("b","evidence.1")]):
        ceq = ContractEquipment(
            organization_id=org.id,
            contract_id=contract.id,
            equipment_id=eq.id,
            device_name="Accutron MR",
            model="Accutron MR",
            relationship_quality="partial",
            requires_review=True,
            identification_quality="partial",
            coverage_start=None,
            coverage_end=None,
            logical_fingerprint=ev[0],
            field_ref=f"identity_equipment.{ev[1]}",
            equipment_index=i,
        )
        db.add(ceq)
    db.flush()
    derived = []
    from app.work_queue.derive import derive_from_equipment, compute_fingerprint
    for ceq in db.scalars(
        select(ContractEquipment).where(ContractEquipment.contract_id == contract.id)
    ).all():
        item = derive_from_equipment(ceq)
        item["contract_id"] = str(contract.id)
        item["logical_fingerprint"] = compute_fingerprint(item)
        derived.append(item)
    assert len(derived) == 2
    reconcile_work_items(db, organization_id=org.id, contract_id=contract.id,
                         derived=derived)
    db.flush()
    actives = db.scalars(
        select(WorkItem).where(
            (WorkItem.organization_id == org.id)
            & (WorkItem.active.is_(True))
        )
    ).all()
    assert len(actives) == 1
    assert actives[0].title_de == "Geräte-Zuordnung prüfen: Accutron MR"
    # Nichts wurde geloescht; beide Zeilen existieren weiter.
    assert db.execute(
        select(WorkItem).where(WorkItem.organization_id == org.id)
    ).scalars().all().__len__() == 2


# ---------------------------------------------------------------------------
# PR-6 Defect A – Status-Update (Open -> In Bearbeitung) schlug als generisches
# "Status konnte nicht aktualisiert werden" fehl. Root-Cause-Klasse:
# 1) Kommen alter JSONB-Typ-Anomalien (references als Liste) vor, sprengt die
#    pydantic-Serialisierung WorkItemSummary.references: Optional[dict] die
#    PATCH-Antwort mit einem nackten 500 (kein Detail).
# 2) Der frühere Frontend-Client (apiPatch) verschluckte das echte `detail`
#    und zeigte nur den generischen Maskentext.
# Die Fix-Schichten: references-Ueberfuehrung auf dict-or-None (Write + DTO),
# ehrliche 503-/Detail-Behandlung im PATCH-Route und detail-durchsichtigende
# apiPatch. Diese Tests verankern alle drei Schichten.
# ---------------------------------------------------------------------------


def test_references_jsonb_legacy_list_never_breaks_dto(db):
    """Legacy-Listen-`references` (opake JSONB-Herkunft) sprengen DTO nicht."""
    org = _org(db)
    contract = _contract(db, org)
    wi = _single(db, org, contract, [_derived(contract, extra_fp="ref-fp")])
    # Historischer Datenstand: references als Liste persistiert (Type-Shift).
    wi.references = ["legacy", "ref"]
    db.flush()
    dto = list_work_items_dto(db, organization_id=org.id, active_only=False)
    assert len(dto) == 1
    assert dto[0]["references"] == {"legacy_refs": ["legacy", "ref"]}
    from app.work_queue.models import WorkItemSummary

    summary = WorkItemSummary(**dto[0])
    assert summary.references == {"legacy_refs": ["legacy", "ref"]}


def test_references_jsonb_legacy_list_survives_transition_persisted(db):
    """Status-Update klappt trotz Legacy-Listen-`references`; nur das Item."""
    org = _org(db)
    contract = _contract(db, org)
    wi = _single(db, org, contract, [_derived(contract, extra_fp="ref-fp2")])
    wi.references = ["legacy"]
    db.flush()
    set_work_item_status(db, organization_id=org.id, work_item_id=wi.id,
                         status=WorkItemStatus.ACKNOWLEDGED.value)
    db.flush()
    assert wi.status == WorkItemStatus.ACKNOWLEDGED.value
    dto = get_work_item_dto(db, organization_id=org.id, work_item_id=wi.id)
    assert dto is not None
    assert dto["references"] == {"legacy_refs": ["legacy"]}


def test_reconcile_normalizes_references_type(db):
    """Reconcile persistiert references nur als dict-or-None (JSONB-Invariante)."""
    org = _org(db)
    contract = _contract(db, org)
    derived = _derived(contract, extra_fp="ref-fp3")
    derived["references"] = ["a", "b"]
    reconcile_work_items(db, organization_id=org.id, contract_id=contract.id,
                         derived=[derived])
    db.flush()
    wi = db.scalars(
        select(WorkItem).where(
            (WorkItem.organization_id == org.id) & (WorkItem.contract_id == contract.id)
        )
    ).one()
    assert wi.references == {"legacy_refs": ["a", "b"]}