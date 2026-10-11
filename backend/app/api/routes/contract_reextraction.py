"""Erneute Erfassung aus dem Vertragsdokument (Plan ERNEUT_ERFASSEN_PLAN_20261011).

Starten, Stand abfragen, Ergebnis vergleichen, ausgewaehlte Angaben uebernehmen,
verwerfen, abbrechen. Org-Scope und Berechtigung werden vor jedem Modellaufruf
geprueft; ein Lauf aendert die Vertragswahrheit nie selbst.
"""

from __future__ import annotations

from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.ai.providers import discovery
from app.ai.settings_service import resolve_ai_selection
from app.api.routes.contract_register import _contract, _register_actor
from app.auth.permissions import can, require
from app.core.config import settings
from app.database.session import create_session
from app.documents.processing import ReextractionConflict
from app.reextract import facts, service

router = APIRouter(prefix="/api/contracts", tags=["contract-reextraction"])


class StartRequest(BaseModel):
    mode: Literal["full", "missing_fields"] = "full"
    fields: list[str] = Field(default_factory=list, max_length=80)
    page_hint: list[int] = Field(default_factory=list, max_length=40)
    reread_document: bool = False
    model_id: Optional[str] = Field(default=None, max_length=200)


class ApplyRequest(BaseModel):
    keys: list[str] = Field(default_factory=list, max_length=120)


