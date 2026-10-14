"""Fokussierte Regression – UAT Re-Test (Defect 1-4).

Deckt NUR die neuen, generischen Fix-Schichten der Re-Test-Runde ab (kein DB,
kein OpenAI/LLM, kein Dateisystem/OCR):

- Defect 1: ein Fakt hat EINE kanonische Quell-Seite (Reihenfolge-Fix +
  Dedupe `_settle_canonical_evidence`; Laufzeitdaten setzen eigene Evidence-Refs)
- Defect 2: Leistungsumfang als Drei-Zustand-Semantik (`_scope_concept_verdict`)
- Defect 3: System-Identitaet ("Impella AIC System") vor den Komponenten
- Defect 4: deutsche Labels statt roher Keys (DTO-Anteile)
"""

from __future__ import annotations

from datetime import date

from app.contracts.detail.recovery import (  # noqa: E402
    RecoveredLaufzeit,
    _find_system_identity,
    recover_financial_facts,
)
from app.contracts.detail.service import (  # noqa: E402
    _SCOPE_TERMS,
    _dates_section,
    _price_schedule_items,
    _scope_concept_verdict,
    _scope_text_analysis,
    _settle_canonical_evidence,
    _variable_charge_items,
)
from app.contracts.review import material as mat  # noqa: E402


# ---------------------------------------------------------------------------
# Defect 3 – System-Identitaet (Betreff-Zeile "für das Impella® AIC System")
# ---------------------------------------------------------------------------
class TestSystemIdentityRecovery:
    @staticmethod
    def _subject_page():
        return [{
            "page": 1,
            "text": "Full-Service-Vertrag für das Impella® AIC System Vertr.-Nr.: 40015645",
            "elements": [
                {"text": "ABIOMED Europe GmbH", "region": {"x0": 0, "y0": 1, "x1": 100, "y1": 20}},
                {"text": "für das Impella® AIC System", "region": {"x0": 0, "y0": 25, "x1": 200, "y1": 45}},
                {"text": "Vertr.-Nr.: 40015645", "region": {"x0": 0, "y0": 50, "x1": 150, "y1": 70}},
            ],
        }]

    def test_subject_line_found(self):
        res = _find_system_identity(self._subject_page())
        assert res is not None
        assert res["system"] == "Impella AIC System"
        assert res["page"] == 1

    def test_no_subject_returns_none(self):
        assert (
            _find_system_identity([
                {"page": 1, "text": "Wartungsvertrag", "elements": [
                    {"text": "Servicevereinbarung", "region": {"x0": 0, "y0": 1, "x1": 50, "y1": 20}},
                ]},
            ])
            is None
        )

    def test_recover_financial_facts_carries_system_identity(self):
        pages = self._subject_page()
        pages.append({
            "page": 5,
            "text": "Der Full-Service-Vertrag beginnt am 01.04.2025 und endet am "
                    "31.03.2029. Er hat eine Laufzeit von 4 Jahren und wird nicht "
                    "automatisch verlängert.",
        })
        facts = recover_financial_facts(pages)
        assert facts.identity.system_identity == "Impella AIC System"
        assert facts.identity.system_identity_page == 1


class TestEquipmentIdentitySystemFirst:
    def test_system_precedes_components(self):
        r = {
            "identity": {"system_identity": "Impella AIC System"},
            "equipment": [{"device_name": "Impella Controller", "system_name": "", "model": None}],
        }
        assert mat._equipment_identity_value(r) == "Impella AIC System | Impella Controller"

    def test_system_never_dropped_by_component(self):
        r = {
            "identity": {"system_identity": "Impella AIC System"},
            "equipment": [
                {"device_name": "Impella Controller", "system_name": "", "model": None},
                {"device_name": None, "system_name": None, "model": None},
            ],
        }
        assert mat._equipment_identity_value(r) == "Impella AIC System | Impella Controller"

    def test_without_system_components_only(self):
        r = {"equipment": [{"device_name": "Impella Controller", "system_name": "", "model": None}]}
        assert mat._equipment_identity_value(r) == "Impella Controller"


