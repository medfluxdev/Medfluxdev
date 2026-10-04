import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractFinancePanel from "@/components/contracts/detail/ContractFinancePanel";
import type { FinanceDto } from "@/lib/domain-api/finance";

const api = vi.hoisted(() => ({
  getFinance: vi.fn(),
  createFinanceEntry: vi.fn(),
  updateFinanceEntry: vi.fn(),
  deleteFinanceEntry: vi.fn(),
  createServiceItem: vi.fn(),
  deleteServiceItem: vi.fn(),
  setCostAllocations: vi.fn(),
  acceptFinanceSuggestion: vi.fn(),
  dismissFinanceSuggestion: vi.fn(),
  downloadFinanceCsv: vi.fn(),
}));

vi.mock("@/lib/domain-api/finance", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/finance")>()),
  ...api,
}));
vi.mock("@/lib/domain-api/catalogs", () => ({
  listLookups: vi.fn().mockResolvedValue({ field_keys: [], items: [
    { id: "c1", field_key: "cost_type", code: "wartung", label: "Wartung / Service", description: null, is_active: true, sort_order: 0 },
    { id: "r1", field_key: "recharge_mode", code: "teilweise", label: "Teilweise", description: null, is_active: true, sort_order: 0 },
  ] }),
}));
vi.mock("@/lib/domain-api/organizations", () => ({
  listCostCenters: vi.fn().mockResolvedValue({ items: [
    { id: "cc1", hospital_id: "h1", department_id: null, code: "471100", name: "Radiologie", is_active: true },
    { id: "cc2", hospital_id: "h1", department_id: null, code: "471200", name: "Kardiologie", is_active: true },
  ] }),
}));

const money = (net: string, gross: string) => ({ net, gross });

function finance(overrides: Partial<FinanceDto> = {}): FinanceDto {
  return {
    contract_id: "c-1",
    as_of: "2026-10-04",
    entries: [{
      id: "e-1", direction: "expense", label: "Wartungspauschale", cost_type_code: "wartung", amount: "3500.00", amount_basis: "net",
      vat_rate: "19.00", currency: "EUR", interval: "monthly", valid_from: "2026-01-01", valid_to: null, apply_price_adjustment: true,
      note: null, origin: "ai_confirmed", source_key: "costs.monthly_cost", created_by_name: "Admin",
    }],
    summaries: [{
      currency: "EUR",
      expense: { current_year: money("42000.00", "49980.00"), to_date: money("35000.00", "41650.00"), remaining_to_end: null, total_term: null, annual_run_rate: money("42000.00", "49980.00") },
      income: { current_year: money("0.00", "0.00"), to_date: money("0.00", "0.00"), remaining_to_end: null, total_term: null, annual_run_rate: money("0.00", "0.00") },
      contract_end: null,
      projected_adjustment: false,
      notes: ["Kein Vertragsende bekannt: Beträge bis Vertragsende und für die Gesamtlaufzeit sind nicht berechenbar."],
    }],
    services: [],
    allocations: [],
    primary_cost_center_id: null,
    price_adjustment: { kind: "percent", percent: "3.000", index_name: null, next_date: "2027-01-01", interval_months: 12 },
    suggestions: {
      entries: [],
      services: [{ key: "costs.hourly_rate", values: { label: "Stundensatz", amount: "125.00", unit: "pro Stunde", currency: "EUR" }, source_field: "costs.hourly_rate" }],
    },
    ...overrides,
  };
}

describe("Finanzdaten", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getFinance.mockResolvedValue(finance());
    api.createFinanceEntry.mockResolvedValue(finance());
    api.acceptFinanceSuggestion.mockResolvedValue(finance({ suggestions: { entries: [], services: [] } }));
    api.setCostAllocations.mockResolvedValue(finance());
  });

  it("zeigt Monatsmatrix, ehrliche Hinweise, Preisanpassung und Herkunft", async () => {
    const { container } = render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    const table = await screen.findByRole("table", { name: "Finanzübersicht EUR" });
    const expense = within(table).getByRole("row", { name: /Ausgaben/ });
    expect(expense).toHaveTextContent("42.000,00");
    expect(within(expense).getAllByText("nicht berechenbar")).toHaveLength(2);
    expect(screen.getByText(/Kein Vertragsende bekannt/)).toBeInTheDocument();
    expect(screen.getByText(/Preisanpassung: Prozentual 3 %/)).toBeInTheDocument();
    expect(screen.getByText("KI · bestätigt")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("übernimmt KI-Vorschläge erst auf Klick und legt Einträge an", async () => {
    const user = userEvent.setup();
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "KI-Vorschläge aus dem Vertrag" });
    expect(api.acceptFinanceSuggestion).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Übernehmen" }));
    expect(api.acceptFinanceSuggestion).toHaveBeenCalledWith("test-klinik", "c-1", "service", "costs.hourly_rate");

    await user.click(screen.getByRole("button", { name: "Eintrag erstellen" }));
    const form = screen.getByRole("form", { name: "Finanzeintrag anlegen" });
    await user.type(within(form).getByLabelText("Bezeichnung *"), "Softwarepflege");
    await user.type(within(form).getByLabelText("Betrag *"), "1200");
    await user.selectOptions(within(form).getByLabelText("Intervall"), "annual");
    await user.type(within(form).getByLabelText("Gültig ab *"), "2026-01-01");
    await user.click(within(form).getByRole("button", { name: "Speichern" }));
    expect(api.createFinanceEntry).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({
      label: "Softwarepflege", amount: "1200", interval: "annual", valid_from: "2026-01-01", valid_to: null, direction: "expense",
    }));
  });

  it("speichert die Kostenstellen-Aufteilung nur bei 100 %", async () => {
    const user = userEvent.setup();
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Kostenstellen-Aufteilung" });
    await user.click(screen.getByRole("button", { name: "Kostenstelle hinzufügen" }));
    await user.click(screen.getByRole("button", { name: "Kostenstelle hinzufügen" }));
    const selects = screen.getAllByLabelText("Kostenstelle");
    await waitFor(() => expect(within(selects[0]).getByRole("option", { name: "471100 – Radiologie" })).toBeInTheDocument());
    await user.selectOptions(selects[0], "cc1");
    await user.selectOptions(selects[1], "cc2");
    const shares = screen.getAllByLabelText("Anteil %");
    await user.clear(shares[0]);
    await user.type(shares[0], "70");
    expect(screen.getByRole("button", { name: "Aufteilung speichern" })).toBeDisabled();
    await user.type(shares[1], "30");
    await user.click(screen.getByRole("button", { name: "Aufteilung speichern" }));
    expect(api.setCostAllocations).toHaveBeenCalledWith("test-klinik", "c-1", [
      { cost_center_id: "cc1", share_percent: "70", recharge_mode: null },
      { cost_center_id: "cc2", share_percent: "30", recharge_mode: null },
    ]);
  });
});
