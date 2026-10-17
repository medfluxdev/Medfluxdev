import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EvidenceReviewMode from "@/components/contracts/detail/EvidenceReviewMode";
import { evidenceNumbers, factsByEvidence } from "@/components/contracts/detail/EvidencePane";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";

const api = vi.hoisted(() => ({ reviewContractFact: vi.fn() }));
vi.mock("@/lib/domain-api/contracts", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/contracts")>()),
  reviewContractFact: api.reviewContractFact,
}));

const ref = (id: string, page: number, field: string, snippet: string): EvidenceRef => ({
  evidence_id: id, field_ref: field, document_version_id: "doc-1", original_filename: "Full-Service-Vertrag.pdf", page,
  source_type: "page", paragraph_index: null, table_index: null, snippet, confidence: 0.9, requires_review: true,
  bbox: { x0: 10, y0: 10, x1: 60, y1: 20 }, precision: "line", geometry_normalized: false, bbox_space: "pdf_points", supports_exact_navigation: true,
} as EvidenceRef);
const fact = (key: string, label: string, value: string, ids: string[], state = "unreviewed"): FactReviewStateDto => ({
  fact_key: key, label_de: label, present: true, state, state_label_de: state, original_value: value, effective_value: value,
  reviewer_display_name: null, reviewer_identity_type: null, reviewed_at: null, evidence_ref: null, has_history: false,
  evidence_count: ids.length, linked_evidence: [], linked_evidence_refs: ids, needs_evidence: false, is_critical: false,
} as FactReviewStateDto);

const EVIDENCE = [ref("e1", 1, "identity.customer", "Krankenhaus Nordwest GmbH Frankfurt"), ref("e2", 2, "dates.start_date", "beginnt am 01.04.2025")];
const FACTS = [fact("identity.customer", "Auftraggeber", "Krankenhaus Nordwest GmbH Frankfurt", ["e1"]), fact("dates.start_date", "Vertragsbeginn", "01.04.2025", ["e2"])];

function renderMode(overrides: Partial<Parameters<typeof EvidenceReviewMode>[0]> = {}) {
  const props = {
    contractId: "c-1", orgSlug: "test-klinik", evidence: EVIDENCE, numbers: evidenceNumbers(EVIDENCE), factByEvidence: factsByEvidence(FACTS),
    startId: null, canReview: true, viewer: <div>Original</div>, onShow: vi.fn(), onExit: vi.fn(), onReload: vi.fn(), ...overrides,
  };
  return { ...render(<EvidenceReviewMode {...props} />), props };
}

describe("Nachweise prüfen (geführt)", () => {
  beforeEach(() => { vi.clearAllMocks(); api.reviewContractFact.mockResolvedValue({}); });

  it("zeigt Nachweis, erkannte Angabe; „Stimmt überein · Weiter“ bestätigt und geht weiter", async () => {
    const user = userEvent.setup();
    const { container, props } = renderMode();
    const card = screen.getByRole("region", { name: "Aktueller Nachweis" });
    expect(within(card).getByText("1 / 2")).toBeInTheDocument();
    expect(within(card).getByRole("heading", { name: /Auftraggeber/ })).toBeInTheDocument();
    expect(within(card).getByText("Noch nicht geprüft")).toBeInTheDocument();
    expect(within(card).getByText("Krankenhaus Nordwest GmbH Frankfurt")).toBeInTheDocument();
    expect(props.onShow).toHaveBeenCalledWith(EVIDENCE[0]);
    expect(await axe(container)).toHaveNoViolations();

    await user.click(within(card).getByRole("button", { name: /Stimmt überein · Weiter/ }));
    expect(api.reviewContractFact).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "identity.customer", action: "confirmed", evidence_ref: "e1" }));
    await waitFor(() => expect(within(card).getByRole("heading", { name: /Vertragsbeginn/ })).toBeInTheDocument());
    expect(props.onReload).toHaveBeenCalled();
    expect(screen.getByText("2 von 2 Nachweisen")).toBeInTheDocument();
  });

  it("„Abweichung melden“ verlangt eine Begründung und speichert die Korrektur", async () => {
    const user = userEvent.setup();
    renderMode();
    await user.click(screen.getByRole("button", { name: "Abweichung melden" }));
    const submit = screen.getByRole("button", { name: "Korrigieren · Weiter" });
    expect(submit).toBeDisabled();
    await user.clear(screen.getByLabelText("Richtiger Wert"));
    await user.type(screen.getByLabelText("Richtiger Wert"), "Krankenhaus Nordwest gGmbH");
    await user.type(screen.getByLabelText("Was weicht ab?"), "Rechtsform falsch erkannt");
    await user.click(submit);
    expect(api.reviewContractFact).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({
      action: "corrected", corrected_value: "Krankenhaus Nordwest gGmbH", note: "Rechtsform falsch erkannt",
    }));
  });

  it("Überspringen bis zum Ende zeigt die Zusammenfassung; Escape beendet", async () => {
    const user = userEvent.setup();
    const { props } = renderMode();
    await user.click(screen.getByRole("button", { name: /Überspringen/ }));
    await user.click(screen.getByRole("button", { name: /Überspringen/ }));
    expect(screen.getByRole("heading", { name: "Alle Nachweise durchgesehen" })).toBeInTheDocument();
    expect(screen.getByText("2 noch offen")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(props.onExit).toHaveBeenCalled();
  });

  it("ohne Prüfrecht nur lesen und weiterblättern", () => {
    renderMode({ canReview: false });
    expect(screen.queryByRole("button", { name: /Stimmt überein/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Weiter/ })).toBeInTheDocument();
    expect(screen.getByText(/Nur Lesen/)).toBeInTheDocument();
  });
});
