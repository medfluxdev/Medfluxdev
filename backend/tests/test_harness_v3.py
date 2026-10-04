import json
from types import SimpleNamespace

import pytest

from app.ai.harness import get_harness_class
from app.ai.harness.document import DocumentModel
from app.ai.harness.source_signals import collect_source_signals
from app.ai.harness.v3 import (
    DirectContractHarness,
    HarnessV3,
    _financial_source_rejection,
    _normalize_money_payload,
    _pack_pages,
    _per_call_rows,
    _retry_output_plan,
    _complete_scheduled_total,
    _staged_price_rows,
    _steady_annual_amount,
    _primary_contract_title,
    _explicit_labelled_contract_dates,
    _derive_start_condition,
    _duration_from_offer_table,
    _derive_supplier,
    _derive_customer_from_parties,
    _unwrap_json_code_fence,
    _wire_fact_value,
    _wire_fact_value_for_schema,
)
from app.ai.schemas import ModelCapabilities, ModelDescriptor
from app.core.config import Settings
from app.documents.intelligence.canonical import (
    DocumentIntelligenceResult,
    Element,
    Page,
    ProcessingProvenance,
)
from app.models.contract import Contract
from app.models.values import Duration, FlexibleDate



def test_per_device_evidence_attribution_requires_identity_in_quote():
    from app.ai.harness.pipeline import equipment_identity_in_quote
    from app.models.contract import Equipment

    scanner = Equipment(device_name="CT Scanner Alpha", serial_number="CT-001")
    infusion = Equipment(system_name="Accutron MR", serial_number="MR-002")
    quote = "Gerät: CT Scanner Alpha, Seriennummer CT-001"
    assert equipment_identity_in_quote(scanner, quote)
    assert not equipment_identity_in_quote(infusion, quote)
    assert not equipment_identity_in_quote(infusion, "Anlage Accutron MR")
    assert equipment_identity_in_quote(infusion, "Anlage Accutron MR, SN MR-002")
    assert not equipment_identity_in_quote(infusion, "Geräte und Anlagen gemäß Anhang")

    # Identical model or name must not attribute one unit's source to
    # another physical unit with its own serial number.
    second = Equipment(device_name="CT Scanner Alpha", model="CT-X",
                       serial_number="CT-002")
    assert not equipment_identity_in_quote(second, quote)
    assert equipment_identity_in_quote(second, "CT Scanner Alpha CT-002")
    assert not equipment_identity_in_quote(second, "CT-X service")
    assert not equipment_identity_in_quote(
        Equipment(device_name="CT Scanner"), "CT ScannerAlpha"
    )
    # Hyphenated serials must match as complete tokens, not prefixes.
    assert not equipment_identity_in_quote(scanner, "CT-0019")
    assert not equipment_identity_in_quote(scanner, "XCT-001")
    assert equipment_identity_in_quote(scanner, "(CT-001), service included")
    assert equipment_identity_in_quote(
        Equipment(system_name="Accutron MR"), "Anlage: Accutron MR."
    )


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


def test_primary_contract_title_prefers_canonical_text_with_trademark():
    canonical = DocumentIntelligenceResult(
        document_id="doc-title",
        source_sha256="a" * 64,
        canonical_text="Rahmenvertrag Nr. RAV-00074 4 - OPTIS™ Mobile Next Imaging System",
        pages=[Page(
            page_number=1, width_pt=600, height_pt=800,
            text="Rahmenvertrag Nr. RAV-00074 4 - OPTIS™ Mobile Next Imaging System",
            elements=[],
        )],
        provenance=ProcessingProvenance(provider="docling"),
    )
    document_model = DocumentModel.build(canonical)

    result = _primary_contract_title(canonical, document_model)

    assert result is not None
    assert result[0] == "Rahmenvertrag Nr. RAV-00074 - OPTIS™ Mobile Next Imaging System"
    assert result[1].source_text == "Rahmenvertrag Nr. RAV-00074 4 - OPTIS™ Mobile Next Imaging System"


