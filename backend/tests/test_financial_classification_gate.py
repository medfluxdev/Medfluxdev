import json
from types import SimpleNamespace

import pytest

from app.ai.harness.v3 import (
    _financial_classification_verified,
)
from app.ai.harness.visual_first import Observation, Reconciled
from app.ai.schemas import ModelCapabilities, ModelDescriptor
from app.core.config import Settings
from app.documents.intelligence.canonical import (
    DocumentIntelligenceResult,
    Element,
    Page,
    ProcessingProvenance,
)


def settings(**overrides):
    base = {
        "harness_engine": "v3",
        "harness_max_calls": 16,
        "harness_output_tokens": 1800,
        "harness_context_tokens": 8192,
        "harness_vision_max_calls": 2,
        "visual_first_experiment_enabled": True,
        "visual_first_max_pages": 9,
        "visual_first_max_reviews": 0,
        "harness_vision_warmup_enabled": False,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def document(page3_text: str):
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
            page_number=2,
            width_pt=600,
            height_pt=800,
            text="Allgemeine Bedingungen und Servicezeiten.",
            elements=[
                Element(
                    element_id="p2",
                    page=2,
                    reading_order=0,
                    text="Allgemeine Bedingungen und Servicezeiten.",
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
        Page(
            page_number=3,
            width_pt=600,
            height_pt=800,
            text=page3_text,
            elements=[
                Element(
                    element_id="p3",
                    page=3,
                    reading_order=0,
                    text=page3_text,
                    type="paragraph",
                    method="ocr",
                )
            ],
        ),
    ]
    return DocumentIntelligenceResult(
        document_id="gate-test",
        source_sha256="b" * 64,
        canonical_text="\n".join(page.text for page in pages),
        provenance=ProcessingProvenance(provider="docling"),
        pages=pages,
    )


ANNUAL_FACT = {
    "field": "costs.annual_cost",
    "value": "12.000,00 EUR",
    "page": 3,
    "applicability": "applicable",
    "period": "annual",
}

IDENTITY_FACTS = [
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
]


PROPOSAL = {"field": "costs.annual_cost", "value": "12.000,00 EUR", "page": 3}


class GateProvider:
    """Canned provider: configurable vision claims (default: one un-corroborated
    page-3 vision observation) plus canned semantic money + identity facts."""

    supports_structured_output = True
    last_done_reason = None
    last_usage = {}

    def __init__(self, annual_facts, vision_claims=None):
        self.annual_facts = (
            annual_facts if isinstance(annual_facts, list) else [annual_facts]
        )
        if vision_claims is None:
            vision_claims = [
                {
                    "page": 3,
                    "label": "Einmalige Zusatzkosten",
                    "value": "12.000 EUR",
                    "quote": "Einmalige Zusatzkosten 12.000 EUR",
                    "region": [10, 10, 20, 20],
                    "uncertain": False,
                }
            ]
        self.vision_claims = vision_claims

    async def generate_request(
        self, text, system, schema, max_tokens, context_tokens, images=None
    ):
        title = schema["title"]
        if title == "VisionClaims":
            if "Page=3." in text:
                return json.dumps({"claims": self.vision_claims})
            return json.dumps({"claims": []})
        if title == "ProposedFactBatch":
            if "commercial" in text or "payment" in text:
                return json.dumps({"facts": self.annual_facts})
            return json.dumps({"facts": IDENTITY_FACTS})
        raise AssertionError(f"Unexpected schema title {title}")


def ai(provider):
    async def runtime():
        return provider, ModelDescriptor(
            provider_id="mock",
            model_id="qwen3-vl:8b-instruct",
            context_length=8192,
            capabilities=ModelCapabilities(text=True, vision=True),
        )

    return SimpleNamespace(harness_runtime=runtime)


@pytest.mark.asyncio
async def test_uncorroborated_annual_without_period_anchor_cannot_enter_annual_cost():
    from app.ai.harness.v3 import HarnessV3

    # Page 3 carries the literal "12.000 EUR" but WITHOUT any recurring-period
    # qualifier. The visual-first reconciliation cannot corroborate it (vision
    # observation is vision_only). An ambiguous amount must NOT become an
    # authoritative annual obligation - even though the whole analysis will be
    # requires_review anyway.
    annual_fact = dict(ANNUAL_FACT)
    annual_fact["quote"] = "Verguetung 12.000 EUR pauschal."
    provider = GateProvider([annual_fact])
    result = await HarnessV3(settings(), ai=ai(provider)).analyze(
        document("Verguetung 12.000 EUR pauschal."),
        original_page_loader=lambda p: ("iVBORw0KGgo=" if p == 3 else "iVBORw0KGgo="),
    )
    assert result.contract is not None, result.error
    rejected = [
        r for r in result.diagnostics["rejected_facts"]
        if r.get("reason") == "financial_classification_unverified"
    ]
    assert rejected, result.diagnostics["rejected_facts"]
    assert all(r["field"] == "costs.annual_cost" and r["page"] == 3
               for r in rejected)
    # The authoritative model carries NO annual obligation from the ambiguous
    # figure; downstream calculation/forecast/search/analytics see None.
    assert result.contract.costs.annual_cost is None
    assert result.contract.costs.monthly_cost is None
    assert result.contract.costs.quarterly_cost is None
    assert result.contract.costs.semi_annual_cost is None
    assert result.contract.costs.maintenance_fee is None
    assert not any(
        f.get("field") == "costs.annual_cost"
        for f in result.diagnostics["accepted_facts"]
    )
    assert result.requires_review is True
    assert any(
        "Financial classification requires manual review" in i
        for i in result.diagnostics["issues"]
    )


@pytest.mark.asyncio
async def test_annual_period_anchor_accepts_uncorroborated_amount_into_annual_cost():
    from app.ai.harness.v3 import HarnessV3

    # Deterministic classification evidence: the quote itself carries "Jaehrliche"
    # (recurring annual anchor) AND exactly the proposed amount. Independent of
    # whether the visual row was corroborated, the amount is proven to be an
    # annual obligation and may enter annual_cost.
    annual_fact = dict(ANNUAL_FACT)
    annual_fact["quote"] = "Jaehrliche Verguetung 12.000 EUR."
    provider = GateProvider([annual_fact])
    result = await HarnessV3(settings(), ai=ai(provider)).analyze(
        document("Jaehrliche Verguetung 12.000 EUR."),
        original_page_loader=lambda p: "iVBORw0KGgo=",
    )
    assert result.contract is not None, result.error
    assert not any(
        r.get("reason") == "financial_classification_unverified"
        for r in result.diagnostics["rejected_facts"]
    )
    annual = result.contract.costs.annual_cost
    assert annual is not None and float(annual.amount) == 12000.0


@pytest.mark.asyncio
async def test_same_page_annual_5k_and_one_time_12k_only_annual_bound():
    from app.ai.harness.v3 import HarnessV3

    # Real same-page scenario: an annual 5.000 EUR row and an one-time 12.000
    # EUR row. The semantic model proposes BOTH as annual_cost. Only the 5.000
    # fact is bound to its own annual clause; the 12.000 one-time amount must
    # fail the classification gate and stay review-only.
    page3_text = (
        "Jaehrliche Verguetung: 5.000 EUR pro Jahr. "
        "Einmalige Zusatzkosten: 12.000 EUR pauschal."
    )
    facts = [
        PROPOSAL | {"value": "5.000 EUR",
                    "quote": "Jaehrliche Verguetung: 5.000 EUR pro Jahr."},
        PROPOSAL | {"value": "12.000 EUR",
                    "quote": "Einmalige Zusatzkosten: 12.000 EUR pauschal."},
    ]
    claims = [
        {"page": 3, "label": "Jaehrliche Verguetung", "value": "5.000 EUR",
         "quote": "Jaehrliche Verguetung: 5.000 EUR pro Jahr.",
         "region": [10, 10, 20, 20], "uncertain": False},
        {"page": 3, "label": "Einmalige Zusatzkosten", "value": "12.000 EUR",
         "quote": "Einmalige Zusatzkosten: 12.000 EUR pauschal.",
         "region": [30, 30, 40, 40], "uncertain": False},
    ]
    result = await HarnessV3(settings(), ai=ai(GateProvider(facts, claims))).analyze(
        document(page3_text),
        original_page_loader=lambda p: "iVBORw0KGgo=",
    )
    assert result.contract is not None, result.error
    annual = result.contract.costs.annual_cost
    assert annual is not None and float(annual.amount) == 5000.0
    # The one-time 12.000 must never enter annual_cost.
    assert not any(
        f.get("field") == "costs.annual_cost" and "12.000" in str(f.get("value"))
        for f in result.diagnostics["accepted_facts"]
    )
    rejected = [
        r for r in result.diagnostics["rejected_facts"]
        if r.get("reason") == "financial_classification_unverified"
    ]
    assert rejected, result.diagnostics["rejected_facts"]
    assert all(r["field"] == "costs.annual_cost" and r["page"] == 3
               for r in rejected)
    assert result.requires_review is True


def _vision_only_rows(field_page=3, status="vision_only", label="Einmalige Zusatzkosten",
                      quote="Einmalige Zusatzkosten 12.000 EUR", value="12.000 EUR"):
    obs = Observation(
        page=field_page, source="vision", label=label,
        value=value, quote=quote,
        region=(10, 10, 20, 20),
    )
    return [Reconciled(field_page, obs.label, obs.value, status, [obs])]


def test_classification_predicate_decision_matrix():
    annual = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                             quote="Verguetung 12.000 EUR pauschal.")
    anchored = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                               quote="Jaehrliche Verguetung 12.000 EUR.")
    quarterly_quote = SimpleNamespace(field="costs.annual_cost", page=3,
                                      value="12.000 EUR",
                                      quote="Quartalsweise 12.000 EUR.")
    monthly = SimpleNamespace(field="costs.monthly_cost", page=3, value="12.000 EUR",
                              quote="pauschal 12.000 EUR")
    monthly_anchored = SimpleNamespace(field="costs.monthly_cost", page=3,
                                       value="12.000 EUR",
                                       quote="pro Monat 12.000 EUR")
    maintenance = SimpleNamespace(field="costs.maintenance_fee", page=3,
                                  value="12.000 EUR", quote="pauschal 12.000 EUR")
    maintenance_anchored = SimpleNamespace(field="costs.maintenance_fee", page=3,
                                           value="12.000 EUR",
                                           quote="Wartung 12.000 EUR")
    identity = SimpleNamespace(field="identity.supplier", page=1,
                               value="ABIOMED Europe GmbH",
                               quote="ABIOMED Europe GmbH")

    # Legacy/Hybrid-Pfad ohne Visual-First bleibt unbelastet.
    assert _financial_classification_verified(annual, []) is True
    # Nicht-Periode-Felder sind nie betroffen (auch mit Visual-First-Zeilen).
    assert _financial_classification_verified(identity, _vision_only_rows(1)) is True
    # Keine passende Zeile auf der Zielseite: ein Periodenwort einer anderen
    # Seite ist KEIN Beweis fuer diesen Betrag.
    assert _financial_classification_verified(
        annual, _vision_only_rows(2)) is False
    # Unbestatigte visuelle Evidenz + kein Periodenanker: abgelehnt.
    assert _financial_classification_verified(annual, _vision_only_rows()) is False
    assert _financial_classification_verified(
        annual, _vision_only_rows(status="disputed")) is False
    assert _financial_classification_verified(
        annual, _vision_only_rows(status="uncertain")) is False
    # Periodenanker + genau passender Betrag im Zitat genuegt.
    assert _financial_classification_verified(anchored, _vision_only_rows()) is True
    # Falscher Periodenanker fuer dieses Feld genuegt nicht.
    assert _financial_classification_verified(quarterly_quote, _vision_only_rows()) is False
    assert _financial_classification_verified(monthly, _vision_only_rows()) is False
    assert _financial_classification_verified(monthly_anchored, _vision_only_rows()) is True
    assert _financial_classification_verified(maintenance, _vision_only_rows()) is False
    assert _financial_classification_verified(maintenance_anchored, _vision_only_rows()) is True
    # Korrobation OHNE Periodenanker (z.B. "Pauschale" von OCR+Vision bezeugt)
    # beweist nur den Literal, nicht die Kostenperiode -> Ablehnung.
    assert _financial_classification_verified(
        annual, _vision_only_rows(status="corroborated")) is False
    # Korrobation MIT Periodenanker in Label oder Zitat belegt die Klasse - und
    # die Zeile muss exakt den vorgeschlagenen Betrag tragen.
    assert _financial_classification_verified(
        annual, _vision_only_rows(status="corroborated",
                                  label="Jaehrliche Verguetung")) is True
    assert _financial_classification_verified(
        annual, _vision_only_rows(status="corroborated",
                                  quote="Jaehrliche Verguetung 12.000 EUR")) is True
    # Auch bei korroborierter Seite entscheidet zuerst das Fakt-Zitat.
    assert _financial_classification_verified(anchored, _vision_only_rows()) is True


