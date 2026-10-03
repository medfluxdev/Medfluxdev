import asyncio
import json
from types import SimpleNamespace

from app.ai.harness.visual_first_bridge import prepare_visual_first
from app.ai.harness.visual_first import Observation

class FakeProvider:
    def __init__(self):
        self.prompts = []
    async def generate_request(self, prompt, system, schema, output, context, images):
        self.prompts.append((prompt, images))
        assert images == ["orig_base64"]
        assert "12.000 EUR" not in prompt  # no OCR priming
        if "Conflicting" in prompt:
            return json.dumps({"claims":[{"page":1,"label":"Total",
                "value":"12.000 EUR","quote":"Total 12.000 EUR"}]})
        return json.dumps({"claims":[{"page":1,"label":"Total",
            "value":"12.000 EUR","quote":"Total 12.000 EUR"}]})

def test_real_adapter_independent_and_disputed():
    provider=FakeProvider()
    canonical=SimpleNamespace(pages=[SimpleNamespace(page_number=1, elements=[], tables=[],
                                                     text="Total 12.000 EUR")],
                              source_sha256="source-hash", document_id="test")
    signal={"page":1,"kind":"money","value":"15.000 EUR",
            "quote":"Total 15.000 EUR","block_id":"none"}
    readings, rows, meta = asyncio.run(prepare_visual_first(
        canonical=canonical, source_signals=[signal], page_image_loader=lambda page:"orig_base64",
        provider=provider, context=8192, output_tokens=1500, max_pages=1,max_reviews=0))
    assert len(rows)==1
    assert rows[0].status=="disputed"
    assert all(row.requires_review for row in rows)
    assert readings[1].visible_text==["Total 12.000 EUR"]
    assert meta["review_attempts"]==0
    assert meta["source_pdf_sha256"]=="source-hash"

def test_missing_original_page_fails_closed():
    provider=FakeProvider()
    canonical=SimpleNamespace(pages=[SimpleNamespace(page_number=1, elements=[], tables=[], text="")],
                              source_sha256="source-hash", document_id="test")
    try:
        asyncio.run(prepare_visual_first(
            canonical=canonical, source_signals=[], page_image_loader=None,
            provider=provider,context=8192, output_tokens=1500))
        assert False, "Should fail"
    except ValueError as err:
        assert "Original" in str(err)

def test_wrong_page_claim_is_discarded_and_flagged_without_relabelling():
    class WrongPageProvider:
        async def generate_request(self, prompt, system, schema, output, context, images):
            return json.dumps({"claims":[{"page":99,"label":"Unverified",
                "value":"12.000 EUR","quote":"Wrong page 12.000 EUR"}]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=1, elements=[], tables=[], text="")],
        source_sha256="source-hash",document_id="test")
    signals=[{"page":1,"kind":"money","value":"15.000 EUR",
              "quote":"Total 15.000 EUR","block_id":"none"}]
    readings, rows, meta = asyncio.run(prepare_visual_first(
        canonical=canonical, source_signals=signals,
        page_image_loader=lambda page:"orig_base64",
        provider=WrongPageProvider(), context=8192, output_tokens=800,
        max_pages=1, max_reviews=0))
    assert readings[1].visible_text == []
    assert len(rows)==1 and rows[0].status=="ocr_only"
    assert rows[0].requires_review
    assert any(call.get("rejected_page_mismatch") for call in meta["calls"])


def test_invalid_regions_and_malformed_claims_do_not_corrupt_other_evidence():
    class MixedClaims:
        async def generate_request(self, prompt, system, schema, output, context, images):
            return json.dumps({"claims":[
                {"page":1,"label":"Wrong geometry","value":"12.000 EUR",
                 "quote":"Wrong geometry 12.000 EUR","region":[9,9,1,1]},
                {"page":1,"label":"Malformed geometry","value":"12.000 EUR",
                 "quote":"Malformed geometry 12.000 EUR","region":"wrong"},
                {"page":1,"label":"Valid value","value":"15.000 EUR",
                 "quote":"Valid value 15.000 EUR"}
            ]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=1,elements=[],tables=[],
                               text="Wrong geometry 12.000 EUR Malformed geometry "
                                    "12.000 EUR Valid value 15.000 EUR")],
        source_sha256="source-hash",document_id="test")
    readings, rows, meta=asyncio.run(prepare_visual_first(
        canonical=canonical,source_signals=[],
        page_image_loader=lambda page:"orig_base64",
        provider=MixedClaims(),context=8192,output_tokens=800,
        max_pages=1,max_reviews=0))
    # Missing label on a source-OK claim and the valid claim keep their grounded
    # literals; malformed region boxes are dropped (region forced manual review),
    # while wholly unparsable claims still cannot corrupt evidence.
    assert readings[1].visible_text==["Wrong geometry 12.000 EUR","Valid value 15.000 EUR"]
    assert len(rows)==2 and all(r.status=="vision_only" for r in rows)
    assert rows[0].requires_review and rows[1].requires_review
    assert any(c.get("rejected_invalid_region") and c.get("region_dropped")
               for c in meta["calls"])
    assert any(c.get("rejected_malformed_claim") for c in meta["calls"])

