import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DeviceTypeComparison from "@/components/analytics/DeviceTypeComparison";
import ContractDeviceTypesPanel from "@/components/contracts/detail/ContractDeviceTypesPanel";

const api = vi.hoisted(() => ({
  listDeviceTypes: vi.fn(),
  getContractDeviceTypes: vi.fn(),
  saveContractDeviceTypes: vi.fn(),
  getDeviceTypeComparison: vi.fn(),
  getContractDepartmentRoles: vi.fn(),
  getOrganizationStructure: vi.fn(),
}));

vi.mock("@/lib/domain-api/deviceTypes", async (original) => ({ ...(await original<object>()), ...api }));
vi.mock("@/lib/domain-api/ownership", () => ({ getContractDepartmentRoles: api.getContractDepartmentRoles }));
vi.mock("@/lib/domain-api/organizations", () => ({ getOrganizationStructure: api.getOrganizationStructure }));
vi.mock("@/components/ui/Toast", () => ({ useToast: () => vi.fn() }));

const kind = (id: string, label: string, area: "medizintechnik" | "it", areaLabel: string, department: string | null = null) => ({
  id, code: id, label, area, area_label: areaLabel, department_id: department ? "d-1" : null, department_name: department,
  keywords: null, description: null, is_active: true, sort_order: 0,
});

describe("Gerätearten am Vertrag", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listDeviceTypes.mockResolvedValue({ items: [kind("ct", "CT", "medizintechnik", "Medizintechnik", "Medizintechnik"), kind("mrt", "MRT", "medizintechnik", "Medizintechnik"), kind("server", "Server", "it", "IT", "IT")], areas: {} });
    // Abteilungen des Vertrags nicht ladbar: Rückfall auf den Namen der verantwortlichen Abteilung.
    api.getContractDepartmentRoles.mockRejectedValue(new Error("down"));
    api.getOrganizationStructure.mockResolvedValue({ hospitals: [], departments: [] });
    api.getContractDeviceTypes.mockResolvedValue({ items: [], suggestions: [{ device_type_id: "ct", label: "CT", reason: "im Dokument: „somatom“" }] });
    api.saveContractDeviceTypes.mockImplementation(async (_org: string, _id: string, items: { device_type_id: string; quantity: number | null; note: string | null }[]) => ({
      items: items.map((item) => ({ ...item, label: item.device_type_id.toUpperCase(), area: "medizintechnik", area_label: "Medizintechnik" })), suggestions: [],
    }));
  });

  it("übernimmt einen Vorschlag, ergänzt die Anzahl je Zeile und fügt hinzu (Abteilung zuerst) – jede Änderung speichert sofort", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    const { container } = render(<ContractDeviceTypesPanel contractId="c-1" orgSlug="test-klinik" canEdit responsibleDepartment="Medizintechnik" onSaved={onSaved} />);
    const suggestions = await screen.findByRole("list", { name: "Vorschläge aus dem Dokument" });
    expect(within(suggestions).getByText("CT")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Gerätearten (0)" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.click(within(suggestions).getByRole("button", { name: "Übernehmen" }));
    await waitFor(() => expect(api.saveContractDeviceTypes).toHaveBeenLastCalledWith("test-klinik", "c-1", [{ device_type_id: "ct", quantity: null, note: null }]));
    const table = await screen.findByRole("table", { name: "Gerätearten des Vertrags" });
    expect(within(table).getByRole("rowheader", { name: "CT" })).toBeInTheDocument();
    expect(within(table).getByText("Nicht angegeben")).toBeInTheDocument();

    await user.click(within(table).getByRole("button", { name: "CT bearbeiten" }));
    await user.type(screen.getByRole("spinbutton", { name: "Anzahl CT" }), "2");
    await user.click(within(table).getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.saveContractDeviceTypes).toHaveBeenLastCalledWith("test-klinik", "c-1", [{ device_type_id: "ct", quantity: 2, note: null }]));

    // Hinzufügen: Geräteart, Anzahl und Notiz auf einmal, dann einmal speichern.
    await user.click(screen.getByRole("button", { name: "Geräteart hinzufügen" }));
    const form = screen.getByRole("form", { name: "Geräteart hinzufügen" });
    const select = within(form).getByRole("combobox", { name: "Geräteart" });
    expect(within(select).getAllByRole("group")[0]).toHaveAttribute("label", "Passend zu den Abteilungen");
    expect(within(form).getByRole("button", { name: "Hinzufügen" })).toBeDisabled();
    await user.selectOptions(select, "server");
    await user.type(within(form).getByRole("spinbutton", { name: "Anzahl" }), "3");
    await user.type(within(form).getByRole("textbox", { name: "Notiz" }), "Rechenzentrum");
    await user.click(within(form).getByRole("button", { name: "Hinzufügen" }));
    await waitFor(() => expect(api.saveContractDeviceTypes).toHaveBeenLastCalledWith("test-klinik", "c-1", [
      { device_type_id: "ct", quantity: 2, note: null },
      { device_type_id: "server", quantity: 3, note: "Rechenzentrum" },
    ]));
    expect(onSaved).toHaveBeenCalledTimes(3);

    // „⋯ → Zuordnung entfernen“ nimmt nur die Zuordnung weg.
    await user.click(screen.getByRole("button", { name: "Weitere Aktionen: Server" }));
    await user.click(screen.getByRole("menuitem", { name: "Zuordnung entfernen" }));
    await waitFor(() => expect(api.saveContractDeviceTypes).toHaveBeenLastCalledWith("test-klinik", "c-1", [{ device_type_id: "ct", quantity: 2, note: null }]));
  });

  it("gleiche Regel wie die Organisationszuordnung: nutzende und übergeordnete Abteilungen zählen", async () => {
    api.getContractDepartmentRoles.mockResolvedValue({ contract_id: "c-1", responsible_department_id: "d-rad", beneficiary_department_ids: ["d-it"], unclassified_department_ids: [] });
    api.getOrganizationStructure.mockResolvedValue({ hospitals: [], departments: [
      { id: "d-mt", hospital_id: "h-1", parent_id: null, name: "Medizintechnik", code: "MT", is_active: true },
      { id: "d-rad", hospital_id: "h-1", parent_id: "d-mt", name: "Radiologie", code: "RAD", is_active: true },
      { id: "d-it", hospital_id: "h-1", parent_id: null, name: "IT-Abteilung", code: "IT", is_active: true },
    ] });
    api.listDeviceTypes.mockResolvedValue({ items: [kind("mrt", "MRT", "medizintechnik", "Medizintechnik"), kind("server", "Server", "it", "IT"), { ...kind("aufzug", "Aufzug", "it", "Haustechnik"), area: "haustechnik" }], areas: {} });
    const user = userEvent.setup();
    render(<ContractDeviceTypesPanel contractId="c-1" orgSlug="test-klinik" canEdit responsibleDepartment="Radiologie" />);
    await user.click(await screen.findByRole("button", { name: "Geräteart hinzufügen" }));
    const select = screen.getByRole("combobox", { name: "Geräteart" });
    await waitFor(() => expect(within(select).getAllByRole("group")[0]).toHaveAttribute("label", "Passend zu den Abteilungen"));
    expect(within(within(select).getAllByRole("group")[0]).getAllByRole("option").map((option) => option.textContent)).toEqual(["MRT", "Server"]);
    expect(within(select).getByRole("group", { name: "Haustechnik" })).toHaveTextContent("Aufzug");
  });

  it("ohne Bearbeitungsrecht nur lesen", async () => {
    api.getContractDeviceTypes.mockResolvedValue({ items: [{ device_type_id: "ct", label: "CT", area: "medizintechnik", area_label: "Medizintechnik", quantity: 2, note: "Haus A" }], suggestions: [] });
    render(<ContractDeviceTypesPanel contractId="c-1" orgSlug="test-klinik" canEdit={false} />);
    const table = await screen.findByRole("table", { name: "Gerätearten des Vertrags" });
    expect(within(table).getByText("2 Geräte")).toBeInTheDocument();
    expect(within(table).getByText("Haus A")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /hinzufügen|entfernen|speichern|übernehmen/i })).not.toBeInTheDocument();
  });
});

