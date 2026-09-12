"""Override-/Audit-Dienst für manuelle Bestätigungen & Material-Fakt-Overrides.

Append-only: `record_override` schreibt IMMER eine neue Zeile in
`contract_override` (niemals UPDATE). Der „aktuelle wirksame" Wert je `key`
wird aus der jüngsten `set`-Zeile abgeleitet; eine `void`-Zeile legt eine
Tombstone (kein wirksamer Wert).

STEP 16 (Authentication) ist NICHT implementiert: `actor_id`/`actor_type`
bleiben None und `is_development=True` wird gesetzt, um die Provenienz ehrlich
zu kennzeichnen – es wird NIE eine Mitarbeiter-Identität erfunden.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Contract, ContractOverride
from app.contracts.overrides.keys import ALLOWED_KEYS, OVERRIDE_VALUE_KEYS

OVERRIDE_ACTIONS = frozenset({"set", "void", "confirm"})


class OverrideError(Exception):
    detail_de = "Override konnte nicht gespeichert werden."


def _assert_allowed(key: str, action: str) -> None:
    if key not in ALLOWED_KEYS:
        raise OverrideError(f"Unbekannter Override-Key: {key}")
    if action not in OVERRIDE_ACTIONS:
        raise OverrideError(f"Unbekannte Aktion: {action}")
    if action != "confirm" and key not in OVERRIDE_VALUE_KEYS:
        raise OverrideError(f"Key {key} unterstuetzt kein set/void")


def record_override(
    session: Session,
    *,
    organization_id: uuid.UUID,
    contract_id: uuid.UUID,
    key: str,
    action: str,
    value: Optional[dict] = None,
    fact_ref: Optional[str] = None,
    note: Optional[str] = None,
) -> ContractOverride:
    """Schreibt eine append-only Override-/Audit-Zeile (org-gebunden)."""
    _assert_allowed(key, action)
    contract = session.get(Contract, contract_id)
    if contract is None or contract.organization_id != organization_id:
        raise OverrideError("Vertrag nicht gefunden.")

    row = ContractOverride(
        organization_id=organization_id,
        contract_id=contract_id,
        key=key,
        action=action,
        value=value if action == "set" else None,
        fact_ref=fact_ref,
        note=note,
        actor_id=None,
        actor_type=None,
        is_development=True,
    )
    session.add(row)
    session.flush()
    return row


def effective_overrides(
    session: Session, *, organization_id, contract_id
) -> dict[str, dict]:
    """Liefert den aktuell wirksamen Override je `key`.

    Rückgabe: {key: {"value": ..., "created_at": ..., "note": ...}}. Ein `void`
    als jüngste Zeile ergibt KEINEN wirksamen Wert (Tombstone). Kein Fabrication:
    was nicht gesetzt wurde, fehlt.
    """
    rows = session.scalars(
        select(ContractOverride)
        .where(
            (ContractOverride.organization_id == organization_id)
            & (ContractOverride.contract_id == contract_id)
        )
        .order_by(ContractOverride.created_at, ContractOverride.id)
    ).all()

    effective: dict[str, dict] = {}
    for row in rows:
        if row.key not in OVERRIDE_VALUE_KEYS:
            continue
        if row.action == "set":
            effective[row.key] = {
                "value": row.value,
                "created_at": row.created_at,
                "note": row.note,
                "is_development": bool(row.is_development),
            }
        elif row.action == "void":
            effective.pop(row.key, None)
    return effective


def audit_history(
    session: Session, *, organization_id, contract_id
) -> list[dict]:
    """Append-only Audit-Historie (neu zuerst), angepasst für das DTO (keine Secrets).

    `old_value` = der VOR dieser Zeile wirksame Override desselben Feldes
    (chronologisch bestimmt). Macht set/void-Verbleib ehrlich nachvollziehbar.
    """
    rows = session.scalars(
        select(ContractOverride)
        .where(
            (ContractOverride.organization_id == organization_id)
            & (ContractOverride.contract_id == contract_id)
        )
        .order_by(ContractOverride.created_at.desc(), ContractOverride.id.desc())
    ).all()

    ascending = list(reversed(rows))
    effective: dict[str, dict] = {}
    old_by_id: dict[uuid.UUID, Optional[dict]] = {}
    for r in ascending:
        if r.key not in OVERRIDE_VALUE_KEYS:
            old_by_id[r.id] = None
            continue
        old_by_id[r.id] = effective.get(r.key)
        if r.action == "set":
            effective[r.key] = {
                "value": r.value,
                "created_at": r.created_at,
                "note": r.note,
                "is_development": bool(r.is_development),
            }
        elif r.action == "void":
            effective.pop(r.key, None)

    return [
        {
            "id": str(r.id),
            "key": r.key,
            "action": r.action,
            "value": r.value,
            "fact_ref": r.fact_ref,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "is_development": bool(r.is_development),
            "actor_type": r.actor_type,
            "old_value": old_by_id.get(r.id),
        }
        for r in rows
    ]


def confirmed_fact_refs(session: Session, *, organization_id, contract_id) -> set[str]:
    """Feld-Referenzen, die manuell (confirm) bestätigt wurden."""
    rows = session.scalars(
        select(ContractOverride).where(
            (ContractOverride.organization_id == organization_id)
            & (ContractOverride.contract_id == contract_id)
            & (ContractOverride.action == "confirm")
        )
    ).all()
    return {r.fact_ref for r in rows if r.fact_ref}
