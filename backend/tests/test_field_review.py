"""Feldprüfung: ein Feld → Kandidaten → Nachweise; eine Prüfung für Karte und geführten Ablauf.

Teil 1: reine Logik (Normalisierung, Kandidaten, Stände, Zähler, Weitere Informationen).
Teil 2: API gegen PostgreSQL (entscheiden, Nachweise wählen/ausschließen, Weitere Informationen, Protokoll).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.contracts.review import field_review as fr
from app.contracts.review import service as review_service
from app.contracts.review.events import ReviewEvents
from app.contracts.review.field_actions import plan_decision, plan_evidence, plan_finding
from app.contracts.review.service import ReviewConflict, ReviewError


# =========================================================================
# Teil 1 – reine Logik
# =========================================================================


def test_normalize_groups_equivalent_spellings_but_not_different_meanings():
    assert fr.normalize("31.03.2029") == fr.normalize("2029-03-31") == fr.normalize("2029-03-31T00:00:00")
    assert fr.normalize("12,0 Monate") == fr.normalize("12 Monate")
    assert fr.normalize("1.200,50 EUR") == fr.normalize("1200.50 EUR")
    assert fr.normalize("Ja") == fr.normalize(True) == fr.normalize("true")
    assert fr.normalize("  Abiomed  GmbH. ") == fr.normalize("abiomed gmbh")
    # Andere Bedeutung bleibt getrennt: Einheiten werden nie umgerechnet.
    assert fr.normalize("12 Monate") != fr.normalize("1 Jahr")
    assert fr.normalize("31.03.2029") != fr.normalize("31.03.2028")


def _data(**overrides):
    base = {
        "identity": {"supplier": "Abiomed GmbH", "contract_number": "4711"},
        "dates": {"documented_end_date": "2029-03-31", "start_date": "2025-04-01"},
        "costs": {"monthly_recurring": {"amount": "1200", "currency": "EUR"}, "tax_breakdown": {"rate_percent": 19.0, "monthly_net": "1200"}},
        "extracted_terms": {"termination.cancellation_period": "6 Monate"},
        "scope": {}, "sla": {},
        "documents": [{"document_version_id": "doc-1", "role": "main", "original_filename": "v.pdf"}],
        "warnings": [],
        "fact_reviews": [],
        "evidence": [
            {"field_ref": "dates.end_date.evidence.0", "evidence_id": "e1", "page": 3, "snippet": "Der Vertrag endet am 31.03.2029.",
             "document_version_id": "doc-1", "location": "exact", "text_verified": True, "confidence": 0.93},
            {"field_ref": "dates.end_date.evidence.1", "evidence_id": "e2", "page": 9, "snippet": "Laufzeit bis 31.03.2029",
             "document_version_id": "doc-1", "location": "page", "confidence": 0.8},
            {"field_ref": "identity.supplier", "evidence_id": "e3", "page": 1, "snippet": "Abiomed GmbH",
             "document_version_id": "doc-1", "location": "exact", "text_verified": True},
            {"field_ref": "costs.discounts.0", "evidence_id": "e9", "page": 5, "snippet": "3 % Skonto bei Zahlung in 10 Tagen",
             "document_version_id": "doc-1", "location": "exact", "text_verified": True},
            {"field_ref": "identity.service_email", "evidence_id": "e10", "page": 1, "snippet": "service@abiomed.example",
             "document_version_id": "doc-1", "location": "exact"},
        ],
    }
    base.update(overrides)
    return base


def _model(monkeypatch, data, *, latest=None, events=None, proposals=()):
    monkeypatch.setattr(review_service, "_latest_fact_reviews", lambda session, contract_id: latest or {})
    monkeypatch.setattr(review_service, "auto_accept_allowed", lambda *a, **k: False)
    events = events or ReviewEvents()
    monkeypatch.setattr(review_service, "load_events", lambda session, contract_id: events)
    monkeypatch.setattr(fr, "_open_proposals", lambda session, contract_id: list(proposals))
    states = review_service.build_fact_review_states(None, organization_id=None, contract_id=None, data=data)
    return states, fr.build_field_review(None, contract_id=None, data=data, states=states, events=events)


def _field(model, key):
    return next(f for f in model["fields"] if f["fact_key"] == key)


def test_two_agreeing_evidence_are_one_candidate_with_support_and_one_decision(monkeypatch):
    _, model = _model(monkeypatch, _data())
    end = _field(model, "dates.end_date")
    assert len(end["candidates"]) == 1
    assert end["candidates"][0]["support_count"] == 2 and end["candidates"][0]["evidence_ids"] == ["e1", "e2"]
    assert end["status"] == "open" and end["decision_needed"]
    # Der erste belegte Fund mit genauer Fundstelle ist der Hauptnachweis; „Nur Seite“ gilt nicht als bestätigt.
    assert end["primary_evidence_id"] == "e1" and end["source_state"] == "verified"
    second = next(e for e in end["evidence"] if e["evidence_id"] == "e2")
    assert second["source_state"] == "located" and not second["primary"]
    # Ein Feld, eine Entscheidung: die Bestätigung deckt beide Belege.
    plan = plan_decision(end, "keep")
    assert plan.fact_action == "confirmed" and not plan.changes_value


def test_conflicting_end_dates_are_one_field_with_competing_candidates(monkeypatch):
    warning = {
        "warning_type": "calculation_conflict", "target_kind": "contract_end", "requires_review": True, "source_refs": ["dates.end_date"],
        "title_de": "Berechnungskonflikt",
    }
    data = _data(
        warnings=[warning],
        dates={"documented_end_date": "2029-03-31", "start_date": "2025-04-01",
               "calculated_end_basis": {"inputs": {"end_date": "2029-03-31", "derived_end_date": "2028-03-31", "start_date": "2025-04-01", "duration": "36 months"}}},
    )
    review_service.resolve_review_warnings(data, [], "unreviewed")  # setzt warning["conflict"]
    _, model = _model(monkeypatch, data)
    end = _field(model, "dates.end_date")
    shown = {c["display"]: c for c in end["candidates"]}
    assert set(shown) == {"31.03.2029", "31.03.2028"}
    assert end["status"] == "conflict" and end["decision_needed"]
    # Das Datum aus dem Dokument trägt die Belege, das berechnete nicht (Berechnung ≠ Beleg).
    assert shown["31.03.2029"]["evidence_ids"] == ["e1", "e2"] and shown["31.03.2028"]["evidence_ids"] == []
    # Ein anderer Kandidat ändert den Wert – das muss ausdrücklich bestätigt werden.
    other = shown["31.03.2028"]
    with pytest.raises(ReviewError, match="ausdrücklich bestätigen"):
        plan_decision(end, "accept", candidate_key=other["key"])
    plan = plan_decision(end, "accept", candidate_key=other["key"], confirm_change=True)
    assert plan.fact_action == "corrected" and plan.changes_value and plan.chosen == "31.03.2028"
    assert [a["display"] for a in plan.alternatives] == ["31.03.2029"]  # verworfene Alternative bleibt festgehalten


def test_different_meanings_are_never_merged(monkeypatch):
    """Vertragsende und Gewährleistungsende sind verschiedene Dinge: ein Zitat zu etwas anderem wird kein Kandidat."""
    data = _data()
    data["evidence"].append({"field_ref": "dates.warranty_end.evidence.0", "evidence_id": "e20", "page": 4, "snippet": "Gewährleistung bis 31.03.2031",
                             "document_version_id": "doc-1", "location": "exact"})
    states, model = _model(monkeypatch, data)
    end = _field(model, "dates.end_date")
    assert [c["display"] for c in end["candidates"]] == ["31.03.2029"]
    assert any(f["finding_key"] == "evidence.dates.warranty_end" for f in model["findings"])


def test_excluding_one_evidence_keeps_the_other_and_the_value(monkeypatch):
    from datetime import datetime, timezone
    from app.contracts.review.events import Exclusion

    events = ReviewEvents(excluded={"e1": Exclusion("wrong_place", "falsche Seite", "A. Prüfer", datetime.now(timezone.utc))})
    states, model = _model(monkeypatch, _data(), events=events)
    end = _field(model, "dates.end_date")
    by_id = {e["evidence_id"]: e for e in end["evidence"]}
    assert by_id["e1"]["excluded"] and by_id["e1"]["exclusion_reason_label"] == "Falsche Stelle im Dokument"
    assert not by_id["e2"]["excluded"] and by_id["e2"]["primary"]  # Hauptnachweis rückt nach; e1 bleibt erhalten
    assert end["active_evidence_count"] == 1
    # Der Wert und der Prüfstand des Felds ändern sich durch den Ausschluss nicht.
    assert end["current"] == "31.03.2029" and end["status"] == "open"
    assert end["candidates"][0]["support_count"] == 1


def test_excluding_all_evidence_does_not_reject_the_field(monkeypatch):
    from datetime import datetime, timezone
    from app.contracts.review.events import Exclusion

    now = datetime.now(timezone.utc)
    events = ReviewEvents(excluded={i: Exclusion("outdated", None, "A", now) for i in ("e1", "e2")})
    _, model = _model(monkeypatch, _data(), events=events)
    end = _field(model, "dates.end_date")
    assert end["present"] and end["current"] == "31.03.2029"
    assert end["primary_evidence_id"] is None and end["source_state"] == "unresolved"


def test_selecting_primary_evidence_does_not_exclude_others(monkeypatch):
    events = ReviewEvents(primary={"dates.end_date": "e2"})
    _, model = _model(monkeypatch, _data(), events=events)
    end = _field(model, "dates.end_date")
    assert end["primary_evidence_id"] == "e2" and not any(e["excluded"] for e in end["evidence"])
    kind, extra, _ = plan_evidence(end, "e1", "primary", None, None)
    assert kind == "primary_selected" and extra == {}
    with pytest.raises(ReviewError, match="Grund"):
        plan_evidence(end, "e1", "exclude", None, None)
    with pytest.raises(ReviewError, match="beschreiben"):
        plan_evidence(end, "e1", "exclude", "other", "")
    kind, extra, _ = plan_evidence(end, "e1", "exclude", "outdated", None)
    assert kind == "evidence_excluded" and extra["reason"] == "outdated"


def test_missing_essential_field_is_explicit_and_blocks_only_when_essential(monkeypatch):
    _, model = _model(monkeypatch, _data())
    renewal = _field(model, "termination.renewal_period")  # wesentlich, nicht gefunden
    assert renewal["status"] == "missing" and renewal["decision_needed"] and not renewal["present"]
    assert "nicht gefunden" in renewal["reason"]
    notes = _field(model, "sla.sla_notes")  # optional, nicht gefunden: still
    assert notes["status"] == "missing" and not notes["decision_needed"]
    essential = model["stages"][0]
    assert essential["missing"] >= 1 and not model["essential_complete"]
    # „Nicht im Dokument“ festhalten ist eine ausdrückliche Entscheidung (kein erfundener Wert).
    plan = plan_decision(renewal, "not_in_document")
    assert plan.event_kind == "not_in_document" and plan.fact_action is None
    events = ReviewEvents(absent={"termination.renewal_period": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)})
    _, again = _model(monkeypatch, _data(), events=events)
    assert _field(again, "termination.renewal_period")["status"] == "absent"
    assert not _field(again, "termination.renewal_period")["decision_needed"]


def test_unavailable_source_is_never_shown_as_verified(monkeypatch):
    data = _data(documents=[])  # Dokument nicht verfügbar
    _, model = _model(monkeypatch, data)
    end = _field(model, "dates.end_date")
    assert end["source_state"] == "unavailable" and end["source_state_label"] == "Dokument nicht verfügbar"
    assert not any(e["source_state"] == "verified" for e in end["evidence"])


def test_additional_findings_are_kept_but_do_not_count_or_block(monkeypatch):
    states, model = _model(monkeypatch, _data())
    keys = {f["finding_key"] for f in model["findings"]}
    assert {"evidence.costs.discounts.0", "evidence.identity.service_email"} <= keys
    # Weder Zähler noch Prüfstand der Felder enthalten sie.
    assert all(not f["fact_key"].startswith("evidence.") for f in model["fields"])
    summary = review_service.build_review_summary(states)
    assert summary["relevant_count"] == len([f for f in model["fields"] if f["kind"] == "extracted" and f["present"]])
    discount = next(f for f in model["findings"] if f["finding_key"] == "evidence.costs.discounts.0")
    assert discount["consequential"] and discount["decision"] is None
    assert next(f for f in model["findings"] if f["finding_key"] == "evidence.identity.service_email")["contact"]
    assert model["findings_open"] == len(model["findings"])


def test_finding_decisions_link_note_dismiss(monkeypatch):
    _, model = _model(monkeypatch, _data())
    finding = next(f for f in model["findings"] if f["finding_key"] == "evidence.costs.discounts.0")
    kind, extra, _ = plan_finding(finding, model["fields"], "link", "costs.price_indexation", None)
    assert kind == "finding_linked" and extra["target_fact_key"] == "costs.price_indexation"
    with pytest.raises(ReviewError, match="Feld"):
        plan_finding(finding, model["fields"], "link", "dates.latest_cancellation", None)  # berechnet: kein Ziel
    assert plan_finding(finding, model["fields"], "dismiss", None, None)[0] == "finding_dismissed"
    assert plan_finding(finding, model["fields"], "note", None, "merken")[0] == "finding_note"


def test_linked_finding_becomes_a_candidate_of_the_target_field(monkeypatch):
    from types import SimpleNamespace
    from datetime import datetime, timezone

    event = SimpleNamespace(kind="finding_linked", payload={"target_fact_key": "costs.price_indexation"}, note=None,
                            actor_name="A", created_at=datetime.now(timezone.utc))
    events = ReviewEvents(findings={"evidence.costs.discounts.0": event})
    _, model = _model(monkeypatch, _data(), events=events)
    target = _field(model, "costs.price_indexation")
    assert [c["display"] for c in target["candidates"]] == ["3 % Skonto bei Zahlung in 10 Tagen"]
    assert target["candidates"][0]["sources"][0]["source"] == "finding"
    # Zugeordnet ist erledigt: kein offener Fund mehr.
    assert next(f for f in model["findings"] if f["finding_key"] == "evidence.costs.discounts.0")["decision"] == "linked"


def test_calculated_values_follow_their_inputs_and_are_not_counted(monkeypatch):
    from types import SimpleNamespace
    from datetime import datetime, timezone

    data = _data(dates={"documented_end_date": "2029-03-31", "start_date": "2025-04-01", "latest_cancellation_date": "2028-09-30"})
    now = datetime.now(timezone.utc)

    def row(key):
        return SimpleNamespace(action="confirmed", original_value={"value": "x"}, new_effective_value={"value": "x"}, created_at=now, reviewer_display_name="A",
                               reviewer_identity_type="manual_unverified", evidence_ref=None, note=None)

    open_states, open_model = _model(monkeypatch, data)
    waiting = _field(open_model, "dates.latest_cancellation")
    assert waiting["kind"] == "calculated" and waiting["status"] == "waiting" and not waiting["decision_needed"]

    latest = {k: row(k) for k in ("dates.end_date", "termination.cancellation_period", "termination.auto_renewal")}
    states, model = _model(monkeypatch, data, latest=latest)
    done = _field(model, "dates.latest_cancellation")
    assert done["status"] == "derived" and done["status_label"] == "Berechnet" and not done["decision_needed"]
    assert next(s for s in states if s["fact_key"] == "dates.latest_cancellation")["state"] == "derived"
    # Berechnete Werte zählen weder als Angabe noch blockieren sie; ihre Eingaben sind erkennbar.
    summary = review_service.build_review_summary(states)
    assert "dates.latest_cancellation" not in [s["fact_key"] for s in states if review_service._counts_as_field(s)]
    assert any(i["fact_key"] == "dates.end_date" and i["decided"] for i in done["inputs"])
    with pytest.raises(ReviewError, match="Berechnete"):
        plan_decision(done, "keep")
    assert summary["reviewed_count"] <= summary["relevant_count"]


def test_confirmed_field_is_not_asked_again_without_a_meaningful_change(monkeypatch):
    from types import SimpleNamespace
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    confirmed = SimpleNamespace(action="confirmed", original_value={"value": "31.03.2029"}, new_effective_value={"value": "31.03.2029"}, created_at=now,
                                reviewer_display_name="A", reviewer_identity_type="manual_unverified", evidence_ref=None, note=None)
    # Neu laden, andere Schreibweise, höhere KI-Sicherheit, neueres Datum der Dokumentversion: nichts davon öffnet erneut.
    _, model = _model(monkeypatch, _data(), latest={"dates.end_date": confirmed})
    assert _field(model, "dates.end_date")["status"] == "decided" and not _field(model, "dates.end_date")["decision_needed"]
    spelled = _data(dates={"documented_end_date": "2029-03-31T00:00:00", "start_date": "2025-04-01"})
    _, model = _model(monkeypatch, spelled, latest={"dates.end_date": confirmed})
    assert _field(model, "dates.end_date")["status"] == "decided"
    # Meaningful change: der Wert im Dokument ist ein anderer.
    changed = _data(dates={"documented_end_date": "2030-03-31", "start_date": "2025-04-01"})
    _, model = _model(monkeypatch, changed, latest={"dates.end_date": confirmed})
    end = _field(model, "dates.end_date")
    assert end["status"] == "changed" and end["decision_needed"] and "geändert" in end["reason"]


def test_new_analysis_proposal_reopens_a_confirmed_field_only_when_it_differs(monkeypatch):
    from types import SimpleNamespace
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    confirmed = SimpleNamespace(action="confirmed", original_value={"value": "31.03.2029"}, new_effective_value={"value": "31.03.2029"}, created_at=now,
                                reviewer_display_name="A", reviewer_identity_type="manual_unverified", evidence_ref=None, note=None)

    def proposal(display):
        return (SimpleNamespace(id="p1", field_key="dates.end_date", new_display=display, new_value=display, new_evidence=[], confidence=0.9),
                SimpleNamespace(number=2))

    _, same = _model(monkeypatch, _data(), latest={"dates.end_date": confirmed}, proposals=[proposal("31.03.2029")])
    assert _field(same, "dates.end_date")["status"] == "decided"
    _, differing = _model(monkeypatch, _data(), latest={"dates.end_date": confirmed}, proposals=[proposal("30.06.2029")])
    end = _field(differing, "dates.end_date")
    assert end["status"] == "changed"
    analysis = next(c for c in end["candidates"] if c["display"] == "30.06.2029")
    assert analysis["proposal_id"] == "p1" and analysis["run_number"] == 2
    with pytest.raises(ReviewError, match="Analyse"):
        plan_decision(end, "accept", candidate_key=analysis["key"], confirm_change=True)


def test_deferred_field_stays_open_until_decided(monkeypatch):
    from datetime import datetime, timezone

    events = ReviewEvents(deferred={"dates.end_date": datetime.now(timezone.utc)})
    _, model = _model(monkeypatch, _data(), events=events)
    end = _field(model, "dates.end_date")
    assert end["status"] == "deferred" and end["decision_needed"]


def test_tiers_follow_meaning_and_contract_type(monkeypatch):
    _, model = _model(monkeypatch, _data(sections=None))
    assert _field(model, "identity.supplier")["tier"] == "essential"
    assert _field(model, "sla.response_time")["tier"] == "important"
    assert _field(model, "sla.sla_notes")["tier"] == "optional"
    _, maintenance = _model(monkeypatch, _data(sections={"sla": True, "maintenance": True, "scope": True, "equipment": True}))
    assert _field(maintenance, "sla.response_time")["tier"] == "essential"
    assert _field(maintenance, "sla.response_time")["why"]


def test_counters_count_fields_not_evidence(monkeypatch):
    states, model = _model(monkeypatch, _data())
    summary = review_service.build_review_summary(states)
    evidence_total = len(_data()["evidence"])
    assert summary["relevant_count"] < evidence_total + 10
    assert all(not s["is_evidence_item"] for s in states if review_service._counts_as_field(s))
    stage_total = sum(s["total"] for s in model["stages"])
    assert stage_total >= summary["relevant_count"]  # + fehlende wesentliche Angaben


def test_version_check_blocks_stale_decisions(monkeypatch):
    from app.contracts.review.field_actions import check_version

    _, model = _model(monkeypatch, _data())
    end = _field(model, "dates.end_date")
    check_version(end, end["version"])  # gleich: ok
    check_version(end, None)  # Feld unberührt beim Laden und jetzt noch unberührt: ok
    with pytest.raises(ReviewConflict):
        check_version(end, "2020-01-01T00:00:00+00:00")


# =========================================================================
# Teil 2 – API (PostgreSQL)
# =========================================================================

from tests.test_customer_demo_readiness import (  # noqa: E402
    _build_committed_chain, _temp_env, engine, import_app, _require_pg,  # noqa: F401
)


def _post(client, org, cid, path, body):
    return client.post(f"/api/contracts/{cid}/field-review/{path}?organization_slug={org}", json={"reviewer_display_name": "M. Kraft", **body})


def test_card_and_guided_review_produce_the_same_state(engine):
    d, _storage, svc = _temp_env()
    try:
        org, cid, _ = _build_committed_chain(engine, svc)
        client = TestClient(import_app())
        # Karte: bestätigen über die Faktprüfung.
        r1 = client.post(f"/api/contracts/{cid}/fact-reviews?organization_slug={org}",
                         json={"fact_key": "identity.supplier", "action": "confirmed", "reviewer_display_name": "M. Kraft"})
        assert r1.status_code == 200, r1.text
        # Geführte Prüfung: Wert behalten (derselbe Weg).
        detail = client.get(f"/api/contracts/{cid}?organization_slug={org}").json()
        number = next(f for f in detail["field_review"]["fields"] if f["fact_key"] == "identity.contract_number")
        r2 = _post(client, org, cid, "decide", {"fact_key": "identity.contract_number", "decision": "keep", "expected_version": number["version"]})
        assert r2.status_code == 200, r2.text
        fields = {f["fact_key"]: f for f in r2.json()["field_review"]["fields"]}
        assert fields["identity.supplier"]["fact_state"] == "confirmed" == fields["identity.contract_number"]["fact_state"]
        assert fields["identity.supplier"]["status"] == "decided" == fields["identity.contract_number"]["status"]
        assert {s["fact_key"]: s["state"] for s in r2.json()["fact_review_states"]}["identity.contract_number"] == "confirmed"
    finally:
        d.cleanup()


def test_choice_between_candidates_is_explicit_and_persisted_with_alternatives(engine):
    d, _storage, svc = _temp_env()
    try:
        org, cid, _ = _build_committed_chain(engine, svc)
        client = TestClient(import_app())
        detail = client.get(f"/api/contracts/{cid}?organization_slug={org}").json()
        net = next(f for f in detail["field_review"]["fields"] if f["fact_key"] == "costs.monthly_net")
        # Von Hand: anderer Wert -> korrigiert, Alternative (Wert aus dem Dokument) bleibt im Protokoll.
        r = _post(client, org, cid, "decide", {"fact_key": "costs.monthly_net", "decision": "manual", "value": "1250.00", "note": "Nachtrag 2", "expected_version": net["version"]})
        assert r.status_code == 200, r.text
        field = next(f for f in r.json()["field_review"]["fields"] if f["fact_key"] == "costs.monthly_net")
        assert field["fact_state"] == "corrected" and field["status"] == "decided" and field["current"] == "1250.00"
        entry = next(h for h in field["history"] if h["kind"] == "decision")
        assert entry["by"] == "M. Kraft" and [a["display"] for a in entry["alternatives"]] == ["1200.00"]
        # Gleichzeitige Änderung: veralteter Stand -> 409, nichts wird überschrieben.
        stale = _post(client, org, cid, "decide", {"fact_key": "costs.monthly_net", "decision": "keep", "expected_version": net["version"]})
        assert stale.status_code == 409
    finally:
        d.cleanup()


def test_evidence_exclusion_and_primary_are_logged_and_leave_the_value_alone(engine):
    d, _storage, svc = _temp_env()
    try:
        org, cid, _ = _build_committed_chain(engine, svc)
        client = TestClient(import_app())
        detail = client.get(f"/api/contracts/{cid}?organization_slug={org}").json()
        field = next(f for f in detail["field_review"]["fields"] if f["fact_key"] == "costs.monthly_net")
        evidence_id = field["evidence"][0]["evidence_id"]
        bad = _post(client, org, cid, "evidence", {"fact_key": "costs.monthly_net", "evidence_id": evidence_id, "action": "exclude", "expected_version": field["version"]})
        assert bad.status_code == 422  # ohne Grund
        ok = _post(client, org, cid, "evidence", {"fact_key": "costs.monthly_net", "evidence_id": evidence_id, "action": "exclude", "reason": "wrong_place", "expected_version": field["version"]})
        assert ok.status_code == 200, ok.text
        after = next(f for f in ok.json()["field_review"]["fields"] if f["fact_key"] == "costs.monthly_net")
        assert after["evidence"][0]["excluded"] and after["evidence"][0]["exclusion_reason"] == "wrong_place"
        assert after["current"] == field["current"] and after["present"]  # Wert unberührt, Feld nicht verworfen
        assert after["fact_state"] != "voided"
        assert any(h["kind"] == "evidence_excluded" for h in after["history"])
        restored = _post(client, org, cid, "evidence", {"fact_key": "costs.monthly_net", "evidence_id": evidence_id, "action": "restore"})
        assert restored.status_code == 200
        again = next(f for f in restored.json()["field_review"]["fields"] if f["fact_key"] == "costs.monthly_net")
        assert not again["evidence"][0]["excluded"]
        assert [h["kind"] for h in again["history"]].count("evidence_excluded") == 1  # früherer Ausschluss bleibt im Verlauf
    finally:
        d.cleanup()


def test_deferral_and_missing_essential_field_via_api(engine):
    d, _storage, svc = _temp_env()
    try:
        org, cid, _ = _build_committed_chain(engine, svc)
        client = TestClient(import_app())
        detail = client.get(f"/api/contracts/{cid}?organization_slug={org}").json()
        number = next(f for f in detail["field_review"]["fields"] if f["fact_key"] == "identity.contract_number")
        deferred = _post(client, org, cid, "decide", {"fact_key": "identity.contract_number", "decision": "defer", "expected_version": number["version"]})
        assert deferred.status_code == 200, deferred.text
        now = next(f for f in deferred.json()["field_review"]["fields"] if f["fact_key"] == "identity.contract_number")
        assert now["status"] == "deferred" and now["decision_needed"]
        # Wert vorhanden: „Nicht im Vertrag“ verwirft den gefundenen Wert ausdrücklich (ohne Wert kein Erfinden).
        discarded = _post(client, org, cid, "decide", {"fact_key": "identity.contract_number", "decision": "not_in_document"})
        assert discarded.status_code == 200, discarded.text
        renewal = next(f for f in detail["field_review"]["fields"] if f["fact_key"] == "termination.renewal_period")
        absent = _post(client, org, cid, "decide", {"fact_key": "termination.renewal_period", "decision": "not_in_document", "expected_version": renewal["version"]})
        assert absent.status_code == 200, absent.text
        assert next(f for f in absent.json()["field_review"]["fields"] if f["fact_key"] == "termination.renewal_period")["status"] == "absent"
    finally:
        d.cleanup()


def test_decision_requires_a_named_reviewer(engine):
    d, _storage, svc = _temp_env()
    try:
        org, cid, _ = _build_committed_chain(engine, svc)
        client = TestClient(import_app())
        r = client.post(f"/api/contracts/{cid}/field-review/decide?organization_slug={org}", json={"fact_key": "identity.supplier", "decision": "keep"})
        assert r.status_code == 422 and "Name" in r.json()["detail"]  # nie ein stilles Speichern ohne Prüfer
        unknown = _post(client, org, cid, "decide", {"fact_key": "gibt.es.nicht", "decision": "keep"})
        assert unknown.status_code == 422
    finally:
        d.cleanup()


def test_deciding_a_field_closes_its_open_analysis_proposals(monkeypatch):
    """Bestätigen des bisherigen Werts darf nicht an einem offenen Analyse-Vorschlag hängen bleiben."""
    from types import SimpleNamespace

    from app.reextract import service as reextract

    mine = SimpleNamespace(field_key="dates.end_date")
    other = SimpleNamespace(field_key="dates.start_date")
    run = SimpleNamespace(id="r1")
    decided, settled = [], []
    monkeypatch.setattr(fr, "_open_proposals", lambda session, contract_id: [(mine, run), (other, run)])
    monkeypatch.setattr(reextract, "mark_decided", lambda session, actor, r, items, decision: decided.append((items[0].field_key, decision)))
    monkeypatch.setattr(reextract, "_settle", lambda session, r: settled.append(r.id))
    assert fr.close_open_proposals(None, "c1", "dates.end_date", "kept_old", object()) == 1
    assert decided == [("dates.end_date", "kept_old")] and settled == ["r1"]


def test_free_text_value_is_accepted_even_when_it_is_not_a_duration_or_date(engine):
    """„Automatisch“ statt einer Dauer: der eigene Wert gilt in der Prüfung, die Vertragsdaten bleiben unverändert."""
    d, _storage, svc = _temp_env()
    try:
        org, cid, _ = _build_committed_chain(engine, svc)
        client = TestClient(import_app())
        detail = client.get(f"/api/contracts/{cid}?organization_slug={org}").json()
        field = next(f for f in detail["field_review"]["fields"] if f["fact_key"] == "dates.end_date")
        r = _post(client, org, cid, "decide", {"fact_key": "dates.end_date", "decision": "manual", "value": "Automatisch", "expected_version": field["version"]})
        assert r.status_code == 200, r.text
        saved = next(f for f in r.json()["field_review"]["fields"] if f["fact_key"] == "dates.end_date")
        assert saved["current"] == "Automatisch" and saved["status"] == "decided"
    finally:
        d.cleanup()