def test_unusable_region_keeps_grounded_literal_and_marks_review():
    class BadRegion:
        async def generate_request(self, prompt, system, schema, output, context, images):
            return json.dumps({"claims":[{"page":1,"label":"Total",
                "value":"12.000 EUR","quote":"Total 12.000 EUR",
                "region":[12.0, 44.0, 2.0, 1.0]}]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=1,elements=[],tables=[],
                               text="Total 12.000 EUR")],
        source_sha256="source-hash",document_id="test")
    readings,rows,meta=asyncio.run(prepare_visual_first(
        canonical=canonical,source_signals=[],
        page_image_loader=lambda page:"orig_base64",
        provider=BadRegion(),context=8192,output_tokens=800,
        max_pages=1,max_reviews=0))
    assert readings[1].visible_text==["Total 12.000 EUR"]
    assert len(rows)==1 and rows[0].status=="vision_only" and rows[0].requires_review
    assert any(c.get("rejected_invalid_region") and c.get("region_dropped")
               for c in meta["calls"])


def test_uniform_single_step_page_offset_is_reanchored():
    class OffsetProvider:
        async def generate_request(self, prompt, system, schema, output, context, images):
            return json.dumps({"claims":[
                {"page":0,"label":"Total","value":"12.000 EUR",
                 "quote":"Total 12.000 EUR"},
                {"page":0,"label":"Device","value":"System A",
                 "quote":"Device System A"}]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=1,elements=[],tables=[],
                               text="Total 12.000 EUR Device System A")],
        source_sha256="source-hash",document_id="test")
    readings,rows,meta=asyncio.run(prepare_visual_first(
        canonical=canonical,source_signals=[],
        page_image_loader=lambda page:"orig_base64",
        provider=OffsetProvider(),context=8192,output_tokens=800,
        max_pages=1,max_reviews=0))
    assert readings[1].visible_text==["Total 12.000 EUR","Device System A"]
    assert len(rows)==2 and all(r.status=="vision_only" and r.page==1 for r in rows)
    assert not any(c.get("rejected_page_mismatch") for c in meta["calls"])

def test_multi_step_page_offset_is_not_reanchored():
    class MultiStepProvider:
        async def generate_request(self, prompt, system, schema, output, context, images):
            return json.dumps({"claims":[{"page":5,"label":"Total",
                "value":"12.000 EUR","quote":"Total 12.000 EUR"}]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=2,elements=[],tables=[],text="")],
        source_sha256="source-hash",document_id="test")
    readings,rows,meta=asyncio.run(prepare_visual_first(
        canonical=canonical,source_signals=[],
        page_image_loader=lambda page:"orig_base64",
        provider=MultiStepProvider(),context=8192,output_tokens=800,
        max_pages=1,max_reviews=0))
    assert readings[2].visible_text==[]
    assert rows == []
    assert any(c.get("rejected_page_mismatch") for c in meta["calls"])

def test_mixed_page_offsets_stay_fail_closed_on_shifted_claims():
    class MixedProvider:
        async def generate_request(self, prompt, system, schema, output, context, images):
            return json.dumps({"claims":[
                {"page":0,"label":"Wrong shift","value":"12.000 EUR",
                 "quote":"Wrong shift 12.000 EUR"},
                {"page":1,"label":"Good claim","value":"15.000 EUR",
                 "quote":"Good claim 15.000 EUR"}]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=1,elements=[],tables=[],
                               text="Good claim 15.000 EUR")],
        source_sha256="source-hash",document_id="test")
    readings,rows,meta=asyncio.run(prepare_visual_first(
        canonical=canonical,source_signals=[],
        page_image_loader=lambda page:"orig_base64",
        provider=MixedProvider(),context=8192,output_tokens=800,
        max_pages=1,max_reviews=0))
    assert readings[1].visible_text==["Good claim 15.000 EUR"]
    assert any(c.get("rejected_page_mismatch") for c in meta["calls"])

