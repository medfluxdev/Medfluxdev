"""Operational lifecycle workflows for contracts and equipment.

These endpoints capture human operational decisions. They do not overwrite
accepted extraction truth or deterministic contract status.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.clock import today_local
from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import (
    Contract,
    ContractLifecycleDecision,
    Equipment,
    EquipmentLifecycleRecord,
)
from app.database.models.activity_log import ActivityLog
from app.database.models.deadlines import ContractDeadline
from app.database.models.lifecycle import CONTRACT_DECISIONS, DECISION_STATUS, EQUIPMENT_LIFECYCLE
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session
from app.deadlines.service import DeadlineError, change_deadline_status, create_manual_deadline, update_deadline
from app.register.service import RegisterActor
from app.reports.decision_steps import STEP_KEYS, decision_steps
from app.reports.renewal import step_facts

router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])
MANAGE_ROLES = {"admin", "contract_manager"}


class DecisionReminder(BaseModel):
    """Erinnerung zur Entscheidung: ein normaler Termin unter „Fristen & Aufgaben“."""

    title: str = Field(min_length=1, max_length=200)
    due_date: date
    kind: str | None = None
    todo_text: str | None = Field(default=None, max_length=500)


class ContractDecisionCreate(BaseModel):
    decision: str
    status: str = "planned"
    effective_date: date | None = None
    note: str | None = Field(default=None, max_length=4000)
    reminder: DecisionReminder | None = None


class ContractDecisionUpdate(BaseModel):
    status: str
    # Optional: die Entscheidung selbst nachtraeglich aendern (z. B. Beobachten -> Kuendigen).
    decision: str | None = None
    effective_date: date | None = None
    note: str | None = Field(default=None, max_length=4000)
    # Erinnerung anlegen bzw. die verknuepfte offene Erinnerung aendern; remove_reminder bricht sie ab.
    reminder: DecisionReminder | None = None
    remove_reminder: bool = False


class DecisionStepUpdate(BaseModel):
    done: bool


class EquipmentLifecycleUpdate(BaseModel):
    status: str
    next_service_date: date | None = None
    note: str | None = Field(default=None, max_length=4000)


def _actor_or_forbid(request: Request):
    actor = getattr(request.state, "actor", None)
    if not settings.auth_enabled:
        return actor
    if actor is None:
        raise HTTPException(status_code=401, detail="Anmeldung erforderlich.")
    if not actor.is_developer and (actor.role or "").casefold() not in MANAGE_ROLES:
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Aktion.")
    return actor


def _org(session, slug: str, request: Request):
    org = get_organization(session, slug)
    actor = getattr(request.state, "actor", None)
    if org is None or (actor is None and settings.auth_enabled) or (actor is not None and actor.organization_id != org.id):
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    return org


def _require_contract(session, org_id: UUID, contract_id: UUID):
    row = session.get(Contract, contract_id)
    if row is None or row.organization_id != org_id or row.lifecycle_state != "active" or row.is_archived:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    scope = current_scope_context()
    allowed = scoped_contract_ids(session, org_id, scope.hospital_id, scope.department_id)
    if allowed is not None and contract_id not in allowed:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    return row, scope


def _require_equipment(session, org_id: UUID, equipment_id: UUID):
    row = session.get(Equipment, equipment_id)
    if row is None or row.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
    scope = current_scope_context()
    if scope.department_id is not None and row.department_id != scope.department_id:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
    if scope.department_id is None and scope.hospital_id is not None and row.hospital_id != scope.hospital_id:
        raise HTTPException(status_code=404, detail="Gerät nicht gefunden.")
    return row, scope


def _log(session, actor, scope, contract_id, event_name: str, context: dict) -> None:
    if actor is None:
        return
    session.add(ActivityLog(
        organization_id=actor.organization_id,
        hospital_id=scope.hospital_id,
        department_id=scope.department_id,
        account_id=actor.account_id,
        display_name_snapshot=actor.display_name,
        role_snapshot="developer" if actor.is_developer else actor.role,
        event_name=event_name,
        object_type="contract",
        object_id=contract_id,
        context_data=context,
    ))


def _current_end(contract) -> date | None:
    from app.register.service import term_inputs
    from app.register.terms import compute_terms

    terms = compute_terms(term_inputs(contract), today_local())
    return terms.actual_end or terms.possible_end


def _require_decision(session, org_id: UUID, contract_id: UUID, decision_id: UUID) -> ContractLifecycleDecision:
    row = session.get(ContractLifecycleDecision, decision_id)
    if row is None or row.organization_id != org_id or row.contract_id != contract_id:
        raise HTTPException(status_code=404, detail="Lifecycle-Entscheidung nicht gefunden.")
    return row


def _register_actor(actor, org_id: UUID, scope) -> RegisterActor:
    return RegisterActor(
        organization_id=org_id,
        account_id=getattr(actor, "account_id", None),
        display_name=getattr(actor, "display_name", None) or "local-development",
        role=getattr(actor, "role", None) or "admin",
        is_developer=bool(getattr(actor, "is_developer", False)),
        hospital_id=scope.hospital_id,
        department_id=scope.department_id,
    )


def _linked_reminder(session, row: ContractLifecycleDecision) -> ContractDeadline | None:
    if row.reminder_deadline_id is None:
        return None
    deadline = session.get(ContractDeadline, row.reminder_deadline_id)
    if deadline is None or deadline.contract_id != row.contract_id:
        return None
    return deadline


def _reminder_values(reminder: DecisionReminder, current: ContractDeadline | None = None) -> dict:
    values = {"title": reminder.title.strip(), "due_date": reminder.due_date.isoformat()}
    if reminder.todo_text is not None:
        values["todo_text"] = reminder.todo_text
    if current is None:
        values.update({"kind": reminder.kind or "pruefung", "send_email": True})
    elif current.remind_on == current.due_date or current.remind_on > reminder.due_date:
        # Erinnern am Faelligkeitstag wandert mit; ein eigenes frueheres Datum bleibt.
        values["remind_on"] = reminder.due_date.isoformat()
    return values


def _create_reminder(session, *, contract, actor: RegisterActor, reminder: DecisionReminder) -> ContractDeadline:
    """Neue Erinnerung – oder der gleiche offene Termin, falls schon vorhanden (kein Duplikat)."""
    existing = session.scalars(select(ContractDeadline).where(
        ContractDeadline.contract_id == contract.id,
        ContractDeadline.source == "manual",
        ContractDeadline.status == "open",
        ContractDeadline.title == reminder.title.strip(),
        ContractDeadline.due_date == reminder.due_date,
    )).first()
    if existing is not None:
        return existing
    return create_manual_deadline(session, contract=contract, actor=actor, values=_reminder_values(reminder), as_of=today_local())


def _cancel_reminder(session, *, decision: ContractLifecycleDecision, reminder: ContractDeadline | None, contract, actor: RegisterActor, note: str) -> None:
    """Offene Erinnerung abbrechen, wenn keine andere Entscheidung sie noch nutzt."""
    if reminder is None or reminder.status != "open" or reminder.source != "manual":
        return
    shared = session.scalar(select(ContractLifecycleDecision.id).where(
        ContractLifecycleDecision.reminder_deadline_id == reminder.id,
        ContractLifecycleDecision.id != decision.id,
    ))
    if shared is None:
        change_deadline_status(session, row=reminder, contract=contract, actor=actor, action="cancel", note=note)


def _deadline_http(exc: DeadlineError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail_de)


def _reminder_payload(deadline: ContractDeadline | None) -> dict | None:
    if deadline is None:
        return None
    return {"id": str(deadline.id), "title": deadline.title, "due_date": deadline.due_date, "status": deadline.status}


def _decision_payload(row: ContractLifecycleDecision, reminder: ContractDeadline | None = None, steps: list[dict] | None = None) -> dict:
    return {
        "steps": steps,
        "id": str(row.id),
        "contract_id": str(row.contract_id),
        "decision": row.decision,
        "status": row.status,
        "effective_date": row.effective_date,
        "note": row.note,
        "actor_display_name": row.actor_display_name,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "reminder": _reminder_payload(reminder),
    }


def _steps(session, contract, row: ContractLifecycleDecision, reminder: ContractDeadline | None, as_of: date) -> list[dict] | None:
    """Umsetzungsschritte nur für offene Entscheidungen (geplant / in Bearbeitung)."""
    if row.status not in ("planned", "in_progress"):
        return None
    return decision_steps(step_facts(session, contract, row, reminder, as_of))


@router.get("/contracts/{contract_id}")
def contract_lifecycle(request: Request, organization_slug: str, contract_id: UUID):
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        _require_contract(session, org.id, contract_id)
        rows = session.scalars(
            select(ContractLifecycleDecision).where(
                ContractLifecycleDecision.organization_id == org.id,
                ContractLifecycleDecision.contract_id == contract_id,
            ).order_by(ContractLifecycleDecision.created_at.desc())
        ).all()
        reminder_ids = {row.reminder_deadline_id for row in rows if row.reminder_deadline_id is not None}
        reminders = {
            deadline.id: deadline
            for deadline in session.scalars(select(ContractDeadline).where(ContractDeadline.id.in_(reminder_ids)))
        } if reminder_ids else {}
        contract = session.get(Contract, contract_id)
        today = today_local()
        return {"items": [
            _decision_payload(row, reminders.get(row.reminder_deadline_id), _steps(session, contract, row, reminders.get(row.reminder_deadline_id), today))
            for row in rows
        ]}
    finally:
        session.close()


@router.post("/contracts/{contract_id}")
def create_contract_decision(request: Request, organization_slug: str, contract_id: UUID, body: ContractDecisionCreate):
    actor = _actor_or_forbid(request)
    decision = body.decision.casefold().strip()
    status = body.status.casefold().strip()
    if decision not in CONTRACT_DECISIONS or status not in DECISION_STATUS:
        raise HTTPException(status_code=422, detail="Ungültige Lifecycle-Angaben.")
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        contract, scope = _require_contract(session, org.id, contract_id)
        display_name = getattr(actor, "display_name", None) or "local-development"
        row = ContractLifecycleDecision(
            organization_id=org.id,
            contract_id=contract_id,
            decision=decision,
            status=status,
            effective_date=body.effective_date,
            note=body.note,
            actor_account_id=getattr(actor, "account_id", None),
            actor_display_name=display_name,
            baseline_end=_current_end(contract),
            steps_done={},
        )
        session.add(row)
        reminder = None
        if body.reminder is not None:
            # Entscheidung und Erinnerung in einem Schritt: beides oder nichts.
            try:
                reminder = _create_reminder(session, contract=contract, actor=_register_actor(actor, org.id, scope), reminder=body.reminder)
            except DeadlineError as exc:
                session.rollback()
                raise _deadline_http(exc)
            row.reminder_deadline_id = reminder.id
        _log(session, actor, scope, contract_id, "contract.lifecycle_decision_created",
             {"decision": decision, "status": status, "effective_date": body.effective_date.isoformat() if body.effective_date else None,
              "reminder_deadline_id": str(reminder.id) if reminder is not None else None})
        session.commit()
        return _decision_payload(row, reminder, _steps(session, contract, row, reminder, today_local()))
    finally:
        session.close()


@router.post("/contracts/{contract_id}/{decision_id}/steps/{step_key}")
def update_decision_step(request: Request, organization_slug: str, contract_id: UUID, decision_id: UUID, step_key: str, body: DecisionStepUpdate):
    """Einen Umsetzungsschritt abhaken bzw. zurücknehmen; der erste Haken setzt „in Bearbeitung“."""
    actor = _actor_or_forbid(request)
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        contract, scope = _require_contract(session, org.id, contract_id)
        row = _require_decision(session, org.id, contract_id, decision_id)
        if row.status not in ("planned", "in_progress"):
            raise HTTPException(status_code=409, detail="Die Entscheidung ist bereits abgeschlossen oder storniert.")
        if step_key not in STEP_KEYS.get(row.decision, set()):
            raise HTTPException(status_code=404, detail="Schritt nicht gefunden.")
        done = dict(row.steps_done or {})
        name = getattr(actor, "display_name", None) or "local-development"
        if body.done:
            done[step_key] = {"by": name, "at": datetime.now(timezone.utc).isoformat()}
        else:
            done.pop(step_key, None)
        row.steps_done = done
        if body.done and row.status == "planned":
            row.status = "in_progress"
        _log(session, actor, scope, contract_id, "contract.lifecycle_step_done" if body.done else "contract.lifecycle_step_undone",
             {"decision_id": str(row.id), "decision": row.decision, "step": step_key})
        reminder = _linked_reminder(session, row)
        session.commit()
        return _decision_payload(row, reminder, _steps(session, contract, row, reminder, today_local()))
    finally:
        session.close()


@router.patch("/contracts/{contract_id}/{decision_id}")
def update_contract_decision(request: Request, organization_slug: str, contract_id: UUID, decision_id: UUID, body: ContractDecisionUpdate):
    actor = _actor_or_forbid(request)
    status = body.status.casefold().strip()
    decision = body.decision.casefold().strip() if body.decision else None
    if status not in DECISION_STATUS:
        raise HTTPException(status_code=422, detail="Ungültiger Lifecycle-Status.")
    if decision is not None and decision not in CONTRACT_DECISIONS:
        raise HTTPException(status_code=422, detail="Ungültige Lifecycle-Angaben.")
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        contract, scope = _require_contract(session, org.id, contract_id)
        row = _require_decision(session, org.id, contract_id, decision_id)
        previous = row.status
        before = {"decision": row.decision, "effective_date": row.effective_date, "note": row.note}
        row.status = status
        if decision is not None:
            row.decision = decision
        row.effective_date = body.effective_date
        row.note = body.note
        if previous != status:
            _log(session, actor, scope, contract_id, f"contract.lifecycle_{status}",
                 {"decision_id": str(row.id), "decision": row.decision, "previous_status": previous, "status": status})
        changed = [key for key, value in before.items() if value != getattr(row, key)]
        if changed:
            _log(session, actor, scope, contract_id, "contract.lifecycle_decision_updated", {
                "decision_id": str(row.id),
                "changed": changed,
                "previous_decision": before["decision"],
                "decision": row.decision,
                "previous_effective_date": before["effective_date"].isoformat() if before["effective_date"] else None,
                "effective_date": row.effective_date.isoformat() if row.effective_date else None,
            })
        reminder = _linked_reminder(session, row)
        register_actor = _register_actor(actor, org.id, scope)
        try:
            if body.remove_reminder:
                _cancel_reminder(session, decision=row, reminder=reminder, contract=contract, actor=register_actor,
                                 note="Mit der Entscheidung entfernt.")
                row.reminder_deadline_id = None
                reminder = None
            elif body.reminder is not None:
                if reminder is not None and reminder.status == "open":
                    update_deadline(session, row=reminder, contract=contract, actor=register_actor,
                                    values=_reminder_values(body.reminder, reminder), as_of=today_local())
                else:
                    reminder = _create_reminder(session, contract=contract, actor=register_actor, reminder=body.reminder)
                    row.reminder_deadline_id = reminder.id
        except DeadlineError as exc:
            session.rollback()
            raise _deadline_http(exc)
        session.commit()
        return _decision_payload(row, reminder, _steps(session, contract, row, reminder, today_local()))
    finally:
        session.close()


@router.delete("/contracts/{contract_id}/{decision_id}")
def delete_contract_decision(request: Request, organization_slug: str, contract_id: UUID, decision_id: UUID, keep_reminder: bool = False):
    """Irrtuemlich erfasste Entscheidung entfernen; das Protokoll behaelt, was geloescht wurde.
    Die offene Erinnerung dazu wird abgebrochen, ausser keep_reminder."""
    actor = _actor_or_forbid(request)
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        contract, scope = _require_contract(session, org.id, contract_id)
        row = _require_decision(session, org.id, contract_id, decision_id)
        reminder = _linked_reminder(session, row)
        if not keep_reminder:
            _cancel_reminder(session, decision=row, reminder=reminder, contract=contract,
                             actor=_register_actor(actor, org.id, scope), note="Mit der Entscheidung gelöscht.")
        _log(session, actor, scope, contract_id, "contract.lifecycle_decision_deleted", {
            "decision_id": str(row.id),
            "decision": row.decision,
            "status": row.status,
            "effective_date": row.effective_date.isoformat() if row.effective_date else None,
            "created_by": row.actor_display_name,
        })
        session.delete(row)
        session.commit()
        return {"deleted": True, "id": str(decision_id)}
    finally:
        session.close()


@router.get("/equipment/{equipment_id}")
def equipment_lifecycle(request: Request, organization_slug: str, equipment_id: UUID):
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        _require_equipment(session, org.id, equipment_id)
        row = session.scalars(select(EquipmentLifecycleRecord).where(
            EquipmentLifecycleRecord.organization_id == org.id,
            EquipmentLifecycleRecord.equipment_id == equipment_id,
        )).first()
        if row is None:
            return {"equipment_id": str(equipment_id), "status": "active", "next_service_date": None, "note": None, "updated_by_display_name": None, "updated_at": None}
        return {"equipment_id": str(row.equipment_id), "status": row.status, "next_service_date": row.next_service_date, "note": row.note, "updated_by_display_name": row.updated_by_display_name, "updated_at": row.updated_at}
    finally:
        session.close()


@router.put("/equipment/{equipment_id}")
def update_equipment_lifecycle(request: Request, organization_slug: str, equipment_id: UUID, body: EquipmentLifecycleUpdate):
    actor = _actor_or_forbid(request)
    status = body.status.casefold().strip()
    if status not in EQUIPMENT_LIFECYCLE:
        raise HTTPException(status_code=422, detail="Ungültiger Geräte-Lifecycle-Status.")
    session = create_session()
    try:
        org = _org(session, organization_slug, request)
        _, scope = _require_equipment(session, org.id, equipment_id)
        row = session.scalars(select(EquipmentLifecycleRecord).where(EquipmentLifecycleRecord.equipment_id == equipment_id)).first()
        display_name = getattr(actor, "display_name", None) or "local-development"
        if row is None:
            row = EquipmentLifecycleRecord(organization_id=org.id, equipment_id=equipment_id, status=status, updated_by_account_id=getattr(actor, "account_id", None), updated_by_display_name=display_name)
            session.add(row)
            previous = None
        else:
            previous = row.status
            row.status = status
            row.updated_by_account_id = getattr(actor, "account_id", None)
            row.updated_by_display_name = display_name
        row.next_service_date = body.next_service_date
        row.note = body.note
        if actor is not None:
            session.add(ActivityLog(
                organization_id=actor.organization_id,
                hospital_id=scope.hospital_id,
                department_id=scope.department_id,
                account_id=actor.account_id,
                display_name_snapshot=actor.display_name,
                role_snapshot="developer" if actor.is_developer else actor.role,
                event_name=f"equipment.lifecycle_{status}",
                object_type="equipment",
                object_id=equipment_id,
                context_data={"previous_status": previous, "status": status, "next_service_date": body.next_service_date.isoformat() if body.next_service_date else None},
            ))
        session.commit()
        return {"equipment_id": str(row.equipment_id), "status": row.status, "next_service_date": row.next_service_date, "note": row.note, "updated_by_display_name": row.updated_by_display_name, "updated_at": row.updated_at}
    finally:
        session.close()