def test_anchor_on_other_amount_in_same_quote_never_binds():
    # The quote carries the annual anchor, but it belongs to the 5.000 EUR
    # clause; the proposed 12.000 is the one-time amount. The matcher must not
    # bind the period to the other amount in the same quote.
    proposed = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                               quote="Jaehrliche Verguetung 5.000 EUR; einmalig 12.000 EUR")
    assert _financial_classification_verified(proposed, _vision_only_rows()) is False


def test_explicit_one_time_and_special_price_labels_block_wrong_recurring_or_total_roles():
    investment_as_annual = SimpleNamespace(
        field="costs.annual_cost",
        page=3,
        value="12.000,00 EUR",
        quote=(
            "Anteilige Zahlung für Investitionsgut: 12.000,00 EUR. "
            "Die Zahlung wird zu Beginn der Vertragslaufzeit fällig."
        ),
    )
    special_stk_as_total = SimpleNamespace(
        field="costs.total_contract_value",
        page=3,
        value="2.395,00 EUR",
        quote=(
            "Sonderkondition Sicherheitstechnische Kontrolle: "
            "Sonderpreis in Höhe von 2.395,00 EUR"
        ),
    )
    unlabelled_amount_as_total = SimpleNamespace(
        field="costs.total_contract_value",
        page=3,
        value="9.500,00 EUR",
        quote="€ 9.500,00",
    )
    explicitly_labelled_total = SimpleNamespace(
        field="costs.total_contract_value",
        page=3,
        value="21.500,00 EUR",
        quote="Gesamtpreis netto: 21.500,00 EUR",
    )

    assert _financial_classification_verified(investment_as_annual, []) is False
    assert _financial_classification_verified(special_stk_as_total, []) is False
    assert _financial_classification_verified(unlabelled_amount_as_total, []) is False
    assert _financial_classification_verified(explicitly_labelled_total, []) is True


