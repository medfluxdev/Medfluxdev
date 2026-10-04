"""Kataloge (H2): Vertragspartner, Vertragstypen/-kategorien, Auswahllisten.

KI-Unterstuetzung ist deterministisch und nur vorschlagend: Partnerabgleich
ueber normalisierte Namen, Dublettenerkennung, Typvorschlag aus KI-Vertragsart
und eindeutigen Titel-Stichworten. Nichts wird automatisch angelegt.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from difflib import SequenceMatcher
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.register import (
    CatalogContractCategory,
    CatalogContractType,
    CatalogContractTypeCategory,
    ContractPartner,
    LookupValue,
)
from app.register.defaults import (
    AI_CONTRACT_TYPE_TO_CODE,
    CONTRACT_CATEGORIES,
    CONTRACT_TYPES,
    LOOKUPS,
    TITLE_KEYWORDS,
)

LOOKUP_FIELD_KEYS = tuple(LOOKUPS.keys())

_LEGAL_FORMS = re.compile(
    r"\b(gmbh|mbh|ag|kg|ohg|gbr|ug|se|e\.?\s?v|ev|co|und|&|partg|partmbb|inc|ltd|llc|bv|sa|sas|srl|plc|holding|deutschland|germany)\b"
)
_NON_WORD = re.compile(r"[^a-z0-9 ]+")

PARTNER_FIELDS = (
    "short_name", "name1", "name2", "street", "postal_code", "city", "country", "po_box",
    "po_box_postal_code", "phone", "fax", "email", "website", "vat_id", "industry_code", "partner_type", "note",
)


class CatalogError(ValueError):
    def __init__(self, status_code: int, detail_de: str, similar: Optional[list[dict]] = None):
        super().__init__(detail_de)
        self.status_code = status_code
        self.detail_de = detail_de
        self.similar = similar


# --------------------------------------------------------------------------- seeds


def ensure_defaults(session: Session, organization_id: uuid.UUID) -> dict[str, int]:
    """Legt fehlende Standardeintraege an (idempotent, aendert nichts Bestehendes)."""
    created = {"contract_types": 0, "contract_categories": 0, "type_category_links": 0, "lookups": 0}
    types = {
        row.code: row
        for row in session.scalars(
            select(CatalogContractType).where(CatalogContractType.organization_id == organization_id)
        ).all()
    }
    for index, (code, label, confidential) in enumerate(CONTRACT_TYPES):
        if code not in types:
            row = CatalogContractType(
                organization_id=organization_id, code=code, label=label,
                is_confidential=confidential, sort_order=index * 10,
            )
            session.add(row)
            types[code] = row
            created["contract_types"] += 1
    categories = {
        row.code: row
        for row in session.scalars(
            select(CatalogContractCategory).where(CatalogContractCategory.organization_id == organization_id)
        ).all()
    }
    new_categories = []
    for index, (code, label, _) in enumerate(CONTRACT_CATEGORIES):
        if code not in categories:
            row = CatalogContractCategory(organization_id=organization_id, code=code, label=label, sort_order=index * 10)
            session.add(row)
            categories[code] = row
            new_categories.append(code)
            created["contract_categories"] += 1
    session.flush()
    for code, _, type_codes in CONTRACT_CATEGORIES:
        if code not in new_categories:
            continue
        for type_code in type_codes:
            if type_code in types:
                session.add(
                    CatalogContractTypeCategory(
                        contract_type_id=types[type_code].id, contract_category_id=categories[code].id
                    )
                )
                created["type_category_links"] += 1
    existing_lookups = set(
        session.execute(
            select(LookupValue.field_key, LookupValue.code).where(LookupValue.organization_id == organization_id)
        ).all()
    )
    for field_key, entries in LOOKUPS.items():
        for index, (code, label, description) in enumerate(entries):
            if (field_key, code) in existing_lookups:
                continue
            session.add(
                LookupValue(
                    organization_id=organization_id, field_key=field_key, code=code, label=label,
                    description=description, sort_order=index * 10,
                )
            )
            created["lookups"] += 1
    session.flush()
    return created


# --------------------------------------------------------------------------- partners


def normalize_partner_name(name: Optional[str]) -> str:
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ß", "ss")
    text = _NON_WORD.sub(" ", text)
    text = _LEGAL_FORMS.sub(" ", text)
    return " ".join(text.split())


def partner_similarity(left: Optional[str], right: Optional[str]) -> float:
    a, b = normalize_partner_name(left), normalize_partner_name(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ratio = SequenceMatcher(None, a, b).ratio()
    tokens_a, tokens_b = set(a.split()), set(b.split())
    overlap = len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)
    if tokens_a <= tokens_b or tokens_b <= tokens_a:
        overlap = max(overlap, 0.85)
    return round(max(ratio, overlap), 3)


def partner_payload(row: ContractPartner) -> dict[str, Any]:
    data = {name: getattr(row, name) for name in PARTNER_FIELDS}
    data.update({
        "id": str(row.id),
        "is_active": row.is_active,
        "display_name": " ".join(part for part in (row.name1, row.name2) if part),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    })
    return data


def _clean_partner_values(values: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in values.items():
        if key not in PARTNER_FIELDS:
            continue
        if value is not None and not isinstance(value, str):
            raise CatalogError(422, f"Feld {key}: Text erwartet.")
        text = value.strip() if isinstance(value, str) else None
        out[key] = text or None
    if not partial:
        out.setdefault("short_name", None)
        if out["short_name"] and not out.get("name1"):
            out["name1"] = out["short_name"]
    for required, label in (("short_name", "Kurzname"), ("name1", "Name")):
        if required in out and not out[required]:
            raise CatalogError(422, f"{label} ist erforderlich.")
    return out


def _short_name_taken(session: Session, organization_id: uuid.UUID, short_name: str, exclude: Optional[uuid.UUID]) -> bool:
    stmt = select(ContractPartner.id).where(
        ContractPartner.organization_id == organization_id,
        func.lower(ContractPartner.short_name) == short_name.lower(),
    )
    if exclude is not None:
        stmt = stmt.where(ContractPartner.id != exclude)
    return session.scalar(stmt) is not None


def similar_partners(
    session: Session, organization_id: uuid.UUID, name: str, *, limit: int = 5, threshold: float = 0.72,
    exclude: Optional[uuid.UUID] = None,
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(ContractPartner).where(
            ContractPartner.organization_id == organization_id, ContractPartner.is_active.is_(True)
        )
    ).all()
    scored = []
    for row in rows:
        if exclude is not None and row.id == exclude:
            continue
        score = max(partner_similarity(name, row.short_name), partner_similarity(name, row.name1))
        if score >= threshold:
            scored.append((score, row))
    scored.sort(key=lambda item: (-item[0], item[1].short_name.lower()))
    return [{**partner_payload(row), "score": score} for score, row in scored[:limit]]


def create_partner(session: Session, organization_id: uuid.UUID, values: dict[str, Any], *, allow_similar: bool) -> tuple[ContractPartner, list[dict]]:
    clean = _clean_partner_values(values, partial=False)
    if _short_name_taken(session, organization_id, clean["short_name"], None):
        raise CatalogError(409, "Ein Vertragspartner mit diesem Kurznamen existiert bereits.")
    similar = similar_partners(session, organization_id, clean["name1"])
    if similar and not allow_similar:
        raise CatalogError(409, "Möglicherweise existiert dieser Vertragspartner bereits.", similar=similar)
    row = ContractPartner(organization_id=organization_id, **clean)
    session.add(row)
    session.flush()
    return row, similar


def update_partner(session: Session, row: ContractPartner, values: dict[str, Any]) -> ContractPartner:
    clean = _clean_partner_values(values, partial=True)
    if "short_name" in clean and _short_name_taken(session, row.organization_id, clean["short_name"], row.id):
        raise CatalogError(409, "Ein Vertragspartner mit diesem Kurznamen existiert bereits.")
    for key, value in clean.items():
        setattr(row, key, value)
    if "is_active" in values:
        if not isinstance(values["is_active"], bool):
            raise CatalogError(422, "is_active: Ja/Nein erwartet.")
        row.is_active = values["is_active"]
    session.flush()
    return row


def duplicate_groups(session: Session, organization_id: uuid.UUID, threshold: float = 0.88) -> list[list[dict]]:
    rows = list(
        session.scalars(
            select(ContractPartner)
            .where(ContractPartner.organization_id == organization_id, ContractPartner.is_active.is_(True))
            .order_by(ContractPartner.short_name)
        ).all()
    )
    seen: set[uuid.UUID] = set()
    groups = []
    for index, row in enumerate(rows):
        if row.id in seen:
            continue
        group = [row]
        for other in rows[index + 1:]:
            if other.id in seen:
                continue
            if partner_similarity(row.name1, other.name1) >= threshold:
                group.append(other)
        if len(group) > 1:
            seen.update(member.id for member in group)
            groups.append([partner_payload(member) for member in group])
    return groups


# --------------------------------------------------------------------------- types / categories / lookups


def type_suggestion(session: Session, organization_id: uuid.UUID, ai_contract_type: Optional[str], title: Optional[str]) -> Optional[dict]:
    """Typvorschlag: eindeutiges Titel-Stichwort vor KI-Vertragsart."""
    code = None
    reason = None
    if title:
        lowered = title.lower()
        hits = {type_code for keyword, type_code in TITLE_KEYWORDS if keyword in lowered}
        if len(hits) == 1:
            code = hits.pop()
            reason = "Vertragstitel"
    if code is None and ai_contract_type:
        code = AI_CONTRACT_TYPE_TO_CODE.get(ai_contract_type)
        reason = "KI-Vertragsart" if code else None
    if code is None:
        return None
    row = session.scalars(
        select(CatalogContractType).where(
            CatalogContractType.organization_id == organization_id,
            CatalogContractType.code == code,
            CatalogContractType.is_active.is_(True),
        )
    ).first()
    if row is None:
        return None
    return {"id": str(row.id), "label": row.label, "reason": reason}


def type_payload(row: CatalogContractType) -> dict[str, Any]:
    return {
        "id": str(row.id), "code": row.code, "label": row.label, "description": row.description,
        "is_confidential": row.is_confidential, "is_active": row.is_active, "sort_order": row.sort_order,
    }


def category_payload(row: CatalogContractCategory, type_ids: list[str]) -> dict[str, Any]:
    return {
        "id": str(row.id), "code": row.code, "label": row.label, "description": row.description,
        "is_active": row.is_active, "sort_order": row.sort_order, "contract_type_ids": type_ids,
    }


def lookup_payload(row: LookupValue) -> dict[str, Any]:
    return {
        "id": str(row.id), "field_key": row.field_key, "code": row.code, "label": row.label,
        "description": row.description, "is_active": row.is_active, "sort_order": row.sort_order,
    }


def list_types_and_categories(session: Session, organization_id: uuid.UUID) -> dict[str, list[dict]]:
    types = session.scalars(
        select(CatalogContractType)
        .where(CatalogContractType.organization_id == organization_id)
        .order_by(CatalogContractType.sort_order, CatalogContractType.label)
    ).all()
    categories = session.scalars(
        select(CatalogContractCategory)
        .where(CatalogContractCategory.organization_id == organization_id)
        .order_by(CatalogContractCategory.sort_order, CatalogContractCategory.label)
    ).all()
    links = session.execute(
        select(CatalogContractTypeCategory.contract_category_id, CatalogContractTypeCategory.contract_type_id)
        .join(CatalogContractType, CatalogContractType.id == CatalogContractTypeCategory.contract_type_id)
        .where(CatalogContractType.organization_id == organization_id)
    ).all()
    by_category: dict[uuid.UUID, list[str]] = {}
    for category_id, type_id in links:
        by_category.setdefault(category_id, []).append(str(type_id))
    return {
        "contract_types": [type_payload(row) for row in types],
        "contract_categories": [category_payload(row, sorted(by_category.get(row.id, []))) for row in categories],
    }


def _code(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(422, "Code ist erforderlich.")
    code = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")
    if not code or len(code) > 64:
        raise CatalogError(422, "Code ist ungültig.")
    return code


def _label(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(422, "Bezeichnung ist erforderlich.")
    if len(value.strip()) > 160:
        raise CatalogError(422, "Bezeichnung ist zu lang.")
    return value.strip()


def _code_exists(session: Session, model, organization_id: uuid.UUID, code: str, exclude: Optional[uuid.UUID] = None, field_key: Optional[str] = None) -> bool:
    stmt = select(model.id).where(model.organization_id == organization_id, model.code == code)
    if field_key is not None:
        stmt = stmt.where(model.field_key == field_key)
    if exclude is not None:
        stmt = stmt.where(model.id != exclude)
    return session.scalar(stmt) is not None


def _label_exists(session: Session, model, organization_id: uuid.UUID, label: str, exclude: Optional[uuid.UUID] = None, field_key: Optional[str] = None) -> bool:
    stmt = select(model.id).where(model.organization_id == organization_id, func.lower(model.label) == label.lower())
    if field_key is not None:
        stmt = stmt.where(model.field_key == field_key)
    if exclude is not None:
        stmt = stmt.where(model.id != exclude)
    return session.scalar(stmt) is not None


def upsert_type(session: Session, organization_id: uuid.UUID, values: dict[str, Any], row: Optional[CatalogContractType] = None) -> CatalogContractType:
    if row is None:
        code = _code(values.get("code") or values.get("label"))
        label = _label(values.get("label"))
        if _code_exists(session, CatalogContractType, organization_id, code):
            raise CatalogError(409, "Dieser Code ist bereits vergeben.")
        if _label_exists(session, CatalogContractType, organization_id, label):
            raise CatalogError(409, "Ein Vertragstyp mit dieser Bezeichnung existiert bereits.")
        row = CatalogContractType(organization_id=organization_id, code=code, label=label)
        session.add(row)
    elif "label" in values:
        label = _label(values["label"])
        if _label_exists(session, CatalogContractType, organization_id, label, row.id):
            raise CatalogError(409, "Ein Vertragstyp mit dieser Bezeichnung existiert bereits.")
        row.label = label
    _apply_common(row, values)
    if "is_confidential" in values:
        row.is_confidential = _bool(values["is_confidential"])
    session.flush()
    return row


def upsert_category(session: Session, organization_id: uuid.UUID, values: dict[str, Any], row: Optional[CatalogContractCategory] = None) -> CatalogContractCategory:
    if row is None:
        code = _code(values.get("code") or values.get("label"))
        label = _label(values.get("label"))
        if _code_exists(session, CatalogContractCategory, organization_id, code):
            raise CatalogError(409, "Dieser Code ist bereits vergeben.")
        if _label_exists(session, CatalogContractCategory, organization_id, label):
            raise CatalogError(409, "Eine Kategorie mit dieser Bezeichnung existiert bereits.")
        row = CatalogContractCategory(organization_id=organization_id, code=code, label=label)
        session.add(row)
        session.flush()
    elif "label" in values:
        label = _label(values["label"])
        if _label_exists(session, CatalogContractCategory, organization_id, label, row.id):
            raise CatalogError(409, "Eine Kategorie mit dieser Bezeichnung existiert bereits.")
        row.label = label
    _apply_common(row, values)
    if "contract_type_ids" in values:
        wanted = set()
        for raw in values["contract_type_ids"] or []:
            try:
                type_id = uuid.UUID(str(raw))
            except ValueError:
                raise CatalogError(422, "Ungültiger Vertragstyp.")
            type_row = session.get(CatalogContractType, type_id)
            if type_row is None or type_row.organization_id != organization_id:
                raise CatalogError(422, "Vertragstyp nicht verfügbar.")
            wanted.add(type_id)
        existing = {
            link.contract_type_id: link
            for link in session.scalars(
                select(CatalogContractTypeCategory).where(CatalogContractTypeCategory.contract_category_id == row.id)
            ).all()
        }
        for type_id, link in existing.items():
            if type_id not in wanted:
                session.delete(link)
        for type_id in wanted - set(existing):
            session.add(CatalogContractTypeCategory(contract_type_id=type_id, contract_category_id=row.id))
    session.flush()
    return row


def upsert_lookup(session: Session, organization_id: uuid.UUID, values: dict[str, Any], row: Optional[LookupValue] = None) -> LookupValue:
    if row is None:
        field_key = values.get("field_key")
        if field_key not in LOOKUP_FIELD_KEYS:
            raise CatalogError(422, "Unbekannte Auswahlliste.")
        code = _code(values.get("code") or values.get("label"))
        label = _label(values.get("label"))
        if _code_exists(session, LookupValue, organization_id, code, field_key=field_key):
            raise CatalogError(409, "Dieser Code ist bereits vergeben.")
        if _label_exists(session, LookupValue, organization_id, label, field_key=field_key):
            raise CatalogError(409, "Ein Eintrag mit dieser Bezeichnung existiert bereits.")
        row = LookupValue(organization_id=organization_id, field_key=field_key, code=code, label=label)
        session.add(row)
    elif "label" in values:
        label = _label(values["label"])
        if _label_exists(session, LookupValue, organization_id, label, row.id, field_key=row.field_key):
            raise CatalogError(409, "Ein Eintrag mit dieser Bezeichnung existiert bereits.")
        row.label = label
    _apply_common(row, values)
    session.flush()
    return row


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise CatalogError(422, "Ja/Nein erwartet.")
    return value


def _apply_common(row, values: dict[str, Any]) -> None:
    if "description" in values:
        description = values["description"]
        if description is not None and not isinstance(description, str):
            raise CatalogError(422, "Beschreibung: Text erwartet.")
        row.description = (description or "").strip()[:500] or None
    if "is_active" in values:
        row.is_active = _bool(values["is_active"])
    if "sort_order" in values:
        try:
            row.sort_order = int(values["sort_order"])
        except (TypeError, ValueError):
            raise CatalogError(422, "Sortierung: Zahl erwartet.")


def lookup_label(session: Session, organization_id: uuid.UUID, field_key: str, code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return session.scalar(
        select(LookupValue.label).where(
            LookupValue.organization_id == organization_id,
            LookupValue.field_key == field_key,
            LookupValue.code == code,
        )
    )
