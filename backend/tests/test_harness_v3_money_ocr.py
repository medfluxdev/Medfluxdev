"""Regression-Suite: OCR-tolerant Evidence Matching und Geld-Locator.

Deckt die drei Diagnose-Probleme des Frankfurt E2E ab:

1.  Context-Budget: `_effective_context` rahmt die effektive num_ctx innerhalb der
    Modellkapazitaet; genau EIN gebundener Retry bei `done_reason=length`, danach
    fail-closed.  Diagnosefelder: estimated_prompt_tokens, requested_context,
    output_reserve, effective_context, retry_reason, retry_count.
2.  OCR-tolerantes Evidence-Matching: Pipe-Separatoren, OCR-Typos, Waehrungs-
    Praefix/Suffix und Label/Wert-Naehe; Geld wird NIE allein ueber die Zahl
    gebunden.  Ambiguitaet -> unresolved/review.
3.  Page-Provenance: canonical page == PDF page ist kein "gesichert theoretisch",
    sondern wird gegen die reale Verteilung der Literale geprueft.
"""
import json
from types import SimpleNamespace

import pytest

from app.ai.harness.document import DocumentModel
from app.ai.harness.pipeline import _find_quote_tolerant
from app.ai.harness.source_signals import collect_source_signals, _MONEY_RE
from app.ai.harness.v3 import (
    _MONEY_FIELDS,
    _MONEY_LITERAL_RE,
    _effective_context,
    _locate_money_staged,
    _money_amount,
    _money_amounts_from_value,
    _money_label_phrase,
    _normalize_duration_payload,
    _normalize_fact_value,
    _normalize_row_amount,
    _retry_output_plan,
)
from app.core.config import Settings
from app.documents.intelligence.canonical import (
    DocumentIntelligenceResult,
    Element,
    Page,
    ProcessingProvenance,
)
from tests.test_harness_v3 import FakeProvider, ai, settings, document


def _ocr_pricing_document() -> DocumentIntelligenceResult:
    """Frankfurt-Stil PDF: Preis-Annex Seite 3 und 4 im OCR/Pipe-Layout.

    Seite 3: gestaffelte Jahrespreise + Einmalanteil + Einzelkomponenten.
    Seite 4: Jahresmengen-Tabelle (keine Betraege).
    """
    money_page = Page(
        page_number=3,
        width_pt=600,
        height_pt=800,
        text=(
            "1.Jahr |  |  |  | 0,00 EUR\n"
            "2.Jahr |  |  |  | 8.000,00 EUR\n"
            "3.Jahr |  |  |  | 8.000,00 EUR\n"
            "4.Jahr |  |  |  | 8.000,00 EUR\n"
            "Anteilige Zahlung für Investitionsgut: |  | € 12.000,00\n"
            "Kosten Einzelkomponeten: |  |  |  | € 9.500,00"
        ),
        elements=[
            Element(
                element_id="p3-costs",
                page=3,
                reading_order=i,
                text=(
                    "1.Jahr |  |  |  | 0,00 EUR\n"
                    "2.Jahr |  |  |  | 8.000,00 EUR\n"
                    "3.Jahr |  |  |  | 8.000,00 EUR\n"
                    "4.Jahr |  |  |  | 8.000,00 EUR\n"
                    "Anteilige Zahlung für Investitionsgut: |  | € 12.000,00\n"
                    "Kosten Einzelkomponeten: |  |  |  | € 9.500,00"
                )
                if i == 0
                else "",
                type="paragraph",
                method="ocr",
            )
            for i in range(1)
        ],
    )
    page4 = Page(
        page_number=4,
        width_pt=600,
        height_pt=800,
        text=(
            "PressureWire | 120 Stück | × 4 Jahr\n"
            "Dragonfly OpStar | 60 Stück | × 4 Jahr"
        ),
        elements=[
            Element(
                element_id="p4-qty",
                page=4,
                reading_order=0,
                text="PressureWire | 120 Stück | × 4 Jahr",
                type="paragraph",
                method="ocr",
            )
        ],
    )
    base = document()
    pages = [*base.pages]
    pages.append(money_page)
    pages.append(page4)
    return DocumentIntelligenceResult(
        document_id="ocr-pricing",
        source_sha256="d" * 64,
        canonical_text="\n".join(page.text or "" for page in pages),
        provenance=ProcessingProvenance(provider="docling"),
        pages=pages,
    )


