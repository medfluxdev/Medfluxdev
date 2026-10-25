"""Vergleich und Zusammenfuehrung von Extraktionen fuer die erneute Erfassung.

Reiner Code ohne DB: `compare` stellt die akzeptierte Extraktion und einen
Kandidaten Fakt fuer Fakt gegenueber, `merge` uebernimmt nur die ausgewaehlten
Fakten (samt Nachweisen) in eine Kopie der akzeptierten Extraktion. Nicht
ausgewaehlte und nicht erneut gefundene Angaben bleiben unveraendert – eine
erneute Erfassung kann den Vertrag nie verschlechtern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Iterable, Optional

from pydantic import BaseModel

from app.contracts.review.material import SCOPE_FACTS
from app.models.contract import Contract as ExtractedContract

GROUPS = ("identity", "dates", "termination", "costs", "payment", "services", "sla")

# Bereiche der erneuten Erfassung, benannt nach den Reitern der Vertragsakte, in denen die Angaben stehen
# (Schluessel wie in "Nachweise pruefen", frontend lib/evidence.ts; Namen wie ANALYSIS_SECTION_LABEL im Frontend).
SECTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "partner": ("Vertragsdaten", ("identity",)),
    "term": ("Fristen & Aufgaben", ("dates", "termination")),
    "cost": ("Finanzen", ("costs", "payment")),
    "services": ("Leistungen & SLA", ("services", "sla")),
    "device": ("Verknüpfungen (Geräte)", ("equipment",)),
}
_SKIP = {"evidence", "default_currency"}
# Enum-Werte, die "nichts gefunden" bedeuten.
_EMPTY_ENUMS = {"unknown", "other"}

LABELS: dict[str, str] = {
    "identity.contract_title": "Vertragstitel",
    "identity.contract_number": "Vertragsnummer",
    "identity.contract_type": "Vertragsart",
    "identity.supplier": "Vertragspartner / Lieferant",
    "identity.contractor": "Auftragnehmer",
    "identity.customer": "Auftraggeber",
    "identity.contact_person": "Ansprechpartner",
    "identity.service_email": "Service-E-Mail",
    "identity.service_phone": "Service-Telefon",
    "identity.customer_number": "Kundennummer",
    "identity.department": "Abteilung (laut Dokument)",
    "identity.location": "Standort (laut Dokument)",
    "equipment": "Geräte",
    "dates.start_date": "Vertragsbeginn",
    "dates.end_date": "Vertragsende",
    "dates.duration": "Laufzeit",
    "dates.minimum_duration": "Mindestlaufzeit",
    "dates.start_condition": "Bedingung für den Beginn",
    "dates.end_condition": "Bedingung für das Ende",
    "termination.cancellation_period": "Kündigungsfrist",
    "termination.cancellation_condition": "Kündigungstermin",
    "termination.cancellation_to_contract_end": "Kündigung zum Vertragsende",
    "termination.automatic_renewal": "Automatische Verlängerung",
    "termination.renewal_period": "Verlängerungszeitraum",
    "termination.extraordinary_termination": "Außerordentliche Kündigung",
    "costs.total_contract_value": "Gesamtvertragswert",
    "costs.annual_cost": "Jährliche Kosten",
    "costs.monthly_cost": "Monatliche Kosten",
    "costs.quarterly_cost": "Quartalskosten",
    "costs.semi_annual_cost": "Halbjährliche Kosten",
    "costs.one_time_cost": "Einmalkosten",
    "costs.setup_installation_cost": "Installationskosten",
    "costs.maintenance_fee": "Wartungspauschale",
    "costs.hourly_rate": "Stundensatz",
    "costs.travel_cost": "Reisekosten",
    "costs.material_cost": "Materialkosten",
    "costs.spare_parts_cost": "Ersatzteilkosten",
    "costs.additional_costs": "Weitere Kosten",
    "costs.scheduled_prices": "Preisstaffel",
    "costs.variable_charges": "Variable Entgelte",
    "costs.discounts": "Rabatte",
    "costs.price_adjustment_clause": "Preisanpassungsklausel",
    "costs.price_indexation": "Preisindexierung",
    "costs.tax_basis": "Netto oder brutto",
    "costs.tax_rate_percent": "MwSt.-Satz",
    "payment.payment_terms": "Zahlungsbedingungen",
    "payment.payment_deadline_days": "Zahlungsziel",
    "payment.billing_interval": "Abrechnungsintervall",
    "payment.advance_payment": "Vorauszahlung",
    "payment.payment_notes": "Hinweise zur Zahlung",
    "services.included_services": "Enthaltene Leistungen",
    "services.excluded_services": "Ausgeschlossene Leistungen",
    "services.maintenance": "Wartung enthalten",
    "services.inspection": "Inspektion enthalten",
    "services.repair": "Reparatur enthalten",
    "services.calibration": "Kalibrierung enthalten",
    "services.software_updates": "Software-Updates enthalten",
    "services.remote_support": "Fernwartung enthalten",
    "services.technical_support": "Technischer Support enthalten",
    "services.spare_parts_included": "Ersatzteile enthalten",
    "services.consumables_included": "Verbrauchsmaterial enthalten",
    "services.emergency_service": "Notdienst enthalten",
    "sla.response_time": "Reaktionszeit",
    "sla.resolution_time": "Behebungszeit",
    "sla.service_hours": "Servicezeiten",
    "sla.emergency_availability": "Notfallerreichbarkeit",
    "sla.sla_notes": "Hinweise zum Service-Level",
}

# Welche Felder der Vertragsdaten aus einem Fakt abgeleitet werden (register/ai_mapping.py).
REGISTER_KEYS: dict[str, tuple[str, ...]] = {
    "identity.contract_title": ("contract_title",),
    "dates.start_date": ("term_start_date",),
    "dates.end_date": ("term_fixed_end_date", "term_model"),
    "dates.duration": ("initial_term_value", "initial_term_unit", "term_model"),
    "dates.minimum_duration": ("minimum_term_value", "minimum_term_unit", "term_model"),
    "termination.cancellation_period": ("notice_period_value", "notice_period_unit", "term_model"),
    "termination.cancellation_condition": ("notice_to", "term_model"),
    "termination.cancellation_to_contract_end": ("notice_to", "term_model"),
    "termination.automatic_renewal": ("term_model",),
    "termination.renewal_period": ("renewal_period_value", "renewal_period_unit"),
    "costs.price_adjustment_clause": ("price_adjustment_kind", "price_adjustment_percent"),
    "costs.price_indexation": ("price_adjustment_kind", "price_adjustment_index_name"),
}

# Angaben zu Laufzeit/Kuendigung, die das Lesemodell fuer die Pruefung als Text liefert.
REVIEW_TERM_FACTS = (
    "dates.duration", "termination.cancellation_period", "termination.cancellation_condition", "termination.renewal_period",
)

# Weitere Angaben, die das Lesemodell fuer die Pruefung als Text liefert (Vertragsgegenstand, -art, Zahlungsrhythmus).
REVIEW_EXTRA_FACTS = ("identity.contract_title", "identity.contract_type", "payment.billing_interval")

SCOPE_REVIEW_FACTS = tuple(f"scope.{key}" for key, _ in SCOPE_FACTS)

# Uebernommener Fakt -> Pruef-Angaben, die dadurch einen neuen Wert bekommen (auch berechnete).
REVIEW_FACTS: dict[str, tuple[str, ...]] = {
    "identity.contract_number": ("identity.contract_number",),
    "identity.supplier": ("identity.supplier",),
    "identity.contract_title": ("identity.contract_title",),
    "identity.contract_type": ("identity.contract_type",),
    "payment.billing_interval": ("payment.billing_interval",),
    "dates.start_date": ("dates.start_date", "dates.end_date", "dates.latest_cancellation"),
    "dates.start_condition": ("dates.event_start",),
    "dates.end_date": ("dates.end_date", "dates.latest_cancellation"),
    "dates.duration": ("dates.duration", "dates.end_date", "dates.latest_cancellation"),
    "dates.minimum_duration": ("dates.minimum_duration", "dates.latest_cancellation"),
    "termination.cancellation_period": ("termination.cancellation_period", "dates.latest_cancellation"),
    "termination.cancellation_condition": ("termination.cancellation_condition", "dates.latest_cancellation"),
    "termination.cancellation_to_contract_end": ("termination.cancellation_condition", "dates.latest_cancellation"),
    "termination.automatic_renewal": ("termination.auto_renewal", "dates.latest_cancellation"),
    "termination.renewal_period": ("termination.renewal_period",),
    "costs.monthly_cost": ("costs.monthly_recurring", "costs.monthly_net", "costs.monthly_gross", "costs.annual", "costs.currency"),
    "costs.annual_cost": ("costs.annual",),
    "costs.tax_rate_percent": ("costs.vat_rate", "costs.vat_amount", "costs.monthly_gross"),
    "costs.price_indexation": ("costs.price_indexation",),
    "costs.price_adjustment_clause": ("costs.price_fixed", "costs.price_indexation"),
    "equipment": ("equipment.identity", "equipment.serial"),
    "services.included_services": SCOPE_REVIEW_FACTS + ("scope.other_included",),
    "services.excluded_services": SCOPE_REVIEW_FACTS + ("scope.other_excluded",),
    **{f"services.{key}": (f"scope.{key}",) for key, _ in SCOPE_FACTS},
    "sla.response_time": ("sla.response_time",),
    "sla.resolution_time": ("sla.resolution_time",),
    "sla.service_hours": ("sla.service_hours",),
    "sla.emergency_availability": ("sla.emergency_availability",),
    "sla.availability_24_7": ("sla.emergency_availability",),
    "sla.sla_notes": ("sla.sla_notes",),
}

# Pruef-Angabe -> Vertragsdaten-Feld (Basisname), das eine Korrektur in der Pruefung mit aendert.
REVIEW_TO_REGISTER: dict[str, str] = {
    "dates.start_date": "term_start_date",
    "dates.end_date": "term_fixed_end_date",
    "dates.duration": "initial_term",
    "dates.minimum_duration": "minimum_term",
    "termination.cancellation_period": "notice_period",
    "termination.cancellation_condition": "notice_to",
    "termination.renewal_period": "renewal_period",
}


def review_facts_for(keys: Iterable[str]) -> list[str]:
    out: list[str] = []
    for key in keys:
        for fact in REVIEW_FACTS.get(key, ()):
            if fact not in out:
                out.append(fact)
    return out


# Umgekehrt: Vertragsdaten-Feld -> Fakten, die es fuellen (fuer "Nur fehlende Angaben").
def facts_for_register_key(key: str) -> list[str]:
    base = key.removesuffix("_value").removesuffix("_unit")
    return [path for path, keys in REGISTER_KEYS.items() if key in keys or any(k == base or k.startswith(base + "_") for k in keys)]


def register_search_map() -> dict[str, list[dict]]:
    """Vertragsdaten-Feld -> Fakten zum gezielten Suchen ("Im Dokument suchen")."""
    keys = {key for group in REGISTER_KEYS.values() for key in group}
    out: dict[str, list[dict]] = {}
    for key in sorted(keys):
        paths = facts_for_register_key(key)
        if paths:
            out[key] = [{"key": path, "label": LABELS.get(path, path)} for path in paths]
    return out


_UNITS = {"days": ("Tag", "Tage"), "weeks": ("Woche", "Wochen"), "months": ("Monat", "Monate"),
          "years": ("Jahr", "Jahre"), "hours": ("Stunde", "Stunden")}
_PERIODS = {"annual": "jährlich", "yearly": "jährlich", "monthly": "monatlich", "quarterly": "vierteljährlich",
            "semi_annual": "halbjährlich", "once": "einmalig", "one_time": "einmalig"}
_ENUM_DE = {"monthly": "monatlich", "quarterly": "vierteljährlich", "semi_annual": "halbjährlich",
            "annual": "jährlich", "once": "einmalig", "maintenance": "Wartung", "service": "Service",
            "lease": "Leasing", "rental": "Miete", "net": "netto", "gross": "brutto"}


def fact_paths(model: ExtractedContract) -> list[str]:
    out: list[str] = []
    for group in GROUPS:
        holder = getattr(model, group)
        for name in type(holder).model_fields:
            if name not in _SKIP:
                out.append(f"{group}.{name}")
        if group == "identity":
            out.append("equipment")
    return out


def section_of(path: str) -> str:
    group = "equipment" if path == "equipment" else path.split(".", 1)[0]
    return next((key for key, (_label, groups) in SECTIONS.items() if group in groups), "partner")


def all_paths() -> list[str]:
    return fact_paths(ExtractedContract())


def paths_for_sections(sections: Iterable[str]) -> list[str]:
    wanted = set(sections)
    return [path for path in all_paths() if section_of(path) in wanted]


def empty_paths(model: Optional[ExtractedContract]) -> list[str]:
    """Angaben ohne Wert (Modus "Ergaenzen"); ohne fruehere Analyse alle."""
    if model is None:
        return all_paths()
    return [path for path in fact_paths(model) if is_empty(get_fact(model, path))]


def get_fact(model: ExtractedContract, path: str) -> Any:
    if path == "equipment":
        return model.equipment
    group, name = path.split(".", 1)
    return getattr(getattr(model, group), name)


def _set_fact(model: ExtractedContract, path: str, value: Any) -> None:
    if path == "equipment":
        model.equipment = value
        return
    group, name = path.split(".", 1)
    setattr(getattr(model, group), name, value)


def dump_fact(value: Any) -> Any:
    """JSON-Schnappschuss eines Fakts (fuer Vorschlag und Zuruecknahme)."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [dump_fact(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    return value


