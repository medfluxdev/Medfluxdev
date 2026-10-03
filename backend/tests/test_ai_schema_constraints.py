"""Tests für die Schema-Normalisierung der strukturierten Ausgabe.

Regression: Ollamas Decodierer lehnt jedes Teilschema ab, das nur
Annotationsschlüssel trägt und keinen strukturellen Typ. Pydantic rendert ein
`Any`-Feld genau so (`{"title": "Value"}`), wodurch der Aufruf previously mit
HTTP 500 `invalid JSON schema in format` abbrach. Ausschließlich Mock-Transports,
keine echte Ollama-Instanz nötig.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from app.ai.harness.v3 import (
    ProposedFactBatch,
    ProposedFactBatchOutput,
    VisualPageReading,
)
from app.ai.providers.ollama import OllamaProvider, _safe_error_category
from app.ai.schema import normalize_constrained_schema, pydantic_json_schema
from app.core.config import Settings


class _AnyFact(BaseModel):
    field: str
    value: Any = None


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, ollama_base_url="http://127.0.0.1:11434", **overrides)


# ------------------------------------------------------- Normalisierung selbst

def test_annotation_only_subschema_gets_permissive_type():
    raw = _AnyFact.model_json_schema()["properties"]["value"]
    assert "type" not in raw

    fixed = normalize_constrained_schema(_AnyFact.model_json_schema())
    value = fixed["properties"]["value"]
    assert set(value["type"]) == {
        "object", "array", "string", "number", "boolean", "null"
    }


def test_normalization_keeps_annotation_keywords():
    normalized = normalize_constrained_schema(ProposedFactBatch.model_json_schema())
    item = normalized["properties"]["facts"]["items"]["properties"]
    assert item["field"]["title"] == "Field"
    assert item["quote"]["default"] == ""
    assert item["applicability"]["enum"] == [
        "applicable",
        "alternative",
        "superseded",
        "unknown",
    ]


def test_normalization_preserves_optionals_enums_and_bounds():
    normalized = normalize_constrained_schema(ProposedFactBatch.model_json_schema())
    item = normalized["properties"]["facts"]["items"]["properties"]
    assert item["page"]["anyOf"] == [{"type": "integer"}, {"type": "null"}]
    assert item["confidence"]["anyOf"][0]["minimum"] == 0.0
    assert item["confidence"]["anyOf"][0]["maximum"] == 1.0
    assert normalized["properties"]["facts"]["items"]["required"] == ["field", "value"]


def test_normalization_inlines_references_for_ollama():
    normalized = normalize_constrained_schema(ProposedFactBatch.model_json_schema())
    rendered = json.dumps(normalized)
    assert "$ref" not in rendered
    assert "$defs" not in rendered


def test_normalization_does_not_mutate_input():
    raw = ProposedFactBatch.model_json_schema()
    before = json.dumps(raw, sort_keys=True)
    normalize_constrained_schema(raw)
    assert json.dumps(raw, sort_keys=True) == before


def test_normalization_reaches_nested_containers():
    schema = {
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"label": {"title": "Label"}},
                },
            }
        },
    }
    fixed = normalize_constrained_schema(schema)
    label = fixed["properties"]["rows"]["items"]["properties"]["label"]
    assert set(label["type"]) == {
        "object", "array", "string", "number", "boolean", "null"
    }


def test_equipment_name_cleaning_preserves_verbatim_multiword_name():
    from app.ai.harness.v3 import _clean_device_name

    source_name = "Exactrac X-Ray System"
    assert _clean_device_name(source_name) == source_name


def test_normalization_handles_any_of_alternatives():
    schema = {"anyOf": [{"title": "Free"}, {"type": "string"}]}
    fixed = normalize_constrained_schema(schema)
    assert set(fixed["anyOf"][0]["type"]) == {
        "object", "array", "string", "number", "boolean", "null"
    }


def test_already_constrained_schema_is_unchanged():
    raw = {"type": "object", "properties": {"x": {"type": "string", "title": "X"}}}
    assert normalize_constrained_schema(raw) == raw


def test_contract_schema_stays_inlinable_and_constrained():
    schema = pydantic_json_schema_from_contract()
    assert "$defs" not in schema
    normalized = normalize_constrained_schema(schema)
    assert json.dumps(normalized)


def pydantic_json_schema_from_contract() -> dict:
    from app.ai.schema import contract_json_schema

    return contract_json_schema()


# --------------------------------------------------------- Provider-Verhalten

@pytest.mark.asyncio
async def test_provider_normalizes_schema_before_sending_it():
    captured: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(req.content)
        return httpx.Response(
            200,
            text=json.dumps(
                {
                    "model": "minicpm",
                    "message": {"content": '[]'},
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 10,
                    "eval_count": 3,
                }
            ),
        )

    provider = OllamaProvider(_settings())
    provider._get_client = lambda: _client(handler)  # type: ignore[method-assign]

    raw = await provider.generate_request(
        "prompt", "system", ProposedFactBatchOutput.model_json_schema(), 128, 4096, None
    )

    assert json.loads(raw) == []
    sent_schema = captured["payload"]["format"]
    assert "$ref" not in json.dumps(sent_schema)
    assert "$defs" not in sent_schema
    assert sent_schema["type"] == "array"
    sent_value = sent_schema["items"]["properties"]["value"]
    assert sent_value["type"] == "string"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("body", "category"),
    [
        ("invalid JSON schema in format", "invalid_schema"),
        ("model requires more system memory", "insufficient_memory"),
        ("model runner has unexpectedly stopped", "model_runner_stopped"),
        ("unclassified provider failure", None),
    ],
)
@pytest.mark.asyncio
async def test_provider_reports_safe_error_category(body, category):
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500, json={"error": body}
        )

    provider = OllamaProvider(_settings())
    provider._get_client = lambda: _client(handler)  # type: ignore[method-assign]

    with pytest.raises(Exception) as excinfo:
        await provider.generate_request(
            "prompt", "system", ProposedFactBatch.model_json_schema(), 128, 4096, None
        )

    error = excinfo.value
    assert error.status_code == 500
    assert error.category == category
    assert body not in str(error)


def test_unknown_error_body_yields_no_category():
    assert _safe_error_category("something went wrong") is None
    assert _safe_error_category(None) is None


def test_known_error_bodies_map_to_categories():
    assert _safe_error_category('{"error":"invalid JSON schema in format"}') == "invalid_schema"
    assert _safe_error_category("model requires more system memory") == "insufficient_memory"
    assert (
        _safe_error_category("model runner has unexpectedly stopped")
        == "model_runner_stopped"
    )


@pytest.mark.parametrize(
    ("body", "category"),
    [
        ('{"error":"invalid JSON schema in format"}', "invalid_schema"),
        ("request timed out", "timeout"),
        ("CUDA out of memory", "insufficient_memory"),
        ("model runner has unexpectedly stopped", "model_runner_stopped"),
        ("unclassified provider response", "unknown"),
    ],
)
def test_harness_failure_categories_are_safe(body, category):
    from app.ai.exceptions import AIHTTPError, AITimeoutError

    if category == "timeout":
        error = AITimeoutError()
    elif category == "unknown":
        error = AIHTTPError(500, None)
    else:
        error = AIHTTPError(500, _safe_error_category(body))

    resolved = getattr(error, "category", None) or "unknown"
    assert resolved == category
    assert body not in str(error)


def test_ollama_raw_error_body_is_not_retained_in_safe_exception():
    from app.ai.exceptions import AIHTTPError

    raw = "invalid JSON schema in format; sensitive prompt fragment"
    error = AIHTTPError(500, _safe_error_category(raw))
    assert "sensitive prompt fragment" not in str(error)
    assert error.category == "invalid_schema"


def test_user_message_never_contains_raw_body():
    from app.ai.exceptions import AIHTTPError

    error = AIHTTPError(500, "invalid_schema")
    assert "invalid JSON schema" not in error.user_message
    assert "500" not in error.user_message


# ------------------------------------------------- Begrenzter Vision-Vertrag

def test_visual_reading_schema_bounds_every_list():
    schema = normalize_constrained_schema(VisualPageReading.model_json_schema())
    for name in ("visible_text", "layout_relations", "unresolved"):
        field = schema["properties"][name]
        assert field["maxItems"] == 12
        assert field["items"]["maxLength"] == 160


def test_visual_reading_rejects_overlong_fragment():
    with pytest.raises(Exception):
        VisualPageReading(page=1, visible_text=["x" * 161])


def test_visual_reading_rejects_too_many_fragments():
    with pytest.raises(Exception):
        VisualPageReading(page=1, visible_text=["x"] * 13)


def test_visual_reading_accepts_bounded_input():
    reading = VisualPageReading(
        page=1,
        visible_text=["Laufzeit 01.01.2025 - 31.12.2025"],
        layout_relations=["checkbox on page 1 is marked"],
        unresolved=["stamped date not legible"],
    )
    assert reading.page == 1
    assert len(reading.visible_text) == 1
    assert normalize_constrained_schema(VisualPageReading.model_json_schema())


# --------------------------------------------- Kontext-Budget des Harness

def test_effective_context_never_grows_past_operator_budget():
    from app.ai.harness.v3 import _effective_context

    # Ein ueberschaetzter Prompt darf das Kontextbudget nicht anheben.
    assert _effective_context(9000, 1800, 8192, 40960) == 8192
    assert _effective_context(7000, 3200, 8192, 40960) == 8192


def test_effective_context_stays_below_model_capacity():
    from app.ai.harness.v3 import _effective_context

    assert _effective_context(1000, 500, 8192, 4096) == 4096


def test_effective_context_can_grow_only_when_explicitly_allowed():
    from app.ai.harness.v3 import _effective_context

    assert _effective_context(9000, 1800, 8192, 40960, allow_growth=True) == 11312


def test_estimate_tokens_is_calibrated_and_pessimistic():
    from app.ai.harness.v3 import _estimate_tokens

    # Gemessen: deutscher Vertrags-Prompt ~3.2 Bytes/Token, real 5520 Tokens.
    assert _estimate_tokens("W" * 17849) >= 5520
    assert _estimate_tokens("") == 1


def test_output_budget_shrinks_instead_of_growing_context():
    from app.ai.harness.v3 import (
        _fits_output_budget,
        _shrunk_output_budget,
    )

    assert not _fits_output_budget(7054, 1800, 8192)
    shrunk = _shrunk_output_budget(7054, 8192)
    assert shrunk == 8192 - 7054 - 512
    assert _fits_output_budget(7054, shrunk, 8192)


def test_output_budget_never_drops_below_generation_floor():
    from app.ai.harness.v3 import _MIN_OUTPUT_TOKENS, _shrunk_output_budget

    assert _shrunk_output_budget(20000, 8192) == _MIN_OUTPUT_TOKENS


def test_image_reserve_consumes_the_output_budget():
    from app.ai.harness.v3 import _shrunk_output_budget

    assert _shrunk_output_budget(6000, 8192, image_reserve=1024) == 8192 - 6000 - 1024 - 512


def test_default_config_keeps_context_growth_disabled():
    settings = Settings(_env_file=None)
    assert settings.harness_allow_context_growth is False


# ------------------------------------- MiniCPM-Repr- und Equipment-Rettung

def test_python_repr_of_nested_model_is_parsed():
    from app.ai.harness.v3 import _parse_python_repr

    assert _parse_python_repr("Duration(days=30)") == {"days": 30}
    assert _parse_python_repr("Money(amount=12000.0, currency='EUR')") == {
        "amount": 12000.0,
        "currency": "EUR",
    }
    assert _parse_python_repr("Outer(inner=FlexibleDate(date='2029-06-03'))") == {
        "inner": {"date": "2029-06-03"}
    }
    assert _parse_python_repr("no repr here") is None
    assert _parse_python_repr("Broken(x") is None


def test_duration_repr_recovers_real_duration():
    from app.ai.harness.v3 import _normalize_duration_payload

    assert _normalize_duration_payload("Duration(days=30)") == {
        "value": 30,
        "unit": "days",
    }
    assert _normalize_duration_payload("Duration(months=48)") == {
        "value": 48,
        "unit": "months",
    }


def test_date_repr_recovers_iso_date():
    from app.ai.harness.v3 import _normalize_date_payload

    parsed = _normalize_date_payload("FlexibleDate(YYYY-MM-DD=2029-06-03)")
    assert parsed["date"] == "2029-06-03"


def test_incomplete_date_repr_is_rejected_not_silently_emptied():
    from app.ai.harness.v3 import _normalize_date_payload

    # Nur eine Jahreszahl ist kein Datum: nicht erfinden, sondern ablehnen.
    normalized = _normalize_date_payload("FlexibleDate(YYYY-MM-DD=1983)")
    assert not (isinstance(normalized, dict) and normalized.get("date"))
    assert not (isinstance(normalized, dict) and normalized.get("literal_value"))


def test_device_name_drops_table_cell_noise():
    from app.ai.harness.v3 import _clean_device_name

    assert _clean_device_name("OPTIS(TM) Mobile Next Imaging System | 1014932 | SN:") == (
        "OPTIS(TM) Mobile Next Imaging System"
    )
    assert _clean_device_name("  Impella(R) AIC System ") == "Impella(R) AIC System"
    assert _clean_device_name("1014932") == "1014932"


def test_equipment_is_derived_from_bound_title_only():
    from app.ai.harness.v3 import _equipment_from_title_evidence

    identity = _StubIdentity(
        contract_title="Rahmenvertrag Nr. RAV-00074 - OPTIS(TM) Mobile Next Imaging System",
        evidence=_StubSource(
            source_text="Rahmenvertrag Nr. RAV-00074 - OPTIS(TM) Mobile Next Imaging System"
        ),
    )
    derived = _equipment_from_title_evidence(_StubContract(identity=identity))
    assert derived is not None
    assert derived.device_name == "OPTIS(TM) Mobile Next Imaging System"
    assert derived.evidence is identity.evidence


def test_equipment_is_not_derived_without_bound_evidence():
    from app.ai.harness.v3 import _equipment_from_title_evidence

    identity = _StubIdentity(
        contract_title="Rahmenvertrag Nr. RAV-00074 - OPTIS(TM) Mobile",
        evidence=None,
    )
    assert _equipment_from_title_evidence(_StubContract(identity=identity)) is None


def test_equipment_is_not_derived_when_name_is_absent_from_the_source():
    from app.ai.harness.v3 import _equipment_from_title_evidence

    identity = _StubIdentity(
        contract_title="Rahmenvertrag Nr. RAV-00074 - Phantom Geraet",
        evidence=_StubSource(source_text="Rahmenvertrag Nr. RAV-00074"),
    )
    assert _equipment_from_title_evidence(_StubContract(identity=identity)) is None


class _StubSource:
    def __init__(self, source_text):
        self.source_text = source_text


class _StubIdentity:
    def __init__(self, contract_title, evidence):
        self.contract_title = contract_title
        self.evidence = evidence


class _StubContract:
    def __init__(self, identity):
        self.identity = identity
        self.equipment = []


# ------------------------------- Temporale Verifikation / Laufzeit-Ableitung

class _StubFact:
    def __init__(self, field, value, page):
        self.field = field
        self.value = value
        self.page = page


def test_duration_needs_a_matching_signal_on_its_own_page():
    from app.ai.harness.v3 import _temporal_signal_supported

    signals = [
        {"kind": "duration", "value": "3 Wochen", "page": 4,
         "quote": "Installation (Dauer i.d.R. 2-3 Wochen)"},
        {"kind": "duration", "value": "48 Monaten", "page": 2,
         "quote": "Der Vertrag hat eine Laufzeit von 48 Monaten"},
    ]
    ok = _StubFact("dates.duration", {"value": 48, "unit": "months"}, 2)
    assert _temporal_signal_supported(ok, signals) is True
    # Falsche Einheit auf derselben Seite: nicht akzeptieren.
    wrong_unit = _StubFact("dates.duration", {"value": 3, "unit": "days"}, 4)
    assert _temporal_signal_supported(wrong_unit, signals) is False
    # Richtiger Wert, aber auf einer anderen Seite: nicht akzeptieren.
    wrong_page = _StubFact("dates.duration", {"value": 48, "unit": "months"}, 4)
    assert _temporal_signal_supported(wrong_page, signals) is False


def test_date_needs_a_matching_date_signal():
    from app.ai.harness.v3 import _temporal_signal_supported

    signals = [{"kind": "date", "value": "03.06.2029", "page": 2, "quote": "bis 03.06.2029"}]
    good = _StubFact("dates.end_date", {"date": "2029-06-03"}, 2)
    assert _temporal_signal_supported(good, signals) is True
    invented = _StubFact("dates.end_date", {"date": "1983-01-01"}, 2)
    assert _temporal_signal_supported(invented, signals) is False


class _StubSignal:
    def __init__(self, kind, value, page, quote):
        self.kind = kind
        self.value = value
        self.page = page
        self.quote = quote


class _StubCanonicalPage:
    def __init__(self, page_number, text):
        self.page_number = page_number
        self.text = text


class _StubCanonical:
    def __init__(self, pages):
        self.pages = pages


class _StubDates:
    def __init__(self):
        self.duration = None
        self.evidence = None


class _StubDurationContract:
    def __init__(self):
        self.dates = _StubDates()
        self.identity = None
        self.equipment = []


def test_runtime_duration_is_derived_from_the_agreeing_literal_signal():
    from app.ai.harness.v3 import _duration_from_runtime_signal

    signals = [
        _StubSignal("duration", "48 Monaten", 2,
                    "Der Vertrag hat eine Laufzeit von 48 Monaten (nachfolgend Vertragszeitraum)."),
        _StubSignal("duration", "48 Monaten", 3,
                    "Verbrauchsmaterial fuer den Vertragszeitraum von 48 Monaten:"),
        _StubSignal("duration", "3 Wochen", 4,
                    "die Installation planen (Dauer i.d.R. 2-3 Wochen nach Vertragsabschluss"),
    ]
    pages = _StubCanonical([
        _StubCanonicalPage(2, "Der Vertrag hat eine Laufzeit von 48 Monaten (nachfolgend Vertragszeitraum)."),
        _StubCanonicalPage(3, "Verbrauchsmaterial fuer den Vertragszeitraum von 48 Monaten:"),
        _StubCanonicalPage(4, "die Installation planen (Dauer i.d.R. 2-3 Wochen nach Vertragsabschluss"),
    ])
    contract = _StubDurationContract()
    result = _duration_from_runtime_signal(contract, signals, _StubDocument(), pages)
    assert result is not None
    duration, evidence = result
    assert duration.value == 48
    assert str(duration.unit.value) == "months"
    # Die staerkere Laufzeit-Aussage ist die Quelle, nicht die Verbrauchsmaterial-Zeile.
    assert evidence.page == 2


def test_conflicting_runtime_durations_stay_unresolved():
    from app.ai.harness.v3 import _duration_from_runtime_signal

    signals = [
        _StubSignal("duration", "48 Monaten", 2, "Der Vertrag hat eine Laufzeit von 48 Monaten."),
        _StubSignal("duration", "24 Monaten", 3, "Der Vertrag hat eine Vertragslaufzeit von 24 Monaten."),
    ]
    pages = _StubCanonical([
        _StubCanonicalPage(2, "Der Vertrag hat eine Laufzeit von 48 Monaten."),
        _StubCanonicalPage(3, "Der Vertrag hat eine Vertragslaufzeit von 24 Monaten."),
    ])
    result = _duration_from_runtime_signal(
        _StubDurationContract(), signals, _StubDocument(), pages
    )
    assert result is None


def test_installation_lead_time_is_not_taken_as_the_contract_term():
    from app.ai.harness.v3 import _duration_from_runtime_signal

    signals = [
        _StubSignal("duration", "3 Wochen", 4,
                    "die Installation planen (Dauer i.d.R. 2-3 Wochen nach Vertragsabschluss)"),
    ]
    pages = _StubCanonical([
        _StubCanonicalPage(4, "die Installation planen (Dauer i.d.R. 2-3 Wochen nach Vertragsabschluss)"),
    ])
    result = _duration_from_runtime_signal(
        _StubDurationContract(), signals, _StubDocument(), pages
    )
    assert result is None


class _StubDocument:
    pages_blocks = {}
    blocks = []


# ------------------------------- Preis-Tabellen, Startbedingung, Lieferantenbeleg

_PRICE_PAGE_3 = """Abbott
(1.1) OPTIS Mobile Next Imaging System
Bezeichnung | Modell | Menge
OPTIS Mobile Next Imaging System |  | 
Anteilige Zahlung fuer Investitionsgut: | | EUR 12.000,00
Einzelkomponenten:
Bezeichnung | Modell | Menge | Preis pro Stueck | Kaufpreis
OPTIS Mobile zusaetzliches Install-Kit (Verkabelung ACR inkl. Material & Service fuer 1 HKL) | C408666 | 1 Stueck | EUR 9.500,00 | EUR 9.500,00
Kosten Einzelkomponenten: |  |  |  | EUR 9.500,00
(1.2) Verbrauchsmaterial fuer den Vertragszeitraum von 48 Monaten:
Bezeichnung | Modell | Abnahme gesamt | Preis pro Stueck
PressureWire X Kabelloser FFR-Druckmessdraht, 175cm | C12059 | 480 Stueck | Basispreis
"""

_PRICE_PAGE_5 = """Zwischen den Vertragsparteien wird vierteljaehrlich die Abnahmemenge ausgewertet.
Werden die unter paragraph 2, Punkt 1.2 vereinbarten Gesamtmengen fuer das Verbrauchsmaterial in der Vertragslaufzeit nicht erreicht, so hat die Klinik zum Ende der Vertragslaufzeit folgendes Wahlrecht:
Produkt | Ausgleichszahlung/Stueck Zielmengenverfehlung
PressureWire X Kabelloser FFR-Druckmessdraht, 175cm | EUR 180,00
Dragonfly OpStar OCT-Katheter Kit | EUR 200,00
"""


class _StubCostContract:
    def __init__(self):
        from app.models.contract import ContractIdentity, Costs

        self.costs = Costs()
        self.identity = ContractIdentity()
        self.equipment = []
        self.dates = None


def test_parties_clause_is_not_truncated_by_casefold_expansion():
    from app.ai.harness.v3 import _parties_clause

    # "Schanzenfeldstraße" casefolds to "Schanzenfeldstrasse" (+1 char). An
    # Index aus der casegefoldeten Kopie wuerde den Klauselanfang abschneiden.
    line = (
        "Abbott Medical GmbH Betriebsstätte Wetzlar Schanzenfeldstraße 2 35578 Wetzlar "
        "Abbott zwischen Abbott Medical GmbH Schanzenfeldstraße 2 und Klinik Nordwest"
    )
    clause = _parties_clause(line, "Abbott Medical GmbH")
    assert clause is not None
    assert clause.startswith("zwischen Abbott Medical GmbH")


def test_equipment_survives_a_repointed_identity_evidence_slot():
    from app.ai.harness.v3 import _equipment_from_title_evidence
    from app.models.evidence import SourceEvidence

    contract = _StubContract(
        identity=_StubIdentity(
            contract_title="Rahmenvertrag Nr. RAV-00074 - OPTIS Mobile Next Imaging",
            evidence=None,
        )
    )
    title_source = SourceEvidence(
        page=1,
        source_type="page",
        source_text="Rahmenvertrag Nr. RAV-00074 - OPTIS Mobile Next Imaging",
    )
    derived = _equipment_from_title_evidence(contract, title_source)
    assert derived is not None
    assert derived.device_name == "OPTIS Mobile Next Imaging"
    assert derived.evidence is title_source


def test_supplier_is_derived_from_the_contracting_parties_sentence():
    from app.ai.harness.v3 import _derive_supplier

    contract = _StubCostContract()
    page1 = (
        "Abbott Medical GmbH Betriebsstätte Wetzlar Schanzenfeldstraße 2 35578 Wetzlar "
        "T: +49 800 180 8192 www.abbott.com "
        "zwischen Abbott Medical GmbH Betriebsstätte Wetzlar Schanzenfeldstr. 2 35578 Wetzlar "
        "und Krankenhaus Nordwest GmbH Steinbacher Hohl 2-26 60488 Frankfurt"
    )
    pages = _StubCanonical([
        _StubCanonicalPage(1, "Rahmenvertrag Nr. RAV-00074 4 - OPTIS Mobile"),
        _StubCanonicalPage(2, page1),
    ])
    evidence = _derive_supplier(contract, pages, _StubDocument())
    assert evidence is not None
    assert contract.identity.supplier == "Abbott Medical GmbH"
    assert evidence.page == 2
    assert evidence.extraction_method.value == "programmatic"
    assert evidence.source_text.startswith("zwischen Abbott Medical GmbH")


def test_derived_supplier_never_overwrites_an_accepted_supplier():
    from app.ai.harness.v3 import _derive_supplier

    contract = _StubCostContract()
    contract.identity.supplier = "Klinik Nordwest GmbH"
    pages = _StubCanonical([
        _StubCanonicalPage(
            1, "zwischen Abbott Medical GmbH Wetzlar und Klinik Nordwest GmbH Frankfurt"
        ),
    ])
    assert _derive_supplier(contract, pages, _StubDocument()) is None
    assert contract.identity.supplier == "Klinik Nordwest GmbH"


def test_derived_supplier_never_picks_the_hospital_customer():
    from app.ai.harness.v3 import _derive_supplier

    contract = _StubCostContract()
    contract.identity.customer = "Krankenhaus Nordwest GmbH"
    pages = _StubCanonical([
        _StubCanonicalPage(
            1, "zwischen Abbott Medical GmbH Wetzlar und Krankenhaus Nordwest GmbH Frankfurt"
        ),
    ])
    evidence = _derive_supplier(contract, pages, _StubDocument())
    assert contract.identity.supplier == "Abbott Medical GmbH"
    assert "Nordwest" not in (contract.identity.supplier or "")
    assert evidence is not None


def test_derived_supplier_requires_a_literal_legal_form():
    from app.ai.harness.v3 import _derive_supplier

    contract = _StubCostContract()
    pages = _StubCanonical([
        _StubCanonicalPage(1, "Lieferant: Abbott Medical, Lieferadresse Frankfurt am Main."),
    ])
    assert _derive_supplier(contract, pages, _StubDocument()) is None
    assert not (contract.identity.supplier or "").strip()


def test_price_table_rows_are_read_literally():
    from app.ai.harness.v3 import _derive_costs_from_price_tables

    contract = _StubCostContract()
    pages = _StubCanonical([
        _StubCanonicalPage(3, _PRICE_PAGE_3),
        _StubCanonicalPage(5, _PRICE_PAGE_5),
    ])
    derived = _derive_costs_from_price_tables(contract, pages, _StubDocument())
    fields = {row["field"] for row in derived}

    assert contract.costs.one_time_cost.amount == 12000.0
    assert contract.costs.one_time_cost.currency == "EUR"
    assert contract.costs.one_time_cost.period == "once"
    assert contract.costs.setup_installation_cost.amount == 9500.0
    assert "costs.one_time_cost" in fields
    assert "costs.setup_installation_cost" in fields

    # Die Summenzeile wiederholt 9.500,00 - sie darf keinen zweiten Betrag erzeugen.
    amounts = [
        row["amount"] for row in derived
        if row["field"] == "costs.setup_installation_cost"
    ]
    assert amounts == [9500.0]


def test_explicit_contiguous_year_price_rows_are_recovered_with_page_evidence():
    from app.ai.harness.v3 import _explicit_yearly_price_schedule

    text = (
        "Waehrung: EUR\n"
        "*Jahr 1: Gesamtpreis Netto | 52.500,00\n"
        "Jahr 2: Gesamtpreis Netto | 52.500,00\n"
        "Jahr 3: Gesamtpreis Netto | 52.500,00\n"
        "Jahr 4: Gesamtpreis Netto | 52.500,00\n"
    )
    result = _explicit_yearly_price_schedule(
        _StubCanonical([_StubCanonicalPage(1, text)]), _StubDocument()
    )

    assert result is not None
    page, rows, evidence = result
    assert page == 1
    assert [row.period_index for row in rows] == [1, 2, 3, 4]
    assert [row.amount.amount for row in rows] == [52500.0] * 4
    assert all(row.amount.currency == "EUR" for row in rows)
    assert evidence.page == 1
    assert "Jahr 4" in evidence.source_text


def test_explicit_year_price_rows_reject_gaps_or_missing_currency():
    from app.ai.harness.v3 import _explicit_yearly_price_schedule

    gapped = _StubCanonical([_StubCanonicalPage(1, (
        "EUR\nJahr 1: Gesamtpreis Netto | 52.500,00\n"
        "Jahr 3: Gesamtpreis Netto | 52.500,00\n"
    ))])
    no_currency = _StubCanonical([_StubCanonicalPage(1, (
        "Jahr 1: Gesamtpreis Netto | 52.500,00\n"
        "Jahr 2: Gesamtpreis Netto | 52.500,00\n"
    ))])

    assert _explicit_yearly_price_schedule(gapped, _StubDocument()) is None
    assert _explicit_yearly_price_schedule(no_currency, _StubDocument()) is None


def test_price_tables_never_invent_a_recurring_budget():
    from app.ai.harness.v3 import _derive_costs_from_price_tables

    contract = _StubCostContract()
    pages = _StubCanonical([
        _StubCanonicalPage(3, _PRICE_PAGE_3),
        _StubCanonicalPage(5, _PRICE_PAGE_5),
    ])
    _derive_costs_from_price_tables(contract, pages, _StubDocument())
    # Der Vertrag hat keine wiederkehrende Rate: nie auffuellen.
    assert contract.costs.annual_cost is None
    assert contract.costs.monthly_cost is None
    assert contract.costs.quarterly_cost is None
    assert contract.costs.total_contract_value is None


def test_conditional_compensation_prices_keep_label_and_condition():
    from app.ai.harness.v3 import _derive_costs_from_price_tables

    contract = _StubCostContract()
    pages = _StubCanonical([
        _StubCanonicalPage(3, _PRICE_PAGE_3),
        _StubCanonicalPage(5, _PRICE_PAGE_5),
    ])
    _derive_costs_from_price_tables(contract, pages, _StubDocument())
    labels = {row.label: row.amount.amount for row in contract.costs.variable_charges}
    assert labels == {
        "PressureWire X Kabelloser FFR-Druckmessdraht, 175cm": 180.0,
        "Dragonfly OpStar OCT-Katheter Kit": 200.0,
    }
    for row in contract.costs.variable_charges:
        assert row.unit == "per_piece"
        assert row.condition and "nicht erreicht" in row.condition


def test_derived_cost_evidence_is_page_bound():
    from app.ai.harness.v3 import _derive_costs_from_price_tables

    contract = _StubCostContract()
    pages = _StubCanonical([
        _StubCanonicalPage(3, _PRICE_PAGE_3),
        _StubCanonicalPage(5, _PRICE_PAGE_5),
    ])
    derived = _derive_costs_from_price_tables(contract, pages, _StubDocument())
    for row in derived:
        assert row["page"] in (3, 5)
        assert row["evidence"] is not None
        assert row["evidence"]["page"] == row["page"]
        assert "12.000,00" in row["evidence"]["source_text"] or "9.500,00" in row[
            "evidence"
        ]["source_text"] or "180,00" in row["evidence"]["source_text"] or "200,00" in row[
            "evidence"
        ]["source_text"]


def test_existing_cost_value_is_not_overwritten():
    from app.ai.harness.v3 import _derive_costs_from_price_tables
    from app.models.values import Money

    contract = _StubCostContract()
    contract.costs.one_time_cost = Money(amount=999.0, currency="EUR", period="once")
    pages = _StubCanonical([_StubCanonicalPage(3, _PRICE_PAGE_3)])
    _derive_costs_from_price_tables(contract, pages, _StubDocument())
    assert contract.costs.one_time_cost.amount == 999.0


def test_start_condition_is_read_from_the_trigger_clause():
    from app.ai.harness.v3 import _derive_start_condition

    class _Dates:
        start_condition = None

    class _C:
        dates = _Dates()

    page_text = (
        "paragraph 1 Allgemeines\n"
        "Der Vertrag hat eine Laufzeit von 48 Monaten.\n"
        "Er startet an dem Tag der Installation und Inbetriebnahme.\n"
    )
    pages = _StubCanonical([_StubCanonicalPage(2, page_text)])
    result = _derive_start_condition(_C(), pages)
    assert result is not None
    page_number, clause = result
    assert page_number == 2
    assert "Installation" in clause and "Inbetriebnahme" in clause
    assert "48 Monaten" not in clause


def test_start_condition_is_not_invented_without_a_trigger():
    from app.ai.harness.v3 import _derive_start_condition

    class _Dates:
        start_condition = None

    class _C:
        dates = _Dates()

    pages = _StubCanonical([
        _StubCanonicalPage(1, "Der Vertrag beginnt mit der Unterschrift beider Parteien.")
    ])
    assert _derive_start_condition(_C(), pages) is None


def test_supplier_evidence_prefers_an_explicit_legal_form_mention():
    from app.ai.harness.v3 import _bind_supplier_evidence

    contract = _StubCostContract()
    contract.identity.supplier = "Abbott Medical GmbH"
    title_line = "Rahmenvertrag Nr. RAV-00074 - OPTIS Mobile Next Imaging System"
    letterhead = (
        "Abbott Medical GmbH Betriebsstaette Wetzlar Schanzenfeldstrasse 2 35578 Wetzlar"
    )
    pages = _StubCanonical([
        _StubCanonicalPage(1, f"OPTIS Mobile Next Imaging System\n{title_line}"),
        _StubCanonicalPage(6, f"{letterhead}\nRahmenvertrag Nr. RAV-00074"),
    ])
    evidence = _bind_supplier_evidence(contract, pages, _StubDocument())
    assert evidence is not None
    assert "Abbott Medical GmbH" in evidence.source_text
    assert "GmbH" in evidence.source_text
    # Der Titelbeleg nennt den Lieferanten nicht und wird ersetzt.
    assert title_line not in evidence.source_text


def test_supplier_evidence_prefers_the_contracting_parties_clause():
    from app.ai.harness.v3 import _bind_supplier_evidence

    contract = _StubCostContract()
    contract.identity.supplier = "Abbott Medical GmbH"
    noisy = (
        "AbbottN Betriebs Schanze 35578V T: +49 8 www.ab Abbott zwischen "
        "Abbott Medical GmbH Betriebsstaette Wetzlar Schanzenfeldstr. 2 35578 Wetzlar "
        "und Krankenhaus Nordwest GmbH Steinbacher Hohl 2-26 60488 Frankfurt"
    )
    pages = _StubCanonical([
        _StubCanonicalPage(1, f"OPTIS Mobile\nRahmenvertrag Nr. RAV-00074\n{noisy}"),
    ])
    evidence = _bind_supplier_evidence(contract, pages, _StubDocument())
    assert evidence is not None
    # Auf den Vertragsparteisatz zugeschnitten, OCR-Rauschen abgeschnitten.
    assert evidence.source_text.startswith("zwischen Abbott Medical GmbH")
    assert evidence.source_text.endswith("60488 Frankfurt")
    assert "www.ab Abbott" not in evidence.source_text
    assert evidence.page == 1


def test_supplier_evidence_is_kept_when_it_already_names_the_supplier():
    from app.ai.harness.v3 import _bind_supplier_evidence
    from app.models.evidence import SourceEvidence

    contract = _StubCostContract()
    contract.identity.supplier = "Abbott Medical GmbH"
    line = "Rahmenvertrag Nr. RAV-00074 zwischen Abbott Medical GmbH und der Klinik"
    contract.identity.evidence = SourceEvidence(
        page=1, source_type="page", source_text=line
    )
    pages = _StubCanonical([_StubCanonicalPage(1, line)])
    assert _bind_supplier_evidence(contract, pages, _StubDocument()) is None


def test_supplier_evidence_requires_a_legal_form():
    from app.ai.harness.v3 import _bind_supplier_evidence

    contract = _StubCostContract()
    contract.identity.supplier = "Abbott Medical GmbH"
    pages = _StubCanonical([
        _StubCanonicalPage(1, "Die Klinik und Abbott Medical zusammen nachfolgend Vertragsparteien")
    ])
    assert _bind_supplier_evidence(contract, pages, _StubDocument()) is None


def test_primary_contract_heading_wins_over_later_standard_terms_heading():
    from types import SimpleNamespace
    from app.ai.harness.v3 import _primary_contract_title

    canonical = SimpleNamespace(pages=[
        SimpleNamespace(page_number=1, text="Cover"),
        SimpleNamespace(page_number=2, text="SERVICEVERTRAG RADIOSURGERY"),
        SimpleNamespace(page_number=18, text="Allgemeine Geschäftsbedingungen"),
    ])
    document = SimpleNamespace(pages_blocks={
        1: [SimpleNamespace(text="Angebot Nr. 100", reading_order=0, source_type="page")],
        2: [SimpleNamespace(text="SERVICEVERTRAG RADIOSURGERY", reading_order=0, source_type="page")],
        18: [SimpleNamespace(text="Allgemeine Geschäftsbedingungen", reading_order=0, source_type="page")],
    })

    result = _primary_contract_title(canonical, document)

    assert result is not None
    title, evidence = result
    assert title == "SERVICEVERTRAG RADIOSURGERY"
    assert evidence.page == 2
    assert evidence.source_text == title


def test_primary_contract_heading_ignores_indexed_contracts_on_first_page():
    from types import SimpleNamespace
    from app.ai.harness.v3 import _primary_contract_title

    index = (
        "1 | 82020-28 | SERVICEVERTRAG SYSTEMHARDWARE / ANWENDUNGSSUPPORT "
        "EXACTRAC X-RAY | 48\n"
        "5 | 85020-02 | SERVICEVERTRAG SYSTEMHARDWARE NODE SERVER | 1 | 48"
    )
    canonical = SimpleNamespace(pages=[
        SimpleNamespace(page_number=1, text=index),
        SimpleNamespace(page_number=2, text="SERVICEVERTRAG RADIOSURGERY"),
        SimpleNamespace(page_number=3, text="Leistungsbeschreibung"),
    ])
    document = SimpleNamespace(pages_blocks={
        1: [SimpleNamespace(text=index, reading_order=0, source_type="page")],
        2: [SimpleNamespace(text="SERVICEVERTRAG RADIOSURGERY", reading_order=0, source_type="page")],
        3: [SimpleNamespace(text="Leistungsbeschreibung", reading_order=0, source_type="page")],
    })

    result = _primary_contract_title(canonical, document)

    assert result is not None
    title, evidence = result
    assert title == "SERVICEVERTRAG RADIOSURGERY"
    assert evidence.page == 2


def test_equipment_names_are_bound_to_the_explicit_service_scope_sentence():
    from types import SimpleNamespace
    from app.ai.harness.v3 import _equipment_from_service_scope

    text = (
        "SERVICEVERTRAG RADIOSURGERY\n"
        "Servicevertrag für ein ExacTrac X-Ray und ein ExacTrac Infrared System "
        "sowie für die Prep/Review Workstation, einschließlich der unten genannten Leistungen."
    )
    canonical = _StubCanonical([_StubCanonicalPage(2, text)])
    document = SimpleNamespace(pages_blocks={
        2: [SimpleNamespace(text=text, reading_order=0, source_type="page")],
    })

    result = _equipment_from_service_scope(canonical, document, page_number=2)

    assert result is not None
    items, evidence = result
    assert [item.device_name for item in items] == [
        "ExacTrac X-Ray",
        "ExacTrac Infrared System",
        "Prep/Review Workstation",
    ]
    assert evidence.page == 2
    assert all(item.evidence.page == 2 for item in items)


def test_generic_service_scope_does_not_create_equipment():
    from types import SimpleNamespace
    from app.ai.harness.v3 import _equipment_from_service_scope

    text = "Servicevertrag für die Pflege und den Support, einschließlich Reaktion im Störungsfall."
    canonical = _StubCanonical([_StubCanonicalPage(2, text)])
    document = SimpleNamespace(pages_blocks={
        2: [SimpleNamespace(text=text, reading_order=0, source_type="page")],
    })

    assert _equipment_from_service_scope(canonical, document, page_number=2) is None


def test_offer_term_table_binds_months_to_the_selected_contract_title():
    from types import SimpleNamespace
    from app.ai.harness.v3 import _duration_from_offer_table

    header = "Pos. Art.-Nr. | Beschreibung Anz. Monaten | Laufzeit in"
    row = "1 | | SERVICEVERTRAGRADIOSURGERY 82020-28 SERVICEVERTRAG EXACTRAC | 48"
    page_text = f"{header}\n{row}"
    canonical = _StubCanonical([_StubCanonicalPage(1, page_text)])
    document = SimpleNamespace(pages_blocks={
        1: [SimpleNamespace(text=page_text, reading_order=0, source_type="page")],
    })
    contract = SimpleNamespace(
        identity=SimpleNamespace(contract_title="SERVICEVERTRAG RADIOSURGERY")
    )

    result = _duration_from_offer_table(contract, canonical, document)

    assert result is not None
    duration, evidence, _quote = result
    assert duration.value == 48
    assert duration.unit.value == "months"
    assert evidence.page == 1
    assert evidence.requires_review is True


def test_offer_term_table_refuses_conflicting_title_bound_durations():
    from types import SimpleNamespace
    from app.ai.harness.v3 import _duration_from_offer_table

    text = (
        "Laufzeit in Monaten\n"
        "SERVICEVERTRAG RADIOSURGERY | 48\n"
        "SERVICEVERTRAG RADIOSURGERY | 36\n"
    )
    canonical = _StubCanonical([_StubCanonicalPage(1, text)])
    document = SimpleNamespace(pages_blocks={
        1: [SimpleNamespace(text=text, reading_order=0, source_type="page")],
    })
    contract = SimpleNamespace(
        identity=SimpleNamespace(contract_title="SERVICEVERTRAG RADIOSURGERY")
    )

    assert _duration_from_offer_table(contract, canonical, document) is None


def test_primary_contract_heading_uses_generic_contract_markers():
    from types import SimpleNamespace
    from app.ai.harness.v3 import _primary_contract_title

    title = "Rahmenvertrag Nr. 41 – OPTIS Mobile Next Imaging System"
    canonical = SimpleNamespace(pages=[SimpleNamespace(page_number=1, text=title)])
    document = SimpleNamespace(pages_blocks={
        1: [SimpleNamespace(text=title, reading_order=0, source_type="page")],
    })

    assert _primary_contract_title(canonical, document)[0] == title