def test_primary_contract_title_prefers_opening_service_heading_over_later_terms():
    canonical = DocumentIntelligenceResult(
        document_id="doc-multipage-service-title",
        source_sha256="f" * 64,
        canonical_text=(
            "SERVICEVERTRAG RADIOSURGERY\n"
            "Allgemeine Geschäftsbedingungen für alle Lieferungen"
        ),
        pages=[
            Page(
                page_number=1, width_pt=600, height_pt=800,
                text="SERVICEVERTRAG RADIOSURGERY", elements=[],
            ),
            Page(
                page_number=18, width_pt=600, height_pt=800,
                text="Allgemeine Geschäftsbedingungen für alle Lieferungen",
                elements=[],
            ),
        ],
        provenance=ProcessingProvenance(provider="docling"),
    )
    document_model = DocumentModel.build(canonical)

    result = _primary_contract_title(canonical, document_model)

    assert result is not None
    assert result[0] == "SERVICEVERTRAG RADIOSURGERY"
    assert result[1].page == 1
    assert result[1].source_text == "SERVICEVERTRAG RADIOSURGERY"


def test_explicit_contract_date_labels_bind_dates_and_reject_offer_date():
    canonical = DocumentIntelligenceResult(
        document_id="doc-dates",
        source_sha256="b" * 64,
        pages=[Page(
            page_number=1, width_pt=600, height_pt=800,
            text=(
                "Datum: 15.04.2025\nVERTRAGS-STARTDATUM\n04.06.2025\n"
                "VERTRAGS-ENDDATUM\n03.06.2029"
            ),
            elements=[],
        )],
        provenance=ProcessingProvenance(provider="docling"),
    )
    document_model = DocumentModel.build(canonical)
    contract = Contract()
    contract.dates.start_condition = "Er startet an dem Tag der Installation und Inbetriebnahme"

    derived = _explicit_labelled_contract_dates(contract, canonical, document_model)

    assert str(contract.dates.start_date.date) == "2025-06-04"
    assert str(contract.dates.end_date.date) == "2029-06-03"
    assert contract.dates.start_condition is None
    assert [row["field"] for row in derived] == [
        "dates.start_date", "dates.end_date"
    ]
    assert all(row["source"].page == 1 for row in derived)


def test_explicit_contract_date_labels_reject_conflicting_values():
    canonical = DocumentIntelligenceResult(
        document_id="doc-conflicting-dates",
        source_sha256="c" * 64,
        pages=[
            Page(page_number=1, width_pt=600, height_pt=800,
                 text="VERTRAGS-STARTDATUM\n04.06.2025", elements=[]),
            Page(page_number=2, width_pt=600, height_pt=800,
                 text="VERTRAGS-STARTDATUM\n05.06.2025", elements=[]),
        ],
        provenance=ProcessingProvenance(provider="docling"),
    )
    document_model = DocumentModel.build(canonical)
    contract = Contract()

    derived = _explicit_labelled_contract_dates(contract, canonical, document_model)

    assert contract.dates.start_date is None
    assert not any(row["field"] == "dates.start_date" for row in derived)


def test_explicit_contract_date_label_overrides_conflicting_model_value():
    canonical = DocumentIntelligenceResult(
        document_id="doc-model-date-conflict",
        source_sha256="d" * 64,
        pages=[Page(
            page_number=1, width_pt=600, height_pt=800,
            text="VERTRAGS-ENDDATUM\n03.06.2029", elements=[],
        )],
        provenance=ProcessingProvenance(provider="docling"),
    )
    document_model = DocumentModel.build(canonical)
    contract = Contract()
    contract.dates.end_date = FlexibleDate(date="2025-06-04")

    derived = _explicit_labelled_contract_dates(contract, canonical, document_model)

    assert str(contract.dates.end_date.date) == "2029-06-03"
    assert derived[0]["model_conflict"] is True


def test_contract_date_pair_skips_unrelated_datum_in_reordered_ocr():
    canonical = DocumentIntelligenceResult(
        document_id="doc-reordered-date-table",
        source_sha256="e" * 64,
        pages=[Page(
            page_number=1, width_pt=600, height_pt=800,
            text=(
                "INSTALLATIONSDATUM\n04.06.2025\nSERIEN-NUMMER\n20488972\n"
                "VERTRAGS-STARTDATUM\nVERTRAGS-ENDDATUM\n04.06.2025\n"
                "Datum:\n15.04.2025\n03.06.2029"
            ),
            elements=[],
        )],
        provenance=ProcessingProvenance(provider="docling"),
    )
    document_model = DocumentModel.build(canonical)
    contract = Contract()
    contract.dates.start_condition = "Er startet an dem Tag der Installation und Inbetriebnahme"

    derived = _explicit_labelled_contract_dates(contract, canonical, document_model)

    assert str(contract.dates.start_date.date) == "2025-06-04"
    assert str(contract.dates.end_date.date) == "2029-06-03"
    assert contract.dates.start_condition is None
    assert all("Datum:\n15.04.2025" in row["quote"] for row in derived)
    assert _derive_start_condition(contract, canonical) is None


