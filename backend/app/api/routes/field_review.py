"""Feldprüfung (Karte und geführte Prüfung teilen dieselben Werte): entscheiden, Nachweise wählen, Weitere Informationen.

- `POST /api/contracts/{id}/field-review/decide`   Kandidat übernehmen, Wert behalten, von Hand eintragen,
                                                    zurückstellen oder „nicht im Dokument“ festhalten
- `POST /api/contracts/{id}/field-review/evidence` Hauptnachweis wählen, Nachweis ausschließen oder wiederherstellen
- `POST /api/contracts/{id}/field-review/finding`  Weitere Information zuordnen, als Notiz sichern oder ausblenden

Den Wert eines Felds ändert allein die Faktprüfung (`_apply_fact_action`, derselbe Weg wie in den Karten). Alles
andere – gewählte Alternative, verworfene Kandidaten, Ausschlussgründe – steht im Ereignisprotokoll.
Jede Antwort ist das neu berechnete Detail des Vertrags, damit Karte und geführte Prüfung denselben Stand zeigen.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.api.routes.contracts import (
    _apply_fact_action,
    _build_augmented_detail,
    _not_found,
    _record_account_activity,
    _scope_denies,
    actor_org_mismatch,
)
from app.auth.context import reviewer_name
from app.contracts.detail.models import ContractDetailResponse
from app.contracts.detail.service import DetailError
from app.contracts.review.events import add_event
from app.contracts.review.field_actions import (
    check_version,
    finding_note_text,
    plan_decision,
    plan_evidence,
    plan_finding,
)
from app.contracts.review.service import ReviewConflict, ReviewError, complete_if_all_reviewed
from app.database.models import Contract
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/contracts", tags=["field-review"])


class FieldDecisionRequest(BaseModel):
    fact_key: str
    decision: str  # keep | accept | manual | defer | not_in_document
    candidate_key: Optional[str] = None
    value: Optional[str] = None
    note: Optional[str] = None
    #: Die Wertänderung wurde dem Nutzer ausdrücklich gezeigt und bestätigt (nötig, wenn ein anderer Kandidat gilt).
    confirm_change: bool = False
    #: Stand des Felds beim Laden (`version`); weicht er ab, antwortet der Server mit 409.
    expected_version: Optional[str] = None
    reviewer_display_name: Optional[str] = None


class FieldEvidenceRequest(BaseModel):
    fact_key: str
    evidence_id: str
    action: str  # primary | exclude | restore
    reason: Optional[str] = None
    note: Optional[str] = None
    expected_version: Optional[str] = None
    reviewer_display_name: Optional[str] = None


class FindingRequest(BaseModel):
    finding_key: str
    decision: str  # link | note | dismiss | restore
    target_fact_key: Optional[str] = None
    note: Optional[str] = None
    reviewer_display_name: Optional[str] = None


def _open(request: Request, organization_slug: str, contract_id: str):
    try:
        cid = UUID(contract_id)
    except ValueError:
        raise _not_found()
    session = create_session()
    org = get_organization(session, organization_slug)
    if org is None or actor_org_mismatch(request, org.id) or _scope_denies(session, org.id, cid):
        session.close()
        raise _not_found()
    return session, org, cid


def _lock(session, org, cid) -> Contract:
    """Gleichzeitige Entscheidungen am selben Vertrag laufen nacheinander."""
    contract = session.get(Contract, cid, with_for_update=True)
    if contract is None or contract.organization_id != org.id:
        raise _not_found()
    return contract


def _actor(request: Request, supplied: Optional[str]) -> tuple[Optional[object], str]:
    name = reviewer_name(request, supplied)
    if not (name or "").strip():
        raise ReviewError("Bitte den Namen der prüfenden Person angeben.")
    actor = getattr(request.state, "actor", None)
    return getattr(actor, "account_id", None), name.strip()


def _field(data: dict, fact_key: str) -> dict:
    field = next((item for item in (data.get("field_review") or {}).get("fields") or [] if item["fact_key"] == fact_key), None)
    if field is None:
        raise ReviewError("Diese Angabe gibt es in diesem Vertrag nicht.")
    return field


def _respond(session, org, cid) -> ContractDetailResponse:
    try:
        data = _build_augmented_detail(session, organization_id=org.id, contract_id=cid)
    except DetailError as exc:
        raise HTTPException(status_code=500, detail=exc.detail_de)
    if data is None:
        raise _not_found()
    return ContractDetailResponse.model_validate(data)


def _fresh(session, org, cid) -> dict:
    data = _build_augmented_detail(session, organization_id=org.id, contract_id=cid)
    if data is None:
        raise _not_found()
    return data


@router.post("/{contract_id}/field-review/decide", response_model=ContractDetailResponse)
def decide_field(request: Request, organization_slug: str, contract_id: str, payload: FieldDecisionRequest) -> ContractDetailResponse:
    session, org, cid = _open(request, organization_slug, contract_id)
    try:
        try:
            _lock(session, org, cid)
            account_id, name = _actor(request, payload.reviewer_display_name)
            data = _fresh(session, org, cid)
            field = _field(data, payload.fact_key)
            if "expected_version" in payload.model_fields_set:
                check_version(field, payload.expected_version)
            plan = plan_decision(
                field, payload.decision, candidate_key=payload.candidate_key, value=payload.value,
                note=payload.note, confirm_change=payload.confirm_change,
            )
            if plan.fact_action:
                _apply_fact_action(
                    request, organization_slug, session, org, cid, data, fact_key=payload.fact_key,
                    action=plan.fact_action, corrected_value=plan.corrected_value, note=plan.note,
                    reviewer_display_name=payload.reviewer_display_name,
                )
            add_event(
                session, organization_id=org.id, contract_id=cid, kind=plan.event_kind, fact_key=payload.fact_key,
                note=plan.note if plan.event_kind != "decision" else None,
                payload={
                    "decision": payload.decision, "chosen": plan.chosen, "previous": plan.previous,
                    "changes_value": plan.changes_value, "alternatives": plan.alternatives,
                } if plan.event_kind == "decision" else {"decision": payload.decision},
                actor_account_id=account_id, actor_name=name,
            )
            _record_account_activity(session, request, f"field_review.{payload.decision}", cid, {"fact_key": payload.fact_key})
            if plan.event_kind in ("decision", "not_in_document"):
                # Letzte wesentliche Angabe entschieden: „Wesentliche Prüfung abgeschlossen“ festhalten.
                session.flush()
                complete_if_all_reviewed(
                    session, organization_id=org.id, contract_id=cid, data=_fresh(session, org, cid), reviewer_display_name=name,
                )
            session.commit()
        except ReviewConflict as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=exc.detail_de)
        except ReviewError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        return _respond(session, org, cid)
    finally:
        session.close()


@router.post("/{contract_id}/field-review/evidence", response_model=ContractDetailResponse)
def field_evidence(request: Request, organization_slug: str, contract_id: str, payload: FieldEvidenceRequest) -> ContractDetailResponse:
    session, org, cid = _open(request, organization_slug, contract_id)
    try:
        try:
            _lock(session, org, cid)
            account_id, name = _actor(request, payload.reviewer_display_name)
            data = _fresh(session, org, cid)
            field = _field(data, payload.fact_key)
            if "expected_version" in payload.model_fields_set:
                check_version(field, payload.expected_version)
            kind, extra, note = plan_evidence(field, payload.evidence_id, payload.action, payload.reason, payload.note)
            add_event(
                session, organization_id=org.id, contract_id=cid, kind=kind, fact_key=payload.fact_key,
                evidence_id=payload.evidence_id, note=note, payload=extra, actor_account_id=account_id, actor_name=name,
            )
            _record_account_activity(session, request, f"field_review.evidence_{payload.action}", cid, {"fact_key": payload.fact_key})
            session.commit()
        except ReviewConflict as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=exc.detail_de)
        except ReviewError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        return _respond(session, org, cid)
    finally:
        session.close()


@router.post("/{contract_id}/field-review/finding", response_model=ContractDetailResponse)
def field_finding(request: Request, organization_slug: str, contract_id: str, payload: FindingRequest) -> ContractDetailResponse:
    session, org, cid = _open(request, organization_slug, contract_id)
    try:
        try:
            contract = _lock(session, org, cid)
            account_id, name = _actor(request, payload.reviewer_display_name)
            data = _fresh(session, org, cid)
            review = data.get("field_review") or {}
            finding = next((item for item in review.get("findings") or [] if item["finding_key"] == payload.finding_key), None)
            if finding is None:
                raise ReviewError("Diese Information gibt es in diesem Vertrag nicht.")
            kind, extra, note = plan_finding(finding, review.get("fields") or [], payload.decision, payload.target_fact_key, payload.note)
            if kind == "finding_note":
                from app.api.routes.contract_register import _register_actor, _require_write
                from app.register.service import RegisterError, add_remark

                actor = _register_actor(request, organization_slug)
                _require_write(actor, "remark.add")
                try:
                    remark = add_remark(session, contract=contract, actor=actor, body=finding_note_text(finding) + (f"\n{note}" if note else ""))
                except RegisterError as exc:
                    raise ReviewError(exc.detail_de) from exc
                extra = {**extra, "remark_id": str(remark.id)}
            add_event(
                session, organization_id=org.id, contract_id=cid, kind=kind, fact_key=payload.finding_key,
                evidence_id=finding.get("evidence_id"), note=note, payload=extra, actor_account_id=account_id, actor_name=name,
            )
            _record_account_activity(session, request, f"field_review.{kind}", cid, {"finding": payload.finding_key})
            session.commit()
        except ReviewConflict as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=exc.detail_de)
        except ReviewError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        return _respond(session, org, cid)
    finally:
        session.close()
