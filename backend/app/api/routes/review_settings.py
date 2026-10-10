"""Prüfmodus der Organisation: manuell oder nicht-kritische Angaben automatisch übernehmen."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import current_actor
from app.auth.permissions import can, require
from app.database.models.activity_log import ActivityLog
from app.database.models.organization import REVIEW_MODE_ALLOWED, Organization
from app.database.session import create_session

router = APIRouter(prefix="/api/review-settings", tags=["review-settings"])

MODE_LABELS = {
    "manual": "Jede Angabe prüft ein Mensch",
    "auto_noncritical": "Nicht-kritische Angaben mit eindeutigem Beleg automatisch übernehmen",
}


class ReviewSettingsUpdate(BaseModel):
    review_mode: str


def _payload(organization: Organization, actor) -> dict:
    return {
        "review_mode": organization.review_mode,
        "review_mode_label": MODE_LABELS.get(organization.review_mode, organization.review_mode),
        "options": [{"value": value, "label": MODE_LABELS[value]} for value in REVIEW_MODE_ALLOWED],
        "can_edit": can(actor, "review.settings"),
    }


@router.get("")
def get_review_settings(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    session = create_session()
    try:
        organization = session.get(Organization, actor.organization_id)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        return _payload(organization, actor)
    finally:
        session.close()


@router.put("")
def put_review_settings(payload: ReviewSettingsUpdate, request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    require(actor, "review.settings", "Nur Administratoren dürfen den Prüfmodus ändern.")
    if payload.review_mode not in REVIEW_MODE_ALLOWED:
        raise HTTPException(status_code=422, detail="Unbekannter Prüfmodus.")
    session = create_session()
    try:
        organization = session.get(Organization, actor.organization_id, with_for_update=True)
        if organization is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
        before = organization.review_mode
        if before != payload.review_mode:
            organization.review_mode = payload.review_mode
            session.add(ActivityLog(
                organization_id=actor.organization_id,
                account_id=actor.account_id,
                display_name_snapshot=actor.display_name,
                role_snapshot="developer" if getattr(actor, "is_developer", False) else actor.role,
                event_name="organization.review_mode_changed",
                object_type="organization",
                object_id=organization.id,
                context_data={"before": before, "after": payload.review_mode},
            ))
            session.commit()
        return _payload(organization, actor)
    finally:
        session.close()
