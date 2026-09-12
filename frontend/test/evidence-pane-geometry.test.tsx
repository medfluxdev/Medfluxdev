import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import EvidencePane from "@/components/contracts/detail/EvidencePane";
import type { EvidenceRef } from "@/lib/contract-detail-types";

function ref(overrides: Partial<EvidenceRef>): EvidenceRef {
  return {
    evidence_id: "e-1",
    field_ref: "costs.annual_cost",
    document_version_id: "dv-1",
    original_filename: "wartung.pdf",
    page: 2,
    paragraph_index: null,
    table_index: null,
    source_type: "paragraph",
    snippet: "Jährliche Vergütung 12.000 EUR.",
    confidence: 0.9,
    requires_review: false,
    bbox: { x0: 50, y0: 80, x1: 250, y1: 120 },
    precision: "coarse",
    geometry_normalized: false,
    bbox_space: "pdf_points",
    supports_exact_navigation: true,
    ...overrides,
  };
}

function renderPane(items: EvidenceRef[]) {
  return render(
    <EvidencePane evidence={items} activeEvidenceId={null} onNavigate={() => {}} />
  );
}

describe("EvidencePane: Ehrliche Geometrie-Auszeichnung (UAT Defect D)", () => {
  it("kennzeichnet eine seitenfüllende Region als 'Ungefähre Lage'", () => {
    const { container } = renderPane([
      ref({
        evidence_id: "coarse",
        // Nahezu die ganze A4-Seite -> nur ungefähr lokalisiert.
        bbox: { x0: 89.66, y0: 69.16, x1: 543.86, y1: 725.15 },
      }),
    ]);
    expect(screen.getByText("Ungefähre Lage")).toBeInTheDocument();
    expect(
      screen.getByText(
        /Seitenbereich grob markiert – die Quelle ist dort nur ungefähr/
      )
    ).toBeInTheDocument();
    expect(container.textContent).not.toContain("Positionsbestimmt");
  });

  it("behält 'Positionsbestimmt' für eine schmale, vertrauenswürdige Region", () => {
    renderPane([
      ref({ evidence_id: "exact", bbox: { x0: 100, y0: 200, x1: 160, y1: 212 } }),
    ]);
    expect(screen.queryByText("Ungefähre Lage")).not.toBeInTheDocument();
    expect(screen.getByText("Positionsbestimmt")).toBeInTheDocument();
  });

  it("differenziert Seite-ohne-Position und Ohne-Positionsangabe ehrlich", () => {
    renderPane([
      ref({ evidence_id: "page-only", page: 3, bbox: null, supports_exact_navigation: false }),
      ref({ evidence_id: "no-page", page: null, bbox: null, supports_exact_navigation: false }),
    ]);
    expect(screen.getByText("Seite, ohne Position")).toBeInTheDocument();
    expect(screen.getByText("Ohne Positionsangabe")).toBeInTheDocument();
  });

  it("stellt Quellenangaben ohne erfundene Hervorhebung dar (Kontext sichtbar)", () => {
    const { container } = renderPane([
      ref({
        evidence_id: "coarse",
        bbox: { x0: 89.66, y0: 69.16, x1: 543.86, y1: 725.15 },
      }),
    ]);
    const list = container.querySelector(".evidence-list");
    expect(within(list as HTMLElement).getByText(/12\.000 EUR/)).toBeInTheDocument();
  });
});