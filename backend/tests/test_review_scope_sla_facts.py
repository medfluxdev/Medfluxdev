"""SLA-Werte und Leistungsumfang als eigene Angaben der Faktprüfung."""

from app.contracts.review.material import (
    CRITICAL_FACTS,
    MATERIAL_FACT_KEYS,
    fact_label,
    material_report,
)
from app.reextract.facts import review_facts_for


def _data(**kwargs):
    return {"scope": {}, "sla": {}, **kwargs}


def test_sla_values_are_review_facts():
    report = material_report(_data(sla={"response_time": "4 Stunden", "availability_24_7": True}))
    assert report["sla.response_time"] == {"present": True, "value": "4 Stunden", "critical": True}
    assert report["sla.resolution_time"]["present"] is False
    assert report["sla.emergency_availability"]["value"] == "24/7 erreichbar"
    assert report["sla.service_hours"]["critical"] is False
    assert fact_label("sla.response_time") == "Reaktionszeit (SLA)"


def test_scope_items_are_review_facts():
    scope = {
        "scope_status": {
            "maintenance": {"status": "included"},
            "repair": {"status": "excluded"},
            "calibration": {"status": "mentioned"},
            "inspection": {"status": "not_established"},
        },
        "maintenance": True,
    }
    report = material_report(_data(scope=scope))
    assert report["scope.maintenance"]["value"] == "Inklusive"
    assert report["scope.repair"]["value"] == "Exklusive"
    assert report["scope.calibration"]["present"] is True
    assert report["scope.inspection"]["present"] is False
    assert not any(key.startswith("scope.") for key in CRITICAL_FACTS)


def test_scope_falls_back_to_booleans_without_status():
    report = material_report(_data(scope={"repair": False}))
    assert report["scope.repair"]["value"] == "Exklusive"


def test_coverage_summary_is_replaced():
    assert "services.coverage" not in MATERIAL_FACT_KEYS


def test_reextraction_reopens_the_matching_facts():
    assert review_facts_for(["sla.response_time"]) == ["sla.response_time"]
    assert review_facts_for(["services.repair"]) == ["scope.repair"]
    assert "scope.maintenance" in review_facts_for(["services.included_services"])


def test_ai_yes_no_is_a_suggestion_when_the_text_is_unclear():
    scope = {"scope_status": {
        "repair": {"status": "mentioned", "ai_suggestion": True},
        "calibration": {"status": "not_established", "ai_suggestion": False},
        "maintenance": {"status": "excluded", "ai_suggestion": True},
    }}
    report = material_report(_data(scope=scope))
    assert report["scope.repair"]["value"] == "Inklusive"
    assert report["scope.calibration"]["value"] == "Exklusive"
    # Ein Beleg im Text geht dem KI-Vorschlag vor.
    assert report["scope.maintenance"]["value"] == "Exklusive"


def test_further_services_and_sla_notes_are_review_facts():
    data = _data(
        scope={"included_services": ["Schulung", " ", "Hotline"], "excluded_services": []},
        sla={"sla_notes": "Ersatzgerät binnen 48 Stunden"},
    )
    report = material_report(data)
    assert report["scope.other_included"]["value"] == "Schulung; Hotline"
    assert report["scope.other_excluded"]["present"] is False
    assert report["sla.sla_notes"]["value"] == "Ersatzgerät binnen 48 Stunden"
    assert review_facts_for(["sla.sla_notes"]) == ["sla.sla_notes"]
    assert "scope.other_included" in review_facts_for(["services.included_services"])


# --------------------------------------------------------------------------- Verknüpfung Faktprüfung ↔ Hinweise/Status

from app.contracts.review import service as review_service


def _state(key, state, present=True):
    return {"fact_key": key, "state": state, "present": present}


def test_review_warning_resolves_once_its_fact_is_reviewed():
    data = {
        "warnings": [
            {"title_de": "Berechnungskonflikt", "requires_review": True, "source_refs": ["dates.end_date"], "target_kind": "contract_end"},
            {"title_de": "Kündigungstermin", "requires_review": True, "source_refs": [], "target_kind": "cancellation_deadline"},
        ],
        "review": {"requires_manual_review": True, "review_reasons": ["x"]},
    }
    states = [_state("dates.end_date", "confirmed"), _state("dates.latest_cancellation", "unreviewed")]
    review_service.resolve_review_warnings(data, states, "in_review")
    assert data["warnings"][0]["requires_review"] is False and data["warnings"][0]["review_resolved"] is True
    assert data["warnings"][1]["requires_review"] is True
    assert data["review"] == {"requires_manual_review": True, "review_reasons": ["Kündigungstermin"]}


def test_warning_without_fact_resolves_only_with_completed_review():
    def run(status, states):
        data = {"warnings": [{"title_de": "Unklar", "requires_review": True, "source_refs": ["contract.dates"], "target_kind": "data_quality"}], "review": {}}
        review_service.resolve_review_warnings(data, states, status)
        return data["warnings"][0]["requires_review"]

    assert run("reviewed", [_state("identity.supplier", "confirmed")]) is False
    assert run("changed_after_review", [_state("identity.supplier", "confirmed")]) is True
    assert run("reviewed", [_state("identity.supplier", "unreviewed")]) is True


