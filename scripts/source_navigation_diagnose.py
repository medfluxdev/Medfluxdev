"""STEP 8B Gate D – fokussierte Diagnostik: Text-Span → Prov-Item → BBox-Zuordnung.

NUR Diagnose auf Basis der gecachten kanonischen Ergebnisse + Original-PDFs
(inspiziert: Tinte vorhanden? Seiten-Texte in Lesereihenfolge vs. BBox-y-Ordnung).
KEINE Korrektur, kein Docling-Refresh, kein Qwen, keine Benchmark.

Schluessel-Invariante (laut Auftrag): ein BBox-Kandidat darf nur verwendet
werden, wenn der zugehoerige Text das Ziel enthaelt. Diese Diagnose prueft das
auf zwei Ebenen:
  A) KANONISCH: enthaelt der dem BBox zugeordnete segment/element-Text das Ziel?
     (basiert auf der identischen (text,bbox)-Paarung, die wir rendern)
  B) VISUELL: liegt an der BBox-Position im Original-PDF ueberhaupt Tinte?
     (dunkle Pixel im sauberen Pixmap, ohne Overlays)
Plus Ordnungs-Kennzahl je Seite: Ist die BBox-y-Folge monoton zu der
Text-/Element-Reihenfolge? (Nicht-Monotonie / Richtungs-Wechsel = Text- und
BBox-Folge beim Provider nicht synchron.)

Ergebnis je Ziel ehrlich: INVARIANT_CANONICAL_PASS/FAIL + BBOX_INK_PRESENT + PAGE_ORDER.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.documents.intelligence.canonical import BoundingRegion, DocumentIntelligenceResult
from app.documents.intelligence.highlight import medibox_to_view

BASE = ROOT / "data" / "benchmark_v2"
INPUT = BASE / "input"
REPORTS = BASE / "di_reports"

DATE_MONTH_RE = None  # nicht benoetigt: alle Ziele sind literal

TARGETS = {
    "Vision RFD 3D": {"file": "Vision RFD 3D.pdf", "targets": ["13.06.2017", "13.115,00"]},
    "GE MACLAB": {"file": "GE MACLAB.pdf", "targets": ["3.429,-"]},
    "Truebeam STX": {"file": "Truebeam STX.PDF", "targets": ["942.480,00", "Kündigungsfrist"]},
}


def load(name: str) -> DocumentIntelligenceResult:
    return DocumentIntelligenceResult.model_validate_json(
        (REPORTS / f"{name}.canonical.json").read_text(encoding="utf-8")
    )


def ink_fraction(page, x0, y0, x1, y1, pix, scale):
    xs0 = max(0, int(x0 * scale)); ys0 = max(0, int(y0 * scale))
    xs1 = min(pix.width, int(x1 * scale)); ys1 = min(pix.height, int(y1 * scale))
    if xs1 - xs0 < 3 or ys1 - ys0 < 3:
        return -1.0
    dark = tot = 0
    for y in range(ys0, ys1):
        for x in range(xs0, xs1):
            r, g, b = pix.pixel(x, y)
            tot += 1
            if 0.299 * r + 0.587 * g + 0.114 * b < 128:
                dark += 1
    return dark / tot


def page_order_metrics(page) -> dict:
    ys = [float(e.region.y0) for e in page.elements if e.region and e.text.strip()]
    inversions = sum(1 for k in range(len(ys) - 1) if ys[k] > ys[k + 1])
    dirs = [1 if ys[k + 1] > ys[k] else -1 for k in range(len(ys) - 1)]
    flips = sum(1 for k in range(1, len(dirs)) if dirs[k] != dirs[k - 1])
    return {
        "text_items": len(ys),
        "y_inversions": inversions,
        "direction_flips": flips,
        "y_monotonic_with_text_order": flips == 0,
    }


def main() -> int:
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "DIAGNOSTIC_ONLY_NO_FIX",
        "note": "Kanonische Invarianz (text enthaelt ziel) wird getrennt von visueller "
                "Plaes_Invaliditaet (Tinte an bbox) berichtet. Keine Hardware-Änderung.",
        "contracts": {},
    }
    for name, cfg in TARGETS.items():
        result = load(name)
        pdf_path = INPUT / cfg["file"]
        entries = []
        doc = fitz.open(pdf_path)
        try:
            for token in cfg["targets"]:
                low = token.lower()
                entry = {"target": token, "found": False,
                         "invariant_canonical_pass": False, "bbox_ink_present": False}
                found_page = None
                for page in result.pages:
                    idx = page.text.lower().find(low)
                    if idx >= 0:
                        found_page = page
                        entry["page_number"] = page.page_number
                        entry["canonical_start"] = idx
                        entry["canonical_end"] = idx + len(token)
                        ctx = page.text[max(0, idx - 100): idx + len(token) + 100]
                        entry["context_around_100"] = ctx
                        break
                if found_page is None:
                    entries.append(entry)
                    continue
                page = found_page
                entry["found"] = True
                entry["page_order"] = page_order_metrics(page)
                # A) KANONISCHE KANDIDATEN: alle word_regions / Elemente, deren
                #    Text das Ziel enthaelt (die Paarung, die wir rendern wuerden)
                candidates = []
                for e in page.elements:
                    for wr in e.word_regions:
                        if token.lower() in (wr.text or "").lower():
                            candidates.append({
                                "source": "word_region",
                                "element_id": e.element_id,
                                "element_type": e.type,
                                "element_is_table": e.table is not None,
                                "text": wr.text,
                                "offset": wr.offset,
                                "length": wr.length,
                                "granularity": wr.granularity,
                                "bbox": wr.region.model_dump() if wr.region else None,
                            })
                    if token.lower() in (e.text or "").lower() and not any(
                        c["element_id"] == e.element_id for c in candidates
                    ):
                        candidates.append({
                            "source": "element_only",
                            "element_id": e.element_id,
                            "element_type": e.type,
                            "element_is_table": e.table is not None,
                            "text": e.text,
                            "offset": e.spans[0].offset if e.spans else None,
                            "length": e.spans[0].length if e.spans else None,
                            "granularity": "element",
                            "bbox": e.region.model_dump() if e.region else None,
                        })
                entry["candidates"] = candidates
                entry["invariant_canonical_pass"] = len(candidates) > 0

                # B) VISUELL: Tinte an der gerenderten BBox (Original-Seite, sauber)
                ink_box = -1.0
                if candidates and candidates[0]["bbox"]:
                    reg = BoundingRegion(**candidates[0]["bbox"])
                    pdf = doc.load_page(page.page_number - 1)
                    rot = pdf.rotation
                    med = pdf.mediabox
                    view_w = med.height if rot in (90, 270) else med.width
                    view_h = med.width if rot in (90, 270) else med.height
                    v = medibox_to_view(reg, rot, view_w=float(view_w), view_h=float(view_h))
                    pix = pdf.get_pixmap(dpi=160)
                    scale = 160.0 / 72.0
                    # Nur Innere (25% Rand weggelassen, um Outline/Schriftraender zu meiden)
                    w = v.x1 - v.x0
                    h = v.y1 - v.y0
                    ink_box = ink_fraction(pdf, v.x0 + 0.25 * w, v.y0 + 0.25 * h,
                                           v.x1 - 0.25 * w, v.y1 - 0.25 * h, pix, scale)
                    entry["bbox_view_pt"] = [round(v.x0, 1), round(v.y0, 1), round(v.x1, 1), round(v.y1, 1)]
                    entry["bbox_ink_fraction"] = round(ink_box, 3)
                    entry["bbox_ink_present"] = ink_box > 0.01
                entries.append(entry)
        finally:
            doc.close()
        report["contracts"][name] = {"source": cfg["file"], "targets": entries}

    out = REPORTS / "source_navigation_diagnosis.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Diagnose geschrieben: {out}\n")
    for name, c in report["contracts"].items():
        for t in c["targets"]:
            cand = t.get("candidates") or []
            best = cand[0] if cand else {}
            print(f"[{name}] target={t['target']!r} page={t.get('page_number')} found={t['found']}")
            print(f"    canonical span {t.get('canonical_start')}..{t.get('canonical_end')}")
            print(f"    context: ...{t.get('context_around_100','')!r}...")
            if cand:
                print(f"    selected: {best['source']} {best['granularity']} elem={best['element_id']} "
                      f"(table={best['element_is_table']}) text_tail={best['text'][-45:]!r} bbox={best['bbox']}")
            print(f"    INVARIANT_CANONICAL(text_contains_target)={t['invariant_canonical_pass']} | "
                  f"BBOX_INK={t.get('bbox_ink_present')} ({t.get('bbox_ink_fraction')}) | "
                  f"PAGE_ORDER1 {t.get('page_order')}")
            print(f"    nearby_candidates={len(cand)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())