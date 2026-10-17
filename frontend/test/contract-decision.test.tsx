import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDecisionCard, { pendingDecision, deadlineSignal, followUpDue } from "@/components/contracts/detail/ContractDecisionCard";
import RenewalOverview from "@/components/deadlines/RenewalOverview";
import type { ContractLifecycleDecision, DecisionStep } from "@/lib/domain-api/lifecycle";
import type { RenewalBrief } from "@/lib/domain-api/registerGrid";

const api = vi.hoisted(() => ({
  getRenewalBrief: vi.fn(),
  listRenewals: vi.fn(),
  getContractLifecycle: vi.fn(),
  createContractLifecycleDecision: vi.fn(),
  updateContractLifecycleDecision: vi.fn(),
  deleteContractLifecycleDecision: vi.fn(),
  updateDecisionStep: vi.fn(),
}));

vi.mock("@/lib/domain-api/registerGrid", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/registerGrid")>()),
  getRenewalBrief: api.getRenewalBrief,
  listRenewals: api.listRenewals,
}));
vi.mock("@/lib/domain-api/lifecycle", () => ({
  getContractLifecycle: api.getContractLifecycle,
  createContractLifecycleDecision: api.createContractLifecycleDecision,
  updateContractLifecycleDecision: api.updateContractLifecycleDecision,
  deleteContractLifecycleDecision: api.deleteContractLifecycleDecision,
  updateDecisionStep: api.updateDecisionStep,
}));


function brief(overrides: Partial<RenewalBrief> = {}): RenewalBrief {
  return {
    contract_id: "c-1", register_number: "000001", short_description: "Wartung CT", business_status: "gueltig",
    term_model: "Automatische Verlängerung", as_of: "2026-08-15", urgency: "soon", days_left: 46,
    cancel_by: "2026-09-30", current_end: "2026-12-31", next_end_if_no_action: "2027-12-31",
    if_no_action: "Ohne Kündigung bis 30.09.2026 verlängert sich der Vertrag um 1 Jahr bis 31.12.2027.",
    annual_cost: "12000.00", renewal_cost: "12360.00", price_adjustment_notes: [], partner: "MEDTEC",
    partner_contracts: [{ contract_id: "c-2", register_number: "000002", short_description: "Wartung MRT" }],
    responsible: "Admin", reminder_recipient: null, documents: 1, review_pending: false, open_deadlines: [],
    decision: null,
    hints: [{ kind: "info", text: "Bei Verlängerung entstehen bis 31.12.2027 voraussichtlich 12.360,00 € (netto).", reason: "Hochrechnung." }],
    explanation: [],
    ...overrides,
  };
}

const SAVED: ContractLifecycleDecision = {
  id: "l-1", contract_id: "c-1", decision: "terminate", status: "planned", effective_date: "2026-12-31",
  note: "Neues Angebot", actor_display_name: "Ahmad", created_at: "2026-08-15T10:00:00Z", updated_at: null,
};