def test_title_bound_offer_term_table_overrides_unrelated_model_duration():
    canonical = DocumentIntelligenceResult(
        document_id="doc-term-table",
        source_sha256="f" * 64,
        pages=[Page(
            page_number=1,
            width_pt=600,
            height_pt=800,
            text=(
                "Laufzeit in Anzahl Monaten\n"
                "SERVICEVERTRAG RADIOSURGERY | 82020-28 | EXACTRAC X-RAY | 48\n"
                "Die Preise gelten ab Ausstellungsdatum für 90 Tage"
            ),
            elements=[],
        )],
        provenance=ProcessingProvenance(provider="docling"),
    )
    document_model = DocumentModel.build(canonical)
    contract = Contract()
    contract.identity.contract_title = "SERVICEVERTRAG RADIOSURGERY"
    contract.dates.duration = Duration(value=30, unit="days")

    result = _duration_from_offer_table(contract, canonical, document_model)

    assert result is not None
    duration, evidence, quote = result
    assert duration == Duration(value=48, unit="months")
    assert evidence.page == 1
    assert evidence.requires_review is True
    assert quote.endswith("| 48")


def test_source_ranked_supplier_letterhead_replaces_weaker_model_party():
    canonical = DocumentIntelligenceResult(
        document_id="doc-supplier-party",
        source_sha256="a" * 64,
        pages=[Page(
            page_number=1,
            width_pt=600,
            height_pt=800,
            text=(
                "Brainlab Sales GmbH Olof-Palme-Straße 9 81829 Munich Germany\n"
                "SERVICEVERTRAG RADIOSURGERY"
            ),
            elements=[],
        ), Page(
            page_number=7,
            width_pt=600,
            height_pt=800,
            text='"BRAINLAB" bezeichnet die BRAINLAB Gesellschaft, welche im ANGEBOT spezifiziert ist.',
            elements=[],
        )],
        provenance=ProcessingProvenance(provider="docling"),
    )
    document_model = DocumentModel.build(canonical)
    contract = Contract()
    contract.identity.supplier = "BRAINLAB Gesellschaft"
    contract.identity.customer = "Brainlab Sales GmbH"

    evidence = _derive_supplier(contract, canonical, document_model)

    assert contract.identity.supplier == "Brainlab Sales GmbH"
    assert evidence is not None
    assert evidence.page == 1
    assert "81829" in evidence.source_text


def test_customer_is_resolved_as_other_legal_party_from_between_clause():
    canonical = DocumentIntelligenceResult(
        document_id="doc-customer-party",
        source_sha256="b" * 64,
        pages=[Page(
            page_number=1,
            width_pt=600,
            height_pt=800,
            text=(
                "zwischen Abbott Medical GmbH Betriebsstätte Wetzlar "
                "Schanzenfeldstr. 2 35578 Wetzlar und Krankenhaus Nordwest GmbH "
                "Steinbacher Hohl 2-26 60488 Frankfurt"
            ),
            elements=[],
        )],
        provenance=ProcessingProvenance(provider="docling"),
    )
    document_model = DocumentModel.build(canonical)
    contract = Contract()
    contract.identity.supplier = "Abbott Medical GmbH"
    contract.identity.customer = "Klinik"

    result = _derive_customer_from_parties(contract, canonical, document_model)

    assert result is not None
    customer, evidence = result
    assert customer == "Krankenhaus Nordwest GmbH"
    assert contract.identity.customer == customer
    assert evidence.page == 1
    assert evidence.requires_review is True
    assert "zwischen Abbott Medical GmbH" in evidence.source_text


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


def document_with_page_8_text(text):
    source = document()
    page = next(page for page in source.pages if page.page_number == 8)
    page.text = text
    for element in page.elements:
        element.text = text
    source.canonical_text = "\n".join(page.text for page in source.pages)
    return source


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


