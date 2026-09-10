"""Auflösung der aktiven KI-Auswahl (Schritt 6B).

Die Umgebungskonfiguration (.env) liefert Bootstrap-Defaults. Sobald in der DB
eine Auswahl persistiert wurde (Einstellungs-Oberfläche), gewinnt diese – sie
überlebt Refresh/Restart. Fallen DB-Lesevorgänge aus (nicht migriert / nicht
erreichbar), wird still auf die Umgebungskonfiguration zurückgefallen.
"""

from __future__ import annotations

import logging

from app.ai.providers.registry import endpoint_for
from app.core.config import Settings

logger = logging.getLogger(__name__)


def resolve_provider_id(settings: Settings) -> str:
    """Persistierter oder Bootstrap-Provider (sklavisch, kehrt nie um)."""
    try:
        from app.database.ai_selection import get_ai_selection

        provider, _model, _endpoint = get_ai_selection()
    except Exception as exc:  # noqa: BLE001 - DB darf die KI nicht lahmlegen
        logger.warning("KI-Auswahl nicht lesbar (Fallback auf Umgebung): %s", exc)
        provider = None
    if provider:
        return provider
    return settings.ai_provider


def resolve_model_id(settings: Settings) -> str:
    """Persistiertes oder Bootstrap-Modell."""
    try:
        from app.database.ai_selection import get_ai_selection

        _provider, model, _endpoint = get_ai_selection()
    except Exception as exc:  # noqa: BLE001 - DB darf die KI nicht lahmlegen
        logger.warning("KI-Modell nicht lesbar (Fallback auf Umgebung): %s", exc)
        model = None
    if model:
        return model
    return settings.ollama_model


def resolve_endpoint_for_provider(settings: Settings, provider_id: str) -> str:
    """Endpunkt: DB-Override (generic-openai) sonst Provider-Konfiguration."""
    try:
        from app.database.ai_selection import get_ai_selection

        _provider, _model, endpoint = get_ai_selection()
    except Exception as exc:  # noqa: BLE001
        logger.warning("KI-Endpunkt nicht lesbar (Fallback auf Umgebung): %s", exc)
        endpoint = None
    return endpoint_for(provider_id, settings, endpoint_override=endpoint)


def resolve_ai_selection(settings: Settings) -> tuple[str, str]:
    """(provider_id, model_id) der aktiven Auswahl."""
    return resolve_provider_id(settings), resolve_model_id(settings)


def selection_source(settings: Settings) -> str:
    """'db', wenn mindestens eine Auswahl persistiert wurde, sonst 'env'."""
    try:
        from app.database.ai_selection import get_ai_selection

        provider, model, _endpoint = get_ai_selection()
    except Exception as exc:  # noqa: BLE001 - DB darf die KI nicht lahmlegen
        logger.warning("KI-Auswahl nicht lesbar (source=env): %s", exc)
        return "env"
    return "db" if (provider or model) else "env"