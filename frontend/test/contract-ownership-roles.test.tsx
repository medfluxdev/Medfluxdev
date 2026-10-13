import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractOwnershipPanel from "@/components/contracts/detail/ContractOwnershipPanel";

const mocks = vi.hoisted(() => ({
  getOrganizationStructure: vi.fn(),
  listCostCenters: vi.fn(),
  listOwnershipAssignees: vi.fn(),
  getContractOwnership: vi.fn(),
  getContractDepartmentRoles: vi.fn(),
  updateContractOwnership: vi.fn(),
  updateContractDepartmentRoles: vi.fn(),
  listContractTypes: vi.fn(),
  getContractRegister: vi.fn(),
  updateContractRegister: vi.fn(),
  listDeviceTypes: vi.fn(),
  getContractDeviceTypes: vi.fn(),
  saveContractDeviceTypes: vi.fn(),
}));

vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({ role: "contract_manager", account: { is_developer: false } }),
}));
vi.mock("@/lib/domain-api/organizations", () => ({
  getOrganizationStructure: mocks.getOrganizationStructure,
  listCostCenters: mocks.listCostCenters,
}));
vi.mock("@/lib/domain-api/catalogs", () => ({ listContractTypes: mocks.listContractTypes }));
vi.mock("@/lib/domain-api/register", () => ({ getContractRegister: mocks.getContractRegister, updateContractRegister: mocks.updateContractRegister }));
vi.mock("@/lib/domain-api/deviceTypes", () => ({
  listDeviceTypes: mocks.listDeviceTypes,
  getContractDeviceTypes: mocks.getContractDeviceTypes,
  saveContractDeviceTypes: mocks.saveContractDeviceTypes,
}));
vi.mock("@/lib/domain-api/ownership", () => ({
  getContractOwnership: mocks.getContractOwnership,
  getContractDepartmentRoles: mocks.getContractDepartmentRoles,
  listOwnershipAssignees: mocks.listOwnershipAssignees,
  updateContractOwnership: mocks.updateContractOwnership,
  updateContractDepartmentRoles: mocks.updateContractDepartmentRoles,
}));

