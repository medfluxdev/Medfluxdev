"""Massenimport von Stammdaten aus einer CSV-Liste (Vertragspartner, Abteilungen,
Kostenstellen, Auswahllisten).

Wie beim Benutzerimport: alle Zeilen werden zuerst vollstaendig geprueft;
angelegt wird nur, wenn keine Zeile einen Fehler hat (alles oder nichts).
Bestehende Eintraege werden nie geaendert. Hinweise (z. B. aehnliche
Vertragspartner) blockieren den Import nicht.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.organization_structure import DEPARTMENT_UNIT_TYPES, CostCenter, Department, Hospital
from app.database.models.register import ContractPartner, LookupValue
from app.register import catalogs
from app.register.catalogs import CatalogError

MAX_ROWS = 1000
IMPORT_KINDS = ("partner", "department", "cost_center", "lookup")
PERMISSION_BY_KIND = {
    "partner": "partner.edit",
    "department": "organization.admin",
    "cost_center": "organization.admin",
    "lookup": "catalog.admin",
}

_PARTNER_LENGTHS = {
    name: ContractPartner.__table__.c[name].type.length
    for name in catalogs.PARTNER_FIELDS
    if getattr(ContractPartner.__table__.c[name].type, "length", None)
}


def _key(value: Optional[str]) -> str:
    return (value or "").strip().casefold()


def _text(row: dict[str, Any], name: str) -> str:
    value = row.get(name)
    return value.strip() if isinstance(value, str) else ""


@dataclass
class _Checked:
    line: int
    label: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def payload(self) -> dict:
        return {"line": self.line, "label": self.label, "errors": self.errors, "warnings": self.warnings}


def _match(items: list, value: str, kind: str, code_attr: str = "code", name_attr: str = "name") -> tuple[Any, Optional[str]]:
    wanted = _key(value)
    by_code = [item for item in items if _key(getattr(item, code_attr)) == wanted]
    if len(by_code) == 1:
        return by_code[0], None
    by_name = [item for item in items if _key(getattr(item, name_attr)) == wanted]
    if len(by_name) == 1:
        return by_name[0], None
    if len(by_code) > 1 or len(by_name) > 1:
        return None, f"{kind} „{value}“ ist nicht eindeutig – bitte das Kürzel verwenden."
    return None, f"{kind} „{value}“ gibt es nicht."


# --------------------------------------------------------------------------- partner


def _check_partners(session: Session, organization_id: uuid.UUID, rows: list[dict]) -> tuple[list[_Checked], list[Callable]]:
    taken = {
        name.casefold()
        for name in session.scalars(
            select(ContractPartner.short_name).where(ContractPartner.organization_id == organization_id)
        ).all()
    }
    seen: dict[str, int] = {}
    checked: list[_Checked] = []
    creates: list[Callable] = []
    for line, row in enumerate(rows, start=1):
        short_name = _text(row, "short_name")
        values = {name: _text(row, name) or None for name in catalogs.PARTNER_FIELDS if name in row}
        item = _Checked(line, short_name or _text(row, "name1"))
        if not short_name:
            item.errors.append("Kurzname fehlt.")
        elif short_name.casefold() in taken:
            item.errors.append("Diesen Kurznamen gibt es bereits.")
        elif short_name.casefold() in seen:
            item.errors.append(f"Doppelt in der Liste (auch Zeile {seen[short_name.casefold()]}).")
        else:
            seen[short_name.casefold()] = line
        for name, value in values.items():
            limit = _PARTNER_LENGTHS.get(name)
            if value and limit and len(value) > limit:
                item.errors.append(f"{name}: höchstens {limit} Zeichen.")
        if not item.errors:
            similar = catalogs.similar_partners(session, organization_id, values.get("name1") or short_name, limit=3)
            if similar:
                item.warnings.append("Ähnlich zu: " + ", ".join(entry["short_name"] for entry in similar))
            creates.append(lambda values=values: catalogs.create_partner(session, organization_id, values, allow_similar=True)[0])
        checked.append(item)
    return checked, creates


# --------------------------------------------------------------------------- department


def _unit_type(value: str) -> tuple[Optional[str], Optional[str]]:
    if not value:
        return None, None
    key = _key(value)
    if key in DEPARTMENT_UNIT_TYPES:
        return key, None
    return None, f"Unbekannter Einheitentyp „{value}“."


def _check_departments(session: Session, organization_id: uuid.UUID, rows: list[dict]) -> tuple[list[_Checked], list[Callable]]:
    hospitals = list(session.scalars(select(Hospital).where(Hospital.organization_id == organization_id, Hospital.is_active.is_(True))))
    departments = list(session.scalars(select(Department).where(Department.organization_id == organization_id)))
    codes = {(item.hospital_id, item.code.upper()) for item in departments}
    planned: dict[tuple[uuid.UUID, str], dict] = {}
    checked: list[_Checked] = []
    creates: list[Callable] = []
    for line, row in enumerate(rows, start=1):
        name, code = _text(row, "name"), _text(row, "code").upper()
        item = _Checked(line, f"{code} – {name}" if code and name else (name or code))
        hospital = None
        if not _text(row, "hospital"):
            item.errors.append("Krankenhaus fehlt.")
        else:
            hospital, problem = _match(hospitals, _text(row, "hospital"), "Krankenhaus")
            if problem:
                item.errors.append(problem)
        if not name:
            item.errors.append("Name fehlt.")
        elif len(name) > 255:
            item.errors.append("Name: höchstens 255 Zeichen.")
        if not code:
            item.errors.append("Kürzel fehlt.")
        elif len(code) > 40:
            item.errors.append("Kürzel: höchstens 40 Zeichen.")
        unit_type, problem = _unit_type(_text(row, "unit_type"))
        if problem:
            item.errors.append(problem)

        parent_ref: Optional[Any] = None
        parent_text = _text(row, "parent")
        if hospital is not None and code:
            if (hospital.id, code) in codes:
                item.errors.append("Dieses Kürzel gibt es in diesem Krankenhaus bereits.")
            elif (hospital.id, code) in planned:
                item.errors.append(f"Doppelt in der Liste (auch Zeile {planned[(hospital.id, code)]['line']}).")
            if parent_text:
                own = [entry for entry in departments if entry.hospital_id == hospital.id and entry.is_active]
                earlier = planned.get((hospital.id, parent_text.upper()))
                if earlier is not None:
                    parent_ref = earlier
                else:
                    parent_ref, problem = _match(own, parent_text, "Übergeordnete Einheit")
                    if problem:
                        item.errors.append(problem + " (Elterneinheiten früher in der Liste aufführen)")
        if not item.errors and hospital is not None:
            entry = {"line": line, "row": None}
            planned[(hospital.id, code)] = entry

            def create(hospital=hospital, name=name, code=code, unit_type=unit_type, parent_ref=parent_ref, entry=entry):
                parent_id = None
                if isinstance(parent_ref, dict):
                    parent_id = parent_ref["row"].id
                elif parent_ref is not None:
                    parent_id = parent_ref.id
                created = Department(
                    organization_id=organization_id, hospital_id=hospital.id, parent_id=parent_id,
                    name=name, code=code, unit_type=unit_type, is_active=True,
                )
                session.add(created)
                session.flush()
                entry["row"] = created
                return created

            creates.append(create)
        checked.append(item)
    return checked, creates


# --------------------------------------------------------------------------- cost center


def _check_cost_centers(session: Session, organization_id: uuid.UUID, rows: list[dict]) -> tuple[list[_Checked], list[Callable]]:
    hospitals = list(session.scalars(select(Hospital).where(Hospital.organization_id == organization_id, Hospital.is_active.is_(True))))
    departments = list(session.scalars(select(Department).where(Department.organization_id == organization_id, Department.is_active.is_(True))))
    taken = set(session.scalars(select(func.upper(CostCenter.code)).where(CostCenter.organization_id == organization_id)).all())
    seen: dict[str, int] = {}
    checked: list[_Checked] = []
    creates: list[Callable] = []
    for line, row in enumerate(rows, start=1):
        code, name = _text(row, "code").upper(), _text(row, "name")
        item = _Checked(line, f"{code} – {name}" if code and name else (name or code))
        if not code:
            item.errors.append("Kostenstelle (Nummer) fehlt.")
        elif len(code) > 80:
            item.errors.append("Kostenstelle: höchstens 80 Zeichen.")
        elif code in taken:
            item.errors.append("Diese Kostenstelle gibt es bereits.")
        elif code in seen:
            item.errors.append(f"Doppelt in der Liste (auch Zeile {seen[code]}).")
        else:
            seen[code] = line
        if not name:
            item.errors.append("Bezeichnung fehlt.")
        elif len(name) > 255:
            item.errors.append("Bezeichnung: höchstens 255 Zeichen.")
        hospital = department = None
        if not _text(row, "hospital"):
            item.errors.append("Krankenhaus fehlt.")
        else:
            hospital, problem = _match(hospitals, _text(row, "hospital"), "Krankenhaus")
            if problem:
                item.errors.append(problem)
        if _text(row, "department") and hospital is not None:
            own = [entry for entry in departments if entry.hospital_id == hospital.id]
            department, problem = _match(own, _text(row, "department"), "Abteilung")
            if problem:
                item.errors.append(problem + " (im gewählten Krankenhaus)")
        if not item.errors and hospital is not None:
            def create(hospital=hospital, department=department, code=code, name=name):
                created = CostCenter(
                    organization_id=organization_id, hospital_id=hospital.id,
                    department_id=department.id if department else None, code=code, name=name, is_active=True,
                )
                session.add(created)
                session.flush()
                return created

            creates.append(create)
        checked.append(item)
    return checked, creates


# --------------------------------------------------------------------------- lookups


def _check_lookups(session: Session, organization_id: uuid.UUID, rows: list[dict], field_key: Optional[str]) -> tuple[list[_Checked], list[Callable]]:
    existing = list(session.scalars(
        select(LookupValue).where(LookupValue.organization_id == organization_id, LookupValue.field_key == field_key)
    ))
    labels = {item.label.casefold() for item in existing}
    codes = {item.code for item in existing}
    seen_labels: dict[str, int] = {}
    seen_codes: dict[str, int] = {}
    checked: list[_Checked] = []
    creates: list[Callable] = []
    for line, row in enumerate(rows, start=1):
        label, description = _text(row, "label"), _text(row, "description")
        item = _Checked(line, label)
        code = None
        try:
            label = catalogs._label(label)
            code = catalogs._code(_text(row, "code") or label)
        except CatalogError as exc:
            item.errors.append(exc.detail_de)
        if code is not None:
            if label.casefold() in labels:
                item.errors.append("Diesen Eintrag gibt es bereits.")
            elif label.casefold() in seen_labels:
                item.errors.append(f"Doppelt in der Liste (auch Zeile {seen_labels[label.casefold()]}).")
            elif code in codes or code in seen_codes:
                item.errors.append("Dieser Code ist bereits vergeben.")
            else:
                seen_labels[label.casefold()] = line
                seen_codes[code] = line
        if len(description) > 500:
            item.errors.append("Beschreibung: höchstens 500 Zeichen.")
        if not item.errors:
            values = {"field_key": field_key, "code": code, "label": label, "description": description or None}
            creates.append(lambda values=values: catalogs.upsert_lookup(session, organization_id, values))
        checked.append(item)
    return checked, creates


# --------------------------------------------------------------------------- entry point


def import_rows(
    session: Session,
    organization_id: uuid.UUID,
    kind: str,
    rows: list[dict[str, Any]],
    *,
    dry_run: bool,
    field_key: Optional[str] = None,
    log: Callable[[str, Any, dict], None],
) -> dict:
    if kind not in IMPORT_KINDS:
        return {"valid": False, "created": 0, "errors": ["Diese Datenart kann nicht importiert werden."], "rows": []}
    if kind == "lookup" and field_key not in catalogs.LOOKUP_FIELD_KEYS:
        return {"valid": False, "created": 0, "errors": ["Unbekannte Auswahlliste."], "rows": []}
    if not rows:
        return {"valid": False, "created": 0, "errors": ["Die Liste enthält keine Einträge."], "rows": []}
    if len(rows) > MAX_ROWS:
        return {"valid": False, "created": 0, "errors": [f"Höchstens {MAX_ROWS} Einträge je Import."], "rows": []}

    if kind == "partner":
        checked, creates = _check_partners(session, organization_id, rows)
    elif kind == "department":
        checked, creates = _check_departments(session, organization_id, rows)
    elif kind == "cost_center":
        checked, creates = _check_cost_centers(session, organization_id, rows)
    else:
        checked, creates = _check_lookups(session, organization_id, rows, field_key)

    valid = all(not item.errors for item in checked)
    result = {"valid": valid, "created": 0, "errors": [], "rows": [item.payload() for item in checked]}
    if dry_run or not valid:
        session.rollback()
        return result

    try:
        created = [create() for create in creates]
    except CatalogError as exc:
        session.rollback()
        return {**result, "valid": False, "errors": [exc.detail_de]}
    for row in created:
        log("created", row, {"import": True})
    log("bulk_imported", None, {"count": len(created), **({"field_key": field_key} if field_key else {})})
    session.commit()
    return {**result, "created": len(created)}
