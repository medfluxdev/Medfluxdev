"""Vertrags-Portfolio-Route (STEP 13) – GET /api/contracts.

Duenne READ-Schicht -> `app.contracts.search`. Alle Parameter typisiert und
allowlist-validiert; Organisation wird server-seitig via `organization_slug`
aufgeloest; alle Abfragen sind org-gebunden (Query-Ebene, KEIN client-Filter).
`sas.` `as_of_date` wird an der API-Grenze aufgeloest und abwaerts gereicht.
Ungueltige Werte -> 422 (sauber); interne Fehler -> generischer Deutscher Text.

Hinweis (STEP 13 Checkpoint §17): `organization_slug` ist hier REIN ein
Routing-/Kontext-Schluessel, KEINE Autorisierungs-Credential. Vollstaendige
Identiaet/Autorisierung folgt in STEP 16.
"""

from __future__ import annotations

import urllib.parse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from app.core.clock import today_local
from app.core.scope_context import current_scope_context
from app.core.config import settings
from app.database.scope_queries import scoped_contract_ids

from app.auth.context import reviewer_name
from app.contracts.overrides.keys import (
    OVERRIDE_KEY_TAX_BASIS,
    OVERRIDE_KEY_TAX_RATE_PERCENT,
    OVERRIDE_KEY_EVENT_START,
)
from app.contracts.overrides.service import OverrideError, record_override

from app.contracts.search import (
    PAGE_SIZES,
    RISK_ALLOWLIST,
    SORT_ALLOWLIST,
    STATUS_ALLOWLIST,
    VALID_DIRECTIONS,
    WARNING_TYPE_ALLOWLIST,
)
from app.contracts.search.models import ContractListResponse
from app.contracts.search.service import SearchError, SearchParams, build_contract_search
from app.contracts.detail.models import ContractDetailResponse
from app.contracts.detail.service import DetailError, build_contract_detail
from app.contracts.review.material import material_report
from app.contracts.review.service import (
    ReviewConflict,
    ReviewError,
    build_fact_review_states,
    build_review_summary,
    complete_review,
    record_fact_action,
    review_detail_response,
    start_review,
)
from app.documents.status import build_import_state
from app.database.models.activity_log import ActivityLog
from app.database.models.contract import BUSINESS_STATUS_ALLOWED
from app.database.models import (
    Contract,
    DocumentFile,
    DocumentVersion,
    Organization,
)
from app.database.services import get_organization
from app.database.session import create_session
from app.documents.persistence import DocumentPersistenceService
from app.documents.storage import StorageError

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


class OverrideRequest(BaseModel):
    """Manuelle Bestätigung/Override eines materialen Vertragsfakts (UAT Batch A)."""

    key: str
    action: str = "set"  # set | void | confirm
    value: Optional[object] = None  # str/Number/ISO-Datum je key; wird kanonisiert
    fact_ref: Optional[str] = None
    note: Optional[str] = None


class FactReviewRequest(BaseModel):
    """Faktgenaue manuelle Prüf-Aktion (Customer-Demo-Readiness).

    `confirmed` bestätigt den System-Wert (kein Override):
    `corrected` überschreibt ihn mit `corrected_value`.
    """

    fact_key: str
    action: str = "confirmed"  # confirmed | corrected | voided | reopened
    corrected_value: Optional[object] = None
    system_value: Optional[object] = None
    reviewer_display_name: Optional[str] = None
    note: Optional[str] = None
    evidence_ref: Optional[str] = None
    # Optionaler Versionsstand (reviewed_at der Angabe beim Laden; null = noch ungeprüft).
    # Weicht der aktuelle Stand ab, antwortet der Server mit 409 statt still zu überschreiben.
    expected_reviewed_at: Optional[str] = None


class ReviewLifecycleRequest(BaseModel):
    """Start/Abschluss des manuellen Vertragsreviews."""

    reviewer_display_name: Optional[str] = None
    note: Optional[str] = None
    acknowledge_unreviewed: bool = False


def _build_augmented_detail(session, *, organization_id, contract_id):
    """Detail-Read-Model + Importzustand + faktgenaue Prüfung + Vertragsreview."""
    data = build_contract_detail(
        session, organization_id=organization_id, contract_id=contract_id
    )
    if data is None:
        return None
    data = review_detail_response(
        session, organization_id=organization_id, contract_id=contract_id, data=data
    )
    data["import_state"] = build_import_state(
        session, organization_id=organization_id, contract_id=contract_id, detail=data
    )
    return data


