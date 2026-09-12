from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.auth.service import authenticate, create_login_session, memberships_for_account, revoke_login_session
from app.core.config import settings
from app.database.session import create_session

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    ok: bool = True


def _account_payload(account, memberships):
    return {
        "id": str(account.id),
        "email": account.login_name,
        "display_name": account.display_name,
        "is_active": account.is_active,
        "last_login_at": account.last_login_at.isoformat() if account.last_login_at else None,
        "profile_photo_data_url": account.profile_photo_data_url,
        "phone": account.phone,
        "job_title": account.job_title,
        "department": account.department,
        "bio": account.bio,
        "memberships": [
            {
                "organization_id": str(org.id),
                "organization_slug": org.slug,
                "organization_name": org.name,
                "role": membership.role,
                "hospital_id": str(membership.hospital_id) if membership.hospital_id else None,
                "department_id": str(membership.department_id) if membership.department_id else None,
                "is_default": membership.is_default,
            }
            for membership, org in memberships
        ],
    }


@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response) -> LoginResponse:
    session = create_session()
    try:
        account = authenticate(session, payload.email, payload.password)
        if account is None:
            raise HTTPException(status_code=401, detail="E-Mail oder Passwort ist falsch.")
        selector, _ = create_login_session(session, account.id)
        session.commit()
        response.set_cookie(
            key=settings.auth_cookie_name,
            value=selector,
            httponly=True,
            secure=settings.auth_cookie_secure,
            samesite="lax",
            max_age=settings.auth_session_days * 24 * 60 * 60,
            path="/",
        )
        return LoginResponse()
    finally:
        session.close()


@router.post("/auth/logout", response_model=LoginResponse)
def logout(request: Request, response: Response) -> LoginResponse:
    selector = request.cookies.get(settings.auth_cookie_name, "")
    if selector:
        session = create_session()
        try:
            revoke_login_session(session, selector)
            session.commit()
        finally:
            session.close()
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return LoginResponse()


@router.get("/me")
def me(request: Request):
    from app.auth.service import account_from_selector

    selector = request.cookies.get(settings.auth_cookie_name, "")
    session = create_session()
    try:
        account = account_from_selector(session, selector)
        if account is None:
            raise HTTPException(status_code=401, detail="Bitte anmelden.")
        return _account_payload(account, memberships_for_account(session, account.id))
    finally:
        session.close()