describe("Contract360 Organisationszuordnung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getOrganizationStructure.mockResolvedValue({
      hospitals: [{ id: "hospital-1", name: "Klinikum Heidelberg", code: "HD", is_active: true }],
      departments: [
        { id: "dept-root", hospital_id: "hospital-1", parent_id: null, name: "Medizintechnik", code: "MT", is_active: true },
        { id: "dept-rad", hospital_id: "hospital-1", parent_id: "dept-root", name: "Radiologie", code: "RAD", is_active: true },
        { id: "dept-icu", hospital_id: "hospital-1", parent_id: null, name: "Intensivmedizin", code: "ITS", is_active: true },
      ],
    });
    mocks.listCostCenters.mockResolvedValue({ items: [{ id: "cc-1", hospital_id: "hospital-1", department_id: "dept-rad", code: "4400", name: "Radiologie", is_active: true }] });
    mocks.listOwnershipAssignees.mockResolvedValue({ items: [] });
    mocks.getContractOwnership.mockResolvedValue({ contract_id: "contract-1", hospital_id: "hospital-1", department_ids: ["dept-rad", "dept-icu"], cost_center_id: null, responsible_account_id: null, scope_type: "department" });
    mocks.getContractDepartmentRoles.mockResolvedValue({ contract_id: "contract-1", responsible_department_id: "dept-rad", beneficiary_department_ids: ["dept-icu"], unclassified_department_ids: [] });
    mocks.updateContractOwnership.mockResolvedValue({ contract_id: "contract-1", hospital_id: "hospital-1", department_ids: ["dept-rad", "dept-icu"], cost_center_id: "cc-1", responsible_account_id: null, scope_type: "department" });
    mocks.updateContractDepartmentRoles.mockResolvedValue({});
    mocks.listContractTypes.mockResolvedValue({
      contract_types: [
        { id: "t-wartung", label: "Wartungsvertrag", is_active: true },
        { id: "t-miete", label: "Mietvertrag", is_active: true },
      ],
      contract_categories: [{ id: "cat-mt", label: "Medizintechnik", is_active: true, contract_type_ids: ["t-wartung"] }],
    });
    mocks.getContractRegister.mockResolvedValue({ fields: { contract_type_id: { value: "t-wartung" }, contract_category_id: { value: "cat-mt" } } });
    mocks.updateContractRegister.mockResolvedValue({});
    const deviceType = (id: string, label: string, area: string, area_label: string) => ({ id, code: id, label, area, area_label, department_id: null, department_name: null, keywords: null, description: null, is_active: true, sort_order: 0 });
    mocks.listDeviceTypes.mockResolvedValue({ items: [
      deviceType("dt-ct", "CT", "medizintechnik", "Medizintechnik"),
      deviceType("dt-mrt", "MRT", "medizintechnik", "Medizintechnik"),
      deviceType("dt-server", "Server", "it", "IT"),
      { ...deviceType("dt-monitor", "Patientenmonitoring", "sonstiges", "Sonstiges"), department_id: "dept-icu", department_name: "Intensivmedizin" },
    ] });
    mocks.getContractDeviceTypes.mockResolvedValue({ items: [{ device_type_id: "dt-ct", label: "CT", area: "medizintechnik", area_label: "Medizintechnik", quantity: 2, note: "Haus A" }], suggestions: [] });
    mocks.saveContractDeviceTypes.mockImplementation(async (_org: string, _id: string, items: { device_type_id: string }[]) => ({ items: items.map((item) => ({ ...item, label: item.device_type_id, area: "it", area_label: "IT" })), suggestions: [] }));
  });

  it("Gerätearten: passende der Abteilungen zuerst, hinzufügen und entfernen, Anzahl und Notiz bleiben", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    expect(await screen.findByRole("list", { name: "Gerätearten" })).toHaveTextContent("CT");
    const add = screen.getByLabelText("Geräteart hinzufügen");
    // Radiologie liegt unter Medizintechnik; Patientenmonitoring gehört der nutzenden Intensivmedizin.
    const matching = within(add).getByRole("group", { name: "Passend zu den Abteilungen" });
    expect(within(matching).getAllByRole("option").map((option) => option.textContent)).toEqual(["MRT", "Patientenmonitoring"]);
    expect(within(add).getByRole("group", { name: "IT" })).toHaveTextContent("Server");
    expect(within(add).queryByRole("option", { name: "CT" })).not.toBeInTheDocument();

    await user.selectOptions(add, "dt-server");
    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));
    await waitFor(() => expect(mocks.saveContractDeviceTypes).toHaveBeenCalledWith("klinik", "contract-1", [
      { device_type_id: "dt-ct", quantity: 2, note: "Haus A" },
      { device_type_id: "dt-server", quantity: null, note: null },
    ]));

    mocks.saveContractDeviceTypes.mockClear();
    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));
    await waitFor(() => expect(mocks.updateContractOwnership).toHaveBeenCalledTimes(2));
    expect(mocks.saveContractDeviceTypes).not.toHaveBeenCalled();
  });

  it("Gerätearten nicht ladbar: Feld fehlt, Zuordnung bleibt speicherbar", async () => {
    mocks.listDeviceTypes.mockRejectedValue(new Error("down"));
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await screen.findByLabelText("Vertragstyp");
    expect(screen.queryByLabelText("Geräteart hinzufügen")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zuordnung speichern" })).toBeEnabled();
  });

  it("Vertragstyp: zeigt den aktuellen Typ und speichert einen neuen (unpassende Kategorie wird geleert)", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    const type = await screen.findByLabelText("Vertragstyp");
    expect(type).toHaveValue("t-wartung");
    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));
    await waitFor(() => expect(mocks.updateContractOwnership).toHaveBeenCalled());
    expect(mocks.updateContractRegister).not.toHaveBeenCalled();

    await user.selectOptions(type, "t-miete");
    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));
    await waitFor(() => expect(mocks.updateContractRegister).toHaveBeenCalledWith("klinik", "contract-1", {
      changes: { contract_type_id: "t-miete", contract_category_id: null },
    }));
  });

  it("zeigt Verantwortlichen und nutzenden Bereich mit vollständigem Pfad und speichert beide Rollen", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);

    const responsible = await screen.findByLabelText("Verantwortliche Abteilung");
    expect(responsible).toHaveValue("dept-rad");
    expect(screen.getByRole("option", { name: "Medizintechnik › Radiologie" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Nutzende Abteilungen" })).toHaveTextContent("Intensivmedizin");

    await user.selectOptions(screen.getByLabelText("Kostenstelle"), "cc-1");
    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));

    await waitFor(() => expect(mocks.updateContractDepartmentRoles).toHaveBeenCalledWith("klinik", "contract-1", {
      responsible_department_id: "dept-rad",
      beneficiary_department_ids: ["dept-icu"],
    }));
    expect(mocks.updateContractOwnership).toHaveBeenCalledWith("klinik", "contract-1", expect.objectContaining({
      department_ids: ["dept-rad", "dept-icu"],
      cost_center_id: "cc-1",
    }));
    expect(screen.getByRole("status")).toHaveTextContent("Organisationszuordnung gespeichert.");
  });

  it("nutzende Abteilung entfernen: Auswahlfeld bietet sie wieder an und speichert ohne sie", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await user.click(await screen.findByRole("button", { name: "Intensivmedizin entfernen" }));
    expect(screen.queryByRole("list", { name: "Nutzende Abteilungen" })).not.toBeInTheDocument();
    expect(within(screen.getByLabelText("Nutzende Abteilung hinzufügen")).getByRole("option", { name: "Intensivmedizin" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));
    await waitFor(() => expect(mocks.updateContractDepartmentRoles).toHaveBeenCalledWith("klinik", "contract-1", {
      responsible_department_id: "dept-rad",
      beneficiary_department_ids: [],
    }));
  });

  it("ohne Benutzer: sagt es und verlinkt nicht auf eine leere Auswahl", async () => {
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    expect(await screen.findByText(/In dieser Organisation gibt es noch keine Benutzer/)).toBeInTheDocument();
    expect(screen.getByLabelText("Hauptverantwortlich")).toBeDisabled();
  });

  it("mehrere Verantwortliche: Haupt + weitere hinzufügen, entfernen, speichern; alle Benutzer wählbar", async () => {
    const user = userEvent.setup();
    mocks.listOwnershipAssignees.mockResolvedValue({ items: [
      { id: "u-1", display_name: "Maria Becker", email: "m@x", role: "contract_manager", hospital_id: null, department_id: null },
      { id: "u-2", display_name: "Jonas Kurz", email: "j@x", role: "viewer", hospital_id: "hospital-1", department_id: "dept-rad" },
      { id: "u-3", display_name: "Lea Wolf", email: "l@x", role: "viewer", hospital_id: "hospital-1", department_id: "dept-other" },
    ] });
    mocks.getContractOwnership.mockResolvedValue({ contract_id: "contract-1", hospital_id: "hospital-1", department_ids: ["dept-rad"], cost_center_id: null, responsible_account_id: "u-1", further_responsible_account_ids: ["u-2"], scope_type: "department" });
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    expect(await screen.findByLabelText("Hauptverantwortlich")).toHaveValue("u-1");
    expect(screen.getByRole("list", { name: "Weitere Verantwortliche" })).toHaveTextContent("Jonas Kurz");
    // Lea gehört zu einer anderen Abteilung – trotzdem wählbar (unter „Weitere Benutzer der Organisation“).
    const add = screen.getByLabelText("Weitere verantwortliche Person hinzufügen");
    await user.selectOptions(add, "u-3");
    expect(screen.getByRole("list", { name: "Weitere Verantwortliche" })).toHaveTextContent("Lea Wolf");
    await user.click(screen.getByRole("button", { name: "Jonas Kurz entfernen" }));
    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));
    await waitFor(() => expect(mocks.updateContractOwnership).toHaveBeenCalledWith("klinik", "contract-1", expect.objectContaining({
      responsible_account_id: "u-1", further_responsible_account_ids: ["u-3"],
    })));
  });

  it("Abteilung wählen füllt ihre Kostenstelle, Kostenstelle wählen füllt ihre Abteilung", async () => {
    const user = userEvent.setup();
    mocks.listCostCenters.mockResolvedValue({ items: [
      { id: "cc-rad", hospital_id: "hospital-1", department_id: "dept-rad", code: "4400", name: "Radiologie", is_active: true },
      { id: "cc-icu", hospital_id: "hospital-1", department_id: "dept-icu", code: "4500", name: "Intensiv", is_active: true },
    ] });
    mocks.getContractDepartmentRoles.mockResolvedValue({ contract_id: "contract-1", responsible_department_id: null, beneficiary_department_ids: [], unclassified_department_ids: [] });
    mocks.getContractOwnership.mockResolvedValue({ contract_id: "contract-1", hospital_id: "hospital-1", department_ids: [], cost_center_id: null, responsible_account_id: null, scope_type: "hospital" });
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    const department = await screen.findByLabelText("Verantwortliche Abteilung");
    await user.selectOptions(department, "dept-rad");
    expect(screen.getByLabelText("Kostenstelle")).toHaveValue("cc-rad");
    // Kostenstelle einer nutzenden Abteilung wählen: die verantwortliche Abteilung bleibt.
    await user.selectOptions(screen.getByLabelText("Nutzende Abteilung hinzufügen"), "dept-icu");
    const center = screen.getByLabelText("Kostenstelle");
    expect(within(center).getByRole("group", { name: "Verantwortliche Abteilung" })).toHaveTextContent("4400");
    expect(within(center).getByRole("group", { name: "Nutzende Abteilungen" })).toHaveTextContent("4500");
    await user.selectOptions(center, "cc-icu");
    expect(department).toHaveValue("dept-rad");
    expect(screen.getByRole("list", { name: "Nutzende Abteilungen" })).toHaveTextContent("Intensivmedizin");
    expect(center).toHaveValue("cc-icu");
  });

  it("ohne verantwortliche Abteilung: Kostenstelle wählen setzt ihre Abteilung", async () => {
    const user = userEvent.setup();
    mocks.listCostCenters.mockResolvedValue({ items: [{ id: "cc-icu", hospital_id: "hospital-1", department_id: "dept-icu", code: "4500", name: "Intensiv", is_active: true }] });
    mocks.getContractDepartmentRoles.mockResolvedValue({ contract_id: "contract-1", responsible_department_id: null, beneficiary_department_ids: [], unclassified_department_ids: [] });
    mocks.getContractOwnership.mockResolvedValue({ contract_id: "contract-1", hospital_id: "hospital-1", department_ids: [], cost_center_id: null, responsible_account_id: null, scope_type: "hospital" });
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await user.selectOptions(await screen.findByLabelText("Kostenstelle"), "cc-icu");
    expect(screen.getByLabelText("Verantwortliche Abteilung")).toHaveValue("dept-icu");
  });
});

