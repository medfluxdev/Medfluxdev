import json
from types import SimpleNamespace

import pytest

from app.ai.harness import get_harness_class
from app.ai.harness.document import DocumentModel
from app.ai.harness.source_signals import collect_source_signals
from app.ai.harness.v3 import (
    DirectContractHarness,
    HarnessV3,
    _normalize_money_payload,
    _per_call_rows,
    _retry_output_plan,
    _staged_price_rows,
    _steady_annual_amount,
)
from app.ai.schemas import ModelCapabilities, ModelDescriptor
from app.core.config import Settings
from app.documents.intelligence.canonical import (
    DocumentIntelligenceResult,
    Element,
    Page,
    ProcessingProvenance,
)



def test_per_device_evidence_attribution_requires_identity_in_quote():
    from app.ai.harness.pipeline import equipment_identity_in_quote
    from app.models.contract import Equipment

    scanner = Equipment(device_name="CT Scanner Alpha", serial_number="CT-001")
    infusion = Equipment(system_name="Accutron MR", serial_number="MR-002")
    quote = "Gerät: CT Scanner Alpha, Seriennummer CT-001"
    assert equipment_identity_in_quote(scanner, quote)
    assert not equipment_identity_in_quote(infusion, quote)
    assert equipment_identity_in_quote(infusion, "Anlage Accutron MR")
    assert not equipment_identity_in_quote(infusion, "Geräte und Anlagen gemäß Anhang")


