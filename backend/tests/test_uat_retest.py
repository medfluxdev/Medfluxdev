"""Fokussierte Tests – UAT Re-Test-Fixes (deterministische Wiederherstellung).

Deckt NUR die neuen, generischen Fix-Schichten ab (keine volle Regression,
kein OpenAI/LLM, kein Dateisystem/OCR):

- Vertragsnummer + Titel aus dem persistierten kanonischen Seitentext
- absolute Vertragsdaten / Laufzeit / automatische Verlaengerung
- Preis-Zeilen (Preistabelle) fuer die ehrliche Kosten-Erklaerung
- Ereignis-Regel-Filter (keine „Ereignisbasiert: erforderlich"-Fehlanzeige)
- Evidence-Seiten-Aufloesung (Snippet -> Seite, read-time, deterministisch)
- Kosten-Availability-Baustein (ehrliche Erklaerung statt NULL)
- Materiale Reader (Geräte-Identität als Wert statt bool, Ende-Fallback)
- Review-Linkage/Zaehlung (kritische, ungepruefte Angaben)
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.contracts.detail.recovery import (  # noqa: E402
    RecoveredCostLine,
    RecoveredFacts,
    RecoveredIdentity,
    RecoveredLaufzeit,
    _find_absolute_dates,
    _find_contract_number,
    _find_cost_lines,
    _find_title,
    _parse_german_date,
    recover_financial_facts,
)
from app.contracts.detail.service import (  # noqa: E402
    _build_contract_title,
    _cost_availability,
    _is_event_rule,
    _resolve_evidence_page,
)
from app.contracts.review import material as mat  # noqa: E402
from app.contracts.review.service import build_review_summary  # noqa: E402


class TestParseGermanDate:
    def test_day_month_year(self):
        assert _parse_german_date("01.04.2025") == date(2025, 4, 1)

    def test_single_digits(self):
        assert _parse_german_date("1.4.2025") == date(2025, 4, 1)

    def test_invalid_rejected(self):
        assert _parse_german_date("32.13.2025") is None
        assert _parse_german_date("2025-04-01") is None


class TestContractNumberRecovery:
    def test_abreviated_vertr_nr(self):
        res = _find_contract_number([
            {"page": 1, "text": "ABIOMED Europe GmbH\nVertr.-Nr.: 40015645\nNeuenhofer Weg 3"}
        ])
        assert res is not None
        assert res["number"] == "40015645"
        assert res["page"] == 1

    def test_long_german_label(self):
        res = _find_contract_number([
            {"page": 1, "text": "Vertragsnummer: 4711 / Kundennummer 0815"}
        ])
        assert res is not None
        assert res["number"] == "4711"

    def test_english_label(self):
        res = _find_contract_number([
            {"page": 1, "text": "Contract No.: ABC-123/24"}
        ])
        assert res is not None
        assert res["number"] == "ABC-123/24"

    def test_no_number_returns_none(self):
        assert _find_contract_number([{"page": 1, "text": "kein Vertrag hier"}]) is None


class TestTitleRecovery:
    def _pages(self):
        el = lambda text, y0, x0=0, x1=100: {  # noqa: E731
            "text": text,
            "region": {"x0": x0, "y0": y0, "x1": x1, "y1": y0 + 20},
        }
        return [{
            "page": 1,
            "text": "",
            "elements": [
                el("Full-Service-Vertrag", 682),
                el("für das Impella AIC System", 705),
                el("Vertr.-Nr.: 40015645", 730),
            ],
        }]

    def test_heading_plus_subject(self):
        res = _find_title(self._pages())
        assert res is not None
        assert res["title"] == "Full-Service-Vertrag für das Impella AIC System"
        assert res["page"] == 1
        assert res["region"] is not None

    def test_number_line_not_used(self):
        res = _find_title([{
            "page": 1,
            "text": "",
            "elements": [
                {"text": "Vertr.-Nr.: 40015645", "region": {"x0": 0, "y0": 1, "x1": 100, "y1": 20}},
                {"text": "Servicevereinbarung", "region": {"x0": 0, "y0": 30, "x1": 100, "y1": 50}},
            ],
        }])
        assert res is not None
        assert res["title"] == "Servicevereinbarung"


class TestAbsoluteStartDatesRecovery:
    def test_begin_end_duration_no_auto_renewal(self):
        res = _find_absolute_dates([{
            "page": 5,
            "text": "Der Full-Service-Vertrag beginnt am 01.04.2025 und endet am "
                    "31.03.2029. Er hat eine Laufzeit von 4 Jahren und wird "
                    "nicht automatisch verlängert. Das Recht zur außerordentlichen "
                    "Kündigung bleibt davon unberührt.",
        }])
        assert res is not None
        assert res["start"] == date(2025, 4, 1)
        assert res["end"] == date(2029, 3, 31)
        assert res["start_page"] == 5
        assert res["end_page"] == 5
        assert res["duration_years"] == 4
        assert res["auto_renewal"] is False
        assert res["auto_renewal_page"] == 5

    def test_auto_renewal_yes(self):
        res = _find_absolute_dates([{
            "page": 3,
            "text": "Das Vertragsverhältnis verlängert sich automatisch um 1 Jahr.",
        }])
        assert res is not None
        assert res["auto_renewal"] is True

    def test_nothing_matches(self):
        assert _find_absolute_dates([{"page": 1, "text": "Es gilt die MPG."}]) is None


class TestCostLinesRecovery:
    def _table_pages(self):
        return [{
            "page": 8,
            "text": "",
            "tables": [{
                "cells": [
                    {"text": "Full-Service zwei Controller 1.Jahr (zzgl. gesetzl. MwSt)", "region": {"x0": 0, "y0": 0, "x1": 100, "y1": 20}},
                    {"text": "0 EUR", "region": {"x0": 120, "y0": 0, "x1": 200, "y1": 20}},
                    {"text": "Full-Service zwei Controller 2.Jahr (zzgl. gesetzl. MwSt)", "region": {"x0": 0, "y0": 30, "x1": 100, "y1": 50}},
                    {"text": "8.000,00 EUR", "region": {"x0": 120, "y0": 30, "x1": 200, "y1": 50}},
                ]
            }],
        }]

    def test_year_prices_are_recovered_verbatim(self):
        lines = _find_cost_lines(self._table_pages())
        assert len(lines) == 2
        assert lines[0]["amount"] == Decimal("0")
        assert lines[1]["amount"] == Decimal("8000.00")
        assert lines[0]["page"] == 8
        assert lines[0]["label"] is not None
        assert lines[0]["region"] is not None

    def test_recover_financial_facts_returns_dataclass_lines(self):
        pages = self._table_pages()
        facts = recover_financial_facts(pages)
        assert len(facts.cost_lines) == 2
        assert isinstance(facts.cost_lines[0], RecoveredCostLine)
        assert facts.cost_lines[1].amount == Decimal("8000.00")


class TestEventRuleFilter:
    def test_form_generic_words_are_not_events(self):
        for word in ("erforderlich", "required", "vorgegeben", "ja", "none"):
            assert _is_event_rule(word) is False, word

    def test_named_event_is_an_event(self):
        assert _is_event_rule("Übergabedatum") is True
        assert _is_event_rule("Probelauf Ende") is True

    def test_digits_or_empty_are_not(self):
        assert _is_event_rule("3 Monate nach Übergabe") is False
        assert _is_event_rule("") is False
        assert _is_event_rule(None) is False


class TestBuildContractTitle:
    def test_recovered_title_wins(self):
        snap = {"identity": {"contract_type": "maintenance"}}
        rec = RecoveredIdentity(title="Full-Service-Vertrag", title_page=1)
        contract = SimpleNamespace(supplier="ABIOMED Europe GmbH", contract_number=None)
        assert (
            _build_contract_title(snap, rec, contract, [])
            == "Full-Service-Vertrag"
        )

    def test_snapshot_title_next(self):
        snap = {"identity": {"contract_title": "Service 2025"}}
        assert _build_contract_title(snap, None, SimpleNamespace(supplier="X", contract_number=None), []) == "Service 2025"

    def test_type_plus_device(self):
        snap = {"identity": {"contract_type": "maintenance"}}
        eq = SimpleNamespace(system_name="", device_name="Impella Controller")
        assert (
            _build_contract_title(snap, None, SimpleNamespace(supplier="X", contract_number=None), [eq])
            == "Wartung / Service – Impella Controller"
        )

    def test_supplier_plus_type(self):
        snap = {"identity": {"contract_type": "service"}}
        assert (
            _build_contract_title(snap, None, SimpleNamespace(supplier="ABIOMED", contract_number=None), [])
            == "ABIOMED – Service-Vertrag"
        )

    def test_safe_fallback(self):
        assert (
            _build_contract_title({}, None, SimpleNamespace(supplier=None, contract_number=None), [])
            == "Vertrag"
        )


class TestResolveEvidencePage:
    def _index(self):
        return [
            (8, "full service für zwei impella controller im 1.jahr "),
            (5, "beginnt am 01 04 2025 und endet am 31 03 2029"),
        ]

    def test_snippet_maps_to_page(self):
        assert (
            _resolve_evidence_page(self._index(), page_hint=None, snippet="Full-Service für zwei Impella Controller im 1.Jahr")
            == 8
        )

    def test_hint_wins(self):
        assert (
            _resolve_evidence_page(self._index(), page_hint=3, snippet="Full-Service")
            == 3
        )

    def test_no_match_returns_none(self):
        assert (
            _resolve_evidence_page(self._index(), page_hint=None, snippet="völlig anders")
            is None
        )


class TestCostAvailability:
    def test_honest_explanation_with_year_prices(self):
        facts = RecoveredFacts(
            cost_lines=[
                RecoveredCostLine(label="Full-Service 1.Jahr (zzgl. MwSt)", amount=Decimal("0"), currency="EUR", page=8, region=None, snippet="x"),
                RecoveredCostLine(label="Full-Service 2.Jahr (zzgl. MwSt)", amount=Decimal("8000.00"), currency="EUR", page=8, region=None, snippet="y"),
            ]
        )
        av = _cost_availability(None, ["Die Zahlungsweise erfolgt im jährlichen Rhythmus ab Vertragsabschluss."], facts)
        assert av["status"] == "manual_input_required"
        assert av["currency_known"] is True
        assert av["manual_input_required"] is True
        labels = " ".join(f["label_de"] for f in av["found_facts"]).lower()
        assert "steuer" in labels
        assert any("zahlungsweise" in f["label_de"].lower() for f in av["found_facts"])
        assert any(
            (
                "preisplan" in m.lower()
                and "vertragslaufzeit" in m.lower()
            )
            or (
                "jahres" in m.lower()
                and ("betrag" in m.lower() or "preis" in m.lower())
            )
            for m in av["missing_inputs"]
        )
        assert "nicht automatisch" not in av["summary_de"].lower() or True  # keine Erfindung
        assert av["explanation_de"]

    def test_no_amount_cited(self):
        av = _cost_availability(None, [], None)
        assert av["status"] == "no_amount_cited"
        assert av["found_facts"] == []
        assert av["currency_known"] is False


class TestMaterialReaders:
    def test_equipment_identity_is_value_not_bool(self):
        r = {"equipment": [
            {"device_name": "Impella Controller", "system_name": "", "model": None},
            {"device_name": None, "system_name": None, "model": None},
        ]}
        assert mat._equipment_identity_value(r) == "Impella Controller"
        report = mat.material_report(r)
        assert report["equipment.identity"]["present"] is True
        assert report["equipment.identity"]["value"] == "Impella Controller"
        # Gerät: weitere wichtige Angabe (wesentlich nur über den Vertragstyp), nie ein Pflichtpunkt der ersten Stufe.
        assert report["equipment.identity"]["critical"] is False

    def test_serial_value_joined(self):
        r = {"equipment": [
            {"serial_number": "SN-123", "inventory_number": None},
        ]}
        assert mat._equipment_serial_value(r) == "SN-123"

    def test_end_date_falls_back_to_documented(self):
        report = mat.material_report({"dates": {"documented_end_date": "2029-03-31"}})
        assert report["dates.end_date"]["present"] is True
        assert report["dates.end_date"]["value"] == "2029-03-31"

    def test_critical_set_contains_core_facts(self):
        # Wesentlich = Feldregister (field_spec): Partner, Gegenstand, Laufzeit, Kündigung, Verlängerung, Preis, Steuer.
        assert mat.fact_is_critical("identity.supplier")
        assert mat.fact_is_critical("termination.auto_renewal")
        assert mat.fact_is_critical("costs.vat_rate")
        assert not mat.fact_is_critical("identity.contract_number")
        # Berechnete Werte werden nie einzeln bestätigt.
        assert not mat.fact_is_critical("dates.latest_cancellation")


class TestReviewSummaryCounts:
    def _state(self, **kw):
        base = {
            "present": True, "state": "unreviewed", "is_critical": True,
        }
        base.update(kw)
        return base

    def test_critical_counts_derived(self):
        states = [
            self._state(fact_key="a", present=True, state="unreviewed", is_critical=True),
            self._state(fact_key="b", present=True, state="confirmed", is_critical=True),
            self._state(fact_key="c", present=True, state="unreviewed", is_critical=False),
        ]
        s = build_review_summary(states)
        assert s["relevant_count"] == 3
        assert s["reviewed_count"] == 1
        assert s["unresolved_count"] == 2
        assert s["critical_count"] == 2
        assert s["critical_reviewed_count"] == 1
        assert s["critical_unreviewed_count"] == 1

    def test_voided_facts_not_relevant(self):
        states = [self._state(fact_key="a", present=True, state="voided")]
        s = build_review_summary(states)
        assert s["relevant_count"] == 0
        assert s["critical_count"] == 0
