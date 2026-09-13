import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ContractsPage from "@/app/contracts/page";
import type { ContractListItem, ContractListResponse } from "@/lib/contract-types";

const apiGetMock = vi.fn();
const nav = { calls: [] as string[] };
let searchString = "";

vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
}));

vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({ organizationSlug: "test-klinik" }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: (value: string) => {
      nav.calls.push(value);
      const query = value.split("?")[1] ?? "";
      searchString = query;
    },
    push: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams(searchString),
  usePathname: () => "/contracts",
}));

function item(overrides: Partial<ContractListItem> = {}): ContractListItem {
  return {
    contract_id: "11111111-1111-1111-1111-111111111111",
    contract_number: "V-100",
    contract_title: "Wartungsvertrag MRT",
    supplier: "Siemens Healthineers",
    status: "active",
    risk_level: "medium",
    annual_cost: { amount: "42500.00", currency: "EUR", unreliable: false },
    contract_end_date: "2026-12-31",
    latest_cancellation_date: "2026-06-30",
    primary_warning: { warning_type: "contract_end_approaching", severity: "medium", title_de: "Vertragsende nähert sich", target_date: "2026-12-31", days_remaining: 122, requires_review: false, requires_action: true },
    requires_review: false,
    ...overrides,
  };
}

function fixture(overrides: Partial<ContractListResponse> = {}): ContractListResponse {
  return {
    items: [item()],
    total_count: 1,
    page: 1,
    page_size: 25,
    has_next: false,
    has_previous: false,
    freshness: {
      request_as_of_date: "2026-08-31",
      warning_evaluation_as_of_date: "2026-08-31",
      data_freshness: "current",
    },
    ...overrides,
  };
}

function setSearch(value: string) {
  searchString = value;
}

beforeEach(() => {
  vi.clearAllMocks();
  nav.calls = [];
  searchString = "";
  apiGetMock.mockResolvedValue(fixture());
});

afterEach(() => cleanup());

describe("Verträge (STEP 13)", () => {
  it("lädt und zeigt Verträge", async () => {
    render(<ContractsPage />);
    expect(await screen.findByText("Wartungsvertrag MRT")).toBeInTheDocument();
    expect(screen.getByText("Siemens Healthineers")).toBeInTheDocument();
  });

  it("zeigt Filter aus der URL", async () => {
    setSearch("q=wartung&status=active&risk_level=medium");
    render(<ContractsPage />);
    expect(await screen.findByDisplayValue("wartung")).toBeInTheDocument();
    expect(apiGetMock).toHaveBeenCalledWith(expect.stringContaining("q=wartung"));
  });

  it("zeigt den Lieferanten zusätzlich zur Vertragszeile", async () => {
    render(<ContractsPage />);
    await screen.findByText("Wartungsvertrag MRT");
    expect(screen.getAllByText("Siemens Healthineers").length).toBeGreaterThan(0);
  });

  it("zeigt jährliche Kosten aus dem Backend", async () => {
    render(<ContractsPage />);
    await screen.findByText("Wartungsvertrag MRT");
    expect(screen.getByText(/42\.500,00/)).toBeInTheDocument();
  });

  it("zeigt verlässliche Unknown-Semantik für fehlende Kosten", async () => {
    apiGetMock.mockResolvedValue(fixture({ items: [item({ annual_cost: { amount: null, currency: null, unreliable: true } })] }));
    render(<ContractsPage />);
    await screen.findByText("Wartungsvertrag MRT");
    expect(screen.getByText(/Nicht verfügbar/)).toBeInTheDocument();
  });

  it("zeigt Warnung und Priorität", async () => {
    render(<ContractsPage />);
    expect(await screen.findByText("Vertragsende nähert sich")).toBeInTheDocument();
    expect(screen.getByText("Mittel")).toBeInTheDocument();
  });

  it("zeigt die Seitennavigation", async () => {
    render(<ContractsPage />);
    await screen.findByText("Wartungsvertrag MRT");
    expect(screen.getByText(/Seite 1/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Zurück/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Weiter/ })).toBeDisabled();
  });

  it("zeigt aktive Filter", async () => {
    setSearch("risk_level=medium");
    render(<ContractsPage />);
    await screen.findByText("Wartungsvertrag MRT");
    expect(screen.getByText(/1 aktiver Filter/)).toBeInTheDocument();
  });

  it("kann Filter zurücksetzen", async () => {
    setSearch("q=wartung&risk_level=medium");
    render(<ContractsPage />);
    await screen.findByDisplayValue("wartung");
    await userEvent.click(screen.getByRole("button", { name: "Zurücksetzen" }));
    expect(nav.calls[nav.calls.length - 1]).toBe("/contracts");
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
    render(<ContractsPage />);
    await waitFor(() => expect(apiGetMock).toHaveBeenCalled());
    expect(screen.getByRole("link", { name: /V-100 öffnen/ })).toHaveAttribute("href", "/contracts/11111111-1111-1111-1111-111111111111");
  });

  it("zeigt eine Schnellansicht mit Kerninformationen", async () => {
    render(<ContractsPage />);
    await screen.findByText("Wartungsvertrag MRT");
    await userEvent.click(screen.getByRole("button", { name: /in Schnellansicht öffnen/ }));
    expect(screen.getByRole("heading", { name: "Wartungsvertrag MRT" })).toBeInTheDocument();
    expect(screen.getByText("Vollständige Detailansicht öffnen")).toBeInTheDocument();
  });

  it("zeigt bei leerem Ergebnis eine klare Meldung", async () => {
    apiGetMock.mockResolvedValue(fixture({ items: [], total_count: 0 }));
    render(<ContractsPage />);
    await waitFor(() => expect(screen.getByText(/Keine Verträge gefunden/)).toBeInTheDocument());
  });
});
