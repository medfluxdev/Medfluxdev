from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.credential_store import derive_password, verify_password
from app.database.models import Account, AccountMembership, LoginSession, Organization
from app.database.models.account import ACCOUNT_ROLES

SESSION_TTL_DAYS = 14


@dataclass(frozen=True)
class Actor:
    account_id: UUID
    login_name: str
    display_name: str
    organization_id: UUID
    organization_slug: str
    role: str


def normalize_login(value: str) -> str:
    return value.strip().lower()


def create_account(
    session: Session,
    *,
    login_name: str,
    display_name: str,
    password: str,
    organization_id: UUID,
    role: str,
) -> Account:
    login = normalize_login(login_name)
    if not login or "@" not in login:
        raise ValueError("Bitte eine gültige E-Mail-Adresse angeben.")
    if len(password) < 10:
        raise ValueError("Das Passwort muss mindestens 10 Zeichen lang sein.")
    if role not in ACCOUNT_ROLES:
        raise ValueError("Unbekannte Rolle.")
    if session.scalar(select(Account.id).where(Account.login_name == login)) is not None:
        raise ValueError("Für diese E-Mail existiert bereits ein Benutzer.")
    account = Account(
        login_name=login,
        display_name=display_name.strip() or login,
        credential_digest=derive_password(password),
        is_active=True,
    )
    session.add(account)
    session.flush()
    session.add(AccountMembership(
        organization_id=organization_id,
        account_id=account.id,
        role=role,
        is_active=True,
    ))
    session.flush()
    return account


def authenticate(session: Session, login_name: str, password: str) -> Optional[Account]:
    login = normalize_login(login_name)
    account = session.scalar(select(Account).where(Account.login_name == login))
    if account is None or not account.is_active:
        return None
    if not verify_password(password, account.credential_digest):
        return None
    account.last_login_at = datetime.now(timezone.utc)
    session.flush()
    return account


def create_login_session(session: Session, account_id: UUID) -> tuple[str, LoginSession]:
    selector = secrets.token_urlsafe(32)
    digest = hashlib.sha256(selector.encode("utf-8")).hexdigest()
    row = LoginSession(
        account_id=account_id,
        selector_digest=digest,
        expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS),
    )
    session.add(row)
    session.flush()
    return selector, row


def revoke_login_session(session: Session, selector: str) -> None:
    digest = hashlib.sha256(selector.encode("utf-8")).hexdigest()
    row = session.scalar(select(LoginSession).where(LoginSession.selector_digest == digest))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        session.flush()


def account_from_selector(session: Session, selector: str) -> Optional[Account]:
    if not selector:
        return None
    digest = hashlib.sha256(selector.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    row = session.scalar(
        select(LoginSession).where(
            (LoginSession.selector_digest == digest)
            & (LoginSession.revoked_at.is_(None))
            & (LoginSession.expires_at > now)
        )
    )
    if row is None:
        return None
    account = session.get(Account, row.account_id)
    if account is None or not account.is_active:
        return None
    return account


def memberships_for_account(session: Session, account_id: UUID) -> list[tuple[AccountMembership, Organization]]:
    rows = session.execute(
        select(AccountMembership, Organization)
        .join(Organization, Organization.id == AccountMembership.organization_id)
        .where((AccountMembership.account_id == account_id) & (AccountMembership.is_active.is_(True)))
        .order_by(Organization.name.asc())
    ).all()
    return list(rows)


def actor_for_account(session: Session, account: Account, organization_slug: str) -> Optional[Actor]:
    row = session.execute(
        select(AccountMembership, Organization)
        .join(Organization, Organization.id == AccountMembership.organization_id)
        .where(
            (AccountMembership.account_id == account.id)
            & (AccountMembership.is_active.is_(True))
            & (Organization.slug == organization_slug)
        )
    ).first()
    if row is None:
        return None
    membership, organization = row
    return Actor(
        account_id=account.id,
        login_name=account.login_name,
        display_name=account.display_name,
        organization_id=organization.id,
        organization_slug=organization.slug,
        role=membership.role,
    )


def require_role(actor: Actor, *allowed: str) -> None:
    if actor.role not in set(allowed):
        raise PermissionError("Für diese Aktion fehlt die Berechtigung.")
