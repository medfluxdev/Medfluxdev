"""H7.2 Gespeicherte Ansichten ("Arbeitsbereiche"): persoenlich oder global."""

from __future__ import annotations

import uuid
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database.models.register import SAVED_VIEW_KINDS, SavedView
from app.reports.grid import DEFAULT_COLUMNS, GridError, GridSpec

DEFAULT_VIEWS: tuple[tuple[str, str, dict], ...] = (
    ("mine", "Meine Verträge", {"filters": [{"column": "responsible", "op": "me"}]}),
    ("my_followup", "Meine Wiedervorlage", {
        "columns": [*DEFAULT_COLUMNS, "reminder_date"],
        "filters": [
            {"column": "reminder_recipient", "op": "me"},
            {"column": "reminder_date", "op": "due_within_days", "value": 30},
        ],
        "sort": {"column": "reminder_date", "dir": "asc"},
    }),
    ("notice_90", "Kündigungsfrist < 90 Tage", {
        "filters": [{"column": "cancel_by", "op": "within_days", "value": 90}],
        "sort": {"column": "cancel_by", "dir": "asc"},
    }),
    ("in_work", "In Arbeit", {"filters": [{"column": "business_status", "op": "in", "value": ["in_arbeit"]}]}),
    ("deletion_due", "Zum Löschen vorgesehen", {
        "columns": [*DEFAULT_COLUMNS, "deletion_from", "storage_location"],
        "filters": [{"column": "deletion_from", "op": "overdue"}],
        "sort": {"column": "deletion_from", "dir": "asc"},
    }),
    ("deleted", "Gelöschte Verträge", {"filters": [{"column": "business_status", "op": "in", "value": ["geloescht"]}]}),
)


class ViewError(Exception):
    def __init__(self, status_code: int, detail_de: str):
        super().__init__(detail_de)
        self.status_code = status_code
        self.detail_de = detail_de


def ensure_default_views(session: Session, organization_id: uuid.UUID) -> None:
    for index, (key, name, config) in enumerate(DEFAULT_VIEWS):
        session.execute(
            pg_insert(SavedView)
            .values(
                organization_id=organization_id, owner_account_id=None, view_kind="register", name=name,
                config=GridSpec.parse(config).as_dict(), system_key=key, sort_order=index * 10,
                created_by_name="System",
            )
            .on_conflict_do_nothing(
                index_elements=["organization_id", "system_key"], index_where=SavedView.system_key.is_not(None)
            )
        )
    session.flush()


def view_payload(row: SavedView, account_id: Optional[uuid.UUID]) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "config": row.config,
        "is_global": row.owner_account_id is None,
        "is_system": row.system_key is not None,
        "is_own": row.owner_account_id is not None and row.owner_account_id == account_id,
        "created_by_name": row.created_by_name,
        "view_kind": row.view_kind,
    }


def list_views(
    session: Session, organization_id: uuid.UUID, account_id: Optional[uuid.UUID], kind: str = "register"
) -> list[dict]:
    if kind == "register":
        ensure_default_views(session, organization_id)
    rows = session.scalars(
        select(SavedView)
        .where(
            SavedView.organization_id == organization_id,
            SavedView.view_kind == kind,
            or_(SavedView.owner_account_id.is_(None), SavedView.owner_account_id == account_id),
        )
        .order_by(SavedView.owner_account_id.is_not(None), SavedView.sort_order, SavedView.name)
    ).all()
    return [view_payload(row, account_id) for row in rows]


def _clean_list_query(config: Any) -> dict:
    """Klassische Vertragsliste: gespeichert wird nur die Filter-Abfrage (ohne Seite)."""
    raw = config.get("query") if isinstance(config, dict) else None
    if not isinstance(raw, str) or len(raw) > 2000:
        raise ViewError(422, "Ungültige Ansicht.")
    pairs = [(key, value) for key, value in parse_qsl(raw.lstrip("?"), keep_blank_values=False) if key != "page"]
    return {"query": urlencode(pairs)}


def _clean(name: Any, config: Any, kind: str = "register") -> tuple[str, dict]:
    text = str(name or "").strip()
    if not text or len(text) > 120:
        raise ViewError(422, "Name: 1 bis 120 Zeichen.")
    if kind not in SAVED_VIEW_KINDS:
        raise ViewError(422, "Unbekannte Ansichtsart.")
    if kind == "contracts":
        return text, _clean_list_query(config)
    try:
        spec = GridSpec.parse(config)
    except GridError as exc:
        raise ViewError(422, str(exc))
    return text, spec.as_dict()


def create_view(
    session: Session, *, organization_id: uuid.UUID, account_id: Optional[uuid.UUID], display_name: str,
    name: Any, config: Any, is_global: bool, kind: str = "register",
) -> SavedView:
    text, clean = _clean(name, config, kind)
    if not is_global and account_id is None:
        raise ViewError(422, "Persönliche Ansichten benötigen ein Benutzerkonto.")
    row = SavedView(
        organization_id=organization_id, owner_account_id=None if is_global else account_id, view_kind=kind,
        name=text, config=clean, sort_order=1000, created_by_name=display_name,
    )
    session.add(row)
    session.flush()
    return row


def _editable(session: Session, organization_id: uuid.UUID, account_id: Optional[uuid.UUID], may_edit_global: bool,
              view_id: uuid.UUID) -> SavedView:
    row = session.get(SavedView, view_id)
    if row is None or row.organization_id != organization_id:
        raise ViewError(404, "Ansicht nicht gefunden.")
    if row.owner_account_id is None:
        if not may_edit_global:
            raise ViewError(403, "Globale Ansichten dürfen nur Administratoren ändern.")
    elif row.owner_account_id != account_id:
        raise ViewError(404, "Ansicht nicht gefunden.")
    return row


def update_view(
    session: Session, *, organization_id: uuid.UUID, account_id: Optional[uuid.UUID], may_edit_global: bool,
    view_id: uuid.UUID, name: Any, config: Any,
) -> SavedView:
    row = _editable(session, organization_id, account_id, may_edit_global, view_id)
    row.name, row.config = _clean(name, config, row.view_kind)
    session.flush()
    return row


def delete_view(
    session: Session, *, organization_id: uuid.UUID, account_id: Optional[uuid.UUID], may_edit_global: bool,
    view_id: uuid.UUID,
) -> None:
    row = _editable(session, organization_id, account_id, may_edit_global, view_id)
    if row.system_key is not None:
        raise ViewError(403, "Standardansichten können nicht gelöscht werden.")
    session.delete(row)
    session.flush()
