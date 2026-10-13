import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDecisionCard, { deadlineSignal } from "@/components/contracts/detail/ContractDecisionCard";
import RenewalOverview from "@/components/deadlines/RenewalOverview";
import type { ContractLifecycleDecision } from "@/lib/domain-api/lifecycle";
import type { RenewalBrief } from "@/lib/domain-api/registerGrid";

const api = vi.hoisted(() => ({
  getRenewalBrief: vi.fn(),
  getRenewalSummary: vi.fn(),
  listRenewals: vi.fn(),
  getContractLifecycle: vi.fn(),
  createContractLifecycleDecision: vi.fn(),
  updateContractLifecycleDecision: vi.fn(),
}));

vi.mock("@/lib/domain-api/registerGrid", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/registerGrid")>()),
  getRenewalBrief: api.getRenewalBrief,
  getRenewalSummary: api.getRenewalSummary,
  listRenewals: api.listRenewals,
}));
vi.mock("@/lib/domain-api/lifecycle", () => ({
  getContractLifecycle: api.getContractLifecycle,
  createContractLifecycleDecision: api.createContractLifecycleDecision,
  updateContractLifecycleDecision: api.updateContractLifecycleDecision,
}));

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
    hints: [{ kind: "info", text: "Bei Verlängerung entstehen bis 31.12.2027 voraussichtlich 12.360,00 € (netto).", reason: "Hochrechnung." }],
    explanation: [],
    ...overrides,
  };
}

const SAVED: ContractLifecycleDecision = {
  id: "l-1", contract_id: "c-1", decision: "terminate", status: "planned", effective_date: "2026-12-31",
  note: "Neues Angebot", actor_display_name: "Ahmad", created_at: "2026-08-15T10:00:00Z", updated_at: null,
};

describe("Entscheidung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRenewalBrief.mockResolvedValue(brief());
    api.getContractLifecycle.mockReset().mockResolvedValueOnce({ items: [] }).mockResolvedValue({ items: [SAVED] });
    api.createContractLifecycleDecision.mockResolvedValue(SAVED);
  });

  it("zeigt Kennzahlen, „Ohne Handeln“ und Hinweise; ohne Verstöße (axe)", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("Frist in 46 Tagen")).toBeInTheDocument();
    const kpi = (label: string) => screen.getByText(label, { selector: "dt" }).nextElementSibling;
    expect(kpi("Kündbar bis")).toHaveTextContent("30.09.2026");
    expect(kpi("Vertragsende")).toHaveTextContent("31.12.2026");
    expect(kpi("Kosten bei Verlängerung")).toHaveTextContent(/12\.360,00/);
    expect(screen.getByText(/verlängert sich der Vertrag um 1 Jahr/)).toBeInTheDocument();
    expect(screen.getByText("Grundlage: Hochrechnung.")).toBeInTheDocument();
    expect(screen.getByText("Weitere Verträge mit MEDTEC (1)")).toBeInTheDocument();
    expect(screen.getByText("Noch keine Entscheidung erfasst.")).toBeInTheDocument();
    api.getRenewalSummary.mockResolvedValue({ available: true, text: "Der Vertrag ist bis 30.09.2026 kündbar.", message: null, model: "qwen3:8b" });
    await user.click(screen.getByRole("button", { name: "Kurzfassung mit lokaler KI" }));
    expect(await screen.findByText("Der Vertrag ist bis 30.09.2026 kündbar.")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Status im Kopf: keine Frist, Frist bald, Frist überschritten", () => {
    expect(deadlineSignal({ urgency: "none", days_left: null })).toEqual({ tone: "neutral", label: "Keine offene Frist" });
    expect(deadlineSignal({ urgency: "planned", days_left: 200 })).toEqual({ tone: "neutral", label: "Frist in 200 Tagen" });
    expect(deadlineSignal({ urgency: "critical", days_left: 20 })).toEqual({ tone: "warning", label: "Frist in 20 Tagen" });
    expect(deadlineSignal({ urgency: "missed", days_left: -3 })).toEqual({ tone: "critical", label: "Frist überschritten" });
  });

  it("feste Laufzeit: „Kündbar bis“ und Verlängerungskosten bleiben „–“", async () => {
    api.getRenewalBrief.mockResolvedValue(brief({ urgency: "none", days_left: null, cancel_by: null, renewal_cost: null, hints: [], partner_contracts: [] }));
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("Keine offene Frist")).toBeInTheDocument();
    expect(screen.getByText("Kündbar bis", { selector: "dt" }).nextElementSibling).toHaveTextContent("–");
    expect(screen.getByText("Kosten bei Verlängerung", { selector: "dt" }).nextElementSibling).toHaveTextContent("–");
  });

  it("Knopf öffnet das Formular darunter, erneuter Klick schließt; Speichern zeigt die Entscheidung in der Liste", async () => {
    const user = userEvent.setup();
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    const group = await screen.findByRole("group", { name: "Entscheidung" });
    const terminate = within(group).getByRole("button", { name: "Kündigen" });
    expect(terminate).toHaveAttribute("aria-pressed", "false");
    await user.click(terminate);
    expect(terminate).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Wirksam am")).toHaveValue("2026-12-31");
    await user.click(terminate);
    expect(screen.queryByLabelText("Wirksam am")).not.toBeInTheDocument();
    await user.click(within(group).getByRole("button", { name: "Beobachten" }));
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(screen.queryByLabelText("Notiz")).not.toBeInTheDocument();

    await user.click(terminate);
    await user.type(screen.getByLabelText("Notiz"), "Neues Angebot");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));
    await waitFor(() => expect(api.createContractLifecycleDecision).toHaveBeenCalledWith("test-klinik", "c-1", { decision: "terminate", status: "planned", effective_date: "2026-12-31", note: "Neues Angebot" }));
    const list = await screen.findByRole("list", { name: "Bisherige Entscheidungen" });
    expect(within(list).getByText("Kündigen")).toBeInTheDocument();
    expect(within(list).getByText("wirksam am 31.12.2026 · Neues Angebot")).toBeInTheDocument();
    expect(within(list).getByText("Ahmad")).toBeInTheDocument();
    expect(screen.queryByLabelText("Wirksam am")).not.toBeInTheDocument();
    // Nach „Kündigen“: Hinweis auf den Statuswechsel, der die Kündigung dokumentiert.
    expect(screen.getByRole("link", { name: "Status auf „Gekündigt“ setzen" })).toHaveAttribute("href", "/contracts/c-1?tab=register&abschnitt=status");
  });
});

describe("Kündigungsentscheidungen", () => {
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
