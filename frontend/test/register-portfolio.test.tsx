import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import RegisterPortfolio from "@/components/analytics/RegisterPortfolio";
import type { PortfolioReport } from "@/lib/domain-api/registerGrid";

const report: PortfolioReport = vi.hoisted(() => ({
  as_of: "2026-10-04",
  totals: { contracts: 3, running: 2, annual_cost: "18000.00", cost_current_year: "15000.00", income_current_year: "0.00" },
  by_status: [{ status: "in_arbeit", label: "In Arbeit", count: 1 }, { status: "gueltig", label: "Gültig", count: 1 }],
  cost_by: {
    hospital: [{ label: "Klinikum A", value: "Klinikum A", count: 1, annual_cost: "12000.00", cost_current_year: "9000.00" }],
    partner: [{ label: "Medtec", value: "Medtec", count: 2, annual_cost: "18000.00", cost_current_year: "15000.00" }],
  },
  dimensions: [{ key: "hospital", label: "Krankenhaus" }, { key: "partner", label: "Vertragspartner" }],
  cost_by_year: [{ year: 2026, expense: "15000.00", income: "0.00", is_projection: false }, { year: 2027, expense: "18000.00", income: "0.00", is_projection: true }],
  deadlines_by_month: [{ month: "2026-10", notice: 1, other: 0 }, { month: "2026-11", notice: 0, other: 2 }],
  upcoming: [{ contract_id: "c-2", register_number: "000002", short_description: "Reinigung", due_date: "2026-10-31", title: "Kündigungsfrist", kind: "notice" }],
  supplier_concentration: { partner: "Medtec", share_percent: "100.0" },
  insights: [
    { key: "no_responsible", label: "Laufende Verträge ohne verantwortliche Person", count: 1, filter: { column: "responsible", op: "empty" } },
    { key: "no_end", label: "Laufende Verträge ohne berechenbares Vertragsende", count: 0, filter: { column: "possible_end", op: "empty" } },
  ],
}) as PortfolioReport);

vi.mock("@/lib/domain-api/registerGrid", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/registerGrid")>()),
  getPortfolioReport: vi.fn().mockResolvedValue(report),
  downloadPortfolioXlsx: vi.fn(),
}));

describe("Vertragsportfolio", () => {
  it("zeigt Kennzahlen, Handlungsbedarf mit Drill-down und Diagramme mit Tabellenansicht", async () => {
    const user = userEvent.setup();
    const { container } = render(<RegisterPortfolio organizationSlug="test-klinik" />);
    expect((await screen.findByText("Jährliche Kosten")).nextElementSibling).toHaveTextContent("18.000,00 €");
    const insight = screen.getByRole("link", { name: "Laufende Verträge ohne verantwortliche Person" });
    expect(decodeURIComponent(insight.getAttribute("href") ?? "")).toBe('/register?filter=[{"column":"responsible","op":"empty"}]');
    expect(screen.queryByRole("link", { name: /ohne berechenbares Vertragsende/ })).not.toBeInTheDocument();
    expect(screen.getByText(/100,0 %/)).toBeInTheDocument();

    expect(screen.getByRole("group", { name: /Krankenhaus: Klinikum A 9\.000,00/ })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Aufteilen nach"), "partner");
    expect(screen.getByRole("group", { name: /Vertragspartner: Medtec 15\.000,00/ })).toBeInTheDocument();

    const years = screen.getByRole("heading", { name: "Ausgaben und Einnahmen je Jahr" }).closest("section")!;
    expect(within(years).getByText("Prognose")).toBeInTheDocument();
    expect(within(years).getByText("Ausgaben", { selector: "li" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });
});
