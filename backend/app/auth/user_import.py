"""Massenimport von Benutzern (z. B. aus einer CSV-Liste der IT).

Der Administrator vergibt jedem Benutzer ein Erstpasswort. Alle Zeilen werden
zuerst vollstaendig geprueft; angelegt wird nur, wenn keine Zeile einen Fehler
hat (alles oder nichts). Passwoerter werden nie zurueckgegeben oder protokolliert.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.auth.service import normalize_login
from app.database.models import Account
from app.database.models.organization_structure import Department, Hospital

MAX_ROWS = 500
MIN_PASSWORD_LENGTH = 10

ROLE_ALIASES = {
    "admin": "admin", "administrator": "admin", "administratorin": "admin",
    "contract_manager": "contract_manager", "vertragsmanager": "contract_manager", "vertragsmanagerin": "contract_manager",
    "reviewer": "reviewer", "prüfer": "reviewer", "pruefer": "reviewer", "prüferin": "reviewer", "prueferin": "reviewer",
    "viewer": "viewer", "leser": "viewer", "leserin": "viewer", "lesen": "viewer",
}


class ImportRow(BaseModel):
    email: str = Field(default="", max_length=320)
    display_name: str = Field(default="", max_length=255)
    role: str = Field(default="", max_length=64)
    hospital: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    password: str = Field(default="", max_length=256)


def _key(value: str | None) -> str:
    return (value or "").strip().casefold()


def _match(items: list, value: str, kind: str) -> tuple[object | None, str | None]:
    wanted = _key(value)
    by_code = [item for item in items if _key(item.code) == wanted]
    if len(by_code) == 1:
        return by_code[0], None
    by_name = [item for item in items if _key(item.name) == wanted]
    if len(by_name) == 1:
        return by_name[0], None
    if len(by_code) > 1 or len(by_name) > 1:
        return None, f"{kind} „{value.strip()}“ ist nicht eindeutig – bitte das Kürzel verwenden."
    return None, f"{kind} „{value.strip()}“ gibt es in dieser Organisation nicht."


def import_users(
    session,
    actor,
    rows: list[ImportRow],
    *,
    dry_run: bool,
    create_member: Callable,
    log: Callable,
) -> dict:
    if not rows:
        return {"valid": False, "created": 0, "errors": ["Die Liste enthält keine Benutzer."], "rows": []}
    if len(rows) > MAX_ROWS:
        return {"valid": False, "created": 0, "errors": [f"Höchstens {MAX_ROWS} Benutzer je Import."], "rows": []}

    org = actor.organization_id
    hospitals = list(session.scalars(select(Hospital).where(Hospital.organization_id == org, Hospital.is_active.is_(True))))
    departments = list(session.scalars(select(Department).where(Department.organization_id == org, Department.is_active.is_(True))))
    logins = [normalize_login(row.email) for row in rows]
    existing = set(session.scalars(select(Account.login_name).where(Account.login_name.in_([login for login in logins if login]))))

    seen: dict[str, int] = {}
    checked: list[dict] = []
    resolved: list[tuple[ImportRow, str, str, UUID | None, UUID | None]] = []
    for index, (row, login) in enumerate(zip(rows, logins), start=1):
        errors: list[str] = []
        name = row.display_name.strip()
        if not login:
            errors.append("E-Mail bzw. Benutzername fehlt.")
        elif login in existing:
            errors.append("Für diese E-Mail gibt es bereits einen Benutzer.")
        elif login in seen:
            errors.append(f"Doppelt in der Liste (auch Zeile {seen[login]}).")
        else:
            seen[login] = index
        if not name:
            errors.append("Name fehlt.")

        role = ROLE_ALIASES.get(_key(row.role)) if row.role.strip() else "viewer"
        if role is None:
            errors.append(f"Unbekannte Rolle „{row.role.strip()}“ (erlaubt: Administrator, Vertragsmanager, Prüfer, Leser).")

        hospital = department = None
        if row.hospital and row.hospital.strip():
            hospital, problem = _match(hospitals, row.hospital, "Krankenhaus")
            if problem:
                errors.append(problem)
        elif role and role != "admin":
            errors.append("Krankenhaus fehlt (nur Administratoren arbeiten organisationsweit).")
        if row.department and row.department.strip():
            if hospital is None:
                if not any(err.startswith("Krankenhaus") for err in errors):
                    errors.append("Ein Bereich braucht ein Krankenhaus.")
            else:
                own = [item for item in departments if item.hospital_id == hospital.id]
                department, problem = _match(own, row.department, "Bereich")
                if problem:
                    errors.append(problem + " (im gewählten Krankenhaus)")

        password = row.password
        if not password:
            errors.append("Erstpasswort fehlt.")
        elif len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"Erstpasswort ist kürzer als {MIN_PASSWORD_LENGTH} Zeichen.")
        elif password.strip().casefold() in {login, name.casefold()}:
            errors.append("Erstpasswort darf nicht der E-Mail oder dem Namen entsprechen.")

        checked.append({
            "line": index,
            "email": login,
            "display_name": name,
            "role": role,
            "hospital": hospital.name if hospital else None,
            "department": department.name if department else None,
            "errors": errors,
        })
        if not errors:
            resolved.append((row, login, role, hospital.id if hospital else None, department.id if department else None))

    valid = all(not item["errors"] for item in checked)
    if dry_run or not valid:
        session.rollback()
        return {"valid": valid, "created": 0, "errors": [], "rows": checked}

    try:
        for row, login, role, hospital_id, department_id in resolved:
            create_member(
                session, actor,
                email=login, display_name=row.display_name.strip(), password=row.password,
                role=role, hospital_id=hospital_id, department_id=department_id,
            )
        log(session, actor, "account.bulk_imported", actor.account_id, {"count": len(resolved)})
        session.commit()
    except ValueError as exc:
        session.rollback()
        return {"valid": False, "created": 0, "errors": [str(exc)], "rows": checked}
    return {"valid": True, "created": len(resolved), "errors": [], "rows": checked}
