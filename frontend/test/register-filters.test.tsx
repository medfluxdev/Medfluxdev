import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RegisterGrid from "@/components/register/RegisterGrid";
import {
  advancedCount,
  cleanAreaFilters,
  inValues,
  quickLabel,
  readUrlState,
  setArea,
  setInValues,
  toggleFilter,
  writeUrlState,
} from "@/components/register/register-state";
import type { GridColumn, GridFilter, GridResponse, GridSpec, TreeHospital } from "@/lib/domain-api/registerGrid";

const api = vi.hoisted(() => ({
  getGridColumns: vi.fn(),
  listSavedViews: vi.fn(),
  listContractListViews: vi.fn(),
  getGrid: vi.fn(),
  getGridTree: vi.fn(),
  getGridValues: vi.fn(),
}));
vi.mock("@/lib/domain-api/registerGrid", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/registerGrid")>()),
  ...api,
}));
const permissions = vi.hoisted(() => ({ allowed: new Set<string>() }));
vi.mock("@/lib/use-permissions", () => ({ usePermissions: () => ({ can: (key: string) => permissions.allowed.has(key), loaded: true }) }));

const COLUMNS: GridColumn[] = [
  { key: "register_number", label: "Nr.", type: "text", default: true, groupable: false },
  { key: "short_description", label: "Kurzbeschreibung", type: "text", default: true, groupable: false },
  { key: "partner", label: "Vertragspartner", type: "enum", default: true, groupable: true },
  { key: "contract_type", label: "Vertragstyp", type: "enum", default: true, groupable: true },
  { key: "business_status", label: "Status", type: "status", default: true, groupable: true, options: [{ value: "in_arbeit", label: "In Arbeit" }, { value: "gueltig", label: "Gültig" }] },
  { key: "cancel_by", label: "Kündbar bis", type: "date", default: true, groupable: false },
  { key: "possible_end", label: "Vertragsende", type: "date", default: false, groupable: false },
  { key: "hospital", label: "Krankenhaus", type: "enum", default: false, groupable: true },
  { key: "department", label: "Abteilung", type: "enum", default: false, groupable: true },
  { key: "responsible", label: "Verantwortlich", type: "account", default: false, groupable: true },
  { key: "annual_cost", label: "Jährliche Kosten (netto)", type: "money", default: true, groupable: false },
];
const TREE: TreeHospital[] = [
  { hospital: "Klinikum A", label: "Klinikum A", count: 2, departments: [{ department: "Radiologie", label: "Radiologie", count: 2 }] },
  { hospital: null, label: "(ohne Krankenhaus)", count: 1, departments: [{ department: null, label: "(ohne Abteilung)", count: 1 }] },
];
const MINE = { id: "v-mine", name: "Meine Verträge", is_global: true, is_system: true, system_key: "mine", is_own: false, created_by_name: "System",
  config: { columns: ["register_number", "short_description"], filters: [{ column: "responsible", op: "me" }], sort: null, group_by: [], q: null, include_deleted: false } } as const;

function response(spec: Partial<GridSpec>, total = 3): GridResponse {
  return {
    as_of: "2026-10-11", spec: spec as GridSpec, total, groups: [], tree: TREE,
    totals: { count: total, currency: "EUR", sums: { annual_cost: null, cost_current_year: null }, coverage: { annual_cost: { known: 0, missing: total }, cost_current_year: { known: 0, missing: total } } },
    items: total ? [{ contract_id: "c-1", values: { register_number: "000004", short_description: null, annual_cost: null }, group: [] }] : [],
  };
}

const quick = () => within(screen.getByRole("group", { name: "Schnellfilter" }));
const lastSpec = () => api.getGrid.mock.calls[api.getGrid.mock.calls.length - 1][1] as GridSpec;

