"""Abstraktion der lokalen KI – austauschbare Provider (Schritt 6).

Medflux ist nicht fest an ein konkretes lokales Modell gekoppelt. Ein
`AIProvider` kapselt Health-Check, Modell-Info und Textgenerierung, damit
später ein anderes lokales Modell (oder eine andere lokale Engine) ohne
Änderung an der restlichen Anwendung eingesetzt werden kann.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.ai.schemas import AIStatus, ModelInfo


class AIProvider(ABC):
    """Basis-Interface für lokale KI-Anbieter."""

    @abstractmethod
    async def health_check(self) -> AIStatus:
        """Prüft Erreichbarkeit und Modellverfügbarkeit."""

    @abstractmethod
    async def model_info(self) -> ModelInfo:
        """Liefert Name und Verfügbarkeit des konfigurierten Modells."""

    @abstractmethod
    async def generate(
        self, text: str, system_prompt: str, max_tokens: int | None = None
    ) -> str:
        """Sendet Text an das lokale Modell und liefert die Antwort.

        `max_tokens` erlaubt ein aufgabenabhängiges Ausgabe-Budget (z. B. ein
        größeres Budget für strukturierte Extraktion). Bei None wird der
        Provider-Standard (ai_max_tokens) verwendet.
        Wirft bei Fehlern eine `AIProviderError`-Unterklasse mit deutscher Meldung.
        """

    @abstractmethod
    async def generate_structured(
        self,
        text: str,
        system_prompt: str,
        schema: dict[str, Any],
        max_tokens: int | None = None,
    ) -> str:
        """Sendet Text an das lokale Modell und erzwingt eine JSON-Antwort
        gemäß dem übergebenen JSON-Schema (native strukturierte Ausgabe).

        `schema` ist ein selbstenthaltenes JSON-Schema (ohne `$ref`/`$defs`),
        das der Provider nativ erzwingt. Die Antwort ist ein JSON-String, der
        der Struktur des Schemas entspricht (Semantik bleibt der KI überlassen).
        Wirft bei Fehlern eine `AIProviderError`-Unterklasse mit deutscher Meldung.
        """
