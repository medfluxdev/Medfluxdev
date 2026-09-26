from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.harness.document import Block, DocumentModel


_DATE_RE = re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])[./-](?:0?[1-9]|1[0-2])[./-](?:19|20)\d{2}\b")
# Lokale Währungszeichen können vor oder hinter dem Betrag stehen; Scans schreiben
# "€ 12.000,00" ebenso wie "12.000,00 EUR".  Beide Formen sind ein Geld-Signal.
_MONEY_RE = re.compile(
    r"(?<!\w)(?:(?:€|EUR)\s*)?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d{2})?\s*(?:€|EUR)(?!\w)"
    r"|(?<!\w)(?:€|EUR)\s*(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d{2})?(?!\w)",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(
    r"\b\d+\s*(?:Jahr(?:e|en)?|Monat(?:e|en)?|Woche(?:n)?|Tag(?:e|en)?)\b",
    re.IGNORECASE,
)
_CONTRACT_NUMBER_RE = re.compile(
    r"\b(?:Vertr\.?-?Nr\.?|Vertragsnummer|Vertrag\s*Nr\.?)\s*[:#]?\s*([A-Z0-9][A-Z0-9._/-]{2,})",
    re.IGNORECASE,
)
_RENEWAL_NEGATION_RE = re.compile(
    r"\b(?:nicht|keine)\b.{0,48}\b(?:automatisch\w*|verlänger\w*)\b|"
    r"\b(?:automatisch\w*|verlänger\w*)\b.{0,48}\b(?:nicht|keine)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceSignal:
    kind: str
    value: str
    block_id: str
    page: int | None
    quote: str

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "value": self.value,
            "block_id": self.block_id,
            "page": self.page,
            "quote": self.quote,
        }


def _snippet(text: str, start: int, end: int, radius: int = 72) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())


def _matches(block: Block) -> list[SourceSignal]:
    text = block.text or ""
    if not text:
        return []
    rows: list[SourceSignal] = []
    for kind, pattern in (
        ("date", _DATE_RE),
        ("money", _MONEY_RE),
        ("duration", _DURATION_RE),
    ):
        for match in pattern.finditer(text):
            rows.append(
                SourceSignal(
                    kind=kind,
                    value=match.group(0),
                    block_id=block.id,
                    page=block.page,
                    quote=_snippet(text, match.start(), match.end()),
                )
            )

    for match in _CONTRACT_NUMBER_RE.finditer(text):
        rows.append(
            SourceSignal(
                kind="labelled_contract_number",
                value=match.group(1),
                block_id=block.id,
                page=block.page,
                quote=_snippet(text, match.start(), match.end()),
            )
        )

    for match in _RENEWAL_NEGATION_RE.finditer(text):
        rows.append(
            SourceSignal(
                kind="renewal_negation",
                value=match.group(0),
                block_id=block.id,
                page=block.page,
                quote=_snippet(text, match.start(), match.end()),
            )
        )
    return rows


def collect_source_signals(document: DocumentModel, *, limit: int = 160) -> list[dict]:
    """Collect literal OCR/native signals without deciding contract semantics.

    This is a perception aid, not a fact extractor: values remain tied to the
    exact source block and Qwen still decides their contractual role.
    """
    rows: list[SourceSignal] = []
    seen: set[tuple[str, str, str]] = set()
    for block in document.blocks:
        for item in _matches(block):
            key = (item.kind, item.value, item.block_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
            if len(rows) >= limit:
                return [row.as_dict() for row in rows]
    return [row.as_dict() for row in rows]
