"""Erneute Erfassung und Pruefung: neue Werte sind als Angaben pruefbar und korrigierbar.

- Laufzeit/Kuendigung stehen als eigene Angaben in der Pruefung.
- Ein uebernommener neuer Wert oeffnet eine bereits gepruefte Angabe wieder (mit dem neuen Wert).
- Korrektur/Bestaetigung in der Pruefung aendert das passende Vertragsdaten-Feld mit.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.api.routes import contract_reextraction, documents
from app.api.routes.contracts import _build_augmented_detail
from app.contracts.review.service import REEXTRACTION_REOPEN_NOTE, record_fact_action
from app.database.models import Contract
from app.database.session import create_session
from app.register.fields import FieldValidationError
from app.register.service import apply_review_to_register, review_register_changes
from app.reextract import service
from tests.test_contract_documents import _service
from tests.test_reextraction import SECOND, SECOND_EVIDENCE, TEXT, _actor, _client, _imported, _model, _seed


def _states(contract_id) -> dict[str, dict]:
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id))
        data = _build_augmented_detail(session, organization_id=contract.organization_id, contract_id=contract.id)
        return {row["fact_key"]: row for row in data["fact_review_states"]}
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _sync(monkeypatch):
    monkeypatch.setattr(service, "SYNC", True)


def test_term_facts_are_reviewable(tmp_path):
    slug, _ids = _seed()
    contract_id = _imported(tmp_path, slug)
    states = _states(contract_id)
    assert states["termination.cancellation_period"]["present"] is True
    assert states["termination.cancellation_period"]["original_value"] == "3 Monate"
    assert states["termination.cancellation_period"]["label_de"] == "Kündigungsfrist"
    for key in ("dates.duration", "termination.cancellation_condition", "termination.renewal_period"):
        assert key in states and states[key]["present"] is False  # nichts gefunden: nicht „zu prüfen“


def test_applied_new_value_reopens_reviewed_fact_and_updates_register(tmp_path, monkeypatch):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id))
        record_fact_action(session, organization_id=contract.organization_id, contract_id=contract.id,
                           fact_key="termination.cancellation_period", action="confirmed",
                           reviewer_display_name="Prüferin", system_value="3 Monate")
        session.commit()
    finally:
        session.close()
    assert _states(contract_id)["termination.cancellation_period"]["state"] == "confirmed"

    client = _client(monkeypatch, ids, "manager", "contract_manager")
    query = {"organization_slug": slug}

    async def models():
        return "ollama", "qwen", []

    monkeypatch.setattr(contract_reextraction, "_installed_models", models)
    run = client.post(f"/api/contracts/{contract_id}/reextraction", params=query, json={"mode": "full"}).json()
    service.drain(_service(tmp_path, TEXT, _model(SECOND, SECOND_EVIDENCE)))
    monkeypatch.setattr(documents, "_processing_service", _service(tmp_path, TEXT, _model(SECOND)))
    applied = client.post(f"/api/contracts/{contract_id}/reextraction/{run['id']}/apply", params=query,
                          json={"keys": ["termination.cancellation_period", "dates.start_date"]})
    assert applied.status_code == 200, applied.text
    assert "termination.cancellation_period" in applied.json()["reopened"]

    states = _states(contract_id)
    period = states["termination.cancellation_period"]
    # Neuer Wert, wieder offen, mit Grund – die alte Bestaetigung gilt nicht fuer ihn.
    assert period["state"] in ("unreviewed", "needs_review")
    assert period["original_value"] == "6 Monate" and period["effective_value"] == "6 Monate"
    assert period["reopen_note"] == REEXTRACTION_REOPEN_NOTE
    # Neu gefundene Angabe (vorher leer): als zu pruefen sichtbar.
    assert states["dates.start_date"]["present"] is True
    assert states["dates.start_date"]["state"] in ("unreviewed", "needs_review")
    session = create_session()
    try:
        assert session.get(Contract, UUID(contract_id)).notice_period_value == 6
    finally:
        session.close()


def test_review_correction_reads_the_value_and_updates_register(tmp_path):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    assert review_register_changes("termination.cancellation_period", "corrected", "6 Monate") == (
        "notice_period", {"notice_period_value": 6, "notice_period_unit": "months"},
    )
    assert review_register_changes("dates.start_date", "corrected", "01.04.2025")[1]["term_start_date"].isoformat() == "2025-04-01"
    assert review_register_changes("costs.annual", "corrected", "100") == (None, {})  # kein Vertragsdaten-Feld
    with pytest.raises(FieldValidationError, match="nicht lesbar"):
        review_register_changes("termination.cancellation_period", "corrected", "lang")

    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id), with_for_update=True)
        base, changes = review_register_changes("termination.cancellation_period", "corrected", "sechs Monate")
        apply_review_to_register(session, contract=contract, actor=_actor(ids), base=base, changes=changes)
        session.commit()
        assert contract.notice_period_value == 6
        # Bestaetigen in der Pruefung bestaetigt den KI-Wert in den Vertragsdaten.
        contract = session.get(Contract, UUID(contract_id), with_for_update=True)
        from app.register.service import _provenance

        assert _provenance(session, contract.id)["short_description"].origin == "ai"
    finally:
        session.close()


def test_review_route_correction_reaches_register_only_with_edit_right(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.routes import contract_register, contracts
    from app.core.scope_context import ScopeContext
    from app.database import scope_queries

    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)

    def client(key, role):
        actor = SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())
        monkeypatch.setattr(contract_register, "current_actor", lambda request, organization_slug: actor)
        monkeypatch.setattr(contract_register, "current_scope_context", lambda: ScopeContext())
        monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
        app = FastAPI()
        app.include_router(contracts.router)
        return TestClient(app)

    def correct(c, value):
        return c.post(f"/api/contracts/{contract_id}/fact-reviews", params={"organization_slug": slug}, json={
            "fact_key": "termination.cancellation_period", "action": "corrected", "corrected_value": value,
            "reviewer_display_name": "Test", "note": "laut Vertrag",
        })

    def notice():
        session = create_session()
        try:
            return session.get(Contract, UUID(contract_id)).notice_period_value
        finally:
            session.close()

    reviewer = client("reviewer", "reviewer")
    assert correct(reviewer, "4 Monate").status_code == 200
    assert notice() == 3  # Pruefer ohne Bearbeitungsrecht: Vertragsdaten unveraendert

    manager = client("manager", "contract_manager")
    unreadable = correct(manager, "lang")
    assert unreadable.status_code == 422 and "nicht lesbar" in unreadable.json()["detail"]
    assert correct(manager, "6 Monate").status_code == 200
    assert notice() == 6
    assert _states(contract_id)["termination.cancellation_period"]["effective_value"] == "6 Monate"