def _record_account_activity(
    session,
    request: Request,
    event_name: str,
    contract_id: UUID,
    context_data: dict | None = None,
) -> None:
    """Mirror authenticated Ahmad account actions into its activity stream."""
    actor = getattr(request.state, "actor", None)
    if actor is None:
        return
    scope = current_scope_context()
    session.add(
        ActivityLog(
            organization_id=actor.organization_id,
            hospital_id=scope.hospital_id,
            department_id=scope.department_id,
            account_id=actor.account_id,
            display_name_snapshot=actor.display_name,
            role_snapshot=actor.role,
            event_name=event_name,
            object_type="contract",
            object_id=contract_id,
            context_data=context_data,
        )
    )


def _scope_denies(session, organization_id, contract_id: UUID) -> bool:
    """Scope-Isolation ohne Demo-/UAT-Sonderzustand."""
    scope = current_scope_context()
    allowed = scoped_contract_ids(
        session, organization_id, scope.hospital_id, scope.department_id
    )
    if allowed is None:
        return False
    return contract_id not in allowed


def _canonical_override_value(key: str, value):
    """Kanonisiert den Client-Wert in das persistente JSONB-Schema je key."""
    if key == OVERRIDE_KEY_TAX_BASIS:
        return {"value": str(value).strip().lower()}
    if key == OVERRIDE_KEY_TAX_RATE_PERCENT:
        try:
            return {"percent": float(value)}
        except (TypeError, ValueError):
            _invalid("Steuersatz muss eine Zahl sein.")
            return None
    if key == OVERRIDE_KEY_EVENT_START:
        return {"date": str(value).strip()}
    return {"value": value}


def _invalid(detail: str):
    raise HTTPException(status_code=422, detail=detail)


def _validate_list(values, allowlist, name):
    out = []
    for v in values:
        if v not in allowlist:
            _invalid(f"Ungueltiger Wert fuer '{name}': {v!r}")
        out.append(v)
    return out


def _parse_decimal(value: Optional[str], name: str) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        _invalid(f"Ungueltiger Betrag fuer '{name}'.")
    return None


@router.get("", response_model=ContractListResponse)
def contract_list(
    request: Request,
    organization_slug: str,
    q: Optional[str] = Query(default=None, max_length=200),
    status: list[str] = Query(default=[]),
    business_status: list[str] = Query(default=[]),
    risk: list[str] = Query(default=[]),
    warning_type: list[str] = Query(default=[]),
    requires_action: Optional[bool] = None,
    requires_review: Optional[bool] = None,
    critical_cancellation: Optional[bool] = None,
    automatic_renewal: Optional[bool] = None,
    archived: Optional[bool] = None,
    supplier: Optional[str] = Query(default=None, max_length=255),
    contract_number: Optional[str] = Query(default=None, max_length=80),
    cost_center_code: Optional[str] = Query(default=None, max_length=80),
    currency: Optional[str] = Query(default=None, max_length=3),
    annual_cost_min: Optional[str] = None,
    annual_cost_max: Optional[str] = None,
    start_date_from: Optional[date] = None,
    start_date_to: Optional[date] = None,
    end_date_from: Optional[date] = None,
    end_date_to: Optional[date] = None,
    cancellation_from: Optional[date] = None,
    cancellation_to: Optional[date] = None,
    sort: str = Query(default="operational"),
    direction: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25),
) -> ContractListResponse:
    if sort not in SORT_ALLOWLIST:
        _invalid(f"Ungueltiger Sort-Wert: {sort!r}")
    if direction not in VALID_DIRECTIONS:
        _invalid(f"Ungueltige Sortierrichtung: {direction!r}")
    if page_size not in PAGE_SIZES:
        _invalid("page_size muss 25, 50 oder 100 sein.")

    status = _validate_list(status, STATUS_ALLOWLIST, "status")
    business_status = _validate_list(business_status, BUSINESS_STATUS_ALLOWED, "business_status")
    risk = _validate_list(risk, RISK_ALLOWLIST, "risk")
    warning_type = _validate_list(warning_type, WARNING_TYPE_ALLOWLIST, "warning_type")

    today: date = today_local()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()

        params = SearchParams(
            organization_id=org.id,
            q=q,
            status=status,
            business_status=business_status,
            risk=risk,
            warning_type=warning_type,
            requires_action=requires_action,
            requires_review=requires_review,
            critical_cancellation=critical_cancellation,
            automatic_renewal=automatic_renewal,
            archived=archived,
            supplier=supplier.strip() if supplier else None,
            contract_number=contract_number.strip() if contract_number else None,
            cost_center_code=cost_center_code,
            currency=currency.strip().upper() if currency else None,
            annual_cost_min=_parse_decimal(annual_cost_min, "annual_cost_min"),
            annual_cost_max=_parse_decimal(annual_cost_max, "annual_cost_max"),
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            end_date_from=end_date_from,
            end_date_to=end_date_to,
            cancellation_from=cancellation_from,
            cancellation_to=cancellation_to,
            sort=sort,
            direction=direction,
            page=page,
            page_size=page_size,
        )
        try:
            data = build_contract_search(
                session,
                params,
                organization_id=org.id,
                request_as_of=today,
                workspace_contract_ids=scoped_contract_ids(
                    session,
                    org.id,
                    current_scope_context().hospital_id,
                    current_scope_context().department_id,
                ),
            )
        except SearchError as exc:
            raise HTTPException(status_code=400, detail=exc.detail_de)
        return ContractListResponse.model_validate(data)
    finally:
        session.close()


