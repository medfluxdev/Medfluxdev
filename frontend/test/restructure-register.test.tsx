import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RegisterGrid from "@/components/register/RegisterGrid";
import RegisterPage from "@/app/register/page";
import { withParams } from "@/lib/redirect-params";
import type { GridColumn, GridResponse, GridSpec } from "@/lib/domain-api/registerGrid";

const api = vi.hoisted(() => ({
  getGridColumns: vi.fn(),
  listSavedViews: vi.fn(),
  listContractListViews: vi.fn(),
  getGrid: vi.fn(),
  getGridCounts: vi.fn(),
}));
vi.mock("@/lib/domain-api/registerGrid", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/registerGrid")>()),
  ...api,
}));
vi.mock("@/lib/use-permissions", () => ({ usePermissions: () => ({ can: () => true, loading: false }) }));

const COLUMNS: GridColumn[] = [
  { key: "register_number", label: "Nr.", type: "text", default: true, groupable: false },
  { key: "short_description", label: "Kurzbeschreibung", type: "text", default: true, groupable: false },
  { key: "cancel_by", label: "Kündbar bis", type: "date", default: true, groupable: false },
  { key: "annual_cost", label: "Jährliche Kosten (netto)", type: "money", default: true, groupable: false },
];
const VIEWS = [
  { id: "v-review", system_key: "review", name: "Zu prüfen", is_global: true, is_system: true, is_own: false, created_by_name: "System",
    config: { columns: ["register_number"], filters: [{ column: "review_pending", op: "is", value: true }], sort: null, group_by: [], q: null, include_deleted: false } },
  { id: "v-archive", system_key: "archive", name: "Archiv", is_global: true, is_system: true, is_own: false, created_by_name: "System",
    config: { columns: ["register_number"], filters: [], sort: null, group_by: [], q: null, include_deleted: false, archived: true } },
];

function response(spec: Partial<GridSpec>, total = 2): GridResponse {
  return {
    as_of: "2026-10-10", spec: spec as GridSpec, total, groups: [], tree: [],
    totals: { count: total, currency: "EUR", sums: { annual_cost: null, cost_current_year: null }, coverage: { annual_cost: { known: 0, missing: total } } },
    items: total ? [{ contract_id: "c-1", values: { register_number: "000001", short_description: "Wartung", cancel_by: null, annual_cost: null }, group: [] }] : [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  try { window.localStorage.clear(); } catch { /* ignore */ }
  window.history.replaceState(null, "", "/register");
  api.getGridColumns.mockResolvedValue({ columns: COLUMNS });
  api.listSavedViews.mockResolvedValue({ can_manage_global: false, items: VIEWS });
  api.listContractListViews.mockResolvedValue({ items: [], can_manage_global: false });
  api.getGrid.mockImplementation(async (_slug: string, spec: Partial<GridSpec>) => response(spec));
  api.getGridCounts.mockResolvedValue({ bestand: 42, review: 2, archive: 5 });
});

describe("Vertragsliste: Zustand in der Adresse (U4)", () => {
  it("liest Suche, Sortierung und Seite aus der Adresse und schreibt Änderungen zurück", async () => {
    window.history.replaceState(null, "", "/register?q=MRT&sort=cancel_by:desc&seite=2");
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith(
      "test-klinik", expect.objectContaining({ q: "MRT", sort: { column: "cancel_by", dir: "desc" } }), expect.objectContaining({ offset: 100 }),
    ));
    expect(screen.getByLabelText("Suche")).toHaveValue("MRT");
    await waitFor(() => expect(window.location.search).toContain("seite=2"));
    expect(new URLSearchParams(window.location.search).get("sort")).toBe("cancel_by:desc");
  });

  it("zeigt bei Filtern ohne Treffer einen eigenen Leerzustand mit Zurücksetzen", async () => {
    const user = userEvent.setup();
    api.getGrid.mockImplementation(async (_slug: string, spec: Partial<GridSpec>) => response(spec, spec.q ? 0 : 2));
    window.history.replaceState(null, "", "/register?q=gibtsnicht");
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    expect(await screen.findByText(/Die Filter oder die Suche blenden alle Verträge aus/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Filter und Suche zurücksetzen" }));
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({ q: null }), expect.anything()));
  });

  it("öffnet im Bestand nie heimlich eine Reiter-Ansicht aus dem Speicher", async () => {
    window.localStorage.setItem("medflux.register.lastView", "v-archive");
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    await waitFor(() => expect(api.getGrid).toHaveBeenCalled());
    expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({ archived: false }), expect.anything());
    const select = screen.getByLabelText("Ansicht");
    expect(within(select).queryByRole("option", { name: "Archiv" })).not.toBeInTheDocument();
  });
});

describe("Vertragsliste: Reiter", () => {
  it("zeigt Bestand, Zu prüfen und Archiv mit Zahlen und wechselt per Adresse", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);
    const tabs = await screen.findByRole("tablist", { name: "Vertragsbereiche" });
    expect(await within(tabs).findByRole("tab", { name: /Bestand.*42/ })).toHaveAttribute("aria-selected", "true");
    expect(within(tabs).getByRole("tab", { name: /Zu prüfen.*2/ })).toBeInTheDocument();
    await user.click(within(tabs).getByRole("tab", { name: /Archiv.*5/ }));
    expect(window.location.search).toContain("ansicht=archive");
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({ archived: true }), expect.anything()));
  });
});

describe("Weiterleitungen behalten ihre Parameter (U12)", () => {
  it("übernimmt alte Parameter und setzt die Zielansicht", () => {
    expect(withParams("/register", { q: "CT", filter: "[]" }, { ansicht: "review" })).toBe("/register?q=CT&filter=%5B%5D&ansicht=review");
    expect(withParams("/fristen", { nur: "meine", ansicht: "alt" }, { ansicht: "termine" })).toBe("/fristen?nur=meine&ansicht=termine");
    expect(withParams("/stammdaten/vertragspartner", undefined)).toBe("/stammdaten/vertragspartner");
  });
});
