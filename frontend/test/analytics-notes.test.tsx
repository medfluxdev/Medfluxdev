import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import PortfolioQueryPanel from "@/components/analytics/PortfolioQueryPanel";

const analytics = vi.hoisted(() => ({ queryPortfolio: vi.fn() }));
vi.mock("@/lib/domain-api/intelligenceAnalytics", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/intelligenceAnalytics")>()),
  ...analytics,
}));

describe("Analysen – Fragen an das Portfolio", () => {
  it("beantwortet eine Frage und verlinkt die passenden Verträge", async () => {
    const user = userEvent.setup();
    analytics.queryPortfolio.mockResolvedValue({ answer: "2 Verträge enden 2027.", unknowns: [], matches: [{ contract_id: "c-1", contract_number: "000001", supplier: "SIEMENS", status: "active" }] });
    const { container } = render(<PortfolioQueryPanel organizationSlug="test-klinik" />);
    await user.type(screen.getByRole("searchbox", { name: "Frage" }), "Welche Verträge enden 2027?{Enter}");
    await waitFor(() => expect(analytics.queryPortfolio).toHaveBeenCalledWith("test-klinik", { query: "Welche Verträge enden 2027?" }));
    expect(await screen.findByRole("heading", { name: "2 Verträge enden 2027." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "000001" })).toHaveAttribute("href", "/contracts/c-1");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("ein Beispiel stellt die Frage sofort", async () => {
    const user = userEvent.setup();
    analytics.queryPortfolio.mockResolvedValue({ answer: "Keine.", unknowns: [], matches: [] });
    render(<PortfolioQueryPanel organizationSlug="test-klinik" />);
    await user.click(screen.getByRole("button", { name: "Welche Verträge haben keine Kosten?" }));
    await waitFor(() => expect(analytics.queryPortfolio).toHaveBeenCalledWith("test-klinik", { query: "Welche Verträge haben keine Kosten?" }));
    expect(screen.getByRole("searchbox", { name: "Frage" })).toHaveValue("Welche Verträge haben keine Kosten?");
  });
});
