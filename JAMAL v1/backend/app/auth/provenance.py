"""Bindet authentifizierte lokale Identitaet an bestehende Review-Provenienz.

Die Fachservices bleiben auch bei `AUTH_ENABLED=false` abwaertskompatibel.
Bei aktivierter lokaler Anmeldung ueberschreiben diese ORM-Hooks jedoch jede
clientseitige Namensangabe mit der serverseitig authentifizierten Identitaet.
"""

from __future__ import annotations

from sqlalchemy import event

from app.auth.runtime import current_identity
from app.database.models.fact_review import ContractReview, FactReview
from app.database.models.override import ContractOverride

_REGISTERED = False


def _apply_review_identity(target) -> None:
    identity = current_identity()
    if identity is None:
        return
    target.reviewer_display_name = identity.display_name
    target.reviewer_identity_type = (
        "authenticated_account"
        if hasattr(identity, "account_id")
        else "authenticated_local"
    )
    target.authenticated_actor_id = identity.user_id
    if hasattr(target, "actor_role_snapshot"):
        target.actor_role_snapshot = identity.role


def _apply_override_identity(target: ContractOverride) -> None:
    identity = current_identity()
    if identity is None:
        return
    target.actor_id = identity.user_id
    target.actor_type = (
        "authenticated_account"
        if hasattr(identity, "account_id")
        else "authenticated_local"
    )
    target.actor_display_name_snapshot = identity.display_name
    target.actor_role_snapshot = identity.role
    target.is_development = False


def register_auth_provenance_hooks() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    event.listen(FactReview, "before_insert", lambda mapper, connection, target: _apply_review_identity(target))
    event.listen(ContractReview, "before_insert", lambda mapper, connection, target: _apply_review_identity(target))
    event.listen(ContractReview, "before_update", lambda mapper, connection, target: _apply_review_identity(target))
    event.listen(ContractOverride, "before_insert", lambda mapper, connection, target: _apply_override_identity(target))
    _REGISTERED = True
