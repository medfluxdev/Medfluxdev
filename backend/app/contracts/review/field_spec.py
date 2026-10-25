"""Offizielle Felder der Vertragsakte: Karte, Priorität und Art (gelesen oder berechnet).

Eine Quelle für Extraktion, Prüfung und Anzeige: die Prüf-Angaben (`material.MATERIAL_FACTS`) sind die
offiziellen Felder. Hier steht, was sie *bedeuten* – nicht ihr Reiter allein:

- `essential`  : ohne diese Angabe ist der Vertrag nicht belastbar erfasst (Partner, Gegenstand, Laufzeit,
                 Kündigung, Verlängerung, Preis, Währung, Steuer, Zahlungsrhythmus, Preisanpassung).
- `important`  : nächste Stufe (Leistungen, Reaktionszeiten, Servicezeiten …).
- `optional`   : nur bei Bedarf (Kontaktdaten, Hinweise).

Die Priorität folgt der Bedeutung und dem Vertragstyp (z. B. SLA-Zeiten sind bei Wartung von Geräten
wesentlich), nicht dem Reiter. Berechnete Werte (`calculated`) werden nie einzeln bestätigt: sie gelten, wenn
ihre Eingaben geklärt sind. Reiner Code ohne DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

TIER_ESSENTIAL = "essential"
TIER_IMPORTANT = "important"
TIER_OPTIONAL = "optional"
TIERS = (TIER_ESSENTIAL, TIER_IMPORTANT, TIER_OPTIONAL)
TIER_LABELS = {
    TIER_ESSENTIAL: "Wesentliche Angaben",
    TIER_IMPORTANT: "Weitere wichtige Angaben",
    TIER_OPTIONAL: "Optionale Angaben",
}

# Karten (Schlüssel wie die Bereiche der erneuten Erfassung und `EVIDENCE_SECTIONS` im Frontend).
CARD_LABELS = {
    "partner": "Vertragsdaten",
    "term": "Fristen & Aufgaben",
    "cost": "Finanzen",
    "services": "Leistungen & SLA",
    "device": "Geräte",
}


@dataclass(frozen=True)
class FieldSpec:
    key: str
    card: str
    tier: str
    #: berechnet (nicht gelesen): wird nie einzeln bestätigt
    calculated: bool = False
    #: Angaben, aus denen ein berechneter Wert entsteht
    inputs: tuple[str, ...] = ()
    #: Bedeutung in einem Satz (Warum ist das wichtig?) – für Hinweise bei Lücken und Widersprüchen
    why: str = ""


def _spec(key: str, card: str, tier: str, why: str = "", *, calculated: bool = False, inputs: tuple[str, ...] = ()) -> tuple[str, FieldSpec]:
    return key, FieldSpec(key, card, tier, calculated, inputs, why)


E, I, O = TIER_ESSENTIAL, TIER_IMPORTANT, TIER_OPTIONAL

FIELD_SPECS: dict[str, FieldSpec] = dict([
    # Vertragsdaten
    _spec("identity.supplier", "partner", E, "Ohne Vertragspartner ist der Vertrag nicht zuzuordnen."),
    _spec("identity.contract_title", "partner", E, "Der Vertragsgegenstand benennt, worum es im Vertrag geht."),
    _spec("identity.contract_type", "partner", E, "Die Vertragsart bestimmt Fristen, Abschnitte und Regeln."),
    _spec("identity.contract_number", "partner", I),
    # Fristen
    _spec("dates.start_date", "term", E, "Der Beginn legt die Laufzeit fest."),
    _spec("dates.end_date", "term", E, "Das Vertragsende bestimmt Kündigung und Verlängerung."),
    _spec("termination.cancellation_period", "term", E, "Ohne Kündigungsfrist wird der Kündigungstermin nicht überwacht."),
    _spec("termination.auto_renewal", "term", E, "Eine automatische Verlängerung verlängert die Bindung, wenn nicht rechtzeitig gekündigt wird."),
    _spec("termination.renewal_period", "term", E, "Der Verlängerungszeitraum bestimmt, wie lange der Vertrag sich verlängert."),
    _spec("termination.cancellation_condition", "term", I),
    _spec("dates.duration", "term", E, "Die Laufzeit bestimmt, wie lange der Vertrag bindet."),
    _spec("dates.minimum_duration", "term", I),
    _spec("dates.event_start", "term", I),
    _spec("payment.payment_start", "term", I),
    _spec("dates.latest_cancellation", "term", I, calculated=True,
          inputs=("dates.end_date", "termination.cancellation_period", "termination.cancellation_condition", "termination.auto_renewal")),
    # Finanzen
    _spec("costs.monthly_recurring", "cost", E, "Der Betrag ist die Grundlage aller Kostenauswertungen."),
    _spec("costs.currency", "cost", E, "Ohne Währung lassen sich Beträge nicht zusammenrechnen."),
    _spec("costs.vat_rate", "cost", E, "Der Steuersatz entscheidet zwischen Netto- und Bruttobetrag."),
    _spec("payment.billing_interval", "cost", E, "Der Zahlungsrhythmus bestimmt, wann Zahlungen fällig werden."),
    _spec("costs.price_indexation", "cost", E, "Preisanpassungen verändern die Kosten während der Laufzeit."),
    _spec("costs.price_fixed", "cost", I),
    _spec("costs.monthly_net", "cost", I),
    _spec("costs.monthly_gross", "cost", I, calculated=True, inputs=("costs.monthly_net", "costs.vat_rate")),
    _spec("costs.vat_amount", "cost", I, calculated=True, inputs=("costs.monthly_net", "costs.vat_rate")),
    _spec("costs.annual", "cost", I, calculated=True, inputs=("costs.monthly_recurring",)),
    # Leistungen & SLA
    *[_spec(f"scope.{k}", "services", I) for k in (
        "maintenance", "inspection", "repair", "calibration", "software_updates", "remote_support",
        "technical_support", "spare_parts_included", "consumables_included", "emergency_service")],
    _spec("scope.other_included", "services", I),
    _spec("scope.other_excluded", "services", I),
    _spec("sla.response_time", "services", I, "Die Reaktionszeit bestimmt, wie schnell der Dienstleister handeln muss."),
    _spec("sla.resolution_time", "services", I, "Die Behebungszeit bestimmt, wie lange ein Ausfall dauern darf."),
    _spec("sla.service_hours", "services", I),
    _spec("sla.emergency_availability", "services", I),
    _spec("sla.sla_notes", "services", O),
    # Geräte
    _spec("equipment.identity", "device", I),
    _spec("equipment.serial", "device", O),
])

# Bei Verträgen mit SLA-Abschnitt (Wartung/Service von Geräten) sind diese Zeiten wesentlich.
_SLA_ESSENTIAL = ("sla.response_time", "sla.resolution_time")
_SLA_WHY = "Bei Wartung von Geräten bestimmen diese Zeiten die Verfügbarkeit."


def spec_for(fact_key: str) -> Optional[FieldSpec]:
    return FIELD_SPECS.get(fact_key)


def tier_for(fact_key: str, sections: Optional[dict] = None) -> str:
    """Priorität eines Felds – mit sinnvollem Standard je Vertragstyp (`sections` aus register/sections.py)."""
    spec = FIELD_SPECS.get(fact_key)
    if spec is None:
        return TIER_OPTIONAL
    if fact_key in _SLA_ESSENTIAL and sections and sections.get("sla") and sections.get("maintenance"):
        return TIER_ESSENTIAL
    return spec.tier


def why_for(fact_key: str, sections: Optional[dict] = None) -> str:
    if fact_key in _SLA_ESSENTIAL and sections and sections.get("sla") and sections.get("maintenance"):
        return _SLA_WHY
    spec = FIELD_SPECS.get(fact_key)
    return spec.why if spec else ""


def is_calculated(fact_key: str) -> bool:
    spec = FIELD_SPECS.get(fact_key)
    return bool(spec and spec.calculated)


def inputs_of(fact_key: str) -> tuple[str, ...]:
    spec = FIELD_SPECS.get(fact_key)
    return spec.inputs if spec else ()


def card_of(fact_key: str) -> str:
    spec = FIELD_SPECS.get(fact_key)
    return spec.card if spec else "partner"


# Nachweise ohne feste Prüf-Angabe, die ein offizielles Feld belegen (Quellfeld -> Prüf-Angabe).
EVIDENCE_TO_FIELD: dict[str, str] = {
    "identity.contract_title": "identity.contract_title",
    "identity.contract_type": "identity.contract_type",
    "payment.billing_interval": "payment.billing_interval",
}

# Weitere Funde, die zu Stammdaten des Vertragspartners gehören (eigener Weg: Vorschläge am Partner).
CONTACT_FINDINGS = frozenset({
    "identity.service_email", "identity.service_phone", "identity.contact_person", "identity.customer_number",
})
