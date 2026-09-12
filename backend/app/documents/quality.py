"""Dokumentqualität / Textextraktions-Klassifikation für Medflux (Schritt 5/Benchmark v2).

Trennt DETERMINISTISCH die Qualität der Textschicht eines Dokuments von der
KI-Semantik-Extraktion: PDF → native Textschicht prüfen → native_text /
partial_text / scanned_image / unreadable. Grundlage für die spätere
Weiterleitung (native Extraktion vs. lokaler OCR-Fallback) und für das
Vermeiden von „OCR-Fehler = KI-Fehler“-Fehlschlüssen im Benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Eine Seite zählt als „mit sinnvollem nativen Text“, wenn sie mindestens so
# viele nicht-leere Zeichen enthält (deckt sich mit TEXT_POOR_THRESHOLD im
# PDF-Extraktor: darunter -> als gescannt/OCR-bedürftig eingestuft).
MEANINGFUL_THRESHOLD = 50

# Klassifikations-Schwellwerte (tunable, deterministisch).
NATIVE_MIN_COVERAGE = 0.85      # Anteil Seiten mit sinnvollem Text
NATIVE_MIN_DENSITY = 250        # durchschnittl. substanzielle Zeichen/Seite
NATIVE_MIN_TOTAL = 2000         # Gesamtzeichen für „vollständige“ Schicht
TOTAL_SCANNED_MAX = 250         # darunter gilt die Textschicht als nicht vorhanden


DOC_NATIVE = "native_text"
DOC_PARTIAL = "partial_text"
DOC_SCANNED = "scanned_image"
DOC_UNREADABLE = "unreadable/error"


@dataclass
class PageStat:
    """Statistik einer einzelnen Seite (native Textschicht)."""

    page_number: int
    substantive_chars: int = 0
    raw_chars: int = 0
    image_count: int = 0
    text_blocks: int = 0

    @property
    def meaningful(self) -> bool:
        return self.substantive_chars >= MEANINGFUL_THRESHOLD


@dataclass
class DocumentQuality:
    """Ergebnis der Qualitätsprüfung eines Dokuments."""

    filename: str
    page_count: int
    native_text_char_count: int
    meaningful_pages: int
    coverage_ratio: float
    pages_needing_ocr: list[int]
    classification: str
    extraction_warnings: list[str]
    recommended_processing_path: str
    pages: list[PageStat] = field(default_factory=list)
    avg_text_blocks: float = 0.0
    avg_images_per_page: float = 0.0


def _substantive_count(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def recommended_path(classification: str) -> str:
    return {
        DOC_NATIVE: "native_extraction",
        DOC_PARTIAL: "native_plus_ocr_fallback",
        DOC_SCANNED: "full_ocr_required",
        DOC_UNREADABLE: "manual_review",
    }.get(classification, "manual_review")


def classify_pages(
    filename: str,
    page_stats: list[PageStat],
    open_error: str | None = None,
) -> DocumentQuality:
    """Klassifiziert ein Dokument anhand seiner nativen Textschicht.

    `page_stats` je Seite (page_number 1-basiert). Kein PDF-/KI-Aufwand –
    rein deterministisch, testbar.
    """
    if open_error or not page_stats:
        return DocumentQuality(
            filename=filename,
            page_count=len(page_stats),
            native_text_char_count=0,
            meaningful_pages=0,
            coverage_ratio=0.0,
            pages_needing_ocr=[],
            classification=DOC_UNREADABLE,
            extraction_warnings=[open_error or "Keine Seiten gelesen."],
            recommended_processing_path=recommended_path(DOC_UNREADABLE),
        )

    total = sum(p.substantive_chars for p in page_stats)
    meaningful = sum(1 for p in page_stats if p.meaningful)
    coverage = meaningful / len(page_stats)
    density = total / len(page_stats)
    blocks = [p.text_blocks for p in page_stats]

    warnings: list[str] = []
    needs_ocr = [p.page_number for p in page_stats if not p.meaningful]

    if total <= TOTAL_SCANNED_MAX or meaningful == 0:
        classification = DOC_SCANNED
        warnings.append(
            "Keine nennenswerte native Textschicht – Dokument ist gescannt/Bild."
        )
    elif coverage >= NATIVE_MIN_COVERAGE and density >= NATIVE_MIN_DENSITY \
            and total >= NATIVE_MIN_TOTAL:
        classification = DOC_NATIVE
    elif coverage >= NATIVE_MIN_COVERAGE and density < NATIVE_MIN_DENSITY:
        classification = DOC_PARTIAL
        warnings.append(
            "Hohe Seitenabdeckung, aber geringe Textdichte – vorwiegend "
            "Kopf-/Metadaten-Fragmente statt Volltext."
        )
    elif coverage >= NATIVE_MIN_COVERAGE and total < NATIVE_MIN_TOTAL:
        classification = DOC_PARTIAL
        warnings.append(
            "Hohe Seitenabdeckung, aber zu wenig Gesamttext für einen "
            "vollständigen Vertrag."
        )
    else:
        classification = DOC_PARTIAL
        warns = [f"{(1 - coverage) * 100:.0f}% der Seiten ohne sinnvollen Text."]
        if needs_ocr:
            warns.append(
                f"{len(needs_ocr)} Seite(n) textarm: {needs_ocr[:8]} – "
                "OCR-Fallback erforderlich."
            )
        warnings.extend(warns)

    if needs_ocr:
        warnings.append(
            f"{len(needs_ocr)} Seite(n) unter Schwelle "
            f"({MEANINGFUL_THRESHOLD} Zeichen) → lokaler OCR-Kandidat."
        )

    return DocumentQuality(
        filename=filename,
        page_count=len(page_stats),
        native_text_char_count=total,
        meaningful_pages=meaningful,
        coverage_ratio=round(coverage, 3),
        pages_needing_ocr=needs_ocr,
        classification=classification,
        extraction_warnings=warnings,
        recommended_processing_path=recommended_path(classification),
        pages=page_stats,
        avg_text_blocks=(sum(blocks) / len(blocks)) if blocks else 0.0,
        avg_images_per_page=sum(p.image_count for p in page_stats) / len(page_stats) if page_stats else 0.0,
    )


def page_stat_from_text(
    page_number: int,
    text: str,
    image_count: int = 0,
    text_blocks: int = 0,
) -> PageStat:
    return PageStat(
        page_number=page_number,
        substantive_chars=_substantive_count(text),
        raw_chars=len(text),
        image_count=image_count,
        text_blocks=text_blocks,
    )