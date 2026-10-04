import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RegisterGrid from "@/components/register/RegisterGrid";
import type { GridColumn, GridResponse, GridSpec } from "@/lib/domain-api/registerGrid";

const api = vi.hoisted(() => ({
  getGridColumns: vi.fn(),
  listSavedViews: vi.fn(),
  getGrid: vi.fn(),
  getGridTree: vi.fn(),
  getGridValues: vi.fn(),
  downloadGridXlsx: vi.fn(),
  createSavedView: vi.fn(),
  updateSavedView: vi.fn(),
  deleteSavedView: vi.fn(),
  saveBlob: vi.fn(),
}));

vi.mock("@/lib/domain-api/registerGrid", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/registerGrid")>()),
  ...api,
}));

const COLUMNS: GridColumn[] = [
  { key: "register_number", label: "Nr.", type: "text", default: true, groupable: false },
  { key: "short_description", label: "Kurzbeschreibung", type: "text", default: true, groupable: false },
  { key: "business_status", label: "Status", type: "status", default: true, groupable: true, options: [{ value: "in_arbeit", label: "In Arbeit" }, { value: "gueltig", label: "Gültig" }] },
  { key: "hospital", label: "Gesellschaft", type: "enum", default: false, groupable: true },
  { key: "cancel_by", label: "Kündbar bis", type: "date", default: true, groupable: false },
  { key: "annual_cost", label: "Jährliche Kosten (netto)", type: "money", default: true, groupable: false },
];

function grid(spec: Partial<GridSpec>): GridResponse {
  const grouped = (spec.group_by ?? []).length > 0;
  return {
    tree: [{ hospital: "Klinikum A", label: "Klinikum A", count: 1, departments: [{ department: "Radiologie", label: "Radiologie", count: 1 }] }],
    as_of: "2026-10-04",
    spec: spec as GridSpec,
    total: 2,
    totals: { count: 2, sums: { annual_cost: "18000.00", cost_current_year: "15000.00" } },
    groups: grouped ? [
      { path: ["Klinikum A"], labels: ["Klinikum A"], count: 1, sums: { annual_cost: "12000.00" } },
      { path: ["Klinikum B"], labels: ["Klinikum B"], count: 1, sums: { annual_cost: "6000.00" } },
    ] : [],
    items: [
      { contract_id: "c-1", values: { register_number: "000001", short_description: "Wartung MRT", business_status: "In Arbeit", cancel_by: "2026-12-31", annual_cost: "12000.00", hospital: "Klinikum A" }, group: grouped ? ["Klinikum A"] : [] },
      { contract_id: "c-2", values: { register_number: "000002", short_description: "Reinigung", business_status: "Gültig", cancel_by: null, annual_cost: "6000.00", hospital: "Klinikum B" }, group: grouped ? ["Klinikum B"] : [] },
    ],
  };
}