beforeEach(() => {
  vi.clearAllMocks();
  permissions.allowed = new Set();
  try { window.localStorage.clear(); } catch { /* ignore */ }
  window.history.replaceState(null, "", "/register");
  api.getGridColumns.mockResolvedValue({ columns: COLUMNS });
  api.listSavedViews.mockResolvedValue({ can_manage_global: false, items: [MINE] });
  api.listContractListViews.mockResolvedValue({ items: [], can_manage_global: false });
  api.getGrid.mockImplementation(async (_slug: string, spec: Partial<GridSpec>) => response(spec));
  api.getGridTree.mockResolvedValue({ total: 3, hospitals: TREE });
  api.getGridValues.mockImplementation(async (_slug: string, column: string) => ({
    column, values: column === "partner"
      ? [{ value: "Siemens", label: "Siemens", count: 2 }, { value: "", label: "(ohne)", count: 1 }]
      : [{ value: "Wartungsvertrag", label: "Wartungsvertrag", count: 3 }],
  }));
});

describe("Vertragsliste: Filterzustand (rein)", () => {
  const status: GridFilter = { column: "business_status", op: "in", value: ["gueltig"] };

  it("setzt und entfernt den Schnellfilter einer Spalte, ohne weitere Bedingungen anzufassen", () => {
    const contains: GridFilter = { column: "partner", op: "contains", value: "Sie" };
    let filters = setInValues([contains], "partner", ["Siemens"]);
    expect(filters).toEqual([contains, { column: "partner", op: "in", value: ["Siemens"] }]);
    expect(inValues(filters, "partner")).toEqual(["Siemens"]);
    filters = setInValues(filters, "partner", []);
    expect(filters).toEqual([contains]);
  });

  it("zählt am Knopf „Weitere Filter“ nur, was kein Schnellfilter zeigt", () => {
    const filters: GridFilter[] = [
      status,
      { column: "business_status", op: "in", value: ["in_arbeit"] },
      { column: "hospital", op: "in", value: ["Klinikum A"] },
      { column: "department", op: "in", value: ["Radiologie"] },
      { column: "annual_cost", op: "empty" },
    ];
    // Zweiter Statusfilter und Kostenbedingung zählen; erster Status und Bereich sind Schnellfilter.
    expect(advancedCount(filters)).toBe(2);
  });

  it("setzt Krankenhaus und Abteilung immer gemeinsam und lässt andere Bereichsbedingungen stehen", () => {
    const empty: GridFilter = { column: "department", op: "empty" };
    expect(setArea([status, empty], "Klinikum A", "Radiologie")).toEqual([
      status, empty, { column: "hospital", op: "in", value: ["Klinikum A"] }, { column: "department", op: "in", value: ["Radiologie"] },
    ]);
    expect(setArea(setArea([status], "Klinikum A", "Radiologie"), null)).toEqual([status]);
  });

  it("entfernt Krankenhaus-/Abteilungswerte, die im aktuellen Bereich nicht vorkommen", () => {
    const filters: GridFilter[] = [
      status,
      { column: "hospital", op: "in", value: ["Klinikum B", ""] },
      { column: "department", op: "in", value: ["Kardiologie"] },
    ];
    const cleaned = cleanAreaFilters(filters, TREE);
    expect(cleaned.removed).toEqual(["Klinikum B", "Kardiologie"]);
    expect(cleaned.filters).toEqual([status, { column: "hospital", op: "in", value: [""] }]);
    expect(cleanAreaFilters([status], TREE)).toEqual({ filters: [status], removed: [] });
  });

  it("schaltet Schnellauswahlen an und aus und beschriftet Auswahlen knapp", () => {
    const unknown: GridFilter = { column: "annual_cost", op: "empty" };
    expect(toggleFilter(toggleFilter([], unknown), unknown)).toEqual([]);
    expect(quickLabel("Status", [])).toBe("Status");
    expect(quickLabel("Status", ["Gültig", "In Arbeit", "Beendet"])).toBe("Status: Gültig +2");
  });

  it("schreibt Spalten und „Stornierte einbeziehen“ in die Adresse und liest sie zurück", () => {
    const spec: GridSpec = { columns: ["register_number", "possible_end"], filters: [], sort: null, group_by: [], q: null, include_deleted: true, archived: false };
    writeUrlState("bestand", null, spec, 0, ["register_number"]);
    expect(window.location.search).toContain("spalten=register_number%2Cpossible_end");
    expect(window.location.search).toContain("geloescht=1");
    expect(readUrlState()).toMatchObject({ columns: ["register_number", "possible_end"], includeDeleted: true });
    writeUrlState("bestand", null, { ...spec, columns: ["register_number"], include_deleted: false }, 0, ["register_number"]);
    expect(window.location.search).toBe("");
  });
});

