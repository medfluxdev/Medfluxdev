"""Fristen/Termine, Postfach, Vertretungen, Benachrichtigungs-Einstellungen und
Tageslauf-Monitoring (H5)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.auth.dependencies import current_actor
from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import Account, Contract
from app.database.models.deadlines import AccountDeputy, ContractDeadline, JobRun, NotificationOutbox
from app.database.scope_queries import scoped_contract_ids
from app.database.session import create_session
from app.deadlines.mail import smtp_configured
from app.deadlines.notify import JOB_NAME, run_daily
from app.deadlines.service import (
    DeadlineError,
    change_deadline_status,
    create_deputy,
    create_manual_deadline,
    deadline_payloads,
    inbox,
    list_contract_deadlines,
    list_deputies,
    log_activity_account,
    mark_read,
    notification_settings,
    update_deadline,
    update_notification_settings,
)
from app.deadlines.system import sync_system_deadlines
from app.register.service import RegisterActor

router = APIRouter(prefix="/api", tags=["deadlines"])

WRITE_ROLES = frozenset({"admin", "contract_manager"})
STALE_AFTER = timedelta(hours=26)


class DeadlineValues(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class DeadlineAction(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)


class DeputyCreate(BaseModel):
    account_id: Optional[UUID] = None
    deputy_account_id: UUID
    valid_from: date
    valid_to: date


class SettingsUpdate(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


def _actor(request: Request, organization_slug: str) -> RegisterActor:
    actor = current_actor(request, organization_slug)
    scope = current_scope_context()
    return RegisterActor(
        organization_id=actor.organization_id,
        account_id=actor.account_id,
        display_name=actor.display_name,
        role=actor.role,
        is_developer=bool(getattr(actor, "is_developer", False)),
        hospital_id=scope.hospital_id,
        department_id=scope.department_id,
    )


def _is_admin(actor: RegisterActor) -> bool:
    return actor.role == "admin" or actor.is_developer


def _require_write(actor: RegisterActor) -> None:
    if actor.role not in WRITE_ROLES and not actor.is_developer:
        raise HTTPException(status_code=403, detail="Keine Berechtigung zum Bearbeiten von Terminen.")


def _allowed(session, actor: RegisterActor) -> Optional[set[UUID]]:
    if _is_admin(actor):
        return None
    scope = current_scope_context()
    return scoped_contract_ids(session, actor.organization_id, scope.hospital_id, scope.department_id)


def _contract(session, actor: RegisterActor, contract_id: UUID) -> Contract:
    contract = session.get(Contract, contract_id)
    if contract is None or contract.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    allowed = _allowed(session, actor)
    if allowed is not None and contract.id not in allowed:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    return contract


def _deadline(session, actor: RegisterActor, deadline_id: UUID) -> tuple[ContractDeadline, Contract]:
    row = session.scalars(select(ContractDeadline).where(ContractDeadline.id == deadline_id).with_for_update()).first()
    if row is None or row.organization_id != actor.organization_id:
        raise HTTPException(status_code=404, detail="Termin nicht gefunden.")
    return row, _contract(session, actor, row.contract_id)


def _http(exc: DeadlineError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail_de)


# --------------------------------------------------------------------------- contract deadlines


@router.get("/contracts/{contract_id}/deadlines")
def get_contract_deadlines(contract_id: UUID, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        today = date.today()
        sync_system_deadlines(session, contract, today)
        session.commit()
        return {"items": list_contract_deadlines(session, contract, today)}
    finally:
        session.close()


@router.post("/contracts/{contract_id}/deadlines")
def post_contract_deadline(contract_id: UUID, payload: DeadlineValues, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        today = date.today()
        try:
            create_manual_deadline(session, contract=contract, actor=actor, values=payload.values, as_of=today)
        except DeadlineError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": list_contract_deadlines(session, contract, today)}
    finally:
        session.close()


@router.patch("/deadlines/{deadline_id}")
def patch_deadline(deadline_id: UUID, payload: DeadlineValues, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        row, contract = _deadline(session, actor, deadline_id)
        today = date.today()
        try:
            update_deadline(session, row=row, contract=contract, actor=actor, values=payload.values, as_of=today)
        except DeadlineError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": list_contract_deadlines(session, contract, today)}
    finally:
        session.close()


@router.post("/deadlines/{deadline_id}/{action}")
def deadline_action(deadline_id: UUID, action: str, payload: DeadlineAction, request: Request, organization_slug: str):
    if action not in ("done", "cancel", "reopen"):
        raise HTTPException(status_code=404, detail="Unbekannte Aktion.")
    actor = _actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        row, contract = _deadline(session, actor, deadline_id)
        today = date.today()
        try:
            change_deadline_status(session, row=row, contract=contract, actor=actor, action=action, note=payload.note)
        except DeadlineError as exc:
            session.rollback()
            raise _http(exc)
        if action == "done":
            sync_system_deadlines(session, contract, today)
        session.commit()
        return {"items": list_contract_deadlines(session, contract, today)}
    finally:
        session.close()


@router.get("/deadlines")
def list_deadlines(
    request: Request,
    organization_slug: str,
    status: str = Query(default="open", pattern="^(open|done|cancelled|all)$"),
    mine: bool = False,
    due_before: Optional[date] = None,
    limit: int = Query(default=200, ge=1, le=1000),
):
    """Wiedervorlage: Termine ueber alle sichtbaren Vertraege."""
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        today = date.today()
        stmt = (
            select(ContractDeadline)
            .join(Contract, Contract.id == ContractDeadline.contract_id)
            .where(ContractDeadline.organization_id == actor.organization_id, Contract.lifecycle_state == "active")
        )
        if status != "all":
            stmt = stmt.where(ContractDeadline.status == status)
        if mine:
            stmt = stmt.where(ContractDeadline.assignee_account_id == actor.account_id)
        if due_before is not None:
            stmt = stmt.where(ContractDeadline.due_date <= due_before)
        allowed = _allowed(session, actor)
        if allowed is not None:
            stmt = stmt.where(ContractDeadline.contract_id.in_(allowed))
        rows = list(session.scalars(stmt.order_by(ContractDeadline.due_date).limit(limit)).all())
        contracts = {
            row.id: row for row in session.scalars(select(Contract).where(Contract.id.in_({r.contract_id for r in rows}))).all()
        } if rows else {}
        return {"items": deadline_payloads(session, rows, today, contracts)}
    finally:
        session.close()


# --------------------------------------------------------------------------- inbox


@router.get("/inbox")
def get_inbox(request: Request, organization_slug: str, limit: int = Query(default=100, ge=1, le=500)):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        return inbox(session, actor=actor, as_of=date.today(), allowed_contract_ids=_allowed(session, actor), limit=limit)
    finally:
        session.close()


@router.post("/inbox/read-all")
def read_all(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        count = mark_read(session, actor=actor, notification_id=None)
        session.commit()
        return {"marked": count}
    finally:
        session.close()


@router.post("/inbox/{notification_id}/read")
def read_one(notification_id: UUID, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        count = mark_read(session, actor=actor, notification_id=notification_id)
        session.commit()
        return {"marked": count}
    finally:
        session.close()


# --------------------------------------------------------------------------- settings / deputies


@router.get("/me/notification-settings")
def get_settings(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        account = session.get(Account, actor.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Konto nicht gefunden.")
        return notification_settings(session, account, actor.organization_id, date.today())
    finally:
        session.close()


@router.put("/me/notification-settings")
def put_settings(payload: SettingsUpdate, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        account = session.get(Account, actor.account_id)
        if account is None:
            raise HTTPException(status_code=404, detail="Konto nicht gefunden.")
        unknown = set(payload.values) - {"receives_notifications", "receives_reminders", "default_deputy_account_id"}
        if unknown:
            raise HTTPException(status_code=422, detail="Unbekannte Einstellung.")
        try:
            update_notification_settings(session, account=account, actor=actor, values=payload.values)
        except DeadlineError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return notification_settings(session, account, actor.organization_id, date.today())
    finally:
        session.close()


@router.get("/deputies")
def get_deputies(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    session = create_session()
    try:
        return {"items": list_deputies(
            session, organization_id=actor.organization_id,
            account_id=None if _is_admin(actor) else actor.account_id, as_of=date.today(),
        )}
    finally:
        session.close()


@router.post("/deputies")
def post_deputy(payload: DeputyCreate, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_write(actor)
    account_id = payload.account_id or actor.account_id
    if account_id != actor.account_id and not _is_admin(actor):
        raise HTTPException(status_code=403, detail="Vertretungen für andere Personen pflegt die Administration.")
    session = create_session()
    try:
        try:
            create_deputy(
                session, actor=actor, account_id=account_id, deputy_account_id=payload.deputy_account_id,
                valid_from=payload.valid_from, valid_to=payload.valid_to,
            )
        except DeadlineError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": list_deputies(
            session, organization_id=actor.organization_id,
            account_id=None if _is_admin(actor) else actor.account_id, as_of=date.today(),
        )}
    finally:
        session.close()


@router.post("/deputies/{deputy_id}/deactivate")
def deactivate_deputy(deputy_id: UUID, request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        row = session.get(AccountDeputy, deputy_id)
        if row is None or row.organization_id != actor.organization_id:
            raise HTTPException(status_code=404, detail="Vertretung nicht gefunden.")
        if row.account_id != actor.account_id and not _is_admin(actor):
            raise HTTPException(status_code=403, detail="Vertretungen für andere Personen pflegt die Administration.")
        row.is_active = False
        log_activity_account(session, actor, "deputy.deactivated", {"deputy_id": str(row.id)})
        session.commit()
        return {"items": list_deputies(
            session, organization_id=actor.organization_id,
            account_id=None if _is_admin(actor) else actor.account_id, as_of=date.today(),
        )}
    finally:
        session.close()


# --------------------------------------------------------------------------- job monitoring


def _job_status(session, organization_id: UUID) -> dict:
    """Globale Laeufe ohne Zaehler (organisationsuebergreifend), eigene mit Zaehlern."""
    visible = (JobRun.job_name == JOB_NAME) & (
        JobRun.organization_id.is_(None) | (JobRun.organization_id == organization_id)
    )
    runs = session.scalars(select(JobRun).where(visible).order_by(JobRun.started_at.desc()).limit(10)).all()
    last_success = session.scalar(
        select(func.max(JobRun.finished_at)).where(
            JobRun.job_name == JOB_NAME, JobRun.status == "succeeded", JobRun.organization_id.is_(None)
        )
    )
    org_outbox = NotificationOutbox.organization_id == organization_id
    pending = session.scalar(
        select(func.count(NotificationOutbox.id)).where(org_outbox, NotificationOutbox.status == "pending")
    ) or 0
    failed = session.scalar(
        select(func.count(NotificationOutbox.id)).where(org_outbox, NotificationOutbox.status == "failed")
    ) or 0
    return {
        "scheduler_enabled": settings.reminder_scheduler_enabled,
        "run_hour": settings.reminder_run_hour,
        "smtp_configured": smtp_configured(),
        "last_success_at": last_success.isoformat() if last_success else None,
        "stale": last_success is None or datetime.now(timezone.utc) - last_success > STALE_AFTER,
        "emails_pending": pending,
        "emails_failed": failed,
        "runs": [
            {
                "id": str(run.id),
                "trigger": run.trigger,
                "host": run.host,
                "as_of_date": run.as_of_date.isoformat(),
                "status": run.status,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "scope": "organization" if run.organization_id else "global",
                "counts": (run.counts or {}) if run.organization_id else {},
                "error": run.error,
            }
            for run in runs
        ],
    }


@router.get("/jobs/daily")
def get_job_status(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    if not _is_admin(actor):
        raise HTTPException(status_code=403, detail="Nur für Administratoren.")
    session = create_session()
    try:
        return _job_status(session, actor.organization_id)
    finally:
        session.close()


@router.post("/jobs/daily/run")
def run_job_now(request: Request, organization_slug: str):
    actor = _actor(request, organization_slug)
    if not _is_admin(actor):
        raise HTTPException(status_code=403, detail="Nur für Administratoren.")
    result = run_daily(trigger="manual", organization_id=actor.organization_id)
    if result.skipped_locked:
        raise HTTPException(status_code=409, detail="Der Tageslauf läuft bereits.")
    session = create_session()
    try:
        return {"counts": result.counts, **_job_status(session, actor.organization_id)}
    finally:
        session.close()