describe("Vertragsregister – Raster", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    try { window.localStorage.clear(); } catch { /* ignore */ }
    api.getGridColumns.mockResolvedValue({ columns: COLUMNS });
    api.listSavedViews.mockResolvedValue({
      can_manage_global: false,
      items: [{ id: "v-1", name: "Kündigungsfrist < 90 Tage", is_global: true, is_system: true, is_own: false, created_by_name: "System",
        config: { columns: ["register_number", "short_description", "cancel_by"], filters: [{ column: "cancel_by", op: "within_days", value: 90 }], sort: { column: "cancel_by", dir: "asc" }, group_by: [], q: null, include_deleted: false } }],
    });
    api.getGrid.mockImplementation(async (_slug: string, spec: Partial<GridSpec>) => grid(spec));
    api.getGridValues.mockResolvedValue({ column: "hospital", values: [{ value: "Klinikum A", label: "Klinikum A", count: 1 }, { value: "Klinikum B", label: "Klinikum B", count: 1 }] });
    api.createSavedView.mockImplementation(async (_slug: string, payload: { name: string }) => ({ id: "v-2", name: payload.name, config: {}, is_global: false, is_system: false, is_own: true, created_by_name: "Admin" }));
    api.downloadGridXlsx.mockResolvedValue({ blob: new Blob(["x"]), filename: "register.xlsx" });
  });

  it("zeigt formatierte Werte mit Summen und ist barrierefrei", async () => {
    const { container } = render(<RegisterGrid organizationSlug="test-klinik" />);
    const table = await screen.findByRole("table");
    expect(within(table).getByRole("link", { name: "000001" })).toHaveAttribute("href", "/contracts/c-1?tab=register");
    expect(within(table).getByText("31.12.2026")).toBeInTheDocument();
    expect(within(table).getByText(/12\.000,00/)).toBeInTheDocument();
    expect(screen.getByText(/Jährliche Kosten gesamt 18\.000,00/)).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("wendet gespeicherte Ansicht, Gruppierung, Filter und Baum serverseitig an", async () => {
    const user = userEvent.setup();
    render(<RegisterGrid organizationSlug="test-klinik" />);
    await screen.findByRole("table");

    await user.selectOptions(screen.getByLabelText("Ansicht"), "v-1");
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({ filters: [{ column: "cancel_by", op: "within_days", value: 90 }] }), { offset: 0, limit: 100, includeTree: true }));
    expect(screen.getByText("Kündbar bis in den nächsten 90 Tagen")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Gruppieren nach"), "hospital");
    expect(await screen.findByText(/1 Verträge · 12\.000,00/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Filter hinzufügen" }));
    const editor = screen.getByRole("form", { name: "Filter hinzufügen" });
    await user.selectOptions(within(editor).getByLabelText("Spalte"), "hospital");
    await user.click(await within(editor).findByLabelText(/Klinikum B/));
    await user.click(within(editor).getByRole("button", { name: "Filter anwenden" }));
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({
      filters: [{ column: "cancel_by", op: "within_days", value: 90 }, { column: "hospital", op: "in", value: ["Klinikum B"] }],
      group_by: ["hospital"],
    }), expect.anything()));

    await user.click(screen.getByRole("button", { name: /Radiologie/ }));
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({
      filters: [{ column: "cancel_by", op: "within_days", value: 90 }, { column: "hospital", op: "in", value: ["Klinikum A"] }, { column: "department", op: "in", value: ["Radiologie"] }],
    }), expect.anything()));
  });

  it("speichert eine persönliche Ansicht und exportiert die aktuelle Ansicht", async () => {
    const user = userEvent.setup();
    render(<RegisterGrid organizationSlug="test-klinik" />);
    await screen.findByRole("table");
    await user.click(screen.getByRole("button", { name: "Kündbar bis" }));
    await user.click(screen.getByRole("button", { name: "Speichern unter…" }));
    expect(screen.queryByLabelText(/global/)).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Name der Ansicht"), "Meine Fristen");
    await user.click(within(screen.getByRole("form", { name: "Ansicht speichern" })).getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.createSavedView).toHaveBeenCalledWith("test-klinik", expect.objectContaining({ name: "Meine Fristen", is_global: false, config: expect.objectContaining({ sort: { column: "cancel_by", dir: "asc" } }) })));
    expect(await screen.findByText("Ansicht „Meine Fristen“ angelegt.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Excel exportieren" }));
    expect(api.downloadGridXlsx).toHaveBeenCalledWith("test-klinik", expect.objectContaining({ sort: { column: "cancel_by", dir: "asc" } }), "Meine Fristen");
    expect(api.saveBlob).toHaveBeenCalled();
  });
});

describe("Vertragsliste – Übernahme der früheren Liste", () => {
  it("übersetzt alte Listenansichten in Registerfilter", async () => {
    const { legacyQueryToSpec } = await import("@/components/register/RegisterGrid");
    expect(legacyQueryToSpec("q=CT&risk=high&requires_review=true&automatic_renewal=true&critical_cancellation=true")).toEqual({
      q: "CT",
      filters: [
        { column: "risk", op: "in", value: ["Hoch"] },
        { column: "review_pending", op: "is", value: true },
        { column: "term_model", op: "in", value: ["Automatische Verlängerung"] },
        { column: "cancel_by", op: "within_days", value: 90 },
      ],
    });
  });
});
