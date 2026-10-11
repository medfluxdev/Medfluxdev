"""Risiko eines Vertrags: berechnet, bestaetigt oder von einer Person festgelegt.

Berechnet wird es deterministisch aus dem hoechsten Schweregrad der aktiven Warnungen
(`database.services._project_risk_level`). Eine Person kann den berechneten Wert
bestaetigen (gilt, solange er sich nicht aendert) oder mit Begruendung einen anderen
Wert festlegen; der gilt dann ueberall, bis er zurueckgesetzt wird.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import Contract

RISK_LEVELS = ("low", "medium", "high")


class RiskError(ValueError):
    def __init__(self, detail_de: str) -> None:
        super().__init__(detail_de)
        self.detail_de = detail_de


def risk_payload(contract: Contract) -> dict:
    computed = contract.risk_computed or (None if contract.risk_override else contract.risk_level)
    confirmed = (
        contract.risk_confirmed_level is not None
        and contract.risk_override is None
        and contract.risk_confirmed_level == computed
    )
    return {
        "computed": computed,
        "effective": contract.risk_level,
        "override": {
            "level": contract.risk_override,
            "reason": contract.risk_override_reason,
            "by": contract.risk_override_by_name,
            "at": contract.risk_override_at.isoformat() if contract.risk_override_at else None,
        } if contract.risk_override else None,
        # Bestaetigung gilt nur fuer den Wert, der bestaetigt wurde.
        "confirmed": {
            "by": contract.risk_confirmed_by_name,
            "at": contract.risk_confirmed_at.isoformat() if contract.risk_confirmed_at else None,
        } if confirmed else None,
    }


def decide_risk(
    session: Session, *, contract: Contract, actor, action: str, level: Optional[str] = None, reason: Optional[str] = None,
) -> dict:
    from app.register.service import log_activity

    now = datetime.now(timezone.utc)
    before = contract.risk_level
    if action == "confirm":
        if contract.risk_override:
            raise RiskError("Das Risiko ist von Hand festgelegt. Erst auf den berechneten Wert zurücksetzen.")
        contract.risk_confirmed_level = contract.risk_computed or contract.risk_level
        contract.risk_confirmed_by_name = actor.display_name
        contract.risk_confirmed_at = now
    elif action == "override":
        if level not in RISK_LEVELS:
            raise RiskError("Bitte Niedrig, Mittel oder Hoch wählen.")
        text = (reason or "").strip()
        if len(text) < 3:
            raise RiskError("Bitte kurz begründen, warum das Risiko anders eingeschätzt wird.")
        if contract.risk_computed is None:
            contract.risk_computed = contract.risk_level
        contract.risk_override = level
        contract.risk_override_reason = text[:500]
        contract.risk_override_by_name = actor.display_name
        contract.risk_override_at = now
        contract.risk_level = level
    elif action == "reset":
        contract.risk_override = None
        contract.risk_override_reason = None
        contract.risk_override_by_name = None
        contract.risk_override_at = None
        contract.risk_level = contract.risk_computed
    else:
        raise RiskError("Unbekannte Aktion.")
    log_activity(session, actor, contract.id, "contract.risk_decided", {
        "action": action, "before": before, "after": contract.risk_level, "reason": (reason or "").strip()[:500] or None,
    })
    session.flush()
    return risk_payload(contract)