class OcrPricingProvider(FakeProvider):
    """Propose money facts whose quotes carry OCR pipes + prefix currency."""

    async def generate_request(
        self, text, system, schema, max_tokens, context_tokens, images=None
    ):
        raw = await super().generate_request(
            text, system, schema, max_tokens, context_tokens, images
        )
        if schema["title"] != "ProposedFactBatch" or "costs.annual_cost" not in text:
            return raw
        payload = json.loads(raw)
        for fact in payload["facts"]:
            if fact["field"] == "costs.annual_cost":
                fact["value"] = {"amount": 8000, "currency": "EUR", "period": "annual"}
                fact["page"] = 3
                fact["quote"] = "2.Jahr | | | | 8.000,00 EUR"
                fact["applicability"] = "applicable"
        payload["facts"].extend(
            [
                {
                    "field": "payment.advance_payment",
                    "value": {
                        "amount": 12000,
                        "currency": "EUR",
                        "period": None,
                    },
                    "page": 3,
                    "quote": "Anteilige Zahlung für Investitionsgut: | € 12.000,00",
                    "applicability": "applicable",
                },
                {
                    "field": "costs.additional_costs",
                    "value": {
                        "amount": 9500,
                        "currency": "EUR",
                        "period": None,
                    },
                    "page": 3,
                    "quote": "Kosten Einzelkomponeten: | € 9.500,00",
                    "applicability": "applicable",
                },
                {
                    "field": "costs.material_cost",
                    "value": {"amount": 8000, "currency": "EUR", "period": None},
                    "page": 4,
                    "quote": "PressureWire | 120 Stück | × 4 Jahr",
                    "applicability": "applicable",
                },
            ]
        )
        return json.dumps(payload)


@pytest.mark.asyncio
async def test_money_facts_accepted_via_staged_locator_in_full_harness():
    from app.ai.harness import get_harness_class

    harness = get_harness_class(settings())
    result = await harness(settings(), ai(OcrPricingProvider())).analyze(
        _ocr_pricing_document()
    )
    assert result.contract is not None, result.error
    accepted = {row["field"]: row for row in result.diagnostics["accepted_facts"]}

    assert accepted["costs.annual_cost"]["page"] == 3
    assert "8.000,00 EUR" in accepted["costs.annual_cost"]["quote"]
    assert result.contract.costs.annual_cost.amount == 8000

    assert accepted["payment.advance_payment"]["page"] == 3
    assert "12.000,00" in accepted["payment.advance_payment"]["quote"]
    assert result.contract.payment.advance_payment.amount == 12000

    assert accepted["costs.additional_costs"]["page"] == 3
    assert "9.500,00" in accepted["costs.additional_costs"]["quote"]
    assert result.contract.costs.additional_costs.amount == 9500

    # Materialkosten existieren auf Seite 4 nicht -> evidence_not_located.
    rejected = {row["field"]: row["reason"] for row in result.diagnostics["rejected_facts"]}
    assert rejected["costs.material_cost"] == "evidence_not_located"


@pytest.mark.asyncio
async def test_money_fact_with_ocr_typo_in_quote_accepted_in_full_harness():
    src = (
        "Anteilige Zahlung für Investitionsgut: |  | € 12.000,00\n"
        "Kosten Einzelkomponeten: |  |  |  | € 9.500,00"
    )
    canonical = _page1_ocr(src)
    doc = canonical

    class TypoQuoteProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] != "ProposedFactBatch" or "costs.annual_cost" not in text:
                return raw
            payload = json.loads(raw)
            for fact in payload["facts"]:
                if fact["field"] == "costs.annual_cost":
                    fact["value"] = {"amount": 8000, "currency": "EUR", "period": "annual"}
                    fact["page"] = 3
                    fact["quote"] = "8.000,00 EUR"
                    fact["applicability"] = "applicable"
            payload["facts"].append(
                {
                    "field": "costs.additional_costs",
                    "value": {
                        "amount": 9500,
                        "currency": "EUR",
                        "period": None,
                    },
                    "page": 3,
                    "quote": "Kosten Einzelkomponenten: € 9.500,00",
                    "applicability": "applicable",
                }
            )
            return json.dumps(payload)

    from app.ai.harness import get_harness_class

    result = await get_harness_class(settings())(
        settings(), ai(TypoQuoteProvider())
    ).analyze(doc)
    assert result.contract is not None, result.error
    accepted = {row["field"]: row for row in result.diagnostics["accepted_facts"]}
    assert accepted["costs.additional_costs"]["page"] == 3
    assert "9.500,00" in accepted["costs.additional_costs"]["quote"]
    assert result.contract.costs.additional_costs.amount == 9500


