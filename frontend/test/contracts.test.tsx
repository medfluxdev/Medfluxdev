import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractsPage from "@/app/contracts/page";
import type { ContractListResponse } from "@/lib/contract-types";

const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
}));

type NavState = {
  search: string;
  calls: string[];
};

const nav: NavState = { search: "", calls: [] };
function setSearch(str: string) {
  nav.search = str;
}

vi.mock("next/navigation", () => ({
  usePathname: () => "/contracts",
  useRouter: () => ({
    replace: (path: string) => {
      nav.calls.push(String(path));
      const qIndex = String(path).indexOf("?");
      nav.search = qIndex >= 0 ? String(path).slice(qIndex + 1) : "";
    },
    push: (path: string) => {
      nav.calls.push(String(path));
      nav.search = "";
    },
  }),
  useSearchParams: () => new URLSearchParams(nav.search),
}));

function item(overrides: Partial<ContractListResponse["items"][number]> = {}): ContractListResponse["items"][number] {
  return {
    contract_id: "11111111-1111-1111-1111-111111111111",
    contract_number: "CN-1234",
    contract_title: "MRT Wartungsvertrag",
    supplier: "Siemens Healthineers",
    equipment_summary: "MRT, CT",
    status: "active",
    risk_level: "medium",
    automatic_renewal: false,
    contract_end_date: "2026-12-31",
    latest_cancellation_date: "2026-06-30",
    annual_cost: { currency: "EUR", amount: "42500", unreliable: false },
    primary_warning: { warning_type: "contract_end_approaching", severity: "medium", title_de: "Vertragsende nähert sich", target_date: "2026-12-31" },
    requires_action: true,
    requires_review: false,
    ...overrides,
  };
}

function fixture(overrides: Partial<ContractListResponse> = {}): ContractListResponse {
  return {
    organization_slug: "krankenhaus",
    freshness: {
      request_as_of_date: "2026-08-31",
      warning_evaluation_as_of_date: "2026-08-31",
      data_freshness: "current",
    },
    total_count: 2,
    page: 1,
    page_size: 25,
    has_more: false,
    facets: { status_counts: { active: 2 }, requires_action: 1, requires_review: 0, critical_cancellation: 0 },
    items: [
      item(),
      item({
        contract_id: "22222222-2222-2222-2222-222222222222",
        contract_number: "CN-5678",
        contract_title: "CT Wartungsvertrag",
        supplier: "GE Medical",
        annual_cost: { currency: null, amount: null, unreliable: true },
      }),
    ],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  nav.search = "";
  nav.calls = [];
});

async function renderWithData(data: ContractListResponse) {
  apiGetMock.mockReset();
  apiGetMock.mockResolvedValue(data);
  const utils = render(<ContractsPage />);
  await waitFor(() => expect(apiGetMock).toHaveBeenCalled());
  return utils;
}

