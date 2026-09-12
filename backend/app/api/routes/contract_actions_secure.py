from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.auth.service import require_role
from app.contracts.detail.models import ContractDetailResponse
from app.contracts.detail.service import build_contract_detail
from app.contracts.overrides.service import OverrideError, record_override
from app.contracts.review.material import material_report
from app.contracts.review.service import (
    ReviewError,
    build_fact_review_states,
    build_review_summary,
    complete_review,
    record_fact_action,
    start_review,
)
from app.api.routes.contracts import (
    FactReviewRequest,
    OverrideRequest,
    ReviewLifecycleRequest,
    _augmented_detail_response,
    _canonical_override_value,
    _not_found,
    _set_archived,
    _workspace_denies,
)
from app.database.models.activity_log import ActivityLog
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/contracts", tags=["contracts-authenticated"])


def _actor(request: Request, *, allowed: tuple[str, ...]):
    actor = getattr(request.state, "actor", None)
    if actor is None:
        raise HTTPException(status_code=401, detail="Bitte anmelden.")
    try:
        require_role(actor, *allowed)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return actor


def _cid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError:
        raise _not_found()


def _log(session, actor, event_name: str, contract_id: UUID, context_data: dict | None = None) -> None:
    session.add(ActivityLog(
        organization_id=actor.organization_id,
        account_id=actor.account_id,
        display_name_snapshot=actor.display_name,
        role_snapshot=actor.role,
        event_name=event_name,
        object_type="contract",
        object_id=contract_id,
        context_data=context_data,
    ))
    session.flush()


@router.post("/{contract_id}/fact-reviews", response_model=ContractDetailResponse)
def fact_review(request: Request, organization_slug: str, contract_id: str, payload: FactReviewRequest):
    actor = _actor(request, allowed=("admin", "contract_manager", "reviewer"))
    cid = _cid(contract_id)
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or org.id != actor.organization_id or _workspace_denies(session, cid):
            raise _not_found()
        data = build_contract_detail(session, organization_id=org.id, contract_id=cid)
        if data is None:
            raise _not_found()
        system_value = payload.system_value
        if system_value is None:
            system_value = (material_report(data).get(payload.fact_key) or {}).get("value")
        try:
            row = record_fact_action(
                session,
                organization_id=org.id,
                contract_id=cid,
                fact_key=payload.fact_key,
                action=payload.action,
                reviewer_display_name=actor.display_name,
                note=payload.note,
                system_value=system_value,
                corrected_value=payload.corrected_value,
                evidence_ref=payload.evidence_ref,
            )
            row.reviewer_identity_type = "authenticated_account"
            row.authenticated_actor_id = actor.account_id
            row.actor_role_snapshot = actor.role
            _log(session, actor, f"fact_review.{payload.action}", cid, {"fact_key": payload.fact_key})
            session.commit()
        except ReviewError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()


@router.post("/{contract_id}/review/start", response_model=ContractDetailResponse)
def review_start(request: Request, organization_slug: str, contract_id: str, payload: ReviewLifecycleRequest):
    actor = _actor(request, allowed=("admin", "contract_manager", "reviewer"))
    cid = _cid(contract_id)
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or org.id != actor.organization_id or _workspace_denies(session, cid):
            raise _not_found()
        try:
            row = start_review(session, organization_id=org.id, contract_id=cid, reviewer_display_name=actor.display_name, note=payload.note)
            row.reviewer_identity_type = "authenticated_account"
            row.authenticated_actor_id = actor.account_id
            row.actor_role_snapshot = actor.role
            _log(session, actor, "contract_review.started", cid)
            session.commit()
        except ReviewError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()


@router.post("/{contract_id}/review/complete", response_model=ContractDetailResponse)
def review_complete(request: Request, organization_slug: str, contract_id: str, payload: ReviewLifecycleRequest):
    actor = _actor(request, allowed=("admin", "contract_manager", "reviewer"))
    cid = _cid(contract_id)
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or org.id != actor.organization_id or _workspace_denies(session, cid):
            raise _not_found()
        data = build_contract_detail(session, organization_id=org.id, contract_id=cid)
        if data is None:
            raise _not_found()
        states = build_fact_review_states(session, organization_id=org.id, contract_id=cid, data=data)
        summary = build_review_summary(states)
        try:
            row = complete_review(
                session,
                organization_id=org.id,
                contract_id=cid,
                reviewer_display_name=actor.display_name,
                note=payload.note,
                acknowledge_unreviewed=payload.acknowledge_unreviewed,
                relevant_count=summary["relevant_count"],
                reviewed_count=summary["reviewed_count"],
            )
            row.reviewer_identity_type = "authenticated_account"
            row.authenticated_actor_id = actor.account_id
            row.actor_role_snapshot = actor.role
            _log(session, actor, "contract_review.completed", cid, {"acknowledge_unreviewed": bool(payload.acknowledge_unreviewed)})
            session.commit()
        except ReviewError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()


@router.post("/{contract_id}/overrides", response_model=ContractDetailResponse)
def override(request: Request, organization_slug: str, contract_id: str, payload: OverrideRequest):
    actor = _actor(request, allowed=("admin", "contract_manager"))
    cid = _cid(contract_id)
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or org.id != actor.organization_id:
            raise _not_found()
        try:
            value = _canonical_override_value(payload.key, payload.value) if payload.action == "set" else None
            row = record_override(
                session,
                organization_id=org.id,
                contract_id=cid,
                key=payload.key,
                action=payload.action,
                value=value,
                fact_ref=payload.fact_ref,
                note=payload.note,
            )
            row.actor_id = actor.account_id
            row.actor_type = "authenticated_account"
            row.actor_display_name_snapshot = actor.display_name
            row.actor_role_snapshot = actor.role
            row.is_development = False
            _log(session, actor, f"override.{payload.action}", cid, {"key": payload.key, "fact_ref": payload.fact_ref})
            session.commit()
        except OverrideError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()


@router.post("/{contract_id}/archive", response_model=ContractDetailResponse)
def archive(request: Request, organization_slug: str, contract_id: str):
    actor = _actor(request, allowed=("admin", "contract_manager"))
    cid = _cid(contract_id)
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or org.id != actor.organization_id:
            raise _not_found()
        _set_archived(session, org.id, cid, True)
        _log(session, actor, "contract.archived", cid)
        session.commit()
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()


@router.post("/{contract_id}/unarchive", response_model=ContractDetailResponse)
def unarchive(request: Request, organization_slug: str, contract_id: str):
    actor = _actor(request, allowed=("admin", "contract_manager"))
    cid = _cid(contract_id)
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or org.id != actor.organization_id:
            raise _not_found()
        _set_archived(session, org.id, cid, False)
        _log(session, actor, "contract.unarchived", cid)
        session.commit()
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()
