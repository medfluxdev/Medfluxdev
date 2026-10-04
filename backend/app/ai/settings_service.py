"""Auflösung der aktiven KI-Auswahl.

Es gibt bewusst KEIN aktives Standardmodell. Provider/Modell werden nur aus
der explizit gespeicherten Benutzerauswahl gelesen. Fehlt die Auswahl oder
ist die Datenbank nicht lesbar, bleibt Medflux im Zustand "nicht ausgewählt"
und startet keine KI-Analyse.
"""

from __future__ import annotations

import logging

from app.ai.providers.registry import endpoint_for
from app.core.config import Settings

logger = logging.getLogger(__name__)


def _stored_selection() -> tuple[str | None, str | None, str | None]:
    try:
        from app.database.ai_selection import get_ai_selection

        return get_ai_selection()
    except Exception as exc:  # DB-Fehler darf nie heimlich ein Modell aktivieren
        logger.warning("KI-Auswahl nicht lesbar; keine Auswahl aktiv: %s", exc)
        return None, None, None


def resolve_provider_id(settings: Settings) -> str | None:
    """Nur explizit persistierter Provider; niemals Environment-Fallback."""
    provider, model, _endpoint = _stored_selection()
    return provider if provider and model else None


def resolve_model_id(settings: Settings) -> str | None:
    """Nur explizit persistiertes Modell; niemals Bootstrap-/Default-Modell."""
    provider, model, _endpoint = _stored_selection()
    return model if provider and model else None


def resolve_endpoint_for_provider(settings: Settings, provider_id: str) -> str:
    """Endpoint-Override stammt aus der gespeicherten Auswahl; Basis-URLs aus Settings."""
    _provider, _model, endpoint = _stored_selection()
    return endpoint_for(provider_id, settings, endpoint_override=endpoint)


def resolve_ai_selection(settings: Settings) -> tuple[str | None, str | None]:
    return resolve_provider_id(settings), resolve_model_id(settings)


def selection_source(settings: Settings) -> str:
    provider, model, _endpoint = _stored_selection()
    return "db" if provider and model else "none"