describe("Entscheidung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRenewalBrief.mockResolvedValue(brief());
    api.getContractLifecycle.mockReset().mockResolvedValueOnce({ items: [] }).mockResolvedValue({ items: [SAVED] });
    api.createContractLifecycleDecision.mockResolvedValue(SAVED);
  });

  it("zeigt Kennzahlen, „Ohne Handeln“ und Hinweise; ohne Verstöße (axe)", async () => {
    const { container } = render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("Frist in 46 Tagen")).toBeInTheDocument();
    const kpi = (label: string) => screen.getByText(label, { selector: "dt" }).nextElementSibling;
    expect(kpi("Kündbar bis")).toHaveTextContent("30.09.2026");
    expect(kpi("Vertragsende")).toHaveTextContent("31.12.2026");
    expect(kpi("Kosten bei Verlängerung")).toHaveTextContent(/12\.360,00/);
    expect(screen.getByText(/verlängert sich der Vertrag um 1 Jahr/)).toBeInTheDocument();
    expect(screen.getByText("Grundlage: Hochrechnung.")).toBeInTheDocument();
    expect(screen.getByText("Weitere Verträge mit MEDTEC (1)")).toBeInTheDocument();
    expect(screen.getByText("Noch keine Entscheidung erfasst.")).toBeInTheDocument();
    // Keine KI-Kurzfassung in der Entscheidung (entfernt 2026-10-16).
    expect(screen.queryByRole("button", { name: /Kurzfassung/ })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Status im Kopf: keine Frist, Frist bald, Frist überschritten", () => {
    expect(deadlineSignal({ urgency: "none", days_left: null })).toEqual({ tone: "neutral", label: "Keine offene Frist" });
    expect(deadlineSignal({ urgency: "planned", days_left: 200 })).toEqual({ tone: "neutral", label: "Frist in 200 Tagen" });
    expect(deadlineSignal({ urgency: "critical", days_left: 20 })).toEqual({ tone: "warning", label: "Frist in 20 Tagen" });
    expect(deadlineSignal({ urgency: "missed", days_left: -3 })).toEqual({ tone: "critical", label: "Frist überschritten" });
  });

  it("feste Laufzeit: „Keine Kündigungsfrist – Vertrag endet am …“; ohne „Kündbar bis“ und Verlängerungskosten", async () => {
    api.getRenewalBrief.mockResolvedValue(brief({ urgency: "none", days_left: null, cancel_by: null, current_end: "2099-12-31", renewal_cost: null, hints: [], partner_contracts: [] }));
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("Keine Kündigungsfrist – Vertrag endet am 31.12.2099")).toBeInTheDocument();
    expect(screen.queryByText("Kündbar bis", { selector: "dt" })).not.toBeInTheDocument();
    expect(screen.queryByText("Kosten bei Verlängerung", { selector: "dt" })).not.toBeInTheDocument();
  });

  it("Knopf öffnet das Formular darunter, erneuter Klick schließt; Speichern zeigt die Entscheidung in der Liste", async () => {
    const user = userEvent.setup();
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    const group = await screen.findByRole("group", { name: "Entscheidung" });
    const terminate = within(group).getByRole("button", { name: "Kündigen" });
    expect(terminate).toHaveAttribute("aria-pressed", "false");
    await user.click(terminate);
    expect(terminate).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Wirksam am")).toHaveValue("2026-12-31");
    await user.click(terminate);
    expect(screen.queryByLabelText("Wirksam am")).not.toBeInTheDocument();
    await user.click(within(group).getByRole("button", { name: "Beobachten" }));
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(screen.queryByLabelText("Notiz")).not.toBeInTheDocument();

    await user.click(terminate);
    await user.type(screen.getByLabelText("Notiz"), "Neues Angebot");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));
    // Entscheidung und Erinnerung in einem Schritt: der passende Termin wird mit angelegt und verknüpft.
    await waitFor(() => expect(api.createContractLifecycleDecision).toHaveBeenCalledWith("test-klinik", "c-1", {
      decision: "terminate", status: "planned", effective_date: "2026-12-31", note: "Neues Angebot",
      reminder: expect.objectContaining({ title: "Kündigung versenden", kind: "kuendigungsfrist", due_date: "2026-12-31" }),
    }));
    const list = await screen.findByRole("list", { name: "Bisherige Entscheidungen" });
    expect(within(list).getByText("Kündigen")).toBeInTheDocument();
    expect(within(list).getByText("wirksam am 31.12.2026 · Neues Angebot")).toBeInTheDocument();
    expect(within(list).getByText("Ahmad")).toBeInTheDocument();
    expect(screen.queryByLabelText("Wirksam am")).not.toBeInTheDocument();
    // Nach „Kündigen“: Hinweis auf den Statuswechsel, der die Kündigung dokumentiert.
    expect(screen.getByRole("link", { name: "Status auf „Gekündigt“ setzen" })).toHaveAttribute("href", "/contracts/c-1?abschnitt=status");
  });
});

