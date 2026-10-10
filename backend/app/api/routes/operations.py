"""Operative Export-Endpunkte (STEP 17).

Der CSV-Export basiert ausschliesslich auf organisationsgebundenem Current-State.
Er enthaelt keine OCR-Rohdaten, Storage-Pfade oder Credentials.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.core.clock import today_local
from app.auth.context import enforce_org, optional_identity
from app.auth.permissions import require
from app.core.config import settings
from app.core.scope_context import current_scope_context
from app.database.models import Contract
from app.database.models.activity_log import ActivityLog
from app.database.scope_queries import scoped_contract_ids
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/operations", tags=["operations"])

_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _fmt(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _csv_safe(value) -> str:
    text = _fmt(value)
    if not text:
        return text
    candidate = text.lstrip(" \t\r\n")
    if candidate.startswith(_CSV_FORMULA_PREFIXES):
        return "'" + text
    return text


@router.get("/contracts.csv")
def export_contracts_csv(
    request: Request,
    organization_slug: str,
    include_archived: bool = Query(default=True),
) -> Response:
    """Exportiert das sichtbare Vertragsportfolio als UTF-8 CSV."""
    identity = None
    if settings.auth_enabled:
        identity = optional_identity(request)
        if identity is None:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich.")
        enforce_org(identity, organization_slug)
        require(identity, "export", "Keine Berechtigung für Vertrags-Exporte.")

    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")

        stmt = select(Contract).where(
            (Contract.organization_id == org.id)
            & (Contract.lifecycle_state == "active")
        )
        scope = current_scope_context()
        visible_ids = scoped_contract_ids(
            session,
            org.id,
            scope.hospital_id,
            scope.department_id,
        )
        if visible_ids is not None:
            stmt = stmt.where(Contract.id.in_(visible_ids))
        if not include_archived:
            stmt = stmt.where(Contract.is_archived.is_(False))
        stmt = stmt.order_by(
            Contract.supplier.asc().nullslast(),
            Contract.contract_number.asc().nullslast(),
            Contract.id,
        )
        rows = session.scalars(stmt).all()

        out = io.StringIO(newline="")
        writer = csv.writer(out, delimiter=";", lineterminator="\n")
        writer.writerow([
            "contract_id",
            "supplier",
            "contract_number",
            "start_date",
            "end_date",
            "status",
            "risk_level",
            "is_archived",
            "archived_at",
            "updated_at",
        ])
        for row in rows:
            writer.writerow([
                _csv_safe(row.id),
                _csv_safe(row.supplier),
                _csv_safe(row.contract_number),
                _csv_safe(row.start_date),
                _csv_safe(row.end_date),
                _csv_safe(row.status),
                _csv_safe(row.risk_level),
                "true" if row.is_archived else "false",
                _csv_safe(row.archived_at),
                _csv_safe(row.updated_at),
            ])

        if identity is not None:
            session.add(
                ActivityLog(
                    organization_id=org.id,
                    hospital_id=scope.hospital_id,
                    department_id=scope.department_id,
                    account_id=getattr(identity, "account_id", None),
                    display_name_snapshot=identity.display_name,
                    role_snapshot="developer" if getattr(identity, "is_developer", False) else identity.role,
                    event_name="contracts.exported",
                    object_type="organization",
                    object_id=org.id,
                    context_data={"row_count": len(rows), "include_archived": include_archived},
                )
            )
            session.commit()

        filename = f"medflux-vertraege-{organization_slug}-{today_local().isoformat()}.csv"
        return Response(
            content="\ufeff" + out.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        session.close()
