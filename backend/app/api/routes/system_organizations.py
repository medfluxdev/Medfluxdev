from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.database.models import Account, Organization
from app.database.session import create_session

router = APIRouter(prefix="/api/system/organizations", tags=["system-organizations"])


class OrganizationCreate(BaseModel):
    name: str
    slug: str


def _require_developer(request: Request, session):
    if getattr(request.state, "is_developer", False):
        account_id = getattr(request.state, "account_id", None)
        return session.get(Account, account_id) if account_id else None

    account_id = getattr(request.state, "account_id", None)
    account = session.get(Account, account_id) if account_id else None
    if account is None or not account.is_developer:
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
