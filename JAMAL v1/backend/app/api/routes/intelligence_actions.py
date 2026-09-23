"""Human-controlled lifecycle for intelligence action proposals.

No external side effect is executed here. `executed` means a human/operator has
confirmed completion of the approved proposal. Every transition is scoped and
audited. This keeps AI advisory and human authorization strictly separated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import ActionProposalRecord
from app.database.models.activity_log import ActivityLog
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/intelligence/actions", tags=["intelligence-actions"])

MANAGE_ROLES = {"admin", "contract_manager"}
TRANSITIONS = {
    "proposed": {"approved", "rejected", "cancelled"},
    "approved": {"executed", "cancelled"},
    "rejected": set(),
    "executed": set(),
    "cancelled": set(),
}


class ActionTransition(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=2000)


def _actor_or_forbid(request: Request):
    actor = getattr(request.state, "actor", None)
    if not settings.auth_enabled:
        return actor
    if actor is None:
        raise HTTPException(status_code=401, detail="Anmeldung erforderlich.")
    if not actor.is_developer and (actor.role or "").casefold() not in MANAGE_ROLES:
        raise HTTPException(status_code=403, detail="Keine Berechtigung für diese Aktion.")
    return actor


@router.patch("/{proposal_id}")
def transition_action_proposal(
    request: Request,
    proposal_id: UUID,
    organization_slug: str,
    body: ActionTransition,
):
    actor = _actor_or_forbid(request)
    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        row = session.get(ActionProposalRecord, proposal_id)
        if row is None or row.organization_id != org.id:
            raise HTTPException(status_code=404, detail="Aktionsvorschlag nicht gefunden.")

        scope = current_scope_context()
        allowed = scoped_contract_ids(session, org.id, scope.hospital_id, scope.department_id)
        if row.contract_id is not None and allowed is not None and row.contract_id not in allowed:
            raise HTTPException(status_code=404, detail="Aktionsvorschlag nicht gefunden.")

        target = body.status.casefold().strip()
        allowed_targets = TRANSITIONS.get(row.status, set())
        if target not in allowed_targets:
            raise HTTPException(
                status_code=422,
                detail=f"Ungültiger Übergang: {row.status} -> {target}.",
            )

        previous = row.status
        payload = dict(row.payload or {})
        history = list(payload.get("lifecycle_history") or [])
        actor_name = getattr(actor, "display_name", None) if actor is not None else "local-development"
        history.append({
            "from": previous,
            "to": target,
            "at": datetime.now(timezone.utc).isoformat(),
            "by": actor_name,
            "note": body.note,
        })
        payload["lifecycle_history"] = history
        row.payload = payload
        row.status = target

        if actor is not None:
            session.add(ActivityLog(
                organization_id=actor.organization_id,
                hospital_id=scope.hospital_id,
                department_id=scope.department_id,
                account_id=actor.account_id,
                display_name_snapshot=actor.display_name,
                role_snapshot="developer" if actor.is_developer else actor.role,
                event_name=f"intelligence_action.{target}",
                object_type="contract" if row.contract_id else "action_proposal",
                object_id=row.contract_id or row.id,
                context_data={
                    "proposal_id": str(row.id),
                    "kind": row.kind,
                    "previous_status": previous,
                    "status": target,
                    "note": body.note,
                },
            ))
        session.commit()
        return {
            "id": str(row.id),
            "contract_id": str(row.contract_id) if row.contract_id else None,
            "kind": row.kind,
            "reason": row.reason,
            "status": row.status,
            "assignee_role": row.assignee_role,
            "payload": row.payload or {},
            "evidence_refs": row.evidence_refs or [],
            "requires_human_approval": row.requires_human_approval,
        }
    finally:
        session.close()
