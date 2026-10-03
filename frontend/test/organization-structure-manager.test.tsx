import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OrganizationStructureManager from "@/components/settings/OrganizationStructureManager";

const mocks = vi.hoisted(() => ({
  DEPARTMENT_UNIT_TYPE_LABELS: {
    klinik: "Klinik", abteilung: "Abteilung", bereich: "Bereich",
    einheit: "Einheit", station: "Station", funktionsbereich: "Funktionsbereich",
  },
  searchOrganizationStructure: vi.fn(),
  updateCostCenter: vi.fn(),
  createDepartment: vi.fn(),
  createCostCenter: vi.fn(),
  createHospital: vi.fn(),
  getOrganizationStructure: vi.fn(),
  listCostCenters: vi.fn(),
  updateDepartment: vi.fn(),
  updateHospital: vi.fn(),
}));

vi.mock("@/lib/domain-api/organizations", () => mocks);

const structure = {
  hospitals: [{ id: "hospital-1", name: "Krankenhaus Heidelberg", code: "HD", is_active: true }],
  departments: [
    { id: "radiology", hospital_id: "hospital-1", parent_id: null, name: "Radiologie", code: "RAD", is_active: true },
    { id: "ct", hospital_id: "hospital-1", parent_id: "radiology", name: "CT", code: "CT", is_active: true },
  ],
};

describe("Organisationsstrukturverwaltung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getOrganizationStructure.mockResolvedValue(structure);
    mocks.listCostCenters.mockResolvedValue({ items: [] });
    mocks.createDepartment.mockResolvedValue({});
    mocks.updateDepartment.mockResolvedValue({});
  });

  it("zeigt die Hierarchie und vollständige Pfade in der Einheitenauswahl", async () => {
    render(<OrganizationStructureManager organizationSlug="klinik-test" />);

    await waitFor(() => expect(screen.getAllByText("Radiologie › CT").length).toBeGreaterThan(0));
    const form = screen.getByRole("heading", { name: "Einheit hinzufügen" }).closest("form");
    expect(form).not.toBeNull();
    expect(within(form!).getByRole("option", { name: "Radiologie › CT" })).toBeInTheDocument();
  });

  it("legt eine Untereinheit mit der gewählten Elterneinheit an", async () => {
    const user = userEvent.setup();
    render(<OrganizationStructureManager organizationSlug="klinik-test" />);

    const addChildButtons = await screen.findAllByRole("button", { name: "Untereinheit hinzufügen" });
    await user.click(addChildButtons[0]);

    const form = screen.getByRole("heading", { name: "Einheit hinzufügen" }).closest("form");
    expect(form).not.toBeNull();
    const fields = within(form!);
    await user.type(fields.getByLabelText("Name"), "Röntgen");
    await user.type(fields.getByLabelText("Kürzel"), "ROE");
    await act(async () => {
      await user.click(fields.getByRole("button", { name: "Einheit anlegen" }));
      await new Promise((resolve) => window.setTimeout(resolve, 0));
    });

    await waitFor(() => expect(mocks.createDepartment).toHaveBeenCalledWith("klinik-test", {
      hospital_id: "hospital-1",
      parent_id: "radiology",
      name: "Röntgen",
      code: "ROE",
    }));
    expect(await screen.findByRole("status")).toHaveTextContent("Einheit wurde in der Organisationsstruktur angelegt.");
    await waitFor(() => expect(mocks.getOrganizationStructure).toHaveBeenCalledTimes(2));
  });
});