def same_snapshot(value: Any, snapshot: Any) -> bool:
    """Steht im Modell noch der Wert eines Schnappschusses? (ohne Nachweis-/Pruefmarker)"""
    return _normal(value) == _normal(snapshot)


def with_fact(model: ExtractedContract, path: str, snapshot: Any) -> ExtractedContract:
    """Kopie des Modells mit dem Fakt aus einem JSON-Schnappschuss (None = leerer Standardwert)."""
    data = model.model_dump(mode="json")
    if snapshot is None:
        snapshot = dump_fact(get_fact(ExtractedContract(), path))
    if path == "equipment":
        data["equipment"] = snapshot
    else:
        group, name = path.split(".", 1)
        data[group][name] = snapshot
    return ExtractedContract.model_validate(data)


def _belongs(row: dict, key: str) -> bool:
    name = str(row.get("field") or "")
    return name == key or name.startswith(key + ".") or (key == "equipment" and name.startswith("identity_equipment"))


def evidence_rows(model: Optional[ExtractedContract], path: str) -> list[dict]:
    """Rohe Harness-Nachweise eines Fakts (fuer den Schnappschuss)."""
    if model is None:
        return []
    return [dict(row) for row in (model.analysis.harness or {}).get("evidence") or [] if _belongs(row, path)]