@pytest.mark.asyncio
async def test_multiple_variable_charge_facts_are_merged_not_overwritten():
    # Zwei separate variable_charges-Fakten (180,00 + 200,00 auf derselben
    # Seite) sind beide belegt.  Der letzte Fakt darf den ersten NICHT
    # ueberschreiben, sonst geht einer der belegten Betraege still verloren.
    doc = _page1_ocr(
        "PressureWireX Kabelloser FFR-Druckmessdraht | € 180,00 "
        "Dragonfly OpStar OCT-Katheter Kit | € 200,00"
    )

    class TwoVariableChargesProvider(FakeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] != "ProposedFactBatch" or "costs.annual_cost" not in text:
                return raw
            payload = json.loads(raw)
            payload["facts"].append(
                {
                    "field": "costs.variable_charges",
                    "value": [
                        {
                            "label": "PressureWireX",
                            "amount": {"amount": 180, "currency": "EUR"},
                            "unit": "per_call",
                            "condition": None,
                        }
                    ],
                    "page": 3,
                    "quote": "PressureWireX Kabelloser FFR-Druckmessdraht | € 180,00",
                    "applicability": "applicable",
                }
            )
            payload["facts"].append(
                {
                    "field": "costs.variable_charges",
                    "value": [
                        {
                            "label": "Dragonfly OpStar",
                            "amount": {"amount": 200, "currency": "EUR"},
                            "unit": "per_call",
                            "condition": None,
                        }
                    ],
                    "page": 3,
                    "quote": "Dragonfly OpStar OCT-Katheter Kit | € 200,00",
                    "applicability": "applicable",
                }
            )
            return json.dumps(payload)

    from app.ai.harness import get_harness_class

    result = await get_harness_class(settings())(
        settings(), ai(TwoVariableChargesProvider())
    ).analyze(doc)
    assert result.contract is not None, result.error
    amounts = {
        round(vc.amount.amount, 2)
        for vc in result.contract.costs.variable_charges
    }
    assert 180.0 in amounts
    assert 200.0 in amounts


# ---------------------------------------------------------------------------
# 2. Geldformate und OCR-Toleranz (Unit-Level)
# ---------------------------------------------------------------------------


def test_money_literal_re_matches_prefix_and_suffix_forms():
    for literal in ("€ 12.000,00", "12.000,00 €", "12.000,00 EUR", "EUR 12.000,00"):
        match = _MONEY_LITERAL_RE.search(literal)
        assert match is not None, literal
        assert _money_amount(match.group(0)) == 12000.0
    # keine Waehrung -> kein Geldliteral
    assert _MONEY_LITERAL_RE.search("480 Stück") is None
    assert _MONEY_LITERAL_RE.search("120 Stück × 4 Jahr") is None
    assert _MONEY_LITERAL_RE.search("01.04.2025") is None


def test_money_re_in_source_signals_matches_prefix_currency():
    text = "Anteilige Zahlung für Investitionsgut: € 12.000,00!"
    matches = _MONEY_RE.findall(text)
    assert matches
    assert any(_money_amount(m) == 12000.0 for m in matches)


def test_money_amounts_from_value_collects_nested_amounts():
    value = {
        "scheduled": [
            {"amount": {"amount": 9500.0, "currency": "EUR"}},
            {"amount": {"amount": 2395.0, "currency": "EUR"}},
        ],
        "once": {"amount": 12000.0},
        "free_text": "4.500,00 EUR",
    }
    amounts = _money_amounts_from_value(value)
    assert 9500.0 in amounts
    assert 2395.0 in amounts
    assert 12000.0 in amounts
    assert 4500.0 in amounts


def test_money_label_phrase_strips_amount_and_separators():
    phrase = _money_label_phrase("Anteilige Zahlung für Investitionsgut: | € 12.000,00")
    assert "Anteilige" in phrase
    assert "Zahlung" in phrase
    assert "Investitionsgut" in phrase
    assert "12.000,00" not in phrase
    assert "€" not in phrase


