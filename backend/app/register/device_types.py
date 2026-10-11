"""Gerätearten an Verträgen (Plan docs/architecture/GERAETEARTEN_PLAN_20261011.md).

Stammdaten-Liste je Organisation (nach Bereich, optional einer Abteilung zugeordnet) und die
gepflegte Zuordnung Vertrag → Geräteart mit optionaler Anzahl. Vorschläge aus im Dokument
gefundenen Geräten werden nur angezeigt, nie automatisch übernommen.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Contract, Department
from app.database.models.contract import ContractEquipment
from app.database.models.register import CatalogDeviceType, ContractDeviceType
from app.register.catalogs import CatalogError, _apply_common, _code, _code_exists, _label, _label_exists

AREAS: dict[str, str] = {
    "medizintechnik": "Medizintechnik",
    "it": "IT",
    "haustechnik": "Haustechnik",
    "sonstiges": "Sonstiges",
}

# (code, Bezeichnung, Bereich, Suchbegriffe)
DEFAULT_DEVICE_TYPES: tuple[tuple[str, str, str, str], ...] = (
    ("ct", "CT", "medizintechnik", "Computertomograph, Computertomographie, Somatom, Revolution"),
    ("mrt", "MRT", "medizintechnik", "Magnetresonanztomograph, MRI, Kernspin, Magnetom"),
    ("roentgen", "Röntgen", "medizintechnik", "Röntgenanlage, Radiographie, Durchleuchtung, C-Bogen"),
    ("angiographie", "Angiographie", "medizintechnik", "Angiographieanlage, Herzkatheter, Linksherzkatheter"),
    ("mammographie", "Mammographie", "medizintechnik", "Mammograph"),
    ("ultraschall", "Ultraschall", "medizintechnik", "Sonographie, Sonografie, Echokardiographie"),
    ("nuklearmedizin", "Nuklearmedizin", "medizintechnik", "PET, SPECT, Gammakamera"),
    ("strahlentherapie", "Strahlentherapie", "medizintechnik", "Linearbeschleuniger, LINAC"),
    ("beatmung", "Beatmungsgerät", "medizintechnik", "Beatmung, Respirator, Ventilator"),
    ("narkose", "Narkosegerät", "medizintechnik", "Anästhesiegerät, Narkose"),
    ("monitoring", "Patientenmonitoring", "medizintechnik", "Monitor, Überwachungsmonitor, Patientenüberwachung"),
    ("infusion", "Infusionstechnik", "medizintechnik", "Infusionspumpe, Spritzenpumpe, Perfusor"),
    ("endoskopie", "Endoskopie", "medizintechnik", "Endoskop, Gastroskop, Koloskop"),
    ("dialyse", "Dialyse", "medizintechnik", "Dialysegerät, Hämodialyse"),
    ("herzunterstuetzung", "Herzunterstützung", "medizintechnik", "Impella, Herzpumpe, ECMO, IABP"),
    ("defibrillator", "Defibrillator", "medizintechnik", "AED, Defi"),
    ("op_technik", "OP-Technik", "medizintechnik", "OP-Tisch, OP-Leuchte, Chirurgie"),
    ("labor", "Laborgerät", "medizintechnik", "Analysegerät, Analysator, Labor"),
    ("sterilisation", "Sterilisation", "medizintechnik", "Sterilisator, Autoklav, AEMP, Reinigungs- und Desinfektionsgerät"),
    ("server", "Server", "it", "Rechenzentrum, Virtualisierung"),
    ("speicher", "Speichersystem", "it", "Storage, SAN, NAS, Backup"),
    ("netzwerk", "Netzwerk", "it", "Switch, Router, Firewall, WLAN"),
    ("arbeitsplatz", "Arbeitsplatz-PC", "it", "PC, Notebook, Laptop, Thin Client"),
    ("drucker", "Drucker", "it", "Multifunktionsgerät, Kopierer, Drucksystem"),
    ("telefonie", "Telefonie", "it", "Telefonanlage, TK-Anlage, DECT"),
    ("software", "Software", "it", "KIS, PACS, RIS, Lizenz"),
    ("aufzug", "Aufzug", "haustechnik", "Aufzugsanlage, Fahrstuhl, Lift"),
    ("klima", "Klima/Lüftung", "haustechnik", "Klimaanlage, Lüftungsanlage, RLT, Kälteanlage"),
    ("notstrom", "Notstrom", "haustechnik", "Netzersatzanlage, NEA, USV, Notstromaggregat"),
    ("brandschutz", "Brandschutz", "haustechnik", "Brandmeldeanlage, Sprinkler, Rauchabzug"),
    ("med_gase", "Medizinische Gase", "haustechnik", "Gasversorgung, Sauerstoff, Druckluft"),
    ("heizung", "Heizung/Sanitär", "haustechnik", "Heizungsanlage, Sanitär, Warmwasser"),
)

MAX_QUANTITY = 100_000


def ensure_device_types(session: Session, organization_id: uuid.UUID) -> None:
    """Standardliste einmalig anlegen (nur wenn die Organisation noch keine Gerätearten hat)."""
    if session.scalar(select(CatalogDeviceType.id).where(CatalogDeviceType.organization_id == organization_id).limit(1)):
        return
    for index, (code, label, area, keywords) in enumerate(DEFAULT_DEVICE_TYPES):
        session.add(CatalogDeviceType(
            organization_id=organization_id, code=code, label=label, area=area, keywords=keywords, sort_order=index * 10,
        ))
    session.flush()


def device_type_payload(row: CatalogDeviceType, department_names: Optional[dict] = None) -> dict[str, Any]:
    return {
        "id": str(row.id), "code": row.code, "label": row.label, "area": row.area, "area_label": AREAS.get(row.area, row.area),
        "department_id": str(row.department_id) if row.department_id else None,
        "department_name": (department_names or {}).get(row.department_id) if row.department_id else None,
        "keywords": row.keywords, "description": row.description, "is_active": row.is_active, "sort_order": row.sort_order,
    }


def list_device_types(session: Session, organization_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(CatalogDeviceType).where(CatalogDeviceType.organization_id == organization_id)
        .order_by(CatalogDeviceType.area, CatalogDeviceType.sort_order, CatalogDeviceType.label)
    ).all()
    names = dict(session.execute(select(Department.id, Department.name).where(Department.organization_id == organization_id)).all())
    return [device_type_payload(row, names) for row in rows]


def upsert_device_type(
    session: Session, organization_id: uuid.UUID, values: dict[str, Any], row: Optional[CatalogDeviceType] = None,
) -> CatalogDeviceType:
    if row is None:
        label = _label(values.get("label"))
        code = _code(values.get("code") or label)
        if _code_exists(session, CatalogDeviceType, organization_id, code):
            raise CatalogError(409, "Dieser Code ist bereits vergeben.")
        if _label_exists(session, CatalogDeviceType, organization_id, label):
            raise CatalogError(409, "Eine Geräteart mit dieser Bezeichnung existiert bereits.")
        row = CatalogDeviceType(organization_id=organization_id, code=code, label=label)
        session.add(row)
    elif "label" in values:
        label = _label(values["label"])
        if _label_exists(session, CatalogDeviceType, organization_id, label, row.id):
            raise CatalogError(409, "Eine Geräteart mit dieser Bezeichnung existiert bereits.")
        row.label = label
    if "area" in values or row.area is None:
        area = values.get("area") or "sonstiges"
        if area not in AREAS:
            raise CatalogError(422, "Bereich ist ungültig.")
        row.area = area
    if "department_id" in values:
        raw = values["department_id"]
        if raw in (None, ""):
            row.department_id = None
        else:
            try:
                department_id = uuid.UUID(str(raw))
            except ValueError:
                raise CatalogError(422, "Abteilung ist ungültig.")
            department = session.get(Department, department_id)
            if department is None or department.organization_id != organization_id:
                raise CatalogError(422, "Abteilung ist ungültig.")
            row.department_id = department_id
    if "keywords" in values:
        keywords = values["keywords"]
        if keywords is not None and not isinstance(keywords, str):
            raise CatalogError(422, "Suchbegriffe: Text erwartet.")
        row.keywords = (keywords or "").strip()[:500] or None
    _apply_common(row, values)
    session.flush()
    return row


# --------------------------------------------------------------------------- Vertrag


def contract_device_types(session: Session, contract: Contract) -> list[dict[str, Any]]:
    rows = session.execute(
        select(ContractDeviceType, CatalogDeviceType)
        .join(CatalogDeviceType, CatalogDeviceType.id == ContractDeviceType.device_type_id)
        .where(ContractDeviceType.contract_id == contract.id)
        .order_by(CatalogDeviceType.area, CatalogDeviceType.sort_order, CatalogDeviceType.label)
    ).all()
    return [{
        "device_type_id": str(kind.id), "label": kind.label, "area": kind.area, "area_label": AREAS.get(kind.area, kind.area),
        "quantity": link.quantity, "note": link.note,
    } for link, kind in rows]


def device_types_by_contract(session: Session, organization_id: uuid.UUID) -> dict[uuid.UUID, list[tuple[str, Optional[int]]]]:
    """Für die Vertragsliste: je Vertrag (Bezeichnung, Anzahl) in fester Reihenfolge."""
    result: dict[uuid.UUID, list[tuple[str, Optional[int]]]] = {}
    for contract_id, label, quantity in session.execute(
        select(ContractDeviceType.contract_id, CatalogDeviceType.label, ContractDeviceType.quantity)
        .join(CatalogDeviceType, CatalogDeviceType.id == ContractDeviceType.device_type_id)
        .where(ContractDeviceType.organization_id == organization_id)
        .order_by(CatalogDeviceType.area, CatalogDeviceType.sort_order, CatalogDeviceType.label)
    ).all():
        result.setdefault(contract_id, []).append((label, quantity))
    return result


def set_contract_device_types(session: Session, contract: Contract, items: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Gerätearten des Vertrags ersetzen. Gibt (vorher, nachher) für den Verlauf zurück."""
    before = contract_device_types(session, contract)
    wanted: dict[uuid.UUID, tuple[Optional[int], Optional[str]]] = {}
    for item in items:
        try:
            device_type_id = uuid.UUID(str(item.get("device_type_id")))
        except ValueError:
            raise CatalogError(422, "Geräteart ist ungültig.")
        kind = session.get(CatalogDeviceType, device_type_id)
        if kind is None or kind.organization_id != contract.organization_id:
            raise CatalogError(422, "Geräteart ist ungültig.")
        if device_type_id in wanted:
            raise CatalogError(422, f"„{kind.label}“ ist doppelt ausgewählt.")
        quantity = item.get("quantity")
        if quantity in (None, ""):
            quantity = None
        else:
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                raise CatalogError(422, "Anzahl: ganze Zahl erwartet.")
            if not 1 <= quantity <= MAX_QUANTITY:
                raise CatalogError(422, "Anzahl: mindestens 1.")
        note = item.get("note")
        if note is not None and not isinstance(note, str):
            raise CatalogError(422, "Notiz: Text erwartet.")
        wanted[device_type_id] = (quantity, (note or "").strip()[:255] or None)

    existing = {row.device_type_id: row for row in session.scalars(
        select(ContractDeviceType).where(ContractDeviceType.contract_id == contract.id)
    ).all()}
    for device_type_id, row in existing.items():
        if device_type_id not in wanted:
            session.delete(row)
    for device_type_id, (quantity, note) in wanted.items():
        row = existing.get(device_type_id)
        if row is None:
            session.add(ContractDeviceType(
                organization_id=contract.organization_id, contract_id=contract.id, device_type_id=device_type_id,
                quantity=quantity, note=note,
            ))
        elif (row.quantity, row.note) != (quantity, note):
            row.quantity, row.note = quantity, note
    session.flush()
    return before, contract_device_types(session, contract)


