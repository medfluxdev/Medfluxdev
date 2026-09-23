"""Deterministische, provider-neutrale Normalisierung lokaler Label->Wert-Zusammenhaenge.

Kontext (STEP 8B Phase 3D): TableFormer erkennt auf Scans komplexe
Kosten-Tabellen oft nur teilweise. Fuer den Truebeam-Scan gilt belegt:
- table_p5_12 liefert Zell-basiert die Zeile `TrueBeam STx - H192469 -
  Essentials` mit 8 Jahreswerten (€99.000,00) -> strukturierte Beziehung OK.
- die kritischen Betraege `792.000,00` / `942.480,00` stehen als
  Fliesstext-Elemente AUSSERHALB der Tabelle; dort liess sich je Wert GENAU
  EIN Label in derselben y-Bande links daneben verifizieren.

Dieses Modul normalisiert NUR solche Zusammenhaenge deterministisch und
provider-neutral (geometriebasiert ueber y-Banden). Regeln, sonst KEINE
Beziehung und `review_required`:
- 0 oder >1 Kandidaten-Labels in derselben Bande -> nicht eindeutig.
- weitere Geld-Tokens in der Bande -> nicht eindeutig.
- Geld-Token mit verdaechtigem OCR-Muster (token_safety) -> nie normalisieren.
- KEINE supplier-spezifische Interpretation (z. B. "x9", "Jahr n").

Es gibt KEIN Raten: `normalized_amount` wird nur gesetzt, wenn der Wert
unmissverstaendlich deutsch normalisierbar ist.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.documents.intelligence.canonical import Element, TableStructure
from app.documents.intelligence.token_safety import classify_number_token, safe_normalize_money

TrustKind = Literal["structured_table", "geometry", "review_required"]

# Kandidaten fuer kritische Geldwerte: deutsche Tausender-Trennung (Punkt),
# Strichform, ODER verdaechtige Varianten (komma/doppelpunkt-Separatoren).
_MONEY_CANDIDATE_RE = re.compile(
    r"(?<!\w)(?:\d{1,3}(?:\.\d{3})+,\d{2}|\d{1,3}(?:\.\d{3})+,-"
    r"|\d{1,3},\d{3},\d{2}|\d{1,3}\.\d{3}\.\d{2})(?!\d)"
)


class LabelValueRelation(BaseModel):
    """Eine lokale, deterministisch belegbare Label->Wert-Beziehung."""

    label: str
    value_token: str
    page: int
    label_element_id: Optional[str] = None
    value_element_id: Optional[str] = None
    source_id: str = ""
    trust: TrustKind = "review_required"
    reason: str = ""
    label_region: Optional[dict] = None
    value_region: Optional[dict] = None
    normalized_amount: Optional[Decimal] = None


class RelationSet(BaseModel):
    """Alle lokal verifizierten Beziehungen eines Dokuments/Seitenbereichs."""

    relations: list[LabelValueRelation] = Field(default_factory=list)

    @property
    def review_count(self) -> int:
        return sum(1 for r in self.relations if r.trust == "review_required")

    def by_trust(self, trust: TrustKind) -> list[LabelValueRelation]:
        return [r for r in self.relations if r.trust == trust]


def _money_tokens(text: str) -> list[str]:
    return [m.group(0) for m in _MONEY_CANDIDATE_RE.finditer(text)]


def _is_suspicious_money_token(token: str) -> bool:
    return classify_number_token(token)[0] == "suspicious"


def _region_dict(region) -> Optional[dict]:
    if region is None:
        return None
    return {"page": region.page, "x0": region.x0, "y0": region.y0, "x1": region.x1, "y1": region.y1}


def _amount_from_token(token: str) -> Optional[Decimal]:
    m = safe_normalize_money(token)
    return m.amount if m.ok else None


# ------------------------------------------------------------------ Tabellen

def scan_table_relations(table: TableStructure, *, max_label_col: int = 0) -> RelationSet:
    """Beziehungen aus echten Tabellenzellen (Label links, Werte rechts).

    Kein Raten: Werte mit verdaechtigem OCR-Muster werden als
    `review_required` gemeldet und nie normalisiert.
    """
    result = RelationSet()
    for row in range(table.num_rows):
        cells = [table.cell(row, c) for c in range(table.num_cols)]
        nonempty = [c for c in cells if c and (c.text or "").strip()]
        if not nonempty:
            continue
        label_cell = next((c for c in nonempty if c.text.strip() and _money_tokens(c.text) == []), None)
        if label_cell is None:
            continue
        label = " ".join(label_cell.text.split())
        for col in range(table.num_cols):
            c = table.cell(row, col)
            if c is None or c is label_cell:
                continue
            for tok in _money_tokens(c.text):
                suspicious = _is_suspicious_money_token(tok)
                result.relations.append(
                    LabelValueRelation(
                        label=label,
                        value_token=tok,
                        page=table.page,
                        source_id=f"{table.table_id}:r{row}c{col}",
                        trust="review_required" if suspicious else "structured_table",
                        reason="suspicious_ocr_token" if suspicious else "structured_table_cell",
                        label_region=_region_dict(label_cell.region),
                        value_region=_region_dict(c.region),
                        normalized_amount=None if suspicious else _amount_from_token(tok),
                    )
                )
    return result


# ------------------------------------------------------------------ Geometrie

def _band_hits(e: Element, others: list[Element], overlap: float) -> tuple[list[Element], list[Element]]:
    """Liefert (labels_links, geld_links) fuer ein Geld-Element in derselben y-Bande."""
    if e.region is None:
        return [], []
    y0, y1 = e.region.y0, e.region.y1
    labels: list[Element] = []
    money: list[Element] = []
    for o in others:
        if o.region is None or o is e:
            continue
        if o.region.x1 <= e.region.x0:
            inter = max(0.0, min(y1, o.region.y1) - max(y0, o.region.y0))
            band_h = max(0.001, min(y1 - y0, o.region.y1 - o.region.y0))
            if inter / band_h < overlap:
                continue
            if _money_tokens(o.text):
                money.append(o)
            elif (o.text or "").strip():
                labels.append(o)
    return labels, money


def scan_geometry_relations(elements: list[Element], *, y_overlap: float = 0.5) -> RelationSet:
    """Beziehungen der Form `Label | Wert` (Wert rechts vom Label, gleiche y-Bande).

    Bedingungen fuer `trust="geometry"`:
    - genau EIN Label links in derselben Bande
    - kein weiteres Geld-Element in derselben Bande
    - Wert selbst unverdaechtig (sonst review_required)
    Tabellen-Elemente werden uebersprungen (dort gilt scan_table_relations).
    """
    result = RelationSet()
    money_elems = [
        e for e in elements if e.region is not None and e.type.value != "table" and _money_tokens(e.text)
    ]
    for e in money_elems:
        labels, money_in_band = _band_hits(e, elements, y_overlap)
        for tok in _money_tokens(e.text):
            suspicious = _is_suspicious_money_token(tok)
            if suspicious:
                result.relations.append(
                    LabelValueRelation(
                        label=" ".join(labels[0].text.split()) if len(labels) == 1 else "",
                        value_token=tok,
                        page=e.page,
                        label_element_id=labels[0].element_id if len(labels) == 1 else None,
                        value_element_id=e.element_id,
                        source_id=f"geometry:{e.element_id}",
                        trust="review_required",
                        reason="suspicious_ocr_token",
                        label_region=_region_dict(labels[0].region) if len(labels) == 1 else None,
                        value_region=_region_dict(e.region),
                        normalized_amount=None,
                    )
                )
            elif len(labels) == 1 and not money_in_band:
                result.relations.append(
                    LabelValueRelation(
                        label=" ".join(labels[0].text.split()),
                        value_token=tok,
                        page=e.page,
                        label_element_id=labels[0].element_id,
                        value_element_id=e.element_id,
                        source_id=f"geometry:{e.element_id}",
                        trust="geometry",
                        reason="same_band_label_left",
                        label_region=_region_dict(labels[0].region),
                        value_region=_region_dict(e.region),
                        normalized_amount=_amount_from_token(tok),
                    )
                )
            elif len(labels) == 0:
                result.relations.append(
                    LabelValueRelation(
                        label="",
                        value_token=tok,
                        page=e.page,
                        value_element_id=e.element_id,
                        source_id=f"geometry:{e.element_id}",
                        trust="review_required",
                        reason="0_labels_in_band",
                        value_region=_region_dict(e.region),
                    )
                )
            else:
                result.relations.append(
                    LabelValueRelation(
                        label="",
                        value_token=tok,
                        page=e.page,
                        value_element_id=e.element_id,
                        source_id=f"geometry:{e.element_id}",
                        trust="review_required",
                        reason="multiple_labels_in_band",
                        value_region=_region_dict(e.region),
                    )
                )
    return result