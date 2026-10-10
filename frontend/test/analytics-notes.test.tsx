import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import AiPortfolioNotes from "@/components/analytics/AiPortfolioNotes";
import PortfolioQueryPanel from "@/components/analytics/PortfolioQueryPanel";

const analytics = vi.hoisted(() => ({ queryPortfolio: vi.fn() }));
vi.mock("@/lib/domain-api/intelligenceAnalytics", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/intelligenceAnalytics")>()),
  ...analytics,
}));

const REPORT = {
  contracts: { total: 5, active: 4, archived: 1, by_risk: { high: 2, unknown: 3, low: 0 } },
  work_queue: { by_status: { open: 2, acknowledged: 1, resolved: 7 }, by_severity: {} },
  scope: { hospital_id: null, department_id: null },
};

describe("Analysen – KI-Hinweise", () => {
  it("zeigt Risiken auf Deutsch, offene Aufgaben und Archiv mit Links; Partnerpflichten nur wenn vorhanden", async () => {
    const { container, rerender } = render(<AiPortfolioNotes report={REPORT} suppliers={[{ supplier: "SIEMENS", contract_count: 3, total_obligations: 0, breached_obligations: 0, breach_rate: null, status_counts: {} }]} />);
    expect(screen.getByText("Hoch")).toBeInTheDocument();
    expect(screen.getByText("Nicht bewertet")).toBeInTheDocument();
    expect(screen.queryByText("Niedrig")).not.toBeInTheDocument();
    expect(screen.queryByText(/unknown/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "2 Verträge" })).toHaveAttribute("href", expect.stringContaining("/register?filter="));
    expect(screen.getByRole("link", { name: "offene Aufgaben aus der Analyse" })).toHaveAttribute("href", "/fristen?ansicht=aufgaben");
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "archivierter Vertrag" })).toHaveAttribute("href", "/register?ansicht=archive");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    rerender(<AiPortfolioNotes report={REPORT} suppliers={[{ supplier: "SIEMENS", contract_count: 3, total_obligations: 4, breached_obligations: 1, breach_rate: 0.25, status_counts: {} }]} />);
    const table = screen.getByRole("table", { name: "Pflichten der Vertragspartner (aus der Analyse)" });
    expect(within(table).getByText("1 von 4")).toBeInTheDocument();
  });

  it("beantwortet eine Frage und verlinkt die passenden Verträge", async () => {
    const user = userEvent.setup();
    analytics.queryPortfolio.mockResolvedValue({ answer: "2 Verträge enden 2027.", unknowns: [], matches: [{ contract_id: "c-1", contract_number: "000001", supplier: "SIEMENS", status: "active" }] });
    render(<PortfolioQueryPanel organizationSlug="test-klinik" />);
    await user.type(screen.getByRole("searchbox", { name: "Frage" }), "Welche Verträge enden 2027?{Enter}");
    await waitFor(() => expect(analytics.queryPortfolio).toHaveBeenCalledWith("test-klinik", { query: "Welche Verträge enden 2027?" }));
    expect(await screen.findByRole("heading", { name: "2 Verträge enden 2027." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "000001" })).toHaveAttribute("href", "/contracts/c-1");
    expect(screen.queryByText(/Frontend/)).not.toBeInTheDocument();
  });
});
