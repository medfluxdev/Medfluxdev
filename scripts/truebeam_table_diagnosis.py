"""STEP 8B Phase 3D – Diagnose der komplexen Kosten-/Jahrestabelle im Truebeam-Scan.

Nur Analyse (kein Refresh): laedt das gecachte `<contract>.canonical.json` und
untersucht, wie Docling die komplexe Tabelle ("Jährlich ...9 Jahre") wirklich
abgebildet hat – Zellen vs. lineare Lesereihenfolge, und ob eine DETERMINISTISCHE,
provider-neutrale geometrie-basierte Beziehung (Label->Wert in derselben
Zeilen-Bande) rekonstruierbar ist. Ergebnis fliess in die Gate-Entscheidung
und entscheidet, ob ein kleiner table_normalize-Helfer gebaut wird oder
nur "manual review" fuer die betroffenen Betraege gemeldet wird.

Grundregel (STEP 8B): NIE einen Label->Wert-Bezug aus entfernter linearer
Lesereihenfolge "erfinden"; keine supplier-spezifischen Regeln (z. B. "×9").

Nutzung:  python scripts/truebeam_table_diagnosis.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.documents.intelligence.canonical import Cell, DocumentIntelligenceResult, Element

REPORTS = ROOT / "data" / "benchmark_v2" / "di_reports"
CONTRACT = "Truebeam STX"

_KEY_TOKENS = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}|\d{1,3}(?:\.\d{3})+,-|H192469|[Aa]nnual|[Jj]ähr|[Mm]onatlich|[Ss]tundensatz")


def load_result() -> Optional[DocumentIntelligenceResult]:
    path = REPORTS / f"{CONTRACT}.canonical.json"
    if not path.exists():
        return None
    return DocumentIntelligenceResult.model_validate_json(path.read_text(encoding="utf-8"))


def _b(r, what: str) -> dict:
    if r is None:
        return {"page": None}
    return {"page": r.page, "x0": round(r.x0, 1), "y0": round(r.y0, 1), "x1": round(r.x1, 1), "y1": round(r.y1, 1), "mid_y": round((r.y0 + r.y1) / 2, 1)}


def describe_table(t) -> dict:
    grid = t.row_texts()
    return {
        "table_id": t.table_id,
        "page": t.page,
        "dims": [t.num_rows, t.num_cols],
        "cells_captured": len(t.cells),
        "headers": t.headers,
        "region": _b(t.region, "table"),
        "rows_preview": [row for row in grid[:10]],
        "all_money_in_cells": [
            {"row": c.row_index, "col": c.column_index, "text": c.text, "region": _b(c.region, "cell")}
            for c in t.cells
            if c.text and re.search(r"\d", c.text)
        ][:40],
    }


def elements_around(result, page_no: int, tokens: list[str]) -> list[dict]:
    """Alle Elemente auf der Seite, die an den Tokens interessieren."""
    out = []
    page = result.page(page_no)
    if page is None:
        return out
    for e in page.elements:
        if e.type.value == "table":
            continue
        hits = [tok for tok in tokens if tok.lower() in e.text.lower()]
        if hits:
            out.append({
                "element_id": e.element_id,
                "ro": e.reading_order,
                "type": e.type.value,
                "method": e.method.value,
                "text": e.text,
                "region": _b(e.region, "el"),
                "hits": hits,
            })
    return out


def money_tokens_in_element(e: Element) -> list[str]:
    return [m.group(0) for m in re.finditer(r"\d{1,3}(?:\.\d{3})+,\d{2}|\d{1,3}(?:\.\d{3})+,-", e.text)]


def geometry_proposal(page_elements: list[Element]):
    """Versucht deterministisch: Geld-Token -> Label in derselben y-Bande.

    Nur ELEMENT-Ebene (kein Word-Splitting). Rueckgabe mit Provenienz;
    'ok' heisst: fuer jedes Geld-Token genau EIN Label links/rechts in derselben
    Bande (nach y-Overlap), und keine Kollision.
    """
    elems = [e for e in page_elements if e.region is not None and e.text.strip()]
    proposals = []
    for e in elems:
        for tok in money_tokens_in_element(e):
            if re.search(r"(?:\d,\d{3},\d{2}|\d\.\d\.\d{2})", tok):
                proposals.append({"token": tok, "element_id": e.element_id, "suspicious": True, "proposal": None, "reason": "suspicious_ocr_token"})
                continue
            same_band = []
            y0, y1 = e.region.y0, e.region.y1
            for o in elems:
                if o.element_id == e.element_id:
                    continue
                overlap = max(0.0, min(y1, o.region.y1) - max(y0, o.region.y0))
                band_h = max(0.001, min(y1 - y0, o.region.y1 - o.region.y0))
                if overlap / band_h >= 0.5:
                    same_band.append(o)
            labels = [o for o in same_band if o.region.x1 <= e.region.x0 and not money_tokens_in_element(o)]
            if len(labels) == 1:
                proposals.append({
                    "token": tok,
                    "element_id": e.element_id,
                    "suspicious": False,
                    "proposal": labels[0].text,
                    "proposal_element": labels[0].element_id,
                    "reason": "same_band_label_left",
                    "proposal_region": _b(labels[0].region, "label"),
                })
            else:
                proposals.append({
                    "token": tok,
                    "element_id": e.element_id,
                    "suspicious": False,
                    "proposal": None,
                    "reason": f"{len(labels)}_labels_ambiguous",
                })
    return proposals


def main() -> int:
    result = load_result()
    if result is None:
        print(f"Kein Cache fuer {CONTRACT}: zunaechst document_intelligence_diagnosis.py --refresh ausfuehren")
        return 2

    report: dict = {"contract": CONTRACT, "source": result.source_filename}
    report["warnings_subset"] = result.warnings[:12]

    tables = [describe_table(t) for t in result.all_tables()]
    report["tables"] = tables

    # Suchen wir die kritischen Werte in ELEMENT-Zeilen (nicht Tabellenzellen)
    money_elements: list[dict] = []
    for page in result.pages:
        for e in page.elements:
            toks = money_tokens_in_element(e)
            if toks:
                money_elements.append({
                    "page": page.page_number,
                    "element_id": e.element_id,
                    "ro": e.reading_order,
                    "text": e.text[:200],
                    "tokens": toks,
                    "region": _b(e.region, "el"),
                })

    report["money_elements_total"] = len(money_elements)
    report["money_elements"] = money_elements[:60]

    # Geometrie-Proposal auf den wichtigsten Seiten
    for page_no in sorted({m["page"] for m in money_elements}):
        page = result.page(page_no)
        if page is None:
            continue
        report.setdefault("geometry_proposals", {})[f"p{page_no}"] = geometry_proposal(page.elements)

    out_path = REPORTS / "truebeam_table_diagnosis.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Truebeam-Tabellendiagnose geschrieben: {out_path}")
    for t in tables:
        print(f"  {t['table_id']} p{t['page']} dims={t['dims']} cells={t['cells_captured']} rows_preview_count={len(t['rows_preview'])}")
    suspicious = [m for m in report.get("geometry_proposals", {}).values() for p in m if p.get("suspicious") or not p.get("proposal")]
    print(f"  Geld-Elemente gesamt: {report['money_elements_total']} | nicht sicher zuordenbare relationen: {len(suspicious)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())