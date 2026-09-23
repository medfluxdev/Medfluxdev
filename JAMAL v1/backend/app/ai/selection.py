"""Zustand der aktiven KI-Auswahl (Schritt 6B).

Leitet aus der aktuell gültigen Auswahl (DB oder Umgebung) und den ERKANNTEN
Providern einen ehrlichen Auswahl-Zustand ab. Es wird nie still auf ein anderes
Modell/Provider zurückgefallen: Ist die gespeicherte Auswahl nicht mehr
verfügbar, wird das als `unavailable` ausgewiesen – der Administrator muss
bewusst neu auswählen.
"""

from __future__ import annotations

from app.ai.providers.registry import provider_display_name, supports_provider
from app.ai.schemas import ProviderInfo, SelectionInfo
from app.ai.settings_service import (
    resolve_endpoint_for_provider,
    resolve_model_id,
    resolve_provider_id,
    selection_source,
)
from app.core.config import Settings


def build_selection(settings: Settings, providers: list[ProviderInfo]) -> SelectionInfo:
    provider_id = resolve_provider_id(settings)
    model_id = resolve_model_id(settings)
    source = selection_source(settings)
    if not provider_id or not model_id:
        return SelectionInfo(
            provider_id=None,
            model_id=None,
            source="none",
            state="unselected",
            provider_reachable=False,
            model_available=False,
            message_de="Kein KI-Modell ausgewählt. Bitte Provider und Modell bewusst auswählen.",
        )

    display = provider_display_name(provider_id)

    if not supports_provider(provider_id):
        return SelectionInfo(
            provider_id=provider_id,
            model_id=model_id,
            source=source,
            state="unavailable",
            provider_reachable=False,
            model_available=False,
            message_de=(
                f"Der gespeicherte KI-Provider '{provider_id}' ist nicht verfügbar. "
                "Bitte eine andere Auswahl treffen (unterstützte Provider: Ollama, "
                "LM Studio, llama.cpp, OpenAI-kompatibel)."
            ),
        )

    endpoint = resolve_endpoint_for_provider(settings, provider_id)
    matches = [p for p in providers if p.provider_id == provider_id]
    provider_info = None
    if provider_id == "generic-openai" and endpoint:
        provider_info = next((p for p in matches if p.endpoint == endpoint), None)
    provider_info = provider_info or (next(iter(matches), None) if matches else None)

    if provider_info is None or not provider_info.reachable:
        msg = provider_info.message_de if provider_info else None
        if not msg:
            msg = f"Provider '{display}' ist nicht erreichbar. Bitte eine andere Auswahl treffen."
        return SelectionInfo(
            provider_id=provider_id,
            model_id=model_id,
            source=source,
            state="unavailable",
            provider_reachable=False,
            model_available=False,
            message_de=msg,
        )

    model_ids = {m.model_id for m in provider_info.models}
    if model_id not in model_ids:
        return SelectionInfo(
            provider_id=provider_id,
            model_id=model_id,
            source=source,
            state="unavailable",
            provider_reachable=True,
            model_available=False,
            message_de=(
                f"Das Modell '{model_id}' ist bei '{display}' nicht (mehr) installiert. "
                "Bitte ein verfügbares Modell auswählen."
            ),
        )

    return SelectionInfo(
        provider_id=provider_id,
        model_id=model_id,
        source=source,
        state="ready",
        provider_reachable=True,
        model_available=True,
        message_de=f"Bereit: '{display}' mit Modell '{model_id}'.",
    )