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


class GateProvider:
    """Canned provider: one un-corroborated vision observation on page 3 plus
    canned semantic facts. The vision label never appears in the OCR text, so
    reconcile() can only mark the page-3 row vision_only (never corroborated)."""

    supports_structured_output = True
    last_done_reason = None
    last_usage = {}

    def __init__(self, annual_fact: dict):
        self.annual_fact = annual_fact

    async def generate_request(
        self, text, system, schema, max_tokens, context_tokens, images=None
    ):
        title = schema["title"]
        if title == "VisionClaims":
            if "Page=3." in text:
                claim = {
                    "page": 3,
                    "label": "Einmalige Zusatzkosten",
                    "value": "12.000 EUR",
                    "quote": "Einmalige Zusatzkosten 12.000 EUR",
                    "region": [10, 10, 20, 20],
                    "uncertain": False,
                }
                return json.dumps({"claims": [claim]})
            return json.dumps({"claims": []})
        if title == "ProposedFactBatch":
            if "commercial" in text or "payment" in text:
                return json.dumps({"facts": [dict(self.annual_fact)]})
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
    provider = GateProvider(annual_fact)
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
    # (recurring annual anchor). Independent of whether the visual row was
    # corroborated, the amount is proven to be an annual obligation and may
    # enter annual_cost.
    annual_fact = dict(ANNUAL_FACT)
    annual_fact["quote"] = "Jaehrliche Verguetung 12.000 EUR."
    provider = GateProvider(annual_fact)
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


def _vision_only_rows(field_page=3, status="vision_only", label="Einmalige Zusatzkosten",
                      quote="Einmalige Zusatzkosten 12.000 EUR"):
    obs = Observation(
        page=field_page, source="vision", label=label,
        value="12.000 EUR", quote=quote,
        region=[10, 10, 20, 20],
    )
    return [Reconciled(field_page, obs.label, obs.value, status, [obs])]


def test_classification_predicate_decision_matrix():
    annual = SimpleNamespace(field="costs.annual_cost", page=3,
                             quote="Verguetung 12.000 EUR pauschal.")
    anchored = SimpleNamespace(field="costs.annual_cost", page=3,
                               quote="Jaehrliche Verguetung 12.000 EUR.")
    quarterly_quote = SimpleNamespace(field="costs.annual_cost", page=3,
                                      quote="Quartalsweise 12.000 EUR.")
    monthly = SimpleNamespace(field="costs.monthly_cost", page=3,
                              quote="pauschal 12.000 EUR")
    monthly_anchored = SimpleNamespace(field="costs.monthly_cost", page=3,
                                       quote="pro Monat 12.000 EUR")
    maintenance = SimpleNamespace(field="costs.maintenance_fee", page=3,
                                  quote="pauschal 12.000 EUR")
    maintenance_anchored = SimpleNamespace(field="costs.maintenance_fee",
                                           page=3,
                                           quote="Wartung 12.000 EUR")
    identity = SimpleNamespace(field="identity.supplier", page=1,
                               quote="ABIOMED Europe GmbH")

    # Legacy/Hybrid-Pfad ohne Visual-First bleibt unbelastet.
    assert _financial_classification_verified(annual, []) is True
    # Nicht-diskretionaere Felder sind nie betroffen.
    assert _financial_classification_verified(identity, _vision_only_rows(1)) is True
    # Seite ohne visuelle Reconciliation: kein Gate-Zwang.
    assert _financial_classification_verified(
        annual, _vision_only_rows(2)) is True
    # Unbestatigte visuelle Evidenz + kein Periodenanker: abgelehnt.
    assert _financial_classification_verified(annual, _vision_only_rows()) is False
    assert _financial_classification_verified(
        annual, _vision_only_rows(status="disputed")) is False
    # Periodenanker im Zitat genuegt.
    assert _financial_classification_verified(anchored, _vision_only_rows()) is True
    # Deterministischer Anker im Dokumenttext der Zielseite genuegt.
    assert _financial_classification_verified(
        annual, _vision_only_rows(),
        page_texts={3: "Jaehrliche Verguetung 12.000 EUR pauschal."}) is True
    assert _financial_classification_verified(
        annual, _vision_only_rows(),
        page_texts={2: "Jaehrliche Verguetung."}) is False
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
    # Korrobation MIT Periodenanker in Label oder Zitat belegt die Klasse.
    assert _financial_classification_verified(
        annual, _vision_only_rows(status="corroborated",
                                  label="Jaehrliche Verguetung")) is True
    assert _financial_classification_verified(
        annual, _vision_only_rows(status="corroborated",
                                  quote="Jaehrliche Verguetung 12.000 EUR")) is True
    # Auch bei korroborierter Seite entscheidet zuerst das Fakt-Zitat.
    assert _financial_classification_verified(anchored, _vision_only_rows()) is True