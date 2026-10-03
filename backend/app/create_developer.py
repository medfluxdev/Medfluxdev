from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from app.auth.credential_store import derive_password
from app.auth.service import normalize_login
from app.database.models import Account
from app.database.session import create_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the Medflux developer account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Repeat password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    if len(password) < 10:
        raise SystemExit("Password must contain at least 10 characters.")

    login = normalize_login(args.email)
    session = create_session()
    try:
        existing = session.scalar(select(Account).where(Account.login_name == login))
        if existing is not None:
            existing.display_name = args.name.strip() or existing.display_name
            existing.credential_digest = derive_password(password)
            existing.is_active = True
            existing.is_developer = True
            session.commit()
            print("Existing account promoted to Developer.")
            return

        account = Account(
            login_name=login,
            display_name=args.name.strip() or login,
            credential_digest=derive_password(password),
            is_active=True,
            is_developer=True,
        )
        session.add(account)
        session.commit()
        print("Developer account created.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
