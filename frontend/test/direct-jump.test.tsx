import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractRegisterPanel from "@/components/contracts/detail/ContractRegisterPanel";
import MissingList from "@/components/ui/MissingList";
import { baseFieldKey, contractHref, documentSearchHref, registerHref } from "@/lib/fix-targets";
import type { ContractRegister, RegisterField } from "@/lib/domain-api/register";

const api = vi.hoisted(() => ({ getContractRegister: vi.fn(), updateContractRegister: vi.fn() }));
vi.mock("@/lib/domain-api/register", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/register")>()),
  ...api,
}));
vi.mock("@/lib/domain-api/catalogs", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/catalogs")>()),
  listPartners: vi.fn().mockResolvedValue({ total: 0, items: [] }),
  listContractTypes: vi.fn().mockResolvedValue({ contract_types: [], contract_categories: [] }),
  listLookups: vi.fn().mockResolvedValue({ field_keys: [], items: [] }),
}));
vi.mock("@/lib/domain-api/ownership", () => ({ listOwnershipAssignees: vi.fn().mockResolvedValue({ items: [] }) }));
vi.mock("@/lib/domain-api/rules", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/rules")>()),
  getContractRules: vi.fn().mockResolvedValue({ items: [], status: "none", rule_count: 0 }),
}));
// Die Seite liest ?feld=… über den Router; im Test aus der echten Adresse.
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(window.location.search) }));
const auth = vi.hoisted(() => ({ role: "admin" }));
vi.mock("@/components/auth/AuthProvider", () => ({
  useAuth: () => ({ role: auth.role, account: { id: "u-1", is_developer: false }, organizationSlug: "test-klinik", loading: false }),
}));

function field(label: string, value: RegisterField["value"]): RegisterField {
  return { value, label, group: "identity", display: null, origin: null, source_field: null, extraction_id: null, ai_proposed_value: null, confirmed_by_name: null, confirmed_at: null, updated_by_name: null, updated_at: null };
}

function register(overrides: Partial<ContractRegister> = {}, termModel: string | null = "terminable"): ContractRegister {
  return {
    contract_id: "c-1", register_number: "000004", business_status: "in_arbeit", business_status_label: "In Arbeit",
    allowed_transitions: [{ target: "gueltig", label: "Gültig" }], supplier_text: null, has_ai_analysis: false, review_pending: false, ended_on: null,
    fields: {
      short_description: field("Kurzbeschreibung", "Wartung MRT"),
      partner_id: field("Vertragspartner", null),
      term_model: field("Vertragsart", termModel),
      term_start_date: field("Vertragsbeginn", null),
      notice_period_value: field("Kündigungsfrist", null),
      notice_period_unit: field("Kündigungsfrist (Einheit)", null),
      notice_to: field("Kündigung zum", null),
      retention_years_after_end: field("Löschen nach Ende (Jahre)", null),
    },
    terms: { status: "incomplete", earliest_end: null, cancel_by: null, possible_end: null, actual_end: null, reminder_date: null, missing: ["term_start_date", "notice_period_value"], explanation: [] },
    missing_for_valid: ["term_start_date", "partner_id"],
    as_of: "2026-10-11", partner_suggestions: [], type_suggestion: null, storage_location_label: null,
    retention: { years: null, source: null, contract_end: null, deletion_from: null },
    confidentiality: { is_confidential: false, type_confidential: false, effective: false, grants: [] },
    ...overrides,
  } as ContractRegister;
}

const hint = () => screen.getByText(/Für „Gültig“ fehlen noch:/).closest("p")!;

beforeEach(() => {
  vi.clearAllMocks();
  auth.role = "admin";
  window.history.replaceState(null, "", "/contracts/c-1?tab=register");
  api.getContractRegister.mockResolvedValue(register());
  api.updateContractRegister.mockImplementation(async () => register());
});

