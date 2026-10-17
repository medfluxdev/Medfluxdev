"""Deterministische Wiederherstellung von Vertragsfakten aus dem persistierten
kanonischen Dokumenttext (canonical.json, Docling-Schema 1.3+).

Hintergrund (UAT Re-Test): Die strukturierte Extraktion (`contract_snapshot`)
traegt z. B. nur den Netto-Wartungspreis. Der vollstaendige Preis-Tabellen-
Zusammenhang (Netto, MwSt-Satz, MwSt-Betrag, Brutto) sowie Laufzeit-Fakten
(Zahlungsbeginn, Mindestvertragslaufzeit) liegen aber bereits dauerhaft im
kanonischen Artefakt der ACCEPTIERTEN Verarbeitung. Dieses Modul stellt diese
Fakten deterministisch aus diesem persistierten Text wieder her:

- KEINE neue OCR-/LLM-Ingestion, KEINE Neuberechnung durch die KI.
- KEINE erfundenen Werte: ein Fakt wird NUR uebernommen, wenn er wörtlich im
  persistierten Text steht ("nicht gefunden" bleibt None).
- Jeder wiederhergestellte Fakt traegt Seite (`page_number`) + Quell-Snippet
  + (falls vorhanden) Bounding-Box in PDF-Punkten fuer exakte Quell-Navigation.

Recovery-Regeln (konservativ, deterministisch):
- Preis-Tabelle: Zellen mit "Gesamtdienstleistungspreis netto/brutto pro Monat"
  und "zzgl. X% MwSt."; Betraege sind die direkt folgenden Tabellenzellen.
- Basis: "netto ... zzgl. ... MwSt" => NET.
- Zahlungsbeginn: "N Monate nach Ablauf der Gewa(e)hrleistung".
- Mindestvertragslaufzeit: "Mindestvertragslaufzeit:<N> Monate".

Bei jedem Fehler (Datei fehlt/kaputt/unbekanntes Format) kehrt das Read-Model
in den gewohnten Evidence-First-Pfad zurueck (leere Fakten, keine Ausnahme).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.models import DocumentArtifact, ProcessingRun
from app.documents.storage import DocumentStorage


@dataclass
class RecoveredMoney:
    """Wiederhergestellter Preis-Tabellen-Zusammenhang (netto/MwSt/brutto)."""

    monthly_net: Optional[Decimal] = None
    monthly_vat: Optional[Decimal] = None
    vat_rate: Optional[int] = None
    monthly_gross: Optional[Decimal] = None
    currency: Optional[str] = None
    basis: Optional[str] = None  # "net" | "gross"
    # Provenienz (Seite + PDF-Punkt-Box + Quell-Snippet), je Fakt.
    page: Optional[int] = None
    net_region: Optional[dict] = None
    vat_region: Optional[dict] = None
    gross_region: Optional[dict] = None
    snippets: dict = field(default_factory=dict)


@dataclass
class RecoveredIdentity:
    """Wiederhergestellte Identitaet (Vertragsnummer + Dokument-Überschrift +
    System-/Produkt-Identitaet).

    Beides wird deterministisch aus dem persistierten kanonischen Seitentext
    der ACCEPTIERTEN Verarbeitung gelesen – keine KI, keine Erfindung. Jeder
    Fakt traegt Seite + (falls vorhanden) Box + Quell-Snippet.
    """

    contract_number: Optional[str] = None
    contract_number_page: Optional[int] = None
    contract_number_region: Optional[dict] = None
    contract_number_snippet: Optional[str] = None
    title: Optional[str] = None
    title_page: Optional[int] = None
    title_region: Optional[dict] = None
    title_snippet: Optional[str] = None
    # UAT Re-Test (Defect 3): die im Dokument genannte SYSTEM-Identitaet
    # (z. B. "Impella AIC System"), damit eine Komponente (z. B. "Impella
    # Controller") die vertragsprimäre Geräte-Identitaet nicht verdrängt.
    system_identity: Optional[str] = None
    system_identity_page: Optional[int] = None
    system_identity_region: Optional[dict] = None
    system_identity_snippet: Optional[str] = None


@dataclass
class RecoveredLaufzeit:
    """Wiederhergestellte Laufzeit-Fakten (Beginn-Ereignis, Zahlungsbeginn,
    Mindestlaufzeit, absolute Vertragsdaten, automatische Verlaengerung)."""

    start_event: Optional[str] = None
    payment_start_rule: Optional[str] = None
    payment_start_page: Optional[int] = None
    payment_start_region: Optional[dict] = None
    payment_start_snippet: Optional[str] = None
    minimum_duration_months: Optional[int] = None
    minimum_duration_page: Optional[int] = None
    minimum_duration_region: Optional[dict] = None
    minimum_duration_snippet: Optional[str] = None
    # Absolute, wörtlich im Vertrag dokumentierte Laufzeit-Daten.
    absolute_start: Optional[date] = None
    absolute_start_page: Optional[int] = None
    absolute_start_region: Optional[dict] = None
    absolute_start_snippet: Optional[str] = None
    absolute_end: Optional[date] = None
    absolute_end_page: Optional[int] = None
    absolute_end_region: Optional[dict] = None
    absolute_end_snippet: Optional[str] = None
    duration_years: Optional[int] = None
    duration_page: Optional[int] = None
    duration_region: Optional[dict] = None
    duration_snippet: Optional[str] = None
    auto_renewal: Optional[bool] = None
    auto_renewal_page: Optional[int] = None
    auto_renewal_region: Optional[dict] = None
    auto_renewal_snippet: Optional[str] = None


@dataclass
class RecoveredCostLine:
    """Eine im Vertrag wörtlich belegte Preis-Zeile (z. B. je Vertragsjahr)."""

    label: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    page: Optional[int] = None
    region: Optional[dict] = None
    snippet: Optional[str] = None


@dataclass
class RecoveredFacts:
    money: Optional[RecoveredMoney] = None
    laufzeit: Optional[RecoveredLaufzeit] = None
    identity: Optional[RecoveredIdentity] = None
    cost_lines: list = field(default_factory=list)


# =========================================================================
# Ladepfad: persistiertes kanonisches Artefakt -> Seiten mit Text + Elementen
# =========================================================================


def load_canonical_pages(
    session: Session, *, organization_id, document_version_id
) -> list[dict]:
    """Liest die persistierten Seiten des neuesten kanonischen Artefakts.

    Liefert `[{"page": int, "text": str, "elements": [...], "tables": [...]}]`.
    Lehnt jede Abweichung defensiv mit `[]` ab (loses Ende).
    """
    try:
        artifact = session.scalars(
            select(DocumentArtifact)
            .outerjoin(ProcessingRun, DocumentArtifact.processing_run_id == ProcessingRun.id)
            .where(
                (DocumentArtifact.organization_id == organization_id)
                & (DocumentArtifact.document_version_id == document_version_id)
                & (DocumentArtifact.artifact_type == "canonical")
                & (DocumentArtifact.lifecycle_state == "active")
            )
            .order_by(
                func.coalesce(ProcessingRun.created_at, DocumentArtifact.created_at).desc()
            )
            .limit(1)
        ).first()
        if artifact is None:
            return []
        payload = DocumentStorage(settings.contracts_dir).read_reference(artifact.storage_key)
        data = json.loads(payload.decode("utf-8", errors="replace"))
        pages = data.get("pages") if isinstance(data, dict) else None
        if not isinstance(pages, list):
            return []
        flip = legacy_bottom_up(data)
        out = []
        for pg in pages:
            if not isinstance(pg, dict) or not pg.get("page_number"):
                continue
            elements = [e for e in (pg.get("elements") or []) if isinstance(e, dict)]
            tables = [t for t in (pg.get("tables") or []) if isinstance(t, dict)]
            height = _float(pg.get("height_pt"))
            if flip and height:
                _flip_regions(elements, height)
                _flip_regions(tables, height)
            out.append(
                {
                    "page": int(pg["page_number"]),
                    "text": str(pg.get("text") or ""),
                    "elements": elements,
                    "tables": tables,
                    "width_pt": _float(pg.get("width_pt")),
                    "height_pt": height,
                    # Gespeicherte Nachweis-Boxen dieses Artefakts liegen noch unten-links.
                    "legacy_bottom_up": bool(flip and height),
                }
            )
        return out
    except Exception:
        return []


def legacy_bottom_up(data: dict) -> bool:
    """Docling-Artefakte vor Schema 1.4.0 tragen Regionen mit Ursprung unten links
    (der BOTTOMLEFT-Vergleich griff beim Enum nicht). PyMuPDF-Artefakte waren immer oben links."""
    provenance = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
    if str(provenance.get("provider") or "") != "docling":
        return False
    version = str(provenance.get("canonical_schema_version") or "0")
    try:
        parts = tuple(int(p) for p in version.split("."))
    except ValueError:
        return False
    return parts < (1, 4, 0)


def _float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _flip_regions(node, height: float) -> None:
    """Spiegelt jede Region ({page, x0, y0, x1, y1}) an der Seitenhoehe – rekursiv, in place."""
    if isinstance(node, list):
        for item in node:
            _flip_regions(item, height)
        return
    if not isinstance(node, dict):
        return
    if {"x0", "y0", "x1", "y1"} <= node.keys():
        try:
            y0, y1 = float(node["y0"]), float(node["y1"])
        except (TypeError, ValueError):
            return
        node["y0"], node["y1"] = max(0.0, height - y1), max(0.0, height - y0)
        return
    for value in node.values():
        if isinstance(value, (dict, list)):
            _flip_regions(value, height)


# =========================================================================
# Text-Normalisierung (Mojibake-Korrektur bekannter Docling-/OCR-Glyphen)
# =========================================================================

_MOJIBAKE: dict[str, str] = {
    "├╝": "ü",
    "├ñ": "ä",
    "├ö": "ö",
    "├⌐": "é",
    "├¿": "è",
    "├¡": "í",
    "├│": "ó",
    "├║": "ú",
    "├▒": "ñ",
    "├º": "ç",
    "├ê": "Ê",
    "├å": "Æ",
    "├ƒ": "ß",
    "Γé¼": "€",
    "ΓÇ£": "“",
    "ΓÇ¥": "”",
    "ΓÇÿ": "‘",
    "ΓÇÖ": "’",
    "ΓÇð": "–",
    "ΓÇö": "—",
    "ΓÇª": "…",
    "ΓêÆ": "−",
    "ΓêÜ": "√",
    "Γêê": "∈",
    "Γàí": "≤",
    "Γèñ": "≥",
    "ΓûÖ": "•",
}


def fix_text(text: str) -> str:
    """Ersetzt bekannte Mojibake-/OCR-Glyphen durch das Zielzeichen.

    Fehlende Zuordnungen bleiben unveraendert (keine Erfindung); die
    Kern-Regularenaetze sind auf die sauberen Ziel-Strings ausgelegt.
    """
    if not text:
        return text
    for k, v in _MOJIBAKE.items():
        if k in text:
            text = text.replace(k, v)
    return text


# =========================================================================
# Parser (pure Funktionen – testbar ohne DB/Dateisystem)
# =========================================================================


def _parse_german_date(raw: str) -> Optional[date]:
    """Parst ein deutsches Datum (01.04.2025 / 1.4.2025)."""
    m = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*", raw or "")
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


# Deutsche + englische Bezeichner der Vertrags-/Angebotsnummer. Bewusst vor
# "Vertrag Nr." und ohne weitere Satzzeichen, damit z. B. "Vertrags- und
# Auftragsnummer" (ohne Wert) NICHT erfasst wird.
_CONTRACT_NUMBER_RE = re.compile(
    r"(?:Vertr\.?\s*-?\s*Nr\.?|Vertrags\s*-?\s*Nr\.?|Vertragsnr\.?"
    r"|Vertragsnummer|Vertrag\s+Nr\.?|Contract\s*(?:No\.?|Number|Nr\.?)?)"
    r"\s*[:\-–]?\s*([A-Za-z0-9][A-Za-z0-9.\/\-_]{2,40})",
    re.IGNORECASE,
)

_ABSOLUTE_DATES_RE = re.compile(
    r"beginnt\s+am\s+(\d{1,2}\.\d{1,2}\.\d{4})\s+und\s+endet\s+am\s+(\d{1,2}\.\d{1,2}\.\d{4})",
    re.IGNORECASE,
)
_DURATION_YEARS_RE = re.compile(r"Laufzeit\s+von\s+(\d{1,2})\s*Jahren?", re.IGNORECASE)
_AUTO_RENEW_NO_RE = re.compile(
    r"wird\s+(?:nicht|kein[e]?)\s+(?:automatisch\s+)?verl[aä]ngert|nicht\s+automatisch\s+verl[aä]nger",
    re.IGNORECASE,
)
_AUTO_RENEW_YES_RE = re.compile(
    r"automatisch\s+(?:um\s+\d+|verl[aä]ngert)|verl[aä]ngert\s+sich\s+automatisch",
    re.IGNORECASE,
)

# Skimming-Glyphen (OCR-Muell) entfernen – rein kosmetisch, kein erfundener Wert.
_UNWANTED_CHARS = ("\ufffd", "\u00ae", "\u2122", "\u00a0")


def _clean_phrase(text: str) -> str:
    """Raumt Verdrahtungs-/OCR-Muell aus einer belegten Phrase (Kosmetik)."""
    if not text:
        return text
    for ch in _UNWANTED_CHARS:
        text = text.replace(ch, " ")
    return " ".join(str(text).split()).strip()


def _line(x0, y0, x1, y1):
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


def _best_region(text) -> Optional[dict]:
    return None


def _find_contract_number(pages) -> Optional[dict]:
    """Vertragsnummer aus dem persistierten Seitentext (deutscher/englischer Label)."""
    for pg in pages:
        text = fix_text(pg.get("text") or "")
        m = _CONTRACT_NUMBER_RE.search(text)
        if not m:
            continue
        value = m.group(1).strip(" .:-–")
        if not value:
            continue
        return {
            "number": value,
            "page": pg["page"],
            "region": None,
            "snippet": _clean_phrase(m.group(0))[:200],
        }
    return None


def _find_title(pages) -> Optional[dict]:
    """Dokument-Überschrift (z. B. "Full-Service-Vertrag für das Impella AIC
    System") aus den Elementen der ersten Seite.

    Bewusst konservativ: ein kurzes Kopfelement mit "Vertrag"/"Vereinbarung"
    plus ggf. die direkt folgende Subject-Zeile. Keine Parteien-/Nr.-Zeilen,
    keine Paragraphen.
    """
    for pg in pages:
        if int(pg.get("page", 0)) != 1:
            continue
        els = sorted(
            [e for e in (pg.get("elements") or []) if isinstance(e, dict)],
            key=lambda e: (float(e.get("region", {}).get("y0") or 0)),
        )
        for i, el in enumerate(els):
            t = _clean_phrase(fix_text(str(el.get("text") or "")))
            low = t.lower()
            if not (re.search(r"vertrag|vereinbarung", low)):
                continue
            if len(t) < 4 or len(t) > 140:
                continue
            if low.startswith("§") or "nr." in low or low.startswith("zwischen"):
                continue
            if re.search(r"\d{4}", t):
                continue
            heading = t
            subject = None
            for sibling in els[i + 1 :]:
                st = _clean_phrase(fix_text(str(sibling.get("text") or "")))
                if not st or len(st) > 140:
                    continue
                if re.search(r"nr\.|vertrag|zwischen|und$", st.lower()):
                    continue
                if re.search(r"\d{4}", st):
                    continue
                subject = st
                break
            title = f"{heading} {subject}".strip() if subject else heading
            return {
                "title": title,
                "page": pg["page"],
                "region": _region_of(el),
                "snippet": title[:200],
            }
    return None


# UAT Re-Test (Defect 3): System-/Produkt-Identitaet der Betreff-Zeile,
# z. B. "für das Impella® AIC System" -> "Impella AIC System". Das OCR-Muster
# der kanonischen Seiten traegt Umlaut/Sonderzeichen teils als U+FFFD ("f�r
# das Impella� AIC System"); die Cleanup-Phase entfernt diese Glyphen, daher
# toeleriert der Parser "f  r" genauso wie "für".
_SYSTEM_IDENTITY_RE = re.compile(
    r"f[üÃ¼\ufffd\s]{1,3}r\s+das\s+([A-Za-zÄÖÜäöüß0-9\-\.\s]{3,60}?)\s+system\b",
    re.IGNORECASE,
)


def _find_system_identity(pages) -> Optional[dict]:
    """System-Identitaet aus der Betreff-Zeile der ersten Seite.

    Muster: "… für das Impella® AIC System …". Ein Element/Seite 1 mit exakt
    diesem Muster liefert Bezeichnung + Seite + Region + Snippet. Ohne Treffer
    None (keine Erfindung) – eine Komponente ersetzt nie die System-Identitaet.
    """
    for pg in pages:
        if int(pg.get("page", 0)) != 1:
            continue
        els = sorted(
            [e for e in (pg.get("elements") or []) if isinstance(e, dict)],
            key=lambda e: (float(e.get("region", {}).get("y0") or 0)),
        )
        for el in els:
            t = _clean_phrase(fix_text(str(el.get("text") or "")))
            if "für das" not in t.lower():
                continue
            m = _SYSTEM_IDENTITY_RE.search(t)
            if not m:
                continue
            designation = m.group(1).strip(" -.")
            if len(designation) < 3:
                continue
            system = _clean_phrase(f"{designation} System")
            return {
                "system": system,
                "page": pg["page"],
                "region": _region_of(el),
                "snippet": t[:300],
            }
    return None


def _find_absolute_dates(pages) -> Optional[dict]:
    """Absolute, wörtlich dokumentierte Vertragsdaten ("beginnt am ... endet
    am ..."), Laufzeit (Jahre) und automatische Verlaengerung."""
    for pg in pages:
        text = fix_text(pg.get("text") or "")
        result = {}
        m = _ABSOLUTE_DATES_RE.search(text)
        if m:
            s = _parse_german_date(m.group(1))
            e = _parse_german_date(m.group(2))
            if s is not None and e is not None:
                result["start"] = s
                result["end"] = e
                result["start_page"] = pg["page"]
                result["end_page"] = pg["page"]
                result["snippet"] = _clean_phrase(m.group(0))[:200]
        dm = _DURATION_YEARS_RE.search(text)
        if dm:
            try:
                result["duration_years"] = int(dm.group(1))
                result["duration_page"] = pg["page"]
                result["duration_snippet"] = _clean_phrase(dm.group(0))[:200]
            except (TypeError, ValueError):
                pass
        if _AUTO_RENEW_NO_RE.search(text):
            result["auto_renewal"] = False
            result["auto_renewal_page"] = pg["page"]
            m_no = _AUTO_RENEW_NO_RE.search(text)
            result["auto_renewal_snippet"] = _clean_phrase(
                text[max(0, m_no.start() - 40): m_no.end() + 20]
            )[:200]
        elif _AUTO_RENEW_YES_RE.search(text):
            result["auto_renewal"] = True
            result["auto_renewal_page"] = pg["page"]
            m_yes = _AUTO_RENEW_YES_RE.search(text)
            result["auto_renewal_snippet"] = _clean_phrase(
                text[max(0, m_yes.start() - 40): m_yes.end() + 20]
            )[:200]
        if result:
            return result
    return None


def _money_cell_amount(cell_text: str) -> Optional[Decimal]:
    """Parst einen Betrag nur aus Zellen, die eine Waehrung tragen ("0 EUR",
    "8.000,00 EUR", "1.200,00 €"). Ohne Waehrungs-Token -> None (kein Raten)."""
    t = str(cell_text or "").strip()
    if "€" in t:
        t = t.replace("€", "")
    elif re.search(r"\bEUR\b", t, flags=re.IGNORECASE):
        t = re.sub(r"\bEUR\b", "", t, flags=re.IGNORECASE)
    else:
        return None
    return _parse_german_amount(t)


def _money_snippet_is_amount(cell_text: str) -> bool:
    t = str(cell_text or "").strip()
    return "€" in t or re.search(r"\bEUR\b", t, flags=re.IGNORECASE) is not None


def _find_cost_lines(pages) -> list[dict]:
    """Preis-Zeilen wörtlich aus dem Vertrag (je Vertragsjahr, Preise etc.).

    Bevorzugt Tabellen-Zellen (Label + folgender Betrag). Fallback: Seitentext-
    Zeilen im Muster "<Label> | <Betrag> EUR". Deterministisch, keine Erfindung.
    """
    lines: list[dict] = []
    seen = set()
    for pg in pages:
        for tbl in pg.get("tables") or []:
            cells = [c for c in (tbl.get("cells") or []) if isinstance(c, dict)]
            for i, cell in enumerate(cells):
                ct = fix_text(str(cell.get("text") or "")).strip()
                amt = _money_cell_amount(ct)
                if amt is None or not _money_snippet_is_amount(ct):
                    continue
                label = None
                for prev in cells[max(0, i - 3) : i]:
                    pt = fix_text(str(prev.get("text") or "")).strip()
                    if pt and not _money_snippet_is_amount(pt) and len(pt) < 200:
                        label = _clean_phrase(pt)
                        break
                key = (pg["page"], str(amt), label or "")
                if key in seen:
                    continue
                seen.add(key)
                lines.append({
                    "label": label,
                    "amount": amt,
                    "currency": "EUR",
                    "page": pg["page"],
                    "region": _region_of(cell),
                    "snippet": _clean_phrase(f"{label} | {ct}")[:200] if label else _clean_phrase(ct)[:200],
                })
    # Seitentext wird ZUSAETZLICH zu Tabellen gescannt. Ein frueher Return hier
    # verlor bisher valide Preispositionen ausserhalb einer erkannten Tabelle
    # (z. B. "Fixed per call: 2.226,00 EUR" direkt unter einer Jahrestabelle).
    # Seitentext-Fallback: "<Label> | <Betrag> EUR" oder "<Label>: <Betrag> EUR".
    for pg in pages:
        text = fix_text(pg.get("text") or "")
        patterns = (
            r"([^\n]{5,200}?)\s*\|\s*(\d[\d.,]*)\s*(?:EUR|€)",
            # Conservative prose/colon form; require a commercial unit/period word
            # in the label to avoid turning arbitrary nearby numbers into prices.
            r"([^\n]{5,180}?(?:call|einsatz|zusatzleistung|service|jahr|year|monat|month)[^\n]{0,80}?)\s*:?\s*(\d[\d.,]*)\s*(?:EUR|€)",
        )
        for pattern in patterns:
            for m in re.finditer(pattern, text, flags=re.IGNORECASE):
                amt = _parse_german_amount(m.group(2))
                if amt is None:
                    continue
                label = _clean_phrase(m.group(1))
                key = (pg["page"], str(amt), label.casefold())
                if key in seen:
                    continue
                seen.add(key)
                lines.append({
                    "label": label,
                    "amount": amt,
                    "currency": "EUR",
                    "page": pg["page"],
                    "region": None,
                    "snippet": _clean_phrase(m.group(0))[:200],
                })
    return lines


# =========================================================================
# Public API
# =========================================================================


def _parse_german_amount(raw: str) -> Optional[Decimal]:
    """Parst deutsche Betraege (5.916,67 / 1124.17 / '7.040,84 €')."""
    s = str(raw).strip().replace("\u00a0", " ").replace("\xa0", " ")
    for sym in ("€", "EUR", "$", "£", "CHF", "USD"):
        s = s.replace(sym, "")
    s = s.replace(" ", "").strip()
    if not re.fullmatch(r"[0-9][0-9.,]*", s):
        return None
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


_PAYMENT_START_RE = re.compile(
    r"(\d{1,3})\s*Monate?\s*nach\s*Ablauf\s*der\s*Gew[aä]hrleistung",
    re.IGNORECASE,
)
_ELEMENT_MIN_MONATE_RE = re.compile(r"^\s*(\d{1,4})\s*Monate\s*$", re.IGNORECASE)
_START_EVENT_RE = re.compile(
    r"Vertragsbeginn\s*:\s*([A-Za-zÄÖÜäöüß]{2,40})",
    re.IGNORECASE,
)


def _cell_text(cell) -> str:
    return fix_text(str(cell.get("text") or "")).strip()


def _region_of(cell_or_element) -> Optional[dict]:
    region = cell_or_element.get("region")
    if isinstance(region, dict) and all(
        region.get(k) is not None for k in ("x0", "y0", "x1", "y1")
    ):
        try:
            return {
                "x0": float(region["x0"]),
                "y0": float(region["y0"]),
                "x1": float(region["x1"]),
                "y1": float(region["y1"]),
            }
        except (TypeError, ValueError):
            return None
    return None


def _find_price_table(pages) -> Optional[dict]:
    """Findet die Preis-Tabellen-Zeilen (netto/zzgl-MwSt/brutto) im Kanonischen.

    Nutzt zuerst Tabelle-Zellen (robust), faellt auf Seiten-Regex zurueck.
    Liefert {\"page\", \"net\", \"vat_rate\", \"vat\", \"gross\", \"currency\",
    Regions-Boxen, \"snippet\"} oder None.
    """
    net = vat_rate = vat = gross = None
    net_region = vat_region = gross_region = None
    page = currency = None
    snippets: dict = {}

    for pg in pages:
        found_via_table = False
        for tbl in pg.get("tables") or []:
            cells = [c for c in (tbl.get("cells") or []) if isinstance(c, dict)]
            for i, cell in enumerate(cells):
                t = _cell_text(cell)
                label = t.lower()
                if (
                    "gesamtdienstleistungspreis" in label
                    and "netto" in label
                    and "pro" in label
                    and "monat" in label
                    and net is None
                ):
                    if i + 1 < len(cells):
                        nv = _parse_german_amount(_cell_text(cells[i + 1]))
                        if nv is not None:
                            net, net_region, found_via_table = nv, _region_of(cells[i + 1]), True
                            page = pg["page"]
                            snippets["net"] = f"{t} – {_cell_text(cells[i + 1])}"
                            if "€" in t:
                                currency = "EUR"
                us = re.search(r"zzgl\.?\s*(\d{1,3})\s*%\s*mwst", label)
                if us and i + 1 < len(cells) and vat is None:
                    vr = _parse_german_amount(_cell_text(cells[i + 1]))
                    if vr is not None:
                        vat = vr
                        vat_rate = int(us.group(1))
                        vat_region = _region_of(cells[i + 1])
                        snippets["vat"] = f"{t} – {_cell_text(cells[i + 1])}"
                if re.search(r"brutto\s+pro\s+monat", label) and i + 1 < len(cells) and gross is None:
                    gv = _parse_german_amount(_cell_text(cells[i + 1]))
                    if gv is not None:
                        gross = gv
                        gross_region = _region_of(cells[i + 1])
                        snippets["gross"] = f"{t} – {_cell_text(cells[i + 1])}"
                        if "€" in t:
                            currency = "EUR"
            if found_via_table:
                break
        if found_via_table:
            break

    # Fallback: Seiten-Text (falls Tabellen fehlen/anders strukturiert).
    if net is None or gross is None:
        for pg in pages:
            text = fix_text(pg.get("text") or "")
            m_net = re.search(
                r"Gesamtdienstleistungspreis\s+netto\s+pro\s+Monat[^\d]{0,20}(\d[\d.,]*)",
                text,
            )
            m_vat = re.search(r"zzgl\.?\s*(\d{1,3})\s*%\s*MwSt[^\d]{0,20}(\d[\d.,]*)", text)
            m_gross = re.search(
                r"Gesamtdienstleistungspreis\s+brutto\s+pro\s+Monat[^\d]{0,20}(\d[\d.,]*)",
                text,
            )
            if net is None and m_net:
                net = _parse_german_amount(m_net.group(1))
                if net is not None:
                    page, snippets["net"] = pg["page"], m_net.group(0)
            if vat is None and m_vat:
                vr = _parse_german_amount(m_vat.group(2))
                if vr is not None:
                    vat, vat_rate = vr, int(m_vat.group(1))
                    snippets["vat"] = m_vat.group(0)
            if gross is None and m_gross:
                gross = _parse_german_amount(m_gross.group(1))
                snippets["gross"] = m_gross.group(0)
            if "€" in text:
                currency = "EUR"
            if net is not None and gross is not None:
                break

    if net is None:
        return None
    basis = "gross" if gross is not None and net is None else "net"
    if net is not None and vat is not None and gross is not None:
        basis = "net"
    return {
        "page": page,
        "net": net,
        "vat_rate": vat_rate,
        "vat": vat,
        "gross": gross,
        "currency": currency,
        "basis": basis,
        "net_region": net_region,
        "vat_region": vat_region,
        "gross_region": gross_region,
        "snippets": snippets,
    }


def _find_start_event(pages) -> Optional[str]:
    """Beginn-Ereignis (z. B. „Übergabedatum") aus dem persistierten Text.

    Bewusst ein einzelnes Wort ohne Satzzeichen – „Vertragsbeginn: Zahlungs-
    beginn:" auf Seite 4 wird dadurch NICHT fälschlich erfasst.
    """
    for pg in pages:
        text = fix_text(pg.get("text") or "")
        m = _START_EVENT_RE.search(text)
        if not m:
            continue
        word = m.group(1)
        if word.lower() in ("zahlungsbeginn", "mindest", "mindestlaufzeit", "mindestvertragslaufzeit"):
            continue
        return word
    return None


def _find_payment_start(pages) -> Optional[dict]:
    """Zahlungsbeginn-Regel aus dem persistierten Text (Element/Seite)."""
    for pg in pages:
        for el in pg.get("elements") or []:
            text = fix_text(str(el.get("text") or "")).strip()
            m = _PAYMENT_START_RE.search(text)
            if m:
                return {
                    "rule": m.group(0),
                    "page": pg["page"],
                    "region": _region_of(el),
                    "snippet": text[:200],
                }
    for pg in pages:
        text = fix_text(pg.get("text") or "")
        m = _PAYMENT_START_RE.search(text)
        if m:
            return {"rule": m.group(0), "page": pg["page"], "region": None, "snippet": text[:200]}
    return None


def _find_minimum_duration(pages) -> Optional[dict]:
    """Mindestvertragslaufzeit (Monate) aus dem persistierten Text.

    Bevorzugt ein dediziertes Element (z. B. „96 Monate") auf der Seite, die
    auch das Label „Mindest(vertrags)laufzeit" traegt. Fallback: Seiten-Text
    mit dem LETZTEN numerischen Monats-Token nach dem Label – so ueberspringt
    z. B. „Zahlungsbeginn: 3 Monate nach Ablauf der Gewährleistung" den
    Zahlungsbeginn-Wert und nimmt den Mindestlaufzeit-Wert (96) an.
    """
    for pg in pages:
        label_found = any(
            re.search(r"mindest(?:vertrags)?laufzeit", fix_text(str(e.get("text") or "")).lower())
            for e in pg.get("elements") or []
        )
        if not label_found:
            text = fix_text(pg.get("text") or "")
            label_found = re.search(r"mindest(?:vertrags)?laufzeit", text.lower()) is not None
            if not label_found:
                continue
        for el in pg.get("elements") or []:
            et = fix_text(str(el.get("text") or "")).strip()
            m = _ELEMENT_MIN_MONATE_RE.match(et)
            if m:
                return {
                    "months": int(m.group(1)),
                    "page": pg["page"],
                    "region": _region_of(el),
                    "snippet": et[:200],
                }
        text = fix_text(pg.get("text") or "")
        label_m = re.search(r"mindest(?:vertrags)?laufzeit\s*:", text, re.IGNORECASE)
        if not label_m:
            continue
        # Nach dem Label folgen im Layout ggf. weitere Werte (z. B. „Übergabe-
        # datum 3 Monate nach Ablauf der Gewährleistung 96 Monate"). Der
        # Mindestlaufzeit-Wert ist der LETZTE numerische Monats-Token.
        tail = text[label_m.end():]
        tokens = re.findall(r"(\d{1,4})\s*Monate\b", tail, flags=re.IGNORECASE)
        if not tokens:
            continue
        months = int(tokens[-1])
        return {"months": months, "page": pg["page"], "region": None, "snippet": label_m.group(0)}
    return None


# =========================================================================
# Public API
# =========================================================================


def recover_financial_facts(pages: list[dict]) -> RecoveredFacts:
    """Stellt die Fakten aus den persistenten Seiten deterministisch wieder her."""
    if not pages:
        return RecoveredFacts()

    money = None
    table = _find_price_table(pages)
    if table is not None:
        money = RecoveredMoney(
            monthly_net=table["net"],
            monthly_vat=table["vat"],
            vat_rate=table["vat_rate"],
            monthly_gross=table["gross"],
            currency=table["currency"],
            basis=table["basis"],
            page=table["page"],
            net_region=table["net_region"],
            vat_region=table["vat_region"],
            gross_region=table["gross_region"],
            snippets=table["snippets"],
        )

    laufzeit = None
    start_event = _find_start_event(pages)
    ps = _find_payment_start(pages)
    md = _find_minimum_duration(pages)
    absd = _find_absolute_dates(pages) or {}
    if (
        ps is not None or md is not None or start_event is not None or absd
    ):
        laufzeit = RecoveredLaufzeit(
            start_event=start_event,
            payment_start_rule=ps["rule"] if ps else None,
            payment_start_page=ps["page"] if ps else None,
            payment_start_region=ps["region"] if ps else None,
            payment_start_snippet=ps["snippet"] if ps else None,
            minimum_duration_months=md["months"] if md else None,
            minimum_duration_page=md["page"] if md else None,
            minimum_duration_region=md["region"] if md else None,
            minimum_duration_snippet=md["snippet"] if md else None,
            absolute_start=absd.get("start"),
            absolute_start_page=absd.get("start_page"),
            absolute_start_region=absd.get("start_region"),
            absolute_start_snippet=absd.get("snippet"),
            absolute_end=absd.get("end"),
            absolute_end_page=absd.get("end_page"),
            absolute_end_region=absd.get("end_region"),
            absolute_end_snippet=absd.get("snippet"),
            duration_years=absd.get("duration_years"),
            duration_page=absd.get("duration_page"),
            duration_region=absd.get("duration_region"),
            duration_snippet=absd.get("duration_snippet"),
            auto_renewal=absd.get("auto_renewal"),
            auto_renewal_page=absd.get("auto_renewal_page"),
            auto_renewal_region=absd.get("auto_renewal_region"),
            auto_renewal_snippet=absd.get("auto_renewal_snippet"),
        )

    identity = None
    num = _find_contract_number(pages)
    title = _find_title(pages)
    sysid = _find_system_identity(pages)
    if num is not None or title is not None or sysid is not None:
        identity = RecoveredIdentity(
            contract_number=num["number"] if num else None,
            contract_number_page=num["page"] if num else None,
            contract_number_region=num["region"] if num else None,
            contract_number_snippet=num["snippet"] if num else None,
            title=title["title"] if title else None,
            title_page=title["page"] if title else None,
            title_region=title["region"] if title else None,
            title_snippet=title["snippet"] if title else None,
            system_identity=sysid["system"] if sysid else None,
            system_identity_page=sysid["page"] if sysid else None,
            system_identity_region=sysid["region"] if sysid else None,
            system_identity_snippet=sysid["snippet"] if sysid else None,
        )

    cost_lines = [
        RecoveredCostLine(
            label=cl.get("label"),
            amount=cl.get("amount"),
            currency=cl.get("currency"),
            page=cl.get("page"),
            region=cl.get("region"),
            snippet=cl.get("snippet"),
        )
        for cl in _find_cost_lines(pages)
    ]

    if money is None and laufzeit is None and identity is None and not cost_lines:
        return RecoveredFacts()
    return RecoveredFacts(
        money=money, laufzeit=laufzeit, identity=identity, cost_lines=cost_lines
    )