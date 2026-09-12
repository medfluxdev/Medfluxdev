"""Persistente lokale Auth-/Audit-Dienste (STEP 16)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import verify_password
from app.database.models.auth import AuditEvent, User
from app.database.models.organization import Organization


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
