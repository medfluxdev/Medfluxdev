"""API-/Domänen-Schemas für die lokale KI-Integration (Schritt 6).

Erweitert um Anbieter-unabhängige Modell-/Provider-Metadaten (Schritt 6B):
gefundene lokale Provider, deren (normalisierte) Modelllisten und die
aktuell gewählte (persistierte oder bootstrap-default) Auswahl.
"""

from typing import Literal

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


class ModelCapabilities(BaseModel):
    """Normalisierte Fähigkeiten eines Modells.

    `None` = unbekannt (keine autoritative Metadaten-Quelle). Es wird nie aus
    Namens-Bestandteilen ("-vl") gefolgert, wenn Metadaten vorliegen.
    """

    text: bool | None = None
    vision: bool | None = None
    embedding: bool | None = None


class ModelDescriptor(BaseModel):
    """Normalisiertes Modell eines lokalen Providers."""

    model_config = {"protected_namespaces": ()}

    provider_id: str
    model_id: str
    display_name: str | None = None
    state: Literal["available", "unavailable"] = "available"
    loaded: bool | None = None
    context_length: int | None = None
    quantization: str | None = None
    family: str | None = None
    parameter_size: str | None = None
    capabilities: ModelCapabilities = ModelCapabilities()


class ProviderInfo(BaseModel):
    """Gefundener bzw. bekannter lokaler KI-Provider."""

    provider_id: str
    display_name: str
    kind: Literal["native", "openai-compatible"]
    endpoint: str | None = None
    reachable: bool = False
    detection: Literal["native", "openai-compatible"] | None = None
    message_de: str | None = None
    models: list[ModelDescriptor] = []


class SelectionInfo(BaseModel):
    """Aktuell aktive Provider-/Modell-Auswahl (persistiert oder Bootstrap)."""

    provider_id: str
    model_id: str
    source: Literal["db", "env"]
    state: Literal["ready", "unavailable"]
    provider_reachable: bool
    model_available: bool
    message_de: str


class AISnapshot(BaseModel):
    """Kompletter Zustand der lokalen KI für die Einstellungs-Oberfläche."""

    selection: SelectionInfo
    providers: list[ProviderInfo]
    configured_default_provider: str
    configured_default_model: str
    application_version: str


class SelectionUpdate(BaseModel):
    """Neue Provider-/Modell-Auswahl (via Einstellungs-Oberfläche)."""

    model_config = {"protected_namespaces": ()}

    provider_id: str = Field(..., min_length=1, max_length=80)
    model_id: str = Field(..., min_length=1, max_length=300)
    endpoint: str | None = Field(default=None, max_length=500)