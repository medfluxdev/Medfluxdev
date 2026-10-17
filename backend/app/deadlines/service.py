"""Termine anlegen/bearbeiten/erledigen, Postfach, Vertretungen, Einstellungen (H5)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database.models import Account, AccountMembership, ActivityLog, Contract
from app.database.models.deadlines import AccountDeputy, ContractDeadline, Notification
from app.database.models.register import ContractFieldProvenance
from app.deadlines.notify import active_deputy, deputized_account_ids, notify
from app.deadlines.system import TERM_BASIS_FIELDS, sync_system_deadlines
from app.register.reminders import normalize_leads, schedule
from app.register.service import RegisterActor, log_activity

EDITABLE_MANUAL = ("kind", "title", "due_date", "remind_on", "assignee_account_id", "escalation_account_id",
                   "todo_text", "note", "send_email", "send_ics", "reminder_leads")
# Systemtermine: das Datum kommt aus den Vertragsdaten. Was zu tun ist, wer erinnert wird und wann,
# lässt sich je Termin anpassen („Erinnerung anpassen“); leer = wieder der Vertrag.
EDITABLE_SYSTEM = ("todo_text", "assignee_account_id", "reminder_leads", "note", "send_email", "send_ics")
# Am Systemtermin gesetzte Werte, die der Fristenabgleich stehen lässt (contract_deadline.overrides).
SYSTEM_OVERRIDABLE = ("todo_text", "assignee_account_id")


class DeadlineError(ValueError):
    def __init__(self, status_code: int, detail_de: str):
        super().__init__(detail_de)
        self.status_code = status_code
        self.detail_de = detail_de


def _date(value: Any, label: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise DeadlineError(422, f"{label}: Datum im Format JJJJ-MM-TT erwartet.")


def _text(value: Any, label: str, max_length: int, required: bool = False) -> Optional[str]:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise DeadlineError(422, f"{label} ist erforderlich.")
        return None
    if not isinstance(value, str):
        raise DeadlineError(422, f"{label}: Text erwartet.")
    if len(value.strip()) > max_length:
        raise DeadlineError(422, f"{label}: höchstens {max_length} Zeichen.")
    return value.strip()


def _member(session: Session, organization_id: uuid.UUID, value: Any, label: str) -> Optional[uuid.UUID]:
    if value in (None, ""):
        return None
    try:
        account_id = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except ValueError:
        raise DeadlineError(422, f"{label}: ungültige Auswahl.")
    found = session.scalar(
        select(AccountMembership.id)
        .join(Account, Account.id == AccountMembership.account_id)
        .where(
            AccountMembership.account_id == account_id,
            AccountMembership.organization_id == organization_id,
            AccountMembership.is_active.is_(True),
            Account.is_active.is_(True),
        )
    )
    if found is None:
        raise DeadlineError(422, f"{label}: Benutzer ist für diese Organisation nicht verfügbar.")
    return account_id


def _clean(session: Session, organization_id: uuid.UUID, values: dict[str, Any], allowed: tuple[str, ...]) -> dict[str, Any]:
    unknown = [key for key in values if key not in allowed]
    if unknown:
        raise DeadlineError(422, f"Nicht bearbeitbar: {', '.join(unknown)}.")
    out: dict[str, Any] = {}
    for key, value in values.items():
        if key == "kind":
            out[key] = _text(value, "Art", 64, required=True)
        elif key == "title":
            out[key] = _text(value, "Bezeichnung", 255, required=True)
        elif key in ("due_date", "remind_on"):
            out[key] = _date(value, "Fällig am" if key == "due_date" else "Erinnern am")
        elif key in ("assignee_account_id", "escalation_account_id"):
            out[key] = _member(session, organization_id, value, "Zuständig" if key == "assignee_account_id" else "Eskalation an")
        elif key == "todo_text":
            out[key] = _text(value, "Was zu tun ist", 500)
        elif key == "reminder_leads":
            # Erinnerungen je Termin: Liste (auch leer = nur am Termin selbst) oder None = wieder der Vertrag.
            try:
                out[key] = None if value is None else normalize_leads(value)
            except ValueError as exc:
                raise DeadlineError(422, str(exc)) from exc
        elif key == "note":
            out[key] = _text(value, "Bemerkung", 5000)
        elif key in ("send_email", "send_ics"):
            if not isinstance(value, bool):
                raise DeadlineError(422, "Ja/Nein erwartet.")
            out[key] = value
    return out


def basis_unconfirmed(session: Session, contract_id: uuid.UUID) -> bool:
    """Beruht die Fristberechnung auf noch nicht bestaetigten KI-Werten?"""
    return session.scalar(
        select(ContractFieldProvenance.id).where(
            ContractFieldProvenance.contract_id == contract_id,
            ContractFieldProvenance.field_key.in_(TERM_BASIS_FIELDS),
            ContractFieldProvenance.origin == "ai",
        ).limit(1)
    ) is not None


def _names(session: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict(session.execute(select(Account.id, Account.display_name).where(Account.id.in_(ids))).all())


def deadline_payloads(session: Session, rows: list[ContractDeadline], as_of: date, contracts: Optional[dict] = None) -> list[dict]:
    names = _names(session, {
        value for row in rows for value in (row.assignee_account_id, row.escalation_account_id) if value
    })
    # Eskalation nur zeigen, wenn sie wirklich ausgeloest wurde (Benachrichtigung verschickt).
    escalated = dict(session.execute(
        select(Notification.deadline_id, func.min(Notification.created_at))
        .where(Notification.deadline_id.in_([row.id for row in rows]), Notification.kind == "deadline_escalation")
        .group_by(Notification.deadline_id)
    ).all()) if rows else {}
    unconfirmed = {
        contract_id for contract_id in {row.contract_id for row in rows if row.source == "system"}
        if basis_unconfirmed(session, contract_id)
    }
    out = []
    for row in rows:
        contract = (contracts or {}).get(row.contract_id)
        out.append({
            "id": str(row.id),
            "contract_id": str(row.contract_id),
            "contract_label": (
                f"{contract.register_number or contract.contract_number or '–'} · {contract.short_description or contract.supplier or 'Vertrag'}"
                if contract is not None else None
            ),
            "source": row.source,
            "system_key": row.system_key,
            "kind": row.kind,
            "title": row.title,
            "due_date": row.due_date.isoformat(),
            "remind_on": row.remind_on.isoformat(),
            "extra_remind_on": list(row.extra_remind_on or []),
            "days_until_due": (row.due_date - as_of).days,
            "overdue": row.status == "open" and row.due_date < as_of,
            "assignee_account_id": str(row.assignee_account_id) if row.assignee_account_id else None,
            "assignee_name": names.get(row.assignee_account_id),
            "escalation_account_id": str(row.escalation_account_id) if row.escalation_account_id else None,
            "escalation_name": names.get(row.escalation_account_id),
            "escalated_at": escalated[row.id].isoformat() if row.id in escalated else None,
            "todo_text": row.todo_text,
            "note": row.note,
            "status": row.status,
            "send_email": row.send_email,
            "send_ics": row.send_ics,
            "done_by_name": row.done_by_name,
            "done_at": row.done_at.isoformat() if row.done_at else None,
            "basis_unconfirmed": row.contract_id in unconfirmed and row.source == "system",
            "custom_fields": sorted((row.overrides or {}).keys()),
            "reminder_leads": (row.overrides or {}).get("reminder_leads"),
            "escalate_on": row.escalate_on.isoformat() if row.escalate_on else None,
            "editable_fields": list(EDITABLE_SYSTEM if row.source == "system" else EDITABLE_MANUAL),
        })
    return out


def list_contract_deadlines(session: Session, contract: Contract, as_of: date, include_closed: bool = True) -> list[dict]:
    stmt = select(ContractDeadline).where(ContractDeadline.contract_id == contract.id)
    if not include_closed:
        stmt = stmt.where(ContractDeadline.status == "open")
    rows = list(session.scalars(stmt.order_by(ContractDeadline.status != "open", ContractDeadline.due_date)).all())
    return deadline_payloads(session, rows, as_of, {contract.id: contract})


def create_manual_deadline(
    session: Session, *, contract: Contract, actor: RegisterActor, values: dict[str, Any], as_of: date
) -> ContractDeadline:
    clean = _clean(session, contract.organization_id, values, EDITABLE_MANUAL)
    for key, label in (("title", "Bezeichnung"), ("due_date", "Fällig am")):
        if clean.get(key) is None:
            raise DeadlineError(422, f"{label} ist erforderlich.")
    clean.setdefault("kind", "pruefung")
    clean.setdefault("remind_on", clean["due_date"])
    if clean["remind_on"] > clean["due_date"]:
        raise DeadlineError(422, "„Erinnern am“ liegt nach dem Fälligkeitsdatum.")
    clean.setdefault("assignee_account_id", actor.account_id)
    row = ContractDeadline(
        organization_id=contract.organization_id,
        contract_id=contract.id,
        source="manual",
        status="open",
        created_by_name=actor.display_name,
        **clean,
    )
    session.add(row)
    session.flush()
    if row.assignee_account_id and row.assignee_account_id != actor.account_id:
        notify(session, deadline=row, contract=contract, kind="deadline_assigned",
               recipient_ids=[row.assignee_account_id], as_of=as_of, counts={})
    log_activity(session, actor, contract.id, "deadline.created", {"deadline_id": str(row.id), "title": row.title, "due_date": row.due_date.isoformat()})
    return row


def update_deadline(
    session: Session, *, row: ContractDeadline, contract: Contract, actor: RegisterActor, values: dict[str, Any], as_of: date
) -> ContractDeadline:
    if row.status != "open":
        raise DeadlineError(409, "Erledigte oder abgebrochene Termine können nicht bearbeitet werden.")
    allowed = EDITABLE_SYSTEM if row.source == "system" else EDITABLE_MANUAL
    clean = _clean(session, contract.organization_id, values, allowed)
    due = clean.get("due_date", row.due_date)
    remind = clean.get("remind_on", row.remind_on)
    if remind > due:
        raise DeadlineError(422, "„Erinnern am“ liegt nach dem Fälligkeitsdatum.")
    diffs = {}
    custom_reminders = (row.overrides or {}).get("reminder_leads")
    if "reminder_leads" in clean:
        leads = clean.pop("reminder_leads")
        others = {k: v for k, v in (row.overrides or {}).items() if k != "reminder_leads"}
        row.overrides = ({**others, "reminder_leads": leads} if leads is not None else others) or None
        if leads != custom_reminders:
            diffs["reminder_leads"] = {"before": custom_reminders, "after": leads}
        custom_reminders = leads
    elif "remind_on" in clean and custom_reminders is not None:
        # Eigenes „Erinnern am“ ersetzt angepasste Erinnerungen.
        row.overrides = {k: v for k, v in (row.overrides or {}).items() if k != "reminder_leads"} or None
        clean["extra_remind_on"] = None
        custom_reminders = None
    if row.source == "manual" and custom_reminders is not None:
        first, extra = schedule(due, custom_reminders)
        clean["remind_on"], clean["extra_remind_on"] = first, [day.isoformat() for day in extra] or None
    elif row.source == "manual" and "reminder_leads" in diffs:
        clean["extra_remind_on"] = None
    for key, value in clean.items():
        if row.source == "system" and key in SYSTEM_OVERRIDABLE:
            # Gesetzt = gehört dem Termin; geleert = wieder der Standardtext (Abgleich unten).
            custom = {k: v for k, v in (row.overrides or {}).items() if k != key}
            if value is not None:
                custom[key] = value
            row.overrides = custom or None
        before = getattr(row, key)
        if before != value:
            diffs[key] = {"before": str(before) if before is not None else None, "after": str(value) if value is not None else None}
            setattr(row, key, value)
    if row.source == "system" and diffs:
        sync_system_deadlines(session, contract, as_of)
    if "assignee_account_id" in diffs and row.assignee_account_id and row.assignee_account_id != actor.account_id:
        notify(session, deadline=row, contract=contract, kind="deadline_assigned",
               recipient_ids=[row.assignee_account_id], as_of=as_of, counts={})
    if diffs:
        log_activity(session, actor, contract.id, "deadline.updated", {"deadline_id": str(row.id), "fields": diffs})
    session.flush()
    return row


def change_deadline_status(
    session: Session, *, row: ContractDeadline, contract: Contract, actor: RegisterActor, action: str, note: Optional[str]
) -> ContractDeadline:
    if action == "done":
        if row.status != "open":
            raise DeadlineError(409, "Nur offene Termine können erledigt werden.")
        row.status = "done"
        row.done_by_account_id = actor.account_id
        row.done_by_name = actor.display_name
        row.done_at = datetime.now(timezone.utc)
    elif action == "cancel":
        if row.status != "open":
            raise DeadlineError(409, "Nur offene Termine können abgebrochen werden.")
        if row.source == "system":
            raise DeadlineError(409, "Systemtermine werden erledigt oder ändern sich mit den Stammdaten.")
        row.status = "cancelled"
    elif action == "reopen":
        if row.status == "open":
            raise DeadlineError(409, "Der Termin ist bereits offen.")
        if row.source == "system":
            duplicate = session.scalar(select(ContractDeadline.id).where(
                ContractDeadline.contract_id == row.contract_id,
                ContractDeadline.system_key == row.system_key,
                ContractDeadline.status == "open",
            ))
            if duplicate is not None:
                raise DeadlineError(409, "Für diese Frist gibt es bereits einen offenen Termin.")
        row.status = "open"
        row.done_by_account_id = None
        row.done_by_name = None
        row.done_at = None
    else:
        raise DeadlineError(422, "Unbekannte Aktion.")
    if note:
        row.note = (f"{row.note}\n" if row.note else "") + note.strip()[:2000]
    log_activity(session, actor, contract.id, f"deadline.{action}", {"deadline_id": str(row.id), "title": row.title})
    session.flush()
    return row


# --------------------------------------------------------------------------- inbox


def owned_deadline_condition(session: Session, actor: RegisterActor, as_of: date):
    """"Meine" Termine: mir oder einer von mir vertretenen Person zugewiesen, oder
    ohne Zuweisung bei einem Vertrag, für den ich (oder die vertretene Person)
    verantwortlich bin. Eine Definition für Postfach, Termine "Nur meine" und Mein Tag.
    Erwartet einen Join auf `Contract`."""
    represented = deputized_account_ids(session, actor.account_id, actor.organization_id, as_of)
    owners = [actor.account_id, *represented]
    return or_(
        ContractDeadline.assignee_account_id.in_(owners),
        (ContractDeadline.assignee_account_id.is_(None) & Contract.responsible_account_id.in_(owners)),
    ), represented


def _note_scope(stmt, actor: RegisterActor, allowed_contract_ids: Optional[set[uuid.UUID]]):
    stmt = stmt.where(Notification.account_id == actor.account_id, Notification.organization_id == actor.organization_id)
    if allowed_contract_ids is not None:
        stmt = stmt.where(Notification.contract_id.is_(None) | Notification.contract_id.in_(allowed_contract_ids))
    return stmt


def unread_count(session: Session, *, actor: RegisterActor, allowed_contract_ids: Optional[set[uuid.UUID]]) -> int:
    """Ungelesene Benachrichtigungen – dieselbe Definition wie die Liste im Postfach und in der Glocke."""
    stmt = _note_scope(select(func.count(Notification.id)), actor, allowed_contract_ids).where(Notification.read_at.is_(None))
    return session.scalar(stmt) or 0


def notification_href(note: Notification) -> str:
    """Direkt zur Stelle: wohin eine Benachrichtigung fuehrt."""
    if note.contract_id is None:
        return "/postfach"
    if note.kind == "reextraction":
        return f"/contracts/{note.contract_id}?tab=documents&abschnitt=reextraction"
    return f"/contracts/{note.contract_id}?tab=deadlines"


def inbox(
    session: Session, *, actor: RegisterActor, as_of: date, allowed_contract_ids: Optional[set[uuid.UUID]], limit: int = 100,
    offset: int = 0, unread_only: bool = False,
) -> dict:
    note_stmt = _note_scope(select(Notification), actor, allowed_contract_ids)
    total_stmt = _note_scope(select(func.count(Notification.id)), actor, allowed_contract_ids)
    if unread_only:
        note_stmt = note_stmt.where(Notification.read_at.is_(None))
        total_stmt = total_stmt.where(Notification.read_at.is_(None))
    notes = session.scalars(
        note_stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(offset).limit(limit)
    ).all()
    owned, represented = owned_deadline_condition(session, actor, as_of)
    stmt = (
        select(ContractDeadline)
        .join(Contract, Contract.id == ContractDeadline.contract_id)
        .where(
            ContractDeadline.organization_id == actor.organization_id,
            ContractDeadline.status == "open",
            Contract.lifecycle_state == "active",
            owned,
        )
        .order_by(ContractDeadline.due_date)
    )
    if allowed_contract_ids is not None:
        stmt = stmt.where(ContractDeadline.contract_id.in_(allowed_contract_ids))
    rows = list(session.scalars(stmt.limit(500)).all())
    contracts = {
        row.id: row for row in session.scalars(select(Contract).where(Contract.id.in_({r.contract_id for r in rows}))).all()
    } if rows else {}
    return {
        "unread_count": unread_count(session, actor=actor, allowed_contract_ids=allowed_contract_ids),
        "total": session.scalar(total_stmt) or 0,
        "offset": offset,
        "notifications": [
            {
                "id": str(note.id),
                "kind": note.kind,
                "title": note.title,
                "body": note.body,
                "contract_id": str(note.contract_id) if note.contract_id else None,
                "deadline_id": str(note.deadline_id) if note.deadline_id else None,
                "href": notification_href(note),
                "on_behalf_of_name": note.on_behalf_of_name,
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "read_at": note.read_at.isoformat() if note.read_at else None,
            }
            for note in notes
        ],
        "deadlines": deadline_payloads(session, rows, as_of, contracts),
        "representing": [
            {"account_id": str(account_id), "display_name": name}
            for account_id, name in _names(session, set(represented)).items()
        ],
    }


def mark_read(
    session: Session, *, actor: RegisterActor, notification_id: Optional[uuid.UUID],
    allowed_contract_ids: Optional[set[uuid.UUID]] = None,
) -> int:
    """Markiert als gelesen. "Alle" gilt nur für den sichtbaren Bereich (wie Liste und Zähler)."""
    stmt = _note_scope(select(Notification), actor, allowed_contract_ids).where(Notification.read_at.is_(None))
    if notification_id is not None:
        stmt = stmt.where(Notification.id == notification_id)
    rows = session.scalars(stmt).all()
    now = datetime.now(timezone.utc)
    for row in rows:
        row.read_at = now
    session.flush()
    return len(rows)


# --------------------------------------------------------------------------- deputies / settings


def deputy_payload(row: AccountDeputy, names: dict[uuid.UUID, str], as_of: date) -> dict:
    return {
        "id": str(row.id),
        "account_id": str(row.account_id),
        "account_name": names.get(row.account_id),
        "deputy_account_id": str(row.deputy_account_id),
        "deputy_name": names.get(row.deputy_account_id),
        "valid_from": row.valid_from.isoformat(),
        "valid_to": row.valid_to.isoformat(),
        "is_active": row.is_active,
        "current": row.is_active and row.valid_from <= as_of <= row.valid_to,
    }


def list_deputies(session: Session, *, organization_id: uuid.UUID, account_id: Optional[uuid.UUID], as_of: date) -> list[dict]:
    stmt = select(AccountDeputy).where(AccountDeputy.organization_id == organization_id)
    if account_id is not None:
        stmt = stmt.where(or_(AccountDeputy.account_id == account_id, AccountDeputy.deputy_account_id == account_id))
    rows = list(session.scalars(stmt.order_by(AccountDeputy.valid_from.desc())).all())
    names = _names(session, {value for row in rows for value in (row.account_id, row.deputy_account_id)})
    return [deputy_payload(row, names, as_of) for row in rows]


def create_deputy(
    session: Session, *, actor: RegisterActor, account_id: uuid.UUID, deputy_account_id: uuid.UUID,
    valid_from: date, valid_to: date,
) -> AccountDeputy:
    _member(session, actor.organization_id, account_id, "Benutzer")
    _member(session, actor.organization_id, deputy_account_id, "Vertretung")
    if account_id == deputy_account_id:
        raise DeadlineError(422, "Eine Person kann sich nicht selbst vertreten.")
    if valid_to < valid_from:
        raise DeadlineError(422, "Das Ende der Vertretung liegt vor dem Beginn.")
    row = AccountDeputy(
        organization_id=actor.organization_id, account_id=account_id, deputy_account_id=deputy_account_id,
        valid_from=valid_from, valid_to=valid_to,
    )
    session.add(row)
    session.flush()
    log_activity_account(session, actor, "deputy.created", {
        "account_id": str(account_id), "deputy_account_id": str(deputy_account_id),
        "valid_from": valid_from.isoformat(), "valid_to": valid_to.isoformat(),
    })
    return row


def log_activity_account(session: Session, actor: RegisterActor, event_name: str, context: dict) -> None:
    session.add(ActivityLog(
        organization_id=actor.organization_id,
        hospital_id=actor.hospital_id,
        department_id=actor.department_id,
        account_id=actor.account_id,
        display_name_snapshot=actor.display_name,
        role_snapshot=actor.role_snapshot,
        event_name=event_name,
        object_type="account",
        object_id=actor.account_id,
        context_data=context,
    ))


def notification_settings(session: Session, account: Account, organization_id: uuid.UUID, as_of: date) -> dict:
    deputy = active_deputy(session, account.id, as_of)
    default = session.get(Account, account.default_deputy_account_id) if account.default_deputy_account_id else None
    return {
        "receives_notifications": account.receives_notifications,
        "receives_reminders": account.receives_reminders,
        "default_deputy_account_id": str(account.default_deputy_account_id) if account.default_deputy_account_id else None,
        "default_deputy_name": default.display_name if default else None,
        "current_deputy_name": deputy.display_name if deputy else None,
        "email": account.login_name,
    }


def update_notification_settings(
    session: Session, *, account: Account, actor: RegisterActor, values: dict[str, Any]
) -> None:
    for key in ("receives_notifications", "receives_reminders"):
        if key in values:
            if not isinstance(values[key], bool):
                raise DeadlineError(422, "Ja/Nein erwartet.")
            setattr(account, key, values[key])
    if "default_deputy_account_id" in values:
        deputy = _member(session, actor.organization_id, values["default_deputy_account_id"], "Standardvertretung")
        if deputy == account.id:
            raise DeadlineError(422, "Eine Person kann sich nicht selbst vertreten.")
        account.default_deputy_account_id = deputy
    log_activity_account(session, actor, "account.notification_settings_updated", {
        key: str(value) for key, value in values.items()
    })
    session.flush()