# ---------------------------------------------------------------------------
# Defect 1 – kanonische Evidence / Quell-Seite (Dedupe + Laufzeit-Refs)
# ---------------------------------------------------------------------------
class TestSettleCanonicalEvidence:
    def test_recovered_replaces_extraction_for_same_field_ref(self):
        refs = [
            {"evidence_id": "ext-1", "field_ref": "termination.evidence", "page": 3},
            {"evidence_id": "recovered:dates.start_date", "field_ref": "dates.start_date", "page": 5},
            {"evidence_id": "ext-2", "field_ref": "dates.start_date", "page": 2},
        ]
        out = _settle_canonical_evidence(refs)
        by_ref = {r["field_ref"]: r for r in out}
        assert by_ref["dates.start_date"]["evidence_id"] == "recovered:dates.start_date"
        assert by_ref["dates.start_date"]["page"] == 5
        assert by_ref["termination.evidence"]["page"] == 3

    def test_first_recovered_wins(self):
        refs = [
            {"evidence_id": "recovered:dates.start_date", "field_ref": "dates.start_date", "page": 5},
            {"evidence_id": "recovered:dates.start_date.2", "field_ref": "dates.start_date", "page": 1},
        ]
        out = _settle_canonical_evidence(refs)
        assert len(out) == 1
        assert out[0]["page"] == 5

    def test_unref_source_kept(self):
        out = _settle_canonical_evidence([{"evidence_id": "x", "page": 3}])
        assert len(out) == 1


class TestDatesSectionRecoveredEvidence:
    def test_recovered_dates_set_canonical_evidence_refs(self):
        snap = {
            "termination": {"automatic_renewal": True},
            "dates": {"start_date": {"date": "2025-04-01", "condition": None, "requires_review": False}},
        }
        rec = RecoveredLaufzeit(
            absolute_start=date(2025, 4, 1),
            absolute_end=date(2029, 3, 31),
            duration_years=4,
            auto_renewal=False,
        )
        dates = _dates_section(calc=None, snapshot=snap, recovered_laufzeit=rec)
        assert dates["start_date"] == "2025-04-01"
        assert dates["start_date_evidence"] == "dates.start_date"
        assert dates["documented_end_date"] == "2029-03-31"
        assert dates["documented_end_evidence"] == "dates.end_date"
        assert dates["duration_years"] == 4
        assert dates["duration_evidence"] == "dates.duration"
        # Defect 1: dokumentiertes "Nein" schlaegt Extraktion "Ja" + Evidence.
        assert dates["automatic_renewal"] is False
        assert dates["auto_renewal_evidence"] == "termination.auto_renewal"


