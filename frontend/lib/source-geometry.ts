import type { EvidenceBbox } from "@/lib/contract-detail-types";

export interface SourceRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/**
 * A4-Seitenpunkte (595.28 x 841.89) als Rückfall für die Ehrlichkeits-Klassi-
 * fizierung, wo keine echten gerenderten Seitenmaße vorliegen (lib/evidence.ts).
 * Bedarf: ein Beleg, dessen Region fast die ganze Seite ausfüllt, darf nicht
 * als exakte Position suggeriert werden.
 */
export const A4_POINTS = { width: 595.28, height: 841.89 };

/**
 * Abgedeckter Seitenanteil einer Bbox (0..1) gegen die Seitenmaße in Punkten
 * (bzw. [0,1]-Raum bei `normalized`). Liefert `null`, wenn nicht bestimmbar.
 */
export function bboxPageFraction(
  bbox: EvidenceBbox | null | undefined,
  bboxSpace: "pdf_points" | "normalized",
  pagePoints: { width: number; height: number } = A4_POINTS
): number | null {
  if (
    !bbox ||
    pagePoints.width <= 0 ||
    pagePoints.height <= 0 ||
    !Number.isFinite(bbox.x0) ||
    !Number.isFinite(bbox.y0) ||
    !Number.isFinite(bbox.x1) ||
    !Number.isFinite(bbox.y1) ||
    bbox.x1 < bbox.x0 ||
    bbox.y1 < bbox.y0 ||
    bbox.x0 < 0 ||
    bbox.y0 < 0
  ) {
    return null;
  }
  const w = bboxSpace === "pdf_points" ? pagePoints.width : 1;
  const h = bboxSpace === "pdf_points" ? pagePoints.height : 1;
  return ((bbox.x1 - bbox.x0) * (bbox.y1 - bbox.y0)) / (w * h);
}

export type EvidencePrecision = "exact" | "coarse" | "none";

/**
 * Ehrliche Geometrie-Einstufung:
 * - `none`: keine bbox/seite -> KEINE Hervorhebung zeichnen.
 * - `exact`: schmale, vertrauenswuerdige Region -> präzise Hervorhebung.
 * - `coarse`: Region deckt fast die ganze Seite ab -> nur "ungefähre Lage".
 * Eine seitenfuellende Bbox (z. B. Element-/Seiten-Ebene) wird NIE als
 * exakte Position dargestellt – nichts wird erfunden oder übertrieben.
 */
export function evidencePrecision(
  bbox: EvidenceBbox | null | undefined,
  bboxSpace: "pdf_points" | "normalized",
  pagePoints: { width: number; height: number } = A4_POINTS
): EvidencePrecision {
  const frac = bboxPageFraction(bbox, bboxSpace, pagePoints);
  if (frac == null) return "none";
  return frac >= 0.3 ? "coarse" : "exact";
}

/**
 * Wandelt eine Quellen-Bbox in Canvas-Pixel um.
 * - `pdf_points`: echte Benchmark-Bboxen in PDF-Punkten der Original-Seite
 *   (Ursprung oben links, y nach unten). Canvas wird mit `scale` gerendert
 *   (siehe PdfViewer), also Pixel = pt * scale. Keine erfundenen [0,1]-Werte.
 * - `normalized` / beides: Koordinaten in [0,1] der Seite -> * Seitengroesse.
 * Gibt `null` zurueck, wenn kein g�ltiger beidseitiger Raum vorliegt.
 */
export function resolveEvidenceRect(
  bbox: EvidenceBbox,
  bboxSpace: "pdf_points" | "normalized",
  scale: number,
  dims: { width: number; height: number }
): SourceRect | null {
  if (
    !Number.isFinite(bbox.x0) ||
    !Number.isFinite(bbox.y0) ||
    !Number.isFinite(bbox.x1) ||
    !Number.isFinite(bbox.y1) ||
    bbox.x1 < bbox.x0 ||
    bbox.y1 < bbox.y0 ||
    bbox.x0 < 0 ||
    bbox.y0 < 0
  ) {
    return null;
  }
  if (bboxSpace === "pdf_points") {
    return {
      x: bbox.x0 * scale,
      y: bbox.y0 * scale,
      width: (bbox.x1 - bbox.x0) * scale,
      height: (bbox.y1 - bbox.y0) * scale,
    };
  }
  return {
    x: bbox.x0 * dims.width,
    y: bbox.y0 * dims.height,
    width: (bbox.x1 - bbox.x0) * dims.width,
    height: (bbox.y1 - bbox.y0) * dims.height,
  };
}
