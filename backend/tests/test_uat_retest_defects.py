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
    _scope_concept_verdict,
    _scope_text_analysis,
    _settle_canonical_evidence,
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