"""Source-only regression: explicitly labelled equipment must not disappear silently."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.groups.extractor import GroupPipeline, GroupOutcome
from app.documents.extraction.schemas import ExtractionUnit, SourceType
from app.ai.groups.models import IdentityEquipmentGroup


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "Gerät: Accutron MR",
    "Geräte\nModell: Accutron MR",
    "Anlage: MRT-System",
])
async def test_missing_explicit_equipment_requires_review(text):
    pipeline = GroupPipeline.__new__(GroupPipeline)
    pipeline._specs = __import__("app.ai.groups.schema", fromlist=["group_specs"]).group_specs()
    pipeline._run_verification = False
    pipeline._extract_group_for_chunk = AsyncMock(
        side_effect=lambda _chunk, name: GroupOutcome(
            name=name, model=IdentityEquipmentGroup() if name == "identity_equipment" else None
        )
    )
    unit = ExtractionUnit(source_type=SourceType.PARAGRAPH, index=1, text=text)
    contract, _diag, messages = await pipeline.run(
        [SimpleNamespace(index=1, text=text)], [unit]
    )
    assert contract is not None
    assert contract.equipment == []
    assert contract.review.requires_manual_review
    assert any("keine Geräte extrahiert" in message for message in messages)
