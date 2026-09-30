"""Occurrence persistence and work-item lineage regressions (PostgreSQL suite)."""

from datetime import date

from tests.test_pr4_equipment_work_item import _org, _contract
from app.database.services import add_equipment
from app.work_queue.derive import derive_work_items


def test_same_sourced_occurrence_retry_is_idempotent(db):
    org, contract = _org(db), None
    contract = _contract(db, org, "OCC-RETRY")
    values = dict(
        contract_id=contract.id, device_name="Infusion Pump",
        field_ref="identity_equipment.evidence.3", equipment_index=3,
    )
    first = add_equipment(db, **values)
    second = add_equipment(db, **values)
    assert first.id == second.id


def test_two_anonymous_evidence_rows_produce_independent_review_tasks(db):
    org = _org(db)
    contract = _contract(db, org, "OCC-REVIEW")
    rows = [
        add_equipment(
            db, contract_id=contract.id, device_name="Infusion Pump",
            field_ref=f"identity_equipment.evidence.{i}", equipment_index=i,
        ) for i in (0, 1)
    ]
    derived = derive_work_items(
        contract_id=str(contract.id), warnings=[], equipment_rows=rows,
        as_of_date=date(2026, 9, 30), policy_version="test",
    )
    assert len(derived) == 2
    assert len({item["logical_fingerprint"] for item in derived}) == 2


def test_known_unit_coverage_lineage_survives_source_reorder(db):
    org = _org(db)
    contract = _contract(db, org, "OCC-SCOPE")
    def scope_rows(refs):
        return [
            add_equipment(
                db, contract_id=contract.id, device_name="CT Main",
                serial_number="REORDER-1", service_scope=scope,
                field_ref=ref,
            )
            for scope, ref in zip(("Maintenance", "Inspection"), refs)
        ]
    first = scope_rows(("identity_equipment.evidence.0", "identity_equipment.evidence.1"))
    second = scope_rows(("identity_equipment.evidence.1", "identity_equipment.evidence.0"))
    assert [row.id for row in first] == [row.id for row in second]
    assert first[0].occurrence_fingerprint != first[1].occurrence_fingerprint