def test_scheduled_price_requires_year_and_matching_amount_in_same_quote():
    false_schedule = SimpleNamespace(
        field="costs.scheduled_prices",
        page=3,
        value=[{
            "period_index": 1,
            "amount": {"amount": 2395.0, "currency": "EUR"},
        }],
        quote="Sonderpreis für die Sicherheitstechnische Kontrolle (STK): 2.395,00 EUR",
    )
    grounded_schedule = SimpleNamespace(
        field="costs.scheduled_prices",
        page=1,
        value=[{
            "period_index": 1,
            "amount": {"amount": 52500.0, "currency": "EUR"},
        }],
        quote="1. Jahr Gesamtpreis netto | 52.500,00 EUR",
    )

    assert _financial_classification_verified(false_schedule, []) is False
    assert _financial_classification_verified(grounded_schedule, []) is True


def test_two_amounts_same_page_do_not_cross_bind_periodicity():
    # An unrelated corroborated row (matched ANNUAL label but a DIFFERENT amount)
    # must not bind a period to the proposed one-time amount.
    proposed = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                               quote="Einmalig 12.000 EUR")
    annual_obs = Observation(page=3, source="vision", label="Jaehrliche Verguetung",
                             value="5.000 EUR", quote="Jaehrliche Verguetung 5.000 EUR",
                             region=(1, 1, 2, 2))
    unrelated = Reconciled(3, annual_obs.label, annual_obs.value,
                           "corroborated", [annual_obs])
    assert not _financial_classification_verified(
        proposed, [unrelated],
        resolved_page=3)
    # Even with the period word in the proposed quote, two amounts keep it
    # ambiguous: the anchor cannot be assigned to either literal.
    proposed2 = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                                quote="Jaehrliche Verguetung 5.000 EUR; einmalig 12.000 EUR")
    assert not _financial_classification_verified(proposed2, [unrelated],
                                                  resolved_page=3)


