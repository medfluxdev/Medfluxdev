"""Erneute Erfassung aus dem Vertragsdokument (Plan ERNEUT_ERFASSEN_PLAN_20261011).

Starten (Ergaenzen / Bereich / Vollstaendig), Stand und Verlauf abfragen, Vorschlaege
einzeln entscheiden (uebernehmen, behalten, selbst erfassen), unveraenderte sichere
Angaben bestaetigen, verwerfen, abbrechen, einen frueheren Stand wiederherstellen.
Org-Scope und Berechtigung werden vor jedem Modellaufruf geprueft; ein Lauf aendert
die Vertragswahrheit nie selbst.
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
    # "missing_fields" ist der fruehere Name von "supplement".
    mode: Literal["supplement", "sections", "full", "missing_fields"] = "supplement"
    fields: list[str] = Field(default_factory=list, max_length=80)
    sections: list[str] = Field(default_factory=list, max_length=10)
    page_hint: list[int] = Field(default_factory=list, max_length=40)
    hint: Optional[str] = Field(default=None, max_length=500)
    protect_manual: bool = True
    reset_confirmations: bool = False
    reread_document: bool = False
    model_id: Optional[str] = Field(default=None, max_length=200)
    # Optional: ein anderes gültiges Dokument des Vertrags statt des Hauptdokuments analysieren.
    document_version_id: Optional[UUID] = None


class ApplyRequest(BaseModel):
    keys: list[str] = Field(default_factory=list, max_length=120)


class DecideRequest(BaseModel):
    keys: list[str] = Field(default_factory=list, max_length=120)
    decision: Literal["kept_old", "manual", "rejected"]


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
        evidence = service.evidence_count(session, contract)
        rows = service.rows(session, run) if run is not None else []
        session.commit()  # Vorschlaege von Altlaeufen werden beim ersten Lesen angelegt
        return {
            # Auch ohne frühere KI-Analyse: die erste Erfassung vergleicht gegen eine leere Grundlage.
            "can_start": bool(can(actor, "contract.reanalyze") and version_id and contract.lifecycle_state == "active"),
            "blocked_reason": None if version_id else "Kein Vertragsdokument hinterlegt.",
            "first_analysis": contract.accepted_extraction_id is None,
            "missing": [{"key": key, "label": facts.LABELS.get(key, key)} for key in missing],
            "field_search": facts.register_search_map(),
            "reread_suggested": service.reread_suggested(session, version_id),
            "run": service.run_payload(session, run),
            "rows": rows,
            "open_fields": len(service.open_facts(session, contract)),
            "evidence_count": evidence,
            "review_minutes": max(1, round(evidence * service.SECONDS_PER_EVIDENCE / 60)) if evidence else 0,
            "duration_minutes": _last_duration(service.runs(session, contract)),
            "sections": [{"key": key, "label": label} for key, (label, _groups) in facts.SECTIONS.items()],
            "history": service.history(session, contract),
            "new_document": service.new_document(session, contract) if can(actor, "contract.reanalyze") else None,
            "can_review": can(actor, "contract.review"),
        }
    finally:
        session.close()


def _last_duration(items) -> Optional[int]:
    """Dauer der letzten fertigen Analyse in Minuten (Schaetzung fuer die naechste)."""
    for item in items:
        if item.mode != "rollback" and item.started_at and item.finished_at and item.status in {"ready", "applied", "discarded"}:
            return max(1, round((item.finished_at - item.started_at).total_seconds() / 60))
    return None


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
                sections=payload.sections, hint=payload.hint, protect_manual=payload.protect_manual,
                reset_confirmations=payload.reset_confirmations,
                document_version_id=payload.document_version_id,
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
        reopened = _reopen_reviews(session, actor, contract, keys)
        service.mark_applied(session, actor, run, keys)
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


@router.post("/{contract_id}/reextraction/{run_id}/decide")
def decide_reextraction(request: Request, contract_id: UUID, run_id: UUID, organization_slug: str, payload: DecideRequest) -> dict:
    """Vorschlaege ohne Wertaenderung entscheiden: Behalten, Selbst erfassen, Ablehnen."""
    actor = _register_actor(request, organization_slug)
    require(actor, "contract.reanalyze", "Keine Berechtigung für die erneute Erfassung.")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        run = service.get_run(session, contract, run_id, for_update=True)
        count = service.decide(session, actor, run, payload.keys, payload.decision)
        session.commit()
        return {"decided": count, "status": run.status}
    except service.ReextractError as exc:
        session.rollback()
        raise _http(exc) from exc
    finally:
        session.close()


@router.post("/{contract_id}/reextraction/{run_id}/confirm-unchanged")
def confirm_unchanged(request: Request, contract_id: UUID, run_id: UUID, organization_slug: str) -> dict:
    """Alle unveraenderten bestaetigen: gleiche Werte mit Sicherheit >= 0,95 als geprueft markieren."""
    from app.api.routes.contracts import _build_augmented_detail
    from app.contracts.review.material import MATERIAL_FACT_KEYS, material_report
    from app.contracts.review.service import _latest_fact_reviews, record_fact_action

    actor = _register_actor(request, organization_slug)
    require(actor, "contract.review", "Keine Berechtigung für die Prüfung.")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        run = service.get_run(session, contract, run_id, for_update=True)
        if run.status != "ready":
            raise service.ReextractError(409, "Dieses Ergebnis ist nicht mehr offen.")
        items = service.safe_unchanged(session, run)
        report = material_report(_build_augmented_detail(session, organization_id=contract.organization_id, contract_id=contract.id) or {})
        latest = _latest_fact_reviews(session, contract.id)
        confirmed = 0
        for item in items:
            fact_key = (facts.REVIEW_FACTS.get(item.field_key) or (item.field_key,))[0]
            row = latest.get(fact_key)
            if fact_key not in MATERIAL_FACT_KEYS or fact_key not in report or (row is not None and row.action in {"confirmed", "corrected"}):
                continue
            record_fact_action(
                session, organization_id=contract.organization_id, contract_id=contract.id, fact_key=fact_key,
                action="confirmed", reviewer_display_name=actor.display_name or "Prüfung",
                note=f"Unverändert in Analyse #{run.number}", system_value=(report.get(fact_key) or {}).get("value"),
            )
            confirmed += 1
        # Unveraendert bestaetigt: kein Wert aendert sich, es gibt nichts zurueckzunehmen.
        service.mark_decided(session, actor, run, items, "kept_old")
        service.log_activity(session, actor, contract.id, "contract.reextraction_confirmed_unchanged", {
            "run_id": str(run.id), "number": run.number, "count": len(items), "facts": confirmed,
        })
        session.commit()
        return {"confirmed": len(items), "facts": confirmed}
    except service.ReextractError as exc:
        session.rollback()
        raise _http(exc) from exc
    finally:
        session.close()


@router.get("/{contract_id}/reextraction/rollback/{number}")
def rollback_preview(request: Request, contract_id: UUID, number: int, organization_slug: str) -> dict:
    """Was "Auf diesen Stand zurück" aendern wuerde (Vorschau fuer die Rueckfrage)."""
    actor = _register_actor(request, organization_slug)
    require(actor, "contract.reanalyze", "Keine Berechtigung für die erneute Erfassung.")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        _model, entries, _undo = service.rollback_plan(session, contract, number)
        return {"target": number, "entries": entries}
    except service.ReextractError as exc:
        raise _http(exc) from exc
    finally:
        session.close()


@router.post("/{contract_id}/reextraction/rollback/{number}")
async def rollback(request: Request, contract_id: UUID, number: int, organization_slug: str) -> dict:
    """Stand nach Analyse #number wiederherstellen: spaetere Uebernahmen zuruecknehmen."""
    actor = _register_actor(request, organization_slug)
    require(actor, "contract.reanalyze", "Keine Berechtigung für die erneute Erfassung.")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        model, entries, undo = service.rollback_plan(session, contract, number)
        if not undo:
            raise service.ReextractError(409, "Es gibt nichts zurückzunehmen.")
        version_id = service.main_document_version(session, contract)
        base_id = contract.accepted_extraction_id
        undo_ids = {item.id for item in undo}
        keys = list(dict.fromkeys(item.field_key for item in undo))
    except service.ReextractError as exc:
        raise _http(exc) from exc
    finally:
        session.close()

    from app.api.routes.documents import _processing_service

    try:
        result = await run_in_threadpool(
            _processing_service.apply_candidate,
            organization_id=actor.organization_id, contract_id=contract_id, document_version_id=version_id,
            merged_model=model, base_extraction_id=base_id, candidate_extraction_id=base_id, applied_keys=keys,
        )
    except ReextractionConflict as exc:
        raise HTTPException(status_code=409, detail="Die Vertragsdaten haben sich inzwischen geändert. Bitte erneut versuchen.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Der Stand konnte nicht wiederhergestellt werden.") from exc
    if result.status != "reanalyzed":
        raise HTTPException(status_code=404, detail="Vertrag oder Dokument nicht gefunden.")

    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        undone = service.proposals_by_id(session, undo_ids)
        reopened = _reopen_reviews(session, actor, contract, keys)
        entry = service.record_rollback(session, actor, contract, number, undone, entries, base_id)
        entry_number = entry.number
        session.commit()
    finally:
        session.close()
    skipped = sum(1 for item in entries if item["conflict"])
    message = f"Stand von Analyse #{number} wiederhergestellt: {len(keys)} Angabe(n) zurückgenommen."
    if skipped:
        message += f" {skipped} später geänderte Angabe(n) blieben unverändert."
    return {"number": entry_number, "restored": keys, "skipped": skipped, "reopened": reopened, "message": message}