describe("Entscheidung mit Erinnerung", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRenewalBrief.mockResolvedValue(brief());
    api.getContractLifecycle.mockResolvedValue({ items: [] });
    api.createContractLifecycleDecision.mockResolvedValue(SAVED);
  });

  it("Fälligkeit: Kündigungsfrist, sonst Wirksamkeit, nie vergangen; Beobachten in 3 Monaten", () => {
    const b = { cancel_by: "2026-09-30", current_end: "2026-12-31" };
    expect(followUpDue("terminate", b, "2026-12-31", "2026-08-15")).toBe("2026-09-30");
    expect(followUpDue("terminate", b, "2026-12-31", "2026-10-14")).toBe("2026-12-31");
    expect(followUpDue("renew", { cancel_by: null, current_end: "2026-12-31" }, "", "2026-10-14")).toBe("2026-12-31");
    expect(followUpDue("monitor", b, "2026-12-31", "2026-10-14")).toBe("2027-01-14");
    expect(followUpDue("renegotiate", { cancel_by: null, current_end: null }, "", "2026-10-14")).toBe("2026-10-21");
  });

  it("Erinnerung ist vorausgefüllt, änderbar und abwählbar", async () => {
    const user = userEvent.setup();
    const onReminderCreated = vi.fn();
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" onReminderCreated={onReminderCreated} />);
    const group = await screen.findByRole("group", { name: "Entscheidung" });
    await user.click(within(group).getByRole("button", { name: "Beobachten" }));
    expect(screen.getByLabelText("Erinnerung anlegen")).toBeChecked();
    expect(screen.getByLabelText("Termin")).toHaveValue("Entscheidung erneut prüfen");
    await user.clear(screen.getByLabelText("Fällig am"));
    await user.type(screen.getByLabelText("Fällig am"), "2027-02-01");
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));
    await waitFor(() => expect(api.createContractLifecycleDecision).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({
      reminder: expect.objectContaining({ title: "Entscheidung erneut prüfen", due_date: "2027-02-01", kind: "pruefung" }),
    })));
    expect(onReminderCreated).toHaveBeenCalled();

    // Ohne Erinnerung: nur die Entscheidung (ein doppelter gleicher Termin wird im Backend wiederverwendet).
    await user.click(within(group).getByRole("button", { name: "Verlängern" }));
    await user.click(screen.getByLabelText("Erinnerung anlegen"));
    expect(screen.queryByLabelText("Fällig am")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Entscheidung speichern" }));
    await waitFor(() => expect(api.createContractLifecycleDecision).toHaveBeenCalledTimes(2));
    expect(api.createContractLifecycleDecision).toHaveBeenLastCalledWith("test-klinik", "c-1", { decision: "renew", status: "planned", effective_date: "2026-12-31", note: null });
  });
});

describe("Bisherige Entscheidungen ändern und löschen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRenewalBrief.mockResolvedValue(brief());
    api.getContractLifecycle.mockReset().mockResolvedValue({ items: [SAVED] });
  });

  it("Bearbeiten ändert Entscheidung, Datum und Notiz", async () => {
    const user = userEvent.setup();
    api.updateContractLifecycleDecision.mockResolvedValue({ ...SAVED, decision: "renegotiate", note: "Neu verhandeln" });
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    await user.click(await screen.findByRole("button", { name: "Kündigen vom 15.08.2026 bearbeiten" }));
    const form = screen.getByRole("form", { name: "Entscheidung vom 15.08.2026 bearbeiten" });
    await user.selectOptions(within(form).getByLabelText("Entscheidung"), "renegotiate");
    await user.clear(within(form).getByLabelText("Notiz"));
    await user.type(within(form).getByLabelText("Notiz"), "Neu verhandeln");
    await user.click(within(form).getByRole("button", { name: "Änderung speichern" }));
    await waitFor(() => expect(api.updateContractLifecycleDecision).toHaveBeenCalledWith("test-klinik", "c-1", "l-1", { decision: "renegotiate", status: "planned", effective_date: "2026-12-31", note: "Neu verhandeln" }));
    const list = screen.getByRole("list", { name: "Bisherige Entscheidungen" });
    expect(within(list).getByText("wirksam am 31.12.2026 · Neu verhandeln")).toBeInTheDocument();
  });

  it("Bearbeiten ändert auch die verknüpfte Erinnerung oder entfernt sie", async () => {
    const user = userEvent.setup();
    const withReminder = { ...SAVED, reminder: { id: "d-1", title: "Kündigung versenden", due_date: "2026-09-30", status: "open" as const } };
    api.getContractLifecycle.mockReset().mockResolvedValue({ items: [withReminder] });
    api.updateContractLifecycleDecision.mockResolvedValue(withReminder);
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    const list = await screen.findByRole("list", { name: "Bisherige Entscheidungen" });
    expect(within(list).getByText(/Erinnerung am 30\.09\.2026/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kündigen vom 15.08.2026 bearbeiten" }));
    const form = screen.getByRole("form", { name: "Entscheidung vom 15.08.2026 bearbeiten" });
    expect(within(form).getByLabelText("Termin")).toHaveValue("Kündigung versenden");
    await user.selectOptions(within(form).getByLabelText("Entscheidung"), "renegotiate");
    expect(within(form).getByLabelText("Termin")).toHaveValue("Neu verhandeln");
    await user.clear(within(form).getByLabelText("Fällig am"));
    await user.type(within(form).getByLabelText("Fällig am"), "2026-09-15");
    await user.click(within(form).getByRole("button", { name: "Änderung speichern" }));
    await waitFor(() => expect(api.updateContractLifecycleDecision).toHaveBeenCalledWith("test-klinik", "c-1", "l-1", expect.objectContaining({
      decision: "renegotiate", reminder: expect.objectContaining({ title: "Neu verhandeln", due_date: "2026-09-15" }),
    })));

    await user.click(screen.getByRole("button", { name: "Kündigen vom 15.08.2026 bearbeiten" }));
    await user.click(screen.getByLabelText("Erinnerung"));
    expect(screen.getByText("Die Erinnerung wird beim Speichern entfernt.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Änderung speichern" }));
    await waitFor(() => expect(api.updateContractLifecycleDecision).toHaveBeenLastCalledWith("test-klinik", "c-1", "l-1", expect.objectContaining({ remove_reminder: true })));
  });

  it("Löschen erst nach Bestätigung", async () => {
    const user = userEvent.setup();
    api.deleteContractLifecycleDecision.mockResolvedValue({ deleted: true, id: "l-1" });
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    await user.click(await screen.findByRole("button", { name: "Kündigen vom 15.08.2026 löschen" }));
    expect(api.deleteContractLifecycleDecision).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    await user.click(screen.getByRole("button", { name: "Kündigen vom 15.08.2026 löschen" }));
    await user.click(screen.getByRole("button", { name: "Endgültig löschen" }));
    await waitFor(() => expect(api.deleteContractLifecycleDecision).toHaveBeenCalledWith("test-klinik", "c-1", "l-1"));
    expect(await screen.findByText("Noch keine Entscheidung erfasst.")).toBeInTheDocument();
  });
});