# ---------------------------------------------------------------------------
# Defect 2 – Leistungsumfang: Drei-Zustand-Semantik (deterministisch)
# ---------------------------------------------------------------------------
class TestScopeTriStateVerdicts:
    @staticmethod
    def _analysis():
        pages = [
            {
                "page": 3,
                "text": (
                    "Sollte ein Notdienst erforderlich sein: Leistungen an Samstagen, "
                    "Sonn- und Feiertagen fallen nicht in den Rahmen dieses Vertrages "
                    "und werden gesondert vergütet."
                ),
            },
            {
                "page": 7,
                "text": (
                    "Sie umfasst die folgenden Leistungen: Sichtprüfung auf äußere "
                    "Mängel und Vollständigkeit Überprüfung der mechanischen Sicherheit "
                    "Verschleißkontrolle von mechanisch beweglichen Teilen. Austausch von "
                    "Verschleißteilen gemäß Herstellervorgaben (ABIOMED) wie z.B.: Akkus "
                    "und Batterien Lüftereinheiten. Alle Reparaturarbeiten (inklusive "
                    "Arbeitslohn und Materialkosten). Softwarepflege und Aufspielen von "
                    "Softwareupdates. Die einmal jährlich durchzuführende Wartung wird von "
                    "ABIOMED oder einem von ABIOMED Bevollmächtigten an den "
                    "Wartungsobjekten durchgeführt."
                ),
            },
        ]
        return _scope_text_analysis(pages)

    @staticmethod
    def _included_items():
        return [
            "Wartung",
            "Reparatur",
            "Sichtprüfung auf äußere Mängel und Vollständigkeit",
            "Durchführung von Updates (FCN; Field Change Note)",
            "Softwarepflege und Aufspielen von Softwareupdates",
        ]

    @staticmethod
    def _excluded_items():
        return ["Optionale FCNs"]

    def test_maintenance_included(self):
        out = _scope_concept_verdict(
            "maintenance", _SCOPE_TERMS["maintenance"],
            self._included_items(), self._excluded_items(), self._analysis(),
        )
        assert out[0] == "included"
        assert out[1] == 7
        assert out[3] == "scope.included_services"

    def test_repair_included(self):
        out = _scope_concept_verdict(
            "repair", _SCOPE_TERMS["repair"],
            self._included_items(), self._excluded_items(), self._analysis(),
        )
        assert out[0] == "included"
        assert out[1] == 7

    def test_inspection_included_via_anchor(self):
        out = _scope_concept_verdict(
            "inspection", _SCOPE_TERMS["inspection"],
            self._included_items(), self._excluded_items(), self._analysis(),
        )
        assert out[0] == "included"
        assert out[1] == 7

    def test_emergency_excluded_from_canonical_text(self):
        out = _scope_concept_verdict(
            "emergency_service", _SCOPE_TERMS["emergency_service"],
            self._included_items(), self._excluded_items(), self._analysis(),
        )
        assert out[0] == "excluded"
        assert out[1] == 3
        assert out[3] == "scope.excluded_services"

    def test_calibration_not_established(self):
        out = _scope_concept_verdict(
            "calibration", _SCOPE_TERMS["calibration"],
            self._included_items(), self._excluded_items(), self._analysis(),
        )
        assert out[0] == "not_established"
        assert out[1] is None

    def test_remote_support_not_established(self):
        out = _scope_concept_verdict(
            "remote_support", _SCOPE_TERMS["remote_support"],
            self._included_items(), self._excluded_items(), self._analysis(),
        )
        assert out[0] == "not_established"
        assert out[1] is None


# ---------------------------------------------------------------------------
# Defect 4 – deutsche Labels statt roher Keys (Register + fallback)
# ---------------------------------------------------------------------------
class TestGermanLabels:
    def test_scope_status_labels_de(self):
        assert _SCOPE_TERMS["maintenance"] == ("wartung",)

    def test_material_fact_label(self):
        assert mat.fact_label("termination.auto_renewal") == "Automatische Verlängerung"
        assert mat.fact_label("equipment.identity") == "Geräte-Identität"
        assert mat.fact_label("unbekannt.key") == "unbekannt.key"


