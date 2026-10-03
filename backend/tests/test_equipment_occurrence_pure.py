"""Fast pure regressions for equipment occurrence and review identity.

No database, migrations, network, model downloads or fixtures are required.
"""
from app.database.services import _equipment_occurrence_fingerprint
from app.work_queue.derive import compute_fingerprint, derive_from_equipment


def occurrence(**overrides):
    values = dict(
        serial_number=None, inventory_number=None, service_scope=None,
        coverage_start=None, coverage_end=None,
        included_services=None, excluded_services=None,
        field_ref="identity_equipment.evidence.0", equipment_index=0,
    )
    values.update(overrides)
    return _equipment_occurrence_fingerprint("semantic-id", **values)


def review(occurrence_id, *, serial=None, included=None, scope=None):
    row = dict(
        relationship_quality="partial", requires_review=True,
        device_name="CT Main", logical_fingerprint="semantic-id",
        occurrence_fingerprint=occurrence_id, serial_number=serial,
        service_scope=scope, included_services=included,
    )
    return compute_fingerprint(derive_from_equipment(row))


def test_anonymous_distinct_sources_are_distinct_and_retries_stable():
    first = occurrence()
    second = occurrence(field_ref="identity_equipment.evidence.1", equipment_index=1)
    assert first == occurrence()
    assert first != second
    assert review(first) != review(second)


def test_known_unit_scoped_occurrence_survives_source_reordering():
    first = occurrence(serial_number="SN-1", service_scope="Maintenance")
    reordered = occurrence(
        serial_number="SN-1", service_scope="Maintenance",
        field_ref="identity_equipment.evidence.9", equipment_index=9,
    )
    independent = occurrence(serial_number="SN-1", service_scope="Inspection")
    assert first == reordered
    assert first != independent
    assert review(first, serial="SN-1", scope="Maintenance") != review(
        independent, serial="SN-1", scope="Inspection"
    )


def test_included_service_variations_have_independent_occurrence_and_review():
    preventive = occurrence(
        serial_number="SN-1", service_scope="Maintenance",
        included_services=["Preventive"],
    )
    emergency = occurrence(
        serial_number="SN-1", service_scope="Maintenance",
        included_services=["Emergency"],
    )
    assert preventive != emergency
    assert review(preventive, serial="SN-1", scope="Maintenance", included=["Preventive"]) != review(
        emergency, serial="SN-1", scope="Maintenance", included=["Emergency"]
    )



def test_known_identifier_without_scope_survives_evidence_reordering():
    first = occurrence(serial_number="SN-1")
    reordered = occurrence(
        serial_number="SN-1",
        field_ref="identity_equipment.evidence.10", equipment_index=10,
    )
    assert first == reordered
    assert review(first, serial="SN-1") == review(reordered, serial="SN-1")
