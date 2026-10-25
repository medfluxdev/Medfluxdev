"""Vertragsregister-API (H1/H6): Stammdaten lesen/bearbeiten, KI-Vorschlaege
uebernehmen, manuell anlegen, Statuswechsel, Bemerkungen."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.clock import today_local
from app.auth.dependencies import current_actor
from app.auth.permissions import require
from app.core.scope_context import current_scope_context
from app.database.models import Contract, Department, Hospital
from app.database.scope_queries import scoped_contract_ids
from app.database.session import create_session
from app.deadlines.system import sync_system_deadlines
from app.register import catalogs, from_document
from app.register.evidence_reviews import list_evidence_reviews, log_evidence_round, set_evidence_review
from app.register.service import (
    RegisterActor,
    RegisterError,
    accept_ai_proposal,
    dismiss_ai_proposal,
    add_remark,
    edit_remark,
    capture_from_document,
    build_register,
    contract_hospitals,
    create_manual_contract,
    ensure_synced,
    list_remarks,
    delete_remark,
    log_activity,
    load_extracted,
    set_confidentiality,
    set_contract_hospitals,
    transition_status,
    update_register,
)

router = APIRouter(prefix="/api/contracts", tags=["contract-register"])


class RegisterUpdate(BaseModel):
    changes: dict[str, Any] = Field(default_factory=dict)
    confirm: list[str] = Field(default_factory=list)


class ContractCreate(BaseModel):
    hospital_id: Optional[UUID] = None
    values: dict[str, Any] = Field(default_factory=dict)


class StatusTransition(BaseModel):
    target: str
    effective_date: Optional[date] = None
    terminated_on: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)
    acknowledge_unreviewed: bool = False


class HospitalAssignment(BaseModel):
    hospital_ids: list[UUID] = Field(default_factory=list)
    primary_hospital_id: Optional[UUID] = None


class ConfidentialityUpdate(BaseModel):
    is_confidential: bool
    grant_account_ids: list[UUID] = Field(default_factory=list)


class RemarkCreate(BaseModel):
    body: str = Field(max_length=10000)


class EvidenceReviewUpdate(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=255)
    status: str = Field(max_length=16)
    fact_key: Optional[str] = Field(default=None, max_length=120)
    note: Optional[str] = Field(default=None, max_length=2000)


class EvidenceRound(BaseModel):
    confirmed: int = Field(default=0, ge=0, le=10000)
    document: int = Field(default=0, ge=0, le=10000)
    medflux: int = Field(default=0, ge=0, le=10000)
    manual: int = Field(default=0, ge=0, le=10000)
    skipped: int = Field(default=0, ge=0, le=10000)


class RemarkEdit(BaseModel):
    body: str = Field(max_length=10000)
    # Stand beim Öffnen (Feld `version` der Liste); abweichend = 409, damit keine Änderung verloren geht.
    expected_version: Optional[str] = None


def _register_actor(request: Request, organization_slug: str) -> RegisterActor:
    actor = current_actor(request, organization_slug)
    scope = current_scope_context()
    return RegisterActor(
        organization_id=actor.organization_id,
        account_id=actor.account_id,
        display_name=actor.display_name,
        role=actor.role,
        is_developer=bool(getattr(actor, "is_developer", False)),
        hospital_id=scope.hospital_id,
        department_id=scope.department_id,
    )


def _require_write(actor: RegisterActor, permission: str = "contract.edit") -> None:
    require(actor, permission, "Keine Berechtigung für diese Änderung.")


def _contract(session, actor: RegisterActor, contract_id: UUID, *, for_update: bool = False) -> Contract:
    stmt = select(Contract).where(Contract.id == contract_id, Contract.organization_id == actor.organization_id)
    if for_update:
        stmt = stmt.with_for_update()
    contract = session.scalars(stmt).first()
    if contract is None:
        raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    if actor.role != "admin" and not actor.is_developer:
        scope = current_scope_context()
        allowed = scoped_contract_ids(session, actor.organization_id, scope.hospital_id, scope.department_id)
        if allowed is not None and contract.id not in allowed:
            raise HTTPException(status_code=404, detail="Vertrag nicht gefunden.")
    return contract


def _http(exc: RegisterError) -> HTTPException:
    detail: Any = exc.detail_de
    if exc.field_key or exc.missing:
        detail = {"message": exc.detail_de, "field": exc.field_key, "missing": exc.missing}
    return HTTPException(status_code=exc.status_code, detail=detail)


def _register_payload(session, contract: Contract, actor: RegisterActor) -> dict:
    data = build_register(session, contract, actor)
    if contract.partner_id is None and contract.supplier:
        data["partner_suggestions"] = catalogs.similar_partners(session, actor.organization_id, contract.supplier, limit=3)
    else:
        data["partner_suggestions"] = []
    data["type_suggestion"] = None
    if contract.contract_type_id is None:
        ai_type = None
        if contract.accepted_extraction_id is not None:
            extracted = load_extracted(session, contract.accepted_extraction_id)
            ai_type = extracted.identity.contract_type.value if extracted else None
        data["type_suggestion"] = catalogs.type_suggestion(
            session, actor.organization_id, ai_type, contract.contract_title or contract.short_description
        )
    data["storage_location_label"] = catalogs.lookup_label(
        session, actor.organization_id, "storage_location", contract.storage_location_code
    )
    return data


@router.post("")
def create_contract(payload: ContractCreate, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor, "contract.create")
    session = create_session()
    try:
        hospital_id = payload.hospital_id or (actor.hospital_id if actor.role != "admin" else None)
        department_id = actor.department_id if actor.role != "admin" and not actor.is_developer else None
        if department_id is not None:
            department = session.get(Department, department_id)
            if department is None or department.organization_id != actor.organization_id:
                raise HTTPException(status_code=403, detail="Abteilung ist nicht verfügbar.")
            hospital_id = department.hospital_id
        if hospital_id is not None:
            hospital = session.get(Hospital, hospital_id)
            if hospital is None or hospital.organization_id != actor.organization_id:
                raise HTTPException(status_code=422, detail="Krankenhaus ist nicht verfügbar.")
            if actor.role != "admin" and not actor.is_developer and actor.hospital_id not in (None, hospital_id):
                raise HTTPException(status_code=403, detail="Keine Berechtigung für dieses Krankenhaus.")
        try:
            contract = create_manual_contract(
                session, actor=actor, values=payload.values, hospital_id=hospital_id, department_id=department_id
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        sync_system_deadlines(session, contract, today_local())
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.get("/{contract_id}/register")
def get_register(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        if ensure_synced(session, contract):
            sync_system_deadlines(session, contract, today_local())
            session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.get("/{contract_id}/partner-prefill")
def get_partner_prefill(contract_id: UUID, request: Request, organization_slug: str):
    """Angaben zum Vertragspartner, die die KI im Vertrag gefunden hat (zum Vorbelegen von „Neuer Partner“)."""
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        from app.register.partner_suggestions import prefill_for_new_partner

        return prefill_for_new_partner(session, contract)
    finally:
        session.close()


@router.patch("/{contract_id}/register")
def patch_register(contract_id: UUID, payload: RegisterUpdate, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            update_register(session, contract=contract, actor=actor, changes=payload.changes, confirm=payload.confirm)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        if payload.confirm:
            # Vertragsdaten und Faktprüfung zeigen denselben Prüfstand.
            from app.contracts.review.service import confirm_facts_from_register

            confirm_facts_from_register(
                session, organization_id=actor.organization_id, contract_id=contract.id,
                register_keys=payload.confirm, reviewer_display_name=actor.display_name,
            )
        sync_system_deadlines(session, contract, today_local())
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.post("/{contract_id}/register/proposals/{field_key}/accept")
def accept_proposal(contract_id: UUID, field_key: str, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            accept_ai_proposal(session, contract=contract, actor=actor, field_key=field_key)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        sync_system_deadlines(session, contract, today_local())
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.post("/{contract_id}/register/proposals/{field_key}/dismiss")
def dismiss_proposal(contract_id: UUID, field_key: str, request: Request, organization_slug: str):
    """KI-Vorschlag ignorieren: der gepflegte Wert bleibt, derselbe Wert wird nicht erneut vorgeschlagen."""
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            dismiss_ai_proposal(session, contract=contract, actor=actor, field_key=field_key)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


class RiskDecision(BaseModel):
    action: str = Field(pattern="^(confirm|override|reset)$")
    level: Optional[str] = Field(default=None, max_length=24)
    reason: Optional[str] = Field(default=None, max_length=500)


@router.post("/{contract_id}/risk")
def decide_contract_risk(contract_id: UUID, payload: RiskDecision, request: Request, organization_slug: str):
    """Risiko bestaetigen, mit Begruendung festlegen oder auf den berechneten Wert zuruecksetzen."""
    from app.contracts.risk import RiskError, decide_risk

    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            result = decide_risk(session, contract=contract, actor=actor, action=payload.action, level=payload.level, reason=payload.reason)
        except RiskError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de) from exc
        session.commit()
        return result
    finally:
        session.close()


class DocumentCapture(BaseModel):
    field_key: str = Field(max_length=64)
    document_version_id: UUID
    page: int = Field(ge=1, le=10000)
    quote: str = Field(min_length=1, max_length=4000)
    # Nur lesen und zeigen, wie der Wert gespeichert wuerde (nichts speichern).
    dry_run: bool = False


@router.get("/{contract_id}/documents/{document_version_id}/pages/{page}/text")
def document_page_text(contract_id: UUID, document_version_id: UUID, page: int, request: Request, organization_slug: str):
    """Text einer Seite, so wie MedFlux sie gelesen hat (auch OCR) – zum Markieren einer Fundstelle."""
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        result = from_document.page_text(session, contract=contract, document_version_id=document_version_id, page=page)
        if result is None:
            raise HTTPException(status_code=404, detail="Dokument nicht gefunden.")
        return result
    finally:
        session.close()


@router.post("/{contract_id}/register/from-document")
def capture_register_from_document(contract_id: UUID, payload: DocumentCapture, request: Request, organization_slug: str):
    """Angabe aus einer markierten Dokumentstelle uebernehmen (Wert per Code gelesen, Fundstelle gespeichert)."""
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            capture = from_document.prepare_capture(
                session, contract=contract, field_key=payload.field_key, document_version_id=payload.document_version_id,
                page=payload.page, quote=payload.quote,
            )
            if payload.dry_run:
                session.rollback()
                return {"preview": from_document.preview(payload.field_key, capture.changes), "page": capture.page, "quote": capture.quote}
            capture_from_document(session, contract=contract, actor=actor, capture=capture)
        except from_document.CaptureError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de) from exc
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        sync_system_deadlines(session, contract, today_local())
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.post("/{contract_id}/status")
def change_status(contract_id: UUID, payload: StatusTransition, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor, "contract.status")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            transition_status(
                session,
                contract=contract,
                actor=actor,
                target=payload.target,
                effective_date=payload.effective_date,
                terminated_on=payload.terminated_on,
                note=payload.note,
                acknowledge_unreviewed=payload.acknowledge_unreviewed,
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        sync_system_deadlines(session, contract, today_local())
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


@router.get("/{contract_id}/remarks")
def get_remarks(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        return {"items": list_remarks(session, contract.id)}
    finally:
        session.close()


@router.patch("/{contract_id}/remarks/{remark_id}")
def patch_remark(contract_id: UUID, remark_id: UUID, payload: RemarkEdit, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor, "remark.add")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        try:
            edit_remark(session, contract=contract, actor=actor, remark_id=remark_id, body=payload.body, expected_version=payload.expected_version)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": list_remarks(session, contract.id)}
    finally:
        session.close()


@router.delete("/{contract_id}/remarks/{remark_id}")
def remove_remark(contract_id: UUID, remark_id: UUID, request: Request, organization_slug: str, expected_version: Optional[str] = None):
    """Notiz löschen (weich, mit Protokoll); gleiches Recht wie Schreiben und Bearbeiten."""
    actor = _register_actor(request, organization_slug)
    _require_write(actor, "remark.add")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        try:
            delete_remark(session, contract=contract, actor=actor, remark_id=remark_id, expected_version=expected_version)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": list_remarks(session, contract.id)}
    finally:
        session.close()


@router.post("/{contract_id}/remarks")
def post_remark(contract_id: UUID, payload: RemarkCreate, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor, "remark.add")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        try:
            add_remark(session, contract=contract, actor=actor, body=payload.body)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": list_remarks(session, contract.id)}
    finally:
        session.close()


@router.get("/{contract_id}/evidence-reviews")
def get_evidence_reviews(contract_id: UUID, request: Request, organization_slug: str):
    """Ergebnis der Nachweisprüfung je Nachweis (bestätigt, abweichend …, übersprungen)."""
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        return {"items": list_evidence_reviews(session, contract.id)}
    finally:
        session.close()


@router.put("/{contract_id}/evidence-reviews")
def put_evidence_review(contract_id: UUID, payload: EvidenceReviewUpdate, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor, "contract.review")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        try:
            set_evidence_review(
                session, contract=contract, actor=actor, evidence_id=payload.evidence_id,
                status=payload.status, fact_key=payload.fact_key, note=payload.note,
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": list_evidence_reviews(session, contract.id)}
    finally:
        session.close()


@router.post("/{contract_id}/evidence-reviews/round")
def post_evidence_round(contract_id: UUID, payload: EvidenceRound, request: Request, organization_slug: str):
    """Ende einer Prüfrunde: Zusammenfassung in den Verlauf."""
    actor = _register_actor(request, organization_slug)
    _require_write(actor, "contract.review")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        try:
            summary = log_evidence_round(session, contract=contract, actor=actor, counts=payload.model_dump())
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"summary": summary}
    finally:
        session.close()


@router.get("/{contract_id}/hospitals")
def get_hospitals(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        return {"items": contract_hospitals(session, contract.id)}
    finally:
        session.close()


@router.put("/{contract_id}/hospitals")
def put_hospitals(contract_id: UUID, payload: HospitalAssignment, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        if actor.role != "admin" and not actor.is_developer and actor.hospital_id is not None:
            requested = set(payload.hospital_ids) | ({payload.primary_hospital_id} - {None})
            if requested - {actor.hospital_id}:
                raise HTTPException(status_code=403, detail="Nur Administratoren können weitere Gesellschaften zuordnen.")
        try:
            set_contract_hospitals(
                session,
                contract=contract,
                actor=actor,
                hospital_ids=payload.hospital_ids,
                primary_hospital_id=payload.primary_hospital_id,
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": contract_hospitals(session, contract.id)}
    finally:
        session.close()


@router.put("/{contract_id}/confidentiality")
def put_confidentiality(contract_id: UUID, payload: ConfidentialityUpdate, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor, "contract.confidential_manage")
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            set_confidentiality(
                session, contract=contract, actor=actor, is_confidential=payload.is_confidential,
                grant_account_ids=payload.grant_account_ids,
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()


# --------------------------------------------------------------------------- Gerätearten am Vertrag


class DeviceTypeItem(BaseModel):
    device_type_id: UUID
    quantity: Optional[int] = None
    note: Optional[str] = Field(default=None, max_length=255)


class DeviceTypeAssignment(BaseModel):
    items: list[DeviceTypeItem] = Field(default_factory=list, max_length=50)


def _device_type_payload(session, contract: Contract) -> dict:
    from app.register import device_types

    return {"items": device_types.contract_device_types(session, contract), "suggestions": device_types.suggestions(session, contract)}


@router.get("/{contract_id}/device-types")
def get_device_types(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        return _device_type_payload(session, _contract(session, actor, contract_id))
    finally:
        session.close()


@router.put("/{contract_id}/device-types")
def put_device_types(contract_id: UUID, payload: DeviceTypeAssignment, request: Request, organization_slug: str):
    from app.register import device_types
    from app.register.catalogs import CatalogError

    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            before, after = device_types.set_contract_device_types(session, contract, [item.model_dump(mode="json") for item in payload.items])
        except CatalogError as exc:
            session.rollback()
            raise HTTPException(status_code=exc.status_code, detail=exc.detail_de)
        if before != after:
            summary = lambda items: [f"{item['label']}{' × ' + str(item['quantity']) if item['quantity'] else ''}" for item in items]
            log_activity(session, actor, contract.id, "contract.device_types_updated", {"before": summary(before), "after": summary(after)})
        session.commit()
        return _device_type_payload(session, contract)
    finally:
        session.close()


# --------------------------------------------------------------------------- weitere Erinnerungen


class ReminderLead(BaseModel):
    value: int
    unit: str


class ReminderUpdate(BaseModel):
    extra_leads: list[ReminderLead] = Field(default_factory=list, max_length=10)


@router.put("/{contract_id}/reminders")
def put_reminders(contract_id: UUID, payload: ReminderUpdate, request: Request, organization_slug: str):
    """Weitere Erinnerungen vor Kündigungstermin/Vertragsende (die erste steht im Feld „Erinnerung“)."""
    from app.register.reminders import lead_label, normalize_leads

    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            leads = normalize_leads([item.model_dump() for item in payload.extra_leads])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        before = list(contract.reminder_extra_leads or [])
        if before != leads:
            contract.reminder_extra_leads = leads or None
            log_activity(session, actor, contract.id, "contract.reminders_updated", {
                "before": [lead_label(lead) for lead in before], "after": [lead_label(lead) for lead in leads],
            })
            session.flush()
            sync_system_deadlines(session, contract, today_local())
        session.commit()
        return _register_payload(session, contract, actor)
    finally:
        session.close()