def _page1_ocr(*texts: str, page=3) -> DocumentIntelligenceResult:
    elements = [
        Element(
            element_id=f"el-{page}-{idx}",
            page=page,
            reading_order=idx,
            text=text,
            type="paragraph",
            method="ocr",
        )
        for idx, text in enumerate(texts)
    ]
    return DocumentIntelligenceResult(
        document_id="money-test",
        source_sha256="b" * 64,
        canonical_text="\n".join(texts),
        provenance=ProcessingProvenance(provider="docling"),
        pages=[
            Page(
                page_number=page,
                width_pt=600,
                height_pt=800,
                text="\n".join(texts),
                elements=elements,
            )
        ],
    )


def test_locate_money_staged_pipe_separators_prefix_currency():
    canonical = _page1_ocr(
        "Kosten Einzelkomponeten: |  |  |  | € 9.500,00",
        "Anteilige Zahlung für Investitionsgut: |  | € 12.000,00",
    )
    document_model = DocumentModel.build(canonical)
    page_blocks = document_model.pages_blocks.get(3, [])
    found = _locate_money_staged(
        document_model,
        page_blocks,
        "Kosten Einzelkomponeten: | € 9.500,00",
        [9500.0],
    )
    assert found is not None
    block, literal = found
    assert literal == "€ 9.500,00"
    assert block.page == 3


def test_locate_money_staged_ocr_typo_in_label_tolerated():
    canonical = _page1_ocr(
        "Kosten Einzelkomponeten: |  |  |  | € 9.500,00",
    )
    document_model = DocumentModel.build(canonical)
    found = _locate_money_staged(
        document_model,
        document_model.pages_blocks.get(3, []),
        "Kosten Einzelkomponenten: € 9.500,00",
        [9500.0],
    )
    assert found is not None
    assert found[1] == "€ 9.500,00"


def test_locate_money_staged_suffix_currency_and_linebreak():
    canonical = _page1_ocr(
        "Kosten Einzelkomponenten:\n"
        "9.500,00 EUR",
    )
    document_model = DocumentModel.build(canonical)
    found = _locate_money_staged(
        document_model,
        document_model.pages_blocks.get(3, []),
        "Kosten Einzelkomponenten: | 9.500,00 EUR",
        [9500.0],
    )
    assert found is not None
    assert found[1] == "9.500,00 EUR"


def test_locate_money_staged_wrong_page_rejected():
    canonical = _page1_ocr(
        "Kosten Einzelkomponenten: € 9.500,00", page=3
    )
    document_model = DocumentModel.build(canonical)
    # Auf der falschen Seite (page 4) existiert der Betrag nicht.
    found = _locate_money_staged(
        document_model,
        document_model.pages_blocks.get(4, []),
        "Kosten Einzelkomponenten: € 9.500,00",
        [9500.0],
    )
    assert found is None


def test_locate_money_staged_ambiguous_amounts_rejected():
    canonical = _page1_ocr(
        "Position A: € 9.500,00",
        "Position B: € 9.500,00",
    )
    document_model = DocumentModel.build(canonical)
    # gleicher Betrag zweimal ohne unterscheidbares Label -> ambiguous -> None
    found = _locate_money_staged(
        document_model,
        document_model.pages_blocks.get(3, []),
        "Position X: € 9.500,00",
        [9500.0],
    )
    assert found is None


def test_locate_money_staged_wrong_amount_never_bound():
    canonical = _page1_ocr("Kosten Einzelkomponenten: € 9.500,00")
    document_model = DocumentModel.build(canonical)
    found = _locate_money_staged(
        document_model,
        document_model.pages_blocks.get(3, []),
        "Kosten Einzelkomponenten: € 8.000,00",
        [8000.0],
    )
    assert found is None


def test_find_quote_tolerant_pipe_and_typo():
    src = "Kosten Einzelkomponeten: |  |  |  | € 9.500,00"
    hit = _find_quote_tolerant(src, "Kosten Einzelkomponeten: | € 9.500,00")
    assert hit is not None
    hit = _find_quote_tolerant(src, "Kosten Einzelkomponenten: € 9.500,00")
    assert hit is not None
    # fehlendes Wort -> fail-closed
    assert _find_quote_tolerant(src, "Kosten Komponeten: € 9.500,00") is None
    assert _find_quote_tolerant(src, "Fremde Zeile: € 9.500,00") is None
    # Reihenfolge vertauscht -> fail-closed
    assert _find_quote_tolerant(src, "€ 9.500,00 Kosten Einzelkomponeten") is None


