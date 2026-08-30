"""Semantischer Verifier (STEP 8B-Semantik).

Ein zweiter, fokussierter KI-Durchlauf für SENSIBLE Felder. Der Verifier erfindet
KEINEN besseren Wert; er bewertet nur, ob der von der Extraktion vorgeschlagene
Wert durch den zitierten Nachweis/Kontext GESTÜTZT ist. Antwort: supported
bool + knappe Begründung. Bei fehlender Stützung wird der Wert herabgestuft /
zur manuellen Prüfung markiert (never guess).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.ai.service import AIService
from app.ai.schema import pydantic_json_schema
from app.models.enums import BillingInterval, ContractType, TimeUnit


class SensitiveValue(BaseModel):
    """Ein zu verifizierender sensibler Wert (flache, sichere Darstellung)."""

    field: str
    value: Any = None
    evidence: Optional[str] = None  # kurzer source_text-Beleg


class VerificationDecision(BaseModel):
    """Entscheidung des Verifiers für EIN Feld."""

    field: str
    supported: bool = False
    reason: Optional[str] = None


class SensitiveVerificationResult(BaseModel):
    """Gesamtergebnis des Verifier-Durchlaufs."""

    model_config = {"extra": "forbid"}
    decisions: list[VerificationDecision] = Field(default_factory=list)


# Felder, die der Verifier prüfen soll
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
    "Nachweis/Text KONKRET GESTÜTZT ist. Du ERFINDEST KEINEN besseren Wert und änderst "
    "nichts – deine einzige Aufgabe ist supported (true/false) mit einer knappen deutschen Begründung.\n"
    "Regeln:\n"
    "- 'supported'=true nur, wenn der Wert wörtlich oder eindeutig aus dem zitierten "
    "Kontext ableitbar ist.\n"
    "- Bei Widerspruch zum zitierten Text, bei fehlender Stützung oder wenn der Nachweis "
    "den Wert nicht hergibt => supported=false.\n"
    "- Keine Raten von Monats-/Jahreswerten, keine Berechnung von Fristen/Daten.\n"
    "- Die Entscheidungsliste enthält GENAU die vorgegebenen Felder; jedes Feld genau einmal."
)


def _collect_sensitive_values(contract) -> list[SensitiveValue]:
    """Sammelt die sensiblen Werte + kurzen Beleg (evidence.source_text)."""
    out: list[SensitiveValue] = []

    def _ev(section) -> Optional[str]:
        ev = getattr(section, "evidence", None)
        if ev is None:
            return None
        return (ev.source_text or "")[:120] or None

    ident = contract.identity
    out.append(SensitiveValue(field="identity.contract_number",
                              value=getattr(ident, "contract_number", None),
                              evidence=(ident.evidence.source_text[:120] if ident.evidence else None)))

    d = contract.dates
    for f in ("start_date", "end_date", "duration", "minimum_duration"):
        v = getattr(d, f, None)
        out.append(SensitiveValue(field=f"dates.{f}", value=_fmt(v),
                                  evidence=(d.evidence.source_text[:120] if d.evidence else None)))

    t = contract.termination
    for f in ("cancellation_period", "automatic_renewal", "renewal_period"):
        v = getattr(t, f, None)
        out.append(SensitiveValue(field=f"termination.{f}", value=_fmt(v),
                                  evidence=(t.evidence.source_text[:120] if t.evidence else None)))

    c = contract.costs
    for f in ("annual_cost", "monthly_cost", "total_contract_value"):
        v = getattr(c, f, None)
        out.append(SensitiveValue(field=f"costs.{f}", value=_fmt(v),
                                  evidence=(c.evidence.source_text[:120] if c.evidence else None)))

    p = contract.payment
    out.append(SensitiveValue(field="payment.billing_interval",
                              value=getattr(p, "billing_interval", None),
                              evidence=(p.evidence.source_text[:120] if p.evidence else None)))
    return out


def _fmt(v) -> Any:
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "model_dump"):
        return v.model_dump()
    if isinstance(v, (ContractType, BillingInterval, TimeUnit)):
        return v.value
    return v


def _payload(sensitive: list[SensitiveValue], context: str) -> dict:
    import json

    values = json.loads(
        json.dumps([s.model_dump() for s in sensitive], ensure_ascii=False, default=str)
    )
    return {
        "sensitive_values": values,
        "context": context[:4000],
    }

async def run_verifier(
    ai_service: "AIService",
    contract,
    context: str,
    max_tokens: int = 1500,
) -> tuple[SensitiveVerificationResult, int]:
    """Führt den Semantik-Verifier aus.

    Liefert (Ergebnis, anzahl_verifier_calls). Bei Provider-/Parse-Fehler wird
    ein leeres Ergebnis zurückgegeben (Verifikation bricht nicht ab).
    """
    import json

    sensitive = _collect_sensitive_values(contract)
    sensitive = [s for s in sensitive if _is_sensitive_relevant(s)]
    if not sensitive:
        return SensitiveVerificationResult(), 0

    payload = json.dumps(_payload(sensitive, context), ensure_ascii=False)
    schema = pydantic_json_schema(SensitiveVerificationResult)

    try:
        raw = await ai_service.generate_structured(
            payload, VERIFIER_SYSTEM_PROMPT, schema, max_tokens=max_tokens
        )
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
    """Sensitive Werte ohne Extrahierung (None) müssen nicht verifiziert werden."""
    return s.value is not None


def unsupported_fields(result: SensitiveVerificationResult) -> set[str]:
    """Felder, die der Verifier NICHT als gestützt ansieht."""
    return {d.field for d in result.decisions if d.supported is False}
