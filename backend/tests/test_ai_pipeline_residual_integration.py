"""Integration regression for deterministic residual critical-claim gates."""

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

import app.ai.groups.extractor as extractor_module
from app.ai.groups.extractor import GroupOutcome, GroupPipeline
from app.core.config import Settings
from app.documents.extraction.schemas import ExtractionUnit, SourceType


class _DummyGroup(BaseModel):
    marker: str = "ok"


class _DummySpec:
    model = _DummyGroup
    schema: dict = {}
    prompt = "dummy"

    @staticmethod
    def apply(contract, model) -> None:
        contract.payment.payment_terms = "Zahlbar innerhalb von 30 Tagen"


@pytest.mark.asyncio
async def test_group_pipeline_runs_residual_gate_when_semantic_verifier_disabled(monkeypatch):
    pipeline = GroupPipeline(
        None,  # type: ignore[arg-type]
        Settings(_env_file=None),
        run_verification=False,
    )
    pipeline._specs = {"dummy": _DummySpec()}
    monkeypatch.setattr(extractor_module, "group_order", lambda: ["dummy"])

    async def fake_extract(chunk, name):
        return GroupOutcome(name=name, model=_DummyGroup())

    monkeypatch.setattr(pipeline, "_extract_group_for_chunk", fake_extract)

    units = [
        ExtractionUnit(
            source_type=SourceType.PARAGRAPH,
            index=1,
            text="Zahlung innerhalb von 14 Tagen",
        )
    ]
    chunks = [SimpleNamespace(index=1, text=units[0].text)]

    contract, diag, messages = await pipeline.run(chunks, units)

    assert contract is not None
    assert contract.review.requires_manual_review is True
    assert diag.verifier_issues >= 1
    assert any("payment.payment_terms" in message for message in messages)