# ---------------------------------------------------------------------------
# UAT Defect Batch F – generische Evidence-Linkage (Review)
# ---------------------------------------------------------------------------
class TestFactEvidenceLinking:
    @staticmethod
    def _by_ref(refs):
        out = {}
        for ref in refs:
            out.setdefault(ref, []).append({"field_ref": ref, "page": 3})
        return out

    def test_exact_matches_first(self):
        from app.contracts.review.service import _link_fact_evidence

        by_ref = self._by_ref(["dates.start_date"])
        specific, fallback = _link_fact_evidence("dates.start_date", by_ref)
        assert [e["page"] for e in specific] == [3]
        assert fallback == []

    def test_harness_per_fact_rows_bind(self):
        from app.contracts.review.service import _link_fact_evidence

        by_ref = self._by_ref(["identity.supplier.evidence.0"])
        specific, _ = _link_fact_evidence("identity.supplier", by_ref)
        assert len(specific) == 1

    def test_harness_field_alias_binds_to_material_key(self):
        from app.contracts.review.service import _link_fact_evidence

        by_ref = self._by_ref([
            "termination.automatic_renewal.evidence.0",
            "costs.annual_cost.evidence.1",
        ])
        specific, _ = _link_fact_evidence("termination.auto_renewal", by_ref)
        assert len(specific) == 1
        specific, _ = _link_fact_evidence("costs.annual", by_ref)
        assert len(specific) == 1

    def test_cost_tax_recovered_rows_bind(self):
        from app.contracts.review.service import _link_fact_evidence

        by_ref = self._by_ref([
            "costs.tax_table.net",
            "costs.tax_table.vat",
            "costs.tax_table.gross",
        ])
        assert len(_link_fact_evidence("costs.monthly_net", by_ref)[0]) == 1
        assert len(_link_fact_evidence("costs.vat_rate", by_ref)[0]) == 1
        assert len(_link_fact_evidence("costs.monthly_gross", by_ref)[0]) == 1

    def test_equipment_prefixes_bind(self):
        from app.contracts.review.service import _link_fact_evidence

        by_ref = self._by_ref([
            "identity_equipment.evidence.0",
            "equipment.evidence.1",
            "identity.system_identity",
        ])
        for fact_key in ("equipment.identity", "equipment.serial"):
            specific, _ = _link_fact_evidence(fact_key, by_ref)
            assert len(specific) == 3

    def test_scope_and_sla_facts_bind_their_own_rows(self):
        from app.contracts.review.service import _link_fact_evidence

        by_ref = self._by_ref([
            "scope.included_services",
            "sla.service_hours.evidence.0",
            "sla.response_time.evidence.0",
            "services.repair.evidence.1",
            "scope.repair",
        ])
        specific, _ = _link_fact_evidence("scope.repair", by_ref)
        assert sorted(ev["field_ref"] for ev in specific) == ["scope.repair", "services.repair.evidence.1"]
        specific, _ = _link_fact_evidence("sla.service_hours", by_ref)
        assert [ev["field_ref"] for ev in specific] == ["sla.service_hours.evidence.0"]

    def test_group_row_only_as_fallback(self):
        from app.contracts.review.service import _link_fact_evidence

        only_group = self._by_ref(["costs.evidence"])
        specific, fallback = _link_fact_evidence("costs.annual", only_group)
        assert specific == []
        assert len(fallback) == 1
        assert fallback[0]["field_ref"] == "costs.evidence"

        with_specific = self._by_ref(["costs.evidence", "costs.annual_cost.evidence.0"])
        specific, fallback = _link_fact_evidence("costs.annual", with_specific)
        assert len(specific) == 1
        assert fallback == []

    def test_unrelated_refs_never_bind(self):
        from app.contracts.review.service import _link_fact_evidence

        by_ref = self._by_ref(["identity.contract_title", "dates.duration"])
        specific, fallback = _link_fact_evidence("identity.contract_number", by_ref)
        assert specific == []
        assert fallback == []


