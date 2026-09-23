import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "@/app/page";
import NachweisePage from "@/app/nachweise/page";
import type { ContractListResponse } from "@/lib/contract-types";
import type { DashboardOverview } from "@/lib/dashboard-types";

const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Empty States DE (UAT Defect H)", () => {
  it("Nachweise: 'Keine Verträge verfügbar' ohne Verträge", async () => {
    const empty: ContractListResponse = {
      items: [],
      total_count: 0,
      page: 1,
      page_size: 25,
      has_more: false,
      facets: { status: {}, risk: {}, warning_type: {} } as never,
      freshness: {
        data_freshness: "current",
        warning_evaluation_as_of_date: "2026-09-06",
      },
    };
    apiGetMock.mockResolvedValue(empty);
    render(<NachweisePage />);
    expect(
      await screen.findByRole("heading", { name: "Keine Verträge verfügbar" })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Importieren Sie Verträge, um deren Quellen/)
    ).toBeInTheDocument();
  });

  it("Übersicht: 'Keine Arbeitsdaten verfügbar' ohne Kennzahlen", async () => {
    apiGetMock.mockResolvedValue({ kpis: null } as unknown as DashboardOverview);
    render(<DashboardPage />);
    expect(
      await screen.findByRole("heading", { name: "Keine Arbeitsdaten verfügbar" })
    ).toBeInTheDocument();
  });
});