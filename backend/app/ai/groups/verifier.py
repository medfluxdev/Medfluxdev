"""Semantic verifier for safety-critical extracted contract claims.

The verifier is intentionally evidence-first and fail-closed. It never invents a
replacement value: it only decides whether an extracted claim is supported by a
field-specific source excerpt. With real extraction units available, section
level evidence is not borrowed for unrelated critical fields.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Iterable, Optional

from pydantic import BaseModel, Field

from app.ai.groups.critical_policy import current_verifier_fields, policy_for
from app.ai.schema import pydantic_json_schema
from app.ai.service import AIService
from app.models.enums import BillingInterval, ContractType, TimeUnit


class SensitiveValue(BaseModel):
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


# Compatibility export used by GroupPipeline. The central policy is authoritative.
SENSITIVE_FIELDS = current_verifier_fields()

VERIFIER_SYSTEM_PROMPT = (
    "Du bist ein unabhängiger Prüfer für deutsche Wartungs- und Serviceverträge von Medflux.\n"
    "Bewerte NUR, ob jeder vorgeschlagene Wert durch seinen feldspezifischen Beleg konkret gestützt ist. "
    "Erfinde oder korrigiere keine Werte.\n"
    "Regeln:\n"
    "- supported=true nur bei wörtlicher oder eindeutig ableitbarer Stützung.\n"
    "- Feldspezifisches evidence hat Vorrang; allgemeiner Kontext darf fehlenden Beleg nicht ersetzen.\n"
    "- Rollen (Auftraggeber/Auftragnehmer), Geldperiode, Fristart, Service-Flag und SLA-Art müssen zum Feld passen.\n"
    "- false bei Widerspruch, Mehrdeutigkeit, fehlender Stützung oder nur thematisch ähnlichem Text.\n"
    "- Keine Berechnung von Monats-/Jahreswerten, Fristen, Daten oder Vertragswerten.\n"
    "- Die Entscheidungsliste enthält GENAU die vorgegebenen Felder; jedes Feld genau einmal."
)

_DURATION_UNITS = {
    "days": ("tag", "tage", "tagen", "day", "days"),
    "weeks": ("woche", "wochen", "week", "weeks"),
    "months": ("monat", "monate", "monaten", "month", "months"),
    "years": ("jahr", "jahre", "jahren", "year", "years"),
    "hours": ("stunde", "stunden", "hour", "hours", "std"),
}

_FIELD_LABELS: dict[str, re.Pattern[str]] = {
    "dates.minimum_duration": re.compile(r"mindest(?:vertrags)?laufzeit|mindestbindung|minimum\s+(?:term|duration)", re.I),
    "dates.duration": re.compile(r"(?:vertrags)?laufzeit|vertragsdauer|\bdauer\b", re.I),
    "termination.cancellation_period": re.compile(r"kündigungsfrist|kuendigungsfrist|cancellation\s+period|notice\s+period", re.I),
    "termination.renewal_period": re.compile(r"verlänger(?:ung|ungszeitraum)|verlaenger(?:ung|ungszeitraum)|renewal", re.I),
    "termination.automatic_renewal": re.compile(r"automatisch|verlänger|verlaenger|renewal", re.I),
    "dates.start_date": re.compile(r"vertragsbeginn|beginn|start(?:datum| date)?", re.I),
    "dates.end_date": re.compile(r"vertragsende|ende|end(?:datum| date)?", re.I),
    "costs.annual_cost": re.compile(r"jährlich|jaehrlich|pro\s+jahr|jahres(?:preis|gebühr|gebuehr)|annual", re.I),
    "costs.monthly_cost": re.compile(r"monatlich|pro\s+monat|monats(?:preis|gebühr|gebuehr)|monthly", re.I),
    "costs.quarterly_cost": re.compile(r"quartal|vierteljährlich|vierteljaehrlich|quarter", re.I),
    "costs.semi_annual_cost": re.compile(r"halbjährlich|halbjaehrlich|semi[- ]?annual", re.I),
    "costs.one_time_cost": re.compile(r"einmalig|einmalzahlung|one[- ]?time", re.I),
    "costs.maintenance_fee": re.compile(r"wartungsgebühr|wartungsgebuehr|maintenance\s+fee", re.I),
    "costs.hourly_rate": re.compile(r"stundensatz|pro\s+stunde|hourly\s+rate", re.I),
    "costs.additional_costs": re.compile(r"zusatzkosten|zusätzliche\s+kosten|zusaetzliche\s+kosten|additional\s+cost", re.I),
    "costs.total_contract_value": re.compile(r"gesamt(?:wert|preis|betrag)|vertragswert|total", re.I),
    "payment.payment_deadline_days": re.compile(r"zahlungsziel|zahlbar|fällig|faellig|innerhalb", re.I),
    "payment.advance_payment": re.compile(r"vorauszahlung|vorkasse|anzahlung|advance\s+payment", re.I),
    "sla.response_time": re.compile(r"reaktionszeit|response\s+time", re.I),
    "sla.resolution_time": re.compile(r"lösungszeit|loesungszeit|behebungszeit|resolution\s+time", re.I),
    "sla.emergency_availability": re.compile(r"notfall|bereitschaft|emergency", re.I),
}

_PARTY_LABELS = {
    "identity.supplier": re.compile(r"auftragnehmer|dienstleister|lieferant|anbieter|supplier|provider", re.I),
    "identity.customer": re.compile(r"auftraggeber|kunde|besteller|customer|client", re.I),
    "identity.contractor": re.compile(r"auftragnehmer|contractor", re.I),
}

_SERVICE_TERMS = {
    "services.maintenance": ("wartung", "maintenance"),
    "services.repair": ("reparatur", "reparaturen", "repair"),
    "services.software_updates": ("software-update", "software update", "softwareupdates"),
    "services.spare_parts_included": ("ersatzteile", "verschleißteile", "verschleissteile", "spare parts"),
    "services.emergency_service": ("notdienst", "notfallservice", "emergency service", "bereitschaft"),
}

_NEGATION_RE = re.compile(r"\b(?:nicht|kein(?:e|en|er)?|ohne|ausgeschlossen|nicht\s+enthalten)\b", re.I)
_24_7_RE = re.compile(r"24\s*(?:/|x)\s*7|rund\s+um\s+die\s+uhr|24\s*stunden\s*(?:am\s+tag)?", re.I)


def _unit_texts(units: Optional[Iterable[object]]) -> list[str]:
    if not units:
        return []
    return [
        text
        for unit in units
        if (text := str(getattr(unit, "text", "") or "").strip())
    ]


def _short_excerpt(text: str, match_start: int = 0, match_end: Optional[int] = None) -> str:
    text = " ".join(text.split())
    if len(text) <= 220:
        return text
    match_end = match_end if match_end is not None else match_start
    start = max(0, match_start - 75)
    end = min(len(text), max(match_end + 120, start + 220))
    return text[start:end][:220]


def _duration_parts(value: Any) -> tuple[Optional[float], Optional[str]]:
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


def _contains_number(text: str, number: float | int) -> bool:
    raw = str(number)
    variants = {raw, raw.replace(".", ",")}
    if float(number).is_integer():
        integer = int(number)
        variants.update({str(integer), f"{integer:,}".replace(",", "."), f"{integer:,}".replace(",", " ")})
    compact = text.replace(" ", "")
    return any(v.replace(" ", "") in compact for v in variants)


def _contains_duration_value(text: str, value: Any) -> bool:
    number, unit = _duration_parts(value)
    if number is None or not unit:
        return False
    words = _DURATION_UNITS.get(unit, (unit,))
    return _contains_number(text, number) and any(word.casefold() in text.casefold() for word in words)


def _money_currency(value: Any) -> Optional[str]:
    if value is None:
        return None
    currency = getattr(value, "currency", None)
    if isinstance(value, dict):
        currency = value.get("currency")
    return str(currency).strip().upper() if currency else None


def _contains_currency(text: str, currency: Optional[str]) -> bool:
    if not currency:
        return True
    markers = {
        "EUR": ("eur", "€", "euro"),
        "USD": ("usd", "$", "us-dollar", "us dollar"),
        "CHF": ("chf", "fr.", "franken"),
        "GBP": ("gbp", "£", "pound"),
    }.get(currency, (currency.casefold(),))
    low = text.casefold()
    return any(marker.casefold() in low for marker in markers)


def _contains_money_value(text: str, value: Any) -> bool:
    amount = _money_amount(value)
    currency = _money_currency(value)
    return (
        amount is not None
        and _contains_number(text, amount)
        and _contains_currency(text, currency)
    )


def _contains_time_value(text: str, value: Any) -> bool:
    formatted = _fmt(value)
    if not isinstance(formatted, dict):
        return False
    original = str(formatted.get("original_text") or "").strip()
    if original and original.casefold() in text.casefold():
        return True
    return _contains_duration_value(text, formatted)


def _party_evidence(field: str, value: Any, texts: list[str]) -> Optional[str]:
    needle = " ".join(str(value or "").split())
    if not needle:
        return None
    label_re = _PARTY_LABELS[field]
    for text in texts:
        low = text.casefold()
        idx = low.find(needle.casefold())
        role = label_re.search(text)
        if idx >= 0 and role:
            return _short_excerpt(text, min(idx, role.start()), max(idx + len(needle), role.end()))
    return None


def _bool_evidence(texts: list[str], terms: tuple[str, ...], expected: bool) -> Optional[str]:
    for text in texts:
        low = text.casefold()
        positions = [low.find(term.casefold()) for term in terms if low.find(term.casefold()) >= 0]
        if not positions:
            continue
        idx = min(positions)
        start = max(0, idx - 80)
        end = min(len(text), idx + 140)
        window = text[start:end]
        negated = bool(_NEGATION_RE.search(window))
        if expected and not negated:
            return _short_excerpt(text, idx, idx + 1)
        if not expected and negated:
            return _short_excerpt(text, idx, idx + 1)
    return None


def _field_evidence(field: str, value: Any, units: Optional[Iterable[object]]) -> Optional[str]:
    """Return a narrow excerpt that proves both field semantics and value."""
    texts = _unit_texts(units)
    if not texts or value is None:
        return None

    if field in _PARTY_LABELS:
        return _party_evidence(field, value, texts)

    if field == "identity.contract_number":
        needle = str(value).strip()
        label_re = re.compile(r"vertragsnummer|vertrags[- ]?nr\.?|vertrag[- ]?nr\.?|angebotsnummer|angebots[- ]?nr\.?", re.I)
        for text in texts:
            if needle and needle.casefold() in text.casefold() and (m := label_re.search(text)):
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field in {"dates.duration", "dates.minimum_duration", "termination.cancellation_period", "termination.renewal_period"}:
        label_re = _FIELD_LABELS[field]
        for text in texts:
            if (m := label_re.search(text)) and _contains_duration_value(text, value):
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field == "termination.automatic_renewal":
        expected = bool(value)
        for text in texts:
            if not (m := _FIELD_LABELS[field].search(text)):
                continue
            window = _short_excerpt(text, m.start(), m.end())
            negated = bool(_NEGATION_RE.search(window))
            if expected and not negated:
                return window
            if not expected and negated:
                return window
        return None

    if field in {"dates.start_date", "dates.end_date"}:
        label_re = _FIELD_LABELS[field]
        formatted = _fmt(value)
        date_value = formatted.get("date") if isinstance(formatted, dict) else formatted
        condition = formatted.get("condition") if isinstance(formatted, dict) else None
        for text in texts:
            if not (m := label_re.search(text)):
                continue
            if date_value and str(date_value) in text:
                return _short_excerpt(text, m.start(), m.end())
            if condition and str(condition).casefold() in text.casefold():
                return _short_excerpt(text, m.start(), m.end())
        return None

    money_fields = {
        "costs.annual_cost", "costs.monthly_cost", "costs.quarterly_cost",
        "costs.semi_annual_cost", "costs.one_time_cost", "costs.maintenance_fee",
        "costs.hourly_rate", "costs.additional_costs", "costs.total_contract_value",
        "payment.advance_payment",
    }
    if field in money_fields:
        label_re = _FIELD_LABELS[field]
        for text in texts:
            if (m := label_re.search(text)) and _contains_money_value(text, value):
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field == "costs.price_adjustment_clause":
        needle = " ".join(str(value).split())
        for text in texts:
            idx = text.casefold().find(needle.casefold())
            if needle and idx >= 0:
                return _short_excerpt(text, idx, idx + len(needle))
        return None

    if field == "costs.tax_basis":
        wanted = str(value).casefold()
        words = ("netto", "net") if wanted == "net" else ("brutto", "gross") if wanted == "gross" else (wanted,)
        for text in texts:
            low = text.casefold()
            for word in words:
                idx = low.find(word)
                if idx >= 0:
                    return _short_excerpt(text, idx, idx + len(word))
        return None

    if field == "costs.tax_rate_percent":
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        for text in texts:
            if _contains_number(text, number) and "%" in text and re.search(r"mwst|mehrwertsteuer|umsatzsteuer|vat|steuer", text, re.I):
                idx = text.find("%")
                return _short_excerpt(text, max(0, idx - 15), idx + 1)
        return None

    if field == "payment.payment_deadline_days":
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        for text in texts:
            if (m := _FIELD_LABELS[field].search(text)) and _contains_number(text, number) and re.search(r"tag|tage|tagen|days?", text, re.I):
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field == "payment.billing_interval":
        interval = value.value if isinstance(value, BillingInterval) else str(value)
        words = {
            "monthly": ("monatlich", "pro monat", "monthly"),
            "quarterly": ("vierteljährlich", "vierteljaehrlich", "quartalsweise", "quarterly"),
            "semi_annual": ("halbjährlich", "halbjaehrlich", "semi-annual", "semi annual"),
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

    if field in _SERVICE_TERMS:
        return _bool_evidence(texts, _SERVICE_TERMS[field], bool(value))

    if field in {"sla.response_time", "sla.resolution_time", "sla.emergency_availability"}:
        label_re = _FIELD_LABELS[field]
        for text in texts:
            if (m := label_re.search(text)) and _contains_time_value(text, value):
                return _short_excerpt(text, m.start(), m.end())
        return None

    if field == "sla.availability_24_7":
        expected = bool(value)
        for text in texts:
            if not (m := _24_7_RE.search(text)):
                continue
            window = _short_excerpt(text, m.start(), m.end())
            negated = bool(_NEGATION_RE.search(window))
            if expected and not negated:
                return window
            if not expected and negated:
                return window
        return None

    return None


def _fmt(v: Any) -> Any:
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


def _section_evidence(section: Any) -> Optional[str]:
    ev = getattr(section, "evidence", None)
    if ev is None:
        return None
    return (ev.source_text or "")[:180] or None


def _collect_sensitive_values(contract: Any, units: Optional[Iterable[object]] = None) -> list[SensitiveValue]:
    out: list[SensitiveValue] = []
    has_units = bool(_unit_texts(units))
    for field in SENSITIVE_FIELDS:
        section_name, attr_name = field.split(".", 1)
        section = getattr(contract, section_name, None)
        value = getattr(section, attr_name, None) if section is not None else None
        field_ev = _field_evidence(field, value, units)
        if field_ev:
            evidence, scope = field_ev, "field"
        elif not has_units and section is not None:
            # Compatibility for isolated unit tests/callers without source units.
            # Production extraction always supplies units and therefore never
            # borrows unrelated section evidence for a missing critical proof.
            evidence = _section_evidence(section)
            scope = "section" if evidence else None
        else:
            evidence, scope = None, None
        out.append(SensitiveValue(field=field, value=_fmt(value), evidence=evidence, evidence_scope=scope))
    return out


def _claim_has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        if not value:
            return False
        if isinstance(value, dict):
            substantive = [v for k, v in value.items() if k not in {"requires_review"}]
            return any(_claim_has_content(v) for v in substantive)
    return True


def _is_sensitive_relevant(s: SensitiveValue) -> bool:
    """Defaults/empty wrappers are not factual claims and create no verifier noise."""
    if not _claim_has_content(s.value):
        return False
    policy = policy_for(s.field)
    if policy is not None and any(s.value == unknown for unknown in policy.unknown_values):
        return False
    return True


def _payload(sensitive: list[SensitiveValue], context: str) -> dict[str, Any]:
    values = json.loads(json.dumps([s.model_dump() for s in sensitive], ensure_ascii=False, default=str))
    return {"sensitive_values": values, "context": context[:4000]}


async def run_verifier(
    ai_service: AIService,
    contract: Any,
    context: str,
    max_tokens: int = 2200,
    units: Optional[Iterable[object]] = None,
) -> tuple[SensitiveVerificationResult, int]:
    """Run semantic verification and reject incomplete/duplicate result sets."""
    sensitive = [
        s
        for s in _collect_sensitive_values(contract, units=units)
        if _is_sensitive_relevant(s)
    ]
    if not sensitive:
        return SensitiveVerificationResult(), 0

    # Evidence-first invariant: a critical claim without a concrete routed
    # excerpt is deterministically unsupported. Do not ask the model to rescue
    # it from broad context; that would turn the LLM into an authority.
    rejected = {
        s.field: VerificationDecision(
            field=s.field,
            supported=False,
            reason="Kein feldspezifischer Quellenbeleg vorhanden.",
        )
        for s in sensitive
        if not (s.evidence or "").strip()
    }
    to_verify = [s for s in sensitive if s.field not in rejected]

    if not to_verify:
        return SensitiveVerificationResult(
            decisions=[rejected[s.field] for s in sensitive]
        ), 0

    payload = json.dumps(_payload(to_verify, context), ensure_ascii=False)
    schema = pydantic_json_schema(SensitiveVerificationResult)
    try:
        raw = await ai_service.generate_structured(
            payload, VERIFIER_SYSTEM_PROMPT, schema, max_tokens=max_tokens
        )
    except Exception:
        # The model/verifier outage still fails closed for every claim that
        # reached it. Returning no decisions lets GroupPipeline mark them
        # missing, while deterministic no-evidence rejections are preserved.
        return SensitiveVerificationResult(
            decisions=[rejected[s.field] for s in sensitive if s.field in rejected]
        ), 1

    try:
        result = SensitiveVerificationResult.model_validate(json.loads(raw))
    except Exception:
        return SensitiveVerificationResult(
            decisions=[rejected[s.field] for s in sensitive if s.field in rejected]
        ), 1

    expected = [s.field for s in to_verify]
    returned = [d.field for d in result.decisions]
    if len(returned) != len(set(returned)) or set(returned) != set(expected):
        return SensitiveVerificationResult(
            decisions=[rejected[s.field] for s in sensitive if s.field in rejected]
        ), 1

    verified_by_field = {d.field: d for d in result.decisions}
    combined = [
        rejected.get(s.field) or verified_by_field[s.field]
        for s in sensitive
    ]
    return SensitiveVerificationResult(decisions=combined), 1


def unsupported_fields(result: SensitiveVerificationResult) -> set[str]:
    return {d.field for d in result.decisions if d.supported is False}
