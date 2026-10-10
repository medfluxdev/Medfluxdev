"""Zentrale Rechte-Matrix (H8.1): Rolle x Aktion.

Entwickler-Konten haben alle Rechte. Die Middleware sperrt Schreibzugriffe von
Betrachtern/Pruefern zusaetzlich (Defense in depth); diese Matrix ist die
fachliche Quelle fuer Routen und Oberflaeche.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

ROLES = ("admin", "contract_manager", "reviewer", "viewer")
ROLE_LABELS = {
    "admin": "Administration",
    "contract_manager": "Vertragsmanagement",
    "reviewer": "Prüfung",
    "viewer": "Lesen",
}

_ALL = frozenset(ROLES)
_EDITORS = frozenset({"admin", "contract_manager"})
_REVIEWERS = frozenset({"admin", "contract_manager", "reviewer"})
_ADMIN = frozenset({"admin"})

# (Schluessel, Beschriftung, Bereich, Rollen)
PERMISSIONS: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    ("contract.read", "Verträge ansehen", "Verträge", _ALL),
    ("contract.create", "Verträge anlegen", "Verträge", _EDITORS),
    ("contract.edit", "Stammdaten bearbeiten", "Verträge", _EDITORS),
    ("contract.status", "Status ändern", "Verträge", _EDITORS),
    ("contract.mark_deleted", "Als gelöscht markieren", "Verträge", _ADMIN),
    ("contract.review", "KI-Werte prüfen", "Verträge", _REVIEWERS),
    ("contract.confidential_manage", "Vertraulichkeit und Freigaben verwalten", "Verträge", _ADMIN),
    ("document.attach", "Dokumente hinzufügen", "Dokumente", _EDITORS),
    ("finance.edit", "Finanzdaten pflegen", "Finanzen", _EDITORS),
    ("deadline.edit", "Termine pflegen", "Termine", _EDITORS),
    ("remark.add", "Bemerkungen schreiben", "Verträge", _EDITORS),
    ("partner.edit", "Vertragspartner pflegen", "Stammdaten", _EDITORS),
    ("catalog.admin", "Kataloge und Nummernkreis", "Administration", _ADMIN),
    ("organization.admin", "Organisationsstruktur", "Administration", _ADMIN),
    ("review.settings", "Prüfmodus festlegen", "Administration", _ADMIN),
    ("user.admin", "Benutzer und Rollen", "Administration", _ADMIN),
    ("job.admin", "Tageslauf überwachen", "Administration", _ADMIN),
    ("export", "Exportieren", "Berichte", _EDITORS),
    ("audit.view", "Historie ansehen", "Berichte", _EDITORS),
    ("views.global", "Ansichten für alle speichern", "Berichte", _ADMIN),
)

PERMISSION_KEYS = frozenset(key for key, _, _, _ in PERMISSIONS)
_ROLES_BY_PERMISSION = {key: roles for key, _, _, roles in PERMISSIONS}


def _role(actor: Any) -> str:
    return str(getattr(actor, "role", "") or "")


def is_admin(actor: Any) -> bool:
    return bool(getattr(actor, "is_developer", False)) or _role(actor) == "admin"


def can(actor: Any, permission: str) -> bool:
    if permission not in _ROLES_BY_PERMISSION:
        raise KeyError(f"unknown permission {permission!r}")
    if actor is None:
        return False
    if getattr(actor, "is_developer", False):
        return True
    return _role(actor) in _ROLES_BY_PERMISSION[permission]


def require(actor: Any, permission: str, detail_de: str | None = None) -> None:
    if not can(actor, permission):
        raise HTTPException(status_code=403, detail=detail_de or "Für diese Aktion fehlt die Berechtigung.")


def granted(actor: Any) -> list[str]:
    return sorted(key for key in PERMISSION_KEYS if can(actor, key))


def matrix() -> dict:
    return {
        "roles": [{"key": role, "label": ROLE_LABELS[role]} for role in ROLES],
        "permissions": [
            {"key": key, "label": label, "area": area, "roles": [role for role in ROLES if role in roles]}
            for key, label, area, roles in PERMISSIONS
        ],
    }
