import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
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
  toast: vi.fn(),
  searchParams: new URLSearchParams(),
  role: "contract_manager",
}));

vi.mock("next/navigation", () => ({ useSearchParams: () => mocks.searchParams }));
vi.mock("@/components/ui/Toast", () => ({ useToast: () => mocks.toast }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({ role: mocks.role, account: { is_developer: false } }),
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
    mocks.searchParams = new URLSearchParams();
    mocks.role = "contract_manager";
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

  async function openEdit(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole("button", { name: "Organisationszuordnung bearbeiten" }));
  }

  async function pick(user: ReturnType<typeof userEvent.setup>, trigger: string, option: string) {
    await user.click(screen.getByRole("button", { name: trigger }));
    await user.click(within(screen.getByRole("group", { name: trigger })).getByRole("button", { name: option }));
  }

  it("Ansicht: Werte in vier Gruppen, Fehlendes als Signal, kein Speichern-Knopf; ohne Verstöße (axe)", async () => {
    const { container } = render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    expect(await screen.findByRole("button", { name: "Organisationszuordnung bearbeiten" })).toBeInTheDocument();
    for (const name of ["Vertrag", "Krankenhaus & Abteilungen", "Kostenstelle & Geräte", "Verantwortliche Personen"]) {
      expect(screen.getByRole("heading", { level: 3, name })).toBeInTheDocument();
    }
    expect(screen.getByText("Wartungsvertrag")).toBeInTheDocument();
    expect(screen.getByText("Klinikum Heidelberg")).toBeInTheDocument();
    expect(screen.getByText("Medizintechnik › Radiologie")).toBeInTheDocument();
    expect(screen.getByText("CT (2)")).toBeInTheDocument();
    // Ohne Kostenstelle und ohne Hauptverantwortliche: Signal statt leerem Feld.
    expect(screen.getAllByText("Nicht festgelegt")).toHaveLength(2);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Zuordnung speichern" })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Ansicht: Kennfarben-Chips je Art, Person mit Initiale, Pflichtangaben fehlen als Signal, das Bearbeiten öffnet", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    expect((await screen.findByText("Wartungsvertrag")).closest(".tag-chip")).toHaveClass("tag-chip--type");
    expect(screen.getByText("Medizintechnik › Radiologie").closest(".tag-chip")).toHaveClass("tag-chip--department");
    expect(screen.getByText("Intensivmedizin").closest(".tag-chip")).toHaveClass("tag-chip--department");
    expect(screen.getByText("verantwortlich")).toBeInTheDocument();
    expect(screen.getByText("nutzend")).toBeInTheDocument();
    expect(screen.getByText("CT (2)").closest(".tag-chip")).toHaveClass("tag-chip--device");
    // Kostenstelle und Hauptverantwortlich fehlen: kein Grün, sondern Signal mit Liste im Titel.
    expect(screen.queryByText(/Pflichtangaben/)).not.toBeInTheDocument();
    const missing = screen.getByRole("button", { name: "2 Angaben fehlen" });
    expect(missing).toHaveAttribute("title", "Es fehlen: Kostenstelle, Hauptverantwortlich");
    await user.click(missing);
    expect(screen.getByLabelText("Vertragstyp")).toBeInTheDocument();
  });

  it("Ansicht: alle Pflichtangaben gepflegt → grüne Plakette „5 von 5“, Kostenstelle mit Nummer, Person mit Initiale", async () => {
    mocks.getContractOwnership.mockResolvedValue({ contract_id: "contract-1", hospital_id: "hospital-1", department_ids: ["dept-rad", "dept-icu"], cost_center_id: "cc-1", responsible_account_id: "u-1", further_responsible_account_ids: [], scope_type: "department" });
    mocks.listOwnershipAssignees.mockResolvedValue({ items: [{ id: "u-1", display_name: "Dana Weber", role: "contract_manager", hospital_id: null, department_id: null }] });
    const { container } = render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    expect(await screen.findByText("5 von 5 Pflichtangaben")).toBeInTheDocument();
    expect(screen.queryByText(/Angaben? fehl/)).not.toBeInTheDocument();
    const center = screen.getByText("4400").closest(".tag-chip");
    expect(center).toHaveClass("tag-chip--cost");
    expect(center).toHaveTextContent("Radiologie");
    const person = screen.getByText("Dana Weber");
    expect(person.closest(".tag-person")?.querySelector(".tag-avatar")).toHaveTextContent("D");
    expect(person.closest(".tag-person")?.querySelector(".tag-avatar")).toHaveAttribute("aria-hidden", "true");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Ansicht: „+ Person hinzufügen“ statt nur „Keine“ öffnet Bearbeiten mit Fokus auf der Auswahl", async () => {
    const user = userEvent.setup();
    mocks.listOwnershipAssignees.mockResolvedValue({ items: [{ id: "u-1", display_name: "Dana Weber", role: "contract_manager", hospital_id: null, department_id: null }] });
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await user.click(await screen.findByRole("button", { name: "Person hinzufügen" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Weitere verantwortliche Person hinzufügen" })).toHaveFocus());
    // Nutzende Abteilungen sind gepflegt: dort kein Hinzufügen-Knopf in der Ansicht.
    expect(screen.queryByRole("button", { name: "Abteilung hinzufügen" })).not.toBeInTheDocument();
  });

  it("Viele Abteilungen: Suchfeld filtert die verantwortliche Abteilung, die gewählte bleibt", async () => {
    const user = userEvent.setup();
    const extra = ["Kardiologie", "Endoskopie", "Haustechnik", "Röntgen", "Labor", "Apotheke"].map((name, index) => ({ id: `dept-x${index}`, hospital_id: "hospital-1", parent_id: null, name, code: `X${index}`, is_active: true }));
    const structure = await mocks.getOrganizationStructure.getMockImplementation()?.();
    mocks.getOrganizationStructure.mockResolvedValue({ ...structure, departments: [...structure.departments, ...extra] });
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    const select = screen.getByLabelText("Verantwortliche Abteilung");
    await user.type(screen.getByRole("searchbox", { name: "Abteilungen durchsuchen" }), "kard");
    const options = within(select).getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["Bitte auswählen", "Medizintechnik › Radiologie", "Kardiologie"]);
    await user.clear(screen.getByRole("searchbox", { name: "Abteilungen durchsuchen" }));
    await user.type(screen.getByRole("searchbox", { name: "Abteilungen durchsuchen" }), "xyz");
    expect(screen.getByText("Keine Abteilung passt zu „xyz“.")).toBeInTheDocument();
  });

  it("Ohne Bearbeitungsrecht: kein Kasten und keine Hinzufügen-Knöpfe", async () => {
    mocks.role = "viewer";
    const { container } = render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(screen.queryByRole("button", { name: /hinzufügen/ })).not.toBeInTheDocument();
  });

  it("Bearbeiten: Speicherleiste erst nach einer Änderung; Abbrechen stellt die gespeicherten Werte wieder her", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    expect(screen.queryByRole("region", { name: "Änderungen speichern" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abbrechen" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.selectOptions(screen.getByLabelText("Vertragstyp"), "t-miete");
    const bar = screen.getByRole("region", { name: "Änderungen speichern" });
    expect(bar).toHaveTextContent("Ungespeicherte Änderungen");
    expect(screen.getAllByRole("button", { name: "Abbrechen" })).toHaveLength(1);
    // Zurück auf den gespeicherten Wert: keine Änderung mehr.
    await user.selectOptions(screen.getByLabelText("Vertragstyp"), "t-wartung");
    expect(screen.queryByRole("region", { name: "Änderungen speichern" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Vertragstyp"), "t-miete");
    await user.click(within(screen.getByRole("region", { name: "Änderungen speichern" })).getByRole("button", { name: "Abbrechen" }));
    expect(screen.getByRole("button", { name: "Organisationszuordnung bearbeiten" })).toBeInTheDocument();
    expect(screen.getByText("Wartungsvertrag")).toBeInTheDocument();
    expect(mocks.updateContractOwnership).not.toHaveBeenCalled();
    await openEdit(user);
    expect(screen.getByLabelText("Vertragstyp")).toHaveValue("t-wartung");
  });

  it("Strg+S speichert; danach Ansicht mit „Gespeichert“ und Toast", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    await user.selectOptions(screen.getByLabelText("Kostenstelle"), "cc-1");
    await user.keyboard("{Control>}s{/Control}");
    await waitFor(() => expect(mocks.updateContractOwnership).toHaveBeenCalledWith("klinik", "contract-1", expect.objectContaining({ cost_center_id: "cc-1" })));
    expect(await screen.findByText("Gespeichert")).toBeInTheDocument();
    expect(mocks.toast).toHaveBeenCalledWith("Organisationszuordnung gespeichert.", "success");
    expect(screen.getByRole("button", { name: "Organisationszuordnung bearbeiten" })).toBeInTheDocument();
    expect(screen.getByText("4400")).toHaveClass("mono");
  });

  it("gesperrtes Krankenhaus: Grund und Sprung zu den Abteilungen statt stummem Feld", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    const locked = screen.getByRole("group", { name: "Krankenhaus" });
    expect(locked).toHaveTextContent("Klinikum Heidelberg");
    expect(locked).toHaveTextContent("gesperrt");
    expect(locked).toHaveAccessibleDescription(/Änderbar, sobald keine Abteilungen mehr zugeordnet sind/);
    await user.click(screen.getByRole("button", { name: "Abteilungen ansehen" }));
    expect(screen.getByLabelText("Verantwortliche Abteilung")).toHaveFocus();
  });

  it("ohne Krankenhaus: abhängige Felder sagen, was zuerst nötig ist", async () => {
    const user = userEvent.setup();
    mocks.getContractDepartmentRoles.mockResolvedValue({ contract_id: "contract-1", responsible_department_id: null, beneficiary_department_ids: [], unclassified_department_ids: [] });
    mocks.getContractOwnership.mockResolvedValue({ contract_id: "contract-1", hospital_id: null, department_ids: [], cost_center_id: null, responsible_account_id: null, scope_type: "organization" });
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    expect(screen.getAllByText("Zuerst ein Krankenhaus wählen")).toHaveLength(3);
    expect(screen.queryByLabelText("Verantwortliche Abteilung")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nutzende Abteilung hinzufügen" })).not.toBeInTheDocument();
  });

  it("Link mit ?abschnitt=ownership öffnet direkt die Bearbeitung", async () => {
    mocks.searchParams = new URLSearchParams("tab=register&abschnitt=ownership");
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    expect(await screen.findByLabelText("Vertragstyp")).toHaveValue("t-wartung");
  });

  it("Gerätearten: passende der Abteilungen zuerst, hinzufügen und entfernen, Anzahl und Notiz bleiben", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    expect(screen.getByRole("list", { name: /^Gerätearten/ })).toHaveTextContent("CT");
    await user.click(screen.getByRole("button", { name: "Geräteart hinzufügen" }));
    const panel = screen.getByRole("group", { name: "Geräteart hinzufügen" });
    // Radiologie liegt unter Medizintechnik; Patientenmonitoring gehört der nutzenden Intensivmedizin.
    const matching = within(panel).getByRole("group", { name: "Passend zu den Abteilungen" });
    expect(within(matching).getAllByRole("button").map((option) => option.textContent)).toEqual(["MRT", "Patientenmonitoring"]);
    expect(within(panel).getByRole("group", { name: "IT" })).toHaveTextContent("Server");
    expect(within(panel).queryByRole("button", { name: "CT" })).not.toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Server" }));
    expect(screen.getByRole("button", { name: "Geräteart hinzufügen" })).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));
    await waitFor(() => expect(mocks.saveContractDeviceTypes).toHaveBeenCalledWith("klinik", "contract-1", [
      { device_type_id: "dt-ct", quantity: 2, note: "Haus A" },
      { device_type_id: "dt-server", quantity: null, note: null },
    ]));
  });

  it("Escape schließt die Auswahl und gibt den Fokus an den Knopf zurück", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    await user.click(screen.getByRole("button", { name: "Geräteart hinzufügen" }));
    expect(screen.getByRole("group", { name: "Geräteart hinzufügen" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("group", { name: "Geräteart hinzufügen" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Geräteart hinzufügen" })).toHaveFocus();
  });

  it("Gerätearten nicht ladbar: Feld fehlt, Zuordnung bleibt bearbeitbar", async () => {
    const user = userEvent.setup();
    mocks.listDeviceTypes.mockRejectedValue(new Error("down"));
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    expect(screen.queryByRole("button", { name: "Geräteart hinzufügen" })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Kostenstelle"), "cc-1");
    expect(screen.getByRole("button", { name: "Zuordnung speichern" })).toBeEnabled();
  });

  it("Vertragstyp: speichert einen neuen (unpassende Kategorie wird geleert)", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    await user.selectOptions(screen.getByLabelText("Vertragstyp"), "t-miete");
    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));
    await waitFor(() => expect(mocks.updateContractRegister).toHaveBeenCalledWith("klinik", "contract-1", {
      changes: { contract_type_id: "t-miete", contract_category_id: null },
    }));
  });

  it("zeigt Verantwortlichen und nutzenden Bereich mit vollständigem Pfad und speichert beide Rollen", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    const responsible = screen.getByLabelText("Verantwortliche Abteilung");
    expect(responsible).toHaveValue("dept-rad");
    expect(screen.getByRole("option", { name: "Medizintechnik › Radiologie" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: /^Nutzende Abteilungen/ })).toHaveTextContent("Intensivmedizin");

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
  });

  it("nutzende Abteilung entfernen: Auswahl bietet sie wieder an und speichert ohne sie", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    await user.click(screen.getByRole("button", { name: "Intensivmedizin entfernen" }));
    expect(screen.queryByRole("list", { name: /^Nutzende Abteilungen/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Nutzende Abteilung hinzufügen" }));
    expect(within(screen.getByRole("group", { name: "Nutzende Abteilung hinzufügen" })).getByRole("button", { name: "Intensivmedizin" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Zuordnung speichern" }));
    await waitFor(() => expect(mocks.updateContractDepartmentRoles).toHaveBeenCalledWith("klinik", "contract-1", {
      responsible_department_id: "dept-rad",
      beneficiary_department_ids: [],
    }));
  });

  it("ohne Benutzer: sagt es und verlinkt nicht auf eine leere Auswahl", async () => {
    const user = userEvent.setup();
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    expect(screen.getByText(/In dieser Organisation gibt es noch keine Benutzer/)).toBeInTheDocument();
    expect(screen.getByLabelText("Hauptverantwortlich")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Weitere verantwortliche Person hinzufügen" })).not.toBeInTheDocument();
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
    await openEdit(user);
    expect(screen.getByLabelText("Hauptverantwortlich")).toHaveValue("u-1");
    expect(screen.getByRole("list", { name: /^Weitere Verantwortliche/ })).toHaveTextContent("Jonas Kurz");
    // Lea gehört zu einer anderen Abteilung – trotzdem wählbar (unter „Weitere Benutzer der Organisation“).
    await user.click(screen.getByRole("button", { name: "Weitere verantwortliche Person hinzufügen" }));
    const people = screen.getByRole("group", { name: "Weitere verantwortliche Person hinzufügen" });
    expect(within(within(people).getByRole("group", { name: "Weitere Benutzer der Organisation" })).getByRole("button", { name: "Lea Wolf" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await pick(user, "Weitere verantwortliche Person hinzufügen", "Lea Wolf");
    expect(screen.getByRole("list", { name: /^Weitere Verantwortliche/ })).toHaveTextContent("Lea Wolf");
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
    await openEdit(user);
    const department = screen.getByLabelText("Verantwortliche Abteilung");
    await user.selectOptions(department, "dept-rad");
    expect(screen.getByLabelText("Kostenstelle")).toHaveValue("cc-rad");
    // Kostenstelle einer nutzenden Abteilung wählen: die verantwortliche Abteilung bleibt.
    await pick(user, "Nutzende Abteilung hinzufügen", "Intensivmedizin");
    const center = screen.getByLabelText("Kostenstelle");
    expect(within(center).getByRole("group", { name: "Verantwortliche Abteilung" })).toHaveTextContent("4400");
    expect(within(center).getByRole("group", { name: "Nutzende Abteilungen" })).toHaveTextContent("4500");
    await user.selectOptions(center, "cc-icu");
    expect(department).toHaveValue("dept-rad");
    expect(screen.getByRole("list", { name: /^Nutzende Abteilungen/ })).toHaveTextContent("Intensivmedizin");
    expect(center).toHaveValue("cc-icu");
  });

  it("ohne verantwortliche Abteilung: Kostenstelle wählen setzt ihre Abteilung", async () => {
    const user = userEvent.setup();
    mocks.listCostCenters.mockResolvedValue({ items: [{ id: "cc-icu", hospital_id: "hospital-1", department_id: "dept-icu", code: "4500", name: "Intensiv", is_active: true }] });
    mocks.getContractDepartmentRoles.mockResolvedValue({ contract_id: "contract-1", responsible_department_id: null, beneficiary_department_ids: [], unclassified_department_ids: [] });
    mocks.getContractOwnership.mockResolvedValue({ contract_id: "contract-1", hospital_id: "hospital-1", department_ids: [], cost_center_id: null, responsible_account_id: null, scope_type: "hospital" });
    render(<ContractOwnershipPanel contractId="contract-1" orgSlug="klinik" />);
    await openEdit(user);
    await user.selectOptions(screen.getByLabelText("Kostenstelle"), "cc-icu");
    expect(screen.getByLabelText("Verantwortliche Abteilung")).toHaveValue("dept-icu");
  });
});