describe("Kündigungsentscheidungen", () => {
  it("listet anstehende Fristen mit offenem Entscheidungsstand", async () => {
    api.listRenewals.mockResolvedValue({ as_of: "2026-08-15", days: 120, items: [
      { contract_id: "c-1", register_number: "000001", short_description: "Wartung CT", partner: "MEDTEC", cancel_by: "2026-09-30", days_left: 46, urgency: "soon", possible_end: "2026-12-31", annual_cost: "12000.00", responsible: "Admin", decision: null },
    ] });
    const user = userEvent.setup();
    render(<RenewalOverview organizationSlug="test-klinik" />);
    const row = (await screen.findByRole("rowheader", { name: /000001/ })).closest("tr")!;
    expect(within(row).getByText("offen")).toBeInTheDocument();
    expect(screen.getByText("1 Verträge · 1 ohne erfasste Entscheidung")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Zeitraum"), "365");
    await waitFor(() => expect(api.listRenewals).toHaveBeenLastCalledWith("test-klinik", 365));
  });
});

describe("Entscheidung – noch nicht entschieden", () => {
  it("zeigt den offenen Zustand mit Frist; pendingDecision nur für laufende Verträge ohne Entscheidung", async () => {
    vi.clearAllMocks();
    api.getRenewalBrief.mockResolvedValue(brief());
    api.getContractLifecycle.mockReset().mockResolvedValue({ items: [] });
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("Noch nicht entschieden")).toBeInTheDocument();
    expect(screen.getByText("Entscheidung offen")).toBeInTheDocument();
    expect(screen.getByText("Bis 30.09.2026 entscheiden (Kündbar bis)")).toBeInTheDocument();
    // Jede Entscheidung trägt ihre Kennfarbe.
    const group = screen.getByRole("group", { name: "Entscheidung" });
    expect(within(group).getByRole("button", { name: "Kündigen" })).toHaveClass("dec-kind--terminate");
    expect(within(group).getByRole("button", { name: "Verlängern" })).toHaveClass("dec-kind--renew");

    expect(pendingDecision(brief())).toEqual({ due: "2026-09-30", byCancel: true, urgency: "soon" });
    expect(pendingDecision(brief({ cancel_by: null }))).toEqual({ due: "2026-12-31", byCancel: false, urgency: "soon" });
    expect(pendingDecision(brief({ business_status: "gekuendigt" }))).toBeNull();
    expect(pendingDecision(brief({ decision: { id: "l-1", decision: "renew", label: "Verlängern", status: "planned", note: null, by: "Ahmad", at: null } }))).toBeNull();
    // Abgeschlossen = umgesetzt: für den nächsten Termin ist wieder zu entscheiden (wie auf der Karte).
    expect(pendingDecision(brief({ decision: { id: "l-1", decision: "renew", label: "Verlängern", status: "completed", note: null, by: "Ahmad", at: null } }))).toEqual({ due: "2026-09-30", byCancel: true, urgency: "soon" });
  });
});

