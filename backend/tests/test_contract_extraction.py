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
from app.documents.extraction.schemas import (
    ExtractionUnit,
    SourceType,
    TextExtractionResult,
    UnitMethod,
)
from app.main import app as medflux_app
from app.models.enums import ExtractionStatus, ReviewFlag, ReviewStatus, ValidationStatus

from tests.helpers_group import build_handler, chat_reply

client = TestClient(medflux_app)
settings = Settings(_env_file=None)
MODEL = settings.ollama_model


# ---------------------------------------------------------------- Fixtures

def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _user_text(req: httpx.Request) -> str:
    return json.loads(req.content)["messages"][1]["content"]


def _page(index: int, text: str) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.PAGE, index=index, text=text, method=UnitMethod.TEXT)


def _para(index: int, text: str) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.PARAGRAPH, index=index, text=text, method=UnitMethod.TEXT)


def _table(index: int, text: str) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.TABLE, index=index, text=text, method=UnitMethod.TEXT)


def _extractor(
    handler: Callable[[httpx.Request], httpx.Response],
    _max_retries: int = 1,
    **settings_overrides,
) -> StructuredContractExtractor:
    s = _settings(**settings_overrides)
    ai = AIService(s, client=_client(handler))
    return StructuredContractExtractor(ai, s, max_retries=_max_retries)


FULL = {
    "identity": {
        "contract_title": "Wartungsvertrag CT",
        "contract_number": "WM-2024-001",
        "contract_type": "maintenance",
        "supplier": "Siemens Healthineers",
        "customer": "Klinikum Mitte",
    },
    "equipment": [
        {"device_name": "CT-Scanner", "manufacturer": "Siemens", "model": "Somatom go.Top"}
    ],
    "dates": {
        "start_date": {"date": "2024-01-01", "condition": None, "requires_review": False},
        "end_date": {"date": "2026-12-31", "condition": None, "requires_review": False},
        "duration": {"value": 36, "unit": "months"},
    },
    "termination": {
        "cancellation_period": {"value": 6, "unit": "months"},
        "automatic_renewal": True,
        "renewal_period": {"value": 12, "unit": "months"},
    },
    "costs": {
        "default_currency": "EUR",
        "annual_cost": {"amount": 24500.0, "currency": "EUR", "period": "annual"},
        "monthly_cost": {"amount": 2000.0, "currency": "EUR", "period": "monthly"},
    },
    "payment": {"payment_terms": "30 Tage netto", "billing_interval": "annual"},
    "services": {"included_services": ["Wartung", "Reparatur"], "repair": True},
    "sla": {
        "response_time": {"value": 4, "unit": "hours", "original_text": "Reaktionszeit 4 Stunden"}
    },
}


def _json_handler(content: dict) -> Callable[[httpx.Request], httpx.Response]:
    body = json.dumps(content, ensure_ascii=False)
    return lambda req: chat_reply(req, body)


# ---------------------------------------------------------------- Chunking

def test_chunk_units_deterministic_order_and_bound():
    units = [_page(1, "a" * 2500), _page(2, "b" * 2500), _page(3, "c" * 2500)]
    chunks = chunk_units(units, max_chars=4000)
    assert len(chunks) == 3
    assert chunks[0].unit_refs[0].index == 1
    assert chunks[1].unit_refs[0].index == 2
    assert chunks[2].unit_refs[0].index == 3


def test_chunk_single_oversized_unit_not_split():
    unit = _page(1, "x" * 9000)
    chunks = chunk_units([unit], max_chars=1000)
    assert len(chunks) == 1
    assert chunks[0].unit_refs[0].index == 1


# ---------------------------------------------------------------- Valide Extraktion

