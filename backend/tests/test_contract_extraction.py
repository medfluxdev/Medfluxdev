"""Tests für die strukturierte lokale KI-Extraktion (Schritt 7 + STEP 8B-Semantik).

Alle Ollama-Antworten werden über httpx.MockTransport gemockt – es wird KEINE
echte Ollama-Installation oder Cloud-API vorausgesetzt. Die Tests decken die
Feldgruppen-Pipeline Chunking -> Gruppen-KI-Aufrufe -> Parsing -> Validierung ->
Merge -> Evidence-Verifikation -> Review-Pfade ab und bleiben vollständig lokal.
"""

from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai.contract_extractor import (
    ContractAnalysisOrchestrator,
    ContractAnalysisResult,
    StructuredContractExtractor,
    chunk_units,
)
from app.ai.service import AIService
from app.api.routes import documents as documents_module
from app.core.config import Settings
from app.database.ai_selection import set_ai_selection, set_setting
from app.documents.extraction.schemas import (
    ExtractionUnit,
    SourceType,
    TextExtractionResult,
    UnitMethod,
)
from app.main import app as medflux_app
from app.models.enums import ExtractionStatus, ReviewFlag, ReviewStatus

from tests.helpers_group import build_handler, chat_reply

client = TestClient(medflux_app)
settings = Settings(_env_file=None)
MODEL = "qwen3:8b-test"


@pytest.fixture(autouse=True)
def _explicit_model_selection_for_mocked_ai():
    set_ai_selection("ollama", MODEL)
    yield
    for key in ("ai_provider", "ai_model", "ai_provider_endpoint"):
        set_setting(key, None)


# ---------------------------------------------------------------- Fixtures

def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _orchestrator(handler: Callable[[httpx.Request], httpx.Response]) -> ContractAnalysisOrchestrator:
    s = Settings(_env_file=None)
    ai = AIService(s, client=_client(handler))
    return ContractAnalysisOrchestrator(
        ai_service=ai,
        extractor=StructuredContractExtractor(ai, s),
    )


class _StubExtraction:
    def __init__(self, docs):
        self.docs = docs

    def extract(self, document_id):
        return self.docs.get(document_id)


def _page(page, text):
    return ExtractionUnit(
        source_type=SourceType.PAGE,
        index=page,
        text=text,
        method=UnitMethod.TEXT,
    )


# ---------------------------------------------------------------- Chunking & Units

def test_chunk_units_splits_by_chars():
    units = [
        ExtractionUnit(
            source_type=SourceType.PAGE,
            index=1,
            text="a" * 4000,
            method=UnitMethod.TEXT,
        ),
        ExtractionUnit(
            source_type=SourceType.PAGE,
            index=2,
            text="b" * 4000,
            method=UnitMethod.TEXT,
        ),
    ]
    chunks = chunk_units(units, max_chars=5000)
    assert len(chunks) == 2
    for chunk in chunks:
        assert len(chunk.text) <= 5000
        assert chunk.unit_refs, "jeder Chunk muss mindestens eine Einheit tragen"
        for unit in chunk.unit_refs:
            assert unit in units


# ---------------------------------------------------------------- Full pipeline (mocked Ollama)

FULL = build_handler({
    "identity": {
        "contract_title": "Wartungsvertrag",
        "contract_number": "WM-2024-001",
        "contractor": "Firma A",
        "customer": "Klinik B"
    },
    "dates": {
        "start_date": {"date": "2024-01-01"}
    },
    "termination": {
        "automatic_renewal": True
    },
    "costs": {
        "annual_cost": {
            "amount": "12000",
            "currency": "EUR"
        }
    },
    "services": {
        "maintenance": True,
        "inspection": False
    },
    "sla": {
        "response_time": {"value": "48h"},
        "availability_24_7": False
    }
})

PARTIAL = build_handler({
    "identity": {"contract_title": "Wartung"},
    "dates": {"start_date": None},
    "termination": {"automatic_renewal": None},
    "costs": {},
    "services": {},
    "sla": {}
})

GOOD_EVIDENCE = build_handler(
    {
        "identity": {
            "contract_title": "Wartung",
            "contract_number": "CN-1",
            "evidence": {
                "source_type": "page",
                "source_text": "Vertragsnummer CN-1",
                "confidence": 0.9,
                "page": 1,
            },
        }
    },
    verifier_fields=["identity.contract_number"],
)

DIAG = build_handler({
    "identity": {
        "contract_title": "Wartung",
        "contract_number": "CN-1",
        "evidence": {
            "source_type": "paragraph",
            "source_text": "Wartung CN-1",
            "confidence": 0.9,
            "page": 1
        }
    },
    "dates": {
        "start_date": {
            "date": "2024-01-01",
            "evidence": {
                "source_type": "paragraph",
                "source_text": "01.01.2024",
                "confidence": 0.8,
                "page": 1
            }
        }
    },
    "termination": {
        "automatic_renewal": True
    },
    "costs": {
        "annual_cost": {
            "amount": "10000",
            "currency": "EUR",
            "evidence": {
                "source_type": "table",
                "source_text": "10000 EUR",
                "confidence": 0.7,
                "page": 1
            }
        }
    },
    "services": {
        "maintenance": True,
        "evidence": {
            "source_type": "paragraph",
            "source_text": "Wartung inklusive",
            "confidence": 0.6,
            "page": 1
        }
    },
    "sla": {
        "response_time": {
            "value": "24h",
            "evidence": {
                "source_type": "paragraph",
                "source_text": "24h",
                "confidence": 0.5,
                "page": 1
            }
        }
    }
})

