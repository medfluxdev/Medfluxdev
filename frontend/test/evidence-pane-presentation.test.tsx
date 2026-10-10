import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import EvidencePane from "@/components/contracts/detail/EvidencePane";
import type { EvidenceRef } from "@/lib/contract-detail-types";

function evidence(overrides: Partial<EvidenceRef> = {}): EvidenceRef {
  return {
    evidence_id: "ev-1",
    field_ref: "dates.start_date",
    document_version_id: "doc-1",
    original_filename: "vertrag.pdf",
    page: 2,
    paragraph_index: null,
    table_index: null,
    source_type: "page",
    snippet: "Vertragsbeginn 01.01.2026",
    confidence: 0.83,
    requires_review: false,
    bbox: null,
    precision: "none",
    geometry_normalized: false,
    bbox_space: "pdf_points",
    supports_exact_navigation: false,
    ...overrides,
  };
}

describe("Nachweise – ehrliche Präsentation", () => {
  it("zeigt gültige Konfidenz, aber keine erfundene exakte Position", () => {
    render(<EvidencePane evidence={[evidence()]} activeEvidenceId={null} onNavigate={vi.fn()} />);
    expect(screen.getAllByText(/KI-Konfidenz 83 %/).length).toBeGreaterThan(0);
    expect(screen.getByText("Seite, ohne Position")).toBeInTheDocument();
    expect(screen.getByText(/ohne exakte Position/)).toBeInTheDocument();
  });

  it("blendet ungültige Konfidenzwerte aus", () => {
    render(<EvidencePane evidence={[evidence({ confidence: 1.2 })]} activeEvidenceId={null} onNavigate={vi.fn()} />);
    expect(screen.queryByText(/Konfidenz/)).not.toBeInTheDocument();
  });
});
