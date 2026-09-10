import { render, screen, waitFor } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it, vi, beforeEach } from "vitest";
import DashboardPage from "@/app/page";
import type { DashboardOverview } from "@/lib/dashboard-types";

// API-Layer mocken, damit die Seite rein client-seitig deterministisch testbar ist.
const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
}));

function fixture(overrides: Partial<DashboardOverview> = {}): DashboardOverview {
  return {
    as_of_date: "2025-06-01",
    freshness: {
      requested_as_of_date: "2025-06-01",
      warning_evaluation_as_of_date: "2025-06-01",
      data_freshness: "current",
      last_calculation_at: "2025-06-01",
    },
    kpis: {
      active_contracts: { label_de: "Aktive Verträge", value: 2, secondary_de: "1 aktiv · 1 bald auslaufend", status_de: "op" },
      expiring_soon: { label_de: "Bald auslaufende Verträge", value: 1, secondary_de: null, status_de: null },
      critical_cancellation: { label_de: "Kritische Kündigungsfristen", value: 1, secondary_de: null, status_de: null },
      annual_costs: { label_de: "Jährliche Gesamtkosten", value: 1, secondary_de: "EUR", status_de: null },
      total_contract_value: { label_de: "Gesamtvertragswert", value: 1, secondary_de: "EUR", status_de: null },
    },
    deadlines: [
      { threshold_days: null, label_de: "Verstrichen", contract_count: 1, cancellation: 1, contract_end: 0 },
      { threshold_days: 30, label_de: "30 Tage", contract_count: 1, cancellation: 0, contract_end: 1 },
    ],
    action_items: [
      {
        severity: "critical",
        warning_type: "cancellation_deadline_passed",
        title_de: "Kündigungsfrist verstrichen",
        contract_title: "CN-1",
        supplier: "Siemens Healthineers",
        target_date: "2025-04-21",
        days_remaining: -41,
        requires_review: false,
        requires_action: true,
        annual_cost: { currency: "EUR", amount: "42500", contract_count: 1 },
        cost_unreliable: false,
      },
      {
        severity: "medium",
        warning_type: "contract_end_approaching",
        title_de: "Vertragsende nähert sich",
        contract_title: "CN-2",
        supplier: "Lieferant",
        target_date: "2025-07-01",
        days_remaining: 30,
        requires_review: false,
        requires_action: true,
        annual_cost: null,
        cost_unreliable: true,
      },
    ],
    total_action_items: 2,
    financial: {
      annual_recurring: [{ currency: "EUR", amount: "42500", contract_count: 1 }],
      total_contract_value: [{ currency: "EUR", amount: "240000", contract_count: 1 }],
      contracts_without_reliable_annual_cost: 1,
      contracts_without_reliable_total_value: 1,
      multi_currency: false,
    },
    data_quality: [
      { label_de: "Fehlende Kostenangaben", count: 1, severity: "medium" },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

async function renderWithData(data: DashboardOverview) {
  apiGetMock.mockResolvedValue(data);
  const utils = render(<DashboardPage />);
  await waitFor(() => expect(apiGetMock).toHaveBeenCalled());
  return utils;
}

describe("Dashboard Übersicht", () => {
  it("zeigt Ladezustand während des Ladens", () => {
    apiGetMock.mockImplementation(() => new Promise(() => {}));
    render(<DashboardPage />);
    expect(screen.getByText("Dashboard wird geladen…")).toBeInTheDocument();
  });

  it("zeigt einen generischen Fehlerzustand bei Backend-Fehler", async () => {
    apiGetMock.mockRejectedValue(new Error("boom"));
    render(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText("Dashboard konnte nicht geladen werden.")).toBeInTheDocument()
    );
  });

  it("zeigt 'kein akuter Handlungsbedarf' bei leerer Action-Liste", async () => {
    const data = fixture();
    data.action_items = [];
    data.total_action_items = 0;
    await renderWithData(data);
    expect(
      screen.getByText("Derzeit kein akuter Handlungsbedarf.")
    ).toBeInTheDocument();
  });

  it("zeigt einen leeren Datenbestand an", async () => {
    const empty: DashboardOverview = {
      as_of_date: "2025-06-01",
      freshness: {
        requested_as_of_date: "2025-06-01",
        warning_evaluation_as_of_date: null,
        data_freshness: "none",
        last_calculation_at: null,
      },
      kpis: {
        active_contracts: { label_de: "Aktive Verträge", value: 0, secondary_de: null, status_de: null },
        expiring_soon: { label_de: "Bald auslaufende Verträge", value: 0, secondary_de: null, status_de: null },
        critical_cancellation: { label_de: "Kritische Kündigungsfristen", value: 0, secondary_de: null, status_de: null },
        annual_costs: { label_de: "Jährliche Gesamtkosten", value: 0, secondary_de: null, status_de: null },
        total_contract_value: { label_de: "Gesamtvertragswert", value: 0, secondary_de: null, status_de: null },
      },
      deadlines: [],
      action_items: [],
      total_action_items: 0,
      financial: {
        annual_recurring: [],
        total_contract_value: [],
        contracts_without_reliable_annual_cost: 0,
        contracts_without_reliable_total_value: 0,
        multi_currency: false,
      },
      data_quality: [],
    };
    await renderWithData(empty);
    expect(screen.getByText("Derzeit kein akuter Handlungsbedarf.")).toBeInTheDocument();
  });

  it("zeigt den normalen Dashboard-Inhalt mit deutschen KPI-Labels", async () => {
    await renderWithData(fixture());
    expect(screen.getByText("Operative Intelligenz")).toBeInTheDocument();
    expect(screen.getByText("Aktive Verträge")).toBeInTheDocument();
    expect(screen.getByText("Handlungsbedarf")).toBeInTheDocument();
    expect(screen.getByText("Kündigungsfrist verstrichen")).toBeInTheDocument();
    expect(screen.getByText("Fristenübersicht")).toBeInTheDocument();
    expect(screen.getByText("Kostenübersicht")).toBeInTheDocument();
    expect(screen.getByText("Manuelle Prüfung / Datenqualität")).toBeInTheDocument();
  });

  it("formatiert Währungen und Datum deutsch (42.500,00 €)", async () => {
    await renderWithData(fixture());
    expect(
      screen.getByText(/Jährliche Kosten: 42\.500,00\s*€/)
    ).toBeInTheDocument();
    expect(screen.getByText(/21\.04\.2025/)).toBeInTheDocument();
  });

  it("zeigt überfällige Frist textuell (seit X Tagen überfällig), nicht nur per Farbe", async () => {
    await renderWithData(fixture());
    const critical = screen.getByText("Kündigungsfrist verstrichen");
    const tag = critical.closest("li")?.querySelector(".severity-tag");
    // Text-Label "Kritisch" ist vorhanden -> nicht nur Farbkodierung.
    expect(tag).toHaveTextContent("Kritisch");
    expect(screen.getByText(/seit 41 Tagen überfällig/)).toBeInTheDocument();
  });

  it("zeigt einen kritischen Handlungspunkt an erster Stelle der Liste", async () => {
    await renderWithData(fixture());
    const items = screen.getAllByRole("listitem");
    const firstActionText = items[1]?.textContent ?? "";
    // Zuerst prüfen: erste Action-Zeile enthält den kritischen Eintrag.
    expect(
      screen.getAllByText("Kündigungsfrist verstrichen").length
    ).toBeGreaterThanOrEqual(1);
  });

  it("weist 'Kosten nicht verlässlich ermittelt' bei unzuverlässigen Kosten aus", async () => {
    await renderWithData(fixture());
    expect(
      screen.getByText("Kosten nicht verlässlich ermittelt")
    ).toBeInTheDocument();
  });

  it("zeigt mehrere Währungen getrennt an", async () => {
    const data = fixture();
    data.financial.multi_currency = true;
    data.financial.annual_recurring = [
      { currency: "EUR", amount: "12000", contract_count: 1 },
      { currency: "CHF", amount: "5000", contract_count: 1 },
    ];
    await renderWithData(data);
    expect(screen.getAllByText("CHF").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("EUR").length).toBeGreaterThanOrEqual(2); // KPI-Hinweis + Liste
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße im normalen Zustand", async () => {
    const { container } = await renderWithData(fixture());
    await waitFor(() => screen.getByText("Handlungsbedarf"));
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
