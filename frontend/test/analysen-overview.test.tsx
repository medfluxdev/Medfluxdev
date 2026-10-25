import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import AnalysenOverview, { shortEuro } from "@/components/analytics/AnalysenOverview";
import type { PortfolioReport, RenewalListItem } from "@/lib/domain-api/registerGrid";

const item = (label: string, annual: string | null, extra: Record<string, unknown> = {}) => ({ label, value: label, count: 1, annual_cost: annual, cost_current_year: annual, ...extra });

function report(overrides: Record<string, unknown> = {}): PortfolioReport {
  return {
    as_of: "2026-10-25",
    totals: { contracts: 3, running: 3, annual_cost: "80000.00", cost_current_year: "70000.00", income_current_year: "0.00",
      amounts: { annual_cost: { value: "80000.00", currency: "EUR", known: 2, missing: 1, other_currencies: {} } } },
    by_status: [{ status: "in_arbeit", label: "In Arbeit", count: 1 }, { status: "gueltig", label: "Gültig", count: 2 }, { status: "gekuendigt", label: "Gekündigt", count: 0 }, { status: "beendet", label: "Beendet", count: 0 }],
    cost_by: {
      hospital: [item("Nord", "50000.00"), item("Süd", "30000.00")],
      device_type: [item("CT", "55000.00", { shared_count: 1, devices_known: 3, cost_per_device: "18333.33" }), item("MRT", "15000.00", { shared_count: 1 }), item("Ohne Gerätetyp", "10000.00")],
      partner: [item("Siemens", "60000.00")], contract_type: [item("Wartungsvertrag", "80000.00")],
    },
    dimensions: [], deadlines_by_month: [], upcoming: [],
    cost_by_year: [
      { year: 2025, expense: "60000.00", income: null, is_projection: false },
      { year: 2026, expense: "72000.00", income: "5000.00", is_projection: false },
      { year: 2027, expense: "80000.00", income: null, is_projection: true },
    ],
    supplier_concentration: { partner: "Siemens", share_percent: "75.0" },
    insights: [
      { key: "no_finance", label: "x", count: 1, filter: { column: "cost_current_year", op: "empty" } },
      { key: "no_end", label: "y", count: 2, filter: { column: "term_status", op: "in", value: ["Unvollständig"] } },
    ],
    ...overrides,
  } as unknown as PortfolioReport;
}

const day = (offset: number) => { const date = new Date("2026-10-25T00:00:00"); date.setDate(date.getDate() + offset); return date.toISOString().slice(0, 10); };
const renewal = (id: string, days: number, cost: string | null, extra: Record<string, unknown> = {}): RenewalListItem => ({
  contract_id: id, register_number: `00000${id.slice(-1)}`, short_description: `Vertrag ${id}`, partner: "Siemens", cancel_by: day(days), days_left: days,
  urgency: "soon", possible_end: null, annual_cost: cost, responsible: null, decision: null, ...extra,
} as RenewalListItem);

const RISK = { contracts: { total: 3, active: 3, archived: 0, by_risk: { high: 4, medium: 9 } }, work_queue: { by_status: {}, by_severity: {} }, scope: { hospital_id: null, hospital_name: null } } as never;

