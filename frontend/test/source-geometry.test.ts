import { describe, expect, it } from "vitest";
import {
  A4_POINTS,
  bboxPageFraction,
  evidencePrecision,
  resolveEvidenceRect,
} from "@/lib/source-geometry";

describe("source-geometry: Ehrliche Geometrie (UAT Defect D)", () => {
  it("rechnet pdf_points korrekt in Canvas-Pixel um", () => {
    const r = resolveEvidenceRect(
      { x0: 100, y0: 200, x1: 160, y1: 260 },
      "pdf_points",
      2,
      { width: 1190, height: 1684 }
    );
    expect(r).toEqual({ x: 200, y: 400, width: 120, height: 120 });
  });

  it("rechnet normalized-Koordinaten gegen die Seitengröße", () => {
    const r = resolveEvidenceRect(
      { x0: 0.1, y0: 0.2, x1: 0.5, y1: 0.35 },
      "normalized",
      1,
      { width: 1000, height: 800 }
    );
    expect(r).not.toBeNull();
    expect(r!.x).toBeCloseTo(100);
    expect(r!.y).toBeCloseTo(160);
    expect(r!.width).toBeCloseTo(400);
    expect(r!.height).toBeCloseTo(120);
  });

  it("liefert null bei ungültiger/fehlender bbox (nichts erfinden)", () => {
    expect(
      resolveEvidenceRect({ x0: -5, y0: 0, x1: 1, y1: 10 }, "pdf_points", 1, {
        width: 100,
        height: 100,
      })
    ).toBeNull();
    expect(
      resolveEvidenceRect({ x0: 10, y0: 20, x1: 5, y1: 30 }, "pdf_points", 1, {
        width: 100,
        height: 100,
      })
    ).toBeNull();
  });

  it("stuft eine seitenfüllende Region als 'coarse' ein (MEDTRON-Fall)", () => {
    // Nahezu die ganze Seite (89.6..543.9 x 69.2..725.2 von A4) -> nur ungefähr.
    const frac = bboxPageFraction(
      { x0: 89.6566, y0: 69.1639, x1: 543.8618, y1: 725.1515 },
      "pdf_points"
    );
    expect(frac).toBeGreaterThan(0.5);
    expect(frac).toBeGreaterThanOrEqual(0.3);
    expect(
      evidencePrecision(
        { x0: 89.6566, y0: 69.1639, x1: 543.8618, y1: 725.1515 },
        "pdf_points"
      )
    ).toBe("coarse");
  });

  it("stuft eine schmale Wort-Region als 'exact' ein", () => {
    expect(
      evidencePrecision({ x0: 100, y0: 200, x1: 160, y1: 212 }, "pdf_points")
    ).toBe("exact");
    expect(
      evidencePrecision({ x0: 0.5, y0: 0.5, x1: 0.55, y1: 0.515 }, "normalized")
    ).toBe("exact");
  });

  it("stuft eine volle Seite im normalized-Raum als 'coarse' ein", () => {
    expect(evidencePrecision({ x0: 0, y0: 0, x1: 1, y1: 1 }, "normalized")).toBe("coarse");
  });

  it("liefert 'none' ohne gültige Geometrie (keine erfundene Hervorhebung)", () => {
    expect(evidencePrecision(null, "pdf_points")).toBe("none");
    expect(
      evidencePrecision({ x0: -1, y0: 0, x1: 5, y1: 2 }, "pdf_points")
    ).toBe("none");
  });

  it("respektiert echte Seitenmaße statt des A4-Rückfalls", () => {
    // Auf einer kleinen Seite ist 120x120 pt bereits 60% der Fläche -> coarse.
    const smallPage = { width: 200, height: 120 };
    expect(
      evidencePrecision({ x0: 40, y0: 10, x1: 160, y1: 130 }, "pdf_points", smallPage)
    ).toBe("coarse");
    expect(A4_POINTS.width).toBeGreaterThan(A4_POINTS.height / 2);
  });
});