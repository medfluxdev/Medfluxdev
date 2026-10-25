"""Register der materialen Vertragsfakten für die faktgenaue menschliche Prüfung.

Für jeden materialen Fakt (`fact_key` im `field_ref`-Stil, z. B.
`costs.monthly_net`) existiert eine deutsche Bezeichnung (`label_de`) und ein
`reader`, der aus dem Contract-360-Read-Model-Dict bestimmt, ob der Fakt
vorliegt (present) und welchen angezeigten Wert er trägt.

Nur Fakten mit einem vorliegenden Wert zählen als „relevant" für die
Vollständigkeits-Angabe („X von Y relevanten Angaben geprüft"). Dekorative/
nicht-materiale Felder sind bewusst NICHT enthalten.
"""

from __future__ import annotations

from typing import Callable, Optional

from app.contracts.review.field_spec import FIELD_SPECS, TIER_ESSENTIAL

# reader(response: dict) -> Optional[str] (JSON-kompatibler Anzeige-/"System"-Wert)
Reader = Callable[[dict], object]


def _equipment_identity_value(r: dict) -> Optional[str]:
    # UAT Re-Test (Defect 3): die vertragsprimäre SYSTEM-Identitaet (z. B.
    # "Impella AIC System") aus der Betreff-Zeile zuerst; einzelne Komponenten
    # (z. B. "Impella Controller") verdrängen sie nie, sondern folgen dahinter.
    parts = []
    identity = r.get("identity") or {}
    system = identity.get("system_identity")
    if system and str(system).strip():
        parts.append(str(system).strip())
    for e in r.get("equipment") or []:
        value = " · ".join(
            x for x in (
                e.get("system_name"), e.get("device_name"), e.get("model")
            ) if x
        )
        if value and value not in parts:
            parts.append(value)
    return " | ".join(parts) or None


def _equipment_serial_value(r: dict) -> Optional[str]:
    parts = []
    for e in r.get("equipment") or []:
        value = " · ".join(
            x for x in (
                e.get("serial_number"), e.get("inventory_number")
            ) if x
        )
        if value and value not in parts:
            parts.append(value)
    return " | ".join(parts) or None


# Trenner fuer Listen-Angaben (weitere Leistungen) im Pruef-Wert.
LIST_SEPARATOR = "; "


def _joined(items) -> Optional[str]:
    values = [str(item).strip() for item in items or [] if str(item or "").strip()]
    return LIST_SEPARATOR.join(values) or None


SCOPE_VALUE_INCLUDED = "Inklusive"
SCOPE_VALUE_EXCLUDED = "Exklusive"
SCOPE_VALUE_MENTIONED = "Erwähnt – bitte festlegen"


def _scope_reader(key: str) -> Reader:
    """Leistung laut Dokument; nicht belegte Leistungen gelten als nicht vorliegend."""

    def read(r: dict) -> Optional[str]:
        scope = r.get("scope") or {}
        item = (scope.get("scope_status") or {}).get(key) or {}
        status = item.get("status")
        if status is None:
            legacy = scope.get(key)
            status = "included" if legacy is True else "excluded" if legacy is False else None
        # Ohne eindeutigen Beleg im Text: das Ja/Nein der KI als Vorschlag (bleibt zu pruefen).
        if status not in ("included", "excluded") and item.get("ai_suggestion") is not None:
            status = "included" if item["ai_suggestion"] else "excluded"
        return {
            "included": SCOPE_VALUE_INCLUDED,
            "excluded": SCOPE_VALUE_EXCLUDED,
            "mentioned": SCOPE_VALUE_MENTIONED,
        }.get(status or "")

    return read


# Leistungen des Leistungsumfangs (Schluessel wie `scope.scope_status` im Lesemodell).
SCOPE_FACTS: tuple[tuple[str, str], ...] = (
    ("maintenance", "Wartung"),
    ("inspection", "Inspektion"),
    ("repair", "Reparatur"),
    ("calibration", "Kalibrierung"),
    ("software_updates", "Software-Updates"),
    ("remote_support", "Remote-Support"),
    ("technical_support", "Technischer Support"),
    ("spare_parts_included", "Ersatzteile"),
    ("consumables_included", "Verbrauchsmaterial"),
    ("emergency_service", "Notdienst"),
)


