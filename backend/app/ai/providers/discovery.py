"""Lokale Provider-/Modell-Erkennung (Schritt 6B).

Erkennung bleibt strikt auf konfigurierte LOCALHOST-Endpunkte begrenzt
(kurze Timeouts, kein LAN-/Netz-Scan, keine Vertragsdaten). Ein Endpunkt wird
nur dann einem konkreten Provider zugeordnet, wenn ein PROVIDER-SPEZIFISCHER
Fingerabdruck vorliegt. Antwortet ein Endpunkt OpenAI-kompatibel, lässt sich
aber kein Provider autoritativ nachweisen, wird er als generischer
OpenAI-kompatibler Anbieter repräsentiert – nie fälschlich als LM Studio/
llama.cpp ausgegeben.
"""

from __future__ import annotations

import logging

import httpx

from app.ai.exceptions import AIProviderError
from app.ai.providers.openai_compat import probe_openai_models
from app.ai.providers.registry import (
    build_provider,
    get_provider_spec,
    provider_display_name,
    supported_provider_ids,
)
from app.ai.schemas import ProviderInfo
from app.core.config import Settings

logger = logging.getLogger(__name__)

MSG_NOT_CONFIGURED = "Endpunkt für {name} ist nicht konfiguriert."
MSG_UNREACHABLE = "Provider '{name}' ist nicht erreichbar."
MSG_MODELS_FAILED = "Die Modellliste für '{name}' konnte nicht geladen werden."


async def discover_providers(settings: Settings, client: httpx.AsyncClient | None = None) -> list[ProviderInfo]:
    """Erkennt konfigurierte lokale Provider und lädt deren Modelllisten.

    `client` erlaubt das Injizieren eines (gemockten) httpx-Clients in Tests.
    """
    providers: list[ProviderInfo] = []
    identified_endpoints: set[str] = set()
    close = client is None
    probe_client = client or httpx.AsyncClient(timeout=settings.ai_discovery_timeout_seconds)
    try:
        for provider_id in supported_provider_ids():
            spec = get_provider_spec(provider_id)
            if spec is None:
                continue
            endpoint = spec.endpoint(settings).strip()
            if not endpoint:
                # Der generische Anbieter hat keinen eigenen Endpunkt: er
                # erscheint nur, wenn ein Endpunkt OpenAI-kompatibel antwortet
                # (Fallback) oder explizit konfiguriert wurde.
                if provider_id == "generic-openai":
                    continue
                providers.append(
                    ProviderInfo(
                        provider_id=spec.provider_id,
                        display_name=spec.display_name,
                        kind=spec.kind if spec.kind == "openai-compatible" else "native",
                        endpoint=None,
                        reachable=False,
                        message_de=MSG_NOT_CONFIGURED.format(name=spec.display_name),
                    )
                )
                continue
            base = endpoint.rstrip("/")
            reachable = False
            detection = None
            try:
                reachable = bool(await spec.detect(probe_client, base))
            except Exception as exc:  # noqa: BLE001 - Erkennung darf nie crashen
                logger.warning("Erkennung %s fehlgeschlagen: %s", spec.provider_id, exc)
                reachable = False
            if reachable:
                detection = "native" if spec.kind == "native" else "openai-compatible"
                identified_endpoints.add(base)
            providers.append(
                ProviderInfo(
                    provider_id=spec.provider_id,
                    display_name=spec.display_name,
                    kind=spec.kind if spec.kind == "openai-compatible" else "native",
                    endpoint=base,
                    reachable=reachable,
                    detection=detection,
                    message_de=None if reachable else MSG_UNREACHABLE.format(name=spec.display_name),
                    models=[],
                )
            )

        # Generischer Fallback: unidentifizierte, aber OpenAI-kompatible Endpunkte
        # werden als "Kompatibler lokaler Anbieter" geführt (nie als konkreter
        # Provider ausgegeben).
        for provider_id in supported_provider_ids():
            spec = get_provider_spec(provider_id)
            if spec is None:
                continue
            endpoint = spec.endpoint(settings).strip()
            if not endpoint:
                continue
            base = endpoint.rstrip("/")
            if base in identified_endpoints:
                continue
            if any(p.provider_id == "generic-openai" and p.endpoint == base for p in providers):
                continue
            try:
                is_openai = await probe_openai_models(probe_client, base)
            except Exception:  # noqa: BLE001
                is_openai = False
            if is_openai:
                providers.append(
                    ProviderInfo(
                        provider_id="generic-openai",
                        display_name="Kompatibler lokaler Anbieter (OpenAI)",
                        kind="openai-compatible",
                        endpoint=base,
                        reachable=True,
                        detection="openai-compatible",
                        models=[],
                    )
                )

        await _enrich_models(providers, settings, client=probe_client)
    finally:
        if close:
            await probe_client.aclose()
    return providers


async def _enrich_models(
    providers: list[ProviderInfo],
    settings: Settings,
    client: httpx.AsyncClient,
) -> None:
    for provider in providers:
        if not provider.reachable:
            continue
        endpoint = provider.endpoint or (
            settings.generic_openai_base_url if provider.provider_id == "generic-openai" else None
        )
        try:
            adapter = build_provider(
                provider.provider_id,
                settings,
                client=client,
                endpoint_override=endpoint if provider.provider_id == "generic-openai" else None,
            )
            models = await adapter.discover_models()
            provider.models = models
        except AIProviderError as exc:
            provider.message_de = exc.user_message
        except Exception as exc:  # noqa: BLE001 - Modellliste darf Snapshot nie crashen
            logger.warning("Modellliste %s fehlgeschlagen: %s", provider.provider_id, exc)
            provider.message_de = MSG_MODELS_FAILED.format(
                name=provider_display_name(provider.provider_id)
            )


async def probe_provider_reachable(
    provider_id: str,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
    endpoint_override: str | None = None,
) -> bool:
    """Schnelle, einzelne Erreichbarkeitsprobe eines Providers (für Auswahl)."""
    spec = get_provider_spec(provider_id)
    if spec is None:
        return False
    endpoint = (endpoint_override or spec.endpoint(settings)).strip()
    if not endpoint:
        return False
    close = client is None
    probe_client = client or httpx.AsyncClient(timeout=settings.ai_discovery_timeout_seconds)
    try:
        return bool(await spec.detect(probe_client, endpoint.rstrip("/")))
    except Exception:  # noqa: BLE001
        return False
    finally:
        if close:
            await probe_client.aclose()