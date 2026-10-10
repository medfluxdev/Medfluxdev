import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PortfolioDrilldown from "@/components/analytics/PortfolioDrilldown";
import type { DrilldownReport } from "@/lib/domain-api/registerGrid";

const api = vi.hoisted(() => ({ getDrilldown: vi.fn() }));
vi.mock("@/lib/domain-api/registerGrid", () => api);

const totals = (value: string | null, known: number, missing: number) => ({ value, currency: "EUR", known, missing, other_currencies: {} });

function level1(): DrilldownReport {
  return {
    as_of: "2026-10-10", level: "hospital", path: [], count: 3, truncated: false, register_filter: [],
    totals: totals("1500.00", 2, 1),
    items: [
      { label: "Klinikum A", value: "Klinikum A", count: 2, annual_cost: "1500.00", cost_current_year: "1500.00", known: 2, missing: 0 },
      { label: "Ohne Zuordnung", value: "__none__", count: 1, annual_cost: null, cost_current_year: null, known: 0, missing: 1 },
    ],
  };
}

function level2(): DrilldownReport {
  return {
    as_of: "2026-10-10", level: "department", count: 2, truncated: false, totals: totals("1500.00", 2, 0),
    path: [{ level: "hospital", label: "Krankenhaus", value: "Klinikum A", name: "Klinikum A" }],
    register_filter: [{ column: "hospital", op: "in", value: ["Klinikum A"] }],
    items: [{ label: "Radiologie", value: "Radiologie", count: 2, annual_cost: "1500.00", cost_current_year: "1500.00", known: 2, missing: 0 }],
  };
}

function level3(): DrilldownReport {
  return {
    as_of: "2026-10-10", level: "contract", count: 2, truncated: false, totals: totals("1500.00", 1, 1),
    path: [
      { level: "hospital", label: "Krankenhaus", value: "Klinikum A", name: "Klinikum A" },
      { level: "department", label: "Abteilung", value: "Radiologie", name: "Radiologie" },
    ],
    register_filter: [{ column: "hospital", op: "in", value: ["Klinikum A"] }, { column: "department", op: "in", value: ["Radiologie"] }],
    items: [
      { contract_id: "c-1", register_number: "000001", short_description: "MRT Wartung", partner: "Siemens", currency: "EUR", annual_cost: "1500.00", cost_current_year: "1500.00", term_status: "Vollständig" },
      { contract_id: "c-2", register_number: "000002", short_description: "CT Service", partner: null, currency: "EUR", annual_cost: null, cost_current_year: null, term_status: "Unvollständig" },
    ],
  };
}

describe("Analysen-Drilldown", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getDrilldown.mockImplementation((_slug: string, hospital?: string, department?: string) =>
      Promise.resolve(department ? level3() : hospital ? level2() : level1()));
  });

  it("führt von Krankenhaus über Abteilung zu den Verträgen und zurück", async () => {
    const user = userEvent.setup();
    const { container } = render(<PortfolioDrilldown organizationSlug="test-klinik" />);
    const region = await screen.findByRole("region", { name: "Kosten nach Bereich" });
    expect(await within(region).findByRole("button", { name: "Klinikum A" })).toBeInTheDocument();
    // Unbekannt bleibt „—“ und nie 0.
    expect(within(region).getAllByText("—").length).toBeGreaterThan(0);
    expect(await axe(container)).toHaveNoViolations();

    await user.click(within(region).getByRole("button", { name: "Klinikum A" }));
    expect(api.getDrilldown).toHaveBeenLastCalledWith("test-klinik", "Klinikum A", undefined);
    await user.click(await within(region).findByRole("button", { name: "Radiologie" }));
    expect(api.getDrilldown).toHaveBeenLastCalledWith("test-klinik", "Klinikum A", "Radiologie");

    expect(await within(region).findByRole("link", { name: "MRT Wartung" })).toHaveAttribute("href", "/contracts/c-1");
    const listLink = within(region).getByRole("link", { name: /in der Vertragsliste öffnen/ });
    expect(decodeURIComponent(listLink.getAttribute("href") ?? "")).toContain('"column":"department"');

    await user.click(within(region).getByRole("button", { name: "Alle Krankenhäuser" }));
    await waitFor(() => expect(api.getDrilldown).toHaveBeenLastCalledWith("test-klinik", undefined, undefined));
  });

  it("zeigt einen Ladefehler mit erneutem Versuch", async () => {
    api.getDrilldown.mockRejectedValueOnce(new Error("offline"));
    render(<PortfolioDrilldown organizationSlug="test-klinik" />);
    expect(await screen.findByText("Die Auswertung konnte nicht geladen werden.")).toBeInTheDocument();
  });
});
