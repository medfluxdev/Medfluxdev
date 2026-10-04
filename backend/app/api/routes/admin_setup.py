"""U5: Einrichtungs-Checkliste fuer Administratoren (was ist eingerichtet, was fehlt)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app.ai.service import AIService
from app.auth.dependencies import current_actor
from app.auth.permissions import require
from app.core.config import settings
from app.database.models import AccountMembership
from app.database.models.deadlines import JobRun
from app.database.models.organization_structure import CostCenter, Department, Hospital
from app.database.models.register import CatalogContractType, NumberRange
from app.database.session import create_session
from app.deadlines.mail import smtp_configured

router = APIRouter(prefix="/api/admin", tags=["admin"])
_ai = AIService(settings)


def _item(key: str, label: str, ok: bool, detail: str, href: str, optional: bool = False) -> dict:
    return {"key": key, "label": label, "status": "ok" if ok else ("optional" if optional else "todo"), "detail": detail, "href": href}


def _latest_backup() -> datetime | None:
    try:
        folder = Path(settings.backups_dir)
        files = [entry for entry in folder.iterdir() if entry.is_file()] if folder.exists() else []
    except OSError:
        return None
    if not files:
        return None
    return datetime.fromtimestamp(max(entry.stat().st_mtime for entry in files), tz=timezone.utc)


@router.get("/setup-status")
def setup_status(request: Request, organization_slug: str):
    actor = current_actor(request, organization_slug)
    require(actor, "organization.admin", "Nur Administratoren sehen die Einrichtung.")
    org = actor.organization_id
    session = create_session()
    try:
        hospitals = session.scalar(select(func.count()).where(Hospital.organization_id == org, Hospital.is_active.is_(True))) or 0
        departments = session.scalar(select(func.count()).where(Department.organization_id == org, Department.is_active.is_(True))) or 0
        cost_centers = session.scalar(select(func.count()).where(CostCenter.organization_id == org, CostCenter.is_active.is_(True))) or 0
        members = session.scalar(select(func.count()).where(AccountMembership.organization_id == org, AccountMembership.is_active.is_(True))) or 0
        types = session.scalar(select(func.count()).where(CatalogContractType.organization_id == org, CatalogContractType.is_active.is_(True))) or 0
        number_range = session.scalars(select(NumberRange).where(NumberRange.organization_id == org)).first()
        last_run = session.scalars(
            select(JobRun).where((JobRun.organization_id == org) | JobRun.organization_id.is_(None)).order_by(JobRun.started_at.desc())
        ).first()
    finally:
        session.close()

    backup = _latest_backup()
    backup_age = (datetime.now(timezone.utc) - backup).days if backup else None
    run_age = (datetime.now(timezone.utc) - last_run.started_at).days if last_run else None
    items = [
        _item("organization", "Organisationsstruktur", hospitals > 0 and departments > 0,
              f"{hospitals} Krankenhäuser, {departments} Bereiche, {cost_centers} Kostenstellen", "/settings/organization"),
        _item("users", "Benutzer und Rollen", members > 1, f"{members} aktive Zugänge", "/settings/users"),
        _item("catalogs", "Kataloge (Vertragstypen, Auswahllisten)", types > 0, f"{types} Vertragstypen", "/settings/catalogs"),
        _item("numbers", "Nummernkreis für Vertragsnummern", number_range is not None,
              f"nächste Nummer {number_range.prefix}{str(number_range.next_value).zfill(number_range.padding)}" if number_range else "noch nicht eingerichtet",
              "/settings/catalogs"),
        _item("ai", "Lokales KI-Modell", _ai.configured, f"Modell: {_ai.active_model_id()}" if _ai.configured else "kein Modell ausgewählt", "/settings"),
        _item("mail", "E-Mail-Versand (SMTP)", smtp_configured(),
              "eingerichtet" if smtp_configured() else "nicht eingerichtet – Erinnerungen nur im Postfach", "/settings", optional=True),
        _item("daily_job", "Täglicher Lauf (Fristen, Erinnerungen)", run_age is not None and run_age <= 2,
              f"letzter Lauf vor {run_age} Tag(en): {last_run.status}" if last_run else "noch nie gelaufen", "/settings"),
        _item("backup", "Datensicherung", backup_age is not None and backup_age <= 7,
              f"letzte Sicherung vor {backup_age} Tag(en)" if backup_age is not None else "keine Sicherung gefunden", "/settings"),
        _item("search", "Inhaltssuche nach Bedeutung (optional)", bool(settings.search_embedding_model.strip()),
              f"Modell: {settings.search_embedding_model}" if settings.search_embedding_model.strip() else "aus – Volltextsuche ist aktiv", "/suche", optional=True),
    ]
    done = sum(1 for item in items if item["status"] == "ok")
    required = sum(1 for item in items if item["status"] != "optional")
    return {"items": items, "done": done, "total": len(items), "required_open": sum(1 for item in items if item["status"] == "todo"), "required": required}