def test_json_code_fence_unwrap_requires_a_complete_json_document():
    fenced = '```json\n{"page": 1}\n```'
    assert _unwrap_json_code_fence(fenced) == '{"page": 1}'

    extra_text = 'Model result:\n```json\n{"page": 1}\n```'
    assert _unwrap_json_code_fence(extra_text) == extra_text

    invalid_body = '```json\n{"page":}\n```'
    assert _unwrap_json_code_fence(invalid_body) == invalid_body


def test_structured_wire_value_round_trips_json_objects():
    value = {"amount": 52500, "currency": "EUR", "period": "annual"}
    encoded = _wire_fact_value_for_schema(value)
    assert json.loads(encoded) == value
    assert _wire_fact_value(encoded) == value


def test_source_signals_find_reference_values():
    rows = collect_source_signals(DocumentModel.build(document()))
    values = {row["value"] for row in rows}
    assert "40015645" in values
    assert "01.04.2025" in values
    assert "31.03.2029" in values
    assert "4 Jahren" in values
    assert "2.226,00 EUR" in values
    assert "8.000,00 EUR" in values


def test_source_signals_recognize_labelled_frame_contract_number():
    canonical = DocumentIntelligenceResult(
        document_id="optis-contract-number",
        source_sha256="e" * 64,
        pages=[Page(
            page_number=1, width_pt=600, height_pt=800,
            text="Rahmenvertrag Nr. RAV-00074 - OPTIS Mobile Next",
            elements=[],
        )],
        provenance=ProcessingProvenance(provider="ocr"),
    )
    rows = collect_source_signals(DocumentModel.build(canonical))
    matches = [
        row for row in rows
        if row["kind"] == "labelled_contract_number"
    ]
    assert [(row["value"], row["page"]) for row in matches] == [
        ("RAV-00074", 1)
    ]
def test_financial_period_and_amount_must_share_the_same_source_quote():
    assert _financial_source_rejection(
        "costs.annual_cost",
        {"amount": 52500, "currency": "EUR", "period": "annual"},
        "Jährliche Vergütung: 52.500,00 EUR",
    ) is None
    assert _financial_source_rejection(
        "costs.annual_cost",
        {"amount": 52500, "currency": "EUR", "period": "annual"},
        "Vergütung 52.500,00 EUR p.a.",
    ) is None
    assert _financial_source_rejection(
        "costs.annual_cost",
        {"amount": 52500, "currency": "EUR", "period": "annual"},
        "Einmalige Vergütung: 52.500,00 EUR",
    ) == "financial_period_not_explicit_in_evidence"
    assert _financial_source_rejection(
        "costs.annual_cost",
        {"amount": 52500, "currency": "EUR", "period": "annual"},
        "Die Vergütung ist nicht jährlich: 52.500,00 EUR",
    ) == "financial_period_not_explicit_in_evidence"
    assert _financial_source_rejection(
        "costs.annual_cost",
        {"amount": 52500, "currency": "EUR", "period": "annual"},
        "Jährlich 31.000 EUR; einmalig 52.500 EUR",
    ) == "financial_amount_not_bound_to_classification_evidence"
    assert _financial_source_rejection(
        "costs.annual_cost",
        {"amount": 52500, "currency": "USD", "period": "annual"},
        "Jährliche Vergütung: 52.500 EUR",
    ) == "financial_amount_not_bound_to_classification_evidence"


def test_total_contract_value_requires_explicit_total_label_and_matching_amount():
    assert _financial_source_rejection(
        "costs.total_contract_value",
        {"amount": 210000, "currency": "EUR"},
        "Gesamtvertragswert: 210.000 EUR",
    ) is None
    assert _financial_source_rejection(
        "costs.total_contract_value",
        {"amount": 210000, "currency": "EUR"},
        "Jährliche Vergütung: 52.500 EUR",
    ) == "financial_total_not_explicit_in_evidence"


def test_payment_pack_uses_bounded_keyword_pages_without_falling_back_to_entire_document():
    pages = [
        Page(
            page_number=number,
            width_pt=600,
            height_pt=800,
            text=("Zahlbar nach Rechnung in EUR pro Jahr" if number <= 3 else "Leistungsbeschreibung"),
            elements=[],
        )
        for number in range(1, 7)
    ]
    canonical = SimpleNamespace(pages=pages)
    signals = [{"kind": "money", "page": number} for number in range(1, 7)]

    selected = _pack_pages(
        ("payment",),
        canonical,
        signals,
        expand_keywords=True,
        page_limit=2,
        fallback_all=False,
    )

    assert selected == [1, 2]
    assert _pack_pages(
        ("payment",),
        SimpleNamespace(pages=pages[3:]),
        [],
        expand_keywords=True,
        page_limit=2,
        fallback_all=False,
    ) == []


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
    assert contract.costs.annual_cost is None
    assert any(
        row["field"] == "costs.annual_cost"
        and row["reason"] == "financial_period_not_explicit_in_evidence"
        for row in result.diagnostics["rejected_facts"]
    )
    assert contract.costs.variable_charges[0].amount.amount == 2226
    assert result.diagnostics["supported_count"] >= 8
    assert result.diagnostics["evidence_count"] >= 8
    assert result.diagnostics["stage_call_counts"]["semantic"] == 4