describe("Vertragsliste: Werkzeugleiste", () => {
  it("Schnellfilter, Chips und weitere Filter arbeiten auf demselben Zustand", async () => {
    const user = userEvent.setup();
    const { container } = render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    await screen.findByRole("table");

    await user.click(quick().getByRole("button", { name: /^Status/ }));
    await user.click(screen.getByLabelText("Gültig"));
    await waitFor(() => expect(lastSpec().filters).toEqual([{ column: "business_status", op: "in", value: ["gueltig"] }]));
    expect(quick().getByRole("button", { name: /^Status: Gültig/ })).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(quick().getByRole("button", { name: /^Status: Gültig/ })).toHaveFocus();
    expect(within(screen.getByRole("list", { name: "Aktive Filter" })).getByText("Status: Gültig")).toBeInTheDocument();
    // Der Schnellfilter zählt nicht als „weiterer“ Filter.
    expect(screen.getByRole("button", { name: "Weitere Filter" })).toBeInTheDocument();

    await user.click(quick().getByRole("button", { name: /^Vertragspartner/ }));
    await user.click(await screen.findByLabelText(/Siemens/));
    await waitFor(() => expect(lastSpec().filters).toContainEqual({ column: "partner", op: "in", value: ["Siemens"] }));
    await user.keyboard("{Escape}");

    await user.click(screen.getByRole("button", { name: "Weitere Filter" }));
    const drawer = screen.getByRole("dialog", { name: "Weitere Filter" });
    await user.click(within(drawer).getByRole("button", { name: "Kosten unbekannt" }));
    await user.click(await within(drawer).findByLabelText(/Wartungsvertrag/));
    await waitFor(() => expect(lastSpec().filters).toEqual([
      { column: "business_status", op: "in", value: ["gueltig"] },
      { column: "partner", op: "in", value: ["Siemens"] },
      { column: "annual_cost", op: "empty" },
      { column: "contract_type", op: "in", value: ["Wartungsvertrag"] },
    ]));
    // Ohne Recht keine Option für gelöschte Verträge.
    expect(within(drawer).queryByLabelText("Stornierte einbeziehen")).not.toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "Fertig" }));
    expect(screen.getByRole("button", { name: "Weitere Filter (2)" })).toBeInTheDocument();

    // Chip entfernt genau eine Bedingung; der Schnellfilter folgt.
    await user.click(screen.getByRole("button", { name: "Filter entfernen: Status: Gültig" }));
    await waitFor(() => expect(lastSpec().filters).not.toContainEqual({ column: "business_status", op: "in", value: ["gueltig"] }));
    expect(quick().getByRole("button", { name: /^Status$|^Status ▾$/ })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("„Alle zurücksetzen“ behält Ansicht, Reiter und Darstellung und springt auf Seite 1", async () => {
    const user = userEvent.setup();
    api.getGrid.mockImplementation(async (_slug: string, spec: Partial<GridSpec>) => response(spec, 250));
    window.history.replaceState(null, "", `/register?sicht=v-mine&q=MRT&seite=2&gruppe=partner&filter=${encodeURIComponent(JSON.stringify([{ column: "responsible", op: "me" }, { column: "cancel_by", op: "overdue" }]))}`);
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({ q: "MRT" }), expect.objectContaining({ offset: 100 })));

    await user.click(await screen.findByRole("button", { name: "Alle zurücksetzen" }));
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({
      q: null, filters: [{ column: "responsible", op: "me" }], group_by: ["partner"],
    }), expect.objectContaining({ offset: 0 })));
    expect(screen.getByLabelText("Ansicht")).toHaveValue("v-mine");
  });

  it("eine Filteränderung auf Seite 2 springt auf Seite 1", async () => {
    const user = userEvent.setup();
    api.getGrid.mockImplementation(async (_slug: string, spec: Partial<GridSpec>) => response(spec, 250));
    window.history.replaceState(null, "", "/register?seite=2");
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.anything(), expect.objectContaining({ offset: 100 })));
    expect(screen.getByRole("navigation", { name: "Seiten" })).toHaveTextContent("101–200 von 250");
    await user.click(quick().getByRole("button", { name: /^Status/ }));
    await user.click(screen.getByLabelText("In Arbeit"));
    await waitFor(() => expect(api.getGrid).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({
      filters: [{ column: "business_status", op: "in", value: ["in_arbeit"] }],
    }), expect.objectContaining({ offset: 0 })));
  });

  it("entfernt nach einem Bereichswechsel ungültige Abteilungsfilter aus der Adresse und sagt es", async () => {
    window.history.replaceState(null, "", `/register?filter=${encodeURIComponent(JSON.stringify([{ column: "hospital", op: "in", value: ["Klinikum B"] }, { column: "department", op: "in", value: ["Kardiologie"] }]))}`);
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    expect(await screen.findByText(/aus den Filtern entfernt: Klinikum B, Kardiologie/)).toBeInTheDocument();
    await waitFor(() => expect(lastSpec().filters).toEqual([]));
    expect(api.getGridTree).toHaveBeenCalledWith("test-klinik", { archived: false });
  });

  it("stellt Spalten aus der Adresse wieder her und bietet „Standardspalten“ an", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/register?spalten=register_number,possible_end");
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    await waitFor(() => expect(lastSpec().columns).toEqual(["register_number", "possible_end"]));
    await user.click(screen.getByRole("button", { name: /Darstellung/ }));
    await user.click(screen.getByRole("button", { name: "Standardspalten" }));
    await waitFor(() => expect(lastSpec().columns).toEqual(["register_number", "short_description", "partner", "contract_type", "business_status", "cancel_by", "annual_cost"]));
    expect(window.location.search).not.toContain("spalten");
  });

  it("zeigt ohne Beschreibung „Vertrag <Nr.>“ und ehrlich unbekannte Kosten", async () => {
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    const table = await screen.findByRole("table");
    expect(within(table).getByRole("link", { name: "Vertrag 000004" })).toHaveAttribute("href", "/contracts/c-1?tab=register");
    const summary = screen.getByText("3 Verträge").closest("p")!;
    expect(summary).toHaveTextContent("Keine gepflegten Kostendaten (3 Verträge)");
    expect(summary).not.toHaveTextContent("0,00");
  });

  it("zeigt den Status zuerst als Farbe + Form + Wort; der Link bleibt in der Spalte „Vertrag“", async () => {
    api.getGridColumns.mockResolvedValue({ columns: [COLUMNS[4], ...COLUMNS.filter((item) => item.key !== "business_status")] });
    api.getGrid.mockImplementation(async (_slug: string, spec: Partial<GridSpec>) => ({
      ...response(spec, 2),
      items: [
        { contract_id: "c-1", values: { business_status: "Gültig", register_number: "000001", short_description: "Wartung MRT" }, group: [] },
        { contract_id: "c-2", values: { business_status: "In Arbeit", register_number: "000002", short_description: "Reinigung" }, group: [] },
      ],
    }));
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("columnheader")[0]).toHaveTextContent("Status");
    const valid = within(table).getByText("Gültig").closest(".status-badge");
    expect(valid).toHaveClass("status-badge--success");
    expect(valid?.querySelector("svg.signal-icon")).not.toBeNull();
    expect(within(table).getByText("In Arbeit").closest(".status-badge")).toHaveClass("status-badge--information");
    // Der Status ist kein Link; geöffnet wird der Vertrag über seinen Namen.
    expect(within(table).queryByRole("link", { name: "Gültig" })).not.toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "Wartung MRT" })).toBeInTheDocument();
  });

  it("bietet „Stornierte einbeziehen“ nur mit Recht an und merkt es in der Adresse", async () => {
    const user = userEvent.setup();
    permissions.allowed = new Set(["contract.view_deleted"]);
    render(<RegisterGrid organizationSlug="test-klinik" tab="bestand" />);
    await screen.findByRole("table");
    await user.click(screen.getByRole("button", { name: "Weitere Filter" }));
    await user.click(within(screen.getByRole("dialog", { name: "Weitere Filter" })).getByLabelText("Stornierte einbeziehen"));
    await waitFor(() => expect(lastSpec().include_deleted).toBe(true));
    await waitFor(() => expect(window.location.search).toContain("geloescht=1"));
  });
});
