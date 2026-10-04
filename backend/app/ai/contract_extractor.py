"""Strukturierte KI-Extraktion von Vertragsdaten (Schritt 7).

Pipeline (vollständig lokal, ohne DB-Persistenz):

    TextExtractionResult (Schritt 5, ExtractionUnit-Liste)
        -> deterministisches Chunking nach Texteinheiten (Seiten/Absätze/Tabellen)
        -> strukturierte Extraktion je Chunk über die lokale KI (AIService/AIProvider)
        -> strikte JSON-Ausgabe
        -> Parsing
        -> Pydantic-Validierung gegen das Contract-Schema
        -> deterministisches Multi-Chunk-Merging
        -> Contract-Modell + Analyse-Ergebnis

Die KI extrahiert Fakten; KEINE Berechnungen (latest_cancellation_date,
Kostenaggregation, Warnstufen) finden hier statt – das bleibt späteren Schritten.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from app.ai.groups.extractor import GroupPipeline
from app.ai.prompts.contract_extraction_v1 import (
    CONTRACT_EXTRACTION_SYSTEM_PROMPT,
    PROMPT_VERSION,
)
from app.ai.service import AIService
from app.core.config import Settings
from app.documents.extraction.schemas import ExtractionUnit
from app.models.contract import Contract
from app.models.enums import (
    ExtractionStatus,
    ReviewFlag,
    ReviewStatus,
    ValidationStatus,
)

MSG_AI_UNAVAILABLE = "Die lokale KI ist derzeit nicht verfügbar."
MSG_AI_INVALID_JSON = "Der Modell-Ausgabe war kein gültiges JSON zu entnehmen."
MSG_VALIDATION = "Die extrahierten Daten konnten nicht vollständig validiert werden."
MSG_NO_TEXT = "Für dieses Dokument wurde kein Text extrahiert – eine Analyse ist nicht möglich."


@dataclass
class ContractChunk:
    """Ein deterministisch gebildeter, in sich geschlossener Textabschnitt."""

    index: int
    text: str
    unit_refs: list[ExtractionUnit] = field(default_factory=list)


class ContractAnalysisResult(BaseModel):
    """Ergebnis einer vollständigen strukturierten Vertragsanalyse."""

    model_config = {"protected_namespaces": ()}

    document_id: str
    status: ExtractionStatus = ExtractionStatus.FAILED
    validation_status: ValidationStatus = ValidationStatus.UNKNOWN
    requires_review: bool = False
    contract: Optional[Contract] = None
    message: str = ""
    error: Optional[str] = None
    model: Optional[str] = None
    prompt_version: str = PROMPT_VERSION
    chunk_count: int = 0
    processing_duration: float = Field(default=0.0, ge=0.0)
    # STEP 8B: Diagnose-Metriken für strukturierte Ausgabe
    timeout_count: int = 0
    retry_count: int = 0
    truncated_chunks: int = 0
    # STEP 8B-Semantik: Diagnose-Metriken der Feldgruppen-Pipeline
    ai_call_count: int = 0
    groups_processed: int = 0
    evidence_issues: int = 0
    verifier_issues: int = 0
    normalization_issues: int = 0
    # Harness v2.1 diagnostics survive even when ``contract`` is None.
    # The payload is deliberately structured and source-text free so failures can
    # be diagnosed without persisting contract content or chain-of-thought.
    diagnostics: dict[str, Any] = Field(default_factory=dict)


def _unit_header(unit: ExtractionUnit) -> str:
    st = unit.source_type.value if hasattr(unit.source_type, "value") else str(unit.source_type)
    if st == "page":
        return f"\n[Seite {unit.index}]\n"
    return f"\n[{st.capitalize()} {unit.index}]\n"


def _make_chunk(index: int, units: list[ExtractionUnit]) -> ContractChunk:
    parts = []
    for u in units:
        header = _unit_header(u)
        text = u.text.strip()
        parts.append((header + text) if text else header)
    return ContractChunk(index=index, text="".join(parts).strip(), unit_refs=list(units))


def chunk_units(units: list[ExtractionUnit], max_chars: int = 6000) -> list[ContractChunk]:
    """Bildet deterministisch begrenzte Chunks aus extrahierten Einheiten.

    Einheiten (Seiten/Absätze/Tabellen) werden in Dokumentreihenfolge
    zusammengefasst, bis die Zeichen-Grenze erreicht ist. Eine einzelne
    über-große Einheit bildet allein einen eigenen Chunk (sie wird NICHT
    zerstückelt), damit die Quellzuordnung erhalten bleibt.
    """
    if max_chars <= 0:
        max_chars = 6000
    chunks: list[ContractChunk] = []
    current_units: list[ExtractionUnit] = []
    current_len = 0

    for unit in units:
        block_len = len((_unit_header(unit) + unit.text).strip())

        if block_len > max_chars:
            if current_units:
                chunks.append(_make_chunk(len(chunks) + 1, current_units))
                current_units = []
                current_len = 0

            current_units.append(unit)
            current_len = block_len
            chunks.append(_make_chunk(len(chunks) + 1, current_units))
            current_units = []
            current_len = 0
            continue

        if current_units and current_len + block_len > max_chars:
            chunks.append(_make_chunk(len(chunks) + 1, current_units))
            current_units = []
            current_len = 0

        current_units.append(unit)
        current_len += block_len

    if current_units:
        chunks.append(_make_chunk(len(chunks) + 1, current_units))
    return chunks


def _build_user_prompt(chunk: ContractChunk, total_chunks: int) -> str:
    return (
        f"Dokumentauszug (Abschnitt {chunk.index} von {total_chunks}). "
        f"Alle Angaben müssen durch diesen Auszug belegt sein.\n\n"
        f"{chunk.text}\n"
    )


def _parse_json(raw: str) -> Optional[dict[str, Any]]:
    """Parst die Modell-Ausgabe als JSON.

    Primär wird die gesamte (getrimmte) Antwort als JSON gelesen. Nur als
    defensive Notlösung wird bei Bedarf der erste ausgeglichene Objektblock
    extrahiert – NICHT als primärer Mechanismus (kein Markdown-Cleanup-Hack).
    """
    if not raw or not raw.strip():
        return None
    stripped = raw.strip()
    try:
        data = json.loads(stripped)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(stripped)):
        ch = stripped[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(stripped[start : i + 1])
                    return data if isinstance(data, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


_RETRY_SYSTEM_PROMPT_SUFFIX = (
    "\n\nWICHTIG: Deine vorherige Antwort war KEIN gültiges JSON bzw. wich vom "
    "vorgegebenen Schema ab und wurde deshalb verworfen. Antworte jetzt "
    "AUSSCHLIESSLICH mit einem gültigen, VOLLSTÄNDIGEN JSON-Objekt, das "
    "GENAU der vorgegebenen Struktur entspricht (Feldnamen, Listen/Objekte, "
    "contract_type-Kleinbuchstaben-Enum). Kein Markdown, kein Text davor/danach."
)


class StructuredContractExtractor:
    """Führt die strukturierte Extraktion über die lokale KI durch.

    Arbeitet ausschließlich über die vorhandene AIProvider-Abstraktion
    (AIService) – es gibt KEINE abweichenden/Cloud-Aufrufe.
    """

    def __init__(
        self,
        ai_service: AIService,
        settings: Optional[Settings] = None,
        max_retries: int = 1,
    ) -> None:
        self._ai = ai_service
        self._settings = settings or Settings(_env_file=None)
        self._max_retries = max_retries

    async def extract(self, extraction_units: list[ExtractionUnit]) -> ContractAnalysisResult:
        """Extrahiert das Vertragsmodell aus den Texteinheiten.

        Nutzt die spezialisierte Feldgruppen-Extraktion (STEP 8B-Semantik):
        kleine, semantische Gruppen-Schemas statt des kompletten Contract-Schemas
        je Chunk, Evidence-First-Verifikation, deterministische Normalisierung und
        einen semantischen Verifier für sensible Felder.
        """
        start = time.monotonic()

        useful = [u for u in extraction_units if u.text.strip()]
        if not useful:
            return ContractAnalysisResult(
                document_id="",
                status=ExtractionStatus.FAILED,
                validation_status=ValidationStatus.UNKNOWN,
                requires_review=True,
                message=MSG_NO_TEXT,
                error=MSG_NO_TEXT,
                chunk_count=0,
                processing_duration=time.monotonic() - start,
            )

        chunks = chunk_units(useful, self._settings.ai_max_chunk_characters)

        pipeline = GroupPipeline(
            self._ai,
            self._settings,
            max_retries=self._max_retries,
            run_verification=self._settings.ai_run_semantic_verification,
        )
        contract, diag, messages = await pipeline.run(chunks, useful)

        if contract is None:
            error = MSG_VALIDATION
            return ContractAnalysisResult(
                document_id="",
                status=ExtractionStatus.FAILED,
                validation_status=ValidationStatus.INVALID,
                requires_review=True,
                message=error,
                error=error,
                model=self._settings.ollama_model,
                chunk_count=len(chunks),
                processing_duration=time.monotonic() - start,
                timeout_count=diag.timeouts,
                retry_count=diag.retries,
                truncated_chunks=diag.truncated_chunks,
                ai_call_count=diag.ai_calls,
                groups_processed=diag.groups_processed,
                evidence_issues=diag.evidence_issues,
                verifier_issues=diag.verifier_issues,
                normalization_issues=diag.normalization_issues,
            )

        validation_ok = not contract.review.requires_manual_review

        return ContractAnalysisResult(
            document_id="",
            status=(
                ExtractionStatus.SUCCESS if validation_ok else ExtractionStatus.PARTIAL
            ),
            validation_status=(
                ValidationStatus.VALID if validation_ok else ValidationStatus.INVALID
            ),
            requires_review=contract.review.requires_manual_review,
            contract=contract,
            message=(
                "Analyse erfolgreich."
                if validation_ok
                else "Analyse teilweise erfolgreich – bitte prüfen."
            ),
            model=self._settings.ollama_model,
            chunk_count=len(chunks),
            processing_duration=time.monotonic() - start,
            timeout_count=diag.timeouts,
            retry_count=diag.retries,
            truncated_chunks=diag.truncated_chunks,
            ai_call_count=diag.ai_calls,
            groups_processed=diag.groups_processed,
            evidence_issues=diag.evidence_issues,
            verifier_issues=diag.verifier_issues,
            normalization_issues=diag.normalization_issues,
        )

    # ------------------------------------------------------------- intern

    async def _extract_chunk(
        self, chunk: ContractChunk, total_chunks: int
    ) -> tuple[Optional[Contract], bool, Optional[str], dict[str, int]]:
        """Extrahiert und validiert einen einzelnen Chunk (Kompatibilität).

        Wartet STEP 8B-Semantik-Schicht weiterhin hinter der Gruppen-Pipeline;
        diese Methode bleibt als stabile Naht für Tests/Alternativen erhalten
        und nutzt weiterhin das komplette Contract-Schema.
        """
        user_prompt = _build_user_prompt(chunk, total_chunks)
        parsed_data: Optional[dict[str, Any]] = None
        diag = {"timeouts": 0, "retries": 0, "truncated": 0}
        attempts = 0

        from app.ai.schema import contract_json_schema

        for attempt in range(self._max_retries + 1):
            attempts = attempt + 1
            system_prompt = CONTRACT_EXTRACTION_SYSTEM_PROMPT
            if attempt > 0:
                system_prompt = system_prompt + _RETRY_SYSTEM_PROMPT_SUFFIX
            try:
                raw = await self._ai.generate_structured(
                    user_prompt,
                    system_prompt,
                    contract_json_schema(),
                    max_tokens=self._settings.ai_extraction_max_tokens,
                )
            except Exception:
                diag["timeouts"] += 1
                if attempt >= self._max_retries:
                    return None, False, None, diag
                continue

            if self._ai.last_done_reason == "length":
                diag["truncated"] += 1

            parsed_data = _parse_json(raw)
            if parsed_data is None:
                if attempt >= self._max_retries:
                    return None, False, MSG_AI_INVALID_JSON, diag
                continue

            try:
                contract = Contract.model_validate(parsed_data)
                diag["retries"] = max(0, attempts - 1)
                return contract, True, None, diag
            except ValidationError:
                if attempt >= self._max_retries:
                    diag["retries"] = max(0, attempts - 1)
                    return None, False, MSG_VALIDATION, diag
                parsed_data = None

        diag["retries"] = max(0, attempts - 1)
        return None, False, MSG_VALIDATION, diag

    def _finalize_review(self, contract: Contract, validation_ok: bool) -> None:
        """Setzt Prüfinformationen auf dem finalen Vertrag (Kompatibilität)."""
        if not validation_ok:
            contract.review.requires_manual_review = True
            contract.review.review_status = ReviewStatus.NEEDS_REVIEW
            if ReviewFlag.LOW_CONFIDENCE not in contract.review.review_reasons:
                contract.review.review_reasons.append(ReviewFlag.LOW_CONFIDENCE)

    def _merge(self, base: Contract, incoming: Contract) -> Contract:
        """Deterministisches Merge zweier Chunk-Verträge (Kompatibilität)."""
        conflicts: list[str] = []
        merged_data = _deep_merge(
            base.model_dump(exclude_none=False),
            incoming.model_dump(exclude_none=False),
            conflicts,
        )
        merged = Contract.model_validate(merged_data)
        if conflicts:
            merged.review.requires_manual_review = True
            merged.review.review_status = ReviewStatus.NEEDS_REVIEW
            if ReviewFlag.CONFLICT not in merged.review.review_reasons:
                merged.review.review_reasons.append(ReviewFlag.CONFLICT)
            notes = "; ".join(conflicts[:5])
            merged.review.risk_notes = (
                f"{merged.review.risk_notes}; " if merged.review.risk_notes else ""
            ) + notes
        return merged


def _deep_merge(old: Any, new: Any, conflicts: list[str], path: str = "$") -> Any:
    """Mergt zwei JSON-Struktur-Werte deterministisch. Siehe Regeln oben."""

    if isinstance(old, dict) and isinstance(new, dict):
        out: dict[str, Any] = dict(old)
        for key, new_val in new.items():
            child_path = f"{path}.{key}"
            if key not in out:
                out[key] = new_val
            else:
                out[key] = _deep_merge(out[key], new_val, conflicts, child_path)
        return out

    if isinstance(old, list) and isinstance(new, list):
        return _merge_lists(old, new, conflicts, path)

    if old is None:
        return new
    if new is None:
        return old
    if old == new:
        return old

    conflicts.append(f"{path}: unterschiedliche Werte ({old!r} vs {new!r})")
    return old


def _merge_lists(old: list, new: list, conflicts: list[str], path: str) -> list:
    # Für Objekt-Listen (z. B. equipment) deduplizieren wir nach Inhalt.
    if new and isinstance(new[0], dict):
        merged = list(old)
        seen = {_list_key(item) for item in old}
        for item in new:
            k = _list_key(item)
            if k not in seen:
                merged.append(item)
                seen.add(k)
        return merged

    merged = list(old)
    for item in new:
        if item not in merged:
            merged.append(item)
    return merged


def _list_key(item: dict) -> tuple:
    return tuple(sorted((k, str(v)) for k, v in item.items()))


class ContractAnalysisOrchestrator:
    """Orchestriert die Analyse eines bereits extrahierten Dokuments.

    Nimmt das Ergebnis der Schritt-5-Text-Extraktion entgegen und delegiert
    die strukturierte Extraktion an den StructuredContractExtractor. Enthält
    KEINE Berechnungslage – reine Analyse.
    """

    def __init__(
        self,
        extractor: Optional[StructuredContractExtractor] = None,
        ai_service: Optional[AIService] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self._settings = settings or Settings(_env_file=None)
        if extractor is not None:
            self._extractor = extractor
        else:
            ai = ai_service or AIService(self._settings)
            self._extractor = StructuredContractExtractor(ai, self._settings)

    async def analyze(
        self, extraction_result: Any
    ) -> ContractAnalysisResult:
        """Analysiert das Schritt-5-Ergebnis zu einem Contract-Modell.

        `extraction_result` ist ein TextExtractionResult (dokument-agnostisch
        über seine `units`- und `document_id`-Attribute verwendet).
        """
        document_id = getattr(extraction_result, "document_id", "")
        units: list[ExtractionUnit] = getattr(extraction_result, "units", []) or []

        result = await self._extractor.extract(list(units))
        result.document_id = document_id
        return result