@pytest.mark.asyncio
async def test_malformed_optional_vision_response_falls_back_to_text(monkeypatch):
    monkeypatch.setattr("app.ai.harness.v3.visual_candidate_pages", lambda _doc: [1])

    class MalformedVisionProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            if schema["title"] == "VisualPageReading":
                return '{"page": 1, "visible_text": ['
            return await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )

    result = await DirectContractHarness(
        settings(), ai(MalformedVisionProvider())
    ).analyze(document(), page_image_loader=lambda _page: "test-image")

    assert result.contract is not None, result.error
    assert result.status.value == "partial"
    assert result.requires_review is True
    vision_call = next(
        call for call in result.diagnostics["calls"]
        if call.get("purpose") == "vision:1"
    )
    assert vision_call["failed"] is True
    assert vision_call["error_category"] == "malformed_json"
    assert any("Vision response on page 1" in issue for issue in result.diagnostics["issues"])


@pytest.mark.asyncio
async def test_malformed_semantic_pack_preserves_other_fact_groups():
    class MalformedCoreProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            if schema["title"] == "ProposedFactBatch" and "Extract the core contract facts" in text:
                return '{"facts": ['
            return await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )

    result = await DirectContractHarness(
        settings(), ai(MalformedCoreProvider())
    ).analyze(document())

    assert result.contract is not None, result.error
    assert result.status.value == "partial"
    assert result.requires_review is True
    # Commercial pack still ran: its per-call price is kept, while the bare
    # "8.000,00 EUR" quote is held back by the financial evidence gate.
    assert result.contract.costs.variable_charges[0].amount.amount == 2226.0
    assert result.contract.costs.annual_cost is None
    assert result.contract.equipment[0].device_name == "Impella\u00ae AIC System"
    core_call = next(
        call for call in result.diagnostics["calls"]
        if call.get("purpose") == "semantic:core:chunk1"
    )
    assert core_call["failed"] is True
    assert core_call["error_category"] == "malformed_json"
    assert any("Semantic core response" in issue for issue in result.diagnostics["issues"])


@pytest.mark.asyncio
async def test_harness_accepts_fully_fenced_vision_and_semantic_json(monkeypatch):
    monkeypatch.setattr("app.ai.harness.v3.visual_candidate_pages", lambda _doc: [1])

    class FencedProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            return f"```json\n{raw}\n```"

    result = await DirectContractHarness(settings(), ai(FencedProvider())).analyze(
        document(), page_image_loader=lambda _page: "test-image"
    )

    assert result.contract is not None, result.error
    assert not [call for call in result.diagnostics["calls"] if call.get("failed")]
    assert any(call.get("purpose") == "vision:1" for call in result.diagnostics["calls"])
    assert result.contract.identity.supplier == "ABIOMED Europe GmbH"
    # Commercial pack still ran: its per-call price is kept, while the bare
    # "8.000,00 EUR" quote is held back by the financial evidence gate.
    assert result.contract.costs.variable_charges[0].amount.amount == 2226.0
    assert result.contract.costs.annual_cost is None


@pytest.mark.asyncio
async def test_harness_retries_one_invalid_structured_response():
    class RecoverableMalformedCoreProvider(FakeProvider):
        def __init__(self):
            self.core_calls = 0

        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            if schema["title"] == "ProposedFactBatch" and "Extract the core contract facts" in text:
                self.core_calls += 1
                if self.core_calls == 1:
                    return "```json\n{\"facts\": [}\n```"
            return await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )

    provider = RecoverableMalformedCoreProvider()
    result = await DirectContractHarness(settings(), ai(provider)).analyze(document())

    assert result.contract is not None, result.error
    core_call = next(
        call for call in result.diagnostics["calls"]
        if call.get("purpose") == "semantic:core:chunk1"
    )
    assert core_call["failed"] is False
    assert core_call["succeeded"] is True
    assert core_call["structured_output_retry_count"] == 1
    assert core_call["first_error_category"] == "malformed_json"
    assert provider.core_calls == 2


