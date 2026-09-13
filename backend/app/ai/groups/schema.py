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
    def __init__(self, name: str, model: type, schema: dict, prompt: str, apply) -> None:
        self.name = name
        self.model = model
        self.schema = schema
        self.prompt = prompt
        self.apply = apply


def group_specs() -> dict[str, GroupSpec]:
    return {
        "identity_equipment": GroupSpec("identity_equipment", IdentityEquipmentGroup, pydantic_json_schema(IdentityEquipmentGroup), IDENTITY_EQUIPMENT_PROMPT, _apply_identity_equipment),
        "dates_termination": GroupSpec("dates_termination", DatesTerminationGroup, pydantic_json_schema(DatesTerminationGroup), DATES_TERMINATION_PROMPT, _apply_dates_termination),
        "costs_payment": GroupSpec("costs_payment", CostsPaymentGroup, pydantic_json_schema(CostsPaymentGroup), COSTS_PAYMENT_PROMPT, _apply_costs_payment),
        "services_sla": GroupSpec("services_sla", ServicesSlaGroup, pydantic_json_schema(ServicesSlaGroup), SERVICES_SLA_PROMPT, _apply_services_sla),
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
    "Die JSON-Ausgabe-Struktur wird technisch erzwungen – benutze sie GENAU so.\n"
    "ANTI-HALLUZINATION: Extrahiere NUR Fakten, die wörtlich oder eindeutig belegt sind. Fehlend oder nicht entscheidbar => null; fehlende Liste => []. "
    "Erfinde keine Daten, Parteien, Geräte, Kosten, Laufzeiten, Fristen, Vertragsnummern oder Belege.\n"
    "DREIWERTIGE BOOL-SEMANTIK: Optional[bool] ist true nur bei positivem Beleg, false nur bei expliziter Verneinung/Ausschluss, sonst null. Schweigen ist NIEMALS false.\n"
    "TABELLEN: Zeilen und Spaltenüberschriften gemeinsam lesen. OCR-Rauschen nie als neuen Fakt deuten.\n"
    "QUELLEN-NACHWEIS: Für wichtige Angaben evidence setzen; DOCX page=null und source_type paragraph|table mit 1-basiertem Index und kurzem wörtlichem source_text. PDF page=echt.\n"
    "Confidence konservativ; <0.50 zusätzlich requires_review=true. Keine Berechnungen."
)

IDENTITY_EQUIPMENT_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Identität & Geräte:\n"
    "- identity.contract_title: expliziten Vertragstitel/Betreff übernehmen, wenn er den Vertragsgegenstand bezeichnet.\n"
    "- identity.contract_number: NUR eine ausdrücklich als Vertragsnummer/Vertrags-Nr./Vertrag-Nr. oder eindeutig als Angebotsnummer bezeichnete Kennung. "
    "Eine Bestellung/Bestellnummer/Bestell-Nr./purchase order ist KEINE Vertragsnummer und MUSS contract_number=null bleiben, auch wenn sie zusammen mit einem unterschriebenen Servicevertrag genannt wird.\n"
    "- identity.contract_type: maintenance|service|lease|rental|other|unknown; Wartungsvertrag=>maintenance, Servicevertrag/Servicevereinbarung=>service.\n"
    "- identity.supplier = Dienstleister/Lieferant; identity.customer = Auftraggeber/Kunde; identity.contractor = ggf. weiterer Auftragnehmer.\n"
    "- PARTEINAMEN UND OCR: Bestimme zuerst die ROLLE aus dem Vertragsblock (z.B. Auftraggeber/Auftragnehmer). Bestimme danach den besten belegten NAMEN dieser selben Partei aus ALLEN Textstellen des Auszugs. "
    "Wenn der Vertragsblock einen erkennbar OCR-beschädigten Firmennamen enthält und derselbe Absender/Adresse/Domain-Kontext an anderer Stelle einen sauberen vollständigen juristischen Namen zeigt, bevorzuge den sauberen Namen. "
    "Kopiere nicht absichtlich OCR-Zeichenmüll als canonical customer/supplier, wenn eine eindeutig korrespondierende saubere Schreibweise im Dokument vorhanden ist.\n"
    "- Eine E-Mail-Signatur allein beweist nicht automatisch die Vertragsrolle. Sie darf aber die Schreibweise eines bereits über Auftraggeber/Adresse/Organisation eindeutig zugeordneten Namens korrigieren. "
    "Die Rollenbeziehung muss aus Vertrags-/Adresskontext stammen; die saubere Schreibweise darf aus korrespondierendem Begleittext stammen.\n"
    "- identity.department/location nur wenn belegbar.\n"
    "- equipment: tatsächlich abgedeckte Geräte; Formulierungen wie 'Servicevertrag ... für <Gerät>' sind Gerätebeleg. Serien-/Inventarnummer nur wörtlich belegt, sonst null.\n"
    "- Lege keine Geräte ohne Vertragsbezug an."
)

DATES_TERMINATION_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Laufzeit & Kündigung:\n"
    "- start_date/end_date nur echtes Kalenderdatum oder explizit ereignisbasiert.\n"
    "- duration/minimum_duration nur belegt.\n"
    "- cancellation_period/renewal_period nur belegt. automatic_renewal=true nur bei expliziter automatischer Verlängerung; false nur bei explizitem Ausschluss; sonst null.\n"
    "- Keine Kündigungsfristen oder Verlängerungen erfinden."
)

COSTS_PAYMENT_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Kosten & Zahlung:\n"
    "- Geldbeträge semantisch korrekt zuordnen (total/annual/monthly/quarterly/semi_annual/one_time/setup/maintenance/hourly). Keine Umrechnung oder Raten.\n"
    "- price_adjustment/indexation und Steuerbasis nur explizit. payment interval/terms/deadline nur belegt."
)

SERVICES_SLA_PROMPT = (
    _COMMON
    + "\n\nAUFGABE – Leistungen & Service-Level:\n"
    "- In Leistungs-/Matrix-Tabellen aktive Vertragsspalte bestimmen und JEDE dort positiv markierte Leistung übernehmen.\n"
    "- included_services vollständig und originalnah; excluded_services nur explizit.\n"
    "- bool-Flags true nur explizit enthalten, false nur explizit ausgeschlossen, sonst null. Kostenlose Reparaturen=>repair=true; Wartung inkl. Verschleißteile=>maintenance=true und spare_parts_included=true; Software-Updates=>software_updates=true.\n"
    "- SLA-Zeiten nur bei eindeutiger Zuordnung. availability_24_7=true nur explizit 24/7; false nur explizit nicht 24/7; sonst null."
)


def group_order() -> list[str]:
    return ["identity_equipment", "dates_termination", "costs_payment", "services_sla"]