@pytest.mark.asyncio
async def test_valid_structured_extraction():
    ex = _extractor(build_handler(FULL))
    res = await ex.extract([_page(1, "Wartungsvertrag")])
    assert res.status == ExtractionStatus.SUCCESS
    assert res.prompt_version == "contract_extraction_v1"
    assert res.chunk_count == 1
    c = res.contract
    assert c.identity.contract_number == "WM-2024-001"
    assert c.identity.supplier == "Siemens Healthineers"
    assert c.costs.annual_cost.amount == 24500.0
    assert c.costs.annual_cost.period == "annual"
    assert c.termination.renewal_period.value == 12


@pytest.mark.asyncio
async def test_extraction_sends_thinking_disabled_and_token_budget():
    captured: dict = {}
    handler = build_handler(FULL)

    def wrap(req: httpx.Request) -> httpx.Response:
        data = json.loads(req.content)
        captured.setdefault("think", data.get("think"))
        captured.setdefault("num_predict", data["options"]["num_predict"])
        assert data["stream"] is False
        return handler(req)

    ex = _extractor(wrap)
    await ex.extract([_page(1, "Vertrag")])
    assert captured["think"] is False
    assert captured["num_predict"] == _settings().ai_extraction_max_tokens


# ---------------------------------------------------------------- Null / fehlende Werte

EMPTY = {"identity": {}, "equipment": [], "dates": {}, "termination": {},
         "costs": {}, "payment": {}, "services": {}, "sla": {}}


@pytest.mark.asyncio
async def test_missing_fields_become_null():
    ex = _extractor(build_handler(EMPTY, verifier_fields=[]))
    res = await ex.extract([_page(1, "Kurz")])
    c = res.contract
    assert c.identity.supplier is None
    assert c.identity.contract_number is None
    assert c.costs.annual_cost is None
    assert c.dates.start_date is None
    assert c.identity.supplier != "nicht gefunden"
    assert c.identity.supplier != "unknown"


# ---------------------------------------------------------------- Ereignisbasiert / Daten

@pytest.mark.asyncio
async def test_event_based_contract_start():
    contract = {"dates": {
        "start_date": {"date": None, "condition": "Übergabedatum", "requires_review": True}}}
    ex = _extractor(build_handler(contract))
    res = await ex.extract([_page(1, "Vertragsbeginn: Übergabedatum")])
    fd = res.contract.dates.start_date
    assert fd.date is None
    assert fd.condition == "Übergabedatum"
    assert fd.requires_review is True


@pytest.mark.asyncio
async def test_automatic_renewal_and_cancellation_period():
    contract = {"termination": {
        "cancellation_period": {"value": 6, "unit": "months"},
        "automatic_renewal": True,
        "renewal_period": {"value": 12, "unit": "months"},
    }}
    ex = _extractor(build_handler(contract))
    res = await ex.extract([_page(1, "Kündigung 6 Monate, Verlängerung 12 Monate")])
    t = res.contract.termination
    assert t.cancellation_period.value == 6
    assert t.automatic_renewal is True
    assert t.renewal_period.value == 12


# ---------------------------------------------------------------- Geld

@pytest.mark.asyncio
async def test_multiple_monetary_amounts_and_semantic_classification():
    contract = {"costs": {
        "default_currency": "EUR",
        "annual_cost": {"amount": 10000.0, "currency": "EUR", "period": "annual"},
        "one_time_cost": {"amount": 5000.0, "currency": "EUR", "period": "once"},
        "total_contract_value": {"amount": 35000.0, "currency": "EUR", "period": "total"},
    }}
    ex = _extractor(build_handler(contract))
    res = await ex.extract([_page(1, "Kosten")])
    costs = res.contract.costs
    assert costs.annual_cost.amount == 10000.0
    assert costs.one_time_cost.amount == 5000.0
    assert costs.total_contract_value.amount == 35000.0
    assert costs.monthly_cost is None


# ---------------------------------------------------------------- Geräte / Belege

@pytest.mark.asyncio
async def test_multiple_devices():
    contract = {"equipment": [
        {"device_name": "CT", "manufacturer": "Siemens"},
        {"device_name": "MRT", "manufacturer": "Philips"},
    ]}
    ex = _extractor(build_handler(contract))
    res = await ex.extract([_page(1, "Geräte")])
    assert len(res.contract.equipment) == 2
    assert res.contract.equipment[0].device_name == "CT"