_VALID_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    ),
}


def _not_found():
    return HTTPException(status_code=404, detail="Ressource nicht gefunden.")


def _safe_content_disposition(filename: Optional[str], mime: str) -> str:
    """Client-Filename wird NICHT vertraut; Base-Name + RFC-5987-Encode."""
    base = "dokument"
    if filename:
        base = filename.replace("\\", "/").split("/")[-1].replace("\x00", "").strip()
        if not base:
            base = "dokument"
    encoded = urllib.parse.quote(base)
    if mime == "application/pdf":
        return f"inline; filename*=UTF-8''{encoded}"
    return f"attachment; filename*=UTF-8''{encoded}"


@router.get("/deletion/queue")
def contract_deletion_queue(request: Request, organization_slug: str, offset: int = Query(default=0, ge=0, le=100000)) -> dict:
    """Bounded, org-scoped administrative queue; excludes active contracts."""
    _require_explicit_delete_permission(request)
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()
        scope = current_scope_context()
        visible = scoped_contract_ids(session, org.id, scope.hospital_id, scope.department_id)
        query = select(Contract).where(
            Contract.organization_id == org.id,
            Contract.lifecycle_state.in_(("pending_deletion", "deleted")),
        )
        if visible is not None:
            query = query.where(Contract.id.in_(visible))
        rows = session.scalars(query.order_by(Contract.id).offset(offset).limit(101)).all()
        return {
            "items": [
                {"contract_id": str(row.id), "contract_number": row.contract_number,
                 "lifecycle_state": row.lifecycle_state}
                for row in rows[:100]
            ],
            "has_more": len(rows) > 100,
            "next_offset": offset + 100 if len(rows) > 100 else None,
        }
    finally:
        session.close()


@router.get("/capabilities/deletion")
def contract_deletion_capabilities(request: Request, organization_slug: str) -> dict:
    """Server-authoritative UI capability; never trust client-side role checks."""
    actor = getattr(request.state, "actor", None)
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor is None or actor.organization_id != org.id:
            raise _not_found()
        allowed = bool(settings.auth_enabled and settings.contracts_allow_delete
                       and (actor.role or "").casefold() == "admin")
        return {"can_delete": allowed, "can_restore": allowed,
                "requires_confirmation": True}
    finally:
        session.close()


@router.get("/{contract_id}", response_model=ContractDetailResponse)
def contract_detail(
    request: Request,
    organization_slug: str,
    contract_id: str,
) -> ContractDetailResponse:
    try:
        cid = UUID(contract_id)
    except ValueError:
        raise _not_found()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()
        if _scope_denies(session, org.id, cid):
            raise _not_found()
        try:
            data = _build_augmented_detail(
                session, organization_id=org.id, contract_id=cid
            )
        except DetailError as exc:
            raise HTTPException(status_code=500, detail=exc.detail_de)
        if data is None:
            raise _not_found()
        return ContractDetailResponse.model_validate(data)
    finally:
        session.close()


