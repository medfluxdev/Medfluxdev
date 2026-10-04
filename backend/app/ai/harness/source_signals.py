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
_MONEY_NUMBER_RE = re.compile(r"(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d{2})?")
_DURATION_RE = re.compile(
    r"\b\d+\s*(?:Jahr(?:e|en)?|Monat(?:e|en)?|Woche(?:n)?|Tag(?:e|en)?)\b",
    re.IGNORECASE,
)
_CONTRACT_NUMBER_RE = re.compile(
    r"\b(?:Vertr\.?-?Nr\.?|Vertragsnummer|Vertrag\s*Nr\.?|Rahmenvertrag(?:s)?\s*Nr\.?)\s*[:#]?\s*([A-Z0-9][A-Z0-9._/-]{2,})",
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
    source_context: dict | None = None

    def as_dict(self) -> dict:
        result = {
            "kind": self.kind,
            "value": self.value,
            "block_id": self.block_id,
            "page": self.page,
            "quote": self.quote,
        }
        if self.source_context:
            result["source_context"] = self.source_context
        return result


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


def _table_money_signals(document: DocumentModel) -> list[SourceSignal]:
    """Bind numeric table cells to an explicit currency/period column header.

    The exact row stays the evidence quote. Header context is carried separately
    so downstream validation can require the same table and column.
    """
    rows: list[SourceSignal] = []
    for block in document.blocks:
        table = getattr(getattr(block, "element", None), "table", None)
        if table is None:
            continue
        headers: dict[int, str] = {}
        for cell in table.cells:
            if cell.row_index == 0 and cell.text.strip():
                headers[cell.column_index] = cell.text.strip()
        for cell in table.cells:
            if cell.row_index == 0 or not cell.text.strip():
                continue
            header = headers.get(cell.column_index, "")
            currency = re.search(r"\b(EUR|USD|GBP)\b|€|\$|£", header, re.IGNORECASE)
            if not currency or not _MONEY_NUMBER_RE.fullmatch(cell.text.strip()):
                continue
            currency_text = currency.group(0).upper()
            currency_text = {"€": "EUR", "$": "USD", "£": "GBP"}.get(currency_text, currency_text)
            period = header
            row_cells = sorted(
                (candidate for candidate in table.cells if candidate.row_index == cell.row_index),
                key=lambda candidate: candidate.column_index,
            )
            quote = " | ".join(candidate.text.strip() for candidate in row_cells if candidate.text.strip())
            if not quote:
                continue
            rows.append(
                SourceSignal(
                    kind="money",
                    value=f"{cell.text.strip()} {currency_text}",
                    block_id=block.id,
                    page=block.page,
                    quote=quote,
                    source_context={
                        "type": "table_column",
                        "table_id": table.table_id,
                        "row_index": cell.row_index,
                        "column_index": cell.column_index,
                        "header": period,
                    },
                )
            )
    return rows


def collect_source_signals(document: DocumentModel, *, limit: int = 160) -> list[dict]:
    """Collect literal OCR/native signals without deciding contract semantics.

    This is a perception aid, not a fact extractor: values remain tied to the
    exact source block and Qwen still decides their contractual role.
    """
    rows: list[SourceSignal] = []
    seen: set[tuple[str, str, str, str]] = set()
    table_signals = _table_money_signals(document)
    for item in table_signals:
        key = (item.kind, item.value, item.block_id, item.quote)
        seen.add(key)
        rows.append(item)
    for block in document.blocks:
        for item in _matches(block):
            key = (item.kind, item.value, item.block_id, item.quote)
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
    money_signals = [row for row in rows if row.kind == "money"]
    rows = money_signals + [row for row in rows if row.kind != "money"]
    return [row.as_dict() for row in rows[:limit]]
