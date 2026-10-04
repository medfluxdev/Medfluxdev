from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.auth.service import account_from_selector
from app.core.config import settings
from app.database.models import Account
from app.database.session import create_session

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileUpdateRequest(BaseModel):
    display_name: str | None = None
    phone: str | None = None
    job_title: str | None = None
    department: str | None = None
    bio: str | None = None
    profile_photo_data_url: str | None = None


class UiPreferences(BaseModel):
    """U8: Darstellung je Benutzer; unbekannte Schluessel werden abgelehnt."""

    model_config = ConfigDict(extra="forbid")

    theme: Literal["system", "light", "dark"] = "light"
    text_size: Literal["normal", "large", "xlarge"] = "normal"
    density: Literal["comfortable", "compact"] = "comfortable"
    sidebar_collapsed: bool = False
    developer_mode: bool = False


def serialize(account: Account) -> dict:
    return {
        "id": str(account.id),
        "email": account.login_name,
        "display_name": account.display_name,
        "phone": account.phone,
        "job_title": account.job_title,
        "department": account.department,
        "bio": account.bio,
        "profile_photo_data_url": account.profile_photo_data_url,
    }


def current_account(request: Request, session) -> Account:
    # Resolve the account from the same session cookie as /api/me. Depending only
    # on request.state made this route fragile across middleware boundaries and
    # caused a false 401 even while /api/me confirmed an active login.
    selector = request.cookies.get(settings.auth_cookie_name, "")
    account = account_from_selector(session, selector)
    if account is None:
        raise HTTPException(status_code=401, detail="Bitte anmelden.")
    return account


@router.get("")
def get_profile(request: Request):
    session = create_session()
    try:
        return serialize(current_account(request, session))
    finally:
        session.close()


@router.patch("")
def update_profile(request: Request, payload: ProfileUpdateRequest):
    session = create_session()
    try:
        account = current_account(request, session)
        if payload.display_name is not None:
            account.display_name = payload.display_name.strip()[:255] or account.display_name
        if payload.phone is not None:
            account.phone = payload.phone.strip()[:80] or None
        if payload.job_title is not None:
            account.job_title = payload.job_title.strip()[:160] or None
        if payload.department is not None:
            account.department = payload.department.strip()[:160] or None
        if payload.bio is not None:
            account.bio = payload.bio.strip()[:2000] or None
        if payload.profile_photo_data_url is not None:
            account.profile_photo_data_url = payload.profile_photo_data_url or None
        session.commit()
        session.refresh(account)
        return serialize(account)
    finally:
        session.close()


@router.get("/preferences")
def get_preferences(request: Request):
    session = create_session()
    try:
        account = current_account(request, session)
        stored = account.ui_preferences
        return {"preferences": UiPreferences.model_validate(stored).model_dump() if stored else None}
    finally:
        session.close()


@router.put("/preferences")
def put_preferences(request: Request, payload: UiPreferences):
    session = create_session()
    try:
        account = current_account(request, session)
        values = payload.model_dump()
        if not account.is_developer:
            values["developer_mode"] = False
        account.ui_preferences = values
        session.commit()
        return {"preferences": values}
    finally:
        session.close()
