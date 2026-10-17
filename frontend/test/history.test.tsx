import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractHistoryPanel from "@/components/contracts/detail/ContractHistoryPanel";
import OrganizationHistory from "@/components/history/OrganizationHistory";
import type { HistoryEntry } from "@/lib/domain-api/history";

const api = vi.hoisted(() => ({
  getContractHistory: vi.fn(),
  listHistory: vi.fn(),
  downloadHistoryCsv: vi.fn(),
}));

vi.mock("@/lib/domain-api/history", () => api);
vi.mock("@/lib/domain-api/contracts", () => ({
  listContracts: vi.fn().mockResolvedValue({ items: [{ contract_id: "c-1", register_number: "000001", contract_number: null, contract_title: "Wartung CT", supplier: "Medtec" }] }),
}));

function entry(overrides: Partial<HistoryEntry>): HistoryEntry {
  return { id: "x", kind: "activity", category: "contract", at: "2026-10-04T10:15:00Z", actor: "Anna", event: "contract.register_updated", label: "Stammdaten geändert", details: {}, ...overrides };
}

describe("Vertragshistorie", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getContractHistory.mockResolvedValue({ items: [
      entry({ id: "a", label: "Stammdaten geändert", details: { fields: { internal_number: { before: null, after: "INT-1" } } } }),
      entry({ id: "b", kind: "mail", category: "deadline", event: "notification.mail_sent", label: "Erinnerung per E-Mail versendet", actor: "System", details: { recipient: "anna@klinik.invalid" } }),
      entry({ id: "c", kind: "fact_review", category: "fact_review", label: "Bestätigt: Vertragsende", actor: "Ben" }),
    ] });
  });

  it("zeigt alle Spuren mit Änderungsdetails und filtert nach Bereich", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContractHistoryPanel contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("Stammdaten geändert")).toBeInTheDocument();
    expect(screen.getByText("internal_number").parentElement).toHaveTextContent("– → INT-1");
    expect(screen.getByText("Erinnerung per E-Mail versendet")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Prüfungen" }));
    expect(screen.queryByText("Stammdaten geändert")).not.toBeInTheDocument();
    expect(screen.getByText("Bestätigt: Vertragsende")).toBeInTheDocument();
  });
});

describe("Organisationsweite Historie", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listHistory.mockResolvedValue({
      total: 1,
      items: [entry({ id: "a", object_type: "contract", object_id: "c-1", contract_number: "000001", contract_title: "Wartung CT" })],
      actors: [{ account_id: "u-1", display_name: "Anna" }],
      categories: [{ key: "contract", label: "Verträge" }, { key: "finance", label: "Finanzen" }],
    });
    api.downloadHistoryCsv.mockResolvedValue({ blob: new Blob(["x"]), filename: "historie.csv" });
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
  });

  it("filtert serverseitig und exportiert mit denselben Filtern", async () => {
    const user = userEvent.setup();
    const { container } = render(<OrganizationHistory organizationSlug="test-klinik" />);
    const row = (await screen.findByRole("rowheader", { name: /Stammdaten geändert/ })).closest("tr")!;
    expect(within(row).getByRole("link", { name: "000001 · Wartung CT" })).toHaveAttribute("href", "/contracts/c-1");
    expect(await axe(container)).toHaveNoViolations();

    await user.selectOptions(screen.getByLabelText("Benutzer"), "u-1");
    await user.selectOptions(screen.getByLabelText("Bereich"), "finance");
    await waitFor(() => expect(api.listHistory).toHaveBeenLastCalledWith("test-klinik", { account_id: "u-1", category: "finance" }, { limit: 50, offset: 0 }));

    await user.click(screen.getByRole("button", { name: "CSV exportieren" }));
    expect(api.downloadHistoryCsv).toHaveBeenCalledWith("test-klinik", { account_id: "u-1", category: "finance" });
    expect(window.location.search).toBe("?account_id=u-1&category=finance");
  });

  it("übernimmt Filter aus der Adresse", async () => {
    window.history.replaceState(null, "", "/audit?category=deadline&offset=50");
    render(<OrganizationHistory organizationSlug="test-klinik" />);
    await waitFor(() => expect(api.listHistory).toHaveBeenCalledWith("test-klinik", { category: "deadline" }, { limit: 50, offset: 50 }));
    expect(api.listHistory).toHaveBeenCalledTimes(1);
    window.history.replaceState(null, "", "/");
  });
});
