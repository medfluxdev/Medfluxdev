from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from app.auth.service import create_account
from app.database.models import Organization
from app.database.session import create_session


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first Medflux administrator.")
    parser.add_argument("--organization", required=True, help="Organization slug")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Repeat password: ")
    if password != confirm:
        raise SystemExit("Passwords do not match.")

    session = create_session()
    try:
        organization = session.scalar(select(Organization).where(Organization.slug == args.organization))
        if organization is None:
            raise SystemExit("Organization not found.")
        create_account(
            session,
            login_name=args.email,
            display_name=args.name,
            password=password,
            organization_id=organization.id,
            role="admin",
        )
        session.commit()
        print("Administrator created.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
