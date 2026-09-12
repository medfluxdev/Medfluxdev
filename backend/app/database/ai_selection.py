"""Persistenz der KI-Provider-/Modell-Auswahl (Schritt 6B).

Deployment-global (kein Organisations-Scope): die aktive lokale KI-Auswahl ist
pro Installation einmalig. Genutzt wird die `application_setting`-Tabelle über
kurze, atomare Transaktionen (`session_scope`).
"""

from __future__ import annotations

from sqlalchemy import select

from app.database.models.application_setting import ApplicationSetting
from app.database.session import session_scope

KEY_PROVIDER = "ai_provider"
KEY_MODEL = "ai_model"
KEY_ENDPOINT = "ai_provider_endpoint"


def get_setting(key: str) -> str | None:
    """Liest einen String-Einstellungswert (None wenn nicht gesetzt)."""
    with session_scope() as session:
        row = session.get(ApplicationSetting, key)
        return row.value if row is not None else None


def set_setting(key: str, value: str | None) -> None:
    """Setzt (oder löscht bei None) einen String-Einstellungswert."""
    with session_scope() as session:
        row = session.get(ApplicationSetting, key)
        if value is None:
            if row is not None:
                session.delete(row)
            return
        if row is None:
            session.add(ApplicationSetting(key=key, value=value))
        else:
            row.value = value


def set_ai_selection(provider_id: str, model_id: str, endpoint: str | None = None) -> None:
    """Persistiert die aktive KI-Auswahl atomar."""
    with session_scope() as session:
        rows = {}
        for row in session.scalars(
            select(ApplicationSetting).where(
                ApplicationSetting.key.in_([KEY_PROVIDER, KEY_MODEL, KEY_ENDPOINT])
            )
        ):
            rows[row.key] = row
        for key, value in (
            (KEY_PROVIDER, provider_id),
            (KEY_MODEL, model_id),
            (KEY_ENDPOINT, endpoint),
        ):
            if value is None:
                if key in rows:
                    session.delete(rows[key])
                continue
            if key in rows:
                rows[key].value = value
            else:
                session.add(ApplicationSetting(key=key, value=value))


def get_ai_selection() -> tuple[str | None, str | None, str | None]:
    """Aktive Auswahl aus der DB: (provider_id, model_id, endpoint)."""
    with session_scope() as session:
        rows = {}
        for row in session.scalars(
            select(ApplicationSetting).where(
                ApplicationSetting.key.in_([KEY_PROVIDER, KEY_MODEL, KEY_ENDPOINT])
            )
        ):
            rows[row.key] = row.value
    return rows.get(KEY_PROVIDER), rows.get(KEY_MODEL), rows.get(KEY_ENDPOINT)