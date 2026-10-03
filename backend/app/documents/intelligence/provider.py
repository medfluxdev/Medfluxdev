"""Provider-neutrale Dokument-Intelligence-Abstraktion (STEP 8B).

Schnittstelle fuer lokale Dokument-Intelligence-Provider. Jeder Provider
liefert ein Medflux-eigenes kanonisches Dokument (canonical.py) – konkrete
Objekttypen (Docling, Paddle-Strukturen, ...) duerfen die Abstraktion NIE
verlassen.

OCR bleibt ein moeglicher interner Bestandteil eines Providers; der bisherige
OCRProvider (app/documents/extraction/ocr.py) bleibt fuer den Schritt-5-Fallback
unveraendert nutzbar und ist hier bewusst nicht eingebunden.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar, Literal, Optional

from pydantic import BaseModel, Field

from app.documents.intelligence.canonical import DocumentIntelligenceResult

ProviderName = Literal["docling", "native_pdf", "paddle", "tesseract"]


class DocumentIntelligenceSettings(BaseModel):
    """Konfiguration, die einen Verarbeitungslauf reproduzierbar macht."""

    do_ocr: bool = True
    do_table_structure: bool = True
    table_mode: Literal["accurate", "fast"] = "accurate"
    ocr_lang: list[str] = Field(default_factory=lambda: ["de", "en"])
    device: Literal["cpu", "cuda", "auto"] = "auto"
    num_threads: Optional[int] = None
    max_pages: Optional[int] = None
    ocr_backend: str = "rapidocr"
    structural_roles: bool = True


# -------------------------------------------------------------foerderbare Meta

class ProviderCapabilities(BaseModel):
    """Faehigkeiten eines Providers fuer Registrierung/Diagnose."""

    name: str
    version: Optional[str] = None
    available: bool
    availability_reason: Optional[str] = None
    supports_pdf: bool = True
    supports_ocr: bool = False
    supports_tables: bool = False
    supports_layout: bool = False
    supports_reading_order: bool = False
    offline_after_setup: bool = True
    ocr_lang: list[str] = Field(default_factory=list)


class DocumentIntelligenceProvider(ABC):
    """Basisklasse aller Dokument-Intelligence-Provider."""

    name: ClassVar[str] = "abstract"

    @abstractmethod
    def is_available(self) -> bool:
        """True, wenn der Provider lauffaehig ist (Binaerdateien, Pakete)."""

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        ...

    @abstractmethod
    def process(
        self,
        path: Path,
        settings: Optional[DocumentIntelligenceSettings] = None,
    ) -> DocumentIntelligenceResult:
        """Verarbeitet ein PDF/Dokument zu einer kanonischen Repraesentation.

        Wirft IntelligenceProviderError bei Fehlern; Original-PDF bleibt unveraendert.
        """
        ...


class IntelligenceProviderError(Exception):
    """Fehler einer Dokument-Intelligence-Verarbeitung."""


class IntelligenceProviderUnavailableError(IntelligenceProviderError):
    """Provider installiert/konfigurierbar, aber derzeit nicht nutzbar."""


# -------------------------------------------------------------Registry

def _default_factory(name: str) -> DocumentIntelligenceProvider:
    if name == "docling":
        from app.documents.intelligence.docling_provider import DoclingDocumentProvider

        return DoclingDocumentProvider()
    if name == "native_pdf":
        from app.documents.intelligence.native_provider import NativePdfDocumentProvider

        return NativePdfDocumentProvider()
    raise IntelligenceProviderError(f"Unbekannter Provider: {name} (paddle/tesseract folgen spaeter)")


def get_provider(name: str = "docling") -> DocumentIntelligenceProvider:
    return _default_factory(name)


def available_providers() -> list[ProviderCapabilities]:
    """Diagnose: alle bekannten Provider und ihre Lauffaehigkeit."""
    out = []
    for name in ("docling", "native_pdf", "paddle", "tesseract"):
        try:
            provider = _default_factory(name)
            caps = provider.capabilities()
        except IntelligenceProviderError as exc:
            reason = str(exc)
            caps = ProviderCapabilities(
                name=name, available=False, availability_reason=reason
            )
        except Exception as exc:  # pragma: no cover - defensive
            caps = ProviderCapabilities(
                name=name, available=False, availability_reason=f"Fehler: {exc}"
            )
        out.append(caps)
    return out