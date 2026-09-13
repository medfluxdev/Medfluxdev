"""Semantischer Verifier (STEP 8B-Semantik).

Der Verifier bewertet sensible extrahierte Werte gegen feldspezifische Belege.
Wenn Extraktionseinheiten verfügbar sind, wird der Beleg deterministisch für das
konkrete Feld geroutet; section-level evidence ist nur ein Fallback. Dadurch
kann z. B. dates.minimum_duration nicht mehr vom evidence eines anderen
Dates-/Termination-Felds abhängig sein.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

from app.ai.service import AIService
from app.ai.schema import pydantic_json_schema
from app.models.enums import BillingInterval, ContractType, TimeUnit


class SensitiveValue(BaseModel):
    """Ein zu verifizierender sensibler Wert mit seinem konkreten Beleg."""

    field: str
    value: Any = None
    evidence: Optional[str] = None
    evidence_scope: Optional[str] = None  # field|section


class VerificationDecision(BaseModel):
    field: str
    supported: bool = False
    reason: Optional[str] = None


class SensitiveVerificationResult(BaseModel):
    model_config = {"extra": "forbid"}
    decisions: list[VerificationDecision] = Field(default_factory=list)


SENSITIVE_FIELDS = (
    "identity.contract_number",
    "dates.start_date",
    "dates.end_date",
    "dates.duration",
    "dates.minimum_duration",
    "termination.cancellation_period",
    "termination.automatic_renewal",
    "termination.renewal_period",
    "costs.annual_cost",
    "costs.monthly_cost",
    "costs.total_contract_value",
    "payment.billing_interval",
)

VERIFIER_SYSTEM_PROMPT = (
    "Du bist ein unabhängiger Prüfer für deutsche Wartungs- und Serviceverträge von Medflux.\n"
    "Du BEWERTEST NUR, ob ein vorgeschlagener extrahierter Wert durch den beigelegten "
    "feldspezifischen Nachweis/Text KONKRET GESTÜTZT ist. Du ERFINDEST KEINEN besseren Wert und änderst "
    "nichts – deine einzige Aufgabe ist supported (true/false) mit einer knappen deutschen Begründung.\n"
    "Regeln:\n"
    "- 'supported'=true nur, wenn der Wert wörtlich oder eindeutig aus dem Beleg/Kontext ableitbar ist.\n"
    "- Feldspezifisches evidence hat Vorrang vor allgemeinem Kontext.\n"
    "- Bei Widerspruch, fehlender Stützung oder wenn der Beleg den Wert nicht hergibt => supported=false.\n"
    "- Keine Raten von Monats-/Jahreswerten, keine Berechnung von Fristen/Daten.\n"
    "- Die Entscheidungsliste enthält GENAU die vorgegebenen Felder; jedes Feld genau einmal."
)


_DURATION_UNITS = {
    "days": ("tag", "tage", "tagen", "day", "days"),
    "weeks": ("woche", "wochen", "week", "weeks"),
    "months": ("monat", "monate", "monaten", "month", "months"),
    "years": ("jahr", "jahre", "jahren", "year", "years"),
    "hours": ("stunde", "stunden", "hour", "hours", "std"),
}

_FIELD_LABELS = {
    "dates.minimum_duration": re.compile(
        r"mindest(?:vertrags)?laufzeit|mindestbindung|minimum\s+(?:term|duration)", re.I
    ),
    "dates.duration": re.compile(r"(?:vertrags)?laufzeit|vertragsdauer|\bdauer\b", re.I),
    "termination.cancellation_period": re.compile(
        r"kündigungsfrist|kuendigungsfrist|cancellation\s+period|notice\s+period", re.I
    ),
    "termination.renewal_period": re.compile(
        r"verlänger(?:ung|ungszeitraum)|verlaenger(?:ung|ungszeitraum)|renewal", re.I
    ),
    "termination.automatic_renewal": re.compile(
        r"automatisch|verlänger|verlaenger|renewal", re.I
    ),
    "dates.start_date": re.compile(r"vertragsbeginn|beginn|start(?:datum| date)?", re.I),
    "dates.end_date": re.compile(r"vertragsende|ende|end(?:datum| date)?", re.I),
    "costs.annual_cost": re.compile(r"jährlich|jaehrlich|pro\s+jahr|annual", re.I),
    "costs.monthly_cost": re.compile(r"monatlich|pro\s+monat|monthly", re.I),
    "costs.total_contract_value": re.compile(r"gesamt(?:wert|preis|betrag)|total", re.I),
}


def _unit_texts(units: Optional[Iterable[object]]) -> list[str]:
    if not units:
        return []
    out: list[str] = []
    for unit in units:
        text = str(getattr(unit, "text", "") or "").strip()
        if text:
            out.append(text)
    return out


def _short_excerpt(text: str, match_start: int = 0, match_end: Optional[int] = None) -> str:
    text = " ".join(text.split())
    if len(text) <= 180:
        return text
    match_end = match_end if match_end is not None else match_start
    start = max(0, match_start - 60)
    end = min(len(text), max(match_end + 100, start + 180))
    return text[start:end][:180]


def _duration_parts(value: Any) -> tuple[Optional[int], Optional[str]]:
    if value is None:
        return None, None
    number = getattr(value, "value", None)
    unit = getattr(value, "unit", None)
    if isinstance(value, dict):
        number = value.get("value")
        unit = value.get("unit")
    if isinstance(unit, TimeUnit):
        unit = unit.value
    return number, str(unit) if unit else None


def _money_amount(value: Any) -> Optional[float]:
    if value is None:
        return None
    amount = getattr(value, "amount", None)
    if isinstance(value, dict):
        amount = value.get("amount")
    return amount


def _contains_duration_value(text: str, value: Any) -> bool:
    number, unit = _duration_parts(value)
    if number is None or not unit:
        return False
    unit_words = _DURATION_UNITS.get(unit, (unit,))
    number_re = re.compile(rf"(?<!\d){re.escape(str(number))}(?!\d)")
    return bool(number_re.search(text)) and any(word.casefold() in text.casefold() for word in unit_words)


def _contains_money_value(text: str, value: Any) -> bool:
    amount = _money_amount(value)
    if amount is None:
        return False
    integer = int(amount) if float(amount).is_integer() else None
    variants = {str(amount).replace(".", ",")}
    if integer is not None:
        variants.update({str(integer), f"{integer:,}".replace(",", "."), f"{integer:,}".replace(",", " ")})
    compact = text.replace(" ", "")
    return any(v.replace(" ", "") in compact for v in variants)


def _field_evidence(field: str, value: Any, units: Optional[Iterable[object]]) -> Optional[str]:
    """Findet einen engen, feldspezifischen Beleg direkt in den Source Units.

    Diese Funktion akzeptiert nur semantisch passende Zeilen/Einheiten. Ein
    fachfremder Section-Beleg kann dadurch kein sensibles Feld mehr scheinbar
    belegen oder entwerten.
    """
    texts = _unit_texts(units)
    if not texts or value is None:
        return None

    if field == "identity.contract_number":
        needle = str(value).strip()
        label_re = re.compile(
            r"vertragsnummer|vertrags[- ]?nr\.?|vertrag[- ]?nr\.?|angebotsnummer|angebots[- ]?nr\.?"," 
            " re.I
        )
        for text in texts:
            if needle and needle.casefold() in text.casefold() and label_re.search(text):
                m = label_re.search(text)
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field in {
        "dates.duration",
        "dates.minimum_duration",
        "termination.cancellation_period",
        "termination.renewal_period",
    }:
        label_re = _FIELD_LABELS[field]
        for text in texts:
            m = label_re.search(text)
            if m and _contains_duration_value(text, value):
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field == "termination.automatic_renewal":
        label_re = _FIELD_LABELS[field]
        for text in texts:
            m = label_re.search(text)
            if m:
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field in {"dates.start_date", "dates.end_date"}:
        label_re = _FIELD_LABELS[field]
        formatted = _fmt(value)
        date_value = formatted.get("date") if isinstance(formatted, dict) else formatted
        condition = formatted.get("condition") if isinstance(formatted, dict) else None
        for text in texts:
            m = label_re.search(text)
            if not m:
                continue
            if date_value and str(date_value) in text:
                return _short_excerpt(text, m.start(), m.end())
            if condition and str(condition).casefold() in text.casefold():
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field in {"costs.annual_cost", "costs.monthly_cost", "costs.total_contract_value"}:
        label_re = _FIELD_LABELS[field]
        for text in texts:
            m = label_re.search(text)
            if m and _contains_money_value(text, value):
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field == "payment.billing_interval":
        interval = value.value if isinstance(value, BillingInterval) else str(value)
        words = {
            "monthly": ("monatlich", "pro monat", "monthly"),
            "quarterly": ("vierteljährlich", "quartalsweise", "quarterly"),
            "semi_annual": ("halbjährlich", "semi-annual", "semi annual"),
            "annual": ("jährlich", "jaehrlich", "pro jahr", "annual"),
            "once": ("einmalig", "once"),
        }.get(interval, ())
        for text in texts:
            low = text.casefold()
            for word in words:
                idx = low.find(word.casefold())
                if idx >= 0:
                    return _short_excerpt(text, idx, idx + len(word))
    return None


def _collect_sensitive_values(contract, units: Optional[Iterable[object]] = None) -> list[SensitiveValue]:
    """Sammelt sensible Werte mit feldspezifischem Evidence-Routing.

    Source-unit evidence hat Vorrang. Section-level evidence bleibt aus
    Rückwärtskompatibilität als Fallback erhalten.
    """
    out: list[SensitiveValue] = []

    def _section_ev(section) -> Optional[str]:
        ev = getattr(section, "evidence", None)
        if ev is None:
            return None
        return (ev.source_text or "")[:120] or None

    def _add(field: str, value: Any, section) -> None:
        field_ev = _field_evidence(field, value, units)
        if field_ev:
            evidence, scope = field_ev, "field"
        else:
            evidence = _section_ev(section)
            scope = "section" if evidence else None
        out.append(SensitiveValue(field=field, value=_fmt(value), evidence=evidence, evidence_scope=scope))

    ident = contract.identity
    _add("identity.contract_number", getattr(ident, "contract_number", None), ident)

    d = contract.dates
    for name in ("start_date", "end_date", "duration", "minimum_duration"):
        _add(f"dates.{name}", getattr(d, name, None), d)

    t = contract.termination
    for name in ("cancellation_period", "automatic_renewal", "renewal_period"):
        _add(f"termination.{name}", getattr(t, name, None), t)

    c = contract.costs
    for name in ("annual_cost", "monthly_cost", "total_contract_value"):
        _add(f"costs.{name}", getattr(c, name, None), c)

    p = contract.payment
    _add("payment.billing_interval", getattr(p, "billing_interval", None), p)
    return out


def _fmt(v) -> Any:
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (ContractType, BillingInterval, TimeUnit)):
        return v.value
    if hasattr(v, "model_dump"):
        data = v.model_dump()
        for key, value in list(data.items()):
            if isinstance(value, (ContractType, BillingInterval, TimeUnit)):
                data[key] = value.value
            elif isinstance(value, date):
                data[key] = value.isoformat()
        return data
    return v


def _payload(sensitive: list[SensitiveValue], context: str) -> dict:
    import json

    values = json.loads(json.dumps([s.model_dump() for s in sensitive], ensure_ascii=False, default=str))
    return {"sensitive_values": values, "context": context[:4000]}


async def run_verifier(
    ai_service: "AIService",
    contract,
    context: str,
    max_tokens: int = 1500,
    units: Optional[Iterable[object]] = None,
) -> tuple[SensitiveVerificationResult, int]:
    """Führt den Semantik-Verifier fail-safe mit feldspezifischen Belegen aus."""
    import json

    sensitive = _collect_sensitive_values(contract, units=units)
    sensitive = [s for s in sensitive if _is_sensitive_relevant(s)]
    if not sensitive:
        return SensitiveVerificationResult(), 0

    payload = json.dumps(_payload(sensitive, context), ensure_ascii=False)
    schema = pydantic_json_schema(SensitiveVerificationResult)

    try:
        raw = await ai_service.generate_structured(payload, VERIFIER_SYSTEM_PROMPT, schema, max_tokens=max_tokens)
    except Exception:
        return SensitiveVerificationResult(), 1

    try:
        data = json.loads(raw)
    except Exception:
        return SensitiveVerificationResult(), 1

    try:
        return SensitiveVerificationResult.model_validate(data), 1
    except Exception:
        return SensitiveVerificationResult(), 1


def _is_sensitive_relevant(s: SensitiveValue) -> bool:
    """Unknown/default values are not claims and must not create verifier noise."""
    if s.value is None:
        return False
    if s.field == "payment.billing_interval" and s.value in (BillingInterval.OTHER, BillingInterval.OTHER.value, "other"):
        return False
    return True


def unsupported_fields(result: SensitiveVerificationResult) -> set[str]:
    return {d.field for d in result.decisions if d.supported is False}
