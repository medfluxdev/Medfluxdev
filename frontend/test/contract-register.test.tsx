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
  updateContractConfidentiality: vi.fn(),
  listContractRemarks: vi.fn(),
  addContractRemark: vi.fn(),
  saveReminderLeads: vi.fn(),
}));

const toast = vi.hoisted(() => vi.fn());
vi.mock("@/components/ui/Toast", () => ({ useToast: () => toast }));
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

const docs = vi.hoisted(() => ({ listContractDocuments: vi.fn() }));
vi.mock("@/lib/domain-api/contractDocuments", () => docs);

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
    docs.listContractDocuments.mockResolvedValue({ items: [], removed: [], attachment_types: [] });
    api.getContractRegister.mockResolvedValue(register());
    api.updateContractRegister.mockImplementation(async () => register());
    api.acceptRegisterProposal.mockResolvedValue(register());
    api.changeContractStatus.mockResolvedValue(register({ business_status: "gueltig", business_status_label: "Gültig", allowed_transitions: [] }));
  });

  it("zeigt Nummer, Status, berechnete Fristen und die Herkunft der Werte", async () => {
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByRole("heading", { name: "Bearbeitungsstatus" })).toBeInTheDocument();
    expect(screen.getByText("In Arbeit")).toBeInTheDocument();
    const terms = screen.getByRole("heading", { name: "Laufzeit, Fristen & Kündigung" }).closest("section")!;
    expect(within(terms).getByText("Kündbar bis").nextElementSibling).toHaveTextContent("30.06.2027");
    expect(within(terms).queryByText(/Erinnerung/)).not.toBeInTheDocument();
    // Erinnerungen stehen unter Fristen & Aufgaben.
    expect(screen.queryByRole("heading", { name: "Erinnerungen" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Wartung planen" })).not.toBeInTheDocument();
    expect(screen.getByText("KI · Vorschlag")).toHaveAttribute("title", "Quelle: identity.contract_title");
    expect(screen.getByText("KI · korrigiert")).toBeInTheDocument();
    expect(screen.getByText(/Für „Gültig“ fehlen noch:/).closest("p")).toHaveTextContent("Für „Gültig“ fehlen noch: Vertragspartner.");
  });

  it("eingeklappt: Kurzfassung je Kasten, Fehlendes als Signal", async () => {
    const user = userEvent.setup();
    try {
      render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
      await screen.findByRole("heading", { name: "Bearbeitungsstatus" });
      for (const title of ["Bearbeitungsstatus", "Vertrag & Partner", "Laufzeit, Fristen & Kündigung", "Ablage & Abrechnung", "Preisanpassung"]) {
        await user.click(screen.getByRole("button", { name: `${title} einklappen` }));
      }
      const head = (title: string) => screen.getByRole("heading", { level: 2, name: title }).parentElement!;
      expect(head("Vertrag & Partner")).toHaveTextContent("Vertragspartner fehlt");
      expect(head("Vertrag & Partner")).toHaveTextContent("Nr. 000042");
      expect(head("Laufzeit, Fristen & Kündigung")).toHaveTextContent("Kündbar bis 30.06.2027");
      // Jede eingeklappte Karte zeigt eine kurze Angabe unter dem Namen.
      expect(head("Bearbeitungsstatus")).toHaveTextContent(/Status In Arbeit/);
      expect(head("Ablage & Abrechnung")).toHaveTextContent(/Ablage|Konto|Manuelle Abrechnung|Nichts erfasst/);
      expect(head("Preisanpassung")).toHaveTextContent(/Keine Preisanpassung erfasst|nächste/);
      // Bearbeiten bleibt auch eingeklappt erreichbar und klappt auf.
      await user.click(screen.getByRole("button", { name: "Laufzeit, Fristen & Kündigung bearbeiten" }));
      expect(screen.getByRole("button", { name: "Laufzeit, Fristen & Kündigung einklappen" })).toHaveAttribute("aria-expanded", "true");
    } finally {
      window.localStorage.removeItem("medflux.collapsed-sections");
    }
  });

  it("eingeklappt: nicht berechenbare Fristen ohne Kündigungsfrist melden genau das", async () => {
    const user = userEvent.setup();
    const base = register();
    api.getContractRegister.mockResolvedValue({ ...base, terms: { ...base.terms, status: "incomplete", missing: ["notice_period_value"], cancel_by: null } });
    try {
      render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
      await user.click(await screen.findByRole("button", { name: "Laufzeit, Fristen & Kündigung einklappen" }));
      expect(screen.getByRole("heading", { level: 2, name: "Laufzeit, Fristen & Kündigung" }).parentElement).toHaveTextContent("Kündigungsfrist fehlt");
    } finally {
      window.localStorage.removeItem("medflux.collapsed-sections");
    }
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
    // Erfolg nur als Toast, nicht als Text zwischen den Kästen.
    await waitFor(() => expect(toast).toHaveBeenCalledWith("Status auf „Gültig“ gesetzt.", "success"));
    expect(screen.queryByText("Status auf „Gültig“ gesetzt.")).not.toBeInTheDocument();
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
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const button = await screen.findByRole("button", { name: "Stornierung aufheben → Beendet" });
    const toggle = screen.getByRole("button", { name: "Bearbeitungsstatus einklappen" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    // Die Statusknöpfe bleiben im Kopf bedienbar; ein Wechsel klappt den Kasten wieder auf.
    await user.click(button);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    await waitFor(() => expect(screen.getByLabelText("Beendet am")).toHaveFocus());
  });
});

const section = async (name: string) => (await screen.findByRole("heading", { level: 2, name })).closest("section")!;

describe("Vertragsregister – Laufzeit, Fristen & Kündigung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    docs.listContractDocuments.mockResolvedValue({ items: [], removed: [], attachment_types: [] });
  });

  const fixed = (overrides: Partial<ContractRegister> = {}) => {
    const base = register();
    return register({
      fields: {
        ...base.fields,
        term_model: field("Vertragsart", "fixed_term", { origin: "ai_confirmed" }),
        term_fixed_end_date: field("Festes Vertragsende", "2029-03-31"),
        initial_term_value: field("Laufzeit", 4),
        initial_term_unit: field("Laufzeit (Einheit)", "years"),
      },
      terms: { ...base.terms, cancel_by: null, possible_end: "2029-03-31", earliest_end: "2029-03-31", reminder_date: "2028-11-30", reminder_dates: ["2028-11-30", "2029-01-06"], explanation: ["Feste Laufzeit: Ende = festes Vertragsende 31.03.2029."] },
      ...overrides,
    });
  };

  it("feste Laufzeit: nur passende Felder, Berechnet-Streifen mit Vertragsende und Restlaufzeit; ohne Verstöße (axe)", async () => {
    api.getContractRegister.mockResolvedValue(fixed());
    const { container } = render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Laufzeit, Fristen & Kündigung");
    for (const label of ["Vertragsart", "Vertragsbeginn", "Festes Vertragsende", "Laufzeit"]) expect(within(card).getByText(label)).toBeInTheDocument();
    for (const label of ["Kündigungsfrist", "Kündigung zum", "Mindestlaufzeit", "Verlängerung um"]) expect(within(card).queryByText(label)).not.toBeInTheDocument();
    expect(within(card).queryByText("Nicht erfasst")).not.toBeInTheDocument();
    expect(within(card).getByText("Berechnet")).toBeInTheDocument();
    expect(within(card).getByText("Automatisch aus den Angaben oben, Stand 04.10.2026")).toBeInTheDocument();
    expect(within(card).queryByText("Kündbar bis")).not.toBeInTheDocument();
    expect(within(card).getByText("Vertragsende", { selector: "dt" }).nextElementSibling).toHaveTextContent("31.03.2029");
    expect(within(card).getByText("Restlaufzeit", { selector: "dt" }).nextElementSibling).toHaveTextContent("909 Tage");
    expect(within(card).queryByText(/Erinnerung/)).not.toBeInTheDocument();
    expect(within(card).getByText("Wie berechnet?").closest("details")).toHaveTextContent("Feste Laufzeit: Ende = festes Vertragsende 31.03.2029.");
    expect(within(card).getByText("KI · bestätigt")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Bearbeiten: Streifen zeigt die aktuellen Werte mit „Wird nach dem Speichern neu berechnet“, Speichern unten", async () => {
    const user = userEvent.setup();
    api.getContractRegister.mockResolvedValue(fixed());
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Laufzeit, Fristen & Kündigung");
    await user.click(within(card).getByRole("button", { name: "Laufzeit, Fristen & Kündigung bearbeiten" }));
    expect(within(card).getByText("Wird nach dem Speichern neu berechnet")).toBeInTheDocument();
    expect(within(card).queryByText("Wie berechnet?")).not.toBeInTheDocument();
    expect(within(card).getByText("Vertragsende", { selector: "dt" }).nextElementSibling).toHaveTextContent("31.03.2029");
    const bar = within(card).getByRole("region", { name: "Laufzeit, Fristen & Kündigung speichern" });
    expect(within(bar).getByRole("button", { name: "Speichern" })).toBeInTheDocument();
    expect(within(card).getByText("KI · bestätigt")).toBeInTheDocument();
  });

  it("Erinnern: Chips, hinzufügen und entfernen; gespeichert über erste + weitere Erinnerungen", async () => {
    const user = userEvent.setup();
    const base = fixed();
    api.getContractRegister.mockResolvedValue({ ...base, fields: { ...base.fields, reminder_lead_months: field("Erinnerung (Monate vor Frist)", null) }, reminders: { default_lead_months: 4, lead_months: null, extra_leads: [{ value: 12, unit: "weeks" }] } });
    api.saveReminderLeads.mockResolvedValue(base);
    render(<ContractRegisterPanel view="deadlines" contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Erinnerungen");
    // Ansicht „Fristen & Aufgaben“: nur Erinnerungen und Wartungstermin, kein Status, keine Vertragsdaten.
    expect(screen.queryByRole("heading", { name: "Bearbeitungsstatus" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Laufzeit, Fristen & Kündigung" })).not.toBeInTheDocument();
    const chips = () => within(within(card).getByRole("list", { name: "Erinnerungen" })).getAllByRole("listitem").map((item) => item.textContent);
    expect(chips()).toEqual(["4 Monate vorher (Standard)", "12 Wochen vorher"]);

    await user.click(within(card).getByRole("button", { name: "Erinnerungen bearbeiten" }));
    expect(within(card).getByText(/Standard des Vertragstyps: 4 Monate vorher/)).toBeInTheDocument();
    expect(within(card).queryByRole("button", { name: "4 Monate vorher (Standard) entfernen" })).not.toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "+ Erinnerung" }));
    await user.type(within(card).getByLabelText("Anzahl"), "6");
    await user.selectOptions(within(card).getByLabelText("Einheit"), "months");
    await user.click(within(card).getByRole("button", { name: "Hinzufügen" }));
    expect(chips().slice(0, 2)).toEqual(["12 Wochen vorher", "6 Monate vorher"]);
    await user.click(within(card).getByRole("button", { name: "12 Wochen vorher entfernen" }));
    expect(chips()[0]).toBe("6 Monate vorher");
    await user.click(within(within(card).getByRole("region", { name: "Erinnerungen speichern" })).getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { reminder_lead_months: 6 } }));
    await waitFor(() => expect(api.saveReminderLeads).toHaveBeenCalledWith("test-klinik", "c-1", []));
  });

  it("gekündigt: Zeile mit Daten, keine Eingabefelder dafür; „Status ändern“ führt zum Status", async () => {
    const user = userEvent.setup();
    const base = fixed();
    api.getContractRegister.mockResolvedValue({ ...base, business_status: "gekuendigt", business_status_label: "Gekündigt", allowed_transitions: [{ target: "beendet", label: "Beendet" }],
      fields: { ...base.fields, terminated_on: field("Gekündigt am", "2028-02-12"), terminated_effective: field("Gekündigt zum", "2029-03-31") } });
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Laufzeit, Fristen & Kündigung");
    const row = within(card).getByText("Gekündigt").closest(".rg-termrow")!;
    expect(row).toHaveTextContent("Gekündigtam 12.02.2028 · zum 31.03.2029");
    expect(screen.queryByText("Gekündigt am")).not.toBeInTheDocument();
    expect(screen.queryByText("Gekündigt zum")).not.toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Status ändern" }));
    expect(screen.getByRole("button", { name: "→ Beendet" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Laufzeit, Fristen & Kündigung bearbeiten" }));
    expect(screen.queryByLabelText("Gekündigt am")).not.toBeInTheDocument();
  });

  it("unvollständig: Hinweis statt Kacheln; der Link öffnet das Feld", async () => {
    const user = userEvent.setup();
    const base = register();
    api.getContractRegister.mockResolvedValue({ ...base, terms: { ...base.terms, status: "incomplete", missing: ["notice_period_value"], cancel_by: null } });
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Laufzeit, Fristen & Kündigung");
    expect(within(card).getByText(/Fristen noch nicht berechenbar/)).toBeInTheDocument();
    expect(within(card).queryByText("Kündbar bis")).not.toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Kündigungsfrist erfassen" }));
    await waitFor(() => expect(document.getElementById("rg-notice_period")).toHaveFocus());
  });
});

describe("Vertragsregister – Aufbewahrung & Löschung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    docs.listContractDocuments.mockResolvedValue({ items: [], removed: [], attachment_types: [] });
    api.updateContractRegister.mockImplementation(async () => register());
  });

  it("aus Vertragstyp: Frist einmal, Löschen ab mit Rechnung; abweichend festlegen speichert am Vertrag", async () => {
    const user = userEvent.setup();
    api.getContractRegister.mockResolvedValue(register());
    const { container } = render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Aufbewahrung & Löschung");
    expect(within(card).getByText("aus Vertragstyp")).toBeInTheDocument();
    expect(screen.getAllByText(/10 Jahre nach Vertragsende/)).toHaveLength(1);
    expect(within(card).getByText("01.01.2038")).toBeInTheDocument();
    expect(within(card).getByText("Vertragsende 30.09.2027 → Jahresende 2027 + 10 Jahre")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Erläuterung zu Löschen ab" })).toHaveAccessibleDescription(/§ 257 HGB/);
    expect(screen.queryByText("Löschen nach Ende (Jahre)")).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    await user.click(within(card).getByRole("button", { name: "Abweichend festlegen" }));
    const input = within(card).getByLabelText("Aufbewahrung in Jahren");
    expect(input).toHaveFocus();
    await user.clear(input);
    await user.type(input, "12");
    await user.click(within(card).getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { retention_years_after_end: 12 } }));
  });

  it("am Vertrag festgelegt: zurücksetzen auf den Standard; fällige Löschprüfung als Signal", async () => {
    const user = userEvent.setup();
    api.getContractRegister.mockResolvedValue(register({ retention: { years: 12, source: "contract", contract_end: "2013-09-30", deletion_from: "2026-01-01" } }));
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Aufbewahrung & Löschung");
    expect(within(card).getByText("am Vertrag festgelegt")).toBeInTheDocument();
    expect(within(card).getByText("Löschprüfung fällig")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Festlegung am Vertrag entfernen" }));
    await waitFor(() => expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { retention_years_after_end: null } }));
  });

  it("nicht festgelegt und Ende unbekannt: „Festlegen“ und „erst nach bekanntem Vertragsende“", async () => {
    api.getContractRegister.mockResolvedValue(register({ retention: { years: null, source: null, contract_end: null, deletion_from: null } }));
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Aufbewahrung & Löschung");
    expect(within(card).getByText("Nicht festgelegt")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Aufbewahrung festlegen" })).toBeInTheDocument();
    expect(within(card).getByText("erst nach bekanntem Vertragsende")).toBeInTheDocument();
  });
});

