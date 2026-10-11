"""Geschaeftsstatus-Workflow eines Registervertrags (H1.4, Entscheidung D2).

In Arbeit -> Gueltig -> Gekuendigt / Beendet -> Geloescht, plus
Reaktivierung (Beendet/Gekuendigt -> Gueltig). "Geloescht" ist nur eine
Markierung; die echte Loeschung bleibt der bestehende, gesondert
freizugebende Loeschablauf.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from app.core.clock import today_local
from app.register.fields import REQUIRED_FOR_VALID, FIELDS

STATUS_LABELS = {
    "in_arbeit": "In Arbeit",
    "gueltig": "Gültig",
    "gekuendigt": "Gekündigt",
    "beendet": "Beendet",
    # Code bleibt `geloescht`; angezeigt als „Storniert“, damit „gelöscht“ nur die Vertragslöschung meint.
    "geloescht": "Storniert",
}

TRANSITIONS: dict[str, tuple[str, ...]] = {
    "in_arbeit": ("gueltig", "geloescht"),
    "gueltig": ("gekuendigt", "beendet"),
    "gekuendigt": ("beendet", "gueltig"),
    "beendet": ("geloescht", "gueltig"),
    "geloescht": (),
}

# Laufend = gueltig oder gekuendigt und am Stichtag innerhalb der Laufzeit.
# "In Arbeit" ist ein Entwurf und zaehlt nicht als laufend; ein gekuendigter
# Vertrag laeuft bis zu seinem Ende weiter.
RUNNING_STATUSES = ("gueltig", "gekuendigt")


def is_running(business_status: Optional[str], start: Optional[date], end: Optional[date], as_of: date) -> bool:
    if business_status not in RUNNING_STATUSES:
        return False
    if start is not None and start > as_of:
        return False
    if end is not None and end < as_of:
        return False
    return True


WRITE_ROLES = frozenset({"admin", "contract_manager"})
DELETE_ROLES = frozenset({"admin"})


class TransitionError(ValueError):
    def __init__(self, status_code: int, detail_de: str, missing: Optional[list[str]] = None):
        super().__init__(detail_de)
        self.status_code = status_code
        self.detail_de = detail_de
        self.missing = missing or []


@dataclass(frozen=True)
class TransitionPlan:
    target: str
    updates: dict[str, Any]


def allowed_targets(current: str, role: str, is_developer: bool = False) -> list[str]:
    effective = "admin" if is_developer else role
    if effective not in WRITE_ROLES:
        return []
    return [
        target for target in TRANSITIONS.get(current, ())
        if target != "geloescht" or effective in DELETE_ROLES
    ]


def plan_transition(
    *,
    current: str,
    target: str,
    role: str,
    is_developer: bool,
    values: dict[str, Any],
    effective_date: Optional[date],
    terminated_on: Optional[date],
    review_pending: bool,
    acknowledge_unreviewed: bool,
) -> TransitionPlan:
    if target not in STATUS_LABELS:
        raise TransitionError(422, "Unbekannter Zielstatus.")
    if target not in TRANSITIONS.get(current, ()):
        raise TransitionError(
            409, f"Statuswechsel {STATUS_LABELS.get(current, current)} → {STATUS_LABELS[target]} ist nicht möglich."
        )
    if target not in allowed_targets(current, role, is_developer):
        raise TransitionError(403, "Keine Berechtigung für diesen Statuswechsel.")

    updates: dict[str, Any] = {}
    if target == "gueltig":
        if current == "in_arbeit":
            missing = [key for key in REQUIRED_FOR_VALID if values.get(key) in (None, "")]
            if values.get("partner_id") is None and not values.get("supplier"):
                missing.append("partner_id")
            if missing:
                labels = ", ".join(FIELDS[key].label_de for key in missing)
                raise TransitionError(422, f"Für „Gültig“ fehlen Angaben: {labels}.", missing)
            if review_pending and not acknowledge_unreviewed:
                raise TransitionError(
                    409,
                    "Die KI-Werte sind noch nicht geprüft. Bitte Prüfung abschließen oder bewusst bestätigen.",
                )
        else:
            updates.update({"terminated_on": None, "terminated_effective": None, "ended_on": None})
    elif target == "gekuendigt":
        notice_date = terminated_on or values.get("terminated_on")
        end_date = effective_date or values.get("terminated_effective")
        missing = [
            key for key, value in (("terminated_on", notice_date), ("terminated_effective", end_date))
            if value is None
        ]
        if missing:
            raise TransitionError(422, "Für „Gekündigt“ bitte „Gekündigt am“ und „Gekündigt zum“ angeben.", missing)
        if end_date < notice_date:
            raise TransitionError(422, "„Gekündigt zum“ liegt vor „Gekündigt am“.")
        updates.update({"terminated_on": notice_date, "terminated_effective": end_date})
    elif target == "beendet":
        updates["ended_on"] = effective_date or values.get("terminated_effective") or today_local()
    return TransitionPlan(target=target, updates=updates)
