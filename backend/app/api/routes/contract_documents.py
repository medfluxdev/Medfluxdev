"""Vertragsdokumente und Rahmenvertrags-Verknuepfung (H3)."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.routes.contract_register import _contract, _register_actor, _require_write
from app.api.routes.documents import _read_upload_bounded
from app.core.scope_context import current_scope_context
from app.database.models.register import LookupValue
from app.database.scope_queries import scoped_contract_ids
from app.database.session import create_session
from app.documents.processing import DocumentProcessingService
from app.register.defaults import LOOKUPS
from app.register.documents import (
    framework_options,
    link_framework,
    list_documents,
    relation_payloads,
    unlink_framework,
    update_document,
)
from app.register.service import RegisterError

router = APIRouter(prefix="/api/contracts", tags=["contract-documents"])

_processing_service = DocumentProcessingService()


class DocumentUpdate(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class FrameworkLink(BaseModel):
    framework_contract_id: UUID


def _attachment_types(session, organization_id) -> set[str]:
    codes = set(session.scalars(select(LookupValue.code).where(
        LookupValue.organization_id == organization_id,
        LookupValue.field_key == "attachment_type",
        LookupValue.is_active.is_(True),
    )).all())
    return codes or {code for code, _, _ in LOOKUPS["attachment_type"]}


def _http(exc: RegisterError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail_de)


@router.get("/{contract_id}/documents")
def get_documents(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        return {"items": list_documents(session, contract), "attachment_types": sorted(_attachment_types(session, actor.organization_id))}
    finally:
        session.close()


@router.post("/{contract_id}/documents")
async def upload_documents(
    contract_id: UUID,
    request: Request,
    organization_slug: str,
    files: list[UploadFile] = File(...),
    attachment_type: str = Form(...),
    title: Optional[str] = Form(default=None, max_length=255),
    analyze: bool = Form(default=True),
):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    if not files or len(files) > 20:
        raise HTTPException(status_code=422, detail="Bitte 1 bis 20 Dateien hochladen.")
    session = create_session()
    try:
        _contract(session, actor, contract_id)
        if attachment_type not in _attachment_types(session, actor.organization_id):
            raise HTTPException(status_code=422, detail="Unbekannte Dokumentart.")
    finally:
        session.close()
    results = []
    for uploaded in files:
        raw = await _read_upload_bounded(uploaded)
        result = await run_in_threadpool(
            _processing_service.attach_to_contract,
            organization_slug=organization_slug,
            contract_id=contract_id,
            original_filename=uploaded.filename or "",
            content_type=uploaded.content_type or "",
            content=raw,
            attachment_type=attachment_type,
            title=title if len(files) == 1 else None,
            added_by_name=actor.display_name,
            analyze=analyze,
            as_of_date=date.today(),
        )
        results.append({
            "original_filename": uploaded.filename or "",
            "status": result.status,
            "message": result.message,
            "requires_review": result.requires_review,
            "document_version_id": result.document_version_id or None,
        })
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id)
        return {"results": results, "items": list_documents(session, contract)}
    finally:
        session.close()


@router.patch("/{contract_id}/documents/{link_id}")
def patch_document(contract_id: UUID, link_id: UUID, payload: DocumentUpdate, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            update_document(
                session, contract=contract, actor=actor, link_id=link_id, values=payload.values,
                allowed_types=_attachment_types(session, actor.organization_id),
            )
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return {"items": list_documents(session, contract)}
    finally:
        session.close()


def _relations(session, actor, contract) -> dict:
    scope = current_scope_context()
    allowed = None if actor.role == "admin" or actor.is_developer else scoped_contract_ids(
        session, actor.organization_id, scope.hospital_id, scope.department_id
    )
    return {**relation_payloads(session, contract), "framework_options": framework_options(session, contract, allowed)}


@router.get("/{contract_id}/relations")
def get_relations(contract_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    session = create_session()
    try:
        return _relations(session, actor, _contract(session, actor, contract_id))
    finally:
        session.close()


@router.post("/{contract_id}/relations")
def post_relation(contract_id: UUID, payload: FrameworkLink, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        _contract(session, actor, payload.framework_contract_id)
        try:
            link_framework(session, contract=contract, actor=actor, framework_id=payload.framework_contract_id)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return _relations(session, actor, contract)
    finally:
        session.close()


@router.delete("/{contract_id}/relations/{relation_id}")
def delete_relation(contract_id: UUID, relation_id: UUID, request: Request, organization_slug: str):
    actor = _register_actor(request, organization_slug)
    _require_write(actor)
    session = create_session()
    try:
        contract = _contract(session, actor, contract_id, for_update=True)
        try:
            unlink_framework(session, contract=contract, actor=actor, relation_id=relation_id)
        except RegisterError as exc:
            session.rollback()
            raise _http(exc)
        session.commit()
        return _relations(session, actor, contract)
    finally:
        session.close()
