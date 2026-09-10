"""JSON-Schema + Metadaten der Extrakitions-Feldgruppen (STEP 8B-Semantik).

Für jede Feldgruppe wird das JSON-Schema deterministisch aus dem hinterlegten
Pydantic-Modell abgeleitet (kein zweites, manuell gepflegtes Schema). Die
Definition hier zentralisiert, welche Gruppe welche Contract-Abschnitte füllt.
"""

from __future__ import annotations

from app.ai.groups.models import (
    CostsPaymentGroup,
    DatesTerminationGroup,
    IdentityEquipmentGroup,
    ServicesSlaGroup,
)
from app.ai.schema import pydantic_json_schema


class GroupSpec:
    """Beschreibt eine Extraktions-Feldgruppe."""

    def __init__(
        self,
        name: str,
        model: type,
        schema: dict,
        prompt: str,
        apply,
    ) -> None:
        self.name = name
        self.model = model
        self.schema = schema
        self.prompt = prompt
        self.apply = apply  # apply(contract, group) -> überträgt die Gruppe deterministisch


def group_specs() -> dict[str, GroupSpec]:
    """Liefert die konfigurierten Feldgruppen (Name -> GroupSpec)."""
    return {
        "identity_equipment": GroupSpec(
            name="identity_equipment",
            model=IdentityEquipmentGroup,
            schema=pydantic_json_schema(IdentityEquipmentGroup),
            prompt=IDENTITY_EQUIPMENT_PROMPT,
            apply=_apply_identity_equipment,
        ),
        "dates_termination": GroupSpec(
            name="dates_termination",
            model=DatesTerminationGroup,
            schema=pydantic_json_schema(DatesTerminationGroup),
            prompt=DATES_TERMINATION_PROMPT,
            apply=_apply_dates_termination,
        ),
        "costs_payment": GroupSpec(
            name="costs_payment",
            model=CostsPaymentGroup,
            schema=pydantic_json_schema(CostsPaymentGroup),
            prompt=COSTS_PAYMENT_PROMPT,
            apply=_apply_costs_payment,
        ),
        "services_sla": GroupSpec(
            name="services_sla",
            model=ServicesSlaGroup,
            schema=pydantic_json_schema(ServicesSlaGroup),
            prompt=SERVICES_SLA_PROMPT,
            apply=_apply_services_sla,
        ),
    }


# ------------------------------------------------------------- Übernahme auf Contract

def _apply_identity_equipment(contract, group: IdentityEquipmentGroup) -> None:
    contract.identity = group.identity
    contract.equipment = list(group.equipment)


def _apply_dates_termination(contract, group: DatesTerminationGroup) -> None:
    contract.dates = group.dates
    contract.termination = group.termination


def _apply_costs_payment(contract, group: CostsPaymentGroup) -> None:
    contract.costs = group.costs
    contract.payment = group.payment


def _apply_services_sla(contract, group: ServicesSlaGroup) -> None:
    contract.services = group.services
    contract.sla = group.sla


# ------------------------------------------------------------- Prompts (deutsch, semantik-fokussiert)

_COMMON = (
    "Du bist ein präziser Analysator für deutsche Wartungs- und Serviceverträge von Medflux.\n"
    "Die JSON-Ausgabe-Struktur (Feldnamen, Enum-Werte, Typen) wird technisch erzwungen – "
    "benutze sie GENAU so. \n"
    "ANTI-HALLUZINATION: Extrahiere NUR Fakten, die wörtlich oder eindeutig durch den Text "
    "belegt sind. Fehlender Wert => null, leere Liste. Erfinde NICHT: Daten, Dienstleister, "
    "Geräte, Kosten, Laufzeiten, Kündigungsfristen, Vertragsnummern, Beleg-Quellen.\n"
    "QUELLEN-NACHWEIS: Für WICHTIGE Angaben setze evidence; bei DOCX KEINE Seitennummer "
    "(page bleibt null) – nutze source_type 'paragraph'|'table' + paragraph_index/table_index "
    "(jeweils 1-basiert) + einen KURZEN wörtlichen source_text (max. ~60–80 Zeichen, knappes "
    "Fragment, nie erfundene Belege). Bei PDF: page = echte Seitennummer.\n"
    "Confidence konservativ: 0.90–1.00 eindeutig; 0.75–0.89 stark gestützt; 0.50–0.74 mehrdeutig; "
    "< 0.50 zusätzlich requires_review=true.\n"
    "KEINE BERECHNUNGEN (spätester Kündigungstermin, Restlaufzeit, Warnstufen, Kostenaggregation)."
)