def test_matching_corroborated_row_must_carry_period_and_amount():
    proposed = SimpleNamespace(field="costs.annual_cost", page=3,
                               value="12.000 EUR", quote="12.000 EUR")
    matching = _vision_only_rows(status="corroborated",
                                 label="Jaehrliche Verguetung",
                                 quote="Jaehrliche Verguetung 12.000 EUR")
    assert _financial_classification_verified(proposed, matching)
    matching[0].value = "5.000 EUR"
    assert not _financial_classification_verified(proposed, matching)


def _corrob_row(label, value, quote):
    obs = Observation(page=3, source="vision", label=label, value=value,
                      quote=quote, region=(1, 1, 2, 2))
    return Reconciled(3, label, value, "corroborated", [obs])


def test_multiple_amounts_and_periods_only_correct_binding():
    # One page carries three different amounts, each with its own periodicity.
    rows = [
        _corrob_row("Monatliche Wartung", "850 EUR", "Monatliche Wartung 850 EUR"),
        _corrob_row("Quartalsweise Verguetung", "3.000 EUR",
                    "Quartalsweise Verguetung 3.000 EUR"),
        _corrob_row("Jaehrliche Verguetung", "12.000 EUR",
                    "Jaehrliche Verguetung 12.000 EUR"),
    ]
    monthly = SimpleNamespace(field="costs.monthly_cost", page=3, value="850 EUR",
                              quote="Wartung 850 EUR")
    quarterly = SimpleNamespace(field="costs.quarterly_cost", page=3, value="3.000 EUR",
                                quote="Verguetung 3.000 EUR")
    annual = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                             quote="Verguetung 12.000 EUR")
    assert _financial_classification_verified(monthly, rows) is True
    assert _financial_classification_verified(quarterly, rows) is True
    assert _financial_classification_verified(annual, rows) is True
    # Cross-period attempts: an annual classification fed with the monthly
    # amount, or a monthly classification fed with the annual amount/anchor,
    # must fail - the two never bind across rows.
    wrong_period_quote = SimpleNamespace(field="costs.annual_cost", page=3,
                                         value="850 EUR",
                                         quote="Monatliche Wartung 850 EUR")
    assert _financial_classification_verified(wrong_period_quote, rows) is False
    wrong_field = SimpleNamespace(field="costs.monthly_cost", page=3, value="12.000 EUR",
                                  quote="Jaehrliche Verguetung 12.000 EUR")
    assert _financial_classification_verified(wrong_field, rows) is False


