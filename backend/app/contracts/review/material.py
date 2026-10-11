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
        "dates.start_date",
        "Vertragsbeginn (Datum)",
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
    (
        "services.coverage",
        "Service- / Wartungsabdeckung",
        lambda r: _scope_or_sla_present(r),
    ),
]

MATERIAL_FACT_KEYS = {key for key, _, _ in MATERIAL_FACTS}

# Fakten mit Material-Relevanz fuer Verfuegbarkeit/Compliance. Werden in der
# Pruef-Uebersicht besonders hervorgehoben und in der Vollstaendigkeits-Zaehlung
# als kritisch ausgewiesen, solange sie ungeprueft sind.
CRITICAL_FACTS = frozenset({
    "identity.contract_number",
    "identity.supplier",
    "dates.start_date",
    "dates.end_date",
    "dates.latest_cancellation",
    "termination.auto_renewal",
    "equipment.identity",
    "services.coverage",
})


def fact_is_critical(fact_key: str) -> bool:
    return fact_key in CRITICAL_FACTS


def _scope_or_sla_present(r: dict) -> Optional[str]:
    scope = r.get("scope") or {}
    if any(v is True for v in scope.values() if isinstance(v, bool)):
        return "Vorhanden"
    sla = r.get("sla") or {}
    if any(sla.get(k) for k in ("response_time", "resolution_time", "service_hours")):
        return "Vorhanden"
    return None


def fact_label(fact_key: str) -> str:
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