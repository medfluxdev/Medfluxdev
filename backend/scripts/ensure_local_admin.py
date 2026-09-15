"""Ensure the persistent local MedFlux admin account exists.

Security properties:
- The password is NEVER stored in source control or printed.
- Existing credentials are preserved by default, so repeated setup is idempotent.
- On first creation the password is read from MEDFLUX_LOCAL_ADMIN_PASSWORD or,
  when run interactively, requested with getpass.
- This helper is restricted to development/test. Pilot/production account
  provisioning must remain an explicit administrative action.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.auth.credential_store import derive_password
from app.core.config import settings
from app.database.models import Account, AccountMembership, Organization
from app.database.session import create_session

DEFAULT_EMAIL = "admin@medflux.local"
DEFAULT_DISPLAY_NAME = "Admin"
DEFAULT_ORG_NAME = "MedFlux Local"
DEFAULT_ORG_SLUG = "medflux-local"
PASSWORD_ENV = "MEDFLUX_LOCAL_ADMIN_PASSWORD"


def _ensure_local_runtime() -> None:
    env = settings.app_env.strip().casefold()
    if env not in {"development", "test"}:
        raise SystemExit(
            "Abbruch: lokaler Bootstrap-Admin ist nur in APP_ENV=development/test erlaubt."
        )


def _password_from_operator(email: str) -> str:
    password = os.getenv(PASSWORD_ENV, "")
    if not password:
        if not os.isatty(0):
            raise SystemExit(
                f"Account {email} fehlt. Setze {PASSWORD_ENV} einmalig oder "
                "führe das Setup interaktiv aus."
            )
        password = getpass.getpass(f"Passwort für {email}: ")
    if len(password) < 10 and not settings.development_auth_mode:
        raise SystemExit("Passwort muss mindestens 10 Zeichen lang sein.")
    if not password:
        raise SystemExit("Leeres Passwort ist nicht erlaubt.")
    return password


def ensure_admin(
    *,
    email: str = DEFAULT_EMAIL,
    display_name: str = DEFAULT_DISPLAY_NAME,
    reset_password: bool = False,
) -> str:
    _ensure_local_runtime()
    login = email.strip().casefold()
    session = create_session()
    try:
        account = session.scalar(select(Account).where(Account.login_name == login))
        if account is None:
            password = _password_from_operator(login)
            account = Account(
                login_name=login,
                display_name=display_name,
                credential_digest=derive_password(password),
                is_active=True,
                is_developer=False,
            )
            session.add(account)
            session.flush()
            created = True
        else:
            created = False
            account.is_active = True
            if reset_password:
                account.credential_digest = derive_password(
                    _password_from_operator(login)
                )

        membership = session.scalar(
            select(AccountMembership).where(
                (AccountMembership.account_id == account.id)
                & (AccountMembership.is_active.is_(True))
            )
        )
        if membership is None:
            organization = session.scalar(
                select(Organization)
                .where(Organization.is_active.is_(True))
                .order_by(Organization.created_at.asc(), Organization.id.asc())
            )
            if organization is None:
                organization = Organization(
                    name=DEFAULT_ORG_NAME,
                    slug=DEFAULT_ORG_SLUG,
                    is_active=True,
                )
                session.add(organization)
                session.flush()
            session.add(
                AccountMembership(
                    organization_id=organization.id,
                    account_id=account.id,
                    role="admin",
                    is_active=True,
                    is_default=True,
                )
            )
        else:
            membership.role = "admin"
            membership.is_active = True
            membership.is_default = True

        session.commit()
        if created:
            return f"Admin account created: {login}"
        if reset_password:
            return f"Admin account updated and password reset: {login}"
        return f"Admin account already exists; existing password preserved: {login}"
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--display-name", default=DEFAULT_DISPLAY_NAME)
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Nur bewusst verwenden; bestehendes Passwort sonst niemals ändern.",
    )
    args = parser.parse_args()
    print(
        ensure_admin(
            email=args.email,
            display_name=args.display_name,
            reset_password=args.reset_password,
        )
    )


if __name__ == "__main__":
    main()