def with_evidence(model: ExtractedContract, path: str, rows: list[dict]) -> ExtractedContract:
    """Nachweise eines Fakts ersetzen (Zuruecknahme)."""
    harness = dict(model.analysis.harness or {})
    harness["evidence"] = [row for row in harness.get("evidence") or [] if not _belongs(row, path)] + [dict(row) for row in rows]
    copy = model.model_copy(deep=True)
    copy.analysis.harness = harness
    return copy


def evidence_detail(rows: list[dict]) -> list[dict]:
    """Anzeige der Nachweise: Seite, Zitat, Sicherheit, Box."""
    out = []
    for row in rows:
        source = row.get("source") or {}
        if source.get("source_text") or source.get("page"):
            out.append({"page": source.get("page"), "quote": source.get("source_text"),
                        "confidence": source.get("confidence"), "bbox": source.get("bounding_box")})
    return out[:3]


def confidence_of(rows: list[dict]) -> Optional[float]:
    values = [float(row["confidence"]) for row in evidence_detail(rows) if row.get("confidence") is not None]
    return max(values) if values else None


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, Enum):
        return str(value.value) in _EMPTY_ENUMS
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    if isinstance(value, BaseModel):
        data = _normal(value)
        if not isinstance(data, dict):
            return data in (None, "", [], {})
        keys = ("date", "condition", "value", "amount", "original_text")
        present = [data.get(key) for key in keys if key in data]
        return not present or all(item in (None, "") for item in present)
    return False


