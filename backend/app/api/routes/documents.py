"""Import-, Extraktions- und Analyse-Routen für Medflux-Dokumente (Schritt 4+5+7).

Dünne API-Schicht: Multipart-Dateien entgegennehmen bzw. Extraktion/Analyse
anstoßen und an die jeweiligen Services delegieren. Alle Fachlogik liegt im
Service. Die Analyse (Schritt 7) bleibt vollständig lokal – keine DB-Persistenz.
"""

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.ai.contract_extractor import (
    ContractAnalysisOrchestrator,
    ContractAnalysisResult,
)
from app.documents.extraction.schemas import TextExtractionResult
from app.documents.extraction.service import TextExtractionService
from app.documents.schemas import ImportBatchResponse
from app.documents.service import DocumentImportService

router = APIRouter(prefix="/api/documents", tags=["documents"])

_service = DocumentImportService()
_extraction_service = TextExtractionService()
_analysis_service = ContractAnalysisOrchestrator()

MSG_DOCUMENT_NOT_FOUND = "Dokument nicht gefunden."


@router.post("/import", response_model=ImportBatchResponse)
async def import_documents(files: list[UploadFile] = File(default=[])) -> ImportBatchResponse:
    """Importiert eine oder mehrere Dateien (PDF/DOCX) lokal."""
    if not files:
        return ImportBatchResponse(
            total=0, successful=0, failed=0, duplicates=0, documents=[]
        )

    payload: list[tuple[str, str, bytes]] = []
    for f in files:
        raw = await f.read()
        payload.append((f.filename or "", f.content_type or "", raw))

    return _service.import_many(payload)


@router.post("/{document_id}/extract", response_model=TextExtractionResult)
async def extract_document(document_id: str) -> TextExtractionResult:
    """Extrahiert Text aus einem bereits importierten Dokument (lokal)."""
    result = _extraction_service.extract(document_id)
    if result is None:
        raise HTTPException(status_code=404, detail=MSG_DOCUMENT_NOT_FOUND)
    return result


@router.post("/{document_id}/analyze", response_model=ContractAnalysisResult)
async def analyze_document(document_id: str) -> ContractAnalysisResult:
    """Strukturierte lokale KI-Analyse eines importierten Dokuments (Schritt 7).

    Fluss: Dokument lokalisieren -> Text extrahieren (Schritt 5) -> strukturierte
    Extraktion über die lokale KI -> Parsing/Validierung -> Ergebnis. Keine
    DB-Persistenz. Fehler werden deutsch und graceful zurückgegeben.
    """
    extraction = _extraction_service.extract(document_id)
    if extraction is None:
        raise HTTPException(status_code=404, detail=MSG_DOCUMENT_NOT_FOUND)
    return await _analysis_service.analyze(extraction)
