import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OrganizationStructureManager from "@/components/settings/OrganizationStructureManager";

const mocks = vi.hoisted(() => ({
  DEPARTMENT_UNIT_TYPE_LABELS: {
    klinik: "Klinik", abteilung: "Abteilung", bereich: "Bereich",
    einheit: "Einheit", station: "Station", funktionsbereich: "Funktionsbereich",
  },
  createDepartment: vi.fn(),
  createCostCenter: vi.fn(),
  createHospital: vi.fn(),
  getOrganizationStructure: vi.fn(),
  listCostCenters: vi.fn(),
  searchOrganizationStructure: vi.fn(),
  updateCostCenter: vi.fn(),
  updateDepartment: vi.fn(),
  updateHospital: vi.fn(),
}));

vi.mock("@/lib/domain-api/organizations", () => mocks);

const structure = {
  hospitals: [{ id: "hospital-1", name: "Krankenhaus Heidelberg", code: "HD", is_active: true }],
  departments: [
    { id: "radiology", hospital_id: "hospital-1", parent_id: null, name: "Radiologie", code: "RAD", unit_type: "abteilung", is_active: true },
    { id: "ct", hospital_id: "hospital-1", parent_id: "radiology", name: "CT", code: "CT", unit_type: null, is_active: true },
  ],
  unit_types: ["klinik", "abteilung", "bereich", "einheit", "station", "funktionsbereich"],
};
const centers = { items: [
  { id: "cc-1", hospital_id: "hospital-1", department_id: "ct", code: "471120", name: "CT", is_active: true },
] };

describe("Organisationsstruktur – WP1 (Einheitentyp, Kostenstellen, Suche)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getOrganizationStructure.mockResolvedValue(structure);
    mocks.listCostCenters.mockResolvedValue(centers);
    mocks.createDepartment.mockResolvedValue({});
    mocks.updateCostCenter.mockResolvedValue({});
    mocks.searchOrganizationStructure.mockResolvedValue({ query: "471120", items: [
      { kind: "cost_center", id: "cc-1", code: "471120", name: "CT", hospital_id: "hospital-1", hospital_name: "Krankenhaus Heidelberg",
        path: ["Radiologie", "CT"], path_label: "Radiologie › CT", unit_type: null, department_id: "ct", is_active: true },
    ] });
  });

  it("zeigt den Einheitentyp und sendet ihn beim Anlegen mit", async () => {
    const user = userEvent.setup();
    render(<OrganizationStructureManager organizationSlug="klinik-test" />);
    await waitFor(() => expect(screen.getAllByText(/Abteilung/).length).toBeGreaterThan(0));

    const form = screen.getByRole("heading", { name: "Einheit hinzufügen" }).closest("form")!;
    const fields = within(form);
    await user.type(fields.getByLabelText("Name"), "Herzkatheter");
    await user.type(fields.getByLabelText("Kürzel"), "HKL");
    await user.selectOptions(fields.getByLabelText("Einheitentyp (optional)"), "funktionsbereich");
    await user.click(fields.getByRole("button", { name: "Einheit anlegen" }));

    await waitFor(() => expect(mocks.createDepartment).toHaveBeenCalledTimes(1));
    expect(mocks.createDepartment.mock.calls[0][1]).toMatchObject({ name: "Herzkatheter", code: "HKL", unit_type: "funktionsbereich" });
  });

  it("deaktiviert eine Kostenstelle über den Chip", async () => {
    const user = userEvent.setup();
    render(<OrganizationStructureManager organizationSlug="klinik-test" />);
    const button = await screen.findByRole("button", { name: "Kostenstelle 471120 deaktivieren" });
    await user.click(button);
    await waitFor(() => expect(mocks.updateCostCenter).toHaveBeenCalledWith("klinik-test", "cc-1", { is_active: false }));
  });

  it("findet eine Kostenstelle per Nummer und zeigt Pfad und Krankenhaus", async () => {
    const user = userEvent.setup();
    render(<OrganizationStructureManager organizationSlug="klinik-test" />);
    await screen.findAllByText("Krankenhaus Heidelberg");
    await user.type(screen.getByLabelText("Einheit oder Kostenstelle suchen"), "471120");

    await waitFor(() => expect(mocks.searchOrganizationStructure).toHaveBeenCalled());
    expect(mocks.searchOrganizationStructure.mock.calls[0][1]).toBe("471120");
    const results = await screen.findByRole("list", { name: "Suchergebnisse" });
    const hit = within(results).getByText("471120 – CT");
    const item = hit.closest("li")!;
    expect(within(item).getByText("Radiologie › CT")).toBeInTheDocument();
    expect(within(item).getByText("Kostenstelle")).toBeInTheDocument();
    expect(within(item).getByText("Krankenhaus Heidelberg", { selector: "small" })).toBeInTheDocument();
  });
});