def test_bad_model_page_does_not_discard_good_page_or_independent_ocr():
    class IntermittentProvider:
        async def generate_request(self, prompt, system, schema, output, context, images):
            if "Page=1" in prompt:
                return "bad-json"
            return json.dumps({"claims":[{"page":2,"label":"Device",
                "value":"System A","quote":"Device System A"}]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=1,elements=[],tables=[],
                               text=""),
               SimpleNamespace(page_number=2,elements=[],tables=[],
                               text="Device System A")],
        source_sha256="source-hash",document_id="test")
    readings,rows,meta=asyncio.run(prepare_visual_first(
        canonical=canonical,
        source_signals=[{"page":1,"kind":"money","value":"15.000 EUR",
                         "quote":"Total 15.000 EUR","block_id":"none"}],
        page_image_loader=lambda p:"orig_base64",
        provider=IntermittentProvider(),context=8192,
        output_tokens=800,max_pages=2,max_reviews=0))
    assert readings[1].visible_text==[]
    assert readings[2].visible_text==["Device System A"]
    assert any(r.status=="ocr_only" and r.page==1 for r in rows)
    assert any(r.status=="vision_only" and r.page==2 for r in rows)
    assert any(c.get("rejected_page_error") for c in meta["calls"])
    assert all(r.requires_review for r in rows)

def test_duplicate_literal_on_other_page_cannot_trust_reanchored_claim():
    class OffsetProvider:
        async def generate_request(self, prompt, system, schema, output, context, images):
            return json.dumps({"claims":[{"page":1,"label":"Pauschale",
                "value":"12.000 EUR","quote":"Pauschale 12.000 EUR"}]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=1,elements=[],tables=[],
                               text="Pauschale 12.000 EUR"),
               SimpleNamespace(page_number=2,elements=[],tables=[],
                               text="Alle übrigen Kostenpunkte")],
        source_sha256="source-hash",document_id="test")
    readings,rows,meta=asyncio.run(prepare_visual_first(
        canonical=canonical,source_signals=[],
        page_image_loader=lambda page:"orig_base64",
        provider=OffsetProvider(),context=8192,output_tokens=800,
        max_pages=2,max_reviews=0))
    # The model saw the page-2 image but labelled the claim page 1 (uniform -1
    # offset). The literal exists ONLY on page 1. A secondary match alone is not
    # proof that page 2 is wrong, so the grounded reading is kept - but it is
    # flagged ambiguous and MUST stay review-only (never a trusted page ref).
    assert readings[2].visible_text==["Pauschale 12.000 EUR"]
    assert any(c.get("provenance_ambiguous_on_other_page") for c in meta["calls"])
    assert rows and all(row.requires_review for row in rows)

def test_same_duplicate_literal_on_both_pages_cannot_produce_trusted_page():
    class OffsetProvider:
        async def generate_request(self, prompt, system, schema, output, context, images):
            return json.dumps({"claims":[{"page":1,"label":"Pauschale",
                "value":"12.000 EUR","quote":"Pauschale 12.000 EUR"}]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=1,elements=[],tables=[],
                               text="Pauschale 12.000 EUR"),
               SimpleNamespace(page_number=2,elements=[],tables=[],
                               text="Pauschale 12.000 EUR")],
        source_sha256="source-hash",document_id="test")
    readings,rows,meta=asyncio.run(prepare_visual_first(
        canonical=canonical,source_signals=[],
        page_image_loader=lambda page:"orig_base64",
        provider=OffsetProvider(),context=8192,output_tokens=800,
        max_pages=2,max_reviews=0))
    # The identical literal exists on BOTH pages: the page reference is not
    # unique. Keep the reading (grounded on the image the model saw) but mark
    # it multipage-ambiguous so no downstream stage can trust the page binding.
    assert readings[2].visible_text==["Pauschale 12.000 EUR"]
    assert any(c.get("provenance_ambiguous_multipage") for c in meta["calls"])
    assert not any(c.get("provenance_ambiguous_on_other_page") for c in meta["calls"])
    assert rows and all(row.requires_review for row in rows)

def test_quote_not_in_ocr_stays_grounded_but_forced_review():
    class SummaryProvider:
        async def generate_request(self, prompt, system, schema, output, context, images):
            return json.dumps({"claims":[{"page":1,"label":"Gerät",
                "value":"System A","quote":"Gerät System A"}]})
    canonical=SimpleNamespace(
        pages=[SimpleNamespace(page_number=1,elements=[],tables=[],text="")],
        source_sha256="source-hash",document_id="test")
    readings,rows,meta=asyncio.run(prepare_visual_first(
        canonical=canonical,source_signals=[],
        page_image_loader=lambda page:"orig_base64",
        provider=SummaryProvider(),context=8192,output_tokens=800,
        max_pages=1,max_reviews=0))
    # The page-1 image simply has no OCR text: the visible literal cannot be
    # cross-checked. It stays grounded (the image is the authority the model
    # saw) but is flagged unverified and forced into manual review.
    assert readings[1].visible_text==["Gerät System A"]
    assert any(c.get("provenance_unverified_by_ocr") for c in meta["calls"])