def _terms(kind: CatalogDeviceType) -> list[str]:
    raw = [kind.label, *(kind.keywords or "").split(",")]
    return [term.strip().casefold() for term in raw if term and term.strip()]


def suggestions(session: Session, contract: Contract) -> list[dict[str, Any]]:
    """Gerätearten, deren Bezeichnung/Suchbegriff in einem im Dokument gefundenen Gerät steht (nur Vorschlag)."""
    if contract.accepted_extraction_id is None:
        return []
    texts = [
        " ".join(filter(None, (row.device_name, row.equipment_category, row.equipment_type)))
        for row in session.scalars(
            select(ContractEquipment).where(
                ContractEquipment.contract_id == contract.id,
                ContractEquipment.extraction_id == contract.accepted_extraction_id,
            )
        ).all()
    ]
    texts = [text for text in texts if text.strip()]
    if not texts:
        return []
    chosen = set(session.scalars(select(ContractDeviceType.device_type_id).where(ContractDeviceType.contract_id == contract.id)).all())
    kinds = session.scalars(select(CatalogDeviceType).where(
        CatalogDeviceType.organization_id == contract.organization_id, CatalogDeviceType.is_active.is_(True),
    ).order_by(CatalogDeviceType.sort_order)).all()
    return match_device_types(texts, [kind for kind in kinds if kind.id not in chosen])


def match_device_types(texts: list[str], kinds) -> list[dict[str, Any]]:
    """Rein: Gerätearten, deren Bezeichnung oder Suchbegriff als ganzes Wort in einem Text steht."""
    lowered = [text.casefold() for text in texts]
    result = []
    for kind in kinds:
        for term in _terms(kind):
            pattern = re.compile(rf"(?<![\w]){re.escape(term)}(?![\w])")
            if any(pattern.search(text) for text in lowered):
                result.append({"device_type_id": str(kind.id), "label": kind.label, "reason": f"im Dokument: „{term}“"})
                break
    return result
