"""Legt einen lokalen MedFlux-Benutzer sicher an oder aktualisiert sein Passwort.

Ausfuehrung aus Repository-Root:
    .\backend\.venv\Scripts\python.exe scripts\create_local_user.py \
        --organization krankenhaus --username admin --role admin

Das Passwort wird interaktiv abgefragt und erscheint weder in Shell-History noch Logs.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.auth.security import AuthSecurityError, hash_password  # noqa: E402
from app.auth.service import normalize_username  # noqa: E402
from app.database.models import Organization, User  # noqa: E402
from app.database.session import session_scope  # noqa: E402

ROLES = ("admin", "reviewer", "viewer")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lokalen MedFlux-Benutzer anlegen")
    parser.add_argument("--organization", required=True, help="Organization.slug")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--role", choices=ROLES, default="reviewer")
    return parser.parse_args()


def main() -> int:
    args = _args()
    password = getpass.getpass("Neues Passwort: ")
    confirm = getpass.getpass("Passwort wiederholen: ")
    if password != confirm:
        print("Fehler: Passwoerter stimmen nicht ueberein.", file=sys.stderr)
        return 2
    try:
        encoded = hash_password(password)
    except AuthSecurityError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    username = normalize_username(args.username)
    display_name = (args.display_name or args.username).strip()
    if not display_name:
        print("Fehler: Anzeigename darf nicht leer sein.", file=sys.stderr)
        return 2

    with session_scope() as session:
        org = session.scalar(select(Organization).where(Organization.slug == args.organization))
        if org is None:
            print("Fehler: Organisation nicht gefunden.", file=sys.stderr)
            return 3
        user = session.scalar(
            select(User).where(
                User.organization_id == org.id,
                User.username == username,
            )
        )
        if user is None:
            user = User(
                organization_id=org.id,
                username=username,
                display_name=display_name,
                password_hash=encoded,
                role=args.role,
                active=True,
            )
            session.add(user)
            action = "angelegt"
        else:
            user.display_name = display_name
            user.password_hash = encoded
            user.role = args.role
            user.active = True
            action = "aktualisiert"
        session.flush()
        print(
            f"Benutzer {username!r} ({args.role}) fuer {args.organization!r} {action}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
