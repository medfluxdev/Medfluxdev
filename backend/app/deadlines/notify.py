"""Tageslauf (H5.2): Systemtermine abgleichen, Erinnerungen/Ueberfaelligkeiten/
Eskalationen ins Postfach schreiben, E-Mails versenden.

Idempotent: Jede Benachrichtigung hat einen eindeutigen `dedupe_key` je
Empfaenger; ein zweiter Lauf am selben Tag erzeugt nichts doppelt. Ein
Advisory-Lock verhindert parallele Laeufe.
"""

from __future__ import annotations

import logging
import socket
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import Account, Contract
from app.database.models.deadlines import (
    AccountDeputy,
    ContractDeadline,
    JobRun,
    Notification,
    NotificationOutbox,
)
from app.database.session import create_session
from app.deadlines.mail import SmtpTransport, TransportFactory, build_ics, build_message, smtp_configured
from app.deadlines.system import sync_system_deadlines

logger = logging.getLogger("medflux.deadlines")

JOB_NAME = "daily_deadlines"
_ADVISORY_LOCK_KEY = 0x4D46_4458  # "MFDX"
MAX_SEND_ATTEMPTS = 5


@dataclass
class DailyRunResult:
    as_of: date
    counts: dict[str, int] = field(default_factory=dict)
    skipped_locked: bool = False
    job_run_id: Optional[uuid.UUID] = None