IDENTITY_EQUIPMENT_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Identität & Geräte:\n"
    "- identity.contract_number: Vertrags-/Angebotsnummer (exakte Zahl/Buchstabenfolge). "
    "NUR setzen, wenn eine Nummer im Text steht; sonst null. Keine generische Bezeichnung erfinden.\n"
    "- identity.contract_type: exakt aus maintenance|service|lease|rental|other|unknown; "
    "deutsche Begriffe übersetzen ('Wartungsvertrag'->maintenance, 'Servicevertrag'->service).\n"
    "- identity.supplier = Dienstleister/Lieferant; identity.customer = Auftraggeber/Kunde; "
    "identity.contractor = ggf. weiterer Auftragnehmer.\n"
    "- identity.department/location: nur wenn belegbar.\n"
    "- equipment: Liste der abgedeckten Geräte/Anlagen (Name, Hersteller/Marke, Modell, "
    "Seriennummer, Inventarnummer, System/Kategorie, Gerätetyp, Standort/Abteilung). "
    "Doppelte/fast identische Einträge vermeiden.\n"
    "- equipment[].inventory_number/serial_number: NUR wenn wörtlich belegt; nie erfinden. "
    "equipment[].coverage_start/coverage_end: nur bei expliziter Abdeckungs-Zeit (FlexibleDate).\n"
    "- equipment[].service_scope/included_services/excluded_services/sla_notes: nur bei Beleg "
    "(Wartung/Installation/Ersatzteile/Reaktionszeit etc.).\n"
    "- equipment[].evidence: Quellen-Nachweis der Geräte-Zuordnung (Seite bei PDF; bei DOCX "
    "paragraph/table-Index statt erfundener Seite), ein kurzer wörtlicher source_text.\n"
    "- Lege NUR Geräte an, die der Vertrag tatsächlich abdeckt. Keine Geräte erfinden."
)

DATES_TERMINATION_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Laufzeit & Kündigung:\n"
    "- dates.start_date/end_date sind FlexibleDate: ECHTES Kalenderdatum (ISO YYYY-MM-DD) ODER "
    "ereignisbasiert => {date: null, condition: '...', requires_review: true}. Nie ein erfundenes "
    "Kalenderdatum erfinden, wenn es ereignisbasiert ist.\n"
    "- dates.duration = Gesamtlaufzeit, dates.minimum_duration = feste Mindestbindung "
    "(value + unit aus days|weeks|months|years|hours). Einheit exakt.\n"
    "- termination.cancellation_period = Kündigungsfrist (Dauer + Einheit). "
    "termination.automatic_renewal = bool (verlängert sich automatisch). "
    "termination.renewal_period = Länge der Verlängerung. "
    "termination.cancellation_condition/extraordinary_termination nur als Text bei Beleg.\n"
    "Erfinde KEINE Kündigungsfristen oder Verlängerungen."
)

COSTS_PAYMENT_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Kosten & Zahlung (SEMANTISCHE GELDKLASSIFIKATION):\n"
    "- Klassifiziere jeden Betrag nach Bedeutung: costs.total_contract_value = Gesamtwert; "
    "costs.annual_cost = jährliche Gebühr; costs.monthly_cost = monatliche; "
    "costs.quarterly_cost = quartalsweise; costs.semi_annual_cost = halbjährlich; "
    "costs.one_time_cost = Einmalwert; costs.setup_installation_cost = Aufbau/Installation (einmalig); "
    "costs.maintenance_fee = Wartungsgebühr; costs.hourly_rate = Stundensatz.\n"
    "- Money: amount (Zahl ohne Tausender-Trennzeichen), currency (3-Buchstaben-Code groß, z. B. EUR), "
    "period (annual|monthly|quarterly|semi_annual|once|total) – bei wiederkehrenden Beträgen die "
    "Wiederkehrperiode setzen (z. B. 'monatlich' -> monthly). NICHT aus einem Jahresbetrag einen "
    "Monatswert 'raten' – nur den belegten Betrag benennen.\n"
    "- price_adjustment_clause/price_indexation: nur wenn explizit (z. B. Indexierung, Preisanpassung).\n"
    "- costs.tax_basis: NUR wenn der Vertrag Netto/Brutto explizit benennt (net|gross); fehlende "
    "Angabe bleibt null – niemals eine 19 %-Mehrwertsteuer annehmen. costs.tax_rate_percent nur bei "
    "expliziter Prozentangabe.\n"
    "- payment.billing_interval exakt aus monthly|quarterly|semi_annual|annual|once|other; "
    "'monatlich'->monthly, 'jährlich'/pro Jahr->annual. Nur belegt setzen, sonst other.\n"
    "- payment.payment_deadline_days = Zahlungsfrist in Tagen ('30 Tage' => 30). "
    "payment.payment_terms = knappe, belegte Textfassung (z. B. '30 Tage netto')."
)

SERVICES_SLA_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Leistungen & Service-Level:\n"
    "- services.included_services / excluded_services als Listen belegter Leistungen "
    "(z. B. 'Wartung', 'Reparatur', 'Vollwartung'). bool-Flags (maintenance, inspection, repair, "
    "calibration, software_updates, remote_support, technical_support, spare_parts_included, "
    "consumables_included, emergency_service) nur bei Beleg setzen.\n"
    "- sla.response_time/resolution_time/service_hours/emergency_availability: TimeValue mit "
    "value + unit (aus days|weeks|months|years|hours) + original_text (kurzes wörtliches Fragment). "
    "availability_24_7 bool. sla_notes knapp.\n"
    "Erfinde keine SLA-Werte; fehlend => null."
)


def group_order() -> list[str]:
    """Deterministische Reihenfolge der Gruppen für eine stabile Verarbeitung."""
    return ["identity_equipment", "dates_termination", "costs_payment", "services_sla"]
