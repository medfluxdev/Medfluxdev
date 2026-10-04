"""STEP 8B Korrektur (Gate D) – Quell-Navigation auf ATOMARER OCR-Geometrie.

Nutzt die gecachten kanonischen Ergebnisse (inkl. atomic_units aus
scripts/atomic_geometry_augment.py) + Original-PDF fuer Renders. Fuer jedes
der 6 Quell-Navigations-Ziele:
- Aufloesung ueber `resolve_target_atomic` (EXACT_WORD / VALIDATED_TABLE_CELL /
  EXACT_LINE / COARSE_FALLBACK / TARGET_NOT_FOUND) – Containment-bewiesen
  an der atomaren OCR-Geometrie (RapidOCR-Wort/-Zeile bzw. validierte
  Docling-Tabellenzelle). Grobe Element-Boxen erscheinen NUR als ehrlicher
  Fallback, nie still als exakt.
- Transformations-Reportfelder je Ziel: page, target, Quelle-OCR-Unit(s),
  Geometrie-Precision, Boxen (View + MediaBox), Confidence, Alignment-Methode,
  Anomalie-Signale, Render-Datei.

Programmatische Geometrie-Pruefung UND visuelle Bestaetigung sind getrennt:
VISUAL HUMAN VERIFICATION PENDING. Gate bleibt D bis menschliche Bestaetigung.

Nutzung:  python scripts/source_navigation_diagnostics.py
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.documents.intelligence.canonical import (  # noqa: E402
    BoundingRegion,
    DocumentIntelligenceResult,
    Page,
)
from app.documents.intelligence.highlight import (  # noqa: E402
    AtomicResolution,
    page_view_to_mediabox,
    render_transparent_boxes,
    resolve_target_atomic,
)

BASE = ROOT / "data" / "benchmark_v2"
INPUT = BASE / "input"
REPORTS = BASE / "di_reports"
HIGHLIGHTS_ATOMIC = REPORTS / "highlights_atomic"
MANIFEST = REPORTS / "source_navigation_atomic.json"

EXACT_STATUSES = {"EXACT_WORD", "VALIDATED_TABLE_CELL", "EXACT_LINE"}

DATE_MONTH_RE = re.compile(
    r"\d{1,2}\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*\d{2,4}",
    re.I,
)

TARGETS = {
    "Vision RFD 3D": {
        "file": "Vision RFD 3D.pdf",
        "targets": [
            {"kind": "word", "token": "13.06.2017", "label": "datum"},
            {"kind": "word", "token": "13.115,00", "label": "betrag"},
        ],
    },
    "GE MACLAB": {
        "file": "GE MACLAB.pdf",
        "targets": [
            {"kind": "word", "token": "$DATE_MONTH", "label": "datum"},
            {"kind": "word", "token": "3.429,-", "label": "betrag"},
        ],
    },
    "Truebeam STX": {
        "file": "Truebeam STX.PDF",
        "targets": [
            {"kind": "word", "token": "942.480,00", "label": "betrag"},
            {"kind": "phrase", "token": "Kündigungsfrist", "label": "phrase_kuendigung"},
        ],
    },
}


def load(name: str) -> DocumentIntelligenceResult:
    path = REPORTS / f"{name}.canonical.json"
    return DocumentIntelligenceResult.model_validate_json(path.read_text(encoding="utf-8"))


def locate_span(result: DocumentIntelligenceResult, token: str) -> tuple[Optional[Page], int]:
    """Erste exakte Vorkommnis-Position in den kanonischen Seiten-Texten."""
    low = token.lower()
    for page in result.pages:
        off = page.text.lower().find(low)
        if off >= 0:
            return page, off
    return None, -1


def _regiondict(r: BoundingRegion) -> dict:
    return {"page": r.page, "x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1}


def _unitdata(u) -> dict:
    return {
        "unit_id": u.unit_id,
        "kind": u.kind,
        "text": u.text,
        "precision": u.precision.value,
        "confidence": u.confidence,
        "aligned": u.aligned,
        "canonical_offset": u.canonical_offset,
        "canonical_length": u.canonical_length,
    }


def _box_signals(boxes: list[BoundingRegion], page_w: float, page_h: float) -> dict:
    """Anomalie-Signale (NUR informativ, kein Universal-Gate)."""
    infos = []
    for b in boxes:
        infos.append(
            {
                "in_bounds": b.x0 >= 0 and b.y0 >= 0 and b.x1 <= page_w and b.y1 <= page_h,
                "whole_page_width": b.width > 0.9 * page_w if page_w else False,
                "height_pt": round(b.height, 2),
            }
        )
    return {
        "boxes_out_of_bounds": sum(1 for i in infos if not i["in_bounds"]),
        "boxes_whole_page_width": sum(1 for i in infos if i["whole_page_width"]),
        "max_box_height_pt": max((i["height_pt"] for i in infos), default=0.0),
    }


def _resolve_entry(page: Page, offset: int, token: str) -> tuple[AtomicResolution, dict]:
    res = resolve_target_atomic(page, offset, len(token))
    entry = {"resolution": res.status, "precision": res.status}
    if res.units:
        entry["ocr_source"] = (
            "word" if res.status == "EXACT_WORD" else "line" if res.status == "EXACT_LINE" else "cell"
        )
        entry["source_units"] = [_unitdata(u) for u in res.units]
        entry["min_confidence"] = res.signals.get("min_confidence")
    entry["anomaly_signals"] = res.signals
    return res, entry


def main() -> int:
    HIGHLIGHTS_ATOMIC.mkdir(parents=True, exist_ok=True)
    manifest: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "cached canonical JSON (atomic_units aus rapidocr/table_cells) + Original-PDF",
        "geometry_mode": "ATOMIC_OCR_GEOMETRY",
        "visual_verification": "PENDING_HUMAN",
        "note": "Exakte Highlights sind durch atomare OCR-Einheiten (Wort/Zeile/"
                "validierte Tabellenzelle) Containment-bewiesen. Render-PNGs muessen "
                "von einem Menschen am ORIGINAL-PDF VISUELL bestaetigt werden "
                "(VISUAL HUMAN VERIFICATION PENDING). Gate D bis Bestaetigung.",
        "contracts": {},
    }
    for name, cfg in TARGETS.items():
        result = load(name)
        pdf_path = INPUT / cfg["file"]
        entries = []
        for t in cfg["targets"]:
            token = (DATE_MONTH_RE.search(result.canonical_text).group(0).strip()
                     if t["token"] == "$DATE_MONTH" else t["token"])
            entry = {
                "kind": t["kind"],
                "label": t["label"],
                "target": token,
                "found": False,
                "resolution": "TARGET_NOT_FOUND",
                "programmatic_exact_geometry": False,
            }
            page, offset = locate_span(result, token)
            if token and page is not None and offset >= 0:
                res, res_entry = _resolve_entry(page, offset, token)
                entry["page"] = page.page_number
                entry["canonical_span"] = {"offset": offset, "length": len(token)}
                entry["page_size_pt"] = {
                    "view": {"w": page.width_pt, "h": page.height_pt},
                    "original": {
                        "w": page.original_width_pt or page.width_pt,
                        "h": page.original_height_pt or page.height_pt,
                    },
                    "pdf_rotation": page.pdf_rotation,
                }
                entry.update(res_entry)
                entry["found"] = res.status not in ("TARGET_NOT_FOUND",)
                entry["programmatic_exact_geometry"] = res.status in EXACT_STATUSES
                entry["boxes"] = [_regiondict(b) for b in res.boxes]
                entry["alignment_method"] = (
                    "canonical_text_match:line(SequenceMatcher Tokens)+word(casefold find)"
                )

                # MediaBox-Koordinaten fuer den Menschen (Original-PDF)
                rot = int(page.pdf_rotation or 0)
                med_w = page.original_width_pt or page.width_pt
                med_h = page.original_height_pt or page.height_pt
                if rot in (90, 270):
                    med_w, med_h = med_h, med_w
                entry["coordinates_mediabox"] = []
                for b in res.boxes:
                    entry["coordinates_mediabox"].append(
                        _regiondict(page_view_to_mediabox(b, rot, med_w=med_w, med_h=med_h))
                    )
                entry["anomaly_signals"].update(
                    _box_signals(res.boxes, page.width_pt, page.height_pt)
                )

                # Immer rendern (auch grober Fallback), damit ein Mensch beides sieht.
                suffix = "" if res.status in EXACT_STATUSES else f"_{res.status.lower()}"
                safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", token)[:40]
                png = HIGHLIGHTS_ATOMIC / f"{name}_snav_{t['label']}_{safe}{suffix}.png"
                render_info = render_transparent_boxes(pdf_path, page.page_number, res.boxes, png)
                entry["render"] = png.name
                entry["render_info"] = {k: v for k, v in render_info.items() if k != "render"}
            entries.append(entry)
        manifest["contracts"][name] = {"source": cfg["file"], "targets": entries}

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Source-Navigation (atomar): {MANIFEST}")
    exact_count = 0
    for name, c in manifest["contracts"].items():
        for t in c["targets"]:
            if t["found"]:
                marker = "ok " if t["programmatic_exact_geometry"] else "!! "
                source = t.get("ocr_source", "n/a")
                conf = t.get("min_confidence")
                print(
                    f"  [{name}] {t['label']:<10} '{t['target']}' [{marker}{t['resolution']}"
                    f" ~{source} conf={conf}] p{t['page']}"
                    + (f" render={t['render']}" if t.get("render") else "")
                )
            else:
                print(f"  [{name}] {t['label']:<10} '{t['target']}' [!! TARGET_NOT_FOUND]")
            exact_count += 1 if t["programmatic_exact_geometry"] else 0
    print(f"\nEXACT (Wort/Zeile/Zelle): {exact_count}/6")
    print("VISUAL HUMAN VERIFICATION PENDING (Render-PNGs am Original-PDF bestaetigen).")
    return 0 if exact_count == 6 else 1


if __name__ == "__main__":
    sys.exit(main())