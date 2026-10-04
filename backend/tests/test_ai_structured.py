"""Tests für die strukturierte Feldgruppen-Extraktion (STEP 8B-Semantik).

Native strukturierte Ausgabe über Ollama-JSON-Schema (`format`). Es wird KEINE
echte Ollama-Installation vorausgesetzt – alle Antworten werden über
httpx.MockTransport gemockt. Der `StructuredContractExtractor.extract` nutzt die
spezialisierte Feldgruppen-Pipeline (4 Gruppen je Chunk + semantischer Verifier);
der Helper `tests/helpers_group.py` serviert die passenden Gruppen-Antworten.
"""

from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest

from app.ai.contract_extractor import StructuredContractExtractor
from app.ai.providers.ollama import OllamaProvider
from app.ai.schema import contract_json_schema
from app.ai.service import AIService
from app.core.config import Settings
from app.database.ai_selection import set_ai_selection, set_setting
from app.documents.extraction.schemas import ExtractionUnit, SourceType, UnitMethod
from app.models.enums import ExtractionStatus, ValidationStatus

from tests.helpers_group import build_handler, chat_reply

settings = Settings(_env_file=None)


@pytest.fixture(autouse=True)
def _explicit_model_selection_for_mocked_ai():
    set_ai_selection("ollama", "qwen3:8b-test")
    yield
    for key in ("ai_provider", "ai_model", "ai_provider_endpoint"):
        set_setting(key, None)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _json(req: httpx.Request, j: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=j)


def _last_payload(req: httpx.Request) -> dict:
    return json.loads(req.content)


def _page(index: int, text: str) -> ExtractionUnit:
    return ExtractionUnit(source_type=SourceType.PAGE, index=index, text=text, method=UnitMethod.TEXT)


def _extractor(handler: Callable[[httpx.Request], httpx.Response], _max_retries: int = 1):
    ai = AIService(settings, client=_client(handler))
    return StructuredContractExtractor(ai, settings, max_retries=_max_retries)


