"""UAT Round-3 Fix 1: deterministische `services.included_services`.

- Proposal-Form-Varianz (list-of-dicts, einzelner String, Leereintraege)
  wird deterministisch auf `list[str]` normalisiert – nichts geht verloren,
  nur weil die Form der Liste von Lauf zu Lauf wechselt.
- Evidence-gestuetzte Bool-Service-Fakten (True) werden deterministisch in
  die included_services projiziert (kanonischer generischer Leistungs-Begriff).
- False/None/fehlende Evidence bleiben aussen (fail-closed); kein ABIOMED-
  Bezug in der Mapping-Logik.
- Zitat-Resolver toleriert Innen-Ellipsen (`...`/`…`) des Modells, aber
  NIE Paraphrasen (kein Fuzzy-Matching).
"""
import json

import pytest

from app.ai.harness.pipeline import _find_quote
from app.ai.harness.v3 import (
    HarnessV3,
    _merge_service_scope_facts,
    _normalize_scope_list,
)
from app.models.contract import Services
from tests.test_harness_v3 import FakeProvider, ai, settings


def _harness_document():
    from tests.test_harness_v3 import document

    return document()


class ServiceScopeProvider(FakeProvider):
    """Liefert die Operations-Batch mit Bool-Service-Fakten + scope-Liste."""

    def __init__(self, *, emit_list=True, list_shape="list"):
        self.emit_list = emit_list
        self.list_shape = list_shape
        super().__init__()

    async def generate_request(
        self, text, system, schema, max_tokens, context_tokens, images=None
    ):
        raw = await super().generate_request(
            text, system, schema, max_tokens, context_tokens, images
        )
        if schema["title"] != "ProposedFactBatch" or "sla.service_hours" not in text:
            return raw
        payload = json.loads(raw)
        facts = [
            fact
            for fact in payload["facts"]
            if not str(fact["field"]).startswith("services.")
        ]
        facts.extend(
            [
                {
                    "field": "services.inspection",
                    "value": True,
                    "page": 7,
                    "quote": "Inspektionen",
                    "applicability": "applicable",
                },
                {
                    "field": "services.repair",
                    "value": True,
                    "page": 7,
                    "quote": "Reparaturen und Instandsetzung",
                    "applicability": "applicable",
                },
                {
                    "field": "services.software_updates",
                    "value": False,
                    "page": 7,
                    "quote": "Im Vertragsumfang enthalten",
                    "applicability": "applicable",
                },
            ]
        )
        if self.emit_list:
            if self.list_shape == "dict":
                included = [
                    {"description": "Reparaturen und Instandsetzung"},
                    {"label": "Inspektionen"},
                    {"name": "Ersatzteilversorgung"},
                ]
            else:
                included = [
                    "Reparaturen und Instandsetzung",
                    "Inspektionen",
                    "Ersatzteilversorgung",
                ]
            facts.append(
                {
                    "field": "services.included_services",
                    "value": included,
                    "page": 7,
                    "quote": "Im Vertragsumfang enthalten: Reparaturen und "
                    "Instandsetzung",
                    "applicability": "applicable",
                }
            )
        payload["facts"] = facts
        return json.dumps(payload)


# ---------------------------------------------------------------------------
# Unit-Level
# ---------------------------------------------------------------------------


def test_normalize_scope_list_strips_dedupes_and_coerces():
    assert _normalize_scope_list([" Wartung ", "Reparatur", " Wartung "]) == [
        "Wartung",
        "Reparatur",
    ]
    assert _normalize_scope_list(
        [{"description": "Wartung"}, {"label": "Reparatur"}, ""]
    ) == ["Wartung", "Reparatur"]
    assert _normalize_scope_list("Fernwartung") == ["Fernwartung"]
    assert _normalize_scope_list([]) == []
    assert _normalize_scope_list([{"name": 5}, "X"]) == ["X"]
    assert _normalize_scope_list(None) == []


