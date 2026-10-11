import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { parseImportCsv } from "@/components/master-data/CsvImport";
import { costCenterDefinition, departmentDefinition } from "@/components/master-data/definitions/organization";
import { partnerDefinition } from "@/components/master-data/definitions/partners";
import EntityManager from "@/components/master-data/EntityManager";
import MasterDataHub from "@/components/master-data/MasterDataHub";
import MasterDataSectionView from "@/components/master-data/MasterDataSectionView";
import OrganizationTree from "@/components/master-data/OrganizationTree";
import { ApiError } from "@/lib/api";
import type { PartnerDto } from "@/lib/domain-api/catalogs";
import { masterDataSection } from "@/lib/master-data";
import { resetPermissionCache } from "@/lib/use-permissions";

const ALL = ["admin", "contract_manager", "reviewer", "viewer"];
const EDITORS = ["admin", "contract_manager"];
const ADMIN = ["admin"];

const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("@/components/auth/AuthProvider", () => ({
  AuthProvider: ({ children }: { children: unknown }) => children,
  useAuth: () => ({
    account: { id: "u-1", is_developer: false, memberships: [] },
    organizationSlug: "test-klinik",
    role: auth.role,
    previewOf: null,
    loading: false,
  }),
}));

const access = vi.hoisted(() => ({ getPermissionMatrix: vi.fn() }));
vi.mock("@/lib/domain-api/access", () => access);

const catalogs = vi.hoisted(() => ({
  listPartners: vi.fn(),
  createPartner: vi.fn(),
  updatePartner: vi.fn(),
  findSimilarPartners: vi.fn(),
  listPartnerDuplicates: vi.fn(),
  listLookups: vi.fn(),
  listContractTypes: vi.fn(),
  loadDefaultCatalogs: vi.fn(),
}));
vi.mock("@/lib/domain-api/catalogs", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/catalogs")>()),
  ...catalogs,
}));

const organizations = vi.hoisted(() => ({
  getOrganizationStructure: vi.fn(),
  listCostCenters: vi.fn(),
  createDepartment: vi.fn(),
  updateDepartment: vi.fn(),
  updateCostCenter: vi.fn(),
  searchOrganizationStructure: vi.fn(),
}));
vi.mock("@/lib/domain-api/organizations", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/organizations")>()),
  ...organizations,
}));

const masterData = vi.hoisted(() => ({
  getMasterDataUsage: vi.fn(),
  getMasterDataSummary: vi.fn(),
  importMasterData: vi.fn(),
  mergePartners: vi.fn(),
}));
vi.mock("@/lib/domain-api/masterData", () => masterData);

const history = vi.hoisted(() => ({ listHistory: vi.fn() }));
vi.mock("@/lib/domain-api/history", () => history);

