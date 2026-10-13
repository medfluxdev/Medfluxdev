import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractRegisterPanel from "@/components/contracts/detail/ContractRegisterPanel";
import ContractRemarksPanel from "@/components/contracts/detail/ContractRemarksPanel";
import type { ContractRegister, RegisterField } from "@/lib/domain-api/register";
import { enhanceBoxes } from "@/lib/box-collapse";

const api = vi.hoisted(() => ({
  getContractRegister: vi.fn(),
  updateContractRegister: vi.fn(),
  acceptRegisterProposal: vi.fn(),
  changeContractStatus: vi.fn(),
  updateContractConfidentiality: vi.fn(),
  listContractRemarks: vi.fn(),
  addContractRemark: vi.fn(),
}));

vi.mock("@/lib/domain-api/register", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/register")>()),
  ...api,
}));

vi.mock("@/lib/domain-api/catalogs", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/catalogs")>()),
  listPartners: vi.fn().mockResolvedValue({ total: 1, items: [{ id: "p-1", short_name: "MEDTEC", name1: "Medtec GmbH", city: "Berlin", is_active: true }] }),
  listContractTypes: vi.fn().mockResolvedValue({ contract_types: [], contract_categories: [] }),
  listLookups: vi.fn().mockResolvedValue({ field_keys: [], items: [] }),
  createPartner: vi.fn(),
}));

vi.mock("@/lib/domain-api/ownership", () => ({
  listOwnershipAssignees: vi.fn().mockResolvedValue({ items: [{ id: "a-2", display_name: "Vera Viewer" }] }),
}));

function field(label: string, value: RegisterField["value"], extra: Partial<RegisterField> = {}): RegisterField {
  return {
    value, label, group: "identity", display: null, origin: null, source_field: null, extraction_id: null,
    ai_proposed_value: null, confirmed_by_name: null, confirmed_at: null, updated_by_name: null, updated_at: null, ...extra,
  };
}

function register(overrides: Partial<ContractRegister> = {}): ContractRegister {
  return {
    contract_id: "c-1",
    register_number: "000042",
    business_status: "in_arbeit",
    business_status_label: "In Arbeit",
    allowed_transitions: [{ target: "gueltig", label: "Gültig" }],
    supplier_text: "Medtec GmbH",
    has_ai_analysis: true,
    review_pending: true,
    ended_on: null,
    fields: {
      short_description: field("Kurzbeschreibung", "Wartung MRT", { origin: "ai", source_field: "identity.contract_title" }),
      internal_number: field("Interne Nummer", null),
      partner_id: field("Vertragspartner", null),
      contract_type_id: field("Vertragstyp", null),
      contract_category_id: field("Kategorie", null),
      is_framework: field("Rahmenvertrag", false),
      data_protection_relevant: field("Datenschutzrelevant (AVV erforderlich)", true),
      subject_text: field("Vertragsgegenstand", null),
      term_model: field("Vertragsart", "terminable", { origin: "manual" }),
      term_start_date: field("Vertragsbeginn", "2027-04-01", { origin: "ai_corrected", ai_proposed_value: { value: "2027-05-01", source_field: "dates.start_date" } }),
      term_fixed_end_date: field("Festes Vertragsende", null),
      notice_period_value: field("Kündigungsfrist", 3),
      notice_period_unit: field("Kündigungsfrist (Einheit)", "months"),
      notice_to: field("Kündigung zum", "quarter_end"),
      minimum_term_value: field("Mindestlaufzeit", null),
      minimum_term_unit: field("Mindestlaufzeit (Einheit)", null),
      initial_term_value: field("Laufzeit", null),
      initial_term_unit: field("Laufzeit (Einheit)", null),
      renewal_period_value: field("Verlängerung um", null),
      renewal_period_unit: field("Verlängerung (Einheit)", null),
      reminder_lead_months: field("Erinnerung (Monate vor Frist)", 3),
      reminder_recipient_account_id: field("Erinnerung an", null),
      escalation_recipient_account_id: field("Eskalation an", null),
      reminder_todo: field("ToDo", null),
      storage_location_code: field("Lagerort des Originals", null),
      account_number: field("Kontonummer", null),
      manual_billing: field("Manuelle Abrechnung", false),
      terminated_on: field("Gekündigt am", null),
      terminated_effective: field("Gekündigt zum", null),
      retention_years_after_end: field("Löschen nach Ende (Jahre)", null),
    },
    terms: {
      status: "complete", earliest_end: "2027-09-30", cancel_by: "2027-06-30", possible_end: "2027-09-30",
      actual_end: null, reminder_date: "2027-03-30", missing: [], explanation: ["Kündbar mit Frist 3 Monate zum Quartalsende."],
    },
    missing_for_valid: ["partner_id"],
    as_of: "2026-10-04",
    partner_suggestions: [{ id: "p-1", short_name: "MEDTEC", name1: "Medtec GmbH", city: "Berlin", score: 0.97 }],
    type_suggestion: null,
    storage_location_label: null,
    retention: { years: 10, source: "contract_type", contract_end: "2027-09-30", deletion_from: "2038-01-01" },
    confidentiality: { is_confidential: false, type_confidential: false, effective: false, grants: [] },
    ...overrides,
  };
}