def test_last_reviewed_fact_completes_the_contract_review(monkeypatch):
    calls = []
    monkeypatch.setattr(review_service, "get_contract_review", lambda session, **kw: type("R", (), {"status": "changed_after_review"})())
    monkeypatch.setattr(review_service, "complete_review", lambda session, **kw: calls.append(kw))

    def states(items):
        monkeypatch.setattr(review_service, "build_fact_review_states", lambda session, **kw: [
            {**_state(key, value), "is_critical": key.startswith("identity")} for key, value in items
        ])

    states([("identity.supplier", "confirmed"), ("costs.annual", "unreviewed")])
    assert review_service.complete_if_all_reviewed(None, organization_id=1, contract_id=2, data={}, reviewer_display_name="A") is False
    states([("identity.supplier", "confirmed"), ("costs.annual", "corrected")])
    assert review_service.complete_if_all_reviewed(None, organization_id=1, contract_id=2, data={}, reviewer_display_name="A") is True
    assert calls[0]["note"] == review_service.AUTO_COMPLETE_NOTE


def test_every_evidence_belongs_to_one_review_item_with_confidence(monkeypatch):
    monkeypatch.setattr(review_service, "_latest_fact_reviews", lambda session, contract_id: {})
    monkeypatch.setattr(review_service, "auto_accept_allowed", lambda session, organization_id, contract_id: False)
    data = {
        "identity": {"contract_number": "4711"},
        "scope": {}, "sla": {},
        "evidence": [
            {"field_ref": "identity.contract_number.evidence.0", "evidence_id": "e1", "page": 1, "snippet": "Nr. 4711", "confidence": 0.95},
            {"field_ref": "identity.contract_number.evidence.1", "evidence_id": "e2", "page": 2, "snippet": "4711", "confidence": 0.7},
            {"field_ref": "costs.cost_line.0", "evidence_id": "e3", "page": 3, "snippet": "Wartung  1.200 EUR", "confidence": 0.82},
            {"field_ref": "costs.cost_line.0", "evidence_id": "e4", "page": 3, "snippet": "pauschal"},
            {"field_ref": "payment.payment_start", "evidence_id": "e5", "page": 4, "snippet": "ab Abnahme"},
            {"field_ref": "costs.discounts.0", "evidence_id": "e6", "page": 5, "snippet": "3 % Rabatt", "extraction_method": "programmatic"},
        ],
    }
    states = {s["fact_key"]: s for s in review_service.build_fact_review_states(None, organization_id=None, contract_id=None, data=data)}
    assert states["identity.contract_number"]["evidence_count"] == 2
    assert states["identity.contract_number"]["ai_confidence"] == 0.95
    line = states["evidence.costs.cost_line.0"]
    assert line["is_evidence_item"] and line["label_de"] == "Nachweis: Kostenposition 1"
    assert line["original_value"] == "Wartung 1.200 EUR" and line["evidence_count"] == 2 and line["ai_confidence"] == 0.82
    assert states["evidence.payment.payment_start"]["ai_confidence"] is None
    # Ohne Prozent, aber ehrlich begruendet: von festen Regeln woertlich gefunden.
    assert states["evidence.costs.discounts.0"]["ai_confidence"] is None and states["evidence.costs.discounts.0"]["found_by_rule"]
    assert not states["evidence.payment.payment_start"]["found_by_rule"] and not line["found_by_rule"]
    linked = sum(s["evidence_count"] for s in states.values() if s["present"])
    assert linked == len(data["evidence"])


def test_evidence_items_accept_only_safe_keys():
    assert review_service._valid_evidence_key("evidence.costs.cost_line.0")
    assert not review_service._valid_evidence_key("evidence.")
    assert not review_service._valid_evidence_key("evidence.costs; drop")
    assert not review_service._valid_evidence_key("costs.annual")


# --------------------------------------------------------------------------- Widerspruch verständlich + klärbar

def _conflict_data(fact_state="unreviewed"):
    return {
        "dates": {"calculated_end_basis": {"inputs": {
            "end_date": "2029-03-31", "derived_end_date": "2029-05-05", "start_date": "2025-05-05", "duration": "4 years",
        }}},
        "warnings": [{
            "warning_type": "calculation_conflict", "severity": "high", "title_de": "Berechnungskonflikt",
            "requires_review": True, "source_refs": ["dates.end_date"], "target_kind": "contract_end",
        }],
        "risk": {"computed": "high", "effective": "high", "override": None, "confirmed": None},
        "risk_level": "high",
        "review": {},
    }, [{**_state("dates.end_date", fact_state), "effective_value": "2029-03-31", "reviewer_display_name": "Ahmad"}]


def test_end_date_conflict_names_both_values_and_their_origin():
    data, states = _conflict_data()
    review_service.resolve_review_warnings(data, states, "in_review")
    conflict = data["warnings"][0]["conflict"]
    assert conflict["question_de"] == "Welches Vertragsende gilt?"
    assert "31.03.2029" in conflict["explanation_de"] and "05.05.2029" in conflict["explanation_de"] and "35 Tage" in conflict["explanation_de"]
    assert [(o["key"], o["value"]) for o in conflict["options"]] == [("document", "2029-03-31"), ("calculated", "2029-05-05")]
    assert conflict["options"][1]["detail_de"] == "05.05.2025 + 4 Jahre"
    assert data["warnings"][0]["requires_review"] is True
    assert data["risk"]["computed"] == "high"


def test_decided_conflict_no_longer_drives_the_risk():
    data, states = _conflict_data("corrected")
    review_service.resolve_review_warnings(data, states, "reviewed")
    assert data["warnings"][0]["review_resolved"] is True
    assert data["warnings"][0]["conflict"]["decided_by"] == "Ahmad"
    assert data["risk"]["computed"] == "unknown" and data["risk"]["effective"] == "unknown" and data["risk_level"] == "unknown"


def test_risk_override_stays_after_a_decision():
    data, states = _conflict_data("confirmed")
    data["risk"]["override"] = {"level": "high"}
    review_service.resolve_review_warnings(data, states, "reviewed")
    assert data["risk"]["computed"] == "unknown" and data["risk"]["effective"] == "high"
