import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractRenewalBrief from "@/components/contracts/detail/ContractRenewalBrief";
import RenewalOverview from "@/components/deadlines/RenewalOverview";
import type { RenewalBrief } from "@/lib/domain-api/registerGrid";

const api = vi.hoisted(() => ({
  getRenewalBrief: vi.fn(),
  getRenewalSummary: vi.fn(),
  listRenewals: vi.fn(),
  createContractLifecycleDecision: vi.fn(),
}));

vi.mock("@/lib/domain-api/registerGrid", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/registerGrid")>()),
  getRenewalBrief: api.getRenewalBrief,
  getRenewalSummary: api.getRenewalSummary,
  listRenewals: api.listRenewals,
}));
vi.mock("@/lib/domain-api/lifecycle", () => ({ createContractLifecycleDecision: api.createContractLifecycleDecision }));

function brief(overrides: Partial<RenewalBrief> = {}): RenewalBrief {
  return {
    contract_id: "c-1", register_number: "000001", short_description: "Wartung CT", business_status: "gueltig",
    term_model: "Automatische Verlängerung", as_of: "2026-08-15", urgency: "soon", days_left: 46,
    cancel_by: "2026-09-30", current_end: "2026-12-31", next_end_if_no_action: "2027-12-31",
    if_no_action: "Ohne Kündigung bis 30.09.2026 verlängert sich der Vertrag um 1 Jahr bis 31.12.2027.",
    annual_cost: "12000.00", renewal_cost: "12360.00", price_adjustment_notes: [], partner: "MEDTEC",
    partner_contracts: [{ contract_id: "c-2", register_number: "000002", short_description: "Wartung MRT" }],
    responsible: "Admin", reminder_recipient: null, documents: 1, review_pending: false, open_deadlines: [],
    decision: null,
    hints: [
      { kind: "action", text: "Bis 30.09.2026 entscheiden: verlängern, neu verhandeln oder kündigen.", reason: "Noch 46 Tage." },
      { kind: "info", text: "Bei Verlängerung entstehen bis 31.12.2027 voraussichtlich 12.360,00 € (netto).", reason: "Hochrechnung." },
    ],
    explanation: [],
    ...overrides,
  };
}

describe("Entscheidungsvorlage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRenewalBrief.mockResolvedValueOnce(brief()).mockResolvedValue(brief({
      hints: [], decision: { id: "d-1", decision: "renegotiate", label: "Neu verhandeln", status: "planned", note: "Angebot einholen", by: "Admin", at: "2026-08-15T10:00:00Z" },
    }));
    api.createContractLifecycleDecision.mockResolvedValue({});
  });

  it("zeigt Fakten, begründete Hinweise und erfasst eine Entscheidung nur auf Klick", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContractRenewalBrief contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("Bald (≤ 90 Tage)")).toBeInTheDocument();
    expect(screen.getByText("noch 46 Tage")).toBeInTheDocument();
    expect(screen.getByText(/verlängert sich der Vertrag um 1 Jahr/)).toBeInTheDocument();
    expect(screen.getByText("Grundlage: Hochrechnung.")).toBeInTheDocument();
    api.getRenewalSummary.mockResolvedValue({ available: true, text: "Der Vertrag ist bis 30.09.2026 kündbar.", message: null, model: "qwen3:8b" });
    await user.click(screen.getByRole("button", { name: "Kurzfassung mit lokaler KI" }));
    expect(await screen.findByText("Der Vertrag ist bis 30.09.2026 kündbar.")).toBeInTheDocument();
    expect(screen.getByText(/Lokale KI \(qwen3:8b\)/)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    expect(api.createContractLifecycleDecision).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Neu verhandeln" }));
    await user.type(screen.getByLabelText("Begründung (optional)"), "Angebot einholen");
    await user.click(screen.getByRole("button", { name: "Entscheidung erfassen" }));
    await waitFor(() => expect(api.createContractLifecycleDecision).toHaveBeenCalledWith("test-klinik", "c-1", { decision: "renegotiate", status: "planned", note: "Angebot einholen" }));
    expect(await screen.findByText(/Neu verhandeln \(geplant\)/)).toBeInTheDocument();
  });

  it("listet anstehende Fristen mit offenem Entscheidungsstand", async () => {
    api.listRenewals.mockResolvedValue({ as_of: "2026-08-15", days: 120, items: [
      { contract_id: "c-1", register_number: "000001", short_description: "Wartung CT", partner: "MEDTEC", cancel_by: "2026-09-30", days_left: 46, urgency: "soon", possible_end: "2026-12-31", annual_cost: "12000.00", responsible: "Admin", decision: null },
    ] });
    const user = userEvent.setup();
    render(<RenewalOverview organizationSlug="test-klinik" />);
    const row = (await screen.findByRole("rowheader", { name: /000001/ })).closest("tr")!;
    expect(within(row).getByText("offen")).toBeInTheDocument();
    expect(screen.getByText("1 Verträge · 1 ohne erfasste Entscheidung")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Zeitraum"), "365");
    await waitFor(() => expect(api.listRenewals).toHaveBeenLastCalledWith("test-klinik", 365));
  });
});
