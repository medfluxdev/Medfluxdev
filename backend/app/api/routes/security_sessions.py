"""Account-session security controls for revocable Ahmad account sessions."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import update

from app.auth.service import account_from_selector
from app.core.config import settings
from app.database.models import LoginSession
from app.database.session import create_session

router = APIRouter(prefix="/api/auth", tags=["auth-security"])


@router.post("/logout-all")
def logout_all_account_sessions(request: Request, response: Response) -> dict[str, int | bool]:
    """Revoke all DB-backed sessions for the currently authenticated account.

    Legacy signed-token users cannot be globally revoked without rotating the
    installation signing secret, so this endpoint fails clearly for that mode.
    """
    selector = request.cookies.get(settings.auth_cookie_name, "")
    session = create_session()
    try:
        account = account_from_selector(session, selector)
        if account is None:
            raise HTTPException(
                status_code=409,
                detail="Alle Sitzungen können nur für ein widerrufbares Konto beendet werden.",
            )
        result = session.execute(
            update(LoginSession)
            .where(
                LoginSession.account_id == account.id,
                LoginSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(timezone.utc))
        )
        session.commit()
        count = int(result.rowcount or 0)
    finally:
        session.close()
    response.delete_cookie(settings.auth_cookie_name, path="/")
    return {"ok": True, "revoked_sessions": count}
