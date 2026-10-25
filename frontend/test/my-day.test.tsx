import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MyDay from "@/components/dashboard/MyDay";
import { buildTodo, compactEuro } from "@/lib/my-day";

const apiGetMock = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), apiGet: apiGetMock }));

function today(offset: number) {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

const deadline = (id: string, due: number, extra: Record<string, unknown> = {}) => ({
  id, contract_id: `c-${id}`, contract_label: `00000${id} · Wartung`, source: "manual", system_key: null, kind: "aufgabe",
  title: `Termin ${id}`, due_date: today(due), days_until_due: due, overdue: due < 0, ...extra,
});
const renewal = (id: string, days: number, extra: Record<string, unknown> = {}) => ({
  contract_id: id, register_number: `00000${id.slice(-1)}`, short_description: `Vertrag ${id}`, partner: "CLEANMED", cancel_by: today(days),
  days_left: days, urgency: "critical", annual_cost: null, decision: null, ...extra,
});

function routes(options: { deadlines?: unknown[]; renewals?: unknown[]; insights?: unknown[]; review?: number } = {}) {
  return (path: string) => {
    if (path.startsWith("/api/deadlines")) return Promise.resolve({ items: options.deadlines ?? [] });
    if (path.startsWith("/api/register/renewals")) return Promise.resolve({ items: options.renewals ?? [], not_evaluable: [] });
    if (path.startsWith("/api/register/reports/portfolio")) return Promise.resolve({
      totals: { contracts: 3, running: 3, annual_cost: "2400000.00", cost_current_year: "1.00", income_current_year: "0.00" },
      insights: options.insights ?? [],
    });
    if (path.startsWith("/api/register/grid")) return Promise.resolve({ total: options.review ?? 0, items: [], groups: [], totals: { count: 0, sums: {} } });
    return Promise.resolve({});
  };
}

beforeEach(() => { window.localStorage.clear(); apiGetMock.mockReset(); });

describe("buildTodo", () => {
  const base = { overdue: [], openDecisions: [], missingEnd: { count: 0, href: "/e" }, missingCosts: { count: 0, href: "/c" }, reviewCount: 0, hrefs: { overdue: "/o", decisions: "/d", review: "/r" } };

  it("ordnet nach Dringlichkeit und lässt Zeilen mit 0 weg", () => {
    const rows = buildTodo({
      ...base,
      overdue: [deadline("1", -3), deadline("2", -9)] as never,
      openDecisions: [renewal("c-4", 10), renewal("c-5", 50)] as never,
      missingEnd: { count: 17, href: "/e" }, missingCosts: { count: 23, href: "/c" }, reviewCount: 6,
    });
    expect(rows.map((row) => row.key)).toEqual(["overdue", "decision", "missingEnd", "dueSoon", "aiReview", "missingCosts"]);
    expect(rows[0]).toMatchObject({ count: 2, title: "2 Termine überfällig", action: "Anzeigen", href: "/o" });
    expect(rows[2].title).toBe("17 Verträgen fehlt das Vertragsende");
    expect(buildTodo(base)).toEqual([]);
  });

  it("nennt bei einem einzelnen Element dessen Namen und führt direkt hinein", () => {
    const rows = buildTodo({ ...base, overdue: [deadline("1", -3)] as never, openDecisions: [renewal("c-4", 12)] as never });
    expect(rows[0]).toMatchObject({ title: "Termin 1", action: "Öffnen", href: "/contracts/c-1?tab=deadlines" });
    expect(rows[1]).toMatchObject({ action: "Entscheiden", href: "/contracts/c-4?tab=deadlines" });
    expect(rows[1].title).toContain("000004 · Vertrag c-4");
  });

  it("kürzt Euro für die Zahlenzeile", () => {
    expect(compactEuro("2400000.00")).toBe("2,4 Mio. €");
    expect(compactEuro("8000.00")).toBe("8.000 €");
    expect(compactEuro(null)).toBe("–");
  });
});

describe("Mein Tag (v5)", () => {
  it("zeigt einen Block mit zwei Reitern; Zu erledigen ist Standard, Rot im Zähler bei Kritischem", async () => {
    apiGetMock.mockImplementation(routes({ deadlines: [deadline("1", -2), deadline("2", 3)], insights: [{ key: "no_end", label: "x", count: 2, filter: { column: "possible_end", op: "empty" }, severity: "critical" }] }));
    const { container } = render(<MyDay organizationSlug="test-klinik" />);
    const todoTab = await screen.findByRole("tab", { name: /Zu erledigen/ });
    expect(todoTab).toHaveAttribute("aria-selected", "true");
    expect(todoTab.querySelector(".my-day-badge")).toHaveClass("is-critical");
    expect(screen.getByRole("tab", { name: /Termine/ })).toHaveAttribute("aria-selected", "false");
    // Die Zahlen stehen nur im Reiter „Zahlen“, nicht mehr als Zeile unter der Begrüßung.
    expect(screen.queryByLabelText("Kennzahlen")).not.toBeInTheDocument();
    expect(within(screen.getByRole("tabpanel", { name: /Zu erledigen/ })).getByText("Termin 1")).toBeInTheDocument();
    expect(screen.getByText("2 Verträgen fehlt das Vertragsende")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("zeigt „Alles erledigt“ und startet dann mit Termine; Pfeiltasten wechseln den Reiter", async () => {
    apiGetMock.mockImplementation(routes({ deadlines: [deadline("3", 5), deadline("4", 1)] }));
    const user = userEvent.setup();
    render(<MyDay organizationSlug="test-klinik" />);
    const dates = await screen.findByRole("tab", { name: /Termine/ });
    expect(dates).toHaveAttribute("aria-selected", "true");
    // Nur kommende Termine, nach Datum: zuerst der in 1 Tag
    const panel = screen.getByRole("tabpanel", { name: /Termine/ });
    expect(within(panel).getAllByRole("heading", { level: 4 }).map((heading) => heading.textContent)).toEqual(["Termin 4", "Termin 3"]);
    expect(within(panel).getByRole("link", { name: "Alle Termine →" })).toBeInTheDocument();
    dates.focus();
    await user.keyboard("{ArrowLeft}");
    const todo = screen.getByRole("tab", { name: /Zu erledigen/ });
    expect(todo).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Alles erledigt")).toBeInTheDocument();
    expect(screen.getByText("Keine offenen Aufgaben – schönen Tag.")).toBeInTheDocument();
  });

  it("merkt den gewählten Reiter nur für den heutigen Tag", async () => {
    apiGetMock.mockImplementation(routes({ deadlines: [deadline("1", -2)] }));
    const user = userEvent.setup();
    const { unmount } = render(<MyDay organizationSlug="test-klinik" />);
    await user.click(await screen.findByRole("tab", { name: /Termine/ }));
    unmount();
    const second = render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByRole("tab", { name: /Termine/ })).toHaveAttribute("aria-selected", "true");
    second.unmount();
    window.localStorage.setItem("medflux.myday.tab", JSON.stringify({ day: "2000-01-01", tab: "dates" }));
    render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByRole("tab", { name: /Zu erledigen/ })).toHaveAttribute("aria-selected", "true");
  });

  it("leere Termine: ruhiger Hinweis", async () => {
    apiGetMock.mockImplementation(routes({ renewals: [renewal("c-9", 10)] }));
    const user = userEvent.setup();
    render(<MyDay organizationSlug="test-klinik" />);
    await user.click(await screen.findByRole("tab", { name: /Termine/ }));
    expect(screen.getByText("Keine Termine in den nächsten 30 Tagen.")).toBeInTheDocument();
  });

  it("Reiter Zahlen: Vertragskosten im Überblick mit drei Kennzahlen, Hinweis bei Teilübersicht und Kosten je Vertrag", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/register/reports/portfolio")) return Promise.resolve({
        totals: { contracts: 3, running: 3, annual_cost: "120000.00", cost_current_year: "1.00", income_current_year: "0.00",
          amounts: { annual_cost: { value: "120000.00", currency: "EUR", known: 2, missing: 1, other_currencies: {} } } },
        insights: [], cost_by: { contract_type: [{ label: "Wartung", value: null, count: 2, annual_cost: "96000.00", cost_current_year: null }] },
      });
      if (path.includes("cost_current_year")) return Promise.resolve({ total: 1, items: [{ contract_id: "c-3", values: { register_number: "000003", short_description: "PACS" }, group: [] }], groups: [], totals: { count: 1, sums: {} } });
      if (path.startsWith("/api/register/grid")) return Promise.resolve({ total: 2, items: [
        { contract_id: "c-1", values: { register_number: "000001", short_description: "CT", annual_cost: "72000" }, group: [] },
        { contract_id: "c-2", values: { register_number: "000002", short_description: "MRT", annual_cost: "48000" }, group: [] },
      ], groups: [], totals: { count: 2, sums: {} } });
      return routes()(path);
    });
    const user = userEvent.setup();
    render(<MyDay organizationSlug="test-klinik" />);
    await user.click(await screen.findByRole("tab", { name: "Zahlen" }));
    const panel = screen.getByRole("tabpanel", { name: "Zahlen" });
    expect(within(panel).getByRole("heading", { name: /Vertragskosten im Überblick/ })).toBeInTheDocument();
    expect(within(panel).getByText("Erfasste Jahreskosten")).toBeInTheDocument();
    expect(within(panel).getAllByText(/120.000,00/).length).toBeGreaterThan(0);
    expect(within(panel).getByText("2 von 3 Verträgen")).toBeInTheDocument();
    expect(within(panel).getByText("1 unvollständig")).toBeInTheDocument();
    expect(within(panel).getByRole("note")).toHaveTextContent("Fehlende Kosten sind nicht als 0 € enthalten.");
    expect(within(panel).getByText("Wartung")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: /Ergänzen\s*: 000003 · PACS/ })).toHaveAttribute("href", expect.stringContaining("/contracts/c-3"));
    const table = within(panel).getByRole("table");
    expect(within(table).getByText("Summe (2 Verträge)")).toBeInTheDocument();
  });

  it("Reiter Kündigung: Tafel Dringend · Demnächst · Nicht berechenbar mit Fakten je Vertrag", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/register/renewals")) return Promise.resolve({
        items: [renewal("c-6", 60), renewal("c-7", 12), renewal("c-8", 30, { decision: { decision: "renew", label: "Verlängern", status: "planned" } })],
        not_evaluable: [{ contract_id: "c-9", register_number: "000009", short_description: "Ohne Ende", reason: "Laufzeitangaben unvollständig" }],
      });
      return routes()(path);
    });
    const user = userEvent.setup();
    render(<MyDay organizationSlug="test-klinik" />);
    const tab = await screen.findByRole("tab", { name: /Kündigung/ });
    expect(tab.querySelector(".my-day-badge")).toHaveClass("is-critical");
    await user.click(tab);
    const panel = screen.getByRole("tabpanel", { name: /Kündigung/ });
    const urgent = within(panel).getByRole("region", { name: /Dringend/ });
    expect(within(urgent).getAllByRole("article")).toHaveLength(2);
    expect(within(urgent).getAllByRole("article")[0]).toHaveTextContent("Noch 12 Tage");
    expect(within(urgent).getAllByRole("article")[1]).toHaveTextContent("Verlängern");
    expect(within(urgent).getAllByRole("link", { name: /Kündigung vorbereiten/ })[0]).toHaveAttribute("href", "/contracts/c-7?tab=deadlines");
    expect(within(within(panel).getByRole("region", { name: /Demnächst/ })).getByRole("link", { name: /Vertrag prüfen/ })).toBeInTheDocument();
    const unknown = within(panel).getByRole("region", { name: /Nicht berechenbar/ });
    expect(within(unknown).getByText("Laufzeitangaben unvollständig")).toBeInTheDocument();
    expect(within(unknown).getByRole("link", { name: /Laufzeit ergänzen/ })).toBeInTheDocument();
    expect(within(panel).getByText("Vorbereitung versendet keine Kündigung.")).toBeInTheDocument();
  });

  it("Tafel „Was steht an?“: Hinweise in drei Spalten nach Art, je Karte ein Knopf", async () => {
    apiGetMock.mockImplementation(routes({
      deadlines: [deadline("1", -2)], review: 1,
      insights: [
        { key: "no_end", label: "x", count: 2, filter: { column: "possible_end", op: "empty" }, severity: "critical" },
        { key: "no_finance", label: "y", count: 2, filter: { column: "cost_current_year", op: "empty" }, severity: "warning" },
      ],
    }));
    render(<MyDay organizationSlug="test-klinik" />);
    expect(await screen.findByRole("heading", { name: /Was steht an\?/ })).toHaveTextContent("4 Hinweise");
    const urgent = screen.getByRole("region", { name: /Dringend/ });
    expect(within(urgent).getByRole("link", { name: /Öffnen/ })).toHaveAttribute("href", "/contracts/c-1?tab=deadlines");
    const review = screen.getByRole("region", { name: /Zur Prüfung/ });
    expect(within(review).getByText("1 Vertrag wartet auf Ihre Prüfung")).toBeInTheDocument();
    const data = screen.getByRole("region", { name: /Daten ergänzen/ });
    expect(within(data).getAllByRole("link")).toHaveLength(2);
    expect(screen.getByText("Hinweise können denselben Vertrag betreffen.")).toBeInTheDocument();
  });

  it("Zur Prüfung nennt die Verträge und wie viele wesentliche Entscheidungen warten – Klick führt zur Prüfung", async () => {
    apiGetMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/contracts/c-3")) return Promise.resolve({ field_review: { essential_open: 5 } });
      if (path.startsWith("/api/register/grid") && path.includes("review_pending")) return Promise.resolve({ total: 4, items: [{ contract_id: "c-3", values: { register_number: "000003", short_description: "Wartung OEC" }, group: [] }], groups: [], totals: { count: 1, sums: {} } });
      return routes({ review: 4 })(path);
    });
    render(<MyDay organizationSlug="test-klinik" />);
    const review = await screen.findByRole("region", { name: /Zur Prüfung/ });
    expect(await within(review).findByText("5 wesentliche Entscheidungen warten")).toBeInTheDocument();
    expect(within(review).getByText("000003 · Wartung OEC")).toBeInTheDocument();
    expect(within(review).getByRole("link", { name: /Wesentliche Angaben prüfen/ })).toHaveAttribute("href", "/contracts/c-3?tab=documents&subtab=review");
    expect(within(review).getByRole("link", { name: /und 3 weitere Verträge/ })).toHaveAttribute("href", "/register?ansicht=review");
  });
});
