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

describe("Mein Tag (Ruhe & Signal v3)", () => {
  it("zeigt Lagebild, ruhige Kennzahlen, Arbeit nach Dringlichkeit und persönliche Termine", async () => {
    apiGetMock.mockImplementation(routes);
    const { container } = render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByText("Angebot einholen")).toBeInTheDocument();
    // Lagebild nennt Themen, nicht Verträge: überfälliger Termin + Entscheidung in ≤ 30 Tagen
    const brief = screen.getByRole("region", { name: "Lagebild" });
    expect(within(brief).getByText("Heute brauchen 2 Themen Ihre Aufmerksamkeit")).toBeInTheDocument();
    expect(within(brief).getByText("1 Termin überfällig").closest(".signal")).toHaveClass("signal--critical");
    expect(within(brief).getByText("1 Entscheidung in ≤ 30 Tagen").closest(".signal")).toHaveClass("signal--warning");
    // Drei Kennzahlen, neutral; keine Kachel für ungelesene Erinnerungen mehr (Glocke)
    const kpis = screen.getByRole("region", { name: "Kennzahlen" });
    expect(within(kpis).getAllByRole("link")).toHaveLength(3);
    expect(within(kpis).queryByText(/Ungelesene Erinnerungen/)).not.toBeInTheDocument();
    expect(screen.getByText("Jährliche Kosten (netto)").closest(".kpi")!.querySelector(".kpi-value")).toHaveTextContent("74.400,00");
    // Termine: überfällig zuerst, mit Signal statt Farbe
    const deadlines = screen.getByRole("heading", { name: /Meine Termine/ }).closest("section")!;
    expect(within(deadlines).getByText("Überfällig").closest(".signal")).toHaveClass("signal--critical");
    expect(within(deadlines).getByRole("link", { name: "Alle Termine" })).toHaveAttribute("href", "/fristen?ansicht=termine&nur=meine&zeitraum=7");
    const decisions = screen.getByRole("heading", { name: "Entscheidungen vor Kündigungsfrist" }).closest("section")!;
    expect(within(decisions).getByRole("link", { name: "000002 · Reinigung" })).toBeInTheDocument();
    expect(within(decisions).queryByText(/PACS/)).not.toBeInTheDocument();
    // Zu erledigen: ganze Zeile als Link, Signal mit Wort, Anzahl der Problemarten (nicht Verträge)
    const work = screen.getByRole("heading", { name: "Zu erledigen – nach Dringlichkeit" }).closest("section")!;
    expect(within(work).getByText(/1 Problemart/)).toBeInTheDocument();
    const row = within(work).getByRole("link", { name: /Prüfen 1 Laufende Verträge ohne verantwortliche Person/ });
    expect(row).toHaveAttribute("href", expect.stringContaining("/register?filter="));
    expect(await axe(container)).toHaveNoViolations();
  });

  it("ist ruhig, wenn nichts dringend ist, und ordnet Kritisches vor Prüfbedarf", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/deadlines") || path.startsWith("/api/register/renewals")) return Promise.resolve({ items: [], not_evaluable: [] });
      if (path.startsWith("/api/register/reports/portfolio")) return Promise.resolve({
        totals: { contracts: 2, running: 2, annual_cost: null, cost_current_year: null, income_current_year: null,
          amounts: { annual_cost: { value: null, currency: "EUR", known: 0, missing: 2, other_currencies: {} } } },
        insights: [
          { key: "no_finance", label: "Laufende Verträge ohne gepflegte Kosten", count: 2, filter: { column: "cost_current_year", op: "empty" }, severity: "warning" },
          { key: "no_end", label: "Laufzeitangaben unvollständig", count: 2, filter: { column: "term_status", op: "in", value: ["Unvollständig"] }, severity: "critical" },
        ],
      });
      return routes(path);
    });
    const { container } = render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByText("Keine Termine diese Woche", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("Alles entschieden")).toBeInTheDocument();
    expect(container.querySelectorAll(".empty-state-calm")).toHaveLength(2);
    // Kosten unbekannt: „—“ mit Signal, keine 0,00 €
    const cost = screen.getByText("Jährliche Kosten (netto)").closest(".kpi")!;
    expect(cost.querySelector(".kpi-value")).toHaveTextContent("—");
    expect(within(cost as HTMLElement).getByText("Kosten fehlen bei 2 Verträgen").closest(".signal")).toHaveClass("signal--warning");
    const rows = within(screen.getByRole("heading", { name: "Zu erledigen – nach Dringlichkeit" }).closest("section")!).getAllByRole("link");
    expect(rows[0]).toHaveTextContent(/Kritisch/);
    expect(rows[1]).toHaveTextContent(/Prüfen/);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("sagt „Heute ist nichts dringend“ ohne Themen", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/deadlines") || path.startsWith("/api/register/renewals")) return Promise.resolve({ items: [], not_evaluable: [] });
      if (path.startsWith("/api/register/reports/portfolio")) return Promise.resolve({ totals: { contracts: 1, running: 1, annual_cost: "100.00" }, insights: [] });
      return routes(path);
    });
    render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByText("Heute ist nichts dringend")).toBeInTheDocument();
    expect(screen.getByText("Keine Termine diese Woche", { selector: ".signal-label" })).toBeInTheDocument();
  });

  it("meldet einen Ladefehler mit Wiederholen", async () => {
    apiGetMock.mockRejectedValue(new Error("down"));
    render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Die Übersicht konnte nicht geladen werden.");
    expect(screen.getByRole("button", { name: "Erneut laden" })).toBeInTheDocument();
  });
});

describe("Mein Tag – Kosten ohne laufende Verträge", () => {
  it("sagt „Keine laufenden Verträge“ statt „Noch keine Daten“", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/deadlines") || path.startsWith("/api/register/renewals")) return Promise.resolve({ items: [], not_evaluable: [] });
      if (path.startsWith("/api/register/reports/portfolio")) return Promise.resolve({ totals: { contracts: 3, running: 0, in_progress: 3, annual_cost: null }, insights: [] });
      return routes(path);
    });
    render(<MyDay organizationSlug="test-klinik" />);
    const cost = (await screen.findByText("Jährliche Kosten (netto)")).closest(".kpi") as HTMLElement;
    expect(await within(cost).findByText("Keine laufenden Verträge")).toBeInTheDocument();
    expect(within(cost).queryByText("Noch keine Daten")).not.toBeInTheDocument();
  });
});