def test_currency_format_variants():
    cases = [
        ("12.000 EUR", "Jaehrliche Verguetung 12.000 EUR."),
        ("12.000,00 EUR", "Jaehrliche Verguetung 12.000,00 EUR"),
        ("12.000 EUR", "Jaehrliche Verguetung EUR 12.000"),
        ("12.000 EUR", "Jaehrliche Verguetung 12.000 €"),
        ("12.000 EUR", "Jaehrliche Verguetung € 12.000"),
        ("1.200.000,50 EUR", "Jaehrliche Verguetung 1.200.000,50 EUR"),
        (12000.0, "Jaehrliche Verguetung 12.000 EUR."),
    ]
    for value, quote in cases:
        fact = SimpleNamespace(field="costs.annual_cost", page=3,
                               value=value, quote=quote)
        assert _financial_classification_verified(
            fact, _vision_only_rows()) is True, quote
    # A bare number is NOT authoritative money evidence: fail-closed.
    fact = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                           quote="Jaehrliche Verguetung 12.000")
    assert _financial_classification_verified(fact, _vision_only_rows()) is False


def test_correct_annual_amount_accepted_positive():
    # Quote path: anchor + exactly the proposed amount.
    fact = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                           quote="Jaehrliche Verguetung 12.000 EUR.")
    assert _financial_classification_verified(fact, _vision_only_rows()) is True
    # Row path via label anchor.
    assert _financial_classification_verified(
        fact, _vision_only_rows(status="corroborated",
                                label="Jaehrliche Verguetung")) is True
    # Row path via observation quote anchor (label without anchor).
    assert _financial_classification_verified(
        fact, _vision_only_rows(status="corroborated",
                                label="Verguetung",
                                quote="Jaehrliche Verguetung 12.000 EUR")) is True
    # Numeric fact value is a valid single amount.
    numeric = SimpleNamespace(field="costs.annual_cost", page=3, value=12000.0,
                              quote="Jaehrliche Verguetung 12.000 EUR.")
    assert _financial_classification_verified(numeric, _vision_only_rows()) is True