@pytest.mark.asyncio
async def test_truncated_semantic_chunk_is_split_and_retried(monkeypatch):
    from app.ai.harness import v3 as harness_module

    original_pack_pages = harness_module._pack_pages

    def force_two_operations_pages(topics, canonical, source_signals, expand_keywords, **kwargs):
        if "equipment" in topics:
            return [1, 2]
        return original_pack_pages(topics, canonical, source_signals, expand_keywords, **kwargs)

    monkeypatch.setattr(harness_module, "_pack_pages", force_two_operations_pages)

    class TruncatedOperationsProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            if (
                schema["title"] == "ProposedFactBatch"
                and "Extract the operations contract facts" in text
                and "CONTRACT SOURCE (pages [1, 2])" in text
            ):
                self.last_done_reason = "length"
                self.last_usage = {"prompt_tokens": 3000, "completion_tokens": max_tokens}
                return await super().generate_request(
                    text, system, schema, max_tokens, context_tokens, images
                )
            self.last_done_reason = None
            return await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )

    result = await DirectContractHarness(
        settings(), ai(TruncatedOperationsProvider())
    ).analyze(document())

    assert result.contract is not None, result.error
    assert result.status.value == "partial"
    assert result.requires_review is True
    assert any(
        call.get("purpose") == "semantic:operations:chunk1a"
        for call in result.diagnostics["calls"]
    )
    assert any(
        call.get("purpose") == "semantic:operations:chunk1b"
        for call in result.diagnostics["calls"]
    )
    assert any("output was truncated" in issue for issue in result.diagnostics["issues"])


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
async def test_early_source_equipment_survives_later_standard_terms_pages():
    source = document()
    source.pages.append(Page(
        page_number=18,
        width_pt=600,
        height_pt=800,
        text="Allgemeine Geschäftsbedingungen\n§ 1 Allgemeine Geschäftsbedingungen",
        elements=[Element(
            element_id="agb-18",
            page=18,
            reading_order=0,
            text="Allgemeine Geschäftsbedingungen\n§ 1 Allgemeine Geschäftsbedingungen",
            type="paragraph",
            method="ocr",
        )],
    ))
    source.canonical_text = "\n".join(page.text for page in source.pages)

    result = await DirectContractHarness(settings(), ai()).analyze(source)

    assert result.contract is not None, result.error
    assert result.contract.equipment
    assert result.contract.equipment[0].device_name == "Impella® AIC System"
    assert result.contract.equipment[0].evidence.page == 3