class TestAnalysisHistorySafeLabels:
    """Round-2: Analysehistorie zeigt deutsche, sichere Labels statt roher KI-Fehler."""

    def _run(self, status="partial", message=None, error=None):
        class R:
            pass

        r = R()
        r.status = status
        r.message = message
        r.error = error
        return r

    def _summary(self, success=0, failure=0):
        class S:
            pass

        s = S()
        s.success_count = success
        s.failure_count = failure
        s.page_count = 9
        s.doc_type = "pdf"
        s.processed_at = None
        return s

    def test_status_labels_german(self):
        from app.api.routes.processing_jobs import _status_label_de

        assert _status_label_de("succeeded") == "Erfolgreich"
        assert _status_label_de("partial") == "Teilweise (prüfen)"
        assert _status_label_de("failed") == "Fehlgeschlagen"
        assert _status_label_de("running") == "Wird verarbeitet"

    def test_harness_failure_ai_unavailable_maps_to_safe_text(self):
        from app.api.routes.processing_jobs import _result_label_de

        r = self._run(error="HarnessFailure purpose=direct category=AIUnavailableError")
        label = _result_label_de(r, self._summary())
        assert label == "Lokale KI nicht verfügbar."
        assert "HarnessFailure" not in label

    def test_runtime_error_maps_to_safe_text(self):
        from app.api.routes.processing_jobs import _result_label_de

        r = self._run(error="RuntimeError: something internal")
        label = _result_label_de(r, self._summary())
        assert label == "Verarbeitung fehlgeschlagen."
        assert "RuntimeError" not in label

    def test_unknown_error_never_leaks_raw_text(self):
        from app.api.routes.processing_jobs import _result_label_de

        r = self._run(error="zoneinfo.ZoneInfoNotFoundError: 'Europe/Berlin' traceback ...")
        label = _result_label_de(r, self._summary())
        assert "zoneinfo" not in label.lower()
        assert "ZoneInfoNotFoundError" not in label

    def test_succeeded_run_shows_counts(self):
        from app.api.routes.processing_jobs import _result_label_de

        r = self._run(status="succeeded")
        label = _result_label_de(r, self._summary(success=5, failure=7))
        assert label == "5 erfolgreich / 7 fehlgeschlagen"

    def test_partial_run_with_successes_stays_honest(self):
        from app.api.routes.processing_jobs import _result_label_de

        r = self._run(status="partial")
        label = _result_label_de(r, self._summary(success=3, failure=2))
        assert "Teilweise analysiert – 3 erfolgreich / 2 fehlgeschlagen" == label


class TestPriceScheduleAndVariableCharges:
    """Round-2: belegter Preisplan + bedingte Positionen ehrlich getrennt."""

    def test_price_schedule_rows(self):
        costs = {
            "scheduled_prices": [
                {"period_index": 1, "period_label": "1. Jahr", "amount": {"amount": "0", "currency": "EUR"}},
                {"period_index": 4, "period_label": "4. Jahr", "amount": {"amount": 8000, "currency": "EUR"}},
                {"period_index": 2, "period_label": "2. Jahr", "amount": {"amount": 8000, "currency": "EUR"}},
                {"period_index": 3, "period_label": "3. Jahr", "amount": {"amount": 8000, "currency": "EUR"}},
            ]
        }
        rows = _price_schedule_items(costs)
        assert [r["period_index"] for r in rows] == [1, 2, 3, 4]
        assert rows[0]["amount"] == "0"
        assert rows[1]["amount"] == 8000
        assert rows[3]["currency"] == "EUR"

    def test_price_schedule_skips_empty_entries(self):
        costs = {
            "scheduled_prices": [
                {"period_index": 5, "amount": {"amount": None, "currency": "EUR"}},
                {"period_index": 5, "amount": {}},
                "bogus",
            ]
        }
        assert _price_schedule_items(costs) == []

    def test_price_schedule_empty(self):
        assert _price_schedule_items(None) == []
        assert _price_schedule_items({}) == []

    def test_variable_charge_unit_label(self):
        costs = {
            "variable_charges": [
                {"label": "Fixed per call", "amount": {"amount": "2226.00", "currency": "EUR"}, "unit": "per_call", "condition": "Einsatz ausserhalb der Servicezeiten"},
            ]
        }
        items = _variable_charge_items(costs)
        assert len(items) == 1
        assert items[0]["amount"] == "2226.00"
        assert items[0]["unit_label_de"] == "pro Einsatz"
        assert items[0]["condition"] == "Einsatz ausserhalb der Servicezeiten"
        assert "nie zum Fixwert addiert" in items[0]["note_de"]

    def test_variable_charge_defaults(self):
        costs = {"variable_charges": [{"amount": {"amount": 50, "currency": "EUR"}}]}
        items = _variable_charge_items(costs)
        assert items[0]["label"] == "Variable Position"
        assert items[0]["unit"] is None
        assert items[0]["unit_label_de"] is None

    def test_variable_charge_empty(self):
        assert _variable_charge_items(None) == []
        assert _variable_charge_items({"variable_charges": []}) == []