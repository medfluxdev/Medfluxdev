"""KI-Routen (Schritt 6): Status- und Test-Endpunkt der lokalen KI.

Dünne API-Schicht – alle Logik liegt im AIService. Enthält KEINE
Vertrags-Extraktion (das folgt in Schritt 7).
"""

from fastapi import APIRouter

from app.ai.schemas import AITestRequest, AITestResponse, AIStatus
from app.ai.service import AIService
from app.core.config import settings

router = APIRouter(prefix="/api/ai", tags=["ai"])

_ai_service = AIService(settings)


@router.get("/status", response_model=AIStatus)
async def ai_status() -> AIStatus:
    """Liefert den aktuellen Status der lokalen KI."""
    return await _ai_service.status()


@router.post("/test", response_model=AITestResponse)
async def ai_test(payload: AITestRequest) -> AITestResponse:
    """Test-/Entwicklungs-Endpunkt: sendet Text an das lokale Modell."""
    return await _ai_service.generate_test(payload.text)