MATERIAL_FACTS: list[tuple[str, str, Reader]] = [
    (
        "identity.contract_number",
        "Vertragsnummer",
        lambda r: (r.get("identity") or {}).get("contract_number")
        or r.get("contract_number"),
    ),
    (
        "identity.supplier",
        "Vertragspartner / Lieferant",
        lambda r: (r.get("identity") or {}).get("supplier") or r.get("supplier"),
    ),
    (
        "identity.contract_title",
        "Vertragsgegenstand / Titel",
        lambda r: (r.get("extracted_terms") or {}).get("identity.contract_title"),
    ),
    (
        "identity.contract_type",
        "Vertragsart",
        lambda r: (r.get("extracted_terms") or {}).get("identity.contract_type"),
    ),
    (
        "dates.start_date",
        "Vertragsbeginn",
        lambda r: (r.get("dates") or {}).get("start_date")
        or (r.get("dates") or {}).get("overridden_start_date"),
    ),
    (
        "dates.event_start",
        "Ereignisbasierter Vertragsbeginn",
        lambda r: (r.get("dates") or {}).get("start_condition"),
    ),
    (
        "payment.payment_start",
        "Zahlungsbeginn",
        lambda r: (r.get("dates") or {}).get("payment_start_rule"),
    ),
    (
        "dates.minimum_duration",
        "Mindestvertragslaufzeit",
        lambda r: (r.get("dates") or {}).get("minimum_duration_months"),
    ),
    (
        "dates.duration",
        "Laufzeit",
        lambda r: (r.get("extracted_terms") or {}).get("dates.duration"),
    ),
    (
        "termination.cancellation_period",
        "Kündigungsfrist",
        lambda r: (r.get("extracted_terms") or {}).get("termination.cancellation_period"),
    ),
    (
        "termination.cancellation_condition",
        "Kündigungstermin",
        lambda r: (r.get("extracted_terms") or {}).get("termination.cancellation_condition"),
    ),
    (
        "termination.renewal_period",
        "Verlängerungszeitraum",
        lambda r: (r.get("extracted_terms") or {}).get("termination.renewal_period"),
    ),
    (
        "dates.end_date",
        "Vertragsende",
        lambda r: (r.get("dates") or {}).get("calculated_end_date")
        or (r.get("dates") or {}).get("documented_end_date"),
    ),
    (
        "dates.latest_cancellation",
        "Kündigungsfrist (letztes Kündigungsdatum)",
        lambda r: (r.get("dates") or {}).get("latest_cancellation_date"),
    ),
    (
        "termination.auto_renewal",
        "Automatische Verlängerung",
        lambda r: (lambda v: "Ja" if v is True else ("Nein" if v is False else None))(
            (r.get("dates") or {}).get("automatic_renewal")
        ),
    ),
    (
        "costs.monthly_recurring",
        "Wiederkehrende Kosten (monatlich)",
        lambda r: ((r.get("costs") or {}).get("monthly_recurring") or {}).get("amount"),
    ),
    (
        "costs.monthly_net",
        "Monatlicher Nettopreis",
        lambda r: ((r.get("costs") or {}).get("tax_breakdown") or {}).get("monthly_net")
        or ((r.get("costs") or {}).get("monthly_recurring") or {}).get("amount"),
    ),
    (
        "costs.currency",
        "Währung",
        lambda r: ((r.get("costs") or {}).get("monthly_recurring") or {}).get("currency")
        or ((r.get("costs") or {}).get("annual_recurring") or {}).get("currency"),
    ),
    (
        "payment.billing_interval",
        "Zahlungsrhythmus",
        lambda r: (r.get("extracted_terms") or {}).get("payment.billing_interval"),
    ),
    (
        "costs.vat_rate",
        "MwSt.-Satz",
        lambda r: ((r.get("costs") or {}).get("tax_breakdown") or {}).get("rate_percent"),
    ),
    (
        "costs.vat_amount",
        "MwSt.-Betrag (monatlich)",
        lambda r: ((r.get("costs") or {}).get("tax_breakdown") or {}).get("monthly_tax"),
    ),
    (
        "costs.monthly_gross",
        "Monatlicher Bruttopreis",
        lambda r: ((r.get("costs") or {}).get("tax_breakdown") or {}).get("monthly_gross"),
    ),
    (
        "costs.annual",
        "Jährliche Gesamtkosten",
        lambda r: ((r.get("costs") or {}).get("annual_recurring") or {}).get("amount"),
    ),
    (
        "costs.price_fixed",
        "Preisfixierung",
        lambda r: (
            next(
                (
                    p.get("text") or p.get("label")
                    for p in (r.get("costs") or {}).get("price_development") or []
                    if p.get("key") == "price_fixed"
                ),
                None,
            )
        ),
    ),
    (
        "costs.price_indexation",
        "Preisentwicklung (Indexierung/Anpassung)",
        lambda r: (
            next(
                (
                    p.get("text") or p.get("label")
                    for p in (r.get("costs") or {}).get("price_development") or []
                    if p.get("key") != "price_fixed"
                ),
                None,
            )
        ),
    ),
    (
        "equipment.identity",
        "Geräte-Identität",
        _equipment_identity_value,
    ),
    (
        "equipment.serial",
        "Serien- / Inventarnummer",
        _equipment_serial_value,
    ),
    *[
        (f"scope.{key}", f"Leistungsumfang: {label}", _scope_reader(key))
        for key, label in SCOPE_FACTS
    ],
    (
        "scope.other_included",
        "Leistungsumfang: weitere inklusive Leistungen",
        lambda r: _joined((r.get("scope") or {}).get("included_services")),
    ),
    (
        "scope.other_excluded",
        "Leistungsumfang: exklusive Leistungen",
        lambda r: _joined((r.get("scope") or {}).get("excluded_services")),
    ),
    (
        "sla.response_time",
        "Reaktionszeit (SLA)",
        lambda r: (r.get("sla") or {}).get("response_time"),
    ),
    (
        "sla.resolution_time",
        "Lösungszeit (SLA)",
        lambda r: (r.get("sla") or {}).get("resolution_time"),
    ),
    (
        "sla.service_hours",
        "Servicezeiten (SLA)",
        lambda r: (r.get("sla") or {}).get("service_hours"),
    ),
    (
        "sla.emergency_availability",
        "Notfallverfügbarkeit (SLA)",
        lambda r: _emergency_value(r),
    ),
    (
        "sla.sla_notes",
        "Weitere SLA-Angaben",
        lambda r: (r.get("sla") or {}).get("sla_notes"),
    ),
]

