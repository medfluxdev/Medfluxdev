from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.service import account_from_selector
from app.core.config import settings
from app.database.models import Organization
from app.database.session import create_session

router = APIRouter(prefix="/api/system/organizations", tags=["system-organizations"])


class OrganizationCreate(BaseModel):
    name: str
    slug: str


def _require_developer(request: Request, session):
    """Resolve the authenticated account exactly like /api/me.

    System routes must not depend on middleware request-state ordering.  Using the
    same session cookie lookup as /api/me guarantees that an account shown as
    Developer in the UI is treated identically by the system API.
    """
    selector = request.cookies.get(settings.auth_cookie_name, "")
    account = account_from_selector(session, selector)
    if account is None:
        raise HTTPException(status_code=401, detail="Bitte anmelden.")
    if not account.is_developer:
        raise HTTPException(status_code=403, detail="Nur Developer erlaubt.")
    return account


@router.get("")
def list_organizations(request: Request):
    session = create_session()
    try:
        _require_developer(request, session)
        rows = session.scalars(select(Organization).order_by(Organization.name.asc())).all()
        return {"items": [{"id": str(row.id), "name": row.name, "slug": row.slug} for row in rows]}
    finally:
        session.close()


@router.post("")
def create_organization(payload: OrganizationCreate, request: Request):
    session = create_session()
    try:
        _require_developer(request, session)
        name = payload.name.strip()
        slug = payload.slug.strip().lower()
        if not name or not slug:
            raise HTTPException(status_code=422, detail="Name und Slug sind erforderlich.")
        if session.scalar(select(Organization.id).where(Organization.slug == slug)) is not None:
            raise HTTPException(status_code=409, detail="Organisation existiert bereits.")
        row = Organization(name=name, slug=slug)
        session.add(row)
        session.commit()
        session.refresh(row)
        return {"id": str(row.id), "name": row.name, "slug": row.slug}
    finally:
        session.close()