def settings(**overrides):
    base = {
        "harness_engine": "v3",
        "harness_max_calls": 16,
        "harness_output_tokens": 1800,
        "harness_context_tokens": 8192,
        "harness_vision_max_calls": 2,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def document():
    pages = [
        Page(
            page_number=1,
            width_pt=600,
            height_pt=800,
            text="ABIOMED Europe GmbH Vertr.-Nr.: 40015645",
            elements=[
                Element(
                    element_id="p1",
                    page=1,
                    reading_order=0,
                    text="ABIOMED Europe GmbH Vertr.-Nr.: 40015645",
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
        Page(
            page_number=3,
            width_pt=600,
            height_pt=800,
            text=(
                "Impella\u00ae AIC System (Konsoleneinheit). "
                "Servicezeiten: Montag bis Freitag 09:00 bis 17:00, an Wochenenden "
                "und Feiertagen kein Service."
            ),
            elements=[
                Element(
                    element_id="p3",
                    page=3,
                    reading_order=0,
                    text=(
                        "Impella\u00ae AIC System (Konsoleneinheit). "
                        "Servicezeiten: Montag bis Freitag 09:00 bis 17:00, an Wochenenden "
                        "und Feiertagen kein Service."
                    ),
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
        Page(
            page_number=5,
            width_pt=600,
            height_pt=800,
            text=(
                "Der Vertrag beginnt am 01.04.2025 und endet am 31.03.2029. "
                "Die Laufzeit beträgt 4 Jahren. Der Vertrag wird nicht automatisch verlängert."
            ),
            elements=[
                Element(
                    element_id="p5",
                    page=5,
                    reading_order=0,
                    text=(
                        "Der Vertrag beginnt am 01.04.2025 und endet am 31.03.2029. "
                        "Die Laufzeit beträgt 4 Jahren. Der Vertrag wird nicht automatisch verlängert."
                    ),
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
        Page(
            page_number=7,
            width_pt=600,
            height_pt=800,
            text=(
                "Im Vertragsumfang enthalten: Reparaturen und Instandsetzung, "
                "Inspektionen, Ersatzteilversorgung. Nicht enthalten: Wartung an "
                "Wochenenden und Feiertagen, Instandhaltungsarbeiten durch "
                "unsachgemäße Bedienung."
            ),
            elements=[
                Element(
                    element_id="p7",
                    page=7,
                    reading_order=0,
                    text=(
                        "Im Vertragsumfang enthalten: Reparaturen und Instandsetzung, "
                        "Inspektionen, Ersatzteilversorgung. Nicht enthalten: Wartung an "
                        "Wochenenden und Feiertagen, Instandhaltungsarbeiten durch "
                        "unsachgemäße Bedienung."
                    ),
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
        Page(
            page_number=8,
            width_pt=600,
            height_pt=800,
            text="Fixed per call: 2.226,00 EUR. 2.Jahr 8.000,00 EUR.",
            elements=[
                Element(
                    element_id="p8",
                    page=8,
                    reading_order=0,
                    text="Fixed per call: 2.226,00 EUR. 2.Jahr 8.000,00 EUR.",
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
    ]
    return DocumentIntelligenceResult(
        document_id="abiomed-test",
        source_sha256="a" * 64,
        canonical_text="\n".join(page.text for page in pages),
        provenance=ProcessingProvenance(provider="docling"),
        pages=pages,
    )


class FakeProvider:
    supports_structured_output = True
    last_done_reason = None
    last_response_sha256 = None

    async def generate_request(
        self, text, system, schema, max_tokens, context_tokens, images=None
    ):
        title = schema["title"]
        if title == "ProposedFactBatch":
            if "semantic:core" in text:
                raise AssertionError("purpose must not leak into prompt")
            if "identity.contract_number" in text:
                return json.dumps(
                    {
                        "facts": [
                            {
                                "field": "identity.supplier",
                                "value": "ABIOMED Europe GmbH",
                                "page": 1,
                                "quote": "ABIOMED Europe GmbH",
                                "applicability": "applicable",
                            },
                            {
                                "field": "identity.contract_number",
                                "value": "40015645",
                                "page": 1,
                                "quote": "Vertr.-Nr.: 40015645",
                                "applicability": "applicable",
                            },
                            {
                                "field": "dates.start_date",
                                "value": {
                                    "date": "2025-04-01",
                                    "condition": None,
                                    "requires_review": False,
                                },
                                "page": 5,
                                "quote": "beginnt am 01.04.2025",
                                "applicability": "applicable",
                            },
                            {
                                "field": "dates.end_date",
                                "value": {
                                    "date": "2029-03-31",
                                    "condition": None,
                                    "requires_review": False,
                                },
                                "page": 5,
                                "quote": "endet am 31.03.2029",
                                "applicability": "applicable",
                            },
                            {
                                "field": "dates.duration",
                                "value": {"value": 4, "unit": "years"},
                                "page": 5,
                                "quote": "Laufzeit beträgt 4 Jahren",
                                "applicability": "applicable",
                            },
                            {
                                "field": "termination.automatic_renewal",
                                "value": False,
                                "page": 5,
                                "quote": "nicht automatisch verlängert",
                                "applicability": "applicable",
                            },
                        ]
                    }
                )
            if "costs.annual_cost" in text:
                return json.dumps(
                    {
                        "facts": [
                            {
                                "field": "costs.annual_cost",
                                "value": {
                                    "amount": 8000,
                                    "currency": "EUR",
                                    "period": "annual",
                                },
                                "page": 8,
                                "quote": "8.000,00 EUR",
                                "applicability": "applicable",
                            },
                            {
                                "field": "costs.variable_charges",
                                "value": [
                                    {
                                        "label": "Fixed per call",
                                        "amount": {
                                            "amount": 2226,
                                            "currency": "EUR",
                                            "period": None,
                                        },
                                        "unit": "per_call",
                                        "condition": None,
                                    }
                                ],
                                "page": 8,
                                "quote": "Fixed per call: 2.226,00 EUR",
                                "applicability": "applicable",
                            },
                        ]
                    }
                )
            if "sla.service_hours" in text:
                return json.dumps(
                    {
                        "facts": [
                            {
                                "field": "equipment",
                                "value": ["Impella\u00ae AIC System"],
                                "page": 3,
                                "quote": "Impella\u00ae AIC System (Konsoleneinheit)",
                                "applicability": "applicable",
                            },
                            {
                                "field": "sla.service_hours",
                                "value": {
                                    "start_time": "09:00",
                                    "end_time": "17:00",
                                    "days": ["Mo", "Di", "Mi", "Do", "Fr"],
                                },
                                "page": 3,
                                "quote": "Montag bis Freitag 09:00 bis 17:00",
                                "applicability": "applicable",
                            },
                            {
                                "field": "sla.availability_24_7",
                                "value": False,
                                "page": 3,
                                "quote": "an Wochenenden und Feiertagen kein Service",
                                "applicability": "applicable",
                            },
                            {
                                "field": "services.included_services",
                                "value": [
                                    "Reparaturen und Instandsetzung",
                                    "Inspektionen",
                                    "Ersatzteilversorgung",
                                ],
                                "page": 7,
                                "quote": (
                                    "Im Vertragsumfang enthalten: Reparaturen und "
                                    "Instandsetzung"
                                ),
                                "applicability": "applicable",
                            },
                            {
                                "field": "services.excluded_services",
                                "value": [
                                    "Wartung an Wochenenden und Feiertagen",
                                    "Instandhaltungsarbeiten durch unsachgemäße Bedienung",
                                ],
                                "page": 7,
                                "quote": (
                                    "Nicht enthalten: Wartung an Wochenenden und "
                                    "Feiertagen"
                                ),
                                "applicability": "applicable",
                            },
                        ]
                    }
                )
            return '{"facts":[]}'
        if title == "VisualPageReading":
            return json.dumps({"page": 1, "visible_text": [], "unresolved": []})
        raise AssertionError(title)


def ai(provider=None):
    provider = provider or FakeProvider()

    async def runtime():
        return provider, ModelDescriptor(
            provider_id="mock",
            model_id="qwen3-vl:8b-instruct",
            context_length=8192,
            capabilities=ModelCapabilities(text=True, vision=True),
        )

    return SimpleNamespace(harness_runtime=runtime)


def test_engine_selection_uses_replacement_harness():
    assert get_harness_class(settings()) is HarnessV3
    assert issubclass(HarnessV3, DirectContractHarness)


def test_production_constructor_accepts_settings_only():
    harness = HarnessV3(settings())
    assert isinstance(harness, DirectContractHarness)
    assert harness.ai is not None


def test_source_signals_find_reference_values():
    rows = collect_source_signals(DocumentModel.build(document()))
    values = {row["value"] for row in rows}
    assert "40015645" in values
    assert "01.04.2025" in values
    assert "31.03.2029" in values
    assert "4 Jahren" in values
    assert "2.226,00 EUR" in values
    assert "8.000,00 EUR" in values


@pytest.mark.asyncio
async def test_direct_harness_delivers_grounded_contract_without_block_ids():
    result = await DirectContractHarness(settings(), ai()).analyze(document())

    assert result.contract is not None, result.error
    contract = result.contract
    assert contract.identity.supplier == "ABIOMED Europe GmbH"
    assert contract.identity.contract_number == "40015645"
    assert str(contract.dates.start_date.date) == "2025-04-01"
    assert str(contract.dates.end_date.date) == "2029-03-31"
    assert contract.dates.duration.value == 4
    assert contract.termination.automatic_renewal is False
    assert contract.costs.annual_cost.amount == 8000
    assert contract.costs.variable_charges[0].amount.amount == 2226
    assert result.diagnostics["supported_count"] >= 8
    assert result.diagnostics["evidence_count"] >= 8
    assert result.diagnostics["stage_call_counts"]["semantic"] == 4


@pytest.mark.asyncio
async def test_equipment_and_service_hours_and_service_scope_normalize():
    # UAT-Defekte: (1) equipment als List-of-Strings verworfen, (2)
    # sla.service_hours mit start/end_time/days zu {} kollabiert und verworfen,
    # (3) included/excluded services nicht projiziert. Alles muss durch die
    # Deterministic-Normalisierung durchlaufen und im Contract ankommen.
    result = await DirectContractHarness(settings(), ai()).analyze(document())

    assert result.contract is not None, result.error
    assert [
        item.device_name for item in result.contract.equipment
    ] == ["Impella\u00ae AIC System"]
    assert result.contract.equipment[0].evidence is not None
    assert result.contract.equipment[0].evidence.page == 3
    assert result.contract.equipment[0].serial_number is None

    sla = result.contract.sla
    assert sla.service_hours is not None
    assert sla.service_hours.value is None
    assert "09:00" in sla.service_hours.original_text
    assert "17:00" in sla.service_hours.original_text
    assert sla.availability_24_7 is False
    assert sla.evidence is not None
    assert sla.evidence.page == 3

    services = result.contract.services
    assert "Reparaturen und Instandsetzung" in services.included_services
    assert "Ersatzteilversorgung" in services.included_services
    assert "Wartung an Wochenenden und Feiertagen" in services.excluded_services
    assert services.evidence is not None

    rejected_by = {
        row["field"]: row["reason"]
        for row in result.diagnostics["rejected_facts"]
    }
    assert "equipment" not in rejected_by
    assert "sla.service_hours" not in rejected_by
    assert "sla.availability_24_7" not in rejected_by
    assert "services.included_services" not in rejected_by
    assert "services.excluded_services" not in rejected_by


@pytest.mark.asyncio
async def test_separate_equipment_facts_preserve_all_devices_and_own_sources():
    class TwoDeviceProvider(FakeProvider):
        async def generate_request(self, text, system, schema, max_tokens, context_tokens, images=None):
            if schema["title"] == "ProposedFactBatch" and "sla.service_hours" in text:
                return json.dumps({"facts": [
                    {"field": "equipment", "value": [{"device_name": "Impella AIC System"}],
                     "page": 3, "quote": "Impella AIC System", "applicability": "applicable"},
                    {"field": "equipment", "value": [{"system_name": "Accutron MR"}],
                     "page": 7, "quote": "Accutron MR", "applicability": "applicable"},
                ]})
            return await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images=images
            )

    source = document()
    page = next(page for page in source.pages if page.page_number == 7)
    page.text += " Accutron MR"
    page.elements[0].text += " Accutron MR"
    source.canonical_text = "\\n".join(page.text for page in source.pages)
    result = await DirectContractHarness(settings(), ai(TwoDeviceProvider())).analyze(source)
    assert result.contract is not None, result.error
    equipment = result.contract.equipment
    assert [item.device_name or item.system_name for item in equipment] == [
        "Impella AIC System", "Accutron MR"
    ]
    assert [item.evidence.page for item in equipment] == [3, 7]


@pytest.mark.asyncio
async def test_alternative_fact_never_projects():
    class AlternativeProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch" and "costs.annual_cost" in text:
                payload = json.loads(raw)
                for fact in payload["facts"]:
                    if fact["field"] == "costs.annual_cost":
                        fact["applicability"] = "alternative"
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(settings(), ai(AlternativeProvider())).analyze(
        document()
    )
    assert result.contract is not None
    assert result.contract.costs.annual_cost is None
    assert any(
        row["field"] == "costs.annual_cost"
        and row["reason"] == "applicability:alternative"
        for row in result.diagnostics["rejected_facts"]
    )


@pytest.mark.asyncio
async def test_quote_that_spans_layout_elements_binds_to_page_text():
    class SplitElementProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch" and "identity.supplier" in text:
                payload = json.loads(raw)
                for fact in payload["facts"]:
                    if fact["field"] == "identity.supplier":
                        fact["quote"] = (
                            "zwischen\nABIOMED Europe GmbH Neuenhofer Weg 3 "
                            "D-52074 Aachen"
                        )
                return json.dumps(payload)
            return raw

    pages = [
        *document().pages,
    ]
    doc = document()
    doc.pages[0] = Page(
        page_number=1,
        width_pt=600,
        height_pt=800,
        text=(
            "Vertr.-Nr.: 40015645 zwischen\n"
            "ABIOMED Europe GmbH Neuenhofer Weg 3 D-52074 Aachen"
        ),
        elements=[
            Element(
                element_id="el1",
                page=1,
                reading_order=0,
                text="Vertr.-Nr.: 40015645",
                type="paragraph",
                method="ocr",
            ),
            Element(
                element_id="el2",
                page=1,
                reading_order=1,
                text="zwischen",
                type="paragraph",
                method="ocr",
            ),
            Element(
                element_id="el3",
                page=1,
                reading_order=2,
                text="ABIOMED Europe GmbH Neuenhofer Weg 3 D-52074 Aachen",
                type="paragraph",
                method="ocr",
            ),
        ],
    )
    doc.canonical_text = "\n".join(page.text for page in doc.pages)

    result = await DirectContractHarness(settings(), ai(SplitElementProvider())).analyze(
        doc
    )
    assert result.contract is not None, result.error
    accepted = {
        row["field"]: row for row in result.diagnostics["accepted_facts"]
    }
    assert accepted["identity.supplier"]["page"] == 1
    assert result.contract.identity.supplier == "ABIOMED Europe GmbH"
    source = result.contract.identity.evidence
    assert source is not None
    assert source.page == 1
    assert "ABIOMED Europe GmbH" in source.source_text


@pytest.mark.asyncio
async def test_quote_can_bind_by_literal_source_signal_when_model_quote_is_bad():
    class BadQuoteProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch" and "identity.contract_number" in text:
                payload = json.loads(raw)
                for fact in payload["facts"]:
                    if fact["field"] == "identity.contract_number":
                        fact["quote"] = "contract number 40015645"
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(settings(), ai(BadQuoteProvider())).analyze(
        document()
    )
    assert result.contract is not None
    assert result.contract.identity.contract_number == "40015645"
    accepted = {
        row["field"]: row for row in result.diagnostics["accepted_facts"]
    }
    assert accepted["identity.contract_number"]["page"] == 1


@pytest.mark.asyncio
async def test_missing_page_and_quote_are_auto_anchored_and_dates_normalized():
    class SparseEvidenceProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] != "ProposedFactBatch":
                return raw
            payload = json.loads(raw)
            for fact in payload["facts"]:
                if fact["field"] == "identity.supplier":
                    fact["page"] = None
                    fact["quote"] = ""
                if fact["field"] == "dates.start_date":
                    fact["value"] = "01.04.2025"
                    fact["page"] = None
                    fact["quote"] = ""
                if fact["field"] == "dates.end_date":
                    fact["value"] = "31.03.2029"
                    fact["page"] = None
                    fact["quote"] = ""
                if fact["field"] == "dates.duration":
                    fact["value"] = "4 Jahren"
                    fact["page"] = None
                    fact["quote"] = ""
                if fact["field"] == "costs.annual_cost":
                    fact["value"] = "8.000,00 EUR"
                    fact["page"] = None
                    fact["quote"] = ""
            return json.dumps(payload)

    result = await DirectContractHarness(
        settings(), ai(SparseEvidenceProvider())
    ).analyze(document())

    assert result.contract is not None, result.error
    assert result.contract.identity.supplier == "ABIOMED Europe GmbH"
    assert str(result.contract.dates.start_date.date) == "2025-04-01"
    assert str(result.contract.dates.end_date.date) == "2029-03-31"
    assert result.contract.dates.duration.value == 4
    assert result.contract.costs.annual_cost.amount == 8000
    normalized_fields = {
        row["field"] for row in result.diagnostics["normalizations"]
    }
    assert "dates.start_date" in normalized_fields
    assert "dates.end_date" in normalized_fields
    assert "dates.duration" in normalized_fields
    assert "costs.annual_cost" in normalized_fields
    accepted = {
        row["field"]: row for row in result.diagnostics["accepted_facts"]
    }
    assert accepted["identity.supplier"]["page"] == 1
    assert accepted["dates.start_date"]["page"] == 5
    assert accepted["dates.end_date"]["page"] == 5
    assert accepted["costs.annual_cost"]["page"] == 8


@pytest.mark.asyncio
async def test_known_time_value_drops_unknown_model_properties_before_validation():
    class ExtraSlaPropertyProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch" and "sla.service_hours" in text:
                payload = json.loads(raw)
                payload["facts"].append(
                    {
                        "field": "sla.service_hours",
                        "value": {
                            "value": 8,
                            "unit": "hours",
                            "original_text": "8 Stunden",
                            "unexpected": "discard me",
                        },
                        "page": None,
                        "quote": "",
                        "applicability": "applicable",
                    }
                )
                return json.dumps(payload)
            return raw

    # No source evidence for this synthetic SLA value, so it must still be
    # rejected by evidence rather than by schema shape.
    result = await DirectContractHarness(
        settings(), ai(ExtraSlaPropertyProvider())
    ).analyze(document())
    rows = [
        row for row in result.diagnostics["rejected_facts"]
        if row["field"] == "sla.service_hours"
    ]
    assert rows
    assert rows[0]["reason"] == "evidence_not_located"


@pytest.mark.asyncio
async def test_supplier_literal_binds_on_own_page_when_repeated_on_later_page():
    # Frankfurt-Diagnose: identity.supplier ist eine vollstaendige Adresse, die
    # als Briefkopf auf Seite 1 UND Seite 6 (Footern/Reiter) wiederkehrt. Exakt
    # ist sie daher global nicht eindeutig; auf ihrer eigenen Seite (1) ist sie
    # es. Der Literal-Fallback muss zuerst page-scoped suchen, bevor er global
    # zaehlt, sonst fallt ein korrekt annotierter Lieferant in
    # "evidence_not_located".
    supplier_literal = (
        "Abbott Medical GmbH Betriebsstätte Wetzlar "
        "Schanzenfeldstraße 2 35578 Wetzlar"
    )
    pages = [
        Page(
            page_number=1,
            width_pt=600,
            height_pt=800,
            text=supplier_literal + "\nVertr.-Nr.: 40015645",
            elements=[
                Element(
                    element_id="p1-supplier",
                    page=1,
                    reading_order=0,
                    text=supplier_literal,
                    type="paragraph",
                    method="ocr",
                ),
                Element(
                    element_id="p1-nr",
                    page=1,
                    reading_order=1,
                    text="Vertr.-Nr.: 40015645",
                    type="paragraph",
                    method="ocr",
                ),
            ],
        ),
        Page(
            page_number=6,
            width_pt=600,
            height_pt=800,
            text=supplier_literal + " www.abbott.com",
            elements=[
                Element(
                    element_id="p6-header",
                    page=6,
                    reading_order=0,
                    text=supplier_literal,
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
    ]
    canonical = DocumentIntelligenceResult(
        document_id="supplier-page-scope",
        source_sha256="e" * 64,
        canonical_text="\n".join(page.text or "" for page in pages),
        provenance=ProcessingProvenance(provider="docling"),
        pages=pages,
    )

    class FullAddressProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] != "ProposedFactBatch" or "identity.supplier" not in text:
                return raw
            payload = json.loads(raw)
            for fact in payload["facts"]:
                if fact["field"] == "identity.supplier":
                    fact["value"] = supplier_literal
                    fact["page"] = 1
                    # OCR-verstuemmeltes Zitat: bindet weder exakt noch tolerant,
                    # Fact muss ueber den page-scoped Literal-Fallback belegt werden.
                    fact["quote"] = (
                        "Abbott Medical GmbH Betriebsstätte Wetzlar "
                        "Schanzenfeldstr. 2 35578V"
                    )
            return json.dumps(payload)

    result = await DirectContractHarness(
        settings(), ai(FullAddressProvider())
    ).analyze(canonical)
    assert result.contract is not None, result.error
    assert result.contract.identity.supplier == supplier_literal
    accepted = {
        row["field"]: row for row in result.diagnostics["accepted_facts"]
    }
    assert accepted["identity.supplier"]["page"] == 1
    assert supplier_literal in accepted["identity.supplier"]["quote"]


@pytest.mark.asyncio
async def test_money_fact_binds_by_literal_source_signal_when_model_quote_is_bad():
    class BadMoneyQuoteProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch" and "costs.annual_cost" in text:
                payload = json.loads(raw)
                payload["facts"].append(
                    {
                        "field": "costs.monthly_cost",
                        "value": {
                            "amount": 8000,
                            "currency": "EUR",
                            "period": None,
                        },
                        "page": 8,
                        "quote": "8000 EUR",
                        "applicability": "applicable",
                    }
                )
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(
        settings(), ai(BadMoneyQuoteProvider())
    ).analyze(document())
    assert result.contract is not None
    assert result.contract.costs.monthly_cost.amount == 8000
    assert result.contract.costs.evidence is not None
    assert result.contract.costs.evidence.page == 8


@pytest.mark.asyncio
async def test_dict_shapes_for_dates_and_duration_are_normalized():
    class DictShapeProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch":
                payload = json.loads(raw)
                for fact in payload["facts"]:
                    if fact["field"] == "dates.start_date":
                        fact["value"] = {"year": 2025, "month": 4, "day": 1}
                    if fact["field"] == "dates.duration":
                        fact["value"] = {"years": 4}
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(
        settings(), ai(DictShapeProvider())
    ).analyze(document())
    assert result.contract is not None, result.error
    assert str(result.contract.dates.start_date.date) == "2025-04-01"
    assert result.contract.dates.duration.value == 4
    assert result.contract.dates.duration.unit == "years"
    normalized_fields = {
        row["field"] for row in result.diagnostics["normalizations"]
    }
    assert "dates.start_date" in normalized_fields
    assert "dates.duration" in normalized_fields


@pytest.mark.asyncio
async def test_truncated_output_is_retried_with_reduced_output_budget():
    class TruncatingProvider(FakeProvider):
        def __init__(self):
            super().__init__()
            self.semantic_calls = 0

        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            if schema["title"] == "ProposedFactBatch":
                self.semantic_calls += 1
                if self.semantic_calls == 1:
                    self.last_done_reason = "length"
                    self.last_usage = {
                        "prompt_tokens": 3000,
                        "completion_tokens": 1800,
                    }
                    return await super().generate_request(
                        text, system, schema, max_tokens, context_tokens, images
                    )
                self.last_done_reason = None
                self.last_usage = {"prompt_tokens": 3000}
            return await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )

    result = await DirectContractHarness(
        settings(), ai(TruncatingProvider())
    ).analyze(document())
    assert result.contract is not None, result.error
    assert result.diagnostics["failure_count"] == 0
    assert result.diagnostics["stage_call_counts"]["semantic"] == 4
    assert any(
        row.get("retried_with_output_tokens") for row in result.diagnostics["calls"]
    )


@pytest.mark.asyncio
async def test_unknown_applicability_junk_without_quote_is_not_auto_bound():
    class JunkProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] == "ProposedFactBatch" and "identity.contract_number" in text:
                payload = json.loads(raw)
                payload["facts"].append(
                    {
                        "field": "identity.supplier",
                        "value": "ABIOMED Europe GmbH",
                        "page": None,
                        "quote": "",
                        "applicability": "unknown",
                    }
                )
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(
        settings(), ai(JunkProvider())
    ).analyze(document())
    assert result.contract is not None
    assert any(
        row["field"] == "identity.supplier"
        and row["reason"] == "evidence_not_located"
        for row in result.diagnostics["rejected_facts"]
    )


def test_money_normalizer_rescues_value_str_and_currency_code_shapes():
    normalized = _normalize_money_payload(
        {"value_str": "8.000,00", "currency_code": "eur"}
    )
    assert normalized["amount"] == 8000
    assert normalized["currency"] == "eur"

    normalized = _normalize_money_payload(
        {"amount": {"cents": 800000, "currency": "EUR"}}
    )
    assert normalized["amount"] == 800000
    assert normalized["currency"] == "EUR"


def test_staged_price_rows_parse_german_pricing_annex():
    rows = _staged_price_rows(
        "1.Jahr 0 EUR | 2.Jahr 8.000,00 EUR | 3.Jahr 8.000,00 EUR | 4.Jahr 8.000,00 EUR"
    )
    assert [row["period_index"] for row, _ in rows] == [1, 2, 3, 4]
    assert [row["amount"]["amount"] for row, _ in rows] == [
        0.0,
        8000.0,
        8000.0,
        8000.0,
    ]
    assert all(row["amount"]["currency"] == "EUR" for row, _ in rows)
    assert all(quote for _, quote in rows)


def test_per_call_rows_parse_fixed_rate():
    rows = _per_call_rows("Fixed per call: 2.226,00 EUR.")
    assert len(rows) == 1
    row, quote = rows[0]
    assert row["amount"]["amount"] == 2226.0
    assert row["unit"] == "per_call"
    assert "2.226,00 EUR" in quote


def test_steady_annual_amount_derives_recurring_fee():
    rows = [
        {"period_index": 1, "amount": {"amount": 0.0}},
        {"period_index": 2, "amount": {"amount": 8000.0}},
        {"period_index": 3, "amount": {"amount": 8000.0}},
        {"period_index": 4, "amount": {"amount": 8000.0}},
    ]
    assert _steady_annual_amount(rows) == 8000.0

    assert (
        _steady_annual_amount(
            [
                {"period_index": 1, "amount": {"amount": 0.0}},
                {"period_index": 2, "amount": {"amount": 8000.0}},
            ]
        )
        is None
    )
    assert _steady_annual_amount(
        [{"period_index": 1, "amount": {"amount": 8000.0}}]
    ) is None


def test_retry_output_plan_uses_measured_budget():
    plan = _retry_output_plan("semantic:core", 3000, 8192, 1800)
    assert plan[0] is not None
    assert plan[1] == "output_budget_stage_retry"

    plan = _retry_output_plan("semantic:core", 7600, 8192, 1800)
    assert plan[0] is None