describe("Vertragsregister – Stammdaten", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getContractRegister.mockResolvedValue(register());
    api.updateContractRegister.mockImplementation(async () => register());
    api.acceptRegisterProposal.mockResolvedValue(register());
    api.changeContractStatus.mockResolvedValue(register({ business_status: "gueltig", business_status_label: "Gültig", allowed_transitions: [] }));
  });

  it("zeigt Nummer, Status, berechnete Fristen und die Herkunft der Werte", async () => {
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByRole("heading", { name: "Bearbeitungsstatus" })).toBeInTheDocument();
    expect(screen.getByText("In Arbeit")).toBeInTheDocument();
    const terms = screen.getByRole("heading", { name: "Berechnete Fristen" }).closest("section")!;
    expect(within(terms).getByText("Kündbar bis").nextElementSibling).toHaveTextContent("30.06.2027");
    expect(within(terms).getByText("Erinnerung am").nextElementSibling).toHaveTextContent("30.03.2027");
    expect(screen.getByText("KI-Vorschlag")).toHaveAttribute("title", "Quelle: identity.contract_title");
    expect(screen.getByText("KI · korrigiert")).toBeInTheDocument();
    expect(screen.getByText(/Für „Gültig“ fehlen noch:/).closest("p")).toHaveTextContent("Für „Gültig“ fehlen noch: Vertragspartner.");
  });

  it("ist barrierefrei in Ansicht und Bearbeitung", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Bearbeitungsstatus" });
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Vertrag & Partner bearbeiten" }));
    expect(await axe(container)).toHaveNoViolations();
  });

  it("bestätigt einen KI-Wert und übernimmt Vorschläge nur auf Klick", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Bearbeitungsstatus" });

    await user.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: {}, confirm: ["short_description"] });

    const suggestions = screen.getByRole("heading", { name: "KI-Vorschläge" }).closest("section")!;
    const buttons = within(suggestions).getAllByRole("button", { name: "Übernehmen" });
    await user.click(buttons[0]);
    expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { partner_id: "p-1" } });
    await user.click(buttons[1]);
    expect(api.acceptRegisterProposal).toHaveBeenCalledWith("test-klinik", "c-1", "term_start_date");
  });

  it("Interne Nummer ist die automatisch vergebene Vertragsnummer – nicht von Hand änderbar", async () => {
    const user = userEvent.setup();
    api.getContractRegister.mockResolvedValue({ ...(await api.getContractRegister()), fields: { ...(await api.getContractRegister()).fields, internal_number: { ...(await api.getContractRegister()).fields.internal_number, value: "ALT-12" } } });
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const field = (await screen.findByText("Interne Nummer")).closest(".rg-field") as HTMLElement;
    expect(within(field).getByText("automatisch")).toBeInTheDocument();
    expect(within(field).getByText("Frühere interne Nummer: ALT-12")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Vertrag & Partner bearbeiten" }));
    expect(screen.queryByLabelText("Interne Nummer")).not.toBeInTheDocument();
    expect(within(field).queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("speichert nur geänderte Felder", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Bearbeitungsstatus" });
    await user.click(screen.getByRole("button", { name: "Vertrag & Partner bearbeiten" }));
    await user.type(screen.getByLabelText("Vertragsgegenstand"), "INT-7");
    await user.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { subject_text: "INT-7" } }));
  });

  it("verlangt bei ungeprüften KI-Werten eine bewusste Freigabe", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Bearbeitungsstatus" });
    await user.click(screen.getByRole("button", { name: "→ Gültig" }));
    await user.click(screen.getByLabelText(/Ich gebe den Vertrag trotzdem frei/));
    await user.click(screen.getByRole("button", { name: "Status ändern" }));
    await waitFor(() => expect(api.changeContractStatus).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ target: "gueltig", acknowledge_unreviewed: true })));
    expect(await screen.findByText("Status auf „Gültig“ gesetzt.")).toBeInTheDocument();
  });

  it("hebt eine Stornierung auf und kehrt in den früheren Status zurück", async () => {
    const user = userEvent.setup();
    api.getContractRegister.mockResolvedValue(register({ business_status: "geloescht", business_status_label: "Storniert", allowed_transitions: [{ target: "beendet", label: "Beendet" }] }));
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await user.click(await screen.findByRole("button", { name: "Stornierung aufheben → Beendet" }));
    expect(screen.getByText(/kehrt in den Status vor der Stornierung zurück: „Beendet“/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Status ändern" }));
    await waitFor(() => expect(api.changeContractStatus).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ target: "beendet" })));
  });

  it("klappt einen eingeklappten Statuskasten auf, wenn ein Statuswechsel gewählt wird", async () => {
    const user = userEvent.setup();
    window.localStorage.removeItem("medflux.collapsed-boxes");
    api.getContractRegister.mockResolvedValue(register({ business_status: "geloescht", business_status_label: "Storniert", allowed_transitions: [{ target: "beendet", label: "Beendet" }] }));
    const { container } = render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const button = await screen.findByRole("button", { name: "Stornierung aufheben → Beendet" });
    enhanceBoxes(container);
    await user.click(screen.getByRole("button", { name: "Bearbeitungsstatus einklappen" }));
    const box = screen.getByRole("heading", { name: "Bearbeitungsstatus" }).closest("section")!;
    expect(box).toHaveAttribute("data-collapsed");
    await user.click(button);
    expect(box).not.toHaveAttribute("data-collapsed");
    expect(screen.getByLabelText("Beendet am")).toHaveFocus();
  });
});

