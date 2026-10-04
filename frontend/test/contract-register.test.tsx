import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractRegisterPanel from "@/components/contracts/detail/ContractRegisterPanel";
import ContractRemarksPanel from "@/components/contracts/detail/ContractRemarksPanel";
import type { ContractRegister, RegisterField } from "@/lib/domain-api/register";

const api = vi.hoisted(() => ({
  getContractRegister: vi.fn(),
  updateContractRegister: vi.fn(),
  acceptRegisterProposal: vi.fn(),
  changeContractStatus: vi.fn(),
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
  listOwnershipAssignees: vi.fn().mockResolvedValue({ items: [] }),
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
    expect(await screen.findByRole("heading", { name: "Vertrag 000042" })).toBeInTheDocument();
    expect(screen.getByText("In Arbeit")).toBeInTheDocument();
    const terms = screen.getByRole("heading", { name: "Berechnete Fristen" }).closest("section")!;
    expect(within(terms).getByText("Kündbar bis").nextElementSibling).toHaveTextContent("30.06.2027");
    expect(within(terms).getByText("Erinnerung am").nextElementSibling).toHaveTextContent("30.03.2027");
    expect(screen.getByText("KI-Vorschlag")).toHaveAttribute("title", "Quelle: identity.contract_title");
    expect(screen.getByText("KI · korrigiert")).toBeInTheDocument();
    expect(screen.getByText(/Für „Gültig“ fehlen noch: Vertragspartner/)).toBeInTheDocument();
  });

  it("ist barrierefrei in Ansicht und Bearbeitung", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Vertrag 000042" });
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Stammdaten bearbeiten" }));
    expect(await axe(container)).toHaveNoViolations();
  });

  it("bestätigt einen KI-Wert und übernimmt Vorschläge nur auf Klick", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Vertrag 000042" });

    await user.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: {}, confirm: ["short_description"] });

    const suggestions = screen.getByRole("heading", { name: "KI-Vorschläge" }).closest("section")!;
    const buttons = within(suggestions).getAllByRole("button", { name: "Übernehmen" });
    await user.click(buttons[0]);
    expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { partner_id: "p-1" } });
    await user.click(buttons[1]);
    expect(api.acceptRegisterProposal).toHaveBeenCalledWith("test-klinik", "c-1", "term_start_date");
  });

  it("speichert nur geänderte Felder", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Vertrag 000042" });
    await user.click(screen.getByRole("button", { name: "Stammdaten bearbeiten" }));
    await user.type(screen.getByLabelText("Interne Nummer"), "INT-7");
    await user.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { internal_number: "INT-7" } }));
  });

  it("verlangt bei ungeprüften KI-Werten eine bewusste Freigabe", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Vertrag 000042" });
    await user.click(screen.getByRole("button", { name: "→ Gültig" }));
    await user.click(screen.getByLabelText(/Ich gebe den Vertrag trotzdem frei/));
    await user.click(screen.getByRole("button", { name: "Status ändern" }));
    await waitFor(() => expect(api.changeContractStatus).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ target: "gueltig", acknowledge_unreviewed: true })));
    expect(await screen.findByText("Status auf „Gültig“ gesetzt.")).toBeInTheDocument();
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