@pytest.mark.asyncio
async def test_pdf_page_evidence():
    contract = {"identity": {
        "contract_number": "WM-100",
        "evidence": {
            "page": 3, "source_type": "page", "paragraph_index": None,
            "table_index": None, "source_text": "Vertrags-Nr.: WM-100",
            "confidence": 0.95, "requires_review": False,
        }}}
    ex = _extractor(build_handler(contract, verifier_fields=[]),
                    ai_run_semantic_verification=False)
    res = await ex.extract([_page(1, "Seite 1"), _page(3, "Vertrags-Nr.: WM-100)")])
    ev = res.contract.identity.evidence
    assert ev.page == 3
    assert ev.source_type == "page"
    assert ev.confidence == 0.95
    assert ev.extraction_method.value == "ai"


@pytest.mark.asyncio
async def test_docx_source_evidence_no_fake_page():
    contract = {"identity": {
        "contract_number": "WM-200",
        "evidence": {
            "page": None, "source_type": "paragraph",
            "paragraph_index": 4, "source_text": "Vertrags-Nr.: WM-200",
            "confidence": 0.9,
        }}}
    ex = _extractor(build_handler(contract, verifier_fields=[]),
                    ai_run_semantic_verification=False)
    res = await ex.extract([_para(4, "Vertrags-Nr.: WM-200")])
    ev = res.contract.identity.evidence
    assert ev.page is None
    assert ev.source_type == "paragraph"
    assert ev.paragraph_index == 4
    assert ev.table_index is None


# ---------------------------------------------------------------- Confidence / Review

@pytest.mark.asyncio
async def test_low_confidence_sets_review():
    contract = {
        "identity": {"supplier": "Ziehm", "evidence": {
            "page": None, "source_type": "paragraph", "paragraph_index": 2,
            "source_text": "Ziehm Imaging GmbH", "confidence": 0.4,
            "requires_review": True}},
    }
    ex = _extractor(build_handler(contract, verifier_fields=[]),
                    ai_run_semantic_verification=False)
    res = await ex.extract([_para(2, "Ziehm Imaging GmbH")])
    assert res.requires_review is True
    assert res.contract.review.requires_manual_review is True


@pytest.mark.asyncio
async def test_invalid_confidence_causes_review():
    # Ungültige Confidence (1.7) -> Group-Validierung schlägt fehl -> Feld fehlt + Prüfung
    contract = {"identity": {"evidence": {"confidence": 1.7}}}
    ex = _extractor(build_handler(contract, verifier_fields=[]),
                    ai_run_semantic_verification=False)
    res = await ex.extract([_page(1, "x")])
    assert res.status != ExtractionStatus.SUCCESS
    assert res.contract is not None
    assert res.contract.identity.evidence is None or res.requires_review


@pytest.mark.asyncio
async def test_invalid_enum_causes_review():
    # contract_type 'not-a-real-type' -> Group-Validierung der identity_equipment
    # schlägt fehl -> identity fehlt -> Prüfung
    contract = {"identity": {"contract_type": "not-a-real-type"}}
    ex = _extractor(build_handler(contract, verifier_fields=[]),
                    ai_run_semantic_verification=False)
    res = await ex.extract([_page(1, "x")])
    assert res.contract is not None
    assert res.contract.identity.contract_type.value == "unknown" or res.requires_review


# ---------------------------------------------------------------- JSON-Fehler

@pytest.mark.asyncio
async def test_invalid_json_retries_then_fails_per_group():
    calls: list[str] = []
    base = build_handler(FULL)

    def handler(req: httpx.Request) -> httpx.Response:
        data = json.loads(req.content)
        system = data["messages"][0]["content"]
        if "Identität & Geräte" in system:
            calls.append(system)
            return chat_reply(req, "Das ist kein JSON")  # immer ungültig
        return base(req)

    ex = _extractor(handler, _max_retries=1)
    res = await ex.extract([_page(1, "x")])
    # identity_equipment scheitert, andere Gruppen gelingen -> PARTIAL
    assert res.status == ExtractionStatus.PARTIAL
    assert res.contract is not None
    # kontrollierter Retry: genau (max_retries + 1) ident-Aufrufe
    assert len(calls) == 2
    assert "WICHTIG" in calls[1]