def test_unverified_classifications_rejected():
    # No amount in the fact value at all -> nothing to classify.
    no_value = SimpleNamespace(field="costs.annual_cost", page=3,
                               quote="Jaehrliche Verguetung 12.000 EUR.")
    assert _financial_classification_verified(no_value, _vision_only_rows()) is False
    # A fact value carrying several amounts cannot be single-sourced evidence.
    multi = SimpleNamespace(field="costs.annual_cost", page=3,
                            value={"amount": 12000.0, "deposit": 5000.0},
                            quote="Jaehrliche Verguetung 12.000 EUR.")
    assert _financial_classification_verified(multi, _vision_only_rows()) is False
    # Corroborated row with anchored label but a DIFFERENT amount rejects.
    fact = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                           quote="12.000 EUR")
    rows = _vision_only_rows(status="corroborated", label="Jaehrliche Verguetung")
    rows[0].value = "5.000 EUR"
    assert not _financial_classification_verified(fact, rows)
    # Anchored quote whose clause mixes several amounts is ambiguous.
    ambiguous = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                                quote="Einmalig 5.000 EUR und jaehrlich 12.000 EUR")
    row = _vision_only_rows(status="corroborated", label="Verguetung")
    row[0].value = "12.000 EUR"
    assert not _financial_classification_verified(ambiguous, row)


def test_legacy_paths_unaffected():
    annual = SimpleNamespace(field="costs.annual_cost", page=3, value="12.000 EUR",
                             quote="Verguetung 12.000 EUR pauschal.")
    # 1) No visual-first rows: whole gate bypassed, legacy evidence rules apply.
    assert _financial_classification_verified(annual, []) is True
    # 2) Non-periodic fields never impacted, even with visual rows present.
    for other in ("identity.supplier", "dates.start_date",
                  "termination.notice_period", "costs.variable_charges"):
        fact = SimpleNamespace(field=other, page=3, value="x",
                               quote="Verguetung 12.000 EUR pauschal.")
        assert _financial_classification_verified(
            fact, _vision_only_rows()) is True, other
    # 3) maintenance_fee with explicit Wartung anchor still classifies.
    maintenance = SimpleNamespace(field="costs.maintenance_fee", page=3,
                                  value="12.000 EUR", quote="Wartung 12.000 EUR")
    assert _financial_classification_verified(
        maintenance, _vision_only_rows()) is True