describe("Analysen: vier Fragen", () => {
  it("KPI-Zeile, fehlende Daten, Bestand", async () => {
    const renewals = [renewal("c-1", 20, "30000.00"), renewal("c-2", 80, "12000.00"), renewal("c-3", 150, "5000.00")];
    const { container } = render(<AnalysenOverview report={report()} renewals={renewals} notEvaluable={[]} risk={RISK} />);
    expect(screen.getByText("Jährliche Kosten (netto)").parentElement).toHaveTextContent(/80\.000,00/);
    expect(screen.getByText("Veränderung zum Vorjahr").parentElement).toHaveTextContent("↑ +20 %");
    expect(screen.getByText("Kündbar in 90 Tagen").parentElement).toHaveTextContent("2");
    expect(screen.getByText("Kosten der kündbaren Verträge").parentElement).toHaveTextContent("42.000,00");
    expect(screen.getByRole("note")).toHaveTextContent("1 Vertrag ohne Kosten, 2 ohne Vertragsende – nicht enthalten");
    expect(screen.getByRole("link", { name: "2 gültig" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Veränderung zum Vorjahr zeigt „–“, wenn es kein Vorjahr mit Kosten gibt", () => {
    render(<AnalysenOverview report={report({ cost_by_year: [{ year: 2026, expense: "72000.00", income: null, is_projection: false }] })} renewals={[]} notEvaluable={[]} risk={null} />);
    expect(screen.getByText("kein Vorjahr mit Kosten")).toBeInTheDocument();
  });

  it("Kosten je Jahr: Ist und Prognose, Tabelle, Einnahmen nur wenn vorhanden", async () => {
    const user = userEvent.setup();
    render(<AnalysenOverview report={report()} renewals={[]} notEvaluable={[]} risk={null} />);
    expect(screen.getByRole("img", { name: /2027 80\.000,00\s€ \(Prognose\)/ })).toBeInTheDocument();
    expect(screen.getByText(/Zusätzlich Einnahmen 2026: 5\.000,00 €/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kosten je Jahr als Tabelle" }));
    expect(screen.getByRole("cell", { name: "Prognose" })).toBeInTheDocument();
  });

  it("Wohin fließt das Geld: Gerätetyp geteilt, je Gerät, Summe = Jährliche Kosten", async () => {
    const user = userEvent.setup();
    render(<AnalysenOverview report={report()} renewals={[]} notEvaluable={[]} risk={null} />);
    expect(screen.getByText("Nord")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Gerätetyp" }));
    expect(screen.getAllByText("◐ geteilt")).toHaveLength(2);
    expect(screen.getByText("18.333,33 €")).toBeInTheDocument();
    expect(screen.getByText("je Gerät")).toBeInTheDocument();
    expect(screen.getByText(/Summe/)).toHaveTextContent("80.000,00 € = Jährliche Kosten");
  });

  it("Entscheidungen: nach Kosten sortiert, rot bei ≤ 30 Tagen, Monatskachel filtert", async () => {
    const user = userEvent.setup();
    const renewals = [
      renewal("c-1", 20, "30000.00", { device_types: ["CT", "MRT"], renewal_text: "verlängert sich um 12 Monate" }),
      renewal("c-2", 80, "99000.00"),
      renewal("c-3", 150, null),
    ];
    render(<AnalysenOverview report={report()} renewals={renewals} notEvaluable={[]} risk={null} />);
    const list = document.querySelector(".an-decisions") as HTMLElement;
    const rows = within(list).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Vertrag c-2");
    expect(rows[1]).toHaveTextContent("CT, MRT · verlängert sich um 12 Monate");
    expect(rows[1].querySelector(".an-date")).toHaveClass("is-soon");
    expect(rows[2]).toHaveTextContent("Kosten fehlen");
    expect(screen.getByText(/3 Entscheidungen · zusammen 129 Tsd\. € pro Jahr/)).toBeInTheDocument();
    const month = document.querySelectorAll(".an-months button:not([disabled])")[0] as HTMLButtonElement;
    await user.click(month);
    expect(within(document.querySelector(".an-decisions") as HTMLElement).getAllByRole("listitem").length).toBeLessThan(3);
    expect(screen.getByRole("button", { name: "alle Monate" })).toBeInTheDocument();
  });

  it("Entscheidungen: leer mit Hinweis auf Verträge ohne Vertragsende", () => {
    render(<AnalysenOverview report={report()} renewals={[]} notEvaluable={[{ contract_id: "c-9", register_number: "000009", short_description: "x", reason: "Laufzeitangaben unvollständig" }]} risk={null} />);
    expect(screen.getByText(/keine berechenbare Kündigungsfrist.*1 Vertrag ist das Vertragsende nicht bekannt/)).toBeInTheDocument();
  });

  it("Risiken laut KI-Analyse mit Hoch/Mittel und Abhängigkeit", () => {
    render(<AnalysenOverview report={report()} renewals={[]} notEvaluable={[]} risk={RISK} />);
    expect(screen.getByRole("link", { name: "4 Hoch" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "9 Mittel" })).toBeInTheDocument();
    expect(screen.getByText(/Hinweis der lokalen KI – kein geprüfter Wert/)).toBeInTheDocument();
    expect(screen.getByText("75 %")).toBeInTheDocument();
    expect(screen.getByText(/der Kosten bei Siemens/)).toBeInTheDocument();
    expect(screen.getByText("sehr hohe Konzentration")).toBeInTheDocument();
  });

  it("kürzt Euro", () => {
    expect(shortEuro(452000)).toBe("452 Tsd. €");
    expect(shortEuro(2400000)).toBe("2,4 Mio. €");
    expect(shortEuro(8000)).toBe("8.000 €");
    expect(shortEuro(null)).toBe("–");
  });
});