@pytest.mark.asyncio
async def test_separate_equipment_facts_preserve_all_devices_and_own_sources():
    class TwoDeviceProvider(FakeProvider):
        async def generate_request(self, text, system, schema, max_tokens, context_tokens, images=None):
            if schema["title"] == "ProposedFactBatch" and "sla.service_hours" in text:
                return json.dumps({"facts": [
                    {"field": "equipment", "value": [{"device_name": "Impella\u00ae AIC System"}],
                     "page": 3, "quote": "Impella\u00ae AIC System", "applicability": "applicable"},
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
    source.canonical_text = "\n".join(page.text for page in source.pages)
    result = await DirectContractHarness(settings(), ai(TwoDeviceProvider())).analyze(source)
    assert result.contract is not None, result.error
    equipment = result.contract.equipment
    assert [item.device_name or item.system_name for item in equipment] == [
        "Impella\u00ae AIC System", "Accutron MR"
    ]
    assert [item.evidence.page for item in equipment] == [3, 7]


@pytest.mark.asyncio
async def test_repeated_identical_equipment_fact_does_not_duplicate_device():
    class RepeatedDeviceProvider(FakeProvider):
        async def generate_request(self, text, system, schema, max_tokens, context_tokens, images=None):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images=images
            )
            if schema["title"] == "ProposedFactBatch" and "sla.service_hours" in text:
                payload = json.loads(raw)
                equipment = next(
                    fact for fact in payload["facts"] if fact["field"] == "equipment"
                )
                payload["facts"].append(dict(equipment))
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(
        settings(), ai(RepeatedDeviceProvider())
    ).analyze(document())
    assert result.contract is not None, result.error
    assert len(result.contract.equipment) == 1
    assert result.contract.equipment[0].evidence.page == 3


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
    assert result.contract.costs.annual_cost is None
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
    assert "costs.annual_cost" not in accepted


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
    assert result.contract.costs.monthly_cost is None
    assert any(
        row["field"] == "costs.monthly_cost"
        and row["reason"] == "financial_period_not_explicit_in_evidence"
        for row in result.diagnostics["rejected_facts"]
    )


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
async def test_truncated_semantic_pack_keeps_other_grounded_pack_results_for_review():
    class PaymentTruncatingProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            if schema["title"] == "ProposedFactBatch" and text.startswith(
                "Extract the payment"
            ):
                self.last_done_reason = "length"
                self.last_usage = {
                    "prompt_tokens": 3000,
                    "completion_tokens": max_tokens,
                }
                return '{"facts":['
            self.last_done_reason = None
            self.last_usage = {}
            return await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )

    result = await DirectContractHarness(
        settings(), ai(PaymentTruncatingProvider())
    ).analyze(document())

    assert result.contract is not None, result.error
    assert result.contract.identity.supplier == "ABIOMED Europe GmbH"
    assert result.contract.equipment[0].device_name == "Impella® AIC System"
    assert result.status.value == "partial"
    assert result.requires_review is True
    assert result.diagnostics["stage_call_counts"]["semantic"] == 4
    assert any(
        "Semantic payment output remained truncated" in issue
        for issue in result.diagnostics["issues"]
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


def test_complete_schedule_total_requires_every_year_and_one_currency():
    rows = [
        {"period_index": year, "amount": {"amount": 52500.0, "currency": "EUR"}}
        for year in range(1, 5)
    ]
    assert _complete_scheduled_total(rows, expected_years=4) == 210000.0
    assert _complete_scheduled_total(rows[:-1], expected_years=4) is None
    conflicting = [*rows[:-1], {"period_index": 4, "amount": {"amount": 52500.0, "currency": "USD"}}]
    assert _complete_scheduled_total(conflicting, expected_years=4) is None


def test_retry_output_plan_uses_measured_budget():
    plan = _retry_output_plan("semantic:core", 3000, 8192, 1800)
    assert plan[0] is not None
    assert plan[1] == "output_budget_stage_retry"

    long_contract_plan = _retry_output_plan("semantic:payment", 21641, 32768, 1800)
    assert long_contract_plan[0] == 3200

    plan = _retry_output_plan("semantic:core", 7600, 8192, 1800)
    assert plan[0] is None


@pytest.mark.asyncio
async def test_explicit_annual_amount_is_accepted_with_matching_source_evidence():
    class AnnualQuoteProvider(FakeProvider):
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
                        fact["quote"] = "Jährliche Vergütung: 8.000,00 EUR"
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(
        settings(), ai(AnnualQuoteProvider())
    ).analyze(
        document_with_page_8_text(
            "Jährliche Vergütung: 8.000,00 EUR. "
            "Fixed per call: 2.226,00 EUR. 2.Jahr 8.000,00 EUR."
        )
    )

    assert result.contract is not None, result.error
    assert result.contract.costs.annual_cost.amount == 8000
    assert result.contract.costs.evidence.source_text == "Jährliche Vergütung: 8.000,00 EUR"


@pytest.mark.asyncio
async def test_annual_claim_does_not_borrow_period_from_another_amount_on_page():
    class CrossBoundAmountProvider(FakeProvider):
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
                        fact["value"] = {
                            "amount": 12000,
                            "currency": "EUR",
                            "period": "annual",
                        }
                        fact["quote"] = (
                            "Jährliche Vergütung: 5.000 EUR; "
                            "einmalige Zahlung: 12.000 EUR"
                        )
                return json.dumps(payload)
            return raw

    result = await DirectContractHarness(
        settings(), ai(CrossBoundAmountProvider())
    ).analyze(
        document_with_page_8_text(
            "Jährliche Vergütung: 5.000 EUR; einmalige Zahlung: 12.000 EUR"
        )
    )

    assert result.contract is not None, result.error
    assert result.contract.costs.annual_cost is None
    assert any(
        row["field"] == "costs.annual_cost"
        and row["reason"] == "financial_amount_not_bound_to_classification_evidence"
        for row in result.diagnostics["rejected_facts"]
    )
