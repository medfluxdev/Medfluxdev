"""Abbildung der KI-Extraktion auf Registerfelder (Vorschlaege, deterministisch).

Nur Werte, die die Extraktion explizit liefert, werden uebernommen. Die
Vertragsart wird aus strukturierten Fakten abgeleitet; der Kuendigungsstichtag
nur aus einer eindeutigen Formulierung der Kuendigungsbedingung. Mehrdeutiges
bleibt leer ("nicht gefunden") und geht in die Pruefung.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from app.contracts.calculation.dates import group_cancellation_relation
from app.models.contract import Contract as ExtractedContract
from app.models.values import Duration


@dataclass(frozen=True)
class Proposal:
    value: Any
    source_field: str


_NOTICE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("quarter_end", re.compile(r"(quartal|vierteljahr)", re.IGNORECASE)),
    ("half_year_end", re.compile(r"(halbjahr|halben jahres)", re.IGNORECASE)),
    ("year_end", re.compile(r"((?<!halb)jahresende|kalenderjahr|ende (eines|des) (jeweiligen )?jahres|zum jahresschluss)", re.IGNORECASE)),
    ("month_end", re.compile(r"(monatsende|ende (eines|des) (jeweiligen )?(kalender)?monats)", re.IGNORECASE)),
)


def notice_target_from_text(text: Optional[str]) -> Optional[str]:
    """Eindeutiger Kalenderstichtag aus Freitext; bei mehreren Treffern None."""
    if not text or not text.strip():
        return None
    hits = [target for target, pattern in _NOTICE_PATTERNS if pattern.search(text)]
    if len(hits) != 1:
        return None
    return hits[0]


def _duration(value: Optional[Duration]) -> Optional[tuple[int, str]]:
    if value is None or value.value is None or value.unit is None:
        return None
    unit = getattr(value.unit, "value", value.unit)
    if unit not in ("days", "weeks", "months", "years"):
        return None
    return int(value.value), unit


def _date(flexible) -> Any:
    return getattr(flexible, "date", None) if flexible is not None else None


def proposals_from_extraction(contract: ExtractedContract) -> dict[str, Proposal]:
    out: dict[str, Proposal] = {}
    identity, dates, termination = contract.identity, contract.dates, contract.termination

    if identity.contract_title and identity.contract_title.strip():
        out["short_description"] = Proposal(identity.contract_title.strip()[:500], "identity.contract_title")

    start = _date(dates.start_date)
    if start is not None:
        out["term_start_date"] = Proposal(start, "dates.start_date")
    end = _date(dates.end_date)
    if end is not None:
        out["term_fixed_end_date"] = Proposal(end, "dates.end_date")

    for prefix, source, value in (
        ("initial_term", "dates.duration", dates.duration),
        ("minimum_term", "dates.minimum_duration", dates.minimum_duration),
        ("notice_period", "termination.cancellation_period", termination.cancellation_period),
        ("renewal_period", "termination.renewal_period", termination.renewal_period),
    ):
        parsed = _duration(value)
        if parsed is not None:
            out[f"{prefix}_value"] = Proposal(parsed[0], source)
            out[f"{prefix}_unit"] = Proposal(parsed[1], source)

    relation = group_cancellation_relation(contract)
    notice_to: Optional[str] = None
    if relation == "to_contract_end":
        notice_to = "contract_end"
        out["notice_to"] = Proposal(notice_to, "termination.cancellation_to_contract_end")
    else:
        notice_to = notice_target_from_text(termination.cancellation_condition)
        if notice_to is not None:
            out["notice_to"] = Proposal(notice_to, "termination.cancellation_condition")

    has_notice = "notice_period_value" in out
    has_end = "term_fixed_end_date" in out or "initial_term_value" in out
    term_model: Optional[str] = None
    if termination.automatic_renewal is True and has_end:
        term_model = "auto_renewal"
    elif termination.automatic_renewal is False and has_end and notice_to in (None, "contract_end"):
        term_model = "fixed_term"
    elif has_notice and notice_to not in (None, "contract_end"):
        term_model = "terminable_min_term" if "minimum_term_value" in out else "terminable"
    if term_model is not None:
        out["term_model"] = Proposal(term_model, "termination")
    return out