@router.post("/{contract_id}/fact-reviews", response_model=ContractDetailResponse)
def contract_fact_review(
    request: Request,
    organization_slug: str,
    contract_id: str,
    payload: FactReviewRequest,
) -> ContractDetailResponse:
    """Append-only Prüf-Aktion zu einem materialen Fakt (Bestätigen/Korrigieren/...).

    `confirmed` ändert den Wert NIE (kein manueller Override); `corrected`
    setzt den neuen wirksamen Wert; beide Aktionen sind im Audit sichtbar.
    """
    try:
        cid = UUID(contract_id)
    except ValueError:
        raise _not_found()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()
        if _scope_denies(session, org.id, cid):
            raise _not_found()
        try:
            data = build_contract_detail(
                session, organization_id=org.id, contract_id=cid
            )
            if data is None:
                raise _not_found()
            system_value = payload.system_value
            if system_value is None:
                system_value = (material_report(data).get(payload.fact_key) or {}).get(
                    "value"
                )
            # Vertragsdaten-Feld zur Angabe: Korrektur vorab lesen (nicht lesbar -> nichts speichern).
            from app.register.fields import FieldValidationError
            from app.register.service import review_register_changes

            try:
                register_base, register_changes = review_register_changes(
                    payload.fact_key, payload.action, payload.corrected_value
                )
            except FieldValidationError as exc:
                raise ReviewError(getattr(exc, "detail_de", str(exc))) from exc
            record_fact_action(
                session,
                organization_id=org.id,
                contract_id=cid,
                fact_key=payload.fact_key,
                action=payload.action,
                reviewer_display_name=reviewer_name(
                    request, payload.reviewer_display_name
                ),
                note=payload.note,
                system_value=system_value,
                corrected_value=payload.corrected_value,
                evidence_ref=payload.evidence_ref,
                **({"expected_reviewed_at": payload.expected_reviewed_at}
                   if "expected_reviewed_at" in payload.model_fields_set else {}),
            )
            _record_account_activity(
                session,
                request,
                f"fact_review.{payload.action}",
                cid,
                {"fact_key": payload.fact_key},
            )
            _review_into_register(request, organization_slug, session, cid, register_base, register_changes)
            session.commit()
        except ReviewConflict as exc:
            session.rollback()
            raise HTTPException(status_code=409, detail=exc.detail_de)
        except ReviewError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        try:
            data = _build_augmented_detail(
                session, organization_id=org.id, contract_id=cid
            )
        except DetailError as exc:
            raise HTTPException(status_code=500, detail=exc.detail_de)
        if data is None:
            raise _not_found()
        return ContractDetailResponse.model_validate(data)
    finally:
        session.close()


def _review_into_register(request: Request, organization_slug: str, session, contract_id: UUID, base, changes) -> None:
    """Pruefung und Vertragsdaten zeigen denselben Wert: Korrektur/Bestaetigung uebernehmen.

    Nur mit Bearbeitungsrecht (Pruefer ohne `contract.edit` aendern die Vertragsdaten nicht);
    von Hand gepflegte Werte werden bei einer Bestaetigung nicht beruehrt.
    """
    if base is None:
        return
    from app.api.routes.contract_register import _register_actor
    from app.auth.permissions import can
    from app.deadlines.system import sync_system_deadlines
    from app.register.service import RegisterError, apply_review_to_register

    try:
        actor = _register_actor(request, organization_slug)
    except HTTPException:
        # Ohne angemeldetes Konto keine Rechtegrundlage: Vertragsdaten bleiben unveraendert.
        return
    if not can(actor, "contract.edit"):
        return
    contract = session.get(Contract, contract_id, with_for_update=True)
    if contract is None or contract.business_status == "geloescht":
        return
    try:
        if apply_review_to_register(session, contract=contract, actor=actor, base=base, changes=changes):
            sync_system_deadlines(session, contract, today_local())
    except RegisterError as exc:
        raise ReviewError(exc.detail_de) from exc


@router.post("/{contract_id}/review/start", response_model=ContractDetailResponse)
def contract_review_start(
    request: Request,
    organization_slug: str,
    contract_id: str,
    payload: ReviewLifecycleRequest,
) -> ContractDetailResponse:
    try:
        cid = UUID(contract_id)
    except ValueError:
        raise _not_found()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()
        if _scope_denies(session, org.id, cid):
            raise _not_found()
        try:
            start_review(
                session,
                organization_id=org.id,
                contract_id=cid,
                reviewer_display_name=reviewer_name(
                    request, payload.reviewer_display_name
                ),
                note=payload.note,
            )
            _record_account_activity(
                session, request, "contract_review.started", cid
            )
            session.commit()
        except ReviewError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()