def _http(exc: service.ReextractError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


async def _installed_models() -> tuple[Optional[str], Optional[str], list[dict]]:
    """Gewaehlter Provider/Modell und dessen installierte, verfuegbare Modelle (nur lokal)."""
    provider_id, model_id = resolve_ai_selection(settings)
    if not provider_id:
        return None, None, []
    providers = await discovery.discover_providers(settings)
    models: list[dict] = []
    for provider in providers:
        if provider.provider_id != provider_id or not provider.reachable:
            continue
        for model in provider.models:
            if model.state != "available" or model.capabilities.embedding:
                continue
            models.append({
                "model_id": model.model_id,
                "label": model.display_name or model.model_id,
                "parameter_size": model.parameter_size,
                "vision": bool(model.capabilities.vision),
                "current": model.model_id == model_id,
            })
    return provider_id, model_id, models


@router.get("/{contract_id}/reextraction")
def reextraction_state(request: Request, contract_id: UUID, organization_slug: str) -> dict:
    actor = _register_actor(request, organization_slug)
    require(actor, "contract.read")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        run = service.latest_run(session, contract)
        if run is not None and run.status == "queued":
            service.kick()  # selbstheilend, falls der Hintergrundlauf verloren ging
        version_id = service.main_document_version(session, contract)
        missing = service.missing_facts(session, contract) if contract.accepted_extraction_id else []
        return {
            "can_start": bool(can(actor, "contract.reanalyze") and version_id and contract.accepted_extraction_id
                              and contract.lifecycle_state == "active"),
            "blocked_reason": (
                None if version_id and contract.accepted_extraction_id else
                ("Kein Vertragsdokument hinterlegt." if not version_id else "Für diesen Vertrag liegt noch keine KI-Analyse vor.")
            ),
            "missing": [{"key": key, "label": facts.LABELS.get(key, key)} for key in missing],
            "field_search": facts.register_search_map(),
            "reread_suggested": service.reread_suggested(session, version_id),
            "run": service.run_payload(session, run),
            "rows": service.rows(session, run) if run is not None else [],
        }
    finally:
        session.close()


@router.get("/{contract_id}/reextraction/models")
async def reextraction_models(request: Request, contract_id: UUID, organization_slug: str) -> dict:
    actor = _register_actor(request, organization_slug)
    require(actor, "contract.reanalyze", "Keine Berechtigung für die erneute Erfassung.")
    session = create_session()
    try:
        _contract(session, actor, contract_id)
    finally:
        session.close()
    provider_id, model_id, models = await _installed_models()
    return {"provider_id": provider_id, "current_model": model_id, "models": models}


@router.post("/{contract_id}/reextraction", status_code=202)
async def start_reextraction(request: Request, contract_id: UUID, organization_slug: str, payload: StartRequest) -> dict:
    actor = _register_actor(request, organization_slug)
    require(actor, "contract.reanalyze", "Keine Berechtigung für die erneute Erfassung.")
    session = create_session()
    try:
        _contract(session, actor, contract_id)  # Scope vor jeder Modellabfrage
    finally:
        session.close()
    provider_id, current_model, models = await _installed_models()
    if not provider_id or not current_model:
        raise HTTPException(status_code=409, detail="Keine lokale KI ausgewählt. Bitte unter Einstellungen → Lokale KI festlegen.")
    chosen = (payload.model_id or "").strip() or None
    if chosen and chosen != current_model and chosen not in {model["model_id"] for model in models}:
        raise HTTPException(status_code=422, detail="Dieses Modell ist lokal nicht verfügbar.")

    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            run = service.start(
                session, contract=contract, actor=actor, mode=payload.mode, fields=payload.fields,
                page_hint=payload.page_hint, reread=payload.reread_document, provider_id=provider_id,
                model_id=chosen if chosen and chosen != current_model else None,
            )
        except service.ReextractError as exc:
            session.rollback()
            raise _http(exc) from exc
        session.commit()
        result = service.run_payload(session, run)
    finally:
        session.close()
    service.kick()
    return result


@router.post("/{contract_id}/reextraction/{run_id}/apply")
async def apply_reextraction(request: Request, contract_id: UUID, run_id: UUID, organization_slug: str, payload: ApplyRequest) -> dict:
    actor = _register_actor(request, organization_slug)
    require(actor, "contract.reanalyze", "Keine Berechtigung für die erneute Erfassung.")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        run = service.get_run(session, contract, run_id)
        merged, keys = service.prepare_apply(session, contract, run, payload.keys)
        version_id, base_id, candidate_id = run.document_version_id, run.base_extraction_id, run.candidate_extraction_id
    except service.ReextractError as exc:
        raise _http(exc) from exc
    finally:
        session.close()

    from app.api.routes.documents import _processing_service

    try:
        result = await run_in_threadpool(
            _processing_service.apply_candidate,
            organization_id=actor.organization_id, contract_id=contract_id, document_version_id=version_id,
            merged_model=merged, base_extraction_id=base_id, candidate_extraction_id=candidate_id, applied_keys=keys,
        )
    except ReextractionConflict as exc:
        raise HTTPException(status_code=409, detail="Die Vertragsdaten haben sich seit dem Start geändert. Bitte erneut erfassen.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Die Angaben konnten nicht übernommen werden.") from exc
    if result.status != "reanalyzed":
        raise HTTPException(status_code=404, detail="Vertrag oder Dokument nicht gefunden.")

    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        run = service.get_run(session, contract, run_id, for_update=True)
        service.mark_applied(session, actor, run, keys)
        reopened = _reopen_reviews(session, actor, contract, keys)
        session.commit()
    finally:
        session.close()
    message = f"{len(keys)} Angabe(n) übernommen."
    if reopened:
        message += f" {len(reopened)} bereits geprüfte Angabe(n) sind wieder zur Prüfung offen."
    return {"applied": len(keys), "keys": keys, "reopened": reopened, "message": message}


def _reopen_reviews(session, actor, contract, keys: list[str]) -> list[str]:
    """Neue Werte in der Pruefung: geaenderte, bereits gepruefte Angaben wieder oeffnen und die
    Vertragsdaten danach neu abgleichen (eine fruehere Korrektur gilt nicht fuer den neuen Wert)."""
    from app.api.routes.contracts import _build_augmented_detail
    from app.contracts.review.material import material_report
    from app.contracts.review.service import reopen_after_reextraction
    from app.core.clock import today_local
    from app.deadlines.system import sync_system_deadlines
    from app.register.service import load_extracted, sync_from_extraction

    detail = _build_augmented_detail(session, organization_id=contract.organization_id, contract_id=contract.id)
    report = material_report(detail or {})
    values = {fact: (report.get(fact) or {}).get("value") for fact in facts.review_facts_for(keys) if fact in report}
    reopened = reopen_after_reextraction(
        session, organization_id=contract.organization_id, contract_id=contract.id, values=values,
        reviewer_display_name=actor.display_name,
    )
    if reopened:
        session.refresh(contract, with_for_update=True)
        extracted = load_extracted(session, contract.accepted_extraction_id)
        if extracted is not None:
            sync_from_extraction(session, contract=contract, extracted=extracted, extraction_id=contract.accepted_extraction_id)
            sync_system_deadlines(session, contract, today_local())
    return reopened


@router.post("/{contract_id}/reextraction/{run_id}/discard")
def discard_reextraction(request: Request, contract_id: UUID, run_id: UUID, organization_slug: str) -> dict:
    actor = _register_actor(request, organization_slug)
    require(actor, "contract.reanalyze", "Keine Berechtigung für die erneute Erfassung.")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        run = service.get_run(session, contract, run_id, for_update=True)
        service.discard(session, actor, run)
        session.commit()
        return {"status": run.status}
    except service.ReextractError as exc:
        session.rollback()
        raise _http(exc) from exc
    finally:
        session.close()


@router.post("/{contract_id}/reextraction/{run_id}/cancel")
def cancel_reextraction(request: Request, contract_id: UUID, run_id: UUID, organization_slug: str) -> dict:
    actor = _register_actor(request, organization_slug)
    require(actor, "contract.reanalyze", "Keine Berechtigung für die erneute Erfassung.")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        run = service.get_run(session, contract, run_id, for_update=True)
        service.cancel(session, run)
        session.commit()
        return {"status": run.status, "cancel_requested": run.cancel_requested}
    except service.ReextractError as exc:
        session.rollback()
        raise _http(exc) from exc
    finally:
        session.close()
