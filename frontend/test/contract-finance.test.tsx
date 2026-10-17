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
  updateServiceItem: vi.fn(),
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
      payment_timing: null, payment_reminder: false, note: null, origin: "ai_confirmed", source_key: "costs.monthly_cost", created_by_name: "Admin",
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
      entries: [{ key: "costs.annual_cost", values: { label: "Wartungspauschale", amount: "42000.00", amount_basis: "net", interval: "annual", valid_from: "2026-01-01", currency: "EUR" }, source_field: "costs.annual_cost" }],
      services: [],
    },
    ...overrides,
  };
}

// Preisstaffel wie im Entwurf: Jahr 1 kostenfrei (abgelaufen), Jahr 2 aktuell, Jahr 3 und 4 künftig.
function staffel(): FinanceDto {
  const base = finance().entries[0];
  const year = (index: number, from: string, to: string, amount: string) => ({
    ...base, id: `s-${index}`, label: `Preisstufe ${index}. Vertragsjahr`, cost_type_code: null, amount, interval: "annual" as const,
    valid_from: from, valid_to: to, apply_price_adjustment: false, source_key: `costs.scheduled_prices.${index}`,
  });
  return finance({
    as_of: "2026-10-15",
    entries: [
      year(1, "2025-05-05", "2026-05-04", "0.00"),
      year(2, "2026-05-05", "2027-05-04", "8000.00"),
      year(3, "2027-05-05", "2028-05-04", "8000.00"),
      year(4, "2028-05-05", "2029-05-04", "8000.00"),
    ],
    summaries: [{
      currency: "EUR",
      expense: { current_year: money("5333.33", "6346.67"), to_date: money("4000.00", "4760.00"), remaining_to_end: money("20666.67", "24593.33"), total_term: money("24000.00", "28560.00"), annual_run_rate: money("8000.00", "9520.00") },
      income: { current_year: money("0.00", "0.00"), to_date: money("0.00", "0.00"), remaining_to_end: money("0.00", "0.00"), total_term: money("0.00", "0.00"), annual_run_rate: money("0.00", "0.00") },
      contract_end: "2029-05-04",
      projected_adjustment: false,
      notes: [],
    }],
    price_adjustment: { kind: "fixed", percent: null, index_name: null, next_date: null, interval_months: null },
    suggestions: { entries: [], services: [] },
  });
}

const row = (name: RegExp) => within(screen.getByRole("table", { name: "Finanzeinträge" })).getByRole("row", { name });

