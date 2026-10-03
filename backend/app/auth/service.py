"""Persistente lokale Auth-/Audit-Dienste (STEP 16)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.auth.credential_store import derive_password, verify_password as verify_account_password
from app.core.config import settings
from app.database.models.auth import AuditEvent, User
from app.database.models.organization import Organization
from app.database.models import Account, AccountMembership, LoginSession
from app.database.models.account import ACCOUNT_ROLES


# Unknown usernames still perform the same expensive verification family as known
# users. This keeps both the STEP16 and Ahmad account login paths from becoming a
# cheap username/organization timing oracle.
_DUMMY_PASSWORD_HASH = hash_password("medflux-dummy-auth-password")
_DUMMY_ACCOUNT_DIGEST = derive_password("medflux-dummy-account-password")


@dataclass(frozen=True)
class AuthIdentity:
    user_id: uuid.UUID
    organization_id: uuid.UUID
    organization_slug: str
    username: str
    display_name: str
    role: str


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def authenticate_user(
    session: Session, *, organization_slug: str, username: str, password: str
) -> AuthIdentity | None:
    normalized = normalize_username(username)
    stmt = (
        select(User, Organization)
        .join(Organization, Organization.id == User.organization_id)
        .where(
            Organization.slug == organization_slug,
            User.username == normalized,
            User.active.is_(True),
        )
    )
    row = session.execute(stmt).first()
    if row is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    user, org = row
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    return AuthIdentity(
        user_id=user.id,
        organization_id=user.organization_id,
        organization_slug=org.slug,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


def get_identity_by_id(session: Session, user_id: uuid.UUID) -> AuthIdentity | None:
    stmt = (
        select(User, Organization)
        .join(Organization, Organization.id == User.organization_id)
        .where(User.id == user_id, User.active.is_(True))
    )
    row = session.execute(stmt).first()
    if row is None:
        return None
    user, org = row
    return AuthIdentity(
        user_id=user.id,
        organization_id=user.organization_id,
        organization_slug=org.slug,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


def record_audit_event(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    session.add(event)
    session.flush()
    return event


def list_audit_events(session: Session, *, organization_id: uuid.UUID, limit: int = 200) -> list[AuditEvent]:
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


# ---------------------------------------------------------------------------
# Ahmad account/session model — coexists with the STEP16 legacy app_user model.
# The integration branch keeps both so neither line of work is discarded.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Actor:
    account_id: uuid.UUID
    login_name: str
    display_name: str
    organization_id: uuid.UUID
    organization_slug: str
    role: str
    is_developer: bool = False

    @property
    def user_id(self) -> uuid.UUID:
        """Compatibility with JAMAL provenance hooks."""
        return self.account_id

    @property
    def username(self) -> str:
        return self.login_name


def normalize_login(value: str) -> str:
    return value.strip().lower()


def create_account(
    session: Session,
    *,
    login_name: str,
    display_name: str,
    password: str,
    organization_id: uuid.UUID,
    role: str,
) -> Account:
    login = normalize_login(login_name)
    if not login:
        raise ValueError("Bitte einen Benutzernamen oder eine E-Mail-Adresse angeben.")
    if len(password) < 10 and not settings.development_auth_mode:
        raise ValueError("Das Passwort muss mindestens 10 Zeichen lang sein.")
    if role not in ACCOUNT_ROLES:
        raise ValueError("Unbekannte Rolle.")
    if session.scalar(select(Account.id).where(Account.login_name == login)) is not None:
        raise ValueError("Für diesen Benutzernamen existiert bereits ein Benutzer.")
    account = Account(
        login_name=login,
        display_name=display_name.strip() or login,
        credential_digest=derive_password(password),
        is_active=True,
        is_developer=False,
    )
    session.add(account)
    session.flush()
    session.add(
        AccountMembership(
            organization_id=organization_id,
            account_id=account.id,
            role=role,
            is_active=True,
        )
    )
    session.flush()
    return account


def authenticate(session: Session, login_name: str, password: str) -> Optional[Account]:
    login = normalize_login(login_name)
    account = session.scalar(select(Account).where(Account.login_name == login))
    if account is None or not account.is_active:
        verify_account_password(password, _DUMMY_ACCOUNT_DIGEST)
        return None
    if not verify_account_password(password, account.credential_digest):
        return None
    account.last_login_at = datetime.now(timezone.utc)
    session.flush()
    return account


def create_login_session(session: Session, account_id: uuid.UUID) -> tuple[str, LoginSession]:
    selector = secrets.token_urlsafe(32)
    digest = hashlib.sha256(selector.encode("utf-8")).hexdigest()
    row = LoginSession(
        account_id=account_id,
        selector_digest=digest,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.auth_session_days),
    )
    session.add(row)
    session.flush()
    return selector, row


def revoke_login_session(session: Session, selector: str) -> None:
    digest = hashlib.sha256(selector.encode("utf-8")).hexdigest()
    row = session.scalar(
        select(LoginSession).where(LoginSession.selector_digest == digest)
    )
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


def memberships_for_account(
    session: Session, account_id: uuid.UUID
) -> list[tuple[AccountMembership, Organization]]:
    rows = session.execute(
        select(AccountMembership, Organization)
        .join(Organization, Organization.id == AccountMembership.organization_id)
        .where(
            (AccountMembership.account_id == account_id)
            & (AccountMembership.is_active.is_(True))
            & (Organization.is_active.is_(True))
        )
        .order_by(Organization.name.asc())
    ).all()
    return list(rows)


def actor_for_account(
    session: Session, account: Account, organization_slug: str
) -> Optional[Actor]:
    if account.is_developer:
        organization = session.scalar(
            select(Organization).where(
                (Organization.slug == organization_slug)
                & (Organization.is_active.is_(True))
            )
        )
        if organization is None:
            return None
        return Actor(
            account_id=account.id,
            login_name=account.login_name,
            display_name=account.display_name,
            organization_id=organization.id,
            organization_slug=organization.slug,
            role="admin",
            is_developer=True,
        )

    row = session.execute(
        select(AccountMembership, Organization)
        .join(Organization, Organization.id == AccountMembership.organization_id)
        .where(
            (AccountMembership.account_id == account.id)
            & (AccountMembership.is_active.is_(True))
            & (Organization.slug == organization_slug)
            & (Organization.is_active.is_(True))
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
        is_developer=False,
    )


def require_role(actor: Actor, *allowed: str) -> None:
    if actor.is_developer:
        return
    if actor.role not in set(allowed):
        raise PermissionError("Für diese Aktion fehlt die Berechtigung.")