def test_merge_service_scope_facts_deterministic_and_fail_closed():
    s = Services()
    s.included_services = [
        "Reparaturen und Instandsetzung",
        "Ersatzteilversorgung",
    ]
    s.maintenance = True
    s.inspection = True
    s.repair = False
    s.software_updates = None
    _merge_service_scope_facts(s)
    expected = [
        "Reparaturen und Instandsetzung",
        "Ersatzteilversorgung",
        "Wartung",
        "Sichtprüfung / Inspektion",
    ]
    assert s.included_services == expected
    _merge_service_scope_facts(s)
    assert s.included_services == expected
    assert "Reparatur" not in expected
    assert "Softwareupdates" not in expected
    assert "Reparatur" not in Services(
        included_services=["X"], repair=False
    ).included_services


def test_merge_service_scope_facts_noop_without_support():
    assert Services().included_services == []
    empty = Services()
    _merge_service_scope_facts(empty)
    assert empty.included_services == []


def test_find_quote_ellipsis_fallback_only_bridges_ellipsis():
    src = (
        "Im Umfang: Sichtprüfung auf äußere Mängel ... Sicherheitstest … "
        "IEC 62353."
    )
    # gleiche Tokens, nur Ellipsen ueberbrueckt -> treffer
    assert _find_quote(
        src, "Sichtprüfung auf äußere Mängel ... Sicherheitstest"
    ) is not None
    # verkürzt um echte Woerter -> fail-closed
    assert _find_quote(src, "Sichtprüfung ... Sicherheitstest") is None
    # Paraphrase ohne Ellipse -> kein Treffer
    assert _find_quote(src, "Ganz andere Sichtprüfung") is None
    assert _find_quote(src, "Sichtprüfung ganz andere Mängel") is None


# ---------------------------------------------------------------------------
# Integration (fastester Fake-Provider, kein Ollama)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bool_service_facts_are_projected_into_included_services():
    result = await HarnessV3(settings(), ai(ServiceScopeProvider())).analyze(
        _harness_document()
    )
    assert result.contract is not None, result.error
    svc = result.contract.services
    assert "Sichtprüfung / Inspektion" in svc.included_services
    assert "Reparatur" in svc.included_services
    assert "Wartung" not in svc.included_services
    assert svc.included_services.index("Reparatur") > svc.included_services.index(
        "Reparaturen und Instandsetzung"
    )


@pytest.mark.asyncio
async def test_scope_list_shape_variance_is_normalized():
    result = await HarnessV3(
        settings(), ai(ServiceScopeProvider(list_shape="dict"))
    ).analyze(_harness_document())
    assert result.contract is not None, result.error
    included = result.contract.services.included_services
    assert "Reparaturen und Instandsetzung" in included
    assert "Inspektionen" in included
    assert "Ersatzteilversorgung" in included
    assert all(isinstance(item, str) for item in included)


@pytest.mark.asyncio
async def test_included_services_stable_across_runs():
    run1 = await HarnessV3(settings(), ai(ServiceScopeProvider(list_shape="dict"))).analyze(
        _harness_document()
    )
    run2 = await HarnessV3(settings(), ai(ServiceScopeProvider(list_shape="dict"))).analyze(
        _harness_document()
    )
    assert run1.contract is not None and run2.contract is not None
    assert run1.contract.services.included_services == run2.contract.services.included_services
    assert not run1.diagnostics["rejected_facts"]
    assert not run2.diagnostics["rejected_facts"]


@pytest.mark.asyncio
async def test_unlocated_service_fact_never_merges():
    class UnlocatableProvider(ServiceScopeProvider):
        async def generate_request(
            self, text, system, schema, max_tokens, context_tokens, images=None
        ):
            raw = await super().generate_request(
                text, system, schema, max_tokens, context_tokens, images
            )
            if schema["title"] != "ProposedFactBatch" or "sla.service_hours" not in text:
                return raw
            payload = json.loads(raw)
            for fact in payload["facts"]:
                if fact["field"] == "services.repair":
                    fact["quote"] = "vollstaendig andere Paraphrase ohne Beleg"
            return json.dumps(payload)

    result = await HarnessV3(settings(), ai(UnlocatableProvider())).analyze(
        _harness_document()
    )
    assert result.contract is not None, result.error
    assert "Reparatur" not in result.contract.services.included_services
    assert "Sichtprüfung / Inspektion" in result.contract.services.included_services
    assert any(
        row["field"] == "services.repair"
        and row["reason"] == "evidence_not_located"
        for row in result.diagnostics["rejected_facts"]
    )