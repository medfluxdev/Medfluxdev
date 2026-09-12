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

from app.auth.context import enforce_org, optional_identity
from app.core.config import settings
from app.database.models import Contract
from app.database.services import get_organization
from app.database.session import create_session

router = APIRouter(prefix="/api/operations", tags=["operations"])


def _fmt(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@router.get("/contracts.csv")
def export_contracts_csv(
    request: Request,
    organization_slug: str,
    include_archived: bool = Query(default=True),
) -> Response:
    """Exportiert das organisationsgebundene Vertragsportfolio als UTF-8 CSV.

    Bei aktivierter Authentifizierung ist die signierte Session die
    Autoritaetsquelle; ein abweichender Query-Slug wird abgewiesen.
    """
    if settings.auth_enabled:
        identity = optional_identity(request)
        if identity is None:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich.")
        enforce_org(identity, organization_slug)

    session = create_session()
    try:
        org = get_organization(session, organization_slug)
        if org is None:
            raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")

        stmt = (
            select(Contract)
            .where(
                (Contract.organization_id == org.id)
                & (Contract.lifecycle_state == "active")
            )
            .order_by(Contract.supplier.asc().nullslast(), Contract.contract_number.asc().nullslast(), Contract.id)
        )
        if not include_archived:
            stmt = stmt.where(Contract.is_archived.is_(False))
        rows = session.scalars(stmt).all()

        out = io.StringIO(newline="")
        writer = csv.writer(out, delimiter=";", lineterminator="\n")
        writer.writerow(
            [
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
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    str(row.id),
                    row.supplier or "",
                    row.contract_number or "",
                    _fmt(row.start_date),
                    _fmt(row.end_date),
                    row.status or "",
                    row.risk_level or "",
                    "true" if row.is_archived else "false",
                    _fmt(row.archived_at),
                    _fmt(row.updated_at),
                ]
            )

        filename = f"medflux-vertraege-{organization_slug}-{date.today().isoformat()}.csv"
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