describe("Vertragsregister – Vertraulichkeit & Aufbewahrung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getContractRegister.mockResolvedValue(register());
    api.updateContractConfidentiality.mockResolvedValue(register({
      confidentiality: { is_confidential: true, type_confidential: false, effective: true, grants: [{ account_id: "a-2", display_name: "Vera Viewer" }] },
    }));
  });

  it("zeigt Löschfrist aus dem Vertragstyp und setzt Vertraulichkeit mit Freigabe", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const section = (await screen.findByRole("heading", { name: "Vertraulichkeit & Aufbewahrung" })).closest("section")!;
    expect(within(section).getByText("Löschen ab").nextElementSibling).toHaveTextContent("01.01.2038");
    expect(within(section).getByText("aus Vertragstyp")).toBeInTheDocument();
    expect(screen.getByText("Datenschutzrelevant (AVV erforderlich)")).toBeInTheDocument();

    await user.click(within(section).getByRole("button", { name: "Vertraulichkeit bearbeiten" }));
    await user.click(within(section).getByLabelText("Vertrag als vertraulich kennzeichnen"));
    await user.click(await within(section).findByLabelText("Vera Viewer"));
    await user.click(within(section).getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.updateContractConfidentiality).toHaveBeenCalledWith("test-klinik", "c-1", { is_confidential: true, grant_account_ids: ["a-2"] }));
    expect(await within(section).findByText(/freigegeben für: Vera Viewer/)).toBeInTheDocument();
  });
});

describe("Vertragsregister – Bemerkungen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listContractRemarks.mockResolvedValue({ items: [{ id: "r-1", author_name: "Admin", body: "Angebot angefragt", created_at: "2026-10-01T10:00:00Z" }] });
    api.addContractRemark.mockResolvedValue({ items: [
      { id: "r-2", author_name: "Admin", body: "Neue Notiz", created_at: "2026-10-04T10:00:00Z" },
      { id: "r-1", author_name: "Admin", body: "Angebot angefragt", created_at: "2026-10-01T10:00:00Z" },
    ] });
  });

  it("listet das Journal und fügt Einträge an", async () => {
    const user = userEvent.setup();
    render(<ContractRemarksPanel contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("Angebot angefragt")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Neue Bemerkung"), "Neue Notiz");
    await user.click(screen.getByRole("button", { name: "Bemerkung hinzufügen" }));
    expect(api.addContractRemark).toHaveBeenCalledWith("test-klinik", "c-1", "Neue Notiz");
    expect(await screen.findByText("Neue Notiz")).toBeInTheDocument();
    expect(screen.getByLabelText("Neue Bemerkung")).toHaveValue("");
  });
});

describe("Vertragsregister – Formularschutz", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getContractRegister.mockResolvedValue(register());
    api.updateContractRegister.mockImplementation(async () => register());
  });

  it("speichert mit Strg+S und markiert ungespeicherte Änderungen", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Bearbeitungsstatus" });
    await user.click(screen.getByRole("button", { name: "Vertrag & Partner bearbeiten" }));
    await user.type(screen.getByLabelText("Vertragsgegenstand"), "INT-9");
    expect(screen.getByText(/Ungespeicherte Änderungen/)).toBeInTheDocument();
    await user.keyboard("{Control>}s{/Control}");
    await waitFor(() => expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { subject_text: "INT-9" } }));
  });
});