# ---------------------------------------------------------------------------
# 1. Context-Budget (Unit-Level)
# ---------------------------------------------------------------------------


def test_effective_context_keeps_requested_when_budget_is_enough():
    eff = _effective_context(
        prompt_tokens=3000, output_tokens=1800, requested_context=8192,
        model_capacity=262144, image_reserve=0,
    )
    assert eff == 8192


def test_effective_context_never_exceeds_operator_budget():
    # Das konfigurierte Kontextbudget ist ein Speicherbudget: eine pessimistische
    # Prompt-Schaetzung darf num_ctx nicht anheben, sonst wird der KV-Cache auf
    # lokaler GPU mit CPU-Teilauslagerung bezahlt (langsamer, instabil).
    eff = _effective_context(
        prompt_tokens=7865, output_tokens=1800, requested_context=8192,
        model_capacity=262144, image_reserve=0,
    )
    assert eff == 8192


def test_effective_context_grows_only_when_explicitly_allowed():
    eff = _effective_context(
        prompt_tokens=7865, output_tokens=1800, requested_context=8192,
        model_capacity=262144, image_reserve=0, allow_growth=True,
    )
    assert eff > 8192
    assert eff <= 262144
    assert eff == 7865 + 1800 + 512


def test_effective_context_negative_margin():
    # prompt + output + reserve > Modellkapazitaet -> auf Kapazitaet begrenzt
    eff = _effective_context(
        prompt_tokens=200000, output_tokens=1800, requested_context=8192,
        model_capacity=262144, image_reserve=0,
    )
    assert eff <= 262144
    assert eff == 8192
    grown = _effective_context(
        prompt_tokens=200000, output_tokens=1800, requested_context=8192,
        model_capacity=262144, image_reserve=0, allow_growth=True,
    )
    assert grown == 200000 + 1800 + 512
    assert grown <= 262144


def test_effective_context_small_context_model_capped():
    eff = _effective_context(
        prompt_tokens=200000, output_tokens=1800, requested_context=8192,
        model_capacity=8192, image_reserve=0,
    )
    assert eff <= 8192


def test_effective_context_ignores_image_reserve_without_images():
    eff = _effective_context(
        prompt_tokens=1000, output_tokens=500, requested_context=8192,
        model_capacity=262144, image_reserve=0,
    )
    assert eff == 8192


def test_retry_output_plan_reasons_are_explicit():
    enough = _retry_output_plan("semantic:core", 3000, 8192, 1800)
    assert enough[0] is not None
    assert enough[1] == "output_budget_stage_retry"
    negative = _retry_output_plan("semantic:core", 7600, 8192, 1800)
    assert negative[0] is None
    assert negative[1] == "output_retry_not_performed"


# ---------------------------------------------------------------------------
# 3. Page-Provenance: canonical page == PDF page Mapping
# ---------------------------------------------------------------------------


def test_canonical_page_numbers_are_one_based_and_blocks_keep_page():
    # Eine PDF-Seite erzeugt genau einen canonical Page mit page_number=1.
    # Der Block-Eigentümer muss dieselbe 1-basierte Nummer tragen wie die Seite.
    doc = document()
    model = DocumentModel.build(doc)
    assert model.pages_blocks.keys() == {1, 3, 5, 7, 8}
    for page_number in model.pages_blocks:
        page = next(
            (p for p in doc.pages if p.page_number == page_number), None
        )
        assert page is not None
        for block in model.pages_blocks[page_number]:
            assert block.page == page_number


def test_provenance_uses_pdf_page_index_not_zero_based():
    # Ground-Truth Annahme im Diagnose-Bericht lautete "supplier page 1/2".
    # Der Beweis: canonical page 1 enthält den Lieferanten UND Vertragspartner-
    # Stem; page 2 (hier simuliert) muss zusätzlich den Kundennamen tragen.
    # Diese Assertion prueft die *Abbildung* page_number -> Block, nicht die
    # inhaltliche Seite des echten PDF (dazu der E2E-Lauf).
    page = Page(
        page_number=2,
        width_pt=600,
        height_pt=800,
        text="Krankenhaus Nordwest GmbH",
        elements=[
            Element(
                element_id="p2",
                page=2,
                reading_order=0,
                text="Krankenhaus Nordwest GmbH",
                type="paragraph",
                method="ocr",
            )
        ],
    )
    canonical = DocumentIntelligenceResult(
        document_id="provenance-test",
        source_sha256="c" * 64,
        canonical_text="Krankenhaus Nordwest GmbH",
        provenance=ProcessingProvenance(provider="docling"),
        pages=[page],
    )
    model = DocumentModel.build(canonical)
    assert model.pages_blocks[2][0].page == 2
    assert model.pages_blocks[2][0].id == "p2:p2"