describe("Entscheidung – Umsetzung", () => {
  const step = (key: string, title: string, extra: Partial<DecisionStep> = {}): DecisionStep => ({
    key, title, detail: `${title} – so geht es.`, due: null, done: false, done_how: null, done_by: null, done_at: null, target: null, ...extra,
  });
  const steps = [
    step("send", "Kündigung an MEDTEC senden", { due: "2026-08-20" }),
    step("status", "Status auf „Gekündigt“ setzen", { target: { tab: "register", section: "status" } }),
    step("confirmation", "Kündigungsbestätigung ablegen", { done: true, done_how: "auto" }),
  ];
  const decision = (items: DecisionStep[]): ContractLifecycleDecision => ({ ...SAVED, steps: items });

  it("zeigt Schritte mit Fortschritt, „Als Nächstes“, Fälligkeit und Sprung zur Stelle; Haken speichert", async () => {
    const user = userEvent.setup();
    vi.clearAllMocks();
    api.getRenewalBrief.mockResolvedValue(brief());
    api.getContractLifecycle.mockReset().mockResolvedValue({ items: [decision(steps)] });
    api.updateDecisionStep.mockResolvedValue({ ...decision([{ ...steps[0], done: true, done_how: "manual", done_by: "Ahmad", done_at: "2026-08-15T10:00:00Z" }, steps[1], steps[2]]), status: "in_progress" });
    const onDecisionChanged = vi.fn();
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" onDecisionChanged={onDecisionChanged} />);
    const plan = (await screen.findByRole("heading", { name: "Umsetzung: Kündigen" })).closest("section")!;
    expect(within(plan).getByText("1 von 3 erledigt")).toBeInTheDocument();
    const rows = within(plan).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Als Nächstes");
    expect(rows[0]).toHaveTextContent("bis 20.08.2026 · noch 5 Tage");
    expect(within(rows[1]).getByRole("link", { name: "Status setzen →" })).toHaveAttribute("href", "/contracts/c-1?abschnitt=status");
    expect(rows[2]).toHaveTextContent("Erledigt – aus den Vertragsdaten erkannt.");
    expect(within(rows[2]).getByRole("checkbox")).toBeDisabled();

    await user.click(within(rows[0]).getByRole("checkbox", { name: "Kündigung an MEDTEC senden: offen" }));
    expect(api.updateDecisionStep).toHaveBeenCalledWith("test-klinik", "c-1", "l-1", "send", true);
    expect(await within(plan).findByText("2 von 3 erledigt")).toBeInTheDocument();
    expect(within(plan).getByText("Erledigt von Ahmad am 15.08.2026.")).toBeInTheDocument();
    expect(onDecisionChanged).toHaveBeenCalled();
    expect(within(plan).getByRole("button", { name: "Ohne alle Schritte abschließen" })).toBeInTheDocument();
  });

  it("alles erledigt: „Entscheidung abschließen“; „Entscheidung ändern“ als Schritt öffnet die Auswahl", async () => {
    const user = userEvent.setup();
    vi.clearAllMocks();
    api.getRenewalBrief.mockResolvedValue(brief());
    api.getContractLifecycle.mockReset().mockResolvedValue({ items: [
      { ...SAVED, decision: "monitor", steps: [step("watch", "Wiedervorlage festlegen", { done: true, done_how: "auto" }), step("decide", "Erneut entscheiden", { target: { action: "change_decision" } })] },
    ] });
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    const plan = (await screen.findByRole("heading", { name: "Umsetzung: Beobachten" })).closest("section")!;
    await user.click(within(plan).getByRole("button", { name: "Entscheidung ändern" }));
    expect(screen.getByRole("group", { name: "Neue Entscheidung" })).toBeInTheDocument();

    api.getContractLifecycle.mockReset().mockResolvedValue({ items: [decision(steps.map((item) => ({ ...item, done: true, done_how: "auto" as const })))] });
    render(<ContractDecisionCard contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByRole("button", { name: "Entscheidung abschließen" })).toBeInTheDocument();
    expect(screen.getByText("Alle Schritte erledigt")).toBeInTheDocument();
  });
});
