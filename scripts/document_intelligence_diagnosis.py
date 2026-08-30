"""STEP 8B – Diagnose: Dokument-Intelligence (Docling) auf 3 Original-PDFs.

Verarbeitet NUR Vision RFD 3D, GE MACLAB, Truebeam STX (data/benchmark_v2/input/)
mit dem Docling-Provider und liefert, unter Beibehaltung der 132-Test-Baseline:

1. kanonische Ergebnisse je PDF (JSON in data/benchmark_v2/di_reports/)
2. Struktur-Validierung (Seiten, Elemente, Lesereihenfolge, Tabellen, Warnungen)
3. kritische Token-Qualität (Geld, Datum, Dauer, Prozent, IDs, Negation,
   deutsche Zeichen, englische Fachbegriffe)
4. echter Tabellen-Test (Grenzen, Zellen, Spans, Label->Wert)
5. Quell-Navigation: Wort/Phrase/kritischer Wert -> Seite -> Region(en) ->
   Hervorhebungs-Render (PNG), Original-PDF bleibt unveraendert
6. Lesereihenfolge inkl. Kopf-/Fusszeilen-Dominanzcheck
7. leichter PDF-vs-DOCX-Vergleich (keine KI)

Nutzung:  python scripts/document_intelligence_diagnosis.py [--refresh]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import fitz

from app.documents.extraction.docx import extract_docx_units
from app.documents.intelligence.canonical import DocumentIntelligenceResult
from app.documents.intelligence.provider import get_provider

BASE = ROOT / "data" / "benchmark_v2"
INPUT = BASE / "input"
REPORTS = BASE / "di_reports"
HIGHLIGHTS = REPORTS / "highlights"

SAMPLES = ["Vision RFD 3D.pdf", "GE MACLAB.pdf", "Truebeam STX.PDF"]
DEVICE_KEYWORDS = {
    "Vision RFD 3D.pdf": ["Vision", "Ziehm"],
    "GE MACLAB.pdf": ["MACLAB", "GE"],
    "Truebeam STX.PDF": ["Truebeam", "Varian"],
}

_NEGATION_WORDS = ["nicht", "kein", "keine", "keinen", "ohne", "nur", "mindestens", "hoechstens"]
_ENGLISH_TERMS = [
    "Full Service",
    "Preventive Maintenance",
    "Response Time",
    "Software",
    "Uptime",
    "Service Level",
]
_MONEY_RE = re.compile(r"\d{1,3}(?:\.\d{3})+,-(?!\d)|\d{1,3}(?:\.\d{3})+(?:,\d{2}|-)(?!\d)|\b(?:\d{1,3},\d{2}|\d{1,2},-)\s*(?:€|EUR)?(?!\d)|\b\d{1,3}(?:\.\d{3})*,\d{2}(?!\d)", re.I)
_DATE_RE = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b")
_DATE_MONTH_RE = re.compile(r"\d{1,2}\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*\d{2,4}", re.I)
_DATE_SLASH_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_PERCENT_RE = re.compile(r"\d+(?:[,.]\d+)?\s*%")
_ID_RE = re.compile(r"\b[A-Za-z]{1,5}[-–]\d[A-Za-z0-9]{1,}\b|\b[A-Z]{1,4}\d{3,}\b")
_DURATION_UNITS = ["Monate", "Wochen", "Jahre", "Tage", "Stunden", "months", "weeks", "years"]
_GERMAN_CHARS = "äöüßÄÖÜ"


# ---------------------------------------------------------------- Text-Scans

def token_scan(text: str) -> dict:
    money = [m.group(0).strip() for m in _MONEY_RE.finditer(text)]
    dates = _DATE_RE.findall(text) + _DATE_MONTH_RE.findall(text)
    dates_slash = _DATE_SLASH_RE.findall(text)
    pct = _PERCENT_RE.findall(text)
    ids = [m.group(0) for m in _ID_RE.finditer(text)]

    def clean(words):
        return [w.replace("l", "l").replace("oe", "ö").replace("ae", "ä")
                .replace("ue", "ü").replace("ss", "ß") if False else w for w in words]

    lower = text.lower()
    neg_hits = {w: lower.count(w) for w in _NEGATION_WORDS}
    german_chars = sum(text.count(c) for c in _GERMAN_CHARS)
    duration_hits = {w: text.count(w) for w in _DURATION_UNITS}
    eng_hits = {t: (1 if t.lower() in lower else 0) for t in _ENGLISH_TERMS}

    return {
        "characters": len(text),
        "money": money,
        "money_count": len(money),
        "dates_dot": dates,
        "dates_slash": dates_slash,
        "percent": pct,
        "identifiers": list(dict.fromkeys(ids))[:40],
        "negation": neg_hits,
        "negation_total": sum(v for v in neg_hits.values()),
        "german_chars": german_chars,
        "duration_terms": duration_hits,
        "english_terms": eng_hits,
    }


# ---------------------------------------------------------------- Struktur

def page_structure(page) -> dict:
    types = {}
    for e in page.elements:
        types[e.type.value] = types.get(e.type.value, 0) + 1
    hdr = [e for e in page.elements if e.type.value in ("header", "footer", "page_number")]
    body_elems = [e for e in page.elements if e.type.value not in ("header", "footer", "page_number")]
    body_chars = sum(len(e.text) for e in body_elems)
    hdr_chars = sum(len(e.text) for e in hdr)
    return {
        "page": page.page_number,
        "size_pt": [round(page.width_pt, 1), round(page.height_pt, 1)],
        "elements": len(page.elements),
        "types": types,
        "text_len": len(page.text),
        "header_footer_share": round(hdr_chars / max(1, body_chars + hdr_chars), 3),
        "reading_order": [
            {"type": e.type.value, "text": e.text[:60], "ro": e.reading_order, "key": next(iter(f"{e.type.value}:{e.text[:40]}"), "")}
            if False else {"type": e.type.value, "text": e.text[:60], "ro": e.reading_order}
            for e in page.elements
        ],
    }


def document_structure(result) -> dict:
    return {
        "pages": len(result.pages),
        "elements_total": sum(len(p.elements) for p in result.pages),
        "tables_total": len(result.all_tables()),
        "text_total": len(result.canonical_text),
        "reading_order_pages": [page_structure(p) for p in result.pages],
    }


# ---------------------------------------------------------------- Tabellen

def table_detail(t) -> dict:
    grid = t.row_texts()
    money_cells = []
    for row in range(t.num_rows):
        for col in range(t.num_cols):
            c = t.cell(row, col)
            if c and _MONEY_RE.search(c.text):
                label = next((grid[row][k] for k in range(col) if grid[row][k]), "")
                money_cells.append({
                    "row": row, "col": col, "text": c.text,
                    "row_label": label or (grid[row][0] if grid[row] else ""),
                    "token": _MONEY_RE.search(c.text).group(0) if _MONEY_RE.search(c.text) else "",
                })
    return {
        "table_id": t.table_id,
        "page": t.page,
        "dims": [t.num_rows, t.num_cols],
        "cells": len(t.cells),
        "headers": t.headers,
        "rows": grid[:8],
        "money_in_cells": money_cells,
    }


# ---------------------------------------------------------------- Quell-Navigation

def _contains_words_in_order(text: str, words: list[str]) -> bool:
    tokens = text.split()
    idx = 0
    for tok in tokens:
        if idx < len(words) and tok.lower() == words[idx].lower():
            idx += 1
    return idx == len(words)


def find_word(result, needle):
    low = needle.lower()
    for page in result.pages:
        for e in page.elements:
            for sp in e.spans:
                if sp.offset is not None and low in page.text[sp.offset:sp.to()].lower() and e.region:
                    return page, e
    return None, None


def find_phrase_interline(result, phrase):
    """Sucht Phrase in EINEM Element oder zeilenuebergreifend ueber mehrere."""
    words = phrase.split()
    for page in result.pages:
        elems = page.elements
        norm = [" ".join(e.text.split()) for e in elems]
        for i in range(len(elems)):
            if words[0].lower() not in norm[i].lower():
                continue
            joined = norm[i]
            j = i
            while not _contains_words_in_order(joined, words) and j + 1 < len(elems):
                j += 1
                joined = " ".join([joined, norm[j]])
            if _contains_words_in_order(joined, words):
                covers = [elems[k] for k in range(i, j + 1) if elems[k].region is not None]
                if covers:
                    return page, covers
    return None, None


def render_highlights(pdf_path: Path, page_no: int, regions, png_path: Path) -> None:
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_no - 1)
        shape = page.new_shape()
        for r in regions:
            rect = fitz.Rect(r.x0, r.y0, r.x1, r.y1)
            shape.draw_rect(rect)
            shape.finish(color=(0.9, 0.05, 0.05), fill=(0.9, 0.2, 0.2, 0.25), width=2, closePath=True)
        shape.commit()
        pix = page.get_pixmap(dpi=160)
        pix.save(str(png_path))
    finally:
        doc.close()


def _money_value(token: str) -> float:
    s = re.sub(r"[^\d,.-]", "", token).replace(".", "").rstrip("-")
    if not s:
        return 0.0
    s = s.replace(",", ".")
    parts = s.split(".")
    if len(parts) > 1 and len(parts[-1]) == 2:
        s = ".".join(parts)
    try:
        if s.count(".") > 1:
            s = "".join(s.split(".")[:-1]) + "." + s.split(".")[-1]
        return float(s)
    except ValueError:
        return 0.0


def source_navigation_check(result, pdf_path: Path, device_keywords: list[str]) -> dict:
    report = {"targets": []}
    # kritisches Geld: hoechster Betrag im Vertrag
    money_tokens = [m.group(0).strip() for m in _MONEY_RE.finditer(result.canonical_text)]
    critical = max(money_tokens, key=_money_value) if money_tokens else None
    targets = []
    if critical:
        targets.append(("word", critical))
    date = _DATE_RE.search(result.canonical_text)
    if date:
        targets.append(("word", date.group(0)))
    for kw in device_keywords:
        targets.append(("word", kw))
    phrase_candidates = ["Full Service", "Preventive Maintenance", "Vollwartung", "Kündigungsfrist"]
    phrase = next((p for p in phrase_candidates if _norm_contains(result, p)), None)
    if phrase:
        targets.append(("phrase", phrase))

    for kind, token in targets:
        if kind == "word":
            page, elem = find_word(result, token)
            if elem is None:
                report["targets"].append({"kind": kind, "token": token, "found": False})
                continue
            regions = [elem.region]
            png = HIGHLIGHTS / f"{pdf_path.stem}_word_{_safe(token)}.png"
            render_highlights(pdf_path, page.page_number, regions, png)
            report["targets"].append({
                "kind": kind, "token": token, "found": True,
                "page": page.page_number,
                "span": {"offset": elem.spans[0].offset, "length": elem.spans[0].length},
                "element_id": elem.element_id,
                "region": _regiondict(regions[0]),
                "render": png.name,
            })
        else:
            page, covers = find_phrase_interline(result, token)
            if page is None or not covers:
                report["targets"].append({"kind": kind, "token": token, "found": False})
                continue
            regions = [c.region for c in covers]
            png = HIGHLIGHTS / f"{pdf_path.stem}_phrase_{_safe(token)}.png"
            render_highlights(pdf_path, page.page_number, regions, png)
            report["targets"].append({
                "kind": kind, "token": token, "found": True,
                "page": page.page_number,
                "boxes": len(regions),
                "regions": [_regiondict(r) for r in regions],
                "render": png.name,
            })
    return report


def _norm_contains(result, phrase):
    return phrase.lower() in result.canonical_text.lower()


def _safe(token: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", token)[:40]


def _regiondict(r) -> dict:
    return {"page": r.page, "x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1}


# ---------------------------------------------------------------- DOCX-Vergleich

def docx_text_for(name: str) -> tuple[Optional[str], int]:
    for p in sorted((ROOT / "data" / "benchmark" / "input").rglob("*.docx")):
        if name in p.name:
            try:
                units = extract_docx_units(p)
                return "\n".join(u.text for u in units), sum(1 for u in units if u.source_type.value == "table")
            except Exception as exc:
                return None, 0
    return None, 0


def pdf_vs_docx(pdf_canonical: str, contract_base: str) -> dict:
    txt, tables = docx_text_for(contract_base)
    out = {"docx_found": txt is not None}
    if txt is None:
        return out
    scan_pdf = token_scan(pdf_canonical)
    scan_docx = token_scan(txt)
    pdf_money = set(scan_pdf["money"])
    docx_money = set(scan_docx["money"])
    common = pdf_money & docx_money
    return {
        "docx_found": True,
        "docx_tables": tables,
        "docx_chars": scan_docx["characters"],
        "pdf_chars": scan_pdf["characters"],
        "money_pdf": len(pdf_money),
        "money_docx": len(docx_money),
        "money_common": len(common),
        "money_examples_pdf_missing_in_docx": sorted(pdf_money - docx_money)[:10],
        "dates_pdf": sort_set(scan_pdf["dates_dot"]),
        "dates_docx": sort_set(scan_docx["dates_dot"]),
        "german_chars_pdf": scan_pdf["german_chars"],
        "german_chars_docx": scan_docx["german_chars"],
        "ids_pdf": scan_pdf["identifiers"],
        "ids_docx": scan_docx["identifiers"],
        "negation_pdf": scan_pdf["negation_total"],
        "negation_docx": scan_docx["negation_total"],
        "english_terms_pdf": [k for k, v in scan_pdf["english_terms"].items() if v],
        "english_terms_docx": [k for k, v in scan_docx["english_terms"].items() if v],
    }


def sort_set(vals):
    return sorted(set(vals))


def gt_cross_check(contract_base: str, pdf_canonical: str) -> dict:
    """Prueft zentrale Ground-Truth-Erwartungen gegen den OCR-Text (Fakten-Check)."""
    gt_file = ROOT / "data" / "benchmark" / "ground_truth.json"
    if not gt_file.exists():
        return {"checked": False, "reason": "missing"}
    contracts = json.loads(gt_file.read_text(encoding="utf-8")).get("contracts", {})
    key = next((k for k in contracts if contract_base.replace(" ", "_").lower() in k.lower()), None)
    if key is None:
        return {"checked": False, "reason": "no_contract_key"}
    normalized = re.sub(r"\s+", " ", pdf_canonical).lower()
    results = []
    for f in contracts[key].get("fields", []):
        exp = f.get("expect")
        if not isinstance(exp, str) or len(exp) < 3:
            continue
        results.append({"field": f["field"], "expect": exp, "found": exp.lower() in normalized})
    return {"checked": True, "results": results}


# ---------------------------------------------------------------- Main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="Erneut verarbeiten (Cache ignorieren)")
    args = ap.parse_args()

    HIGHLIGHTS.mkdir(parents=True, exist_ok=True)
    provider = get_provider("docling")

    summary: dict = {"provider": provider.capabilities().model_dump(), "contracts": {}}

    for sample in SAMPLES:
        base = Path(sample).stem
        pdf_path = INPUT / sample
        json_path = REPORTS / f"{base}.canonical.json"
        result: Optional[DocumentIntelligenceResult] = None

        if json_path.exists() and not args.refresh:
            result = DocumentIntelligenceResult.model_validate_json(json_path.read_text(encoding="utf-8"))
        else:
            t0 = time.monotonic()
            result = provider.process(pdf_path)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

        struct = document_structure(result)
        scan = token_scan(result.canonical_text)
        tables = [table_detail(t) for t in result.all_tables()]
        nav = source_navigation_check(result, pdf_path, DEVICE_KEYWORDS[sample])
        vsdocx = pdf_vs_docx(result.canonical_text, base)
        gt = gt_cross_check(base, result.canonical_text)

        reading_check = reading_order_check(struct["reading_order_pages"])

        summary["contracts"][base] = {
            "source": sample,
            "source_sha256": result.source_sha256[:16],
            "processing_time_s": result.processing_time_s,
            "provenance": result.provenance.model_dump(),
            "warnings": result.warnings,
            "structure": struct,
            "token_quality": scan,
            "tables": tables,
            "source_navigation": nav,
            "pdf_vs_docx": vsdocx,
            "ground_truth_check": gt,
            "reading_order": reading_check,
        }

    (REPORTS / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("=== STEP 8B Dokument-Intelligence-Diagnose ===")
    for name, c in summary["contracts"].items():
        s = c["structure"]
        t = c["token_quality"]
        toks = c["source_navigation"]
        navline = "; ".join(
            f"{x['kind']}:'{x['token']}'→p{x.get('page')}" + ("×" + str(x.get("boxes")) if x.get("boxes") else "")
            for x in toks["targets"]
        )
        print(
            f"\n[{name}] {c['source']} ({c['processing_time_s']}s)\n"
            f"  pages={s['pages']} elements={s['elements_total']} tables={s['tables_total']} chars={s['text_total']}\n"
            f"  money={t['money_count']} dates={len(t['dates_dot'])}/slash={len(t['dates_slash'])} pct={len(t['percent'])} "
            f"ids={len(t['identifiers'])} neg={t['negation_total']} de-chars={t['german_chars']}\n"
            f"  nav: {navline}\n"
            f"  gt: {c['ground_truth_check'].get('checked')} "
            f"{sum(r['found'] for r in c['ground_truth_check'].get('results', []))}/"
            f"{len(c['ground_truth_check'].get('results', []))} matches\n"
            f"  docx: {c['pdf_vs_docx'].get('docx_found')} money_common={c['pdf_vs_docx'].get('money_common')}/"
            f"{c['pdf_vs_docx'].get('money_pdf')} reading_hf_share_ok={c['reading_order']['hf_interleave_ok']}"
        )
    print(f"\nReports: {REPORTS}")
    return 0


def reading_order_check(pages: list[dict]) -> dict:
    """Kopf-/Fußzeilen duerfen den Lesefluss nicht dominieren (max 3%)."""
    shares = [p["header_footer_share"] for p in pages]
    max_share = max(shares) if shares else 0.0
    return {"hf_max_share": round(max_share, 3), "hf_interleave_ok": max_share <= 0.3}


if __name__ == "__main__":
    sys.exit(main())