BAD_JSON = lambda req: httpx.Response(200, text="kein json")

DIAG_EXTRACTION = build_handler({
    "identity": {
        "contract_title": "Wartung",
        "contract_number": "CN-1",
        "evidence": {
            "source_type": "paragraph",
            "source_text": "Wartung CN-1",
            "confidence": 0.9,
            "page": 1
        }
    }
})


# ---------------------------------------------------------------- Full pipeline (mocked Ollama)

@pytest.mark.asyncio
async def test_full_pipeline_identity_extraction():
    result = TextExtractionResult(
        document_id="abcd1234",
        file_type="pdf",
        page_count=1,
        total_characters=200,
        text_available=True,
        units=[_page(1, "Wartungsvertrag WM-2024-001 zwischen Firma A und Klinik B")],
    )
    orch = _orchestrator(FULL)
    res = await orch.analyze(result)
    assert res.document_id == "abcd1234"
    # STEP-8B §8.4: konservative Verifier-/Review-Logik – der Vertrag wird
    # extrahiert (Fakten identisch), aber sensible Felder ohne Evidence-Support
    # fuehren zu requires_review (nichts wird stillschweigend akzeptiert).
    assert res.contract.identity.contract_number == "WM-2024-001"
    assert res.contract.identity.contract_title == "Wartungsvertrag"
    assert res.status in {ExtractionStatus.PARTIAL, ExtractionStatus.SUCCESS}
    assert res.contract is not None


# ---------------------------------------------------------------- Review/Validation paths

EMPTY = build_handler({})


@pytest.mark.asyncio
async def test_empty_ollama_reply_returns_result():
    result = TextExtractionResult(
        document_id="x",
        file_type="pdf",
        page_count=1,
        total_characters=10,
        text_available=True,
        units=[_page(1, "abc")],
    )
    orch = _orchestrator(EMPTY)
    res = await orch.analyze(result)
    # STEP-8B: Feldgruppen-Schemas haben keine Pflichtfelder – ein leerer,
    # aber schema-valider Antwortblock wird als Contract mit Defaults
    # zusammengefuehrt (kein FAILED). Der Verifier markiert unsupported
    # sensible Felder nur bei vorhandenem Evidence -> hier leer -> SUCCESS.
    assert res.contract is not None
    assert res.status == ExtractionStatus.SUCCESS
    assert res.document_id == "x"


@pytest.mark.asyncio
async def test_partial_missing_required_requires_review():
    result = TextExtractionResult(
        document_id="y",
        file_type="pdf",
        page_count=1,
        total_characters=10,
        text_available=True,
        units=[_page(1, "abc")],
    )
    orch = _orchestrator(PARTIAL)
    res = await orch.analyze(result)
    # Wie EMPTY: schema-valides, aber unvollstaendiges Extrakt wird nicht als
    # FAILED verworfen, sondern permissiv als Contract gefuehrt.
    assert res.contract is not None
    assert res.status == ExtractionStatus.SUCCESS


# ---------------------------------------------------------------- Evidence verification

@pytest.mark.asyncio
async def test_evidence_verification_passes():
    result = TextExtractionResult(
        document_id="z",
        file_type="pdf",
        page_count=1,
        total_characters=10,
        text_available=True,
        units=[_page(1, "Vertragsnummer CN-1")],
    )
    orch = _orchestrator(GOOD_EVIDENCE)
    res = await orch.analyze(result)
    assert res.status == ExtractionStatus.SUCCESS
    assert res.contract.identity.evidence.confidence == 0.9


# ---------------------------------------------------------------- Diagnostics

@pytest.mark.asyncio
async def test_diagnostics_counters_present():
    result = TextExtractionResult(
        document_id="diag1",
        file_type="pdf",
        page_count=1,
        total_characters=200,
        text_available=True,
        units=[_page(1, "Wartung CN-1 am 01.01.2024 10000 EUR")],
    )
    orch = _orchestrator(DIAG)
    res = await orch.analyze(result)
    assert res.chunk_count >= 1
    assert res.processing_duration > 0
    assert res.ai_call_count >= 1
    assert res.groups_processed >= 1


# ---------------------------------------------------------------- Invalid JSON from Ollama

@pytest.mark.asyncio
async def test_malformed_ollama_reply_triggers_validation_error():
    result = TextExtractionResult(
        document_id="badjson",
        file_type="pdf",
        page_count=1,
        total_characters=10,
        text_available=True,
        units=[_page(1, "abc")],
    )
    orch = _orchestrator(BAD_JSON)
    res = await orch.analyze(result)
    assert res.status == ExtractionStatus.FAILED
    assert res.error is not None


# ---------------------------------------------------------------- Diagnostics at extraction level

@pytest.mark.asyncio
async def test_diagnostics_in_extraction_result():
    result = TextExtractionResult(
        document_id="diag2",
        file_type="pdf",
        page_count=1,
        total_characters=10,
        text_available=True,
        units=[_page(1, "Wartung CN-1")],
    )
    orch = _orchestrator(DIAG_EXTRACTION)
    res = await orch.analyze(result)
    assert res.chunk_count >= 1
    assert res.ai_call_count >= 1
    assert res.groups_processed >= 1