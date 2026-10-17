import userEvent from "@testing-library/user-event";
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
    expect(screen.getAllByText(/KI 83 %/).length).toBeGreaterThan(0);
    expect(screen.getByText("Nur Seite")).toBeInTheDocument();
    expect(screen.getByText(/keine Position auf der Seite/)).toBeInTheDocument();
  });

  it("blendet ungültige Konfidenzwerte aus", () => {
    render(<EvidencePane evidence={[evidence({ confidence: 1.2 })]} activeEvidenceId={null} onNavigate={vi.fn()} />);
    expect(screen.queryByText(/KI \d+ %/)).not.toBeInTheDocument();
  });
});

describe("Nachweise – Prüfstand und lesbare Titel", () => {
  it("benennt Nachweise nach der Prüf-Angabe, zeigt den Stand und filtert „Zu prüfen“", async () => {
    const fact = (key: string, label: string, state: string, ids: string[]) => ({ fact_key: key, label_de: label, present: true, state, state_label_de: state, original_value: "x", effective_value: "x", reviewer_display_name: null, reviewer_identity_type: null, reviewed_at: null, evidence_ref: null, has_history: false, evidence_count: ids.length, linked_evidence: [], linked_evidence_refs: ids, needs_evidence: false, is_critical: false });
    const user = userEvent.setup();
    render(<EvidencePane
      evidence={[evidence({ evidence_id: "a", field_ref: "costs.cost_line.7" }), evidence({ evidence_id: "b", field_ref: "dates.start_date" })]}
      facts={[fact("dates.start_date", "Vertragsbeginn", "confirmed", ["b"])]}
      activeEvidenceId={null} onNavigate={vi.fn()} />);
    expect(screen.getByRole("button", { name: /Kostenposition 8/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Nachweis \d+ Vertragsbeginn/ })).toHaveTextContent("Geprüft");
    await user.selectOptions(screen.getByRole("combobox", { name: "Prüfstand" }), "done");
    expect(screen.queryByRole("button", { name: /Kostenposition/ })).not.toBeInTheDocument();
    expect(screen.getByText("1 von 2 Nachweisen")).toBeInTheDocument();
  });
});
