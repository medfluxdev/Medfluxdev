"""Feldkatalog des Vertragsregisters: Typ, Beschriftung, Validierung."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.database.models.contract import (
    DURATION_UNITS_ALLOWED,
    NOTICE_TO_ALLOWED,
    PRICE_ADJUSTMENT_ALLOWED,
    TERM_MODEL_ALLOWED,
)


class FieldValidationError(ValueError):
    def __init__(self, field_key: str, detail_de: str):
        super().__init__(detail_de)
        self.field_key = field_key
        self.detail_de = detail_de


@dataclass(frozen=True)
class FieldSpec:
    key: str
    kind: str  # text | bool | date | int | decimal | enum | uuid
    label_de: str
    group: str
    max_length: Optional[int] = None
    choices: tuple[str, ...] = ()
    reference: Optional[str] = None  # account | partner | contract_type | contract_category


FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec("internal_number", "text", "Interne Nummer", "identity", max_length=120),
    FieldSpec("short_description", "text", "Kurzbeschreibung", "identity", max_length=500),
    FieldSpec("subject_text", "text", "Vertragsgegenstand", "identity", max_length=20000),
    FieldSpec("is_framework", "bool", "Rahmenvertrag", "identity"),
    FieldSpec("data_protection_relevant", "bool", "Datenschutzrelevant (AVV erforderlich)", "identity"),
    FieldSpec("partner_id", "uuid", "Vertragspartner", "identity", reference="partner"),
    FieldSpec("contract_type_id", "uuid", "Vertragstyp", "identity", reference="contract_type"),
    FieldSpec("contract_category_id", "uuid", "Kategorie", "identity", reference="contract_category"),
    FieldSpec("storage_location_code", "text", "Lagerort des Originals", "organisation", max_length=64),
    FieldSpec("manual_billing", "bool", "Manuelle Abrechnung", "organisation"),
    FieldSpec("account_number", "text", "Kontonummer", "organisation", max_length=64),
    FieldSpec("term_model", "enum", "Vertragsart", "term", choices=TERM_MODEL_ALLOWED),
    FieldSpec("term_start_date", "date", "Vertragsbeginn", "term"),
    FieldSpec("term_fixed_end_date", "date", "Festes Vertragsende", "term"),
    FieldSpec("initial_term_value", "int", "Laufzeit", "term"),
    FieldSpec("initial_term_unit", "enum", "Laufzeit (Einheit)", "term", choices=DURATION_UNITS_ALLOWED),
    FieldSpec("minimum_term_value", "int", "Mindestlaufzeit", "term"),
    FieldSpec("minimum_term_unit", "enum", "Mindestlaufzeit (Einheit)", "term", choices=DURATION_UNITS_ALLOWED),
    FieldSpec("notice_period_value", "int", "Kündigungsfrist", "term"),
    FieldSpec("notice_period_unit", "enum", "Kündigungsfrist (Einheit)", "term", choices=DURATION_UNITS_ALLOWED),
    FieldSpec("notice_to", "enum", "Kündigung zum", "term", choices=NOTICE_TO_ALLOWED),
    FieldSpec("renewal_period_value", "int", "Verlängerung um", "term"),
    FieldSpec("renewal_period_unit", "enum", "Verlängerung (Einheit)", "term", choices=DURATION_UNITS_ALLOWED),
    FieldSpec("reminder_lead_months", "int", "Erinnerung (Monate vor Frist)", "reminder"),
    FieldSpec("reminder_recipient_account_id", "uuid", "Erinnerung an", "reminder", reference="account"),
    FieldSpec("escalation_recipient_account_id", "uuid", "Eskalation an", "reminder", reference="account"),
    FieldSpec("reminder_todo", "text", "ToDo", "reminder", max_length=500),
    FieldSpec("terminated_on", "date", "Gekündigt am", "termination"),
    FieldSpec("terminated_effective", "date", "Gekündigt zum", "termination"),
    FieldSpec("retention_years_after_end", "int", "Löschen nach Ende (Jahre)", "termination"),
    FieldSpec("price_adjustment_kind", "enum", "Preisanpassung", "finance", choices=PRICE_ADJUSTMENT_ALLOWED),
    FieldSpec("price_adjustment_percent", "decimal", "Preisanpassung (% je Anpassung)", "finance"),
    FieldSpec("price_adjustment_index_name", "text", "Preisindex", "finance", max_length=120),
    FieldSpec("price_adjustment_next_date", "date", "Nächste Preisanpassung", "finance"),
    FieldSpec("price_adjustment_interval_months", "int", "Anpassung alle (Monate)", "finance"),
)

FIELDS: dict[str, FieldSpec] = {spec.key: spec for spec in FIELD_SPECS}

# Pflichtangaben fuer den Statuswechsel nach "Gueltig".
REQUIRED_FOR_VALID: tuple[str, ...] = ("short_description", "term_model", "term_start_date")

_INT_LIMITS = {
    "reminder_lead_months": (0, 60),
    "retention_years_after_end": (0, 100),
    "price_adjustment_interval_months": (1, 120),
}


def coerce_value(key: str, raw: Any) -> Any:
    """Validiert/normalisiert einen Client-Wert; None/"" leert das Feld."""
    spec = FIELDS.get(key)
    if spec is None:
        raise FieldValidationError(key, f"Feld '{key}' ist nicht bearbeitbar.")
    if raw is None or (isinstance(raw, str) and raw.strip() == "" and spec.kind != "bool"):
        return None
    if spec.kind == "text":
        if not isinstance(raw, str):
            raise FieldValidationError(key, f"{spec.label_de}: Text erwartet.")
        value = raw.strip()
        if spec.max_length and len(value) > spec.max_length:
            raise FieldValidationError(key, f"{spec.label_de}: höchstens {spec.max_length} Zeichen.")
        return value
    if spec.kind == "bool":
        if isinstance(raw, bool):
            return raw
        raise FieldValidationError(key, f"{spec.label_de}: Ja/Nein erwartet.")
    if spec.kind == "date":
        if isinstance(raw, date):
            return raw
        try:
            return date.fromisoformat(str(raw).strip())
        except ValueError:
            raise FieldValidationError(key, f"{spec.label_de}: Datum im Format JJJJ-MM-TT erwartet.")
    if spec.kind == "int":
        if isinstance(raw, bool):
            raise FieldValidationError(key, f"{spec.label_de}: Zahl erwartet.")
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise FieldValidationError(key, f"{spec.label_de}: ganze Zahl erwartet.")
        low, high = _INT_LIMITS.get(key, (0, 1200))
        if not low <= value <= high:
            raise FieldValidationError(key, f"{spec.label_de}: Wert zwischen {low} und {high} erwartet.")
        return value
    if spec.kind == "decimal":
        if isinstance(raw, bool):
            raise FieldValidationError(key, f"{spec.label_de}: Zahl erwartet.")
        try:
            value = Decimal(str(raw).strip().replace(",", "."))
        except InvalidOperation:
            raise FieldValidationError(key, f"{spec.label_de}: Zahl erwartet.")
        if not value.is_finite() or not Decimal("-50") <= value <= Decimal("100"):
            raise FieldValidationError(key, f"{spec.label_de}: Wert zwischen -50 und 100 erwartet.")
        return value.quantize(Decimal("0.001"))
    if spec.kind == "enum":
        value = str(raw).strip()
        if value not in spec.choices:
            raise FieldValidationError(key, f"{spec.label_de}: ungültiger Wert.")
        return value
    if spec.kind == "uuid":
        try:
            return raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
        except ValueError:
            raise FieldValidationError(key, f"{spec.label_de}: ungültige Auswahl.")
    raise FieldValidationError(key, "Unbekannter Feldtyp.")


def to_json(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    return value


def validate_pairs(values: dict[str, Any]) -> None:
    """Wert und Einheit einer Dauer gehoeren zusammen."""
    for prefix in ("initial_term", "minimum_term", "notice_period", "renewal_period"):
        number, unit = values.get(f"{prefix}_value"), values.get(f"{prefix}_unit")
        if (number is None) != (unit is None):
            label = FIELDS[f"{prefix}_value"].label_de
            raise FieldValidationError(f"{prefix}_value", f"{label}: Zahl und Einheit gemeinsam angeben.")
    start, end = values.get("term_start_date"), values.get("term_fixed_end_date")
    if start is not None and end is not None and end < start:
        raise FieldValidationError("term_fixed_end_date", "Vertragsende liegt vor dem Vertragsbeginn.")
    on, effective = values.get("terminated_on"), values.get("terminated_effective")
    if on is not None and effective is not None and effective < on:
        raise FieldValidationError("terminated_effective", "„Gekündigt zum“ liegt vor „Gekündigt am“.")
