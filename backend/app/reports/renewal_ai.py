"""Schritt 13a + §4A: Kurzfassung der Entscheidungsvorlage durch die lokale KI.

Die KI formuliert nur die vom Code berechneten Fakten um. Jede Zahl und jedes
Datum in der Antwort muss woertlich in den Fakten vorkommen; sonst wird die
Antwort verworfen (fail-closed) und die Vorlage bleibt ohne Fliesstext.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Optional

from app.ai.exceptions import AIProviderError
from app.ai.service import AIService

SYSTEM_PROMPT = (
    "Du bist ein Assistent für das Vertragsmanagement eines deutschen Krankenhauses. "
    "Fasse die folgenden FAKTEN in höchstens fünf kurzen deutschen Sätzen für eine Entscheidung "
    "vor der Kündigungsfrist zusammen. Verwende ausschließlich Zahlen, Beträge und Daten, die "
    "wörtlich in den FAKTEN stehen. Erfinde nichts, rechne nichts neu und triff keine Entscheidung; "
    "nenne die Optionen sachlich. Antworte nur mit dem Text, ohne Überschrift und ohne Aufzählung."
)

_NUMBER = re.compile(r"\d[\d.,]*")
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _de(value: Optional[str]) -> Optional[str]:
    return date.fromisoformat(value).strftime("%d.%m.%Y") if value else None


def _euro(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    amount = Decimal(value).quantize(Decimal("0.01"))
    return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def facts_text(brief: dict) -> str:
    lines = [
        f"Vertrag: {brief.get('register_number') or 'ohne Nummer'} – {brief.get('short_description') or ''}",
        f"Vertragspartner: {brief.get('partner') or 'nicht erfasst'}",
        f"Vertragsart: {brief.get('term_model') or 'nicht erfasst'}",
    ]
    if brief.get("cancel_by"):
        lines.append(f"Kündbar bis: {_de(brief['cancel_by'])} (noch {brief['days_left']} Tage)")
    if brief.get("current_end"):
        lines.append(f"Aktuelles Vertragsende: {_de(brief['current_end'])}")
    lines.append(f"Ohne Handeln: {brief['if_no_action']}")
    if brief.get("annual_cost"):
        lines.append(f"Jährliche Kosten (netto): {_euro(brief['annual_cost'])}")
    if brief.get("renewal_cost"):
        lines.append(f"Kosten bei Verlängerung bis {_de(brief['next_end_if_no_action'])} (netto): {_euro(brief['renewal_cost'])}")
    if brief.get("decision"):
        lines.append(f"Bereits erfasste Entscheidung: {brief['decision']['label']}")
    for hint in brief.get("hints", []):
        lines.append(f"Hinweis: {hint['text']}")
    return "\n".join(lines)


def _numbers(text: str) -> set[str]:
    return {match.rstrip(".,") for match in _NUMBER.findall(text) if match.rstrip(".,")}


def verify_against_facts(answer: str, facts: str) -> bool:
    """Jede Zahl der Antwort muss genau so in den Fakten stehen (fail-closed)."""
    return _numbers(answer) <= _numbers(facts)


async def summarize_brief(ai: AIService, brief: dict) -> dict:
    if not ai.configured:
        return {"available": False, "text": None, "message": "Kein lokales KI-Modell ausgewählt."}
    facts = facts_text(brief)
    try:
        raw = await ai.generate_text(f"FAKTEN:\n{facts}", SYSTEM_PROMPT, max_tokens=600)
    except AIProviderError as exc:
        return {"available": False, "text": None, "message": exc.user_message}
    answer = _THINK.sub("", raw or "").strip()
    if not answer:
        return {"available": False, "text": None, "message": "Die lokale KI hat keine Kurzfassung geliefert."}
    if not verify_against_facts(answer, facts):
        return {
            "available": False, "text": None,
            "message": "Die KI-Kurzfassung enthielt Zahlen, die nicht in den Fakten stehen, und wurde verworfen.",
        }
    return {"available": True, "text": answer, "message": None, "model": ai.active_model_id()}
