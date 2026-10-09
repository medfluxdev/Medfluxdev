import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import NewContractPage from "@/app/contracts/new/page";
import { resetPermissionCache } from "@/lib/use-permissions";

const access = vi.hoisted(() => ({ getPermissionMatrix: vi.fn() }));
vi.mock("@/lib/domain-api/access", () => access);

const catalogs = vi.hoisted(() => ({
  listPartners: vi.fn(),
  createPartner: vi.fn(),
  findSimilarPartners: vi.fn(),
  listLookups: vi.fn(),
  listContractTypes: vi.fn(),
}));
vi.mock("@/lib/domain-api/catalogs", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/catalogs")>()),
  ...catalogs,
}));

vi.mock("@/lib/domain-api/organizations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/organizations")>()),
  getOrganizationStructure: vi.fn().mockResolvedValue({ hospitals: [], departments: [] }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/contracts/new",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const existing = { id: "p-1", short_name: "Siemens", name1: "Siemens AG", city: "Erlangen", is_active: true };
const created = { id: "p-2", short_name: "Medtec", name1: "Medtec GmbH", city: null, is_active: true };

beforeEach(() => {
  vi.clearAllMocks();
  resetPermissionCache();
  access.getPermissionMatrix.mockResolvedValue({
    role: "admin", roles: [], granted: [],
    permissions: [
      { key: "partner.edit", label: "", area: "", roles: ["admin", "contract_manager"] },
      { key: "catalog.admin", label: "", area: "", roles: ["admin"] },
    ],
  });
  catalogs.listPartners.mockResolvedValue({ total: 1, items: [existing] });
  catalogs.listContractTypes.mockResolvedValue({ contract_types: [], contract_categories: [] });
  catalogs.listLookups.mockResolvedValue({ field_keys: [], items: [] });
  catalogs.createPartner.mockResolvedValue({ ...created, similar: [] });
});

it("legt einen fehlenden Vertragspartner aus dem Vertragsformular an und wählt ihn aus", async () => {
  const user = userEvent.setup();
  render(<NewContractPage />);
  await user.click(await screen.findByRole("button", { name: "Neuer Partner" }));
  const drawer = await screen.findByRole("dialog", { name: "Vertragspartner anlegen" });
  await user.type(await within(drawer).findByLabelText("Kurzname *"), "Medtec");
  await user.type(within(drawer).getByLabelText("Name *"), "Medtec GmbH");

  catalogs.listPartners.mockResolvedValue({ total: 2, items: [existing, created] });
  await user.click(within(drawer).getByRole("button", { name: "Anlegen" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(catalogs.createPartner).toHaveBeenCalledWith("test-klinik", expect.objectContaining({ short_name: "Medtec", name1: "Medtec GmbH" }), false);
  await waitFor(() => expect(screen.getByLabelText("Vertragspartner")).toHaveValue("p-2"));
});
