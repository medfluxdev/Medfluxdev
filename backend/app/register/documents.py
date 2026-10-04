"""Vertragsdokumente und Rahmenvertrags-Verknuepfung (H3).

- Mehrere typisierte Dokumente je Vertrag; genau ein Hauptdokument,
  ungueltige (abgeloeste) Dokumente bleiben erhalten.
- Analysierbare Anlagen (Nachtrag, Kuendigung, ...) laufen ueber den
  `DocumentProcessingService`; ihre Ergebnisse werden NUR als Vorschlaege an
  den Registerfeldern abgelegt (`ai_proposed_value`), nie direkt uebernommen.
- Rahmenvertraege: `contract_relation` mit `relation_type='governs'`
  (Quelle = Rahmenvertrag, Ziel = Einzelvertrag). KI-Vorschlaege tragen
  `requires_review=True`, bestaetigte Verknuepfungen `False`.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.models import Contract, ContractDocument, DocumentFile, DocumentVersion
from app.database.models.intelligence import ContractRelationRecord
from app.database.models.register import ContractFieldProvenance
from app.models.contract import Contract as ExtractedContract
from app.register.ai_mapping import Proposal, proposals_from_extraction
from app.register.fields import FIELDS, to_json
from app.register.service import RegisterActor, RegisterError, log_activity

ANALYZABLE_TYPES = frozenset({
    "vertrag", "nachtrag", "addendum", "vertragsanpassung", "verguetungsvereinbarung",
    "leistungskatalog", "avv", "kuendigung", "kuendigungsbestaetigung", "aufhebung",
})
TERMINATION_TYPES = frozenset({"kuendigung", "kuendigungsbestaetigung", "aufhebung"})
ROLE_BY_TYPE = {
    "vertrag": "main",
    "nachtrag": "amendment",
    "addendum": "amendment",
    "vertragsanpassung": "amendment",
    "verguetungsvereinbarung": "price_adjustment",
    "leistungskatalog": "sla_attachment",
    "kuendigung": "renewal_letter",
    "kuendigungsbestaetigung": "renewal_letter",
}
FRAMEWORK_RELATION = "governs"
_MIN_REFERENCE_LENGTH = 4
_FRAMEWORK_WORD = re.compile(r"rahmen\s*-?\s*(vertrag|vereinbarung|abkommen)", re.IGNORECASE)


def role_for(attachment_type: Optional[str]) -> str:
    return ROLE_BY_TYPE.get(attachment_type or "", "appendix")


# --------------------------------------------------------------------------- AI proposals from attachments


def attachment_proposals(extracted: ExtractedContract, attachment_type: str) -> dict[str, Proposal]:
    """Vorschlaege aus einer Anlage. Kuendigungsschreiben liefern das
    wirksame Vertragsende als „Gekündigt zum“, keine Laufzeitfelder."""
    if attachment_type in TERMINATION_TYPES:
        end = getattr(extracted.dates.end_date, "date", None) if extracted.dates.end_date else None
        return {"terminated_effective": Proposal(end, "dates.end_date")} if end else {}
    proposals = proposals_from_extraction(extracted)
    proposals.pop("short_description", None)
    return proposals


def propose_from_document(
    session: Session,
    *,
    contract: Contract,
    extracted: ExtractedContract,
    extraction_id: uuid.UUID,
    attachment_type: str,
    document_label: str,
) -> list[str]:
    """Legt abweichende Werte als KI-Vorschlag ab; aendert keine Feldwerte."""
    provenance = {
        row.field_key: row
        for row in session.scalars(
            select(ContractFieldProvenance).where(ContractFieldProvenance.contract_id == contract.id)
        ).all()
    }
    proposed: list[str] = []
    for key, proposal in attachment_proposals(extracted, attachment_type).items():
        if key not in FIELDS or to_json(getattr(contract, key)) == to_json(proposal.value):
            continue
        payload = {"value": to_json(proposal.value), "source_field": proposal.source_field, "document": document_label}
        row = provenance.get(key)
        if row is None:
            row = ContractFieldProvenance(
                organization_id=contract.organization_id,
                contract_id=contract.id,
                field_key=key,
                origin="manual" if getattr(contract, key) is not None else "ai",
            )
            session.add(row)
        row.ai_proposed_value = payload
        row.extraction_id = extraction_id
        proposed.append(key)
    session.flush()
    return proposed


# --------------------------------------------------------------------------- data protection detection

_DATA_PROTECTION = re.compile(
    r"(auftragsverarbeitung|art\.?\s*28\s*dsgvo|art\.?\s*28\s*ds-gvo|personenbezogene[nr]?\s+daten|patientendaten|gesundheitsdaten)",
    re.IGNORECASE,
)


def detect_data_protection(session: Session, contract: Contract, text: str, extraction_id: Optional[uuid.UUID]) -> bool:
    """KI-Hinweis: Text nennt Auftragsverarbeitung/personenbezogene Daten.

    Setzt das Feld nur, wenn es leer oder KI-eigen ist; menschliche Werte
    erhalten einen Vorschlag. Liefert True, wenn ein Treffer vorlag.
    """
    match = _DATA_PROTECTION.search(text or "")
    if match is None:
        return False
    row = session.scalars(select(ContractFieldProvenance).where(
        ContractFieldProvenance.contract_id == contract.id,
        ContractFieldProvenance.field_key == "data_protection_relevant",
    )).first()
    if row is not None and row.origin != "ai":
        if contract.data_protection_relevant is not True:
            row.ai_proposed_value = {"value": True, "source_field": f"Dokumenttext: „{match.group(1)}“"}
        session.flush()
        return True
    contract.data_protection_relevant = True
    if row is None:
        session.add(ContractFieldProvenance(
            organization_id=contract.organization_id, contract_id=contract.id, field_key="data_protection_relevant",
            origin="ai", extraction_id=extraction_id, source_field=f"Dokumenttext: „{match.group(1)}“",
        ))
    session.flush()
    return True


# --------------------------------------------------------------------------- framework detection


def detect_framework_references(session: Session, contract: Contract, text: str) -> list[uuid.UUID]:
    """KI-Vorschlag: Der Text nennt einen Rahmenvertrag und eine Nummer eines
    bestehenden Rahmenvertrags derselben Organisation."""
    if not text or not _FRAMEWORK_WORD.search(text):
        return []
    haystack = re.sub(r"\s+", " ", text)
    candidates = session.scalars(
        select(Contract).where(
            Contract.organization_id == contract.organization_id,
            Contract.is_framework.is_(True),
            Contract.id != contract.id,
            Contract.lifecycle_state == "active",
        )
    ).all()
    created: list[uuid.UUID] = []
    for framework in candidates:
        numbers = {
            value.strip() for value in (framework.register_number, framework.internal_number, framework.contract_number)
            if value and len(value.strip()) >= _MIN_REFERENCE_LENGTH
        }
        hit = next((number for number in sorted(numbers) if re.search(rf"(?<![\w-]){re.escape(number)}(?![\w-])", haystack)), None)
        if hit is None:
            continue
        exists = session.scalar(select(ContractRelationRecord.id).where(
            ContractRelationRecord.source_contract_id == framework.id,
            ContractRelationRecord.target_contract_id == contract.id,
            ContractRelationRecord.relation_type == FRAMEWORK_RELATION,
        ))
        if exists is not None:
            continue
        session.add(ContractRelationRecord(
            organization_id=contract.organization_id,
            source_contract_id=framework.id,
            target_contract_id=contract.id,
            relation_type=FRAMEWORK_RELATION,
            authority="unknown",
            rationale=f"KI-Vorschlag: Dokument nennt Rahmenvertrag mit Nummer {hit}.",
            requires_review=True,
        ))
        created.append(framework.id)
    session.flush()
    return created


# --------------------------------------------------------------------------- documents


def list_documents(session: Session, contract: Contract) -> list[dict]:
    rows = session.execute(
        select(ContractDocument, DocumentVersion, DocumentFile)
        .join(DocumentVersion, DocumentVersion.id == ContractDocument.document_version_id)
        .join(DocumentFile, DocumentFile.id == DocumentVersion.document_file_id)
        .where(ContractDocument.contract_id == contract.id)
        .order_by(ContractDocument.is_main.desc(), ContractDocument.created_at)
    ).all()
    return [
        {
            "link_id": str(link.id),
            "document_version_id": str(version.id),
            "original_filename": file.original_filename,
            "title": link.title or file.original_filename,
            "attachment_type": link.attachment_type,
            "role": link.role,
            "is_main": link.is_main,
            "is_valid": link.is_valid,
            "added_by_name": link.added_by_name,
            "added_at": link.created_at.isoformat() if link.created_at else None,
            "analyzable": (link.attachment_type or "") in ANALYZABLE_TYPES,
        }
        for link, version, file in rows
    ]


def link_attachment(
    session: Session,
    *,
    contract: Contract,
    document_version_id: uuid.UUID,
    attachment_type: str,
    title: Optional[str],
    added_by_name: Optional[str],
) -> ContractDocument:
    link = session.scalars(select(ContractDocument).where(
        ContractDocument.contract_id == contract.id, ContractDocument.document_version_id == document_version_id
    )).first()
    has_main = session.scalar(select(ContractDocument.id).where(
        ContractDocument.contract_id == contract.id, ContractDocument.is_main.is_(True)
    )) is not None
    if link is None:
        link = ContractDocument(
            organization_id=contract.organization_id,
            contract_id=contract.id,
            document_version_id=document_version_id,
        )
        session.add(link)
    link.role = role_for(attachment_type)
    link.attachment_type = attachment_type
    link.title = (title or "").strip()[:255] or None
    link.added_by_name = added_by_name
    if not has_main and attachment_type == "vertrag":
        link.is_main = True
    session.flush()
    return link


def update_document(
    session: Session, *, contract: Contract, actor: RegisterActor, link_id: uuid.UUID, values: dict[str, Any], allowed_types: set[str]
) -> None:
    link = session.get(ContractDocument, link_id)
    if link is None or link.contract_id != contract.id:
        raise RegisterError(404, "Dokument nicht gefunden.")
    changes: dict[str, Any] = {}
    if "attachment_type" in values:
        value = values["attachment_type"]
        if value not in allowed_types:
            raise RegisterError(422, "Unbekannte Dokumentart.")
        link.attachment_type = value
        link.role = role_for(value)
        changes["attachment_type"] = value
    if "title" in values:
        value = values["title"]
        if value is not None and not isinstance(value, str):
            raise RegisterError(422, "Bezeichnung: Text erwartet.")
        link.title = (value or "").strip()[:255] or None
        changes["title"] = link.title
    if "is_valid" in values:
        if not isinstance(values["is_valid"], bool):
            raise RegisterError(422, "Gültig: Ja/Nein erwartet.")
        if link.is_main and values["is_valid"] is False:
            raise RegisterError(409, "Das Hauptdokument kann nicht ungültig gesetzt werden. Bitte zuerst ein anderes Hauptdokument festlegen.")
        link.is_valid = values["is_valid"]
        changes["is_valid"] = link.is_valid
    if values.get("is_main") is True:
        if not link.is_valid:
            raise RegisterError(409, "Ein ungültiges Dokument kann nicht Hauptdokument sein.")
        for other in session.scalars(select(ContractDocument).where(
            ContractDocument.contract_id == contract.id, ContractDocument.is_main.is_(True), ContractDocument.id != link.id
        )).all():
            other.is_main = False
        session.flush()
        link.is_main = True
        changes["is_main"] = True
    if changes:
        log_activity(session, actor, contract.id, "contract.document_updated", {"link_id": str(link.id), "changes": changes})
    session.flush()


# --------------------------------------------------------------------------- relations


def relation_payloads(session: Session, contract: Contract, allowed: Optional[set[uuid.UUID]] = None) -> dict:
    rows = [
        row for row in session.scalars(select(ContractRelationRecord).where(
            ContractRelationRecord.relation_type == FRAMEWORK_RELATION,
            or_(ContractRelationRecord.source_contract_id == contract.id, ContractRelationRecord.target_contract_id == contract.id),
        )).all()
        if allowed is None or (row.source_contract_id if row.target_contract_id == contract.id else row.target_contract_id) in allowed
    ]
    other_ids = {row.source_contract_id if row.target_contract_id == contract.id else row.target_contract_id for row in rows}
    others = {
        row.id: row for row in session.scalars(select(Contract).where(Contract.id.in_(other_ids))).all()
    } if other_ids else {}

    def item(row: ContractRelationRecord, other_id: uuid.UUID) -> dict:
        other = others.get(other_id)
        return {
            "relation_id": str(row.id),
            "contract_id": str(other_id),
            "register_number": other.register_number if other else None,
            "short_description": (other.short_description or other.supplier) if other else None,
            "business_status": other.business_status if other else None,
            "confirmed": not row.requires_review,
            "rationale": row.rationale,
        }

    return {
        "is_framework": contract.is_framework,
        "frameworks": [item(row, row.source_contract_id) for row in rows if row.target_contract_id == contract.id],
        "members": [item(row, row.target_contract_id) for row in rows if row.source_contract_id == contract.id],
    }


def link_framework(session: Session, *, contract: Contract, actor: RegisterActor, framework_id: uuid.UUID) -> None:
    framework = session.get(Contract, framework_id)
    if framework is None or framework.organization_id != contract.organization_id or framework.lifecycle_state != "active":
        raise RegisterError(422, "Rahmenvertrag nicht verfügbar.")
    if framework.id == contract.id:
        raise RegisterError(422, "Ein Vertrag kann nicht zu sich selbst gehören.")
    if not framework.is_framework:
        raise RegisterError(422, "Der gewählte Vertrag ist nicht als Rahmenvertrag gekennzeichnet.")
    row = session.scalars(select(ContractRelationRecord).where(
        ContractRelationRecord.source_contract_id == framework.id,
        ContractRelationRecord.target_contract_id == contract.id,
        ContractRelationRecord.relation_type == FRAMEWORK_RELATION,
    )).first()
    if row is None:
        row = ContractRelationRecord(
            organization_id=contract.organization_id,
            source_contract_id=framework.id,
            target_contract_id=contract.id,
            relation_type=FRAMEWORK_RELATION,
        )
        session.add(row)
    row.requires_review = False
    row.authority = "primary"
    row.rationale = f"Bestätigt von {actor.display_name or 'Benutzer'}."
    log_activity(session, actor, contract.id, "contract.framework_linked", {"framework_id": str(framework.id)})
    session.flush()


def unlink_framework(session: Session, *, contract: Contract, actor: RegisterActor, relation_id: uuid.UUID) -> None:
    row = session.get(ContractRelationRecord, relation_id)
    if row is None or row.relation_type != FRAMEWORK_RELATION or contract.id not in (row.source_contract_id, row.target_contract_id):
        raise RegisterError(404, "Verknüpfung nicht gefunden.")
    log_activity(session, actor, contract.id, "contract.framework_unlinked", {
        "framework_id": str(row.source_contract_id), "member_id": str(row.target_contract_id),
        "was_suggestion": row.requires_review,
    })
    session.delete(row)
    session.flush()


def framework_options(session: Session, contract: Contract, allowed: Optional[set[uuid.UUID]]) -> list[dict]:
    stmt = select(Contract).where(
        Contract.organization_id == contract.organization_id,
        Contract.is_framework.is_(True),
        Contract.lifecycle_state == "active",
        Contract.id != contract.id,
    ).order_by(Contract.register_number)
    if allowed is not None:
        stmt = stmt.where(Contract.id.in_(allowed))
    return [
        {"contract_id": str(row.id), "register_number": row.register_number, "short_description": row.short_description or row.supplier}
        for row in session.scalars(stmt).all()
    ]