describe("Direkt zur Stelle: Ziele", () => {
  it("baut Links in die Vertragsakte und die Liste aus einem Ziel", () => {
    expect(baseFieldKey("notice_period_value")).toBe("notice_period");
    expect(baseFieldKey("term_start_date")).toBe("term_start_date");
    expect(contractHref("c-1", { tab: "register", field: "notice_period_unit" })).toBe("/contracts/c-1?tab=register&feld=notice_period");
    expect(contractHref("c-1", { tab: "documents", subtab: "review" })).toBe("/contracts/c-1?tab=documents&subtab=review");
    expect(contractHref("c-1", { tab: "finance", section: "entries" })).toBe("/contracts/c-1?tab=finance&abschnitt=entries");
    expect(contractHref("c-1", { tab: "overview" })).toBe("/contracts/c-1");
    expect(registerHref([{ column: "annual_cost", op: "empty" }], { ansicht: "review" })).toBe(`/register?ansicht=review&filter=${encodeURIComponent('[{"column":"annual_cost","op":"empty"}]')}`);
  });

  it("zeigt fehlende Angaben als Sprungziele mit verständlichem Namen", async () => {
    const onSelect = vi.fn();
    const { container } = render(<MissingList intro="Es fehlen:" items={[{ key: "a", label: "Vertragsbeginn", onSelect }, { key: "b", label: "Kosten", href: "/contracts/c-1?tab=finance" }, { key: "c", label: "Ohne Ziel" }]} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Vertragsbeginn erfassen" }));
    expect(onSelect).toHaveBeenCalled();
    expect(screen.getByRole("link", { name: "Kosten erfassen" })).toHaveAttribute("href", "/contracts/c-1?tab=finance");
    expect(container.querySelector("p")).toHaveTextContent("Es fehlen: Vertragsbeginn, Kosten, Ohne Ziel.");
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("Direkt zur Stelle: Vertragsdaten", () => {
  it("ein Klick auf „Vertragsbeginn“ öffnet die Bearbeitung und setzt den Cursor ins Feld", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Bearbeitungsstatus" });
    await user.click(within(hint()).getByRole("button", { name: "Vertragsbeginn erfassen" }));
    await waitFor(() => expect(document.getElementById("rg-term_start_date")).toHaveFocus());
    expect(screen.getByRole("button", { name: "Speichern" })).toBeInTheDocument();
    expect(document.getElementById("rg-field-term_start_date")).toHaveClass("rg-field--target");
    expect(window.location.search).toContain("feld=term_start_date");
    expect(await axe(container)).toHaveNoViolations();

    // Abbrechen beendet den Sprung und räumt die Adresse auf.
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(window.location.search).not.toContain("feld=");
  });

  it("Zeiträume: „Kündigungsfrist“ springt in das Anzahl-Feld", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Berechnete Fristen" });
    const terms = screen.getByText(/Fristen noch nicht berechenbar/).closest("p")!;
    await user.click(within(terms).getByRole("button", { name: "Kündigungsfrist erfassen" }));
    await waitFor(() => expect(document.getElementById("rg-notice_period")).toHaveFocus());
  });

  it("öffnet ein Ziel aus der Adresse (?feld=…) direkt", async () => {
    window.history.replaceState(null, "", "/contracts/c-1?tab=register&feld=partner_id");
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await waitFor(() => expect(document.getElementById("rg-partner_id")).toHaveFocus());
  });

  it("ohne Vertragsart führt „Vertragsbeginn“ zuerst zur Vertragsart", async () => {
    const user = userEvent.setup();
    api.getContractRegister.mockResolvedValue(register({}, null));
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Bearbeitungsstatus" });
    await user.click(within(hint()).getByRole("button", { name: "Vertragsbeginn erfassen" }));
    await waitFor(() => expect(document.getElementById("rg-term_model")).toHaveFocus());
    expect(screen.getByText("Erst die Vertragsart wählen – danach erscheint „Vertragsbeginn“.")).toBeInTheDocument();
  });

  it("eine offene Bearbeitung bleibt erhalten, wenn man zu einem anderen Feld springt", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Bearbeitungsstatus" });
    await user.click(within(hint()).getByRole("button", { name: "Vertragsbeginn erfassen" }));
    const start = await waitFor(() => { const el = document.getElementById("rg-term_start_date") as HTMLInputElement; expect(el).toHaveFocus(); return el; });
    await user.type(start, "2026-01-01");
    await user.click(within(hint()).getByRole("button", { name: "Vertragspartner erfassen" }));
    await waitFor(() => expect(document.getElementById("rg-partner_id")).toHaveFocus());
    expect((document.getElementById("rg-term_start_date") as HTMLInputElement).value).toBe("2026-01-01");
  });

  it("ohne Bearbeitungsrecht: springt zum Feld, hebt es hervor und sagt warum nichts zu bearbeiten ist", async () => {
    const user = userEvent.setup();
    auth.role = "viewer";
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByRole("heading", { name: "Bearbeitungsstatus" });
    await user.click(within(hint()).getByRole("button", { name: "Vertragsbeginn erfassen" }));
    await waitFor(() => expect(document.getElementById("rg-field-term_start_date")).toHaveFocus());
    expect(screen.queryByRole("button", { name: "Speichern" })).not.toBeInTheDocument();
    expect(screen.getByText("Nur Lesen – Änderungen über das Vertragsmanagement.")).toBeInTheDocument();
  });

  it("leere Felder haben für Bearbeitende ein „Erfassen“ direkt am Feld", async () => {
    const user = userEvent.setup();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const row = await waitFor(() => { const el = document.getElementById("rg-field-retention_years_after_end")!; expect(el).toBeTruthy(); return el; });
    await user.click(within(row).getByRole("button", { name: "Löschen nach Ende (Jahre) erfassen" }));
    await waitFor(() => expect(document.getElementById("rg-retention_years_after_end")).toHaveFocus());
  });
});

describe("Im Dokument suchen (erneute Erfassung)", () => {
  it("steht nur an leeren, im Dokument suchbaren Feldern und meldet das Feld", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" searchableKeys={new Set(["term_start_date", "notice_period"])} onSearchInDocument={onSearch} />);
    await user.click(await screen.findByRole("button", { name: "Vertragsbeginn im Dokument suchen" }));
    expect(onSearch).toHaveBeenCalledWith("term_start_date");
    expect(screen.getByRole("button", { name: "Kündigungsfrist im Dokument suchen" })).toBeInTheDocument();
    // Nicht suchbar (keine Angabe im Dokument dafür) oder schon gefüllt: kein Knopf.
    expect(screen.queryByRole("button", { name: "Vertragspartner im Dokument suchen" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kurzbeschreibung im Dokument suchen" })).not.toBeInTheDocument();
    expect(documentSearchHref("c-1", "notice_period_value")).toBe("/contracts/c-1?tab=documents&subtab=document&abschnitt=reextraction&suchen=notice_period");
  });

  it("ein aus dem Dokument übernommener Wert zeigt seine Fundstelle", async () => {
    const user = userEvent.setup();
    const onShowSource = vi.fn();
    const source = { document_version_id: "dv-1", page: 4, quote: "beginnt am 01.01.2025" };
    const base = register();
    api.getContractRegister.mockResolvedValue(register({
      fields: { ...base.fields, term_start_date: { ...field("Vertragsbeginn", "2025-01-01"), origin: "manual", document_source: source } },
    }));
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" onShowSource={onShowSource} />);
    const link = await screen.findByRole("button", { name: "Fundstelle von Vertragsbeginn: Seite 4" });
    expect(link).toHaveAttribute("title", "„beginnt am 01.01.2025“");
    await user.click(link);
    expect(onShowSource).toHaveBeenCalledWith(source);
  });

  it("zeigt den Bearbeitungsstatus in seiner Farbe wie in der Vertragsliste (Gültig = grün)", async () => {
    api.getContractRegister.mockResolvedValue(register({ business_status: "gueltig", business_status_label: "Gültig", allowed_transitions: [] }));
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" />);
    const badge = (await screen.findAllByText("Gültig")).map((node) => node.closest(".status-badge")).find(Boolean);
    expect(badge).toHaveClass("status-badge--success");
  });

  it("ohne Bearbeitungsrecht gibt es den Knopf nicht", async () => {
    auth.role = "viewer";
    render(<ContractRegisterPanel contractId="c-1" orgSlug="test-klinik" searchableKeys={new Set(["term_start_date"])} onSearchInDocument={vi.fn()} />);
    await screen.findAllByText("Vertragsbeginn");
    expect(screen.queryByRole("button", { name: /im Dokument suchen/ })).not.toBeInTheDocument();
  });
});

