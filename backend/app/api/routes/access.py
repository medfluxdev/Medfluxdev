"""Rechte-Matrix (H8.1) fuer Oberflaeche und Administration."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.auth.dependencies import current_actor
from app.auth.permissions import granted, matrix

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


@router.get("")
def get_permissions(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    return {**matrix(), "role": "developer" if actor.is_developer else actor.role, "granted": granted(actor)}
