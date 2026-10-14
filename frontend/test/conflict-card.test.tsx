import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ConflictCard from "@/components/contracts/detail/ConflictCard";
import type { DetailWarning, FactReviewStateDto } from "@/lib/contract-detail-types";

const apiPostMock = vi.fn();
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error { status = 0; },
  apiPost: (...args: unknown[]) => apiPostMock(...args),
}));

const warning: DetailWarning = {
  warning_type: "calculation_conflict", severity: "high", title_de: "Berechnungskonflikt", target_kind: "contract_end",
  target_date: null, days_remaining: null, requires_action: false, requires_review: true, action_state: null,
  conflict: {
    topic: "contract_end", title_de: "Widerspruch beim Vertragsende", question_de: "Welches Vertragsende gilt?",
    explanation_de: "Im Dokument steht als Vertragsende der 31.03.2029. Aus Vertragsbeginn und Laufzeit ergibt sich der 05.05.2029 – 35 Tage Unterschied.",
    fact_key: "dates.end_date",
    options: [
      { key: "document", label_de: "Laut Dokument", value: "2029-03-31", detail_de: "Ausdrücklich im Vertrag genannt", fact_keys: ["dates.end_date"] },
      { key: "calculated", label_de: "Aus Beginn + Laufzeit", value: "2029-05-05", detail_de: "05.05.2025 + 4 Jahre", fact_keys: ["dates.start_date"] },
    ],
  },
};
const endFact = { fact_key: "dates.end_date", original_value: "2029-03-31", reviewed_at: null, linked_evidence_refs: [] } as unknown as FactReviewStateDto;

function renderCard(saved = vi.fn()) {
  render(<ConflictCard contractId="c1" orgSlug="klinik" warnings={[warning]} facts={new Map([["dates.end_date", endFact]])} evidence={[]} canDecide onOpenEvidence={() => {}} onOpenTarget={() => {}} onSaved={saved} />);
  return saved;
}

beforeEach(() => apiPostMock.mockReset().mockResolvedValue({}));

describe("Widerspruch klären", () => {
  it("zeigt beide Werte mit Herkunft und den Unterschied", () => {
    renderCard();
    expect(screen.getByRole("heading", { name: "Widerspruch klären" })).toBeInTheDocument();
    expect(screen.getByText("Welches Vertragsende gilt?")).toBeInTheDocument();
    expect(screen.getByText("31.03.2029")).toBeInTheDocument();
    expect(screen.getByText("05.05.2029")).toBeInTheDocument();
    expect(screen.getByText("05.05.2025 + 4 Jahre")).toBeInTheDocument();
    expect(screen.getByText(/35 Tage Unterschied/)).toBeInTheDocument();
  });

  it("Dokument-Wert gilt = Bestätigung; berechneter Wert = Korrektur", async () => {
    const user = userEvent.setup();
    const saved = renderCard();
    const buttons = screen.getAllByRole("button", { name: "Dieses Datum gilt" });
    await user.click(buttons[0]);
    await waitFor(() => expect(apiPostMock).toHaveBeenLastCalledWith(expect.stringContaining("/fact-reviews"), expect.objectContaining({ fact_key: "dates.end_date", action: "confirmed" })));
    await user.click(buttons[1]);
    await waitFor(() => expect(apiPostMock).toHaveBeenLastCalledWith(expect.stringContaining("/fact-reviews"), expect.objectContaining({ action: "corrected", corrected_value: "2029-05-05" })));
    expect(saved).toHaveBeenCalled();
  });

  it("ohne offenen Widerspruch nichts", () => {
    const { container } = render(<ConflictCard contractId="c1" orgSlug="klinik" warnings={[{ ...warning, requires_review: false }]} facts={new Map()} evidence={[]} canDecide onOpenEvidence={() => {}} onOpenTarget={() => {}} onSaved={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