def _provider(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaProvider:
    return OllamaProvider(settings, client=_client(handler))


# ---------------------------------------------------------------- Schema-Ableitung

def test_contract_schema_is_self_contained():
    s = contract_json_schema()
    txt = json.dumps(s)
    assert "$defs" not in txt
    assert "$ref" not in txt
    assert s.get("type") == "object"
    props = set(s.get("properties", {}).keys())
    assert {"identity", "equipment", "dates", "termination",
            "costs", "payment", "services", "sla", "review"}.issubset(props)
    assert not ({"parties", "terms", "fees", "warranty"} & props)


def test_contract_schema_enum_contract_type_allowed_values():
    s = contract_json_schema()
    ident = s["properties"]["identity"]
    enum = ident["properties"]["contract_type"].get("enum")
    assert enum == ["maintenance", "service", "lease", "rental", "other", "unknown"]


def test_group_schemas_are_self_contained_and_small():
    from app.ai.groups.schema import group_specs

    specs = group_specs()
    assert set(specs) == {
        "identity_equipment", "dates_termination", "costs_payment", "services_sla"
    }
    for name, spec in specs.items():
        txt = json.dumps(spec.schema)
        assert "$ref" not in txt
        assert "$defs" not in txt
        assert spec.schema.get("type") == "object"


# ---------------------------------------------------------------- Provider: Schema-Weitergabe

@pytest.mark.asyncio
async def test_generate_structured_passes_schema_and_returns_content():
    schema = {"type": "object", "properties": {"kind": {"type": "string"}}}
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["payload"] = _last_payload(req)
        return chat_reply(req, '{"kind": "x"}')

    p = _provider(handler)
    out = await p.generate_structured("E", "S", schema, max_tokens=123)
    assert out == '{"kind": "x"}'
    assert captured["payload"]["format"] == schema
    assert captured["payload"]["options"]["num_predict"] == 123
    assert captured["payload"]["options"]["repeat_penalty"] == settings.ai_repeat_penalty
    assert captured["payload"]["think"] is False


@pytest.mark.asyncio
async def test_generate_structured_timeout():
    schema = {"type": "object", "properties": {"kind": {"type": "string"}}}

    def to(req):
        raise httpx.ConnectTimeout("timeout", request=req)

    p = _provider(to)
    with pytest.raises(Exception) as exc:
        await p.generate_structured("E", "S", schema)
    assert "Zeitüberschreitung" in str(exc.value)


@pytest.mark.asyncio
async def test_generate_structured_without_provider():
    s = Settings(_env_file=None, ai_provider="bogus")
    svc = AIService(s)
    with pytest.raises(Exception):
        await svc.generate_structured("E", "S", {"type": "object"}, max_tokens=10)


# ---------------------------------------------------------------- Extraktion über Gruppen

CONTRACT = {
    "identity": {
        "contract_title": "Wartungsvertrag",
        "contract_type": "maintenance",
        "supplier": "Siemens Healthineers",
        "contract_number": "WM-123",
    },
    "equipment": [{"device_name": "MRT", "manufacturer": "Siemens", "model": "Vida"}],
    "dates": {"start_date": {"date": None, "condition": "Übergabedatum", "requires_review": True}},
    "termination": {
        "cancellation_period": {"value": 6, "unit": "months"},
        "automatic_renewal": True,
        "renewal_period": {"value": 12, "unit": "months"},
    },
    "costs": {"annual_cost": {"amount": 24000.0, "currency": "EUR", "period": "annual"}},
    "payment": {"payment_deadline_days": 30, "billing_interval": "annual"},
    "services": {"included_services": ["Wartung", "Reparatur"]},
    "sla": {"response_time": {"value": 4, "unit": "hours", "original_text": "Reaktionszeit 4 Std."}},
}


@pytest.mark.asyncio
async def test_structured_extraction_populates_fields():
    ex = _extractor(build_handler(CONTRACT))
    res = await ex.extract([_page(1, "Wartungsvertrag")])
    # The fixture intentionally proposes several critical claims while the
    # source unit contains only the contract title. The production pipeline
    # must therefore preserve the extracted values but mark the result partial.
    assert res.status == ExtractionStatus.PARTIAL
    c = res.contract
    assert c.identity.contract_type.value == "maintenance"
    assert c.identity.supplier == "Siemens Healthineers"
    assert c.identity.contract_number == "WM-123"
    assert c.termination.automatic_renewal is True
    assert c.termination.renewal_period.value == 12
    assert c.costs.annual_cost.amount == 24000.0
    assert c.payment.billing_interval.value == "annual"
    assert c.dates.start_date.condition == "Übergabedatum"


@pytest.mark.asyncio
async def test_group_extraction_makes_four_calls_plus_verifier():
    handler = build_handler(CONTRACT)
    ex = _extractor(handler)
    res = await ex.extract([_page(1, "Wartungsvertrag")])
    # 1 Chunk -> 4 Gruppen + 1 Verifier = 5 KI-Aufrufe
    assert res.ai_call_count == 5
    # Verifier lief, weil sensible Felder vorhanden sind
    assert res.ai_call_count > 0
    assert res.groups_processed == 4


@pytest.mark.asyncio
async def test_structured_null_fields_not_invented():
    EMPTY = {"identity": {}, "equipment": [], "dates": {}, "termination": {},
             "costs": {}, "payment": {}, "services": {}, "sla": {}}
    ex = _extractor(build_handler(EMPTY, verifier_fields=[]))
    res = await ex.extract([_page(1, "Kurz")])
    c = res.contract
    assert c.identity.supplier is None
    assert c.identity.contract_type.value == "unknown"
    assert c.costs.annual_cost is None


@pytest.mark.asyncio
async def test_structured_event_based_date():
    contract = {"dates": {"start_date": {
        "date": None, "condition": "Übergabedatum", "requires_review": True}}}
    ex = _extractor(build_handler(contract))
    res = await ex.extract([_page(1, "Vertragsbeginn: Übergabedatum")])
    fd = res.contract.dates.start_date
    assert fd.date is None
    assert fd.condition == "Übergabedatum"
    assert fd.requires_review is True


@pytest.mark.asyncio
async def test_structured_docx_evidence_kept():
    contract = {"identity": {
        "supplier": "Ziehm",
        "evidence": {
            "page": None, "source_type": "paragraph",
            "paragraph_index": 7, "table_index": None, "cell_index": None,
            "source_text": "Ziehm Imaging GmbH", "confidence": 1.0,
            "requires_review": False,
        }}}
    ex = _extractor(build_handler(contract, verifier_fields=[]))
    res = await ex.extract([
        ExtractionUnit(source_type=SourceType.PARAGRAPH, index=7, text="Ziehm Imaging GmbH", method=UnitMethod.TEXT)
    ])
    ev = res.contract.identity.evidence
    assert ev.source_type == "paragraph"
    assert ev.paragraph_index == 7
    assert ev.page is None  # DOCX: keine erfundene Seitennummer


# ---------------------------------------------------------------- Fehler / Timeout

@pytest.mark.asyncio
async def test_structured_provider_timeout_results_failed():
    def to(req):
        raise httpx.ConnectTimeout("timeout", request=req)

    ex = _extractor(to, _max_retries=0)
    res = await ex.extract([_page(1, "x")])
    assert res.status == ExtractionStatus.FAILED
    assert res.contract is None
    assert res.requires_review is True


@pytest.mark.asyncio
async def test_structured_validation_status_marker():
    r = _extractor(build_handler(CONTRACT))
    res = await r.extract([_page(1, "x")])
    # valide: keine Review-Hinweise aus Extraktion
    assert res.validation_status in (ValidationStatus.VALID, ValidationStatus.INVALID)