MATERIAL_FACT_KEYS = {key for key, _, _ in MATERIAL_FACTS}

# Wesentliche Angaben (Feldregister `field_spec`): ohne sie ist der Vertrag nicht belastbar erfasst. Sie werden in der
# Pruef-Uebersicht hervorgehoben und muessen von einer Person entschieden werden; berechnete Werte zaehlen nie dazu.
CRITICAL_FACTS = frozenset(
    key for key, spec in FIELD_SPECS.items() if spec.tier == TIER_ESSENTIAL and not spec.calculated
)


def fact_is_critical(fact_key: str) -> bool:
    return fact_key in CRITICAL_FACTS


def _emergency_value(r: dict) -> Optional[str]:
    sla = r.get("sla") or {}
    if sla.get("emergency_availability"):
        return sla["emergency_availability"]
    if sla.get("availability_24_7") is True:
        return "24/7 erreichbar"
    if sla.get("availability_24_7") is False:
        return "Nicht 24/7"
    return None


# Pruef-Angaben aus Nachweisen ohne feste Angabe: „evidence.<Quellfeld>“.
EVIDENCE_FACT_PREFIX = "evidence."

_EVIDENCE_LABELS = {
    "identity.system_identity": "System / Gerät (laut Betreff)",
    "identity_equipment": "Gerät",
    "equipment": "Gerät",
    "payment.payment_start": "Zahlungsbeginn",
    "costs.scheduled_prices": "Preisstaffel",
    "costs.tax_table": "Steuertabelle",
    "scope.included_services": "Leistungsumfang (Inklusiv-Liste)",
    "scope.excluded_services": "Leistungsumfang (Ausschlüsse)",
}
_GROUP_LABELS = {
    "identity": "Vertragsangaben",
    "dates": "Laufzeit",
    "termination": "Kündigung",
    "costs": "Kosten",
    "payment": "Zahlung",
    "services": "Leistungen",
    "scope": "Leistungsumfang",
    "sla": "SLA",
    "equipment": "Gerät",
}


def evidence_base(field_ref: str) -> str:
    """Quellfeld eines Belegs ohne Beleg-Zaehler (`dates.duration.evidence.0` -> `dates.duration`)."""
    return str(field_ref).split(".evidence", 1)[0] or str(field_ref)


def evidence_fact_label(base: str) -> str:
    from app.reextract.facts import LABELS

    parts = base.split(".")
    if len(parts) == 3 and parts[1] == "cost_line" and parts[2].isdigit():
        return f"Kostenposition {int(parts[2]) + 1}"
    for key in (base, ".".join(parts[:2]), parts[0]):
        if key in LABELS:
            return LABELS[key]
        if key in _EVIDENCE_LABELS:
            return _EVIDENCE_LABELS[key]
    group = _GROUP_LABELS.get(parts[0], "Angabe")
    return f"{group} (weiterer Nachweis)" if len(parts) == 1 else f"{group}: {' '.join(parts[1:]).replace('_', ' ')}"


def fact_label(fact_key: str) -> str:
    if fact_key.startswith(EVIDENCE_FACT_PREFIX):
        return f"Nachweis: {evidence_fact_label(fact_key[len(EVIDENCE_FACT_PREFIX):])}"
    for key, label, _ in MATERIAL_FACTS:
        if key == fact_key:
            return label
    return fact_key


def material_report(response: dict) -> dict[str, dict]:
    """{fact_key: {"present": bool, "value": object, "critical": bool}}."""
    out: dict[str, dict] = {}
    for key, _label, reader in MATERIAL_FACTS:
        try:
            value = reader(response)
        except Exception:
            value = None
        out[key] = {
            "present": value is not None and value is not False,
            "value": value,
            "critical": key in CRITICAL_FACTS,
        }
    return out