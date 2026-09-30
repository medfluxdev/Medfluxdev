"""PR-4 – Equipment & Arbeitsliste: fokussierte Verifikation.

Nutzt das etablierte Transaktion-pro-Test-Muster (Rollback) gegen native
PostgreSQL. Bei nicht erreichbarer DB wird SKIPPED (Unit-Suite bleibt grün).
Abgedeckt: Identitäts-Ableitung, kanonische Master-Zuordnung (1 Gerät <-> n
Verträge, n Geräte <-> 1 Vertrag), Duplikat-Handling, Beziehungs-Dedup,
deterministische Arbeitslisten-Ableitung, Reconcile-Idempotenz,
stale->inactive, Warn-Herkunft, Lebenszyklus, Org-Isolation, API-Routen,
Reprocessing ohne Duplikate.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from tests.helpers_persistence import attach_minimal_accepted_extraction
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete as sa_delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import (
    Contract,
    ContractEquipment,
    ContractExtraction,
    ContractWarning,
    DocumentFile,
    DocumentVersion,
    Equipment,
    Organization,
    WorkItem,
)
from app.database.services import (
    add_equipment,
    create_contract,
    create_document_version,
    create_organization,
    resolve_equipment_master,
    save_document_file,
)
from app.equipment.identity import (
    identification_quality,
    relationship_quality,
    requires_manual_review,
)
from app.equipment.service import get_equipment_detail, list_equipment
from app.models.enums import IdentificationQuality, RelationshipQuality, WorkItemStatus
from app.work_queue.derive import compute_fingerprint, derive_work_items
from app.work_queue.service import (
    list_work_items,
    reconcile_work_items,
    set_work_item_status,
)

import app.main as _main


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
        pytest.skip("PostgreSQL nicht erreichbar – PR-4-Tests übersprungen")
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
        db, name="PR4-Klinik", slug=f"pr4-{uuid.uuid4().hex[:12]}"
    )


def _contract(db, org, number="CN") -> Contract:
    contract = create_contract(
        db, organization_id=org.id, supplier="Lieferant",
        status="active", contract_number=f"{number}-{uuid.uuid4().hex[:8]}",
    )
    token = uuid.uuid4().hex
    doc = save_document_file(
        db,
        organization_id=org.id,
        sha256=(token + "0" * 32)[:64],
        original_filename="fixture.pdf",
        stored_filename="fixture.pdf",
        file_extension=".pdf",
        file_size_bytes=1,
        storage_key=f"tests/{token}/fixture.pdf",
        mime_type="application/pdf",
    )
    ver = create_document_version(
        db,
        organization_id=org.id,
        document_file_id=doc.id,
        version_no=1,
        sha256=(uuid.uuid4().hex + "1" * 32)[:64],
        storage_key=f"tests/{token}/v1.pdf",
    )
    attach_minimal_accepted_extraction(
        db, contract=contract, document_version_id=ver.id
    )
    return contract


def _warning(db, org, contract, *, wtype, severity="high", requires_action=False,
             requires_review=True, fingerprint=None) -> ContractWarning:
    w = ContractWarning(
        organization_id=org.id,
        contract_id=contract.id,
        warning_type=wtype,
        severity=severity,
        target_kind="cancellation_deadline",
        target_date=date(2026, 6, 1),
        days_remaining=30,
        logical_fingerprint=fingerprint or uuid.uuid4().hex,
        active=True,
        requires_action=requires_action,
        requires_review=requires_review,
        action_state="open",
        calculation_field_refs=["dates.latest_cancellation_date"],
        source_field_refs=["termination.cancellation_period"],
    )
    db.add(w)
    db.flush()
    return w


# ---------------------------------------------------------------------------
# 1) Deterministische Identitäts-Ableitung
# ---------------------------------------------------------------------------

def test_identity_quality_matrix(db):
    assert identification_quality(serial_number="SN-1") == IdentificationQuality.EXACT
    assert identification_quality(inventory_number="INV-9") == IdentificationQuality.EXACT
    assert identification_quality(model="ECG-3000") == IdentificationQuality.PARTIAL
    assert identification_quality(equipment_category="Kühlgeräte") == IdentificationQuality.GENERIC
    assert identification_quality() == IdentificationQuality.UNKNOWN
    # Beziehung
    assert relationship_quality(IdentificationQuality.EXACT, has_evidence=True) == RelationshipQuality.EXACT
    assert relationship_quality(IdentificationQuality.EXACT, has_evidence=False) == RelationshipQuality.PARTIAL
    assert relationship_quality(IdentificationQuality.PARTIAL, has_evidence=True) == RelationshipQuality.PARTIAL
    assert relationship_quality(IdentificationQuality.UNKNOWN) == RelationshipQuality.AMBIGUOUS
    assert requires_manual_review(RelationshipQuality.EXACT) is False
    assert requires_manual_review(RelationshipQuality.PARTIAL) is True


# ---------------------------------------------------------------------------
# 2) Kanonische Master-Zuordnung
# ---------------------------------------------------------------------------

def test_one_device_many_contracts_share_master(db):
    org = _org(db)
    c1 = _contract(db, org, "A")
    c2 = _contract(db, org, "B")
    m1 = resolve_equipment_master(
        db, organization_id=org.id, serial_number="SN-XYZ", device_name="MRT",
        identification_quality="exact",
    )
    m2 = resolve_equipment_master(
        db, organization_id=org.id, serial_number="SN-XYZ", device_name="MRT",
        identification_quality="exact",
    )
    assert m1.id == m2.id
    eq1 = add_equipment(db, contract_id=c1.id, serial_number="SN-XYZ", device_name="MRT", has_evidence=True)
    eq2 = add_equipment(db, contract_id=c2.id, serial_number="SN-XYZ", device_name="MRT", has_evidence=True)
    db.flush()
    assert eq1.equipment_id == eq2.equipment_id == m1.id
    # Beide Verträge zeigen auf dasselbe kanonische Gerät.
    links = list_equipment(db, organization_id=org.id)
    assert len(links) == 1
    assert links[0].contract_count == 2



def test_equipment_catalog_counts_distinct_contracts_not_coverage_rows(db):
    """Two current coverage rows for one physical unit count as one contract."""
    org = _org(db)
    contract = _contract(db, org, "TWO-SCOPES")
    first = add_equipment(
        db, contract_id=contract.id, device_name="CT Main",
        serial_number="SHARED-001", service_scope="Maintenance",
    )
    second = add_equipment(
        db, contract_id=contract.id, device_name="CT Console",
        serial_number="SHARED-001", service_scope="Inspection",
    )
    assert first.id != second.id
    assert first.equipment_id == second.equipment_id
    catalog = list_equipment(db, organization_id=org.id)
    row = next(item for item in catalog if item.id == str(first.equipment_id))
    assert row.contract_count == 1
    detail = get_equipment_detail(
        db, organization_id=org.id, equipment_id=first.equipment_id
    )
    assert detail is not None
    assert detail.contract_count == 1
    assert len(detail.contracts) == 2
    assert {link.service_scope for link in detail.contracts} == {
        "Maintenance", "Inspection"
    }



def test_known_serial_without_source_reports_missing_evidence_not_missing_serial(db):
    """Review guidance must not claim a known serial is absent."""
    from app.work_queue.derive import derive_from_equipment
    from app.equipment.identity import review_reason_de

    org = _org(db)
    contract = _contract(db, org, "KNOWN-NO-SOURCE")
    row = add_equipment(
        db, contract_id=contract.id, device_name="Infusion Pump",
        serial_number="KNOWN-01", has_evidence=False,
    )
    assert row.identification_quality == "exact"
    assert row.relationship_quality == "partial"
    assert row.requires_review
    assert "keine eindeutige Serien" not in " ".join(row.review_reasons or [])
    assert "Quellenbeleg" in " ".join(row.review_reasons or [])
    task = derive_from_equipment(row)
    assert task is not None
    assert "Quellenbeleg" in task["why_de"]
    assert "nur partial identifiziert" not in task["why_de"]



def test_distinct_coverage_scopes_keep_separate_review_tasks(db):
    """One canonical unit with two services requires two review decisions."""
    org = _org(db)
    contract = _contract(db, org, "REVIEW-SCOPES")
    first = add_equipment(
        db, contract_id=contract.id, device_name="CT Main",
        serial_number="REVIEW-001", service_scope="Maintenance",
        has_evidence=False,
    )
    second = add_equipment(
        db, contract_id=contract.id, device_name="CT Console",
        serial_number="REVIEW-001", service_scope="Inspection",
        has_evidence=False,
    )
    assert first.equipment_id == second.equipment_id
    derived = derive_work_items(
        contract_id=str(contract.id), warnings=[],
        equipment_rows=[first, second], as_of_date=date(2026, 9, 30),
        policy_version="test",
    )
    assert len(derived) == 2
    reconcile_work_items(
        db, organization_id=org.id, contract_id=contract.id,
        derived=derived,
    )
    active = db.scalars(
        select(WorkItem).where(
            (WorkItem.organization_id == org.id)
            & (WorkItem.contract_id == contract.id)
            & (WorkItem.active.is_(True))
        )
    ).all()
    assert len(active) == 2
    assert {row.contract_equipment_id for row in active} == {
        first.id, second.id
    }


def test_system_name_only_creates_reviewable_canonical_equipment(db):
    """Keep explicitly extracted system labels in the master equipment list."""
    org = _org(db)
    contract = _contract(db, org, "SYSTEM")
    row = add_equipment(
        db, contract_id=contract.id, system_name="Accutron MR", has_evidence=True
    )
    db.flush()
    assert row.device_name is None
    assert row.system_name == "Accutron MR"
    assert row.identification_quality == "partial"
    assert row.requires_review is True
    assert row.equipment_id is not None
    master = db.get(Equipment, row.equipment_id)
    assert master.device_name == "Accutron MR"
    assert master.organization_id == org.id
    listed = list_equipment(db, organization_id=org.id)
    assert any(item.device_name == "Accutron MR" for item in listed)
    from app.work_queue.derive import derive_from_equipment
    review_item = derive_from_equipment(row)
    assert review_item is not None
    assert "Accutron MR" in review_item["title_de"]
    assert "Accutron MR" in review_item["why_de"]



@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known persistence blocker: fingerprint and unique constraint collapse "
        "distinct same-name units without serial/inventory identifiers"
    ),
)
def test_distinct_same_name_units_without_identifiers_remain_separate(db):
    """Two separately sourced units must not disappear at persistence."""
    org = _org(db)
    contract = _contract(db, org, "SAME-NAME")
    first = add_equipment(
        db, contract_id=contract.id, device_name="Infusion Pump",
        model="IP-7", equipment_index=0,
        field_ref="identity_equipment.evidence.0", has_evidence=True,
    )
    second = add_equipment(
        db, contract_id=contract.id, device_name="Infusion Pump",
        model="IP-7", equipment_index=1,
        field_ref="identity_equipment.evidence.1", has_evidence=True,
    )
    assert first.id != second.id
    assert db.scalar(
        select(func.count(ContractEquipment.id)).where(
            ContractEquipment.contract_id == contract.id,
            ContractEquipment.extraction_id == contract.accepted_extraction_id,
        )
    ) == 2



@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known persistence blocker: equipment fingerprint ignores distinct "
        "coverage scope and returns the first row in one extraction"
    ),
)
def test_same_identified_device_keeps_two_distinct_coverage_scopes(db):
    """A single physical unit may have two independently sourced service rows."""
    org = _org(db)
    contract = _contract(db, org, "SCOPE-ROWS")
    first = add_equipment(
        db, contract_id=contract.id, device_name="CT Main",
        serial_number="SCOPE-001", service_scope="Maintenance",
        field_ref="identity_equipment.evidence.0", equipment_index=0,
        has_evidence=True,
    )
    second = add_equipment(
        db, contract_id=contract.id, device_name="CT Main",
        serial_number="SCOPE-001", service_scope="Inspection",
        field_ref="identity_equipment.evidence.1", equipment_index=1,
        has_evidence=True,
    )
    assert first.id != second.id
    assert first.equipment_id == second.equipment_id
    assert {first.service_scope, second.service_scope} == {
        "Maintenance", "Inspection"
    }


def test_one_contract_many_devices(db):
    org = _org(db)
    c = _contract(db, org, "MULTI")
    a = add_equipment(db, contract_id=c.id, serial_number="SN-1", device_name="MRT")
    b = add_equipment(db, contract_id=c.id, serial_number="SN-2", device_name="CT")
    c3 = add_equipment(db, contract_id=c.id, serial_number="SN-3", device_name="RÖ")
    db.flush()
    rows = db.scalars(
        select(ContractEquipment).where(
            (ContractEquipment.contract_id == c.id)
            & (ContractEquipment.organization_id == org.id)
        )
    ).all()
    assert {r.serial_number for r in rows} == {"SN-1", "SN-2", "SN-3"}


def test_duplicate_serial_inventory_not_replicated_per_org(db):
    org = _org(db)
    c1 = _contract(db, org, "D1")
    c2 = _contract(db, org, "D2")
    m1 = resolve_equipment_master(db, organization_id=org.id, serial_number="SN-DUP", identification_quality="exact")
    m2 = resolve_equipment_master(db, organization_id=org.id, serial_number="SN-DUP", identification_quality="exact")
    assert m1.id == m2.id
    # Gleicher (content-gleicher) Vertrag -> eine Zeile (Dedup je Vertrag).
    e1 = add_equipment(db, contract_id=c1.id, serial_number="SN-DUP", has_evidence=True)
    e2 = add_equipment(db, contract_id=c1.id, serial_number="SN-DUP", has_evidence=True)
    assert e1.id == e2.id
    db.flush()
    cnt = db.scalar(
        select(func.count()).select_from(ContractEquipment).where(
            (ContractEquipment.contract_id == c1.id)
        )
    )
    assert cnt == 1


def test_partial_identity_gets_own_master_not_merged(db):
    org = _org(db)
    c1 = _contract(db, org, "P1")
    add_equipment(db, contract_id=c1.id, model="ECG-3000", has_evidence=True)
    add_equipment(db, contract_id=c1.id, model="ECG-3000", has_evidence=True)
    db.flush()
    eq_row = db.scalars(
        select(ContractEquipment).where(
            (ContractEquipment.contract_id == c1.id)
            & (ContractEquipment.organization_id == org.id)
        )
    ).one()
    assert eq_row.identification_quality == "partial"
    assert eq_row.relationship_quality == "partial"
    assert eq_row.requires_review is True


# ---------------------------------------------------------------------------
# 3) Arbeitslisten-Ableitung (deterministisch, pure)
# ---------------------------------------------------------------------------

def test_derive_work_items_from_warnings_and_equipment(db):
    org = _org(db)
    c = _contract(db, org, "WQ")
    w_active = _warning(db, org, c, wtype="cancellation_deadline_approaching",
                        requires_review=True, fingerprint="fp-cancel")
    eq = add_equipment(db, contract_id=c.id, model="ECG", has_evidence=True)
    db.flush()
    warnings = [w_active]
    eqs = [eq]
    derived = derive_work_items(
        contract_id=str(c.id), warnings=warnings, equipment_rows=eqs,
        as_of_date=date(2026, 9, 3), policy_version="pr4-1",
    )
    types = {d["item_type"].value for d in derived}
    assert "cancellation_deadline" in types
    assert "equipment_coverage_review" in types
    # Fingerprints stabil/deterministisch.
    again = derive_work_items(
        contract_id=str(c.id), warnings=warnings, equipment_rows=eqs,
        as_of_date=date(2026, 9, 3), policy_version="pr4-1",
    )
    assert [d["logical_fingerprint"] for d in derived] == [d["logical_fingerprint"] for d in again]


def test_derive_skips_non_actionable_warning(db):
    org = _org(db)
    c = _contract(db, org, "SKIP")
    _warning(db, org, c, wtype="unclear_contract_data", requires_action=False,
             requires_review=False, fingerprint="fp-skip")
    db.flush()
    warnings = db.scalars(select(ContractWarning).where(ContractWarning.contract_id == c.id)).all()
    derived = derive_work_items(
        contract_id=str(c.id), warnings=warnings, equipment_rows=[],
        as_of_date=date(2026, 9, 3), policy_version="pr4-1",
    )
    assert derived == []


def test_warning_lineage_fields(db):
    org = _org(db)
    c = _contract(db, org, "WQ2")
    w = _warning(db, org, c, wtype="automatic_renewal_attention", requires_review=True,
                 fingerprint="fp-renew", severity="medium")
    db.flush()
    item = derive_work_items(
        contract_id=str(c.id), warnings=[w], equipment_rows=[],
        as_of_date=date(2026, 9, 3), policy_version="pr4-1",
    )[0]
    assert item["item_type"].value == "automatic_renewal"
    assert item["source_warning_fingerprint"] == "fp-renew"
    assert item["source_warning_id"] == w.id


# ---------------------------------------------------------------------------
# 4) Reconcile / Idempotenz / stale->inactive / Lebenszyklus
# ---------------------------------------------------------------------------

def _reconcile(db, org, contract, warnings, eqs, as_of):
    derived = derive_work_items(
        contract_id=str(contract.id), warnings=warnings, equipment_rows=eqs,
        as_of_date=as_of, policy_version="pr4-1",
    )
    reconcile_work_items(db, organization_id=org.id, contract_id=contract.id, derived=derived)
    db.flush()
    return derived


def test_reconcile_idempotent_creates_once(db):
    org = _org(db)
    c = _contract(db, org, "IDEM")
    w = _warning(db, org, c, wtype="cost_conflict", requires_review=True, fingerprint="fp-cost")
    eq = add_equipment(db, contract_id=c.id, model="X", has_evidence=True)
    db.flush()
    as_of = date(2026, 9, 3)
    _reconcile(db, org, c, [w], [eq], as_of)
    _reconcile(db, org, c, [w], [eq], as_of)
    cnt = db.scalar(
        select(func.count()).select_from(WorkItem).where(WorkItem.contract_id == c.id)
    )
    assert cnt == 2  # eine Warn-Arbeit + eine Geräte-Arbeit


def test_reconcile_stale_becomes_inactive(db):
    org = _org(db)
    c = _contract(db, org, "STALE")
    w = _warning(db, org, c, wtype="cancellation_deadline_approaching", requires_review=True, fingerprint="fp-s1")
    eq = add_equipment(db, contract_id=c.id, model="Y", has_evidence=True)
    db.flush()
    _reconcile(db, org, c, [w], [eq], date(2026, 9, 3))
    items_after_first = db.scalars(select(WorkItem).where(WorkItem.contract_id == c.id)).all()
    assert all(i.active for i in items_after_first)
    # Warnung wird nicht mehr abgeleitet (requires_review=False)
    w.requires_review = False
    db.flush()
    _reconcile(db, org, c, [w], [eq], date(2026, 9, 4))
    warning_item = db.scalars(
        select(WorkItem).where(
            (WorkItem.contract_id == c.id)
            & (WorkItem.item_type == "cancellation_deadline")
        )
    ).one()
    assert warning_item.active is False
    eq_item = db.scalars(
        select(WorkItem).where(
            (WorkItem.contract_id == c.id)
            & (WorkItem.item_type == "equipment_coverage_review")
        )
    ).one()
    assert eq_item.active is True


def test_lifecycle_transitions(db):
    org = _org(db)
    c = _contract(db, org, "LC")
    w = _warning(db, org, c, wtype="contract_expired", requires_review=True, fingerprint="fp-lc")
    db.flush()
    _reconcile(db, org, c, [w], [], date(2026, 9, 3))
    item = db.scalars(select(WorkItem).where(WorkItem.contract_id == c.id)).one()
    assert item.status == WorkItemStatus.OPEN.value
    assert item.active is True
    set_work_item_status(db, organization_id=org.id, work_item_id=item.id,
                         status=WorkItemStatus.ACKNOWLEDGED.value)
    db.refresh(item)
    assert item.status == WorkItemStatus.ACKNOWLEDGED.value
    set_work_item_status(db, organization_id=org.id, work_item_id=item.id,
                         status=WorkItemStatus.RESOLVED.value)
    db.refresh(item)
    assert item.status == WorkItemStatus.RESOLVED.value
    assert item.active is False


# ---------------------------------------------------------------------------
# 5) Org-Isolation (Services-Ebene)
# ---------------------------------------------------------------------------

def test_org_isolation_services(db):
    org_a = _org(db)
    org_b = _org(db)
    ca = _contract(db, org_a, "ISO-SA")
    # Org A: Gerät + Arbeit
    add_equipment(db, contract_id=ca.id, serial_number="SN-ISO", has_evidence=True)
    wa = _warning(db, org_a, ca, wtype="missing_cost_data", requires_review=True, fingerprint="fp-iso")
    db.flush()
    eqs_a = db.scalars(select(ContractEquipment).where(ContractEquipment.organization_id == org_a.id)).all()
    _reconcile(db, org_a, ca, db.scalars(
        select(ContractWarning).where(ContractWarning.organization_id == org_a.id)).all(), eqs_a, date(2026, 9, 3))
    # Org B darf es nicht sehen (weder Gerät noch Arbeit noch Warnung).
    assert list_equipment(db, organization_id=org_b.id) == []
    assert list_work_items(db, organization_id=org_b.id, active_only=True) == []
    # Org A sieht es.
    assert len(list_equipment(db, organization_id=org_a.id)) == 1
    assert len(list_work_items(db, organization_id=org_a.id, active_only=True)) == 1


# ---------------------------------------------------------------------------
# 6) API-Routen + Cross-Org-Denial
# ---------------------------------------------------------------------------

def _committed(engine, db, org, contract, *, equipment=True, work=True):
    """Persistiert Equipment/Arbeiten committed (für Lese-APIs)."""
    if equipment:
        add_equipment(db, contract_id=contract.id, serial_number="SN-API", device_name="CT-API", has_evidence=True)
    if work:
        w = _warning(db, org, contract, wtype="contract_expired", requires_review=True, fingerprint="fp-api")
        db.flush()
        eqs = db.scalars(select(ContractEquipment).where(ContractEquipment.contract_id == contract.id)).all()
        _reconcile(db, org, contract, [w], eqs, date(2026, 9, 3))
    db.commit()
    db.close()


def _cleanup_org(engine, org_id):
    """Entfernt committed Test-Daten org-scoped (kein Müll in der Live-DB)."""
    with Session(engine, expire_on_commit=False) as s:
        s.execute(sa_delete(WorkItem).where(WorkItem.organization_id == org_id))
        s.execute(sa_delete(ContractEquipment).where(ContractEquipment.organization_id == org_id))
        s.execute(sa_delete(Equipment).where(Equipment.organization_id == org_id))
        s.execute(sa_delete(ContractWarning).where(ContractWarning.organization_id == org_id))
        s.execute(sa_delete(ContractExtraction).where(ContractExtraction.organization_id == org_id))
        s.execute(sa_delete(DocumentVersion).where(DocumentVersion.organization_id == org_id))
        s.execute(sa_delete(DocumentFile).where(DocumentFile.organization_id == org_id))
        s.execute(sa_delete(Contract).where(Contract.organization_id == org_id))
        s.execute(sa_delete(Organization).where(Organization.id == org_id))
        s.commit()


def test_equipment_routes_ok_and_cross_org_404(engine, db):
    org = _org(db)
    c = _contract(db, org, "EQROUTE")
    _committed(engine, db, org, c)
    org_b = None
    try:
        # Item sauber via neuer Session laden (IDs)
        with Session(engine, expire_on_commit=False) as s:
            equip = s.scalars(select(Equipment).where(Equipment.organization_id == org.id)).one()
            equip_id = equip.id
            chap_slug = org.slug
            org_b = create_organization(s, name="B", slug=f"klinik-b-{uuid.uuid4().hex[:8]}")
            slug_b = org_b.slug
            s.commit()
        client = TestClient(_main.app)
        r = client.get(f"/api/equipment?organization_slug={chap_slug}")
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        r2 = client.get(f"/api/equipment/{equip_id}?organization_slug={chap_slug}")
        assert r2.status_code == 200
        assert len(r2.json()["contracts"]) >= 1
        # Cross-Org: Detail nicht lesbar (404); Liste leer (kein Datenleck).
        assert client.get(f"/api/equipment/{equip_id}?organization_slug={slug_b}").status_code == 404
        rb = client.get(f"/api/equipment?organization_slug={slug_b}")
        assert rb.status_code == 200
        assert rb.json() == []
    finally:
        _cleanup_org(engine, org.id)
        if org_b is not None:
            _cleanup_org(engine, org_b.id)


def test_work_queue_routes_ok_and_cross_org_404(engine, db):
    org = _org(db)
    c = _contract(db, org, "WQROUTE")
    _committed(engine, db, org, c)
    org_b = None
    try:
        with Session(engine, expire_on_commit=False) as s:
            wi = s.scalars(
                select(WorkItem).where(
                    (WorkItem.organization_id == org.id)
                    & (WorkItem.item_type == "contract_expired")
                )
            ).one()
            wi_id = wi.id
            slug = org.slug
            org_b = create_organization(s, name="B2", slug=f"klinik-b2-{uuid.uuid4().hex[:8]}")
            slug_b = org_b.slug
            s.commit()
        client = TestClient(_main.app)
        r = client.get(f"/api/work-queue?organization_slug={slug}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1
        # Status-Transition (PATCH) erlaubt
        rp = client.patch(
            f"/api/work-queue/{wi_id}?organization_slug={slug}",
            json={"status": "acknowledged"},
        )
        assert rp.status_code == 200
        # Cross-Org: Liste leer (kein Datenleck), PATCH verborgen (404).
        rg = client.get(f"/api/work-queue?organization_slug={slug_b}")
        assert rg.status_code == 200
        assert rg.json()["total"] == 0
        rp2 = client.patch(f"/api/work-queue/{wi_id}?organization_slug={slug_b}", json={"status": "resolved"})
        assert rp2.status_code == 404
    finally:
        _cleanup_org(engine, org.id)
        if org_b is not None:
            _cleanup_org(engine, org_b.id)


# ---------------------------------------------------------------------------
# 7) Reprocessing erzeugt keine Duplikate
# ---------------------------------------------------------------------------


def test_equipment_catalog_ignores_superseded_extraction_rows(db):
    """Current equipment links/counts must not include historical reanalysis."""
    from app.database.services import save_extraction

    org = _org(db)
    contract = _contract(db, org, "HISTORY")
    old = add_equipment(
        db, contract_id=contract.id, device_name="CT-Old",
        serial_number="HIST-1", has_evidence=True,
    )
    version = db.scalar(
        select(DocumentVersion).where(
            DocumentVersion.organization_id == org.id
        ).limit(1)
    )
    next_extraction = save_extraction(
        db, organization_id=org.id, document_version_id=version.id,
        snapshot={}, evidence=[], status="success",
        validation_status="unknown", requires_review=False,
        model="test", prompt_version="test",
    )
    contract.accepted_extraction_id = next_extraction.id
    current = add_equipment(
        db, contract_id=contract.id, extraction_id=next_extraction.id,
        device_name="CT-Current", serial_number="HIST-2",
        has_evidence=True,
    )
    db.flush()
    # Historical equipment remains auditable, but not a current link.
    assert db.get(ContractEquipment, old.id) is not None
    assert all(
        item.id != str(old.equipment_id)
        for item in list_equipment(db, organization_id=org.id)
        if item.contract_count > 0
    )
    detail = get_equipment_detail(
        db, organization_id=org.id, equipment_id=old.equipment_id
    )
    assert detail is not None
    assert detail.contract_count == 0
    assert detail.contracts == []
    current_detail = get_equipment_detail(
        db, organization_id=org.id, equipment_id=current.equipment_id
    )
    assert current_detail is not None
    assert current_detail.contract_count == 1
    assert len(current_detail.contracts) == 1
    assert current_detail.contracts[0].contract_id == str(contract.id)


def test_reprocessing_no_duplicate_equipment_or_relationships(db):
    org = _org(db)
    c = _contract(db, org, "REPRO")
    # Simuliert zwei identische Verarbeitungs-Durchläufe für denselben Vertrag.
    e1 = add_equipment(db, contract_id=c.id, serial_number="SN-R", device_name="R", has_evidence=True)
    w = _warning(db, org, c, wtype="cancellation_deadline_approaching", requires_review=True, fingerprint="fp-r")
    db.flush()
    eqs = db.scalars(select(ContractEquipment).where(ContractEquipment.contract_id == c.id)).all()
    _reconcile(db, org, c, [w], eqs, date(2026, 9, 3))
    # Zweiter Durchlauf
    e2 = add_equipment(db, contract_id=c.id, serial_number="SN-R", device_name="R", has_evidence=True)
    _reconcile(db, org, c, [w], eqs, date(2026, 9, 3))
    db.flush()
    assert e1.id == e2.id
    rel_cnt = db.scalar(
        select(func.count()).select_from(ContractEquipment).where(
            (ContractEquipment.contract_id == c.id)
            & (ContractEquipment.organization_id == org.id)
        )
    )
    assert rel_cnt == 1
    master_cnt = db.scalar(
        select(func.count()).select_from(Equipment).where(
            (Equipment.organization_id == org.id) & (Equipment.serial_number == "SN-R")
        )
    )
    assert master_cnt == 1
    work_cnt = db.scalar(
        select(func.count()).select_from(WorkItem).where(WorkItem.contract_id == c.id)
    )
    assert work_cnt == 1  # exakte Seriennr → kein Geräte-Review, nur die Warn-Arbeit, keine Dupes