def test_money_fields_never_bind_by_number_alone():
    # Damit der Locator nicht "Nur-Zahl"-Fakten durchreicht, muss ein facts-
    # Wert ohne Waehrungsliteral auf derselben Seite kein Geld-Signal liefern.
    canonical = _page1_ocr("Anteilige Zahlung für Investitionsgut: € 12.000,00")
    signals = collect_source_signals(DocumentModel.build(canonical))
    money = [s for s in signals if s["kind"] == "money"]
    assert len(money) == 1
    assert money[0]["value"] == "€ 12.000,00"


def test_normalize_row_amount_preserves_flat_currency_string():
    # Qwen liefert Betraege in Zeilen teils flach statt als Money-Objekt:
    # {"amount": "9.500,00 EUR"} bzw. {"amount": "9500", "currency": "EUR"}.
    # Diese waren zuvor leer ({}), wodurch der belegte Betrag verschwand.
    assert _normalize_row_amount("9.500,00 EUR", None) == {
        "amount": 9500.0,
        "currency": "EUR",
        "period": None,
    }
    assert _normalize_row_amount("9500", "EUR") == {
        "amount": 9500.0,
        "currency": "EUR",
        "period": None,
    }
    assert _normalize_row_amount(9500, "EUR") == {
        "amount": 9500.0,
        "currency": "EUR",
        "period": None,
    }
    assert _normalize_row_amount(
        {"amount": "9500", "currency": "EUR"}, None
    ) == {"amount": 9500.0, "currency": "EUR", "period": None}
    assert _normalize_row_amount("nicht lesbar", "EUR") == "nicht lesbar"


def test_scheduled_prices_normalization_preserves_amounts():
    normalized = _normalize_fact_value(
        "costs.scheduled_prices",
        [
            {
                "period_index": 1,
                "amount": "9.500,00 EUR",
                "condition": None,
            }
        ],
    )
    assert normalized[0]["amount"]["amount"] == 9500.0
    assert normalized[0]["amount"]["currency"] == "EUR"


def test_variable_charges_normalization_preserves_amounts():
    normalized = _normalize_fact_value(
        "costs.variable_charges",
        [
            {
                "label": "PressureWire",
                "amount": {"amount": "180,00", "currency": "EUR"},
                "unit": "per_unit",
            }
        ],
    )
    assert normalized[0]["amount"]["amount"] == 180.0
    assert normalized[0]["amount"]["currency"] == "EUR"


def test_duration_literal_value_shape_normalized():
    # Qwen semantic nutzt {"duration_type": "months",
    # "literal_value": "48 Monaten"} - zuvor zu {} geleert.
    normalized = _normalize_duration_payload(
        {"duration_type": "months", "literal_value": "48 Monaten"}
    )
    assert normalized == {"value": 48, "unit": "months"}

    normalized = _normalize_duration_payload(
        {"duration_type": "years", "literal_value": "4 Jahre", "amount": 4}
    )
    assert normalized == {"value": 4, "unit": "years"}


def test_date_literal_value_shape_normalized():
    # Qwen semantic nutzt {"date_type": "start", "literal_value": "04.06.2025"}
    # - zuvor zu {"requires_review": false} geleert und das belegte Datum
    # verloren (start/end date = null im Contract, obwohl akzeptiert).
    normalized = _normalize_fact_value(
        "dates.start_date",
        {"date_type": "start", "literal_value": "04.06.2025"},
    )
    assert normalized == {
        "date": "2025-06-04",
        "condition": None,
        "requires_review": False,
    }
    normalized = _normalize_fact_value(
        "dates.end_date",
        {"date_type": "end", "literal_value": "03.06.2029"},
    )
    assert normalized == {
        "date": "2029-06-03",
        "condition": None,
        "requires_review": False,
    }