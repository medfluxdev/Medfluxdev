"""UAT Round-3 Fix 3: deterministische Read-Layer-Dedupe der Evidence.

- Die DB-Audit-/Extractions-Zeilen werden NIE veraendert/geloescht (nur die
  Read-Antwort wird eindeutig).
- Zwei Zeilen sind nur dann Duplikate, wenn derselbe Fakt (field_ref) an
  derselben Quelle (document_version_id, page, Paragraf-/Tabellen-Index,
  source_type) mit derselben normalisierten Aussage liegt.
- Andere Seite / Quote / Fakt / Quelle bleiben getrennt erhalten.
- Gruppen-Fallback bleibt; feldspezifische Belege haben im Review Vorrang.
- Deterministisch unabhaengig von der DB-Lieferreihenfolge.
"""
from app.contracts.detail.service import _dedupe_evidence
from app.contracts.review.service import _link_fact_evidence


def _ref(**overrides):
    ref = {
        "evidence_id": "evt",
        "field_ref": "services.inspection.evidence.0",
        "document_version_id": "dv1",
        "page": 7,
        "paragraph_index": 0,
        "table_index": None,
        "source_type": "paragraph",
        "snippet": "Sichtprüfung auf äußere Mängel ... Sicherheitstest",
        "confidence": 0.7,
        "requires_review": False,
        "bbox": None,
        "precision": "none",
        "geometry_normalized": True,
        "bbox_space": "pdf_points",
        "supports_exact_navigation": False,
    }
    ref.update(overrides)
    return ref


def test_exact_duplicate_collapses_into_one_row():
    refs = [
        _ref(evidence_id="a"),
        _ref(evidence_id="b"),
        _ref(evidence_id="c", page=7, snippet="Sichtprüfung auf äußere "
                                              "Mängel ... Sicherheitstest"),
    ]
    out = _dedupe_evidence(refs)
    assert len(out) == 1
    assert out[0]["evidence_id"] == "a"
    assert out[0]["page"] == 7


def test_distinct_page_quote_field_and_source_stay():
    base = _ref()
    refs = [
        base,
        _ref(evidence_id="p7x", page=3, snippet="Montag bis Freitag 09:00 bis 17:00"),
        _ref(evidence_id="fx", field_ref="services.repair.evidence.0"),
        _ref(evidence_id="qt", snippet="Ganz andere Leistung"),
        _ref(evidence_id="st", source_type="table"),
    ]
    out = _dedupe_evidence(refs)
    assert len(out) == 5
    assert {r["evidence_id"] for r in out} == {
        "evt", "p7x", "fx", "qt", "st",
    }


def test_duplicate_merges_flags_geometry_and_confidence_deterministically():
    a = _ref(evidence_id="b", confidence=0.6, requires_review=True)
    b = _ref(evidence_id="a", confidence=0.9, requires_review=True,
             bbox={"x0": 0, "y0": 0, "x1": 1, "y1": 1})
    shuffled = [a, b, b, a]
    out1 = _dedupe_evidence(shuffled)
    out2 = _dedupe_evidence(shuffled[::-1])
    assert out1 == out2
    assert len(out1) == 1
    row = out1[0]
    assert row["requires_review"] is True
    assert row["confidence"] == 0.9
    assert row["bbox"] == {"x0": 0, "y0": 0, "x1": 1, "y1": 1}
    assert row["supports_exact_navigation"] is True


def test_recovered_ref_is_preferred_when_same_key():
    refs = [
        _ref(evidence_id="recovered:services.inspection.evidence.0",
             confidence=None, page=7),
        _ref(evidence_id="ext1"),
    ]
    out = _dedupe_evidence(refs)
    assert len(out) == 1
    assert out[0]["evidence_id"] == "recovered:services.inspection.evidence.0"


def test_empty_and_none_safe():
    assert _dedupe_evidence([]) == []
    assert _dedupe_evidence(None) == []


def test_group_fallback_and_field_specific_priority_survive_dedupe():
    # Gruppen-Zeile + feldspezifische Zeile derselben Quelle sind KEINE
    # Duplikate (verschiedene field_ref): beides bleibt, Review bevorzugt
    # den feldspezifischen Beleg und faellt nur ohne diesen auf die Gruppe.
    refs = [
        _ref(evidence_id="grp", field_ref="costs.evidence",
             page=8, snippet="8.000,00 EUR"),
        _ref(evidence_id="fld", field_ref="costs.annual_cost.evidence.0",
             page=8, snippet="8.000,00 EUR"),
        _ref(evidence_id="fld2", field_ref="costs.scheduled_prices.evidence.0",
             page=8, snippet="Jahr 2: 8.000,00 EUR"),
    ]
    out = _dedupe_evidence(refs)
    assert len(out) == 3

    evidence_by_ref: dict[str, list] = {}
    for row in out:
        evidence_by_ref.setdefault(row["field_ref"], []).append(row)

    specific, fallback = _link_fact_evidence("costs.annual", evidence_by_ref)
    assert [r["evidence_id"] for r in specific] == ["fld"]
    assert fallback == []

    specific2, fallback2 = _link_fact_evidence("costs.monthly_recurring", evidence_by_ref)
    assert specific2 == []
    assert [r["evidence_id"] for r in fallback2] == ["grp"]