describe("Vertragsregister – Zugriff & Datenschutz", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    docs.listContractDocuments.mockResolvedValue({ items: [], removed: [], attachment_types: [] });
    api.updateContractConfidentiality.mockResolvedValue(register({
      confidentiality: { is_confidential: true, type_confidential: false, effective: true, grants: [{ account_id: "a-2", display_name: "Vera Viewer" }] },
    }));
    api.updateContractRegister.mockImplementation(async () => register());
  });

  const withDp = (overrides: Partial<ContractRegister> = {}) => {
    const base = register();
    return register({ fields: { ...base.fields, data_protection_relevant: field("Datenschutzrelevant (AVV erforderlich)", true, { origin: "ai", source_field: "Dokumenttext: „personenbezogene Daten“" }) }, ...overrides });
  };

  it("vertraulich mit Freigaben, KI-Vorschlag mit Zitat, ohne AVV ein Hinweis mit Link; ohne Verstöße (axe)", async () => {
    api.getContractRegister.mockResolvedValue(withDp({ confidentiality: { is_confidential: true, type_confidential: false, effective: true, grants: [{ account_id: "a-2", display_name: "Vera Viewer" }] } }));
    const { container } = render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Zugriff & Datenschutz");
    expect(within(card).getByText("Sichtbar für: Administratoren, verantwortliche Person, Erinnerungsempfänger")).toBeInTheDocument();
    expect(within(card).getByText("Vera Viewer").closest(".tag-person")).toBeInTheDocument();
    expect(within(card).getByText("KI · Vorschlag")).toBeInTheDocument();
    expect(within(card).getByText("Dokumenttext: „personenbezogene Daten“")).toBeInTheDocument();
    expect(await within(card).findByText("Kein AVV hinterlegt")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "AVV hochladen" })).toHaveAttribute("href", "/contracts/c-1?tab=documents&subtab=attachments&dokumentart=avv");
    expect(screen.queryAllByText("Datenschutzrelevant (AVV erforderlich)")).toHaveLength(1);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("mit hinterlegtem AVV kein Hinweis", async () => {
    docs.listContractDocuments.mockResolvedValue({ items: [{ link_id: "l-1", attachment_type: "avv" }], removed: [], attachment_types: [] });
    api.getContractRegister.mockResolvedValue(withDp());
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Zugriff & Datenschutz");
    await waitFor(() => expect(docs.listContractDocuments).toHaveBeenCalled());
    expect(within(card).queryByText("Kein AVV hinterlegt")).not.toBeInTheDocument();
  });

  it("Bearbeiten: vertraulich, Freigabe und Datenschutz speichern; ohne Verstöße (axe)", async () => {
    const user = userEvent.setup();
    api.getContractRegister.mockResolvedValue(withDp());
    const { container } = render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Zugriff & Datenschutz");
    await user.click(within(card).getByRole("button", { name: "Zugriff & Datenschutz bearbeiten" }));
    expect(within(card).getByText("Vorschlag der KI: Ja – Dokumenttext: „personenbezogene Daten“.")).toBeInTheDocument();
    await user.click(within(card).getByLabelText(/Vertrag als vertraulich kennzeichnen/));
    await user.click(within(card).getByRole("button", { name: "Person freigeben" }));
    await user.click(within(screen.getByRole("group", { name: "Person freigeben" })).getByRole("button", { name: "Vera Viewer" }));
    await user.click(within(card).getByRole("button", { name: "Nein" }));
    expect(within(card).getByRole("button", { name: "Nein" })).toHaveAttribute("aria-pressed", "true");
    expect(await axe(container)).toHaveNoViolations();
    await user.click(within(card).getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.updateContractConfidentiality).toHaveBeenCalledWith("test-klinik", "c-1", { is_confidential: true, grant_account_ids: ["a-2"] }));
    await waitFor(() => expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { data_protection_relevant: false } }));
  });

  it("Vertragstyp vertraulich: Häkchen gesetzt und gesperrt, mit Hinweis", async () => {
    const user = userEvent.setup();
    api.getContractRegister.mockResolvedValue(register({ confidentiality: { is_confidential: false, type_confidential: true, effective: true, grants: [] } }));
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const card = await section("Zugriff & Datenschutz");
    expect(within(card).getByText("Ja (über Vertragstyp)")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Zugriff & Datenschutz bearbeiten" }));
    const box = within(card).getByLabelText(/Vertrag als vertraulich kennzeichnen/);
    expect(box).toBeChecked();
    expect(box).toBeDisabled();
    expect(within(card).getByText(/Der Vertragstyp ist bereits vertraulich/)).toBeInTheDocument();
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
    expect(within(screen.getByRole("region", { name: "Vertrag & Partner speichern" })).getByText("Ungespeicherte Änderungen")).toBeInTheDocument();
    await user.keyboard("{Control>}s{/Control}");
    await waitFor(() => expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: { subject_text: "INT-9" } }));
  });
});
