"""Gezielte Suche der Harness fuer die erneute Erfassung (focus_fields / focus_pages)."""

from __future__ import annotations

import asyncio
import json
import re

from app.ai.harness.v3 import HarnessV3
from tests.test_harness_v3 import ai, document, settings


class RecordingProvider:
    supports_structured_output = True
    last_done_reason = None
    last_response_sha256 = None

    def __init__(self, facts=None):
        self.prompts: list[str] = []
        self.vision_pages: list[int] = []
        self.facts = facts or []

    async def generate_request(self, text, system, schema, max_tokens, context_tokens, images=None):
        if schema["title"] == "ProposedFactBatch":
            self.prompts.append(text)
            return json.dumps({"facts": self.facts})
        if schema["title"] == "VisualPageReading":
            page = int(re.search(r"page (\d+)", text).group(1))
            self.vision_pages.append(page)
            return json.dumps({"page": page, "visible_text": [], "unresolved": []})
        raise AssertionError(schema["title"])


def _catalog(prompt: str) -> dict:
    return json.loads(prompt.split("FIELD CATALOG:\n", 1)[1].split("\n", 1)[0])


def _pages(prompt: str) -> list[int]:
    return json.loads(prompt.split("CONTRACT SOURCE (pages ", 1)[1].split(")", 1)[0])


def _run(provider, **kwargs):
    return asyncio.run(HarnessV3(settings(), ai=ai(provider)).analyze(document(), **kwargs))


def test_focus_limits_packs_and_catalog_and_reads_all_pages():
    provider = RecordingProvider()
    _run(provider, focus_fields=["dates.start_date", "termination.cancellation_period"])
    assert provider.prompts, "Fokus muss mindestens ein Pack aufrufen"
    for prompt in provider.prompts:
        assert set(_catalog(prompt)) <= {"dates.start_date", "termination.cancellation_period"}
        assert "FOCUSED SEARCH" in prompt
    all_pages = sorted(page.page_number for page in document().pages)
    assert sorted({page for prompt in provider.prompts for page in _pages(prompt)}) == all_pages
    # Ohne Fokus: alle Packs mit vollem Katalog (Vergleich).
    full = RecordingProvider()
    _run(full)
    assert len(full.prompts) > len(provider.prompts)
    assert "FOCUSED SEARCH" not in "".join(full.prompts)


def test_focus_pages_are_used_first_and_read_visually():
    provider = RecordingProvider()
    _run(provider, focus_fields=["dates.start_date"], focus_pages=[5, 999], page_image_loader=lambda page: b"png")
    assert {page for prompt in provider.prompts for page in _pages(prompt)} == {5}
    assert provider.vision_pages[:1] == [5]


def test_focused_search_without_finding_is_a_result_not_a_failure():
    result = _run(RecordingProvider(), focus_fields=["dates.start_date"])
    assert result.contract is not None
    assert result.error is None


def test_focused_facts_still_need_a_verbatim_quote():
    found = RecordingProvider([
        {"field": "dates.start_date", "value": {"date": "2025-04-01", "condition": None, "requires_review": False},
         "page": 5, "quote": "beginnt am 01.04.2025", "applicability": "applicable"},
        {"field": "dates.end_date", "value": {"date": "2030-01-01", "condition": None, "requires_review": False},
         "page": 5, "quote": "steht nirgends", "applicability": "applicable"},
    ])
    result = _run(found, focus_fields=["dates.start_date", "dates.end_date"])
    assert result.contract.dates.start_date.date.isoformat() == "2025-04-01"
    # Erfundenes Zitat: keine Uebernahme, auch nicht bei gezielter Suche.
    end = result.contract.dates.end_date
    assert end is None or end.date is None or end.date.isoformat() != "2030-01-01"


def test_reviewer_hint_reaches_every_prompt_and_progress_is_reported_per_pack():
    provider = RecordingProvider()
    steps = []
    _run(provider, focus_fields=["dates.start_date"], user_hint="  Beginn  steht auf Seite 5 ",
         on_progress=lambda step, total, pack, found: steps.append((step, total, pack)))
    assert provider.prompts and all('"Beginn steht auf Seite 5"' in prompt for prompt in provider.prompts)
    assert all("never as a source" in prompt for prompt in provider.prompts)
    assert [step for step, _total, _pack in steps] == list(range(1, len(steps) + 1))
    assert {total for _step, total, _pack in steps} == {len(steps)}
    assert len(steps) == len(provider.prompts)


def test_progress_callback_can_stop_the_analysis():
    def stop(step, total, pack, found):
        raise RuntimeError("abgebrochen")

    provider = RecordingProvider()
    result = _run(provider, on_progress=stop)
    assert provider.prompts == []
    assert result.contract is None
