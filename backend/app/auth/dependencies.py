from __future__ import annotations

from fastapi import HTTPException, Request

from app.auth.service import Actor, account_from_selector, actor_for_account
from app.core.config import settings
from app.database.session import create_session


def current_actor(request: Request, organization_slug: str) -> Actor:
    selector = request.cookies.get(settings.auth_cookie_name, "")
    session = create_session()
    try:
        account = account_from_selector(session, selector)
        if account is None:
            raise HTTPException(status_code=401, detail="Bitte anmelden.")
        actor = actor_for_account(session, account, organization_slug)
        if actor is None:
            raise HTTPException(status_code=403, detail="Kein Zugriff auf diese Organisation.")
        return actor
    finally:
        session.close()


def require_authenticated_account(request: Request):
    selector = request.cookies.get(settings.auth_cookie_name, "")
    session = create_session()
    try:
        account = account_from_selector(session, selector)
        if account is None:
            raise HTTPException(status_code=401, detail="Bitte anmelden.")
        return account
    finally:
        session.close()