def _de(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def active_deputy(session: Session, account_id: uuid.UUID, as_of: date) -> Optional[Account]:
    row = session.scalars(
        select(AccountDeputy)
        .where(
            AccountDeputy.account_id == account_id,
            AccountDeputy.is_active.is_(True),
            AccountDeputy.valid_from <= as_of,
            AccountDeputy.valid_to >= as_of,
        )
        .order_by(AccountDeputy.valid_from.desc())
    ).first()
    if row is None:
        return None
    deputy = session.get(Account, row.deputy_account_id)
    return deputy if deputy is not None and deputy.is_active else None


def _contract_label(contract: Contract) -> str:
    number = contract.register_number or contract.contract_number or "ohne Nummer"
    title = contract.short_description or contract.supplier or "Vertrag"
    return f"Vertrag {number} – {title}"


def _link(contract: Contract) -> str:
    base = settings.app_public_url.rstrip("/")
    return f"{base}/contracts/{contract.id}?tab=deadlines" if base else ""


def _message(kind: str, deadline: ContractDeadline, contract: Contract, as_of: date) -> tuple[str, str]:
    label = _contract_label(contract)
    if kind == "deadline_reminder":
        title = f"Erinnerung: {deadline.title} am {_de(deadline.due_date)}"
    elif kind == "deadline_overdue":
        title = f"Überfällig: {deadline.title} seit {_de(deadline.due_date)}"
    elif kind == "deadline_escalation":
        title = f"Eskalation: {deadline.title} seit {_de(deadline.due_date)} offen"
    else:
        title = f"Neuer Termin: {deadline.title} am {_de(deadline.due_date)}"
    lines = [label, f"{deadline.title}: fällig am {_de(deadline.due_date)}"]
    if deadline.todo_text:
        lines.append(f"ToDo: {deadline.todo_text}")
    if deadline.source == "system":
        lines.append("Die Frist wurde aus den Vertragsstammdaten berechnet.")
    link = _link(contract)
    if link:
        lines.append(f"Öffnen: {link}")
    return title, "\n".join(lines)


def _wants_mail(account: Account, kind: str) -> bool:
    if not account.is_active or "@" not in (account.login_name or ""):
        return False
    return account.receives_reminders if kind == "deadline_reminder" else account.receives_notifications


def notify(
    session: Session,
    *,
    deadline: ContractDeadline,
    contract: Contract,
    kind: str,
    recipient_ids: Iterable[uuid.UUID],
    as_of: date,
    counts: dict[str, int],
) -> None:
    """Postfach-Eintrag (+ Vertretung) und ggf. E-Mail; doppelte Eintraege werden verworfen."""
    title, body = _message(kind, deadline, contract, as_of)
    targets: list[tuple[Account, Optional[str]]] = []
    seen: set[uuid.UUID] = set()
    for account_id in recipient_ids:
        account = session.get(Account, account_id)
        if account is None or not account.is_active or account.id in seen:
            continue
        targets.append((account, None))
        seen.add(account.id)
        deputy = active_deputy(session, account.id, as_of)
        if deputy is not None and deputy.id not in seen:
            targets.append((deputy, account.display_name))
            seen.add(deputy.id)
    for account, on_behalf_of in targets:
        dedupe = f"{kind}:{deadline.id}:{deadline.due_date.isoformat()}"
        inserted = session.execute(
            pg_insert(Notification)
            .values(
                organization_id=contract.organization_id,
                account_id=account.id,
                kind=kind,
                contract_id=contract.id,
                deadline_id=deadline.id,
                title=title,
                body=body,
                on_behalf_of_name=on_behalf_of,
                dedupe_key=dedupe,
            )
            .on_conflict_do_nothing(constraint="uq_notification_account_dedupe")
            .returning(Notification.id)
        ).scalar_one_or_none()
        if inserted is None:
            continue
        counts[kind] = counts.get(kind, 0) + 1
        if deadline.send_email and _wants_mail(account, kind):
            ics = None
            if deadline.send_ics:
                ics = build_ics(
                    uid=f"{deadline.id}-{deadline.due_date.isoformat()}@medflux",
                    due=deadline.due_date,
                    summary=f"{deadline.title} – {contract.register_number or ''}".strip(" –"),
                    description=body,
                )
            prefix = f"[Vertretung für {on_behalf_of}] " if on_behalf_of else ""
            session.add(NotificationOutbox(
                organization_id=contract.organization_id,
                notification_id=inserted,
                channel="email",
                recipient=account.login_name,
                subject=f"MedFlux: {prefix}{title}"[:255],
                body=body,
                ics=ics,
                status="pending",
            ))
            counts["emails_queued"] = counts.get("emails_queued", 0) + 1


def _eligible_contracts(session: Session, organization_id: Optional[uuid.UUID]) -> list[Contract]:
    stmt = select(Contract).where(
        Contract.lifecycle_state == "active",
        Contract.is_archived.is_(False),
        Contract.business_status.in_(("in_arbeit", "gueltig", "gekuendigt", "beendet")),
    )
    if organization_id is not None:
        stmt = stmt.where(Contract.organization_id == organization_id)
    return list(session.scalars(stmt).all())


def process_deadlines(
    session: Session, as_of: date, counts: dict[str, int], organization_id: Optional[uuid.UUID] = None
) -> None:
    for contract in _eligible_contracts(session, organization_id):
        for key, value in sync_system_deadlines(session, contract, as_of).items():
            counts[f"system_{key}"] = counts.get(f"system_{key}", 0) + value
    stmt = (
        select(ContractDeadline, Contract)
        .join(Contract, Contract.id == ContractDeadline.contract_id)
        .where(
            ContractDeadline.status == "open",
            ContractDeadline.remind_on <= as_of,
            Contract.lifecycle_state == "active",
        )
    )
    if organization_id is not None:
        stmt = stmt.where(ContractDeadline.organization_id == organization_id)
    rows = session.execute(stmt).all()
    for deadline, contract in rows:
        assignee = deadline.assignee_account_id or contract.responsible_account_id
        if assignee is None:
            counts["unassigned"] = counts.get("unassigned", 0) + 1
            continue
        if deadline.due_date >= as_of:
            notify(session, deadline=deadline, contract=contract, kind="deadline_reminder",
                   recipient_ids=[assignee], as_of=as_of, counts=counts)
        else:
            notify(session, deadline=deadline, contract=contract, kind="deadline_overdue",
                   recipient_ids=[assignee], as_of=as_of, counts=counts)
            if deadline.escalation_account_id and deadline.escalation_account_id != assignee:
                notify(session, deadline=deadline, contract=contract, kind="deadline_escalation",
                       recipient_ids=[deadline.escalation_account_id], as_of=as_of, counts=counts)


def send_outbox(
    session: Session,
    transport_factory: TransportFactory,
    counts: dict[str, int],
    organization_id: Optional[uuid.UUID] = None,
    limit: int = 200,
) -> None:
    stmt = select(NotificationOutbox).where(
        NotificationOutbox.status == "pending", NotificationOutbox.attempts < MAX_SEND_ATTEMPTS
    )
    if organization_id is not None:
        stmt = stmt.where(NotificationOutbox.organization_id == organization_id)
    pending = session.scalars(
        stmt.order_by(NotificationOutbox.created_at).limit(limit).with_for_update(skip_locked=True)
    ).all()
    if not pending:
        return
    transport = transport_factory()
    for row in pending:
        row.attempts += 1
        try:
            transport.send(build_message(recipient=row.recipient, subject=row.subject, body=row.body, ics=row.ics))
        except Exception as exc:  # noqa: BLE001 - every transport error is retried, never fatal for the run
            row.last_error = f"{type(exc).__name__}: {exc}"[:500]
            if row.attempts >= MAX_SEND_ATTEMPTS:
                row.status = "failed"
            counts["emails_failed"] = counts.get("emails_failed", 0) + 1
            continue
        row.status = "sent"
        row.sent_at = datetime.now(timezone.utc)
        row.last_error = None
        counts["emails_sent"] = counts.get("emails_sent", 0) + 1


def run_daily(
    *,
    as_of: Optional[date] = None,
    trigger: str = "scheduler",
    transport_factory: Optional[TransportFactory] = None,
    organization_id: Optional[uuid.UUID] = None,
) -> DailyRunResult:
    """Tageslauf; ohne `organization_id` fuer alle Organisationen (Zeitplan)."""
    as_of = as_of or date.today()
    result = DailyRunResult(as_of=as_of)
    lock_session = create_session()
    try:
        if not lock_session.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": _ADVISORY_LOCK_KEY}).scalar():
            result.skipped_locked = True
            return result
        session = create_session()
        run = JobRun(
            job_name=JOB_NAME, organization_id=organization_id, host=socket.gethostname()[:255],
            trigger=trigger, as_of_date=as_of, status="running",
        )
        session.add(run)
        session.commit()
        result.job_run_id = run.id
        counts: dict[str, int] = {}
        try:
            process_deadlines(session, as_of, counts, organization_id)
            session.commit()
            factory = transport_factory or (SmtpTransport if smtp_configured() else None)
            if factory is not None:
                send_outbox(session, factory, counts, organization_id)
                session.commit()
            else:
                waiting = select(func.count(NotificationOutbox.id)).where(NotificationOutbox.status == "pending")
                if organization_id is not None:
                    waiting = waiting.where(NotificationOutbox.organization_id == organization_id)
                counts["emails_waiting_for_smtp"] = session.scalar(waiting) or 0
            run.status = "succeeded"
        except Exception as exc:  # noqa: BLE001 - the failure is recorded on the job run
            session.rollback()
            logger.exception("Tageslauf fehlgeschlagen")
            run = session.get(JobRun, result.job_run_id)
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"[:1000]
        run.counts = counts
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        session.close()
        result.counts = counts
        return result
    finally:
        lock_session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _ADVISORY_LOCK_KEY})
        lock_session.close()


def deputized_account_ids(session: Session, deputy_id: uuid.UUID, organization_id: uuid.UUID, as_of: date) -> list[uuid.UUID]:
    return list(
        session.scalars(
            select(AccountDeputy.account_id).where(
                AccountDeputy.organization_id == organization_id,
                AccountDeputy.deputy_account_id == deputy_id,
                AccountDeputy.is_active.is_(True),
                and_(AccountDeputy.valid_from <= as_of, AccountDeputy.valid_to >= as_of),
            )
        ).all()
    )

