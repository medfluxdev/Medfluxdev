import { render, screen, waitFor } from "@testing-library/react";
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
    expect(screen.getByRole("checkbox", { name: "Intensivmedizin" })).toBeChecked();

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
    await user.selectOptions(screen.getByLabelText("Kostenstelle"), "cc-icu");
    expect(department).toHaveValue("dept-icu");
  });
});

