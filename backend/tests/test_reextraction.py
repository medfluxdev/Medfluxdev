"""Erneute Erfassung aus dem Vertragsdokument: Kandidat, Vergleich, Uebernahme.

Plan: docs/architecture/ERNEUT_ERFASSEN_PLAN_20261011.md. Kernzusagen:
ein Lauf aendert die Vertragswahrheit nie selbst, nicht erneut gefundene Werte
bleiben, Menschwerte bleiben, Uebernahme nur auf dem aktuellen Stand.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import contract_register, contract_reextraction
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import Account, AccountMembership, ActivityLog, Contract
from app.database.models.deadlines import Notification
from app.database.models.organization import Organization
from app.database.models.reextraction import ContractReextraction
from app.database.session import create_session
from app.models.contract import Contract as DomainContract
from app.reextract import facts, service
from app.register.service import RegisterActor, load_extracted
from tests.test_contract_documents import _pdf, _service

TEXT = "Wartungsvertrag CT. Beginn 01.01.2025. Kündigungsfrist sechs Monate zum Jahresende."


def _model(data: dict, evidence: list[dict] | None = None, model: str = "erst") -> DomainContract:
    contract = DomainContract.model_validate(data)
    contract.analysis.harness = {"evidence": evidence or [], "model": model}
    return contract


FIRST = {
    "identity": {"contract_title": "Wartung CT", "supplier": "Siemens"},
    "termination": {"cancellation_period": {"value": 3, "unit": "months"}},
}
SECOND = {
    "identity": {"supplier": "Siemens Healthineers"},
    "dates": {"start_date": {"date": "2025-01-01"}},
    "termination": {"cancellation_period": {"value": 6, "unit": "months"}},
}
SECOND_EVIDENCE = [
    {"field": "dates.start_date", "source": {"page": 1, "source_text": "Beginn 01.01.2025"}},
    {"field": "termination.cancellation_period", "source": {"page": 1, "source_text": "Kündigungsfrist sechs Monate"}},
]


# --- reine Logik ---------------------------------------------------------------------------


def test_compare_groups_and_preselection():
    accepted = _model(FIRST)
    candidate = _model(SECOND, SECOND_EVIDENCE, model="zweit")
    rows = {row.key: row for row in facts.compare(accepted, candidate)}
    assert rows["dates.start_date"].group == "new"
    assert rows["dates.start_date"].preselected is True
    assert rows["dates.start_date"].proposed == "01.01.2025"
    assert rows["dates.start_date"].evidence == [{"page": 1, "quote": "Beginn 01.01.2025"}]
    assert rows["termination.cancellation_period"].group == "changed"
    assert rows["termination.cancellation_period"].preselected is False  # Abweichung nie vorausgewaehlt
    assert (rows["termination.cancellation_period"].current, rows["termination.cancellation_period"].proposed) == ("3 Monate", "6 Monate")
    assert rows["identity.contract_title"].group == "missing_again"
    assert rows["identity.contract_title"].current == "Wartung CT"
    # Ohne Nachweis wird auch eine neue Angabe nicht vorausgewaehlt.
    bare = {row.key: row for row in facts.compare(accepted, _model(SECOND))}
    assert bare["dates.start_date"].group == "new" and bare["dates.start_date"].preselected is False
    # Neu und abweichend stehen oben.
    assert [row.group for row in facts.compare(accepted, candidate)][:2] == ["new", "changed"]


def test_compare_only_limits_to_searched_facts():
    rows = facts.compare(_model(FIRST), _model(SECOND, SECOND_EVIDENCE), only=["dates.start_date"])
    assert [row.key for row in rows] == ["dates.start_date"]


def test_merge_takes_only_selected_and_never_clears():
    accepted = _model(FIRST, [{"field": "termination.cancellation_period", "source": {"page": 2, "source_text": "drei Monate"}}])
    candidate = _model(SECOND, SECOND_EVIDENCE, model="zweit")
    merged = facts.merge(accepted, candidate, ["dates.start_date", "identity.contract_title"], run_id="r1")
    assert merged.dates.start_date.date.isoformat() == "2025-01-01"
    # Nicht ausgewaehlt: bleibt; im Kandidaten leer: wird nie geloescht.
    assert merged.termination.cancellation_period.value == 3
    assert merged.identity.contract_title == "Wartung CT"
    assert merged.identity.supplier == "Siemens"
    fields = [row["field"] for row in merged.analysis.harness["evidence"]]
    assert fields == ["termination.cancellation_period", "dates.start_date"]
    assert merged.analysis.harness["reextractions"] == [{"run_id": "r1", "applied": ["dates.start_date"], "model": "zweit"}]
    # Die akzeptierte Extraktion selbst bleibt unveraendert.
    assert accepted.dates.start_date is None


def test_empty_and_display_rules():
    assert facts.is_empty(DomainContract().identity.contract_type)  # "unknown"
    assert facts.is_empty(DomainContract.model_validate({"dates": {"start_date": {}}}).dates.start_date)
    assert facts.display(DomainContract.model_validate({"costs": {"annual_cost": {"amount": 12345.5, "currency": "EUR", "period": "annual"}}}).costs.annual_cost) == "12.345,50 EUR (jährlich)"
    assert facts.display(True) == "Ja"
    assert facts.facts_for_register_key("term_start_date") == ["dates.start_date"]
    assert "termination.cancellation_period" in facts.facts_for_register_key("notice_period_value")
    search = facts.register_search_map()
    assert search["term_start_date"] == [{"key": "dates.start_date", "label": "Vertragsbeginn"}]
    assert {item["key"] for item in search["notice_period_value"]} == {"termination.cancellation_period"}


# --- Ablauf mit Datenbank --------------------------------------------------------------------


def _seed():
    ids = {key: uuid4() for key in ("org", "admin", "manager", "reviewer", "viewer")}
    slug = f"reextract-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Erfassung Klinik", slug=slug))
        for key in ("admin", "manager", "reviewer", "viewer"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@x.invalid", display_name=key.title(), credential_digest="t"))
        session.flush()
        for key, role in (("admin", "admin"), ("manager", "contract_manager"), ("reviewer", "reviewer"), ("viewer", "viewer")):
            session.add(AccountMembership(organization_id=ids["org"], account_id=ids[key], role=role))
        session.commit()
    finally:
        session.close()
    return slug, ids


def _imported(tmp_path, slug) -> str:
    result = _service(tmp_path, TEXT, _model(FIRST)).process(
        organization_slug=slug, original_filename="ct.pdf", content_type="application/pdf", content=_pdf(),
    )
    assert result.status == "imported", result.message
    return result.contract_id


def _actor(ids, key="manager", role="contract_manager") -> RegisterActor:
    return RegisterActor(organization_id=ids["org"], account_id=ids[key], display_name=key.title(), role=role)


@pytest.fixture(autouse=True)
def _sync_worker(monkeypatch):
    monkeypatch.setattr(service, "SYNC", True)


def _start(contract_id, ids, **kwargs) -> uuid.UUID:
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id))
        run = service.start(session, contract=contract, actor=_actor(ids), mode=kwargs.get("mode", "full"),
                            fields=kwargs.get("fields", []), page_hint=[], reread=False, provider_id="ollama", model_id=None)
        session.commit()
        return run.id
    finally:
        session.close()


def _state(contract_id):
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id))
        extracted = load_extracted(session, contract.accepted_extraction_id)
        return contract.accepted_extraction_id, extracted, contract.notice_period_value, contract.term_start_date
    finally:
        session.close()


def test_run_creates_candidate_only_and_apply_merges_selected(tmp_path):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    before_id, before, notice, start = _state(contract_id)
    assert (notice, start) == (3, None)

    run_id = _start(contract_id, ids)
    assert service.drain(_service(tmp_path, TEXT, _model(SECOND, SECOND_EVIDENCE, model="zweit"))) == 1

    # Ein fertiger Lauf aendert nichts am Vertrag.
    assert _state(contract_id)[0] == before_id
    session = create_session()
    try:
        run = session.get(ContractReextraction, run_id)
        assert run.status == "ready"
        assert run.summary["new"] >= 1 and run.summary["changed"] >= 1
        rows = {row["key"]: row for row in service.rows(session, run)}
        assert rows["dates.start_date"]["preselected"] is True
        contract = session.get(Contract, UUID(contract_id))
        merged, keys = service.prepare_apply(session, contract, run, ["dates.start_date"])
        version_id, base_id, candidate_id = run.document_version_id, run.base_extraction_id, run.candidate_extraction_id
        # Benachrichtigung fuer die Person, die gestartet hat.
        note = session.scalars(select(Notification).where(Notification.contract_id == UUID(contract_id))).one()
        assert note.kind == "reextraction" and note.account_id == ids["manager"]
    finally:
        session.close()

    processing = _service(tmp_path, TEXT, _model(SECOND))
    result = processing.apply_candidate(
        organization_id=ids["org"], contract_id=UUID(contract_id), document_version_id=version_id,
        merged_model=merged, base_extraction_id=base_id, candidate_extraction_id=candidate_id, applied_keys=keys,
    )
    assert result.status == "reanalyzed", result.message
    after_id, after, notice, start = _state(contract_id)
    assert after_id != before_id
    assert start.isoformat() == "2025-01-01"          # uebernommen, in die Vertragsdaten synchronisiert
    assert notice == 3                                 # abweichender Wert nicht gewaehlt: bleibt
    assert after.identity.contract_title == "Wartung CT"  # nicht erneut gefunden: bleibt
    assert after.identity.supplier == "Siemens"

    # Ein zweites Uebernehmen auf altem Stand scheitert sauber.
    from app.documents.processing import ReextractionConflict
    with pytest.raises(ReextractionConflict):
        processing.apply_candidate(
            organization_id=ids["org"], contract_id=UUID(contract_id), document_version_id=version_id,
            merged_model=merged, base_extraction_id=base_id, candidate_extraction_id=candidate_id, applied_keys=keys,
        )


def test_human_values_stay_and_only_one_active_run(tmp_path):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    session = create_session()
    try:
        from app.register.service import update_register

        contract = session.get(Contract, UUID(contract_id), with_for_update=True)
        update_register(session, contract=contract, actor=_actor(ids), changes={"notice_period_value": 4}, confirm=[])
        session.commit()
    finally:
        session.close()

    run_id = _start(contract_id, ids)
    with pytest.raises(service.ReextractError) as conflict:
        _start(contract_id, ids)
    assert conflict.value.status_code == 409

    service.drain(_service(tmp_path, TEXT, _model(SECOND, SECOND_EVIDENCE)))
    session = create_session()
    try:
        run = session.get(ContractReextraction, run_id)
        contract = session.get(Contract, UUID(contract_id))
        merged, keys = service.prepare_apply(session, contract, run, ["termination.cancellation_period"])
        args = dict(document_version_id=run.document_version_id, base_extraction_id=run.base_extraction_id,
                    candidate_extraction_id=run.candidate_extraction_id)
    finally:
        session.close()
    _service(tmp_path, TEXT, _model(SECOND)).apply_candidate(
        organization_id=ids["org"], contract_id=UUID(contract_id), merged_model=merged, applied_keys=keys, **args,
    )
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id))
        assert contract.notice_period_value == 4  # von Hand gepflegt: bleibt, KI-Wert nur als Vorschlag
        from app.database.models.register import ContractFieldProvenance

        row = session.scalars(select(ContractFieldProvenance).where(
            ContractFieldProvenance.contract_id == contract.id, ContractFieldProvenance.field_key == "notice_period_value",
        )).one()
        assert row.ai_proposed_value["value"] == 6
    finally:
        session.close()


def test_missing_fields_mode_and_discard_and_cancel(tmp_path):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id))
        assert "dates.start_date" in service.missing_facts(session, contract)
    finally:
        session.close()
    with pytest.raises(service.ReextractError):
        _start(contract_id, ids, mode="missing_fields", fields=[])
    run_id = _start(contract_id, ids, mode="missing_fields", fields=["dates.start_date"])
    service.drain(_service(tmp_path, TEXT, _model(SECOND, SECOND_EVIDENCE)))
    session = create_session()
    try:
        run = session.get(ContractReextraction, run_id)
        assert [row["key"] for row in service.rows(session, run)] == ["dates.start_date"]
        service.discard(session, _actor(ids), run)
        session.commit()
        assert run.status == "discarded"
        events = {row.event_name for row in session.scalars(select(ActivityLog).where(ActivityLog.object_id == UUID(contract_id)))}
        assert {"contract.reextraction_started", "contract.reextraction_discarded"} <= events
    finally:
        session.close()

    queued = _start(contract_id, ids)
    session = create_session()
    try:
        run = session.get(ContractReextraction, queued)
        service.cancel(session, run)
        session.commit()
        assert run.status == "cancelled"
    finally:
        session.close()
    assert service.drain(_service(tmp_path, TEXT, _model(SECOND))) == 0


def test_failed_analysis_marks_run_failed_and_keeps_contract(tmp_path):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    before = _state(contract_id)[0]
    run_id = _start(contract_id, ids)

    class Broken:
        def extract_candidate(self, **kwargs):
            raise RuntimeError("model down")

    service.drain(Broken())
    session = create_session()
    try:
        run = session.get(ContractReextraction, run_id)
        assert run.status == "failed" and run.message
    finally:
        session.close()
    assert _state(contract_id)[0] == before


# --- API: Berechtigung und Scope -----------------------------------------------------------


def _client(monkeypatch, ids, key, role):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())
    monkeypatch.setattr(contract_register, "current_actor", lambda request, organization_slug: actor)
    monkeypatch.setattr(contract_register, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    app.include_router(contract_reextraction.router)
    return TestClient(app)


def test_api_permissions_and_scope_before_model_call(tmp_path, monkeypatch):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)

    async def no_models():
        raise AssertionError("Modellabfrage vor Scope-/Rechtepruefung")

    monkeypatch.setattr(contract_reextraction, "_installed_models", no_models)
    for key, role in (("viewer", "viewer"), ("reviewer", "reviewer")):
        client = _client(monkeypatch, ids, key, role)
        response = client.post(f"/api/contracts/{contract_id}/reextraction", params={"organization_slug": slug}, json={})
        assert response.status_code == 403
        state = client.get(f"/api/contracts/{contract_id}/reextraction", params={"organization_slug": slug}).json()
        assert state["can_start"] is False

    other_slug, other_ids = _seed()
    client = _client(monkeypatch, other_ids, "admin", "admin")
    response = client.post(f"/api/contracts/{contract_id}/reextraction", params={"organization_slug": other_slug}, json={})
    assert response.status_code == 404

    async def models():
        return "ollama", "qwen", [{"model_id": "qwen", "label": "qwen", "parameter_size": None, "vision": True, "current": True}]

    monkeypatch.setattr(contract_reextraction, "_installed_models", models)
    client = _client(monkeypatch, ids, "manager", "contract_manager")
    state = client.get(f"/api/contracts/{contract_id}/reextraction", params={"organization_slug": slug}).json()
    assert state["can_start"] is True and state["run"] is None
    assert any(item["key"] == "dates.start_date" for item in state["missing"])
    rejected = client.post(f"/api/contracts/{contract_id}/reextraction", params={"organization_slug": slug}, json={"model_id": "fremd"})
    assert rejected.status_code == 422
    started = client.post(f"/api/contracts/{contract_id}/reextraction", params={"organization_slug": slug}, json={"mode": "full"})
    assert started.status_code == 202, started.text
    assert started.json()["status"] == "queued"
    assert client.get(f"/api/contracts/{contract_id}/reextraction", params={"organization_slug": slug}).json()["run"]["status"] == "queued"


def test_missing_fields_run_passes_focus_and_pages_to_the_harness(tmp_path):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id))
        service.start(session, contract=contract, actor=_actor(ids), mode="missing_fields", fields=["dates.start_date"],
                      page_hint=[4, 4, -1, 6], reread=True, provider_id="ollama", model_id="qwen3:14b")
        session.commit()
    finally:
        session.close()
    calls = []

    class Recording:
        def extract_candidate(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("nur aufzeichnen")

    service.drain(Recording())
    # Die Warteschlange ist organisationsuebergreifend; hier zaehlt der eigene Lauf.
    call = next(item for item in calls if item["contract_id"] == UUID(contract_id))
    assert call["focus_fields"] == ["dates.start_date"]
    assert call["focus_pages"] == [4, 6]
    assert call["reread"] is True and call["model_override"] == "qwen3:14b"



def test_first_analysis_for_manually_captured_contract(tmp_path):
    """Ohne frühere KI-Analyse: erste Erfassung gegen eine leere Grundlage, übernommen wird nur Ausgewähltes."""
    from app.register.service import create_manual_contract

    slug, ids = _seed()
    processing = _service(tmp_path, TEXT, _model(SECOND, SECOND_EVIDENCE, model="erst"))
    result = processing.import_for_manual_capture(
        organization_slug=slug, original_filename="manuell.pdf", content_type="application/pdf", content=_pdf(),
        create_contract=lambda session: create_manual_contract(session, actor=_actor(ids), hospital_id=None, values={"short_description": "Wartung CT (manuell)"}),
        added_by_name="Manager",
    )
    contract_id = result.contract_id
    assert contract_id and _state(contract_id)[0] is None

    run_id = _start(contract_id, ids)
    assert service.drain(processing) == 1
    session = create_session()
    try:
        run = session.get(ContractReextraction, run_id)
        assert run.status == "ready" and run.base_extraction_id is None
        rows = {row["key"]: row for row in service.rows(session, run)}
        assert rows["dates.start_date"]["group"] == "new"
        contract = session.get(Contract, UUID(contract_id))
        merged, keys = service.prepare_apply(session, contract, run, ["dates.start_date"])
        version_id, candidate_id = run.document_version_id, run.candidate_extraction_id
    finally:
        session.close()

    applied = processing.apply_candidate(
        organization_id=ids["org"], contract_id=UUID(contract_id), document_version_id=version_id,
        merged_model=merged, base_extraction_id=None, candidate_extraction_id=candidate_id, applied_keys=keys,
    )
    assert applied.status == "reanalyzed", applied.message
    after_id, after, notice, start = _state(contract_id)
    assert after_id is not None
    assert start.isoformat() == "2025-01-01"   # gewählt: übernommen
    assert notice is None                        # nicht gewählt: bleibt leer