@router.post("/{contract_id}/review/complete", response_model=ContractDetailResponse)
def contract_review_complete(
    request: Request,
    organization_slug: str,
    contract_id: str,
    payload: ReviewLifecycleRequest,
) -> ContractDetailResponse:
    """Expliziter menschlicher Abschluss des Vertragsreviews.

    Kritische ungeprüfte Angaben blockieren den Abschluss immer. Nur verbleibende
    nicht-kritische Angaben dürfen mit `acknowledge_unreviewed` + Notiz quittiert
    werden – sonst 422 (kein unbemerktes „Durchwinken").
    """
    try:
        cid = UUID(contract_id)
    except ValueError:
        raise _not_found()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()
        if _scope_denies(session, org.id, cid):
            raise _not_found()
        try:
            data = build_contract_detail(
                session, organization_id=org.id, contract_id=cid
            )
            if data is None:
                raise _not_found()
            states = build_fact_review_states(
                session, organization_id=org.id, contract_id=cid, data=data
            )
            summary = build_review_summary(states)
            complete_review(
                session,
                organization_id=org.id,
                contract_id=cid,
                reviewer_display_name=reviewer_name(
                    request, payload.reviewer_display_name
                ),
                note=payload.note,
                acknowledge_unreviewed=payload.acknowledge_unreviewed,
                relevant_count=summary["relevant_count"],
                reviewed_count=summary["reviewed_count"],
                critical_unreviewed_count=summary["critical_unreviewed_count"],
            )
            _record_account_activity(
                session,
                request,
                "contract_review.completed",
                cid,
                {
                    "acknowledge_unreviewed": bool(
                        payload.acknowledge_unreviewed
                    )
                },
            )
            session.commit()
        except ReviewError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()


def _augmented_detail_response(session, organization_id, contract_id) -> ContractDetailResponse:
    try:
        data = _build_augmented_detail(
            session, organization_id=organization_id, contract_id=contract_id
        )
    except DetailError as exc:
        raise HTTPException(status_code=500, detail=exc.detail_de)
    if data is None:
        raise _not_found()
    return ContractDetailResponse.model_validate(data)