@pytest.mark.asyncio
async def test_malformed_json_with_prose_fallback():
    raw = "Hier etwas Prosa.\n" + json.dumps(FULL, ensure_ascii=False) + "\nEnde."

    def handler(req: httpx.Request) -> httpx.Response:
        data = json.loads(req.content)
        system = data["messages"][0]["content"]
        if "Identität & Geräte" in system or "Laufzeit & Kündigung" in system:
            return chat_reply(req, raw)
        return build_handler(FULL)(req)

    ex = _extractor(handler)
    res = await ex.extract([_page(1, "x")])
    assert res.contract is not None
    assert res.contract.identity.contract_number == "WM-2024-001"


# ---------------------------------------------------------------- Fehler (KI)

@pytest.mark.asyncio
async def test_ai_unavailable_clean_german():
    def conn(req):
        raise httpx.ConnectError("refused", request=req)

    ex = _extractor(conn)
    res = await ex.extract([_page(1, "x")])
    assert res.status == ExtractionStatus.FAILED
    assert res.requires_review is True
    assert res.contract is None


@pytest.mark.asyncio
async def test_ai_timeout_clean_german():
    def to(req):
        raise httpx.ConnectTimeout("timeout", request=req)

    ex = _extractor(to)
    res = await ex.extract([_page(1, "x")])
    assert res.status == ExtractionStatus.FAILED
    assert res.contract is None


@pytest.mark.asyncio
async def test_model_missing_clean_german():
    def missing(req):
        return httpx.Response(404, json={"error": "model not found"})

    ex = _extractor(missing)
    res = await ex.extract([_page(1, "x")])
    assert res.status == ExtractionStatus.FAILED
    assert res.contract is None


# ---------------------------------------------------------------- Multi-Chunk / Merge

@pytest.mark.asyncio
async def test_multi_chunk_extraction_and_null_merge():
    # Zwei Chunks: Chunk 1 hat alle Infos, Chunk 2 liefert leere Gruppen.
    # Späterer null darf zuverlässige frühere Daten nicht überschreiben.
    small = _settings(ai_max_chunk_characters=300)
    responses = iter([FULL, EMPTY])
    base_full = build_handler(FULL)
    base_empty = build_handler(EMPTY, verifier_fields=[])

    def handler(req: httpx.Request) -> httpx.Response:
        data = json.loads(req.content)
        system = data["messages"][0]["content"]
        text = data["messages"][1]["content"]
        if "unabhängiger Prüfer" in system:
            return base_full(req)
        is_chunk1 = "Abschnitt 1" in text
        return base_full(req) if is_chunk1 else base_empty(req)

    ai = AIService(small, client=_client(handler))
    ex = StructuredContractExtractor(ai, small)
    units = [_page(1, "Sehr langer Vertragstext " * 50), _page(2, "Weiterer Text " * 50)]
    res = await ex.extract(units)
    assert res.chunk_count == 2
    c = res.contract
    assert c.identity.contract_number == "WM-2024-001"
    assert c.costs.annual_cost.amount == 24500.0
    assert len(c.equipment) == 1