describe("Verträge (STEP 13)", () => {
  it("zeigt Ladezustand während des Ladens", () => {
    setSearch("q=wartung");
    apiGetMock.mockImplementation(() => new Promise(() => {}));
    render(<ContractsPage />);
    expect(screen.getByText("Verträge werden geladen…")).toBeInTheDocument();
  });

  it("zeigt einen Fehlerzustand bei Backend-Fehler", async () => {
    setSearch("q=wartung");
    apiGetMock.mockRejectedValue(new Error("boom"));
    render(<ContractsPage />);
    await waitFor(() =>
      expect(
        screen.getByText("Vertragsliste konnte nicht geladen werden.")
      ).toBeInTheDocument()
    );
  });

  it("zeigt einen leeren Datenbestand an", async () => {
    const empty = fixture({ total_count: 0, items: [], facets: { status_counts: {}, requires_action: 0, requires_review: 0, critical_cancellation: 0 } });
    await renderWithData(empty);
    expect(screen.getByText("Noch keine Verträge vorhanden.")).toBeInTheDocument();
  });

  it("überträgt den Quick-Filter 'Endet bald' als Status-Filter in die URL (UAT Suche)", async () => {
    await renderWithData(fixture());
    await userEvent.click(screen.getByRole("button", { name: "Endet bald" }));
    expect(nav.search).toContain("status=expiring_soon");
  });

  it("übernimmt die Vertragsnummer als eigenes Filterfeld in die URL (UAT Suche)", async () => {
    await renderWithData(fixture());
    await userEvent.click(
      screen.getByRole("button", { name: "Erweiterte Filter" })
    );
    const input = screen.getByLabelText("Vertragsnummer");
    fireEvent.change(input, { target: { value: "CN-7654" } });
    await waitFor(() =>
      expect(nav.search).toContain("contract_number=CN-7654")
    );
  });

  it("zeigt 'keine Treffer' bei Filter ohne Ergebnisse", async () => {
    setSearch("status=terminated");
    apiGetMock.mockResolvedValue(
      fixture({ total_count: 0, items: [], facets: { status_counts: { terminated: 0 }, requires_action: 0, requires_review: 0, critical_cancellation: 0 } })
    );
    render(<ContractsPage />);
    await waitFor(() =>
      expect(
        screen.getByText("Keine Verträge für die gewählten Filter gefunden.")
      ).toBeInTheDocument()
    );
  });

  it("zeigt Verträge mit deutschen Daten und Währung", async () => {
    await renderWithData(fixture());
    expect(screen.getByRole("heading", { name: "Verträge" })).toBeInTheDocument();
    expect(screen.getByText("CN-1234")).toBeInTheDocument();
    expect(screen.getByText("MRT Wartungsvertrag")).toBeInTheDocument();
    expect(screen.getAllByText(/42\.500,00\s*€/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/31\.12\.2026/).length).toBeGreaterThanOrEqual(2);
  });

  it("zeigt fehlende Kosten als 'Nicht eindeutig', nie 0 €", async () => {
    await renderWithData(fixture());
    const cell = screen.getByText("Nicht eindeutig").closest("td");
    expect(screen.getAllByText("Nicht eindeutig").length).toBeGreaterThanOrEqual(1);
    expect(cell).toHaveClass("unreliable");
    expect(cell?.textContent).not.toContain("€");
  });

  it("zeigt mehrere Währungen korrekt getrennt an", async () => {
    const data = fixture();
    data.items[1].annual_cost = { currency: "CHF", amount: "15000", unreliable: false };
    await renderWithData(data);
    expect(screen.getAllByText(/42\.500,00\s*€/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/15\.000,00\s*CHF/).length).toBeGreaterThanOrEqual(1);
  });

  it("zeigt Warn-Severity textuell (nicht nur per Farbe)", async () => {
    await renderWithData(fixture());
    expect(screen.getAllByText("Mittel").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Vertragsende nähert sich").length).toBeGreaterThanOrEqual(1);
  });

  it("zeigt veraltete Warn-Bewertung an", async () => {
    setSearch("q=wartung");
    apiGetMock.mockResolvedValue(
      fixture({
        freshness: {
          request_as_of_date: "2026-08-31",
          warning_evaluation_as_of_date: "2026-08-01",
          data_freshness: "stale",
        },
      })
    );
    render(<ContractsPage />);
    await waitFor(() => expect(screen.getByText(/veraltet/)).toBeInTheDocument());
  });

  it("überträgt den Quick-Filter an die URL und lädt neu", async () => {
    apiGetMock.mockResolvedValue(fixture());
    const { rerender } = render(<ContractsPage />);
    await waitFor(() => expect(apiGetMock).toHaveBeenCalled());
    vi.clearAllMocks();
    apiGetMock.mockReset();
    apiGetMock.mockResolvedValue(
      fixture({ total_count: 1, items: [item({ contract_id: "33333333-3333-3333-3333-333333333333" })] })
    );
    await userEvent.click(screen.getByRole("button", { name: "Kritische Kündigungsfrist" }));
    expect(nav.calls.length).toBeGreaterThan(0);
    expect(nav.calls[nav.calls.length - 1]).toContain("critical_cancellation=true");
    rerender(<ContractsPage />);
    await waitFor(() =>
      expect(apiGetMock).toHaveBeenCalledWith(expect.stringContaining("critical_cancellation=true"))
    );
  });

  it("navigiert per Zeilen-Klick zum Contract-360-Router des Vertrags", async () => {
    apiGetMock.mockResolvedValue(fixture());
    const user = userEvent.setup();
    render(<ContractsPage />);
    await waitFor(() => expect(apiGetMock).toHaveBeenCalled());

    const row = screen.getByRole("row", { name: /CN-1234/ });
    await user.click(row);
    expect(nav.calls).toContain(
      "/contracts/11111111-1111-1111-1111-111111111111"
    );

    // Vertragsnummer ist ebenfalls ein echter Link zum selben Ziel.
    const numberLink = screen.getByRole("link", { name: "CN-1234 öffnen" });
    expect(numberLink).toHaveAttribute(
      "href",
      "/contracts/11111111-1111-1111-1111-111111111111"
    );
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße im normalen Zustand", async () => {
    const { container } = await renderWithData(fixture());
    await waitFor(() => screen.getByRole("heading", { name: "Verträge" }));
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
