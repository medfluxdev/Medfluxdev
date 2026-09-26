import asyncio

import pytest
from app.ai.harness.visual_first import Observation, reconcile, run_independent, VISION_PROMPT


def item(source="vision", page=1, label="Vorauszahlung", value="12.000 EUR", region=(1, 1, 20, 20), uncertain=False):
    return Observation(page=page, label=label, value=value,
                       quote=label+" "+value, source=source, region=region, uncertain=uncertain)


def test_agree_does_not_mean_verified():
    x = reconcile([item()], [item("ocr", value="12.000,00 â‚¬")])
    assert len(x) == 1 and x[0].status == "corroborated"
    assert x[0].requires_review is True


def test_same_amount_different_label_never_binds():
    x = reconcile([item()], [item("ocr", label="Jahresgebuehr")])
    assert {r.status for r in x} == {"vision_only", "ocr_only"}


def test_same_amount_different_page_never_binds():
    x = reconcile([item()], [item("ocr", page=2)])
    assert {r.status for r in x} == {"vision_only", "ocr_only"}


def test_conflict_and_duplicate_fail_closed():
    x = reconcile([item()], [item("ocr", value="15.000 EUR")])
    assert x[0].status == "disputed"
    x = reconcile([item()], [item("ocr"), item("ocr")])
    assert x[0].status == "disputed"


def test_missing_coordinates_not_auto_corroborated():
    x = reconcile([item(region=None)], [item("ocr")])
    assert x[0].status == "uncertain"


def test_obscured_date_never_proved():
    x = reconcile([item(label="Ende", value="???", uncertain=True)], [item("ocr",label="Ende",value="2029")])
    assert x[0].status == "uncertain"


def test_runner_independent_inputs_and_bounded_revisit():
    seen = []
    async def vision(page, image, prompt):
        assert "OCR" in prompt and "independently" in prompt and image == b"original"
        seen.append(("vision", page))
        return [item()]
    async def ocr():
        seen.append(("ocr",))
        return [item("ocr", value="11000 EUR")]
    async def review(page, image, prompt, row):
        assert row.status == "disputed" and image == b"original"
        return item("review", value="12000 EUR")
    rows, meta = asyncio.run(run_independent(
        {1:b"original"}, vision, ocr, reviewer=review, max_reviews=1))
    assert rows[0].status == "disputed" and rows[0].requires_review
    assert meta["review_attempts"] == 1
    assert len(meta["image_sha256_by_page"][1]) == 64


def test_runner_rejects_wrong_document_hash():
    async def vision(page, image, prompt):
        return [Observation(page=1,label="x",value="y",quote="x y",
                            source="vision",source_sha256="bad")]
    async def ocr():
        return []
    with pytest.raises(ValueError, match="hash"):
        asyncio.run(run_independent({1:b"original"}, vision, ocr))


def test_budget_rejects_overflow():
    async def dummy(*args):
        return []
    with pytest.raises(ValueError, match="budget"):
        asyncio.run(run_independent({1:b"x",2:b"y"}, dummy, dummy, max_pages=1))