def _set_archived(session, organization_id, contract_id, archived: bool) -> None:
    """Archivieren/Ausarchivieren (reversibel, nicht-destruktiv).

    Archivierte Verträge bleiben vollständig erhalten (Nachweise, Prüfungen,
    Audit, Gerätebeziehungen) und erscheinen nicht mehr im aktiven Portfolio.
    """
    contract = session.execute(
        select(Contract).where(
            (Contract.id == contract_id)
            & (Contract.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if contract is None:
        raise _not_found()
    from datetime import datetime, timezone
    contract.is_archived = archived
    contract.archived_at = (
        datetime.now(timezone.utc) if archived else None
    )


@router.post("/{contract_id}/archive", response_model=ContractDetailResponse)
def contract_archive(
    request: Request,
    organization_slug: str,
    contract_id: str,
) -> ContractDetailResponse:
    """Vertrag nicht-destruktiv ins Archiv verschieben (reversibel)."""
    try:
        cid = UUID(contract_id)
    except ValueError:
        raise _not_found()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()
        if _scope_denies(session, org.id, cid):
            raise _not_found()
        existing = session.execute(
            select(Contract.id).where(
                (Contract.id == cid)
                & (Contract.organization_id == org.id)
                & (Contract.lifecycle_state == "active")
            )
        ).scalar_one_or_none()
        if existing is None:
            raise _not_found()
        _set_archived(session, org.id, cid, True)
        _record_account_activity(
            session, request, "contract.archived", cid
        )
        session.commit()
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()


@router.post("/{contract_id}/unarchive", response_model=ContractDetailResponse)
def contract_unarchive(
    request: Request,
    organization_slug: str,
    contract_id: str,
) -> ContractDetailResponse:
    """Archivierten Vertrag wieder in das aktive Portfolio zurückholen."""
    try:
        cid = UUID(contract_id)
    except ValueError:
        raise _not_found()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()
        if _scope_denies(session, org.id, cid):
            raise _not_found()
        existing = session.execute(
            select(Contract.id).where(
                (Contract.id == cid)
                & (Contract.organization_id == org.id)
                & (Contract.lifecycle_state == "active")
            )
        ).scalar_one_or_none()
        if existing is None:
            raise _not_found()
        _set_archived(session, org.id, cid, False)
        _record_account_activity(
            session, request, "contract.unarchived", cid
        )
        session.commit()
        return _augmented_detail_response(session, org.id, cid)
    finally:
        session.close()



def _require_explicit_delete_permission(request: Request) -> None:
    """Fail closed: deleting and restoring require an explicit server opt-in."""
    actor = getattr(request.state, "actor", None)
    if not settings.auth_enabled or actor is None:
        raise HTTPException(status_code=403, detail="Vertragslöschung ist nicht freigegeben.")
    if not settings.contracts_allow_delete or (actor.role or "").casefold() != "admin":
        raise HTTPException(status_code=403, detail="Vertragslöschung ist nicht freigegeben.")


def actor_org_mismatch(request: Request, organization_id) -> bool:
    # Auth-off is permitted only with explicit insecure opt-in in dev/test.
    # Keep pilot/production and every auth-enabled request fail-closed.
    if (
        not settings.auth_enabled
        and settings.medflux_insecure_dev
        and settings.app_env.strip().casefold() in {"development", "test"}
    ):
        return False
    actor = getattr(request.state, "actor", None)
    return actor is None or actor.organization_id != organization_id


def _deletion_transition(request: Request, organization_slug: str, contract_id: str, *,
                         expected: str, target: str) -> dict:
    _require_explicit_delete_permission(request)
    try:
        cid = UUID(contract_id)
    except ValueError:
        raise _not_found()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id) or _scope_denies(session, org.id, cid):
            raise _not_found()
        row = session.execute(
            select(Contract).where(
                Contract.id == cid,
                Contract.organization_id == org.id,
                Contract.lifecycle_state == expected,
            ).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise _not_found()
        actor = request.state.actor
        if target == "pending_deletion" and row.is_archived:
            raise HTTPException(status_code=409, detail="Archivierten Vertrag zuerst wiederherstellen.")
        row.lifecycle_state = target
        if target in {"pending_deletion", "deleted"}:
            row.deletion_owner = str(actor.account_id)
            row.deleted_at = datetime.now(timezone.utc) if target == "deleted" else None
        else:
            row.deletion_owner = None
            row.deleted_at = None
        audit_event = {
            ("active", "pending_deletion"): "contract.deletion_requested",
            ("pending_deletion", "active"): "contract.deletion_cancelled",
            ("pending_deletion", "deleted"): "contract.deletion_confirmed",
            ("deleted", "active"): "contract.restored",
        }[(expected, target)]
        _record_account_activity(session, request, audit_event, cid,
                                 {"previous_state": expected, "new_state": target})
        session.commit()
        return {"contract_id": str(cid), "lifecycle_state": target}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@router.post("/{contract_id}/delete/request")
def request_contract_deletion(request: Request, organization_slug: str, contract_id: str):
    return _deletion_transition(request, organization_slug, contract_id,
                                expected="active", target="pending_deletion")


@router.post("/{contract_id}/delete/cancel")
def cancel_contract_deletion(request: Request, organization_slug: str, contract_id: str):
    return _deletion_transition(request, organization_slug, contract_id,
                                expected="pending_deletion", target="active")


@router.post("/{contract_id}/delete/confirm")
def confirm_contract_deletion(request: Request, organization_slug: str, contract_id: str):
    return _deletion_transition(request, organization_slug, contract_id,
                                expected="pending_deletion", target="deleted")


@router.post("/{contract_id}/delete/restore")
def restore_contract_deletion(request: Request, organization_slug: str, contract_id: str):
    return _deletion_transition(request, organization_slug, contract_id,
                                expected="deleted", target="active")


@router.post("/{contract_id}/overrides", response_model=ContractDetailResponse)
def contract_override(
    request: Request,
    organization_slug: str,
    contract_id: str,
    payload: OverrideRequest,
) -> ContractDetailResponse:
    """Manuelle Bestätigung/Override eines materialen Vertragsfakts (append-only).

    Legt eine neue `contract_override`-Zeile an (Audit). Antwort = frisch
    aufgebautes Detail-Read-Model (wirksame Overrides + Netto/Brutto + Audit).
    Actor bleibt bis STEP 16 NULL / is_development=True (keine erfundene Identität).
    """
    try:
        cid = UUID(contract_id)
    except ValueError:
        raise _not_found()
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()
        if _scope_denies(session, org.id, cid):
            raise _not_found()
        try:
            value = None
            if payload.action == "set":
                value = _canonical_override_value(payload.key, payload.value)
            record_override(
                session,
                organization_id=org.id,
                contract_id=cid,
                key=payload.key,
                action=payload.action,
                value=value,
                fact_ref=payload.fact_ref,
                note=payload.note,
            )
            _record_account_activity(
                session,
                request,
                f"override.{payload.action}",
                cid,
                {"key": payload.key, "fact_ref": payload.fact_ref},
            )
            session.commit()
        except OverrideError as exc:
            session.rollback()
            raise HTTPException(status_code=422, detail=exc.detail_de)
        try:
            data = build_contract_detail(
                session, organization_id=org.id, contract_id=cid
            )
        except DetailError as exc:
            raise HTTPException(status_code=500, detail=exc.detail_de)
        if data is None:
            raise _not_found()
        return ContractDetailResponse.model_validate(data)
    finally:
        session.close()


@router.get("/{contract_id}/documents/{document_version_id}/content")
def contract_document_content(
    request: Request,
    organization_slug: str,
    contract_id: str,
    document_version_id: str,
) -> Response:
    """Sicherer Byte-Zugriff auf ein Original-Dokument (org- & vertragsgebunden).

    Der Browser liefert NUR opaque IDs (contract_id, document_version_id). Die
    verschluesselte Storage-Referenz wird ausschliesslich im Backend aus der
    DB aufgeloest; es werden nie Pfade/Referenzen an den Client uebergeben.
    """
    try:
        cid = UUID(contract_id)
        vid = UUID(document_version_id)
    except ValueError:
        raise _not_found()

    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None or actor_org_mismatch(request, org.id):
            raise _not_found()
        if _scope_denies(session, org.id, cid):
            raise _not_found()
        svc = DocumentPersistenceService()
        version = session.scalars(
            select(DocumentVersion).where(
                (DocumentVersion.id == vid)
                & (DocumentVersion.organization_id == org.id)
            )
        ).first()
        if version is None:
            raise _not_found()

        # MIME-Allowlist: nur PDF/DOCX lieferbar.
        doc_file = None
        if version.document_file_id is not None:
            doc_file = session.get(DocumentFile, version.document_file_id)
        mime = (doc_file.mime_type if doc_file else None) or ""
        ext = (doc_file.file_extension or "").lower() if doc_file else ""
        if _VALID_CONTENT_TYPES.get(ext) != mime:
            raise HTTPException(status_code=415, detail="Dokumenttyp nicht lieferbar.")

        try:
            content = svc.resolve_bytes_for_version(
                session,
                organization_id=org.id,
                document_version_id=vid,
                contract_id=cid,
            )
        except StorageError:
            raise _not_found()

        # Single byte ranges only. Malformed/unsatisfiable requests return 416.
        total = len(content)
        start, end = 0, total - 1
        status_code = 200
        range_header = request.headers.get("range")
        if range_header:
            invalid_range = Response(
                status_code=416, headers={"Content-Range": f"bytes */{total}"}
            )
            if not range_header.startswith("bytes=") or total == 0:
                return invalid_range
            try:
                spec = range_header[6:]
                if spec.count("-") != 1 or "," in spec:
                    return invalid_range
                first, last = spec.split("-", 1)
                if first:
                    if not first.isdecimal() or (last and not last.isdecimal()):
                        return invalid_range
                    start = int(first)
                    end = total - 1 if not last else min(int(last), total - 1)
                else:
                    if not last.isdecimal() or int(last) == 0:
                        return invalid_range
                    start = max(0, total - int(last))
                    end = total - 1
                if start >= total or end < start:
                    return invalid_range
                status_code = 206
            except ValueError:
                return invalid_range

        body = content[start : end + 1]
        headers = {
            "Content-Type": mime,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Content-Disposition": _safe_content_disposition(
                doc_file.original_filename if doc_file else None, mime
            ),
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(body)),
        }
        if status_code == 206:
            headers["Content-Range"] = f"bytes {start}-{end}/{total}"
        return Response(
            content=body,
            status_code=status_code,
            headers=headers,
            media_type=mime,
        )
    finally:
        session.close()