vi.mock("next/navigation", () => ({
  usePathname: () => "/stammdaten/vertragspartner",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

function matrix(role: string) {
  return {
    role,
    roles: [],
    granted: [],
    permissions: [
      { key: "partner.edit", label: "", area: "", roles: EDITORS },
      { key: "catalog.admin", label: "", area: "", roles: ADMIN },
      { key: "organization.admin", label: "", area: "", roles: ADMIN },
      { key: "audit.view", label: "", area: "", roles: EDITORS },
      { key: "export", label: "", area: "", roles: EDITORS },
      { key: "contract.read", label: "", area: "", roles: ALL },
    ],
  };
}

function partner(overrides: Partial<PartnerDto>): PartnerDto {
  return {
    id: "p-1", short_name: "Siemens", name1: "Siemens Healthineers GmbH", name2: null, street: null, postal_code: "91052", city: "Erlangen",
    country: null, po_box: null, po_box_postal_code: null, phone: null, fax: null, email: "service@example.test", website: null, vat_id: null,
    industry_code: null, partner_type: null, note: null, is_active: true, display_name: "Siemens Healthineers GmbH", updated_at: null, contract_count: 2,
    ...overrides,
  };
}

const PARTNERS = [
  partner({}),
  partner({ id: "p-2", short_name: "Philips", name1: "Philips GmbH", display_name: "Philips GmbH", city: "Hamburg", contract_count: 0 }),
  partner({ id: "p-3", short_name: "Altlieferant", name1: "Alt GmbH", display_name: "Alt GmbH", city: "Kiel", is_active: false, contract_count: 0 }),
];

const STRUCTURE = {
  hospitals: [{ id: "h-1", name: "Klinikum Nord", code: "KN", address: null, is_active: true }],
  departments: [
    { id: "d-1", hospital_id: "h-1", parent_id: null, name: "Kardiologie", code: "KAR", unit_type: "klinik" as const, is_active: true },
    { id: "d-2", hospital_id: "h-1", parent_id: "d-1", name: "Station 3", code: "ST3", unit_type: "station" as const, is_active: true },
  ],
};
const CENTERS = [{ id: "c-1", hospital_id: "h-1", department_id: "d-1", code: "471200", name: "Kardiologie", is_active: true }];

beforeEach(() => {
  vi.clearAllMocks();
  auth.role = "admin";
  resetPermissionCache();
  window.history.replaceState(null, "", "/stammdaten/vertragspartner");
  access.getPermissionMatrix.mockResolvedValue(matrix("admin"));
  catalogs.listPartners.mockResolvedValue({ total: PARTNERS.length, items: PARTNERS });
  catalogs.listLookups.mockResolvedValue({ field_keys: [], items: [{ id: "l-1", field_key: "industry", code: "medtech", label: "Medizintechnik", description: null, is_active: true, sort_order: 0 }] });
  catalogs.listPartnerDuplicates.mockResolvedValue({ groups: [] });
  catalogs.updatePartner.mockResolvedValue(PARTNERS[0]);
  masterData.getMasterDataUsage.mockResolvedValue({ kind: "partner", counts: { "p-1": 2 }, tracked_lookup_fields: null });
  organizations.getOrganizationStructure.mockResolvedValue(STRUCTURE);
  organizations.listCostCenters.mockResolvedValue({ items: CENTERS });
  history.listHistory.mockResolvedValue({ total: 1, items: [{ id: "a", kind: "activity", category: "organisation", at: "2026-10-05T09:00:00Z", actor: "Test Admin", event: "partner.updated", label: "Vertragspartner geändert", details: {} }], actors: [], categories: [] });
});

function renderPartners() {
  return render(<EntityManager definition={partnerDefinition} section={masterDataSection("vertragspartner")!} organizationSlug="test-klinik" />);
}

describe("Stammdaten-Liste", () => {
  it("zeigt aktive Einträge mit Verwendung, sucht und blendet Deaktivierte ein", async () => {
    const user = userEvent.setup();
    const { container } = renderPartners();
    const table = await screen.findByRole("table", { name: "Vertragspartner" });
    expect(within(table).getByRole("rowheader", { name: "Siemens" })).toBeInTheDocument();
    expect(within(table).queryByText("Altlieferant")).not.toBeInTheDocument();
    expect(await within(table).findByRole("link", { name: "2 Verträge mit Siemens anzeigen" })).toHaveAttribute("href", expect.stringContaining("/register?filter="));
    expect(await axe(container)).toHaveNoViolations();

    await user.type(screen.getByRole("searchbox", { name: "Vertragspartner durchsuchen" }), "hamburg");
    expect(within(table).queryByText("Siemens")).not.toBeInTheDocument();
    expect(within(table).getByText("Philips")).toBeInTheDocument();
    expect(window.location.search).toContain("q=hamburg");

    await user.clear(screen.getByRole("searchbox", { name: "Vertragspartner durchsuchen" }));
    await user.click(screen.getByRole("checkbox", { name: /Deaktivierte anzeigen \(1\)/ }));
    expect(within(table).getByText("Altlieferant")).toBeInTheDocument();
  });

  it("bearbeitet in der Seitenleiste, speichert mit Strg+S und zeigt den Verlauf", async () => {
    const user = userEvent.setup();
    renderPartners();
    await user.click(await screen.findByRole("button", { name: "Siemens bearbeiten" }));
    const drawer = screen.getByRole("dialog", { name: "Siemens" });
    expect(within(drawer).getByText("In 2 Verträgen verwendet.")).toBeInTheDocument();
    expect(within(drawer).getByRole("button", { name: "Speichern" })).toBeDisabled();

    const city = within(drawer).getByLabelText("Ort");
    await user.clear(city);
    await user.type(city, "Forchheim");
    await user.keyboard("{Control>}s{/Control}");
    await waitFor(() => expect(catalogs.updatePartner).toHaveBeenCalledWith("test-klinik", "p-1", expect.objectContaining({ city: "Forchheim", short_name: "Siemens" })));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Siemens bearbeiten" }));
    await user.click(screen.getByText("Änderungsverlauf"));
    expect(await screen.findByText("Vertragspartner geändert")).toBeInTheDocument();
    expect(history.listHistory).toHaveBeenCalledWith("test-klinik", { object_type: "contract_partner", object_id: "p-1" }, { limit: 50, offset: 0 });
  });

  it("fragt vor dem Verwerfen ungespeicherter Änderungen nach", async () => {
    const user = userEvent.setup();
    renderPartners();
    await user.click(await screen.findByRole("button", { name: "Philips bearbeiten" }));
    await user.type(screen.getByLabelText("Ort"), "-Nord");
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(screen.getByText("Ungespeicherte Änderungen verwerfen?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Verwerfen" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("warnt bei ähnlichen Partnern und legt erst nach Bestätigung an", async () => {
    const user = userEvent.setup();
    catalogs.createPartner
      .mockRejectedValueOnce(new ApiError("Möglicherweise existiert dieser Vertragspartner bereits.", { status: 409 }))
      .mockResolvedValueOnce({ ...partner({ id: "p-9", short_name: "Siemens AG" }), similar: [] });
    catalogs.findSimilarPartners.mockResolvedValue({ items: [PARTNERS[0]] });
    renderPartners();
    await user.click(await screen.findByRole("button", { name: "Vertragspartner anlegen" }));
    const drawer = screen.getByRole("dialog", { name: "Vertragspartner anlegen" });
    await user.click(within(drawer).getByRole("button", { name: "Anlegen" }));
    expect(within(drawer).getByText("Kurzname ist erforderlich.")).toBeInTheDocument();
    expect(catalogs.createPartner).not.toHaveBeenCalled();

    await user.type(within(drawer).getByLabelText("Kurzname *"), "Siemens AG");
    await user.type(within(drawer).getByLabelText("Name *"), "Siemens AG");
    await user.click(within(drawer).getByRole("button", { name: "Anlegen" }));
    expect(await within(drawer).findByText(/Ähnliche Einträge gibt es bereits: Siemens \(Erlangen\)/)).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "Trotzdem anlegen" }));
    await waitFor(() => expect(catalogs.createPartner).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({ short_name: "Siemens AG" }), true));
  });

  it("bestätigt das Deaktivieren, wenn der Eintrag in Verträgen verwendet wird", async () => {
    const user = userEvent.setup();
    renderPartners();
    await user.click(await screen.findByRole("button", { name: "Siemens bearbeiten" }));
    await user.click(screen.getByRole("button", { name: "Deaktivieren" }));
    expect(screen.getByText(/Wird in 2 Verträgen verwendet/)).toBeInTheDocument();
    expect(catalogs.updatePartner).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Trotzdem deaktivieren" }));
    await waitFor(() => expect(catalogs.updatePartner).toHaveBeenCalledWith("test-klinik", "p-1", { is_active: false }));
  });

  it("zeigt Lesern alles, aber ohne Ändern, Import und Export", async () => {
    auth.role = "viewer";
    access.getPermissionMatrix.mockResolvedValue(matrix("viewer"));
    const { container } = renderPartners();
    expect(await screen.findByText(/Ändern dürfen: Vertragsmanagement und Administration/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Siemens ansehen" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Vertragspartner anlegen" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Importieren" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Exportieren" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Siemens ansehen" }));
    expect(screen.getByLabelText("Kurzname *")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Speichern" })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("zeigt aktive Filter als Chips und setzt sie einzeln oder gemeinsam zurück", async () => {
    const user = userEvent.setup();
    renderPartners();
    await screen.findByRole("table", { name: "Vertragspartner" });
    await user.type(screen.getByRole("searchbox", { name: "Vertragspartner durchsuchen" }), "siemens");
    await user.click(screen.getByRole("checkbox", { name: /Deaktivierte anzeigen/ }));
    const chips = screen.getByRole("list", { name: "Aktive Filter" });
    expect(within(chips).getByText("Suche: „siemens“")).toBeInTheDocument();
    expect(within(chips).getByText("Mit deaktivierten")).toBeInTheDocument();
    await user.click(within(chips).getByRole("button", { name: "Filter entfernen: Suche: „siemens“" }));
    expect(screen.getByRole("searchbox", { name: "Vertragspartner durchsuchen" })).toHaveValue("");
    await user.click(screen.getByRole("checkbox", { name: /Deaktivierte anzeigen/ }));
    await user.type(screen.getByRole("searchbox", { name: "Vertragspartner durchsuchen" }), "x");
    await user.click(screen.getByRole("checkbox", { name: /Deaktivierte anzeigen/ }));
    await user.click(within(screen.getByRole("list", { name: "Aktive Filter" })).getByRole("button", { name: "Alle zurücksetzen" }));
    expect(screen.queryByRole("list", { name: "Aktive Filter" })).not.toBeInTheDocument();
  });

  it("öffnet einen Eintrag über den Link ?id=", async () => {
    window.history.replaceState(null, "", "/stammdaten/vertragspartner?id=p-2");
    renderPartners();
    expect(await screen.findByRole("dialog", { name: "Philips" })).toBeInTheDocument();
  });
});

describe("Dubletten zusammenführen", () => {
  it("behält den gewählten Partner und führt nach Bestätigung zusammen", async () => {
    const user = userEvent.setup();
    catalogs.listPartnerDuplicates.mockResolvedValue({ groups: [[PARTNERS[0], partner({ id: "p-4", short_name: "Siemens HC", display_name: "Siemens Healthineers AG", contract_count: 1 })]] });
    catalogs.listPartners.mockResolvedValue({ total: 4, items: [...PARTNERS, partner({ id: "p-4", short_name: "Siemens HC", display_name: "Siemens Healthineers AG", contract_count: 1 })] });
    masterData.mergePartners.mockResolvedValue({ ...PARTNERS[0], merged: [] });
    render(<MasterDataSectionView slug="vertragspartner" />);
    expect(await screen.findByText(/1 mögliche Dublette/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "„Siemens“ behalten und zusammenführen" }));
    expect(screen.getByText(/1 Vertrag werden „Siemens“ zugeordnet/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Zusammenführen" }));
    await waitFor(() => expect(masterData.mergePartners).toHaveBeenCalledWith("test-klinik", "p-1", ["p-4"]));
  });
});

describe("Organisation", () => {
  it("legt eine Untereinheit aus der Strukturansicht mit Elterneinheit und Typ an", async () => {
    const user = userEvent.setup();
    masterData.getMasterDataUsage.mockResolvedValue({ kind: "department", counts: {}, tracked_lookup_fields: null });
    organizations.createDepartment.mockResolvedValue({ id: "d-9", hospital_id: "h-1", name: "Herzkatheterlabor", code: "HKL" });
    const { container } = render(<EntityManager
      definition={departmentDefinition}
      section={masterDataSection("abteilungen")!}
      organizationSlug="test-klinik"
      alternateView={{ label: "Struktur", render: (rows, context, api) => <OrganizationTree rows={rows} context={context} api={api} /> }}
    />);
    const table = await screen.findByRole("table", { name: "Abteilungen" });
    expect(within(table).getByText("Kardiologie › Station 3")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Struktur" }));
    expect(screen.getByRole("region", { name: "Klinikum Nord" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Untereinheit unter Kardiologie anlegen" }));
    const drawer = screen.getByRole("dialog", { name: "Abteilung anlegen" });
    expect(within(drawer).getByLabelText("Übergeordnete Einheit")).toHaveValue("d-1");
    await user.type(within(drawer).getByLabelText("Name *"), "Herzkatheterlabor");
    await user.type(within(drawer).getByLabelText("Kürzel *"), "HKL");
    await user.selectOptions(within(drawer).getByLabelText("Einheitentyp"), "funktionsbereich");
    await user.click(within(drawer).getByRole("button", { name: "Anlegen" }));
    await waitFor(() => expect(organizations.createDepartment).toHaveBeenCalledWith("test-klinik", {
      hospital_id: "h-1", parent_id: "d-1", name: "Herzkatheterlabor", code: "HKL", unit_type: "funktionsbereich", cost_center_code: null,
    }));
  });

  it("deaktiviert eine unbenutzte Kostenstelle ohne Rückfrage", async () => {
    const user = userEvent.setup();
    masterData.getMasterDataUsage.mockResolvedValue({ kind: "cost_center", counts: {}, tracked_lookup_fields: null });
    organizations.updateCostCenter.mockResolvedValue(CENTERS[0]);
    render(<EntityManager definition={costCenterDefinition} section={masterDataSection("kostenstellen")!} organizationSlug="test-klinik" />);
    await user.click(await screen.findByRole("button", { name: "471200 – Kardiologie bearbeiten" }));
    expect(screen.getByText("In keinem Vertrag verwendet.")).toBeInTheDocument();
    expect(screen.getByLabelText("Krankenhaus *")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Deaktivieren" }));
    await waitFor(() => expect(organizations.updateCostCenter).toHaveBeenCalledWith("test-klinik", "c-1", { is_active: false }));
  });
});

describe("CSV-Import", () => {
  const columns = partnerDefinition.importColumns!;

  it("erkennt Spalten über Bezeichnung und Aliasse und meldet fehlende Pflichtspalten", () => {
    const parsed = parseImportCsv("﻿Kurzbezeichnung;Firma;Stadt\r\nMEDTEC;\"Medtec; GmbH\";Berlin\r\n", columns);
    expect(parsed.error).toBeNull();
    expect(parsed.rows).toEqual([expect.objectContaining({ short_name: "MEDTEC", name1: "Medtec; GmbH", city: "Berlin", phone: null })]);
    expect(parseImportCsv("Name;Ort\r\nA;B\r\n", columns).error).toBe("Spalte fehlt: Kurzname.");
    expect(parseImportCsv("Kurzname\r\n", columns).error).toMatch(/mindestens eine Zeile/);
  });

  it("prüft zuerst, zeigt Fehler je Zeile und legt erst danach an", async () => {
    const user = userEvent.setup();
    masterData.importMasterData
      .mockResolvedValueOnce({ valid: false, created: 0, errors: [], rows: [{ line: 1, label: "Siemens", errors: ["Diesen Kurznamen gibt es bereits."], warnings: [] }] })
      .mockResolvedValueOnce({ valid: true, created: 0, errors: [], rows: [{ line: 1, label: "Drägerwerk", errors: [], warnings: ["Ähnlich zu: Dräger"] }] })
      .mockResolvedValueOnce({ valid: true, created: 1, errors: [], rows: [] });
    renderPartners();
    await user.click(await screen.findByRole("button", { name: "Importieren" }));
    const drawer = screen.getByRole("dialog", { name: "Vertragspartner importieren" });

    await user.upload(within(drawer).getByLabelText("Liste auswählen"), new File(["Kurzname;Name\r\nSiemens;Siemens AG\r\n"], "partner.csv", { type: "text/csv" }));
    expect(await within(drawer).findByText("1 Zeilen in der Liste")).toBeInTheDocument();
    expect(within(drawer).getByRole("button", { name: "1 Vertragspartner anlegen" })).toBeDisabled();
    await user.click(within(drawer).getByRole("button", { name: "Liste prüfen" }));
    expect(await within(drawer).findByText("Diesen Kurznamen gibt es bereits.")).toBeInTheDocument();

    await user.upload(within(drawer).getByLabelText("Liste auswählen"), new File(["Kurzname;Name\r\nDrägerwerk;Drägerwerk AG\r\n"], "partner.csv", { type: "text/csv" }));
    await user.click(await within(drawer).findByRole("button", { name: "Liste prüfen" }));
    expect(await within(drawer).findByText("Ähnlich zu: Dräger")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "1 Vertragspartner anlegen" }));
    expect(await within(drawer).findByText("1 Vertragspartner angelegt.")).toBeInTheDocument();
    expect(masterData.importMasterData).toHaveBeenLastCalledWith("test-klinik", "partner", [expect.objectContaining({ short_name: "Drägerwerk", name1: "Drägerwerk AG" })], false, undefined);
  });
});

describe("Stammdaten-Übersicht", () => {
  it("zeigt Bestand je Datenart, Hinweise und sucht über alle Stammdaten", async () => {
    const user = userEvent.setup();
    const count = { total: 3, active: 3, inactive: 0, last_change: null };
    masterData.getMasterDataSummary.mockResolvedValue({
      kinds: { partner: { ...count, inactive: 1, last_change: "2026-10-05T08:00:00Z" }, hospital: count, department: count, cost_center: count, contract_type: count, contract_category: count, lookup: count, rule: count },
      lookup_lists: [{ field_key: "storage_location", active: 4, inactive: 0 }],
      hints: { partner_duplicate_groups: 2, partners_without_contracts: 1 },
    });
    catalogs.listContractTypes.mockResolvedValue({ contract_types: [{ id: "t-1", code: "wartung", label: "Wartungsvertrag", description: null, is_confidential: false, is_active: true, sort_order: 0, retention_years: null }], contract_categories: [] });
    catalogs.listLookups.mockResolvedValue({ field_keys: [], items: [] });
    organizations.searchOrganizationStructure.mockResolvedValue({ query: "war", items: [] });
    const { container } = render(<MasterDataHub organizationSlug="test-klinik" />);

    expect(await screen.findByText("2 mögliche Dubletten bei den Vertragspartnern.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Vertragspartner öffnen/ })).toHaveAttribute("href", "/stammdaten/vertragspartner");
    expect(screen.getByText(/1 deaktiviert · geändert 05\.10\.2026 · 1 ohne Vertrag/)).toBeInTheDocument();
    expect(screen.getByText("4 Einträge")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Fehlende Standardeinträge ergänzen" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.type(screen.getByRole("searchbox", { name: "Suchbegriff" }), "wart");
    const hits = await screen.findByRole("list", { name: "Suchergebnisse" });
    expect(within(hits).getByRole("link", { name: "Wartungsvertrag" })).toHaveAttribute("href", "/stammdaten/vertragstypen?id=t-1");
  });
});
