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
}));

vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({ role: "contract_manager", account: { is_developer: false } }),
}));
vi.mock("@/lib/domain-api/organizations", () => ({
  getOrganizationStructure: mocks.getOrganizationStructure,
  listCostCenters: mocks.listCostCenters,
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
});