describe("Finanzdaten", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    api.getFinance.mockResolvedValue(finance());
    api.createFinanceEntry.mockResolvedValue(finance());
    api.updateFinanceEntry.mockResolvedValue(finance());
    api.acceptFinanceSuggestion.mockResolvedValue(finance({ suggestions: { entries: [], services: [] } }));
    api.setCostAllocations.mockResolvedValue(finance());
  });

  it("zeigt Kopfzahlen, ehrliche Hinweise, Preisanpassung und Herkunft", async () => {
    const { container } = render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    expect((await screen.findAllByText("Jährlich (aktuell)")).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/42\.000,00/).length).toBeGreaterThan(0);
    // Ohne Vertragsende: „Bis Vertragsende“ nicht berechenbar, mit Hinweis und Link.
    expect(screen.getByText("Vertragsende unbekannt")).toBeInTheDocument();
    expect(screen.getByText(/Kein Vertragsende bekannt/)).toBeInTheDocument();
    // Preisanpassung steht in der Berechnungsgrundlage (keine Fußzeile mehr in „Kosten auf einen Blick“).
    const basis = screen.getByRole("heading", { name: "Berechnungsgrundlage" }).closest("section")!;
    const pa = within(basis).getByText("Preisanpassung").nextElementSibling as HTMLElement;
    expect(pa).toHaveTextContent("Prozentual 3 %");
    expect(pa).toHaveTextContent("nächste 01.01.2027");
    expect(within(pa).getByRole("link", { name: "In den Vertragsdaten ändern" })).toHaveAttribute("href", expect.stringContaining("feld=price_adjustment_kind"));
    const glance = screen.getByRole("heading", { name: "Kosten auf einen Blick" }).closest("section")!;
    expect(within(glance).queryByText(/Preisanpassung:/)).not.toBeInTheDocument();
    expect(within(glance).queryByText(/Finanzeintrag · |Finanzeinträge · /)).not.toBeInTheDocument();
    // Herkunft am Eintrag und in der Legende.
    expect(screen.getAllByText("KI · Bestätigt").filter((node) => !node.closest(".fin-legend"))).toHaveLength(1);
    expect(within(container.querySelector(".fin-legend") as HTMLElement).getByText("KI · Ungeprüft")).toBeInTheDocument();
    // Keine Zeitraum-Tabelle mehr (gleiche Zahlen wie die Kennzahlen).
    expect(screen.queryByRole("table", { name: "Finanzübersicht EUR" })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Kosten auf einen Blick: Gesamtkosten, Rechenzeile, Preisanpassung, Säulen je Vertragsjahr und Mehrkosten", async () => {
    const year = (index: number, start: string, end: string, net: string, factor: string) => ({
      index, start, end, months: 12, partial: false, amount: money(net, (Number(net) * 1.19).toFixed(2)), without_adjustment: money("8000.00", "9520.00"), factor,
    });
    const base = finance();
    api.getFinance.mockResolvedValue(finance({
      as_of: "2026-06-30",
      price_adjustment: { kind: "percent", percent: "1.500", index_name: null, next_date: "2027-01-01", interval_months: 12 },
      summaries: [{
        ...base.summaries[0],
        expense: { current_year: money("8000.00", "9520.00"), to_date: money("4000.00", "4760.00"), remaining_to_end: money("20361.80", "24230.54"), total_term: money("24361.80", "28990.54"), annual_run_rate: money("8000.00", "9520.00") },
        contract_end: "2028-12-31",
        projected_adjustment: true,
        notes: [],
        contract_years: [year(1, "2026-01-01", "2026-12-31", "8000.00", "1.000000"), year(2, "2027-01-01", "2027-12-31", "8120.00", "1.015000"), year(3, "2028-01-01", "2028-12-31", "8241.80", "1.030225")],
        total_without_adjustment: money("24000.00", "28560.00"),
      }],
    }));
    const { container } = render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" contractStart="2026-01-01" />);
    const glance = (await screen.findByRole("heading", { name: "Kosten auf einen Blick · 3 Vertragsjahre" })).closest("section")!;
    const total = within(glance).getByText("Gesamtkosten").closest("div")!;
    expect(total).toHaveTextContent("24.361,80 €");
    expect(total).toHaveTextContent("Gesamte Vertragslaufzeit · inkl. Erhöhungen");
    expect(within(glance).getByText(/bisher \+/)).toHaveTextContent("4.000,00 € bisher + 20.361,80 € verbleibend = 24.361,80 € gesamt");
    const pa = within(glance).getByRole("heading", { name: "Preisanpassung" }).closest("section")!;
    expect(pa).toHaveTextContent("+1,5 % jährlich");
    expect(pa).toHaveTextContent("Anpassungen2 in 3 Jahren");
    expect(pa).toHaveTextContent("Preis im Jahr 3");
    expect(pa).toHaveTextContent("Vorjahrespreis × 1,015");
    expect(within(glance).getByRole("heading", { name: /Jahreskosten inklusive Steigerung/ })).toBeInTheDocument();
    expect(within(glance).getByRole("table", { name: "Jahreskosten je Vertragsjahr" })).toHaveTextContent("8.241,80 €");
    expect(within(glance).getByText("Aktuell")).toBeInTheDocument();
    const increase = container.querySelector(".fin-increase") as HTMLElement;
    expect(increase).toHaveTextContent("Ohne Erhöhung (3 Jahre)24.000,00 €");
    expect(increase).toHaveTextContent("Mehrkosten über 3 Jahre+361,80 €");
    expect(increase).toHaveTextContent("Preissteigerung bis Jahr 3+3,02 %");
    expect(within(glance).queryByRole("table", { name: "Jahrestabelle" })).not.toBeInTheDocument();
    await userEvent.click(within(glance).getByRole("button", { name: "Brutto" }));
    expect(total).toHaveTextContent("28.990,54 €");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("jede Karte trägt ihre Kennfarbe (tone)", async () => {
    api.getFinance.mockResolvedValue(finance({ primary_cost_center: { cost_center_id: "cc1", code: "471100", name: "Radiologie", annual_net: "12000" } }));
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    const tone = async (name: string) => (await screen.findByRole("heading", { name })).closest("section")?.getAttribute("data-tone");
    expect(await tone("Kosten auf einen Blick")).toBe("cost");
    expect(await tone("Finanzeinträge")).toBe("cost");
    expect(await tone("Kostenstellen-Aufteilung")).toBe("department");
    expect(await tone("Zu prüfen")).toBe("ai");
    expect(await tone("Berechnungsgrundlage")).toBe("accent");
    expect(screen.queryByRole("heading", { name: "Details aus dem Dokument" })).not.toBeInTheDocument();
  });

  it("Staffel: Zahlung als Signal mit Symbol und Wort, Vertragsjahr, leere Kostenart ausgeblendet", async () => {
    api.getFinance.mockResolvedValue(staffel());
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" contractStart="2025-05-05" />);
    await screen.findByRole("table", { name: "Finanzeinträge" });
    const expectSignal = (scope: HTMLElement, word: string) => {
      const label = within(scope).getByText(word);
      const signal = label.closest(".signal");
      expect(signal).not.toBeNull();
      expect(signal!.querySelector("svg")).not.toBeNull();
    };
    expectSignal(row(/Vertragsjahr 1/), "Keine Zahlung");
    expectSignal(row(/Vertragsjahr 2/), "Nicht erfasst");
    expectSignal(row(/Vertragsjahr 3/), "Fällig 2027");
    expectSignal(row(/Vertragsjahr 4/), "Fällig 2028");
    expect(row(/Vertragsjahr 1/)).toHaveTextContent("kostenfrei");
    // Bezeichnung nur „Vertragsjahr N“, der Stand steht farbig daneben.
    expect(row(/Vertragsjahr 2/)).not.toHaveTextContent("Preisstufe");
    expectSignal(row(/Vertragsjahr 1/), "Abgelaufen");
    expectSignal(row(/Vertragsjahr 2/), "Aktuell · noch 6 Monate");
    expect(within(row(/Vertragsjahr 4/)).getByText("Geplant")).toBeInTheDocument();
    // Aktuelle Zeile ohne Zahlungszeitpunkt: „Zahlung erfassen“; Bearbeiten nur im „⋯“-Menü.
    expect(within(row(/Vertragsjahr 2/)).getByRole("button", { name: "Zahlung erfassen" })).toBeInTheDocument();
    expect(within(row(/Vertragsjahr 3/)).queryByRole("button", { name: /bearbeiten/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Kostenart" })).not.toBeInTheDocument();
    expect(screen.getByText(/Kostenart: in keinem Eintrag gepflegt – Spalte ausgeblendet/)).toBeInTheDocument();
    expect(screen.getAllByText("Vertragsjahr 2").length).toBeGreaterThan(0);
    // Balken je Vertragsjahr: für Screenreader als Tabelle.
    const years = screen.getByRole("table", { name: "Kosten je Vertragsjahr" });
    expect(within(years).getAllByRole("row")).toHaveLength(5);
    expect(screen.getByText(/Summe 24\.000,00/)).toBeInTheDocument();
  });

  it("Netto/Brutto gilt für alle Beträge und wird gemerkt", async () => {
    const user = userEvent.setup();
    api.getFinance.mockResolvedValue({ ...staffel(), primary_cost_center_id: "cc1", primary_cost_center: { cost_center_id: "cc1", code: "471100", name: "Radiologie", annual_net: "8000.00" } });
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" contractStart="2025-05-05" />);
    await screen.findByRole("table", { name: "Finanzeinträge" });
    expect(screen.getByRole("columnheader", { name: "Betrag netto" })).toBeInTheDocument();
    expect(within(row(/Vertragsjahr 2/)).getAllByText(/8\.000,00/)[0]).toHaveClass("fin-amount");
    // Ein Umschalter (in „Kosten auf einen Blick“) stellt alle Beträge des Reiters um.
    expect(screen.getAllByRole("button", { name: "Brutto" })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Brutto" }));
    expect(screen.getByRole("button", { name: "Brutto" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("columnheader", { name: "Betrag brutto" })).toBeInTheDocument();
    expect(within(row(/Vertragsjahr 2/)).getAllByText(/9\.520,00/)[0]).toHaveClass("fin-amount");
    expect(screen.getAllByText(/9\.520,00/).length).toBeGreaterThan(2);
    expect(window.localStorage.getItem("medflux.kosten.nb")).toBe("gross");
    // Auch die Kostenstellen-Aufteilung zeigt jetzt brutto.
    const split = screen.getByRole("heading", { name: "Kostenstellen-Aufteilung" }).closest("section")!;
    expect(within(split).getByText("Basis: 9.520,00 € brutto / Jahr.")).toBeInTheDocument();
    expect(within(split).getByRole("columnheader", { name: "Betrag / Jahr brutto" })).toBeInTheDocument();
  });

  it("„⋯“-Menü per Tastatur: Pfeil öffnet, Escape gibt den Fokus zurück", async () => {
    const user = userEvent.setup();
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    const trigger = await screen.findByRole("button", { name: "Weitere Aktionen: Wartungspauschale" });
    trigger.focus();
    await user.keyboard("{ArrowDown}");
    const menu = screen.getByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: "Bearbeiten" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(within(menu).getByRole("menuitem", { name: "Preis ändern ab …" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("übernimmt KI-Vorschläge erst auf Klick und legt Einträge an", async () => {
    const user = userEvent.setup();
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Zu prüfen" });
    expect(api.acceptFinanceSuggestion).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Übernehmen" }));
    expect(api.acceptFinanceSuggestion).toHaveBeenCalledWith("test-klinik", "c-1", "finance", "costs.annual_cost");

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
    // Ohne Aufteilung keine Eingabe; sie erscheint erst über „Aufteilen“.
    expect(screen.queryByLabelText("Kostenstelle")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Aufteilen" }));
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

  it("ohne Aufteilung zeigt sie die Hauptkostenstelle (100 %) und teilt von dort aus auf", async () => {
    const user = userEvent.setup();
    api.getFinance.mockResolvedValue(finance({ primary_cost_center_id: "cc1", primary_cost_center: { cost_center_id: "cc1", code: "471100", name: "Radiologie", annual_net: "12000" } }));
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    const section = (await screen.findByRole("heading", { name: "Kostenstellen-Aufteilung" })).closest("section")!;
    const table = within(section).getByRole("table", { name: "Kostenstellen-Aufteilung" });
    expect(within(table).getByRole("row", { name: /471100 · Radiologie \(Hauptkostenstelle\) 100 % 12\.000,00/ })).toBeInTheDocument();
    expect(within(table).getByRole("row", { name: /Summe 100 % 12\.000,00/ })).toBeInTheDocument();
    expect(within(section).getByText("Basis: 42.000,00 € netto / Jahr.")).toBeInTheDocument();
    expect(within(section).getByText("Hauptkostenstelle aus der Organisationszuordnung.")).toBeInTheDocument();
    expect(within(section).getByRole("link", { name: "In der Organisationszuordnung ändern" })).toHaveAttribute("href", "/contracts/c-1?tab=register&abschnitt=ownership");
    await user.click(within(section).getByRole("button", { name: "Aufteilen" }));
    const selects = within(section).getAllByLabelText("Kostenstelle");
    expect(selects).toHaveLength(2);
    expect(selects[0]).toHaveValue("cc1");
    expect(within(section).getAllByLabelText("Anteil %")[0]).toHaveValue("100");
  });

  it("Berechnungsgrundlage aus den Einträgen; „Dokumentdetails ansehen“ führt zu den Dokumenten", async () => {
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    const section = (await screen.findByRole("heading", { name: "Berechnungsgrundlage" })).closest("section")!;
    const value = (label: string) => within(section).getByText(label).nextElementSibling?.textContent;
    expect(value("Steuerbasis")).toBe("Netto");
    expect(value("Mehrwertsteuer")).toBe("19 %");
    expect(value("Währung")).toBe("EUR");
    expect(value("Bezugsperiode")).toBe("Monatlich");
    expect(within(section).getByRole("link", { name: "Dokumentdetails ansehen" })).toHaveAttribute("href", "/contracts/c-1?tab=documents");
  });

  it("ohne Einträge: Berechnungsgrundlage laut Dokument, Fehlendes als „Nicht angegeben“", async () => {
    api.getFinance.mockResolvedValue(finance({ entries: [] }));
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" documentBasis={{ tax_basis: "net", tax_rate_percent: 19, currency: "EUR", source_period: null }} />);
    const section = (await screen.findByRole("heading", { name: "Berechnungsgrundlage" })).closest("section")!;
    expect(within(section).getByText("Laut Dokument (KI), noch nicht gepflegt.")).toBeInTheDocument();
    expect(within(section).getByText("Steuerbasis").nextElementSibling).toHaveTextContent("Netto");
    expect(within(section).getByText("Bezugsperiode").nextElementSibling).toHaveTextContent("Nicht angegeben");
  });

  it("KI-Herkunft: „KI · Bestätigt“ öffnet die Fundstelle, ohne Fundstelle nur die Plakette; kein Fuß, kein Zeitraum-Hinweis", async () => {
    const user = userEvent.setup();
    const open = vi.fn();
    const data = staffel();
    data.summaries[0].period_mismatch = { last_entry_end: "2029-05-04", contract_end: "2029-03-31", kind: "after_end" };
    api.getFinance.mockResolvedValue(data);
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" contractStart="2025-05-05" findSource={(key) => (key === "costs.scheduled_prices.2" ? open : null)} />);
    await screen.findByRole("table", { name: "Finanzeinträge" });
    await user.click(within(row(/Vertragsjahr 2/)).getByRole("button", { name: /KI · Bestätigt .* Quelle öffnen/ }));
    expect(open).toHaveBeenCalledTimes(1);
    expect(within(row(/Vertragsjahr 3/)).getByText("KI · Bestätigt")).toBeInTheDocument();
    expect(within(row(/Vertragsjahr 3/)).queryByRole("button", { name: /Quelle öffnen/ })).not.toBeInTheDocument();
    expect(screen.queryByText("KI-erfasste Einträge bestätigt.")).not.toBeInTheDocument();
    expect(screen.queryByText(/Zeiträume prüfen/)).not.toBeInTheDocument();
  });

  it("ohne Kostenstelle: Hinweis mit Link zur Organisationszuordnung", async () => {
    api.getFinance.mockResolvedValue(finance({ primary_cost_center: null }));
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    const link = await screen.findByRole("link", { name: "In der Organisationszuordnung festlegen" });
    expect(link).toHaveAttribute("href", "/contracts/c-1?tab=register&abschnitt=ownership");
  });

  it("„Zahlung erfassen“ pflegt Zahlungszeitpunkt und Erinnerung", async () => {
    const user = userEvent.setup();
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    await user.click(await screen.findByRole("button", { name: "Zahlung erfassen" }));
    const form = screen.getByRole("form", { name: "Zahlung erfassen: Wartungspauschale" });
    const remind = within(form).getByRole("checkbox", { name: "An Zahlung erinnern" });
    // Ohne Zahlungszeitpunkt keine Erinnerung.
    expect(remind).toBeDisabled();
    await user.selectOptions(within(form).getByLabelText("Zahlungszeitpunkt"), "in_advance");
    await user.click(remind);
    await user.click(within(form).getByRole("button", { name: "Speichern" }));
    expect(api.updateFinanceEntry).toHaveBeenCalledWith("test-klinik", "c-1", "e-1", { payment_timing: "in_advance", payment_reminder: true });
  });

  it("Preis ändern ab …: alter Eintrag endet am Vortag, neuer übernimmt die übrigen Angaben", async () => {
    const user = userEvent.setup();
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    await user.click(await screen.findByRole("button", { name: "Weitere Aktionen: Wartungspauschale" }));
    await user.click(screen.getByRole("menuitem", { name: "Preis ändern ab …" }));
    const form = screen.getByRole("form", { name: "Preis ändern: Wartungspauschale" });
    await user.type(within(form).getByLabelText("Neuer Betrag *"), "3700");
    await user.type(within(form).getByLabelText("Gültig ab *"), "2027-01-01");
    await user.click(within(form).getByRole("button", { name: "Neuen Preis speichern" }));
    expect(api.updateFinanceEntry).toHaveBeenCalledWith("test-klinik", "c-1", "e-1", { valid_to: "2026-12-31" });
    expect(api.createFinanceEntry).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({
      label: "Wartungspauschale", amount: "3700", interval: "monthly", valid_from: "2027-01-01", valid_to: null, cost_type_code: "wartung",
    }));
    expect(await screen.findByText(/Neuer Preis ab 01.01.2027 gespeichert/)).toBeInTheDocument();
  });

  it("bearbeitet einen Eintrag über PATCH; Löschen erst nach Bestätigung", async () => {
    const user = userEvent.setup();
    api.deleteFinanceEntry.mockResolvedValue(finance({ entries: [] }));
    render(<ContractFinancePanel contractId="c-1" orgSlug="test-klinik" />);
    await user.click(await screen.findByRole("button", { name: "Weitere Aktionen: Wartungspauschale" }));
    await user.click(screen.getByRole("menuitem", { name: "Bearbeiten" }));
    const form = screen.getByRole("form", { name: "Finanzeintrag bearbeiten" });
    const amount = within(form).getByLabelText("Betrag *");
    expect(amount).toHaveValue("3500");
    await user.clear(amount);
    await user.type(amount, "3600");
    await user.click(within(form).getByRole("button", { name: "Speichern" }));
    expect(api.updateFinanceEntry).toHaveBeenCalledWith("test-klinik", "c-1", "e-1", expect.objectContaining({ amount: "3600", valid_from: "2026-01-01" }));
    expect(api.createFinanceEntry).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Weitere Aktionen: Wartungspauschale" }));
    await user.click(screen.getByRole("menuitem", { name: "Löschen" }));
    expect(api.deleteFinanceEntry).not.toHaveBeenCalled();
    await user.click(within(screen.getByRole("group", { name: "Löschen bestätigen" })).getByRole("button", { name: "Löschen" }));
    expect(api.deleteFinanceEntry).toHaveBeenCalledWith("test-klinik", "c-1", "e-1");
  });

});
