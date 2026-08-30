"""STEP 8B Phase 8 – Manifest-Verifikation der Processing-Reproduzierbarkeit.

Prueft anhand der gecachten kanonischen Ergebnisse, ob die Bearbeitungs-
Herkuen(!) alle fuer Edit/Reproduzierbarkeit benoetigten Informationen behaelt:

- Quell-Identitaet (SHA256, Dateiname, Pfad, document_id)
- DI-Provider + Version
- OCR-Backend + Version
- Sprachen
- DPI (wo anwendbar; bei RapidOCR nicht ergaenzt -> bleibt None, kein Erfinden)
- Preprocessing-Identitaet/-Version (structural_roles_v1)
- kanonische Schema-Version
- Verarbeitungs-Zeitstempel
- Warnungen

KEINE neuen Metadaten werden hinzugefuegt – nur verifiziert, was schon da ist.

Nutzung:  python scripts/manifest_verification.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.documents.intelligence.canonical import DocumentIntelligenceResult

REPORTS = ROOT / "data" / "benchmark_v2" / "di_reports"
CONTRACTS = ["Vision RFD 3D", "GE MACLAB", "Truebeam STX"]


def _sha_ok(v: Optional[str]) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v.lower())


def verify_contract(name: str, result: DocumentIntelligenceResult) -> dict:
    p = result.provenance
    checks = {
        "source_sha256": _sha_ok(result.source_sha256),
        "source_filename": bool(result.source_filename),
        "source_path": bool(result.source_path),
        "document_id_allowed_none": result.document_id is None or bool(result.document_id),
        "provider": p.provider == "docling",
        "provider_version": bool(p.provider_version),
        "ocr_engine": p.ocr_engine == "rapidocr",
        "ocr_engine_version": bool(p.ocr_engine_version),
        "ocr_lang": bool(p.ocr_lang),
        "dpi_field_ok": "dpi" in p.model_fields and p.dpi is None,  # RapidOCR belegt keinen DPI
        "preprocessing_identity": p.preprocessing == "structural_roles_v1",
        "config_structural_roles": bool(p.config.get("structural_roles")),
        "canonical_schema_version": p.canonical_schema_version == "1.1.0",
        "created_at_is_datetime": isinstance(result.created_at, datetime),
        "warnings_list": isinstance(result.warnings, list),
    }
    structural_roles_applied = sum(
        1
        for page in result.pages
        for e in page.elements
        if (e.metadata or {}).get("structural_role")
    )
    return {
        "contract": name,
        "checks": checks,
        "all_ok": all(checks.values()),
        "structural_roles_marked_elements": structural_roles_applied,
        "processed_at": result.created_at.isoformat() if isinstance(result.created_at, datetime) else None,
        "warnings_count": len(result.warnings),
    }


def main() -> int:
    report: dict = {"schema_version": "1.1.0", "contracts": {}}
    for name in CONTRACTS:
        path = REPORTS / f"{name}.canonical.json"
        result = DocumentIntelligenceResult.model_validate_json(path.read_text(encoding="utf-8"))
        report["contracts"][name] = verify_contract(name, result)

    out_path = REPORTS / "manifest_verification.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== Manifest-Verifikation (STEP 8B Phase 8) ===")
    for name, c in report["contracts"].items():
        print(f"\n[{name}] all_ok={c['all_ok']} | Strukturrollen-Elemente={c['structural_roles_marked_elements']} | "
              f"Warnungen={c['warnings_count']} | verarbeitet={c['processed_at']}")
        for check, ok in c["checks"].items():
            if not ok:
                print(f"  FEHLT/NICHT OK: {check}")
    print(f"\nManifest: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())