describe("Analysen: Gerätearten vergleichen", () => {
  beforeEach(() => vi.clearAllMocks());

  it("Übersicht je Geräteart, dann Verträge mit Kosten je Gerät oder Grund", async () => {
    const user = userEvent.setup();
    api.getDeviceTypeComparison.mockImplementation(async (_org: string, deviceType?: string | null) => (deviceType
      ? {
        as_of: "2026-10-11", level: "contracts", device_type: "CT", count: 2, truncated: false, devices_known: 2, devices_missing: 1,
        totals: { value: "70000.00", currency: "EUR", known: 2, missing: 0 },
        register_filter: [{ column: "device_types", op: "in", value: ["CT"] }],
        items: [
          { contract_id: "c-1", register_number: "000001", short_description: "Wartung CT Nord", partner: "Siemens", hospital: "Nord", department: "Radiologie", possible_end: "2028-12-31", currency: "EUR", annual_cost: "40000.00", quantity: 2, other_device_types: [], cost_per_device: "20000.00", cost_per_device_reason: null },
          { contract_id: "c-2", register_number: "000002", short_description: "Service CT Süd", partner: "GE", hospital: "Süd", department: null, possible_end: null, currency: "EUR", annual_cost: "30000.00", quantity: null, other_device_types: ["MRT"], cost_per_device: null, cost_per_device_reason: "Anzahl Geräte nicht gepflegt" },
        ],
      }
      : { as_of: "2026-10-11", level: "types", running_count: 5, without_count: 3, items: [{ label: "CT", value: "CT", count: 2, annual_cost: "70000.00", annual_known: 2, annual_missing: 0, devices_known: 2, devices_missing: 1 }] }));
    const { container } = render(<DeviceTypeComparison organizationSlug="test-klinik" />);
    expect(await screen.findByText("3 von 5 laufenden Verträgen haben noch keine Geräteart.", { exact: false })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "CT" }));
    expect(api.getDeviceTypeComparison).toHaveBeenLastCalledWith("test-klinik", "CT");
    const table = await screen.findByRole("table", { name: "Verträge für CT" });
    expect(within(table).getByText("20.000,00 €")).toBeInTheDocument();
    expect(within(table).getByText(/nicht berechenbar/)).toHaveTextContent("Anzahl Geräte nicht gepflegt");
    expect(within(table).getByText(/auch MRT/)).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "Anzahl für Service CT Süd erfassen" })).toHaveAttribute("href", expect.stringContaining("tab=relations"));
    expect(screen.getByRole("link", { name: /in der Vertragsliste öffnen/ })).toHaveAttribute("href", expect.stringContaining("device_types"));
    expect(window.location.search).toBe("?geraeteart=CT");
  });

  it("ohne Zuordnung: ruhiger Hinweis mit Weg zu den Stammdaten", async () => {
    api.getDeviceTypeComparison.mockResolvedValue({ as_of: "2026-10-11", level: "types", running_count: 0, without_count: 0, items: [] });
    render(<DeviceTypeComparison organizationSlug="test-klinik" />);
    expect(await screen.findByText("Noch keine Verträge mit Geräteart")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Stammdaten → Gerätearten" })).toHaveAttribute("href", "/stammdaten/geraetearten");
  });
});