def _normal(value: Any) -> Any:
    """JSON-Form ohne Nachweis-/Pruefmarker, fuer den Gleichheitsvergleich."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_normal(item) for item in value]
    if isinstance(value, dict):
        return {k: _normal(v) for k, v in value.items() if k not in {"evidence", "requires_review", "confidence"}}
    return value


def same(a: Any, b: Any) -> bool:
    return _normal(a) == _normal(b)


def _number(value: float) -> str:
    text = f"{value:,.2f}" if value != int(value) else f"{int(value):,}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def display(value: Any) -> Optional[str]:
    """Deutsche Anzeige eines Fakts; None, wenn leer."""
    if is_empty(value):
        return None
    if isinstance(value, bool):
        return "Ja" if value else "Nein"
    if isinstance(value, Enum):
        return _ENUM_DE.get(str(value.value), str(value.value))
    if isinstance(value, (int, float)):
        return _number(float(value))
    if isinstance(value, str):
        return _ENUM_DE.get(value, value.strip())
    if isinstance(value, list):
        if value and isinstance(value[0], BaseModel):
            data = _normal(value)
            if "device_name" in data[0] or "system_name" in data[0]:
                names = [d.get("system_name") or d.get("device_name") or d.get("model") or "Gerät" for d in data]
                return f"{len(names)}: " + ", ".join(names[:5]) + (" …" if len(names) > 5 else "")
            return f"{len(value)} Einträge"
        return ", ".join(str(item) for item in value[:8]) + (" …" if len(value) > 8 else "")
    if isinstance(value, BaseModel):
        data = _normal(value)
        if "date" in data or "condition" in data:
            if data.get("date"):
                year, month, day = str(data["date"]).split("-")
                return f"{day}.{month}.{year}"
            return data.get("condition")
        if "amount" in data:
            amount = f"{_number(float(data['amount']))} {data.get('currency') or ''}".strip()
            period = _PERIODS.get(str(data.get("period") or ""))
            return f"{amount} ({period})" if period else amount
        if "value" in data and "unit" in data:
            if data.get("original_text") and data.get("value") is None:
                return data["original_text"]
            number = data.get("value")
            singular, plural = _UNITS.get(str(data.get("unit")), (str(data.get("unit") or ""), str(data.get("unit") or "")))
            if number is None:
                return data.get("original_text")
            return f"{_number(float(number))} {singular if number == 1 else plural}".strip()
    return str(value)


def evidence_for(model: ExtractedContract, path: str) -> list[dict]:
    """Nachweise (Seite + Zitat) eines Fakts aus den Harness-Nachweisen."""
    rows = (model.analysis.harness or {}).get("evidence") or []
    out = []
    for row in rows:
        field_name = str(row.get("field") or "")
        if field_name == path or field_name.startswith(path + ".") or (path == "equipment" and field_name.startswith("identity_equipment")):
            source = row.get("source") or {}
            quote = source.get("source_text")
            if quote or source.get("page"):
                out.append({"page": source.get("page"), "quote": quote})
    return out[:3]


@dataclass
class FactRow:
    key: str
    label: str
    group: str  # new | changed | same | missing_again
    current: Optional[str]
    proposed: Optional[str]
    evidence: list[dict] = field(default_factory=list)
    register_keys: list[str] = field(default_factory=list)
    preselected: bool = False

    def as_dict(self) -> dict:
        return {
            "key": self.key, "label": self.label, "group": self.group, "current": self.current,
            "proposed": self.proposed, "evidence": self.evidence, "register_keys": self.register_keys,
            "preselected": self.preselected,
        }


def compare(accepted: Optional[ExtractedContract], candidate: ExtractedContract, *, only: Optional[Iterable[str]] = None) -> list[FactRow]:
    """Fakt fuer Fakt: neu gefunden, abweichend, gleich, nicht erneut gefunden.

    `only` begrenzt auf gesuchte Fakten (Modus "Nur fehlende Angaben").
    Nur neu gefundene Angaben mit Nachweis sind vorausgewaehlt.
    """
    wanted = set(only) if only else None
    rows: list[FactRow] = []
    for path in fact_paths(candidate):
        if wanted is not None and path not in wanted:
            continue
        new_value = get_fact(candidate, path)
        old_value = get_fact(accepted, path) if accepted is not None else None
        new_empty, old_empty = is_empty(new_value), is_empty(old_value)
        if new_empty and old_empty:
            continue
        if new_empty:
            group = "missing_again"
        elif old_empty:
            group = "new"
        elif same(old_value, new_value):
            group = "same"
        else:
            group = "changed"
        evidence = evidence_for(candidate, path) if not new_empty else []
        rows.append(FactRow(
            key=path, label=LABELS.get(path, path), group=group,
            current=display(old_value), proposed=display(new_value), evidence=evidence,
            register_keys=list(REGISTER_KEYS.get(path, ())),
            preselected=group == "new" and bool(evidence),
        ))
    order = {"new": 0, "changed": 1, "missing_again": 2, "same": 3}
    rows.sort(key=lambda row: order[row.group])
    return rows


def summary(rows: list[FactRow]) -> dict[str, int]:
    out = {"new": 0, "changed": 0, "same": 0, "missing_again": 0}
    for row in rows:
        out[row.group] += 1
    return out


def merge(accepted: ExtractedContract, candidate: ExtractedContract, keys: Iterable[str], *, run_id: str) -> ExtractedContract:
    """Kopie der akzeptierten Extraktion mit den ausgewaehlten Fakten des Kandidaten.

    Nachweise der uebernommenen Fakten kommen mit; leere Kandidatenwerte werden
    nie uebernommen (eine Angabe verschwindet nicht durch eine erneute Erfassung).
    """
    merged = accepted.model_copy(deep=True)
    applied: list[str] = []
    harness = dict(merged.analysis.harness or {})
    evidence = list(harness.get("evidence") or [])
    candidate_evidence = (candidate.analysis.harness or {}).get("evidence") or []
    for key in keys:
        value = get_fact(candidate, key)
        if is_empty(value):
            continue
        _set_fact(merged, key, value.model_copy(deep=True) if isinstance(value, BaseModel) else (
            [item.model_copy(deep=True) if isinstance(item, BaseModel) else item for item in value] if isinstance(value, list) else value
        ))

        evidence = [row for row in evidence if not _belongs(row, key)] + [row for row in candidate_evidence if _belongs(row, key)]
        applied.append(key)
    harness["evidence"] = evidence
    history = list(harness.get("reextractions") or [])
    history.append({"run_id": run_id, "applied": applied, "model": (candidate.analysis.harness or {}).get("model")})
    harness["reextractions"] = history
    merged.analysis.harness = harness
    return merged
