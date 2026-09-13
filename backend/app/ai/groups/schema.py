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
        self.apply = apply


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


_COMMON = (
    "Du bist ein präziser Analysator für deutsche Wartungs- und Serviceverträge von Medflux.\n"
    "Die JSON-Ausgabe-Struktur (Feldnamen, Enum-Werte, Typen) wird technisch erzwungen – benutze sie GENAU so.\n"
    "ANTI-HALLUZINATION: Extrahiere NUR Fakten, die wörtlich oder eindeutig durch den Text belegt sind. "
    "Fehlender oder nicht entscheidbarer Wert => null; fehlende Liste => []. Erfinde NICHT: Daten, Dienstleister, "
    "Geräte, Kosten, Laufzeiten, Kündigungsfristen, Vertragsnummern oder Beleg-Quellen.\n"
    "DREIWERTIGE BOOL-SEMANTIK: Bei Optional[bool] bedeutet fehlende Information IMMER null. "
    "true nur bei explizit positiver Aussage/Markierung; false NUR bei expliziter Verneinung, Ausschluss- oder Nein-Angabe. "
    "Aus Schweigen/Fehlen darf NIEMALS false werden. Der Default für einen nicht belegten Bool ist null, NICHT false.\n"
    "WICHTIG FÜR JEDEN CHUNK: Wenn der aktuelle Auszug keinen positiven UND keinen negativen Beleg für ein Optional[bool]-Feld enthält, "
    "muss dieses Feld null sein. Ein Modell darf eine leere/fehlende Aussage niemals als false interpretieren.\n"
    "TABELLEN: Tabellenzeilen und Spaltenüberschriften gemeinsam lesen. Häkchen/X/Ja in einer Leistungs-Spalte gelten nur "
    "für genau diese Spalte. Eine klar markierte Leistungszeile ist ein expliziter Beleg. OCR-Rauschen nie als neuen Fakt deuten.\n"
    "QUELLEN-NACHWEIS: Für WICHTIGE Angaben setze evidence; bei DOCX KEINE Seitennummer (page bleibt null) – "
    "nutze source_type 'paragraph'|'table' + paragraph_index/table_index (jeweils 1-basiert) + einen KURZEN wörtlichen "
    "source_text (max. ~60–80 Zeichen, knappes Fragment, nie erfundene Belege). Bei PDF: page = echte Seitennummer.\n"
    "Confidence konservativ: 0.90–1.00 eindeutig; 0.75–0.89 stark gestützt; 0.50–0.74 mehrdeutig; "
    "< 0.50 zusätzlich requires_review=true.\n"
    "KEINE BERECHNUNGEN (spätester Kündigungstermin, Restlaufzeit, Warnstufen, Kostenaggregation)."
)

IDENTITY_EQUIPMENT_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Identität & Geräte:\n"
    "- identity.contract_title: den expliziten Vertragstitel/Betreff übernehmen, wenn er den Vertragsgegenstand bezeichnet "
    "(z. B. 'Servicevereinbarung X', 'Servicevertrag Y'). Nicht wegen fehlender Überschrift auf null setzen, wenn ein eindeutiger Betreff vorliegt.\n"
    "- identity.contract_number: Vertrags-/Angebotsnummer (exakte Zahl/Buchstabenfolge). NUR setzen, wenn eine Nummer als "
    "Vertrags-/Angebotsnummer belegt ist; Bestellnummern nicht als Vertragsnummer umdeuten. Sonst null.\n"
    "- identity.contract_type: exakt aus maintenance|service|lease|rental|other|unknown; deutsche Begriffe übersetzen "
    "('Wartungsvertrag'->maintenance, 'Servicevertrag'/'Servicevereinbarung'->service).\n"
    "- identity.supplier = Dienstleister/Lieferant; identity.customer = Auftraggeber/Kunde; identity.contractor = ggf. weiterer Auftragnehmer.\n"
    "- CUSTOMER-PRIORITÄT: Suche ausdrücklich nach dem Krankenhaus/Auftraggeber in Vertragskopf, Empfänger-/Adressblock, E-Mail-Begleittext "
    "und Signatur-/Korrespondenzkontext. Eine eindeutig benannte juristische Krankenhausgesellschaft, die als Empfänger/Auftraggeber erscheint, "
    "ist identity.customer, auch wenn sie nicht mit dem Wort 'Kunde' beschriftet ist.\n"
    "- Wenn derselbe Auszug einen Dienstleister/Lieferanten und eine andere Krankenhausgesellschaft enthält, ordne die Krankenhausgesellschaft "
    "dem customer zu, sofern der Kontext sie als Empfänger/Auftraggeber zeigt. Nicht wegen OCR-Rauschen im Vertragskopf einen sauber lesbaren "
    "Kundennamen aus Begleittext verwerfen.\n"
    "- identity.department/location: nur wenn belegbar.\n"
    "- equipment: Liste der tatsächlich abgedeckten Geräte/Anlagen. Produkt-/Gerätenamen auch aus Formulierungen wie "
    "'Servicevertrag ... für <Gerät>' oder '<Geräteart> <Modell>' erkennen. Ein eindeutiger Vertragsgegenstand wie 'für Accutron MR' "
    "ist ein Beleg für ein Equipment-Objekt, auch wenn Serien-/Inventarnummer noch fehlen.\n"
    "- equipment[].device_name/model: den belegten Produkt-/Modellnamen übernehmen; Hersteller nur setzen, wenn als Hersteller/Marke belegt.\n"
    "- equipment[].inventory_number/serial_number: NUR wenn wörtlich belegt; eine Aussage, dass die Nummer noch fehlt, bedeutet null.\n"
    "- equipment[].coverage_start/coverage_end: nur bei expliziter Abdeckungs-Zeit (FlexibleDate).\n"
    "- equipment[].service_scope/included_services/excluded_services/sla_notes: nur bei Beleg.\n"
    "- equipment[].evidence: Quellen-Nachweis der Geräte-Zuordnung.\n"
    "- Lege NUR Geräte an, die der Vertrag tatsächlich abdeckt. Keine Geräte erfinden."
)

