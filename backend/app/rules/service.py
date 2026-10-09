"""Vertragsregeln ("Playbooks"): von der Organisation festgelegte Anforderungen,
die der Code gegen die gepflegten Vertragsdaten prueft (nie die KI).

Ergebnis je Regel und Vertrag:
- "pass"    erfuellt
- "fail"    verletzt
- "unknown" nicht pruefbar, weil eine Angabe fehlt (nie geraten)
- "na"      gilt fuer diesen Vertrag nicht (Vertragsart oder -typ passt nicht)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.contract import Contract
from app.database.models.register import CatalogContractType, ContractRule
from app.register.fields import FIELD_SPECS

DAYS_PER_MONTH = Decimal("30.4375")

# Art -> (Bezeichnung, Einheit des Grenzwerts oder None)
RULE_KINDS: dict[str, tuple[str, Optional[str]]] = {
    "min_notice_months": ("Kündigungsfrist mindestens", "Monate"),
    "max_term_months": ("Laufzeit bzw. Mindestlaufzeit höchstens", "Monate"),
    "max_renewal_months": ("Automatische Verlängerung höchstens", "Monate"),
    "max_price_increase_percent": ("Preiserhöhung je Anpassung höchstens", "%"),
    "max_annual_cost": ("Jährliche Kosten (netto) höchstens", "€"),
    "required_field": ("Pflichtangabe vorhanden", None),
}

# Felder, die als Pflichtangabe geprueft werden koennen (Stammdaten des Vertrags).
REQUIRED_FIELD_LABELS: dict[str, str] = {
    **{spec.key: spec.label_de for spec in FIELD_SPECS if not spec.key.endswith("_unit")},
    "responsible_account_id": "Verantwortlich",
    "cost_center_id": "Kostenstelle",
    "hospital_id": "Krankenhaus / Gesellschaft",
}

_TERMINABLE = ("terminable", "terminable_min_term", "auto_renewal")


class RuleError(ValueError):
    def __init__(self, status_code: int, detail_de: str):
        super().__init__(detail_de)
        self.status_code = status_code
        self.detail_de = detail_de


@dataclass(frozen=True)
class RuleResult:
    rule_id: uuid.UUID
    label: str
    outcome: str
    detail: str

    def payload(self) -> dict:
        return {"rule_id": str(self.rule_id), "label": self.label, "outcome": self.outcome, "detail": self.detail}


def _months(value: Optional[int], unit: Optional[str]) -> Optional[Decimal]:
    if value is None or unit is None:
        return None
    number = Decimal(value)
    if unit == "years":
        return number * 12
    if unit == "months":
        return number
    if unit == "weeks":
        return (number * 7 / DAYS_PER_MONTH).quantize(Decimal("0.01"))
    if unit == "days":
        return (number / DAYS_PER_MONTH).quantize(Decimal("0.01"))
    return None


def _between(start: Optional[date], end: Optional[date]) -> Optional[Decimal]:
    if not start or not end or end < start:
        return None
    return Decimal((end.year - start.year) * 12 + (end.month - start.month)) + (Decimal(1) if end.day >= start.day else Decimal(0))


def _fmt(number: Decimal) -> str:
    text = f"{number.normalize():f}" if number == number.to_integral() else f"{number:.2f}"
    return text.replace(".", ",")


def _money(number: Decimal) -> str:
    whole = f"{number:,.2f}"
    return whole.replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _limit(rule: ContractRule) -> Decimal:
    return Decimal(rule.threshold)


def evaluate(rule: ContractRule, contract: Contract, annual_cost: Optional[Decimal]) -> RuleResult:
    def result(outcome: str, detail: str) -> RuleResult:
        return RuleResult(rule.id, rule.label, outcome, detail)

    types = [str(item) for item in (rule.contract_type_ids or [])]
    if types and str(contract.contract_type_id) not in types:
        return result("na", "Gilt nicht für diesen Vertragstyp.")

    kind = rule.rule_kind
    if kind == "required_field":
        value = getattr(contract, rule.field_key or "", None)
        label = REQUIRED_FIELD_LABELS.get(rule.field_key or "", rule.field_key or "Angabe")
        if value is None or (isinstance(value, str) and not value.strip()):
            return result("fail", f"{label} fehlt.")
        return result("pass", f"{label} ist erfasst.")

    if kind == "max_annual_cost":
        if annual_cost is None:
            return result("unknown", "Jährliche Kosten sind nicht erfasst.")
        ok = annual_cost <= _limit(rule)
        return result("pass" if ok else "fail", f"{_money(annual_cost)} jährlich (Grenze {_money(_limit(rule))}).")

    model = contract.term_model
    if kind in ("min_notice_months", "max_term_months", "max_renewal_months") and model is None:
        return result("unknown", "Vertragsart ist nicht erfasst.")

    if kind == "min_notice_months":
        if model not in _TERMINABLE:
            return result("na", "Vertrag ist nicht ordentlich kündbar.")
        months = _months(contract.notice_period_value, contract.notice_period_unit)
        if months is None:
            return result("unknown", "Kündigungsfrist ist nicht erfasst.")
        ok = months >= _limit(rule)
        return result("pass" if ok else "fail", f"Kündigungsfrist {_fmt(months)} Monate (mindestens {_fmt(_limit(rule))}).")

    if kind == "max_term_months":
        if model == "terminable_min_term":
            months = _months(contract.minimum_term_value, contract.minimum_term_unit)
            what = "Mindestlaufzeit"
        elif model in ("fixed_term", "auto_renewal"):
            months = _months(contract.initial_term_value, contract.initial_term_unit)
            if months is None and model == "fixed_term":
                months = _between(contract.term_start_date, contract.term_fixed_end_date)
            what = "Laufzeit"
        else:
            return result("na", "Vertrag hat keine feste Laufzeit.")
        if months is None:
            return result("unknown", f"{what} ist nicht erfasst.")
        ok = months <= _limit(rule)
        return result("pass" if ok else "fail", f"{what} {_fmt(months)} Monate (höchstens {_fmt(_limit(rule))}).")

    if kind == "max_renewal_months":
        if model != "auto_renewal":
            return result("na", "Keine automatische Verlängerung.")
        months = _months(contract.renewal_period_value, contract.renewal_period_unit)
        if months is None:
            return result("unknown", "Verlängerungszeitraum ist nicht erfasst.")
        ok = months <= _limit(rule)
        return result("pass" if ok else "fail", f"Verlängerung um {_fmt(months)} Monate (höchstens {_fmt(_limit(rule))}).")

    if kind == "max_price_increase_percent":
        adjustment = contract.price_adjustment_kind
        if adjustment is None:
            return result("unknown", "Preisanpassung ist nicht erfasst.")
        if adjustment == "fixed":
            return result("pass", "Festpreis.")
        if adjustment != "percent":
            return result("unknown", "Preisanpassung nach Index oder Verhandlung – Höhe nicht festgelegt.")
        if contract.price_adjustment_percent is None:
            return result("unknown", "Prozentsatz der Preisanpassung ist nicht erfasst.")
        percent = Decimal(contract.price_adjustment_percent)
        ok = percent <= _limit(rule)
        return result("pass" if ok else "fail", f"Preiserhöhung {_fmt(percent)} % (höchstens {_fmt(_limit(rule))} %).")

    return result("unknown", "Unbekannte Regelart.")


def active_rules(session: Session, organization_id: uuid.UUID) -> list[ContractRule]:
    return list(session.scalars(
        select(ContractRule)
        .where(ContractRule.organization_id == organization_id, ContractRule.is_active.is_(True))
        .order_by(ContractRule.sort_order, ContractRule.label)
    ).all())


def evaluate_all(rules: Iterable[ContractRule], contract: Contract, annual_cost: Optional[Decimal]) -> list[RuleResult]:
    return [evaluate(rule, contract, annual_cost) for rule in rules]


def summary_status(results: list[RuleResult]) -> Optional[str]:
    """Zusammenfassung fuer die Vertragsliste."""
    relevant = [item for item in results if item.outcome != "na"]
    if not relevant:
        return None
    if any(item.outcome == "fail" for item in relevant):
        return "Verstoß"
    if any(item.outcome == "unknown" for item in relevant):
        return "Unvollständig"
    return "Erfüllt"


# --------------------------------------------------------------------------- pflege


def rule_payload(row: ContractRule) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "label": row.label,
        "description": row.description,
        "rule_kind": row.rule_kind,
        "threshold": str(row.threshold) if row.threshold is not None else None,
        "field_key": row.field_key,
        "contract_type_ids": [str(item) for item in (row.contract_type_ids or [])],
        "is_active": row.is_active,
        "sort_order": row.sort_order,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _clean(session: Session, organization_id: uuid.UUID, values: dict[str, Any], row: Optional[ContractRule]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    current = {
        "rule_kind": row.rule_kind if row else None,
        "threshold": row.threshold if row else None,
        "field_key": row.field_key if row else None,
    }
    if "label" in values or row is None:
        label = str(values.get("label") or "").strip()
        if not label or len(label) > 160:
            raise RuleError(422, "Bezeichnung: 1 bis 160 Zeichen.")
        out["label"] = label
    if "description" in values:
        description = str(values.get("description") or "").strip()
        out["description"] = description[:500] or None
    if "rule_kind" in values or row is None:
        kind = values.get("rule_kind")
        if kind not in RULE_KINDS:
            raise RuleError(422, "Unbekannte Regelart.")
        out["rule_kind"] = current["rule_kind"] = kind
    if "threshold" in values:
        raw = values.get("threshold")
        if raw in (None, ""):
            out["threshold"] = current["threshold"] = None
        else:
            try:
                number = Decimal(str(raw).replace(",", "."))
            except InvalidOperation:
                raise RuleError(422, "Grenzwert: Zahl erwartet.")
            if number < 0 or number > Decimal("999999999"):
                raise RuleError(422, "Grenzwert ist ungültig.")
            out["threshold"] = current["threshold"] = number
    if "field_key" in values:
        out["field_key"] = current["field_key"] = values.get("field_key") or None
    if current["rule_kind"] == "required_field":
        if current["field_key"] not in REQUIRED_FIELD_LABELS:
            raise RuleError(422, "Bitte die Pflichtangabe wählen.")
        out["threshold"] = None
    else:
        if current["threshold"] is None:
            raise RuleError(422, "Bitte einen Grenzwert angeben.")
        out["field_key"] = None
    if "contract_type_ids" in values:
        raw_ids = values.get("contract_type_ids") or []
        if not isinstance(raw_ids, list):
            raise RuleError(422, "Vertragstypen: Liste erwartet.")
        try:
            wanted = {uuid.UUID(str(item)) for item in raw_ids}
        except ValueError:
            raise RuleError(422, "Ungültiger Vertragstyp.")
        if wanted:
            known = set(session.scalars(
                select(CatalogContractType.id).where(
                    CatalogContractType.organization_id == organization_id, CatalogContractType.id.in_(wanted)
                )
            ).all())
            if known != wanted:
                raise RuleError(422, "Vertragstyp nicht verfügbar.")
        out["contract_type_ids"] = sorted(str(item) for item in wanted)
    if "is_active" in values:
        if not isinstance(values["is_active"], bool):
            raise RuleError(422, "Aktiv: Ja/Nein erwartet.")
        out["is_active"] = values["is_active"]
    if "sort_order" in values:
        try:
            out["sort_order"] = int(values["sort_order"])
        except (TypeError, ValueError):
            raise RuleError(422, "Reihenfolge: Zahl erwartet.")
    return out


def create_rule(session: Session, organization_id: uuid.UUID, values: dict[str, Any]) -> ContractRule:
    clean = _clean(session, organization_id, values, None)
    row = ContractRule(organization_id=organization_id, **clean)
    session.add(row)
    session.flush()
    return row


def update_rule(session: Session, row: ContractRule, values: dict[str, Any]) -> ContractRule:
    for key, value in _clean(session, row.organization_id, values, row).items():
        setattr(row, key, value)
    session.flush()
    return row


def kinds_payload() -> dict:
    return {
        "kinds": [{"key": key, "label": label, "unit": unit} for key, (label, unit) in RULE_KINDS.items()],
        "required_fields": [{"key": key, "label": label} for key, label in REQUIRED_FIELD_LABELS.items()],
    }
