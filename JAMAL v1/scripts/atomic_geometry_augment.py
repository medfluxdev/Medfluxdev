"""STEP 8B Korrektur – fokussierte atomare OCR-Geometrie (NUR Diagnose-PDFs).

Der ordnungsgemaesse Refresh ist pro Benutzer-Vorgabe auf die DREI
Diagnose-PDFs beschraenkt (kein voller 36er-Refresh). Es wird KEIN Docling
oder Qwen ausgefuehrt; der kanonische Text/Layout bleibt unveraendert.
Nur atomare Geometrie (RapidOCR-Voerter/-Zeilen + validierte Tabellenzellen)
wird erfasst, deterministisch gegen den kanonischen Seiten-Text aligniert und
zurueck in die gecachten canonical JSON geschrieben (Schema-Version 1.2.0).

Nutzung:  python scripts/atomic_geometry_augment.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.documents.intelligence.atomic_ocr import augment_with_atomic_geometry  # noqa: E402
from app.documents.intelligence.canonical import CANONICAL_SCHEMA_VERSION, DocumentIntelligenceResult  # noqa: E402

BASE = ROOT / "data" / "benchmark_v2"
INPUT = BASE / "input"
REPORTS = BASE / "di_reports"

CONTRACTS = {
    "Vision RFD 3D": "Vision RFD 3D.pdf",
    "GE MACLAB": "GE MACLAB.pdf",
    "Truebeam STX": "Truebeam STX.PDF",
}

DPI = 200


def main() -> int:
    start = time.monotonic()
    total_units = 0
    for name, filename in CONTRACTS.items():
        canonical_path = REPORTS / f"{name}.canonical.json"
        pdf_path = INPUT / filename
        if not canonical_path.exists():
            print(f"FEHLT: {canonical_path}")
            sys.exit(1)
        result = DocumentIntelligenceResult.model_validate_json(canonical_path.read_text(encoding="utf-8"))

        t0 = time.monotonic()
        result, stats = augment_with_atomic_geometry(result, pdf_path, dpi=DPI)
        result.provenance.canonical_schema_version = CANONICAL_SCHEMA_VERSION
        result.provenance.config["atomic_geometry"] = {
            "dpi": DPI,
            "provider": "rapidocr",
            "note": "Geometrie-Wiederherstellung (STEP 8B-Fix); Text/Layout unveraendert",
        }
        canonical_path.write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8"
        )

        n_units = sum(len(p.atomic_units) for p in result.pages)
        n_aligned = sum(sum(1 for u in p.atomic_units if u.aligned) for p in result.pages)
        total_units += n_units
        words = sum(p_stats["words"] for p_stats in stats["pages"])
        lines = sum(p_stats["lines"] for p_stats in stats["pages"])
        cells = sum(p_stats["cells"] for p_stats in stats["pages"])
        print(
            f"[{name}] Seiten={len(result.pages)} Zeilen={lines} Woerter={words} "
            f"Zellen={cells} Einheiten={n_units} (aligned={n_aligned}) in "
            f"{time.monotonic() - t0:.1f}s"
        )

    print(f"\nAtomic-Geometrie-Refresh fertig ({time.monotonic() - start:.1f}s, {total_units} Einheiten).")
    print("NAECHSTER SCHRITT: scripts/source_navigation_diagnostics.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())