DATES_TERMINATION_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Laufzeit & Kündigung:\n"
    "- dates.start_date/end_date sind FlexibleDate: ECHTES Kalenderdatum (ISO YYYY-MM-DD) ODER ereignisbasiert => "
    "{date: null, condition: '...', requires_review: true}. Nie ein Kalenderdatum erfinden.\n"
    "- dates.duration = Gesamtlaufzeit, dates.minimum_duration = feste Mindestbindung (value + unit aus days|weeks|months|years|hours).\n"
    "- termination.cancellation_period = Kündigungsfrist; termination.renewal_period = Länge der Verlängerung.\n"
    "- termination.automatic_renewal: true NUR wenn automatische Verlängerung ausdrücklich belegt ist; false NUR wenn ausdrücklich "
    "ausgeschlossen/verneint. Wenn der Auszug dazu schweigt: null.\n"
    "- termination.cancellation_condition/extraordinary_termination nur als Text bei Beleg.\n"
    "Erfinde KEINE Kündigungsfristen oder Verlängerungen."
)

COSTS_PAYMENT_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Kosten & Zahlung (SEMANTISCHE GELDKLASSIFIKATION):\n"
    "- Klassifiziere jeden Betrag nach Bedeutung: costs.total_contract_value = Gesamtwert; costs.annual_cost = jährliche Gebühr; "
    "costs.monthly_cost = monatliche; costs.quarterly_cost = quartalsweise; costs.semi_annual_cost = halbjährlich; "
    "costs.one_time_cost = Einmalwert; costs.setup_installation_cost = Aufbau/Installation; costs.maintenance_fee = Wartungsgebühr; "
    "costs.hourly_rate = Stundensatz.\n"
    "- Money: amount, currency, period nur aus belegter Angabe. NICHT aus einem Jahresbetrag einen Monatswert raten.\n"
    "- price_adjustment_clause/price_indexation nur wenn explizit.\n"
    "- costs.tax_basis nur wenn Netto/Brutto explizit benannt; tax_rate_percent nur bei expliziter Prozentangabe.\n"
    "- payment.billing_interval aus monthly|quarterly|semi_annual|annual|once|other; nur belegt setzen, sonst other.\n"
    "- payment.payment_deadline_days und payment.payment_terms nur bei Beleg."
)

SERVICES_SLA_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Leistungen & Service-Level:\n"
    "- Bei Leistungsübersichten/Matrix-Tabellen zuerst die aktive Tarif-/Vertragsspalte bestimmen und dann JEDE dort positiv "
    "markierte Leistungszeile übernehmen. Nicht nur 1–2 Beispiele auswählen.\n"
    "- services.included_services: alle belegten enthaltenen Leistungen in knapper Originalnähe sammeln, z. B. STK, Arbeitszeit, "
    "Fahrtkosten, Wartung inkl. Verschleißteile, Software-Updates, Gewährleistung, Reparaturen.\n"
    "- services.excluded_services nur bei explizitem Ausschluss.\n"
    "- bool-Flags (maintenance, inspection, repair, calibration, software_updates, remote_support, technical_support, "
    "spare_parts_included, consumables_included, emergency_service): true bei explizit enthaltener Leistung; false nur bei explizitem "
    "Ausschluss/Nein; sonst null. 'Kostenlose Reparaturen' => repair=true. 'Wartung inkl. Austausch von Verschleißteilen' => "
    "maintenance=true und spare_parts_included=true. 'Notwendige Software-Updates' => software_updates=true.\n"
    "- sla.response_time/resolution_time/service_hours/emergency_availability: TimeValue nur bei eindeutiger Zuordnung. "
    "Bei mehreren möglichen Reaktionszeiten ohne klar ausgewählte Option kein eindeutiges SLA erfinden.\n"
    "- sla.availability_24_7 ist DREIWERTIG: true nur bei explizitem 24/7/24x7/rund-um-die-Uhr-Beleg; false NUR wenn der Text "
    "explizit sagt, dass 24/7 NICHT verfügbar/ausgeschlossen ist. Wenn 24/7 gar nicht erwähnt wird oder der Auszug dazu schweigt, "
    "MUSS availability_24_7=null sein. Niemals false als Standardwert ausgeben.\n"
    "- Beispiel: Text enthält nur Reaktionszeit/Wartung, aber keine 24/7-Aussage => availability_24_7: null.\n"
    "Erfinde keine SLA-Werte; fehlend => null."
)


def group_order() -> list[str]:
    """Deterministische Reihenfolge der Gruppen für eine stabile Verarbeitung."""
    return ["identity_equipment", "dates_termination", "costs_payment", "services_sla"]