@pytest.mark.asyncio
async def test_merge_conflict_sets_review():
    # Zwei Chunks liefern unterschiedlichen supplier -> Konflikt -> Review
    c1 = {"identity": {"supplier": "Siemens"}}
    c2 = {"identity": {"supplier": "GE Healthcare"}}
    b1 = build_handler(c1, verifier_fields=[])
    b2 = build_handler(c2, verifier_fields=[])

    def handler(req: httpx.Request) -> httpx.Response:
        data = json.loads(req.content)
        text = data["messages"][1]["content"]
        if "Abschnitt 1" in text:
            return b1(req)
        return b2(req)

    small = _settings(ai_max_chunk_characters=300)
    ai = AIService(small, client=_client(handler))
    ex = StructuredContractExtractor(ai, small)
    units = [_page(1, "A " * 100), _page(2, "B " * 100)]
    res = await ex.extract(units)
    # Alle Gruppen merge-in: erster Wert bleibt, Konflikt ist gespeichert
    assert res.contract is not None
    assert res.contract.identity.supplier in ("Siemens", "GE Healthcare")


@pytest.mark.asyncio
async def test_merge_preserves_multiple_devices_across_chunks():
    c1 = {"equipment": [{"device_name": "CT", "manufacturer": "Siemens"}]}
    c2 = {"equipment": [{"device_name": "MRT", "manufacturer": "Philips"}]}
    b1 = build_handler(c1, verifier_fields=[])
    b2 = build_handler(c2, verifier_fields=[])

    def handler(req: httpx.Request) -> httpx.Response:
        data = json.loads(req.content)
        text = data["messages"][1]["content"]
        return b1(req) if "Abschnitt 1" in text else b2(req)

    small = _settings(ai_max_chunk_characters=300)
    ai = AIService(small, client=_client(handler))
    ex = StructuredContractExtractor(ai, small)
    units = [_page(1, "A " * 100), _page(2, "B " * 100)]
    res = await ex.extract(units)
    assert len(res.contract.equipment) == 2


# ---------------------------------------------------------------- Kein Text

@pytest.mark.asyncio
async def test_no_text_analysis_fails_clearly():
    ex = _extractor(build_handler(FULL))
    res = await ex.extract([_page(1, "")])
    assert res.status == ExtractionStatus.FAILED
    assert res.error == "Für dieses Dokument wurde kein Text extrahiert – eine Analyse ist nicht möglich."


# ---------------------------------------------------------------- Orchestrator

class _StubExtraction:
    def __init__(self, by_id: dict[str, TextExtractionResult]) -> None:
        self._by_id = by_id

    def extract(self, document_id: str):
        return self._by_id.get(document_id)


def _orchestrator(handler) -> ContractAnalysisOrchestrator:
    ai = AIService(settings, client=_client(handler))
    return ContractAnalysisOrchestrator(ai_service=ai, settings=settings)


@pytest.mark.asyncio
async def test_orchestrator_passes_document_id():
    orch = _orchestrator(build_handler(FULL))
    result = TextExtractionResult(
        document_id="abcd1234",
        file_type="pdf",
        page_count=1,
        total_characters=10,
        text_available=True,
        units=[_page(1, "Vertrag")],
    )
    res = await orch.analyze(result)
    assert res.document_id == "abcd1234"
    assert res.status == ExtractionStatus.SUCCESS
    assert res.contract.identity.contract_number == "WM-2024-001"


# ---------------------------------------------------------------- API-Endpunkt

def test_analyze_api_success(monkeypatch):
    result = TextExtractionResult(
        document_id="deadbeef",
        file_type="pdf",
        page_count=1,
        total_characters=9,
        text_available=True,
        units=[_page(1, "Vertrag")],
    )
    orch = _orchestrator(build_handler(FULL))
    monkeypatch.setattr(documents_module, "_extraction_service", _StubExtraction({"deadbeef": result}))
    monkeypatch.setattr(documents_module, "_analysis_service", orch)

    r = client.post("/api/documents/deadbeef/analyze")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["contract"]["identity"]["contract_number"] == "WM-2024-001"
    assert body["prompt_version"] == "contract_extraction_v1"


def test_analyze_api_document_not_found(monkeypatch):
    monkeypatch.setattr(documents_module, "_extraction_service", _StubExtraction({}))
    r = client.post("/api/documents/unknown1/analyze")
    assert r.status_code == 404
    assert r.json()["detail"] == "Dokument nicht gefunden."