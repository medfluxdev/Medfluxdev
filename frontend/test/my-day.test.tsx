import { render, screen, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import MyDay from "@/components/dashboard/MyDay";

const apiGetMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), apiGet: apiGetMock }));

function today(offset: number) {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

function routes(path: string) {
  if (path.startsWith("/api/deadlines")) return Promise.resolve({ items: [
    { id: "d-1", contract_id: "c-1", contract_label: "000001 · Wartung CT", title: "Angebot einholen", due_date: today(-1), days_until_due: -1, overdue: true },
    { id: "d-2", contract_id: "c-2", contract_label: "000002 · Reinigung", title: "Rückruf Lieferant", due_date: today(0), days_until_due: 0, overdue: false },
  ] });
  if (path.startsWith("/api/register/renewals")) return Promise.resolve({ items: [
    { contract_id: "c-2", register_number: "000002", short_description: "Reinigung", partner: "CLEANMED", cancel_by: today(20), days_left: 20, urgency: "critical", annual_cost: "14400.00", decision: null },
    { contract_id: "c-3", register_number: "000003", short_description: "PACS", partner: "SIEMENS", cancel_by: today(60), days_left: 60, urgency: "soon", annual_cost: null, decision: { decision: "renew", label: "Verlängern", status: "planned" } },
  ] });
  if (path.startsWith("/api/register/reports/portfolio")) return Promise.resolve({
    totals: { contracts: 3, running: 3, annual_cost: "74400.00", cost_current_year: "73200.00", income_current_year: "0.00" },
    insights: [
      { key: "no_responsible", label: "Laufende Verträge ohne verantwortliche Person", count: 1, filter: { column: "responsible", op: "empty" } },
      { key: "no_end", label: "Laufende Verträge ohne berechenbares Vertragsende", count: 0, filter: { column: "possible_end", op: "empty" } },
    ],
  });
  if (path.startsWith("/api/inbox")) return Promise.resolve({ unread_count: 2, notifications: [], deadlines: [], representing: [] });
  if (path.startsWith("/api/register/grid")) return Promise.resolve({ total: 0, items: [], groups: [], totals: { count: 0, sums: {} } });
  return Promise.resolve({});
}

describe("Mein Tag", () => {
  it("zeigt eigene Termine, offene Entscheidungen und Kennzahlen aus den Registerdaten", async () => {
    apiGetMock.mockImplementation(routes);
    const { container } = render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByText("Angebot einholen")).toBeInTheDocument();
    expect(screen.getByText("Überfällig")).toBeInTheDocument();
    expect(screen.getByText("Heute")).toBeInTheDocument();
    const decisions = screen.getByRole("heading", { name: "Entscheidungen vor Kündigungsfrist" }).closest("section")!;
    expect(within(decisions).getByRole("link", { name: "000002 · Reinigung" })).toBeInTheDocument();
    expect(within(decisions).queryByText(/PACS/)).not.toBeInTheDocument();
    expect(screen.getByText("Jährliche Kosten (netto)").closest(".kpi")!.querySelector(".kpi-value")).toHaveTextContent("74.400,00");
    expect(screen.getByText("1 ohne Entscheidung")).toBeInTheDocument();
    // Handlungsbedarf steht vorn, mit Anzahl offener Punkte und ganzer Zeile als Link
    const attention = screen.getByRole("heading", { name: /Handlungsbedarf im Portfolio/ }).closest("section")!;
    expect(attention.parentElement!.firstElementChild).toBe(attention);
    expect(screen.getByRole("heading", { name: /Handlungsbedarf im Portfolio/ })).toHaveTextContent("1 offene Punkte");
    const row = within(attention).getByRole("link", { name: "1 Laufende Verträge ohne verantwortliche Person" });
    expect(row).toHaveAttribute("href", expect.stringContaining("/register?filter="));
    expect(row.querySelector(".my-day-pill")).not.toHaveClass("my-day-pill--danger");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("zeigt ohne offene Punkte kompakte leere Zustände und färbt fehlende Vertragsenden rot", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/deadlines") || path.startsWith("/api/register/renewals")) return Promise.resolve({ items: [] });
      if (path.startsWith("/api/register/reports/portfolio")) return Promise.resolve({
        totals: { contracts: 2, running: 2, annual_cost: "0.00", cost_current_year: "0.00", income_current_year: "0.00" },
        insights: [{ key: "no_end", label: "Laufende Verträge ohne berechenbares Vertragsende", count: 2, filter: { column: "possible_end", op: "empty" } }],
      });
      return routes(path);
    });
    const { container } = render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByText("Keine Termine diese Woche")).toBeInTheDocument();
    expect(screen.getByText("Alles entschieden")).toBeInTheDocument();
    expect(container.querySelectorAll(".empty-state-calm")).toHaveLength(2);
    expect(screen.getByText("Keine Entscheidung offen")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ohne berechenbares Vertragsende/ }).querySelector(".my-day-pill")).toHaveClass("my-day-pill--danger");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("meldet einen Ladefehler mit Wiederholen", async () => {
    apiGetMock.mockRejectedValue(new Error("down"));
    render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Die Übersicht konnte nicht geladen werden.");
    expect(screen.getByRole("button", { name: "Erneut laden" })).toBeInTheDocument();
  });
});
