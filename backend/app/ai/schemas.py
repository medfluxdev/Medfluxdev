"""API-/Domänen-Schemas für die lokale KI-Integration (Schritt 6)."""

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """Kurzinformation zu einem lokalen KI-Modell."""

    name: str
    available: bool


class AIStatus(BaseModel):
    """Strukturierter Status der lokalen KI."""

    model_config = {"protected_namespaces": ()}

    provider: str
    available: bool
    model: str
    model_available: bool
    message: str


class AITestRequest(BaseModel):
    """Eingabe für den Test-/Entwicklungs-Endpunkt."""

    text: str = Field(..., min_length=1, max_length=20000)


class AITestResponse(BaseModel):
    """Antwort des Test-Endpunkts (Erfolg oder deutscher Hinweis)."""

    provider: str
    model: str
    response: str | None = None
    error: str | None = None
