"""KI-Routen (Schritt 6/6B): Status, Snapshot, Test- und Auswahl-Endpunkte.

Dünne API-Schicht – alle Logik liegt im AIService bzw. in Discovery/Selection.
Enthält KEINE Vertrags-Extraktion (das folgt in Schritt 7). Die Auswahl wird
NUR validiert und persistiert; an der Auswahl wird nie inferiert.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.ai.providers import discovery
from app.ai.providers.registry import (
    build_provider,
    get_provider_spec,
    provider_display_name,
)
from app.ai.schemas import (
    AISnapshot,
    AITestRequest,
    AITestResponse,
    AIStatus,
    SelectionUpdate,
)
from app.ai.selection import build_selection
from app.ai.service import AIService
from app.auth.context import require_identity
from app.core.config import settings
from app.database.ai_selection import set_ai_selection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

_ai_service = AIService(settings)


async def build_snapshot() -> AISnapshot:
    """Ein kanonischer Schnappschuss: Provider + Modelle + aktive Auswahl."""
    providers = await discovery.discover_providers(settings)
    selection = build_selection(settings, providers)
    return AISnapshot(
        selection=selection,
        providers=providers,
        configured_default_provider=settings.ai_provider,
        configured_default_model=settings.ollama_model,
        application_version=settings.app_version,
    )


@router.get("/status", response_model=AIStatus)
async def ai_status() -> AIStatus:
    """Liefert den aktuellen Status der lokalen KI (kanonischer Zustand)."""
    return await _ai_service.status()


@router.get("/snapshot", response_model=AISnapshot)
async def ai_snapshot() -> AISnapshot:
    """Einstellungen-Schnappschuss: erkannte Provider, Modelle, Auswahl."""
    return await build_snapshot()


@router.post("/test", response_model=AITestResponse)
async def ai_test(payload: AITestRequest) -> AITestResponse:
    """Test-/Entwicklungs-Endpunkt: sendet Text an das lokale Modell."""
    return await _ai_service.generate_test(payload.text)


@router.put("/selection", response_model=AISnapshot)
async def ai_set_selection(payload: SelectionUpdate, request: Request) -> AISnapshot:
    """Persistiert die aktive KI-Auswahl – validiert, ohne zu inferieren.

    Fehlschläge liefern 400 mit deutscher Meldung; Erfolg liefert den frischen
    Snapshot (identischer kanonischer Zustand wie GET /api/ai/snapshot).
    """
    if settings.auth_enabled:
        identity = require_identity(request)
        if identity.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Nur Administratoren duerfen die KI-Auswahl aendern.",
            )

    provider_id = payload.provider_id.strip()
    model_id = payload.model_id.strip()

    spec = get_provider_spec(provider_id)
    if spec is None:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider_id}' wird nicht unterstützt.",
        )

    is_generic = provider_id == "generic-openai"
    endpoint = payload.endpoint.strip() if payload.endpoint else ""
    if is_generic and not endpoint:
        raise HTTPException(
            status_code=400,
            detail="Für den OpenAI-kompatiblen Anbieter ist ein Endpunkt erforderlich.",
        )
    if is_generic:
        if not endpoint.startswith("http://127.0.0.1:") and not endpoint.startswith("http://localhost:"):
            raise HTTPException(
                status_code=400,
                detail="Nur lokale Endpunkte (localhost) sind erlaubt.",
            )
        probe_base = endpoint
    else:
        configured = spec.endpoint(settings).strip()
        if not configured:
            raise HTTPException(
                status_code=400,
                detail=f"Der Endpunkt für '{provider_display_name(provider_id)}' ist nicht konfiguriert.",
            )
        probe_base = configured

    reachable = await discovery.probe_provider_reachable(
        provider_id, settings, endpoint_override=probe_base if is_generic else None
    )
    if not reachable:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Provider '{provider_display_name(provider_id)}' ist nicht erreichbar "
                "und kann nicht ausgewählt werden."
            ),
        )

    adapter = build_provider(
        provider_id,
        settings,
        endpoint_override=probe_base if is_generic else None,
    )
    try:
        models = await adapter.discover_models()
    except Exception as exc:  # noqa: BLE001 - ehrliche deutsche Meldung
        logger.warning("Modellliste für Auswahl %s fehlgeschlagen: %s", provider_id, exc)
        raise HTTPException(
            status_code=400,
            detail=f"Die Modellliste für '{provider_display_name(provider_id)}' konnte nicht geladen werden.",
        ) from exc
    if not any(m.model_id == model_id for m in models):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Das Modell '{model_id}' ist bei '{provider_display_name(provider_id)}' "
                "nicht (mehr) verfügbar."
            ),
        )

    set_ai_selection(
        provider_id,
        model_id,
        endpoint=probe_base if is_generic else None,
    )
    return await build_snapshot()