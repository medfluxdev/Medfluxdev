import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractTimeline, { type EndCheck } from "@/components/contracts/detail/ContractTimeline";
import type { DetailWorkItem } from "@/lib/contract-detail-types";
import type { DeadlineDto } from "@/lib/domain-api/deadlines";

const api = vi.hoisted(() => ({
  listContractDeadlines: vi.fn(),
  createContractDeadline: vi.fn(),
  deadlineAction: vi.fn(),
  updateDeadline: vi.fn(),
  getContractRegister: vi.fn(),
}));

vi.mock("@/lib/domain-api/deadlines", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/deadlines")>()),
  listContractDeadlines: api.listContractDeadlines,
  createContractDeadline: api.createContractDeadline,
  deadlineAction: api.deadlineAction,
  updateDeadline: api.updateDeadline,
}));
vi.mock("@/lib/domain-api/register", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/register")>()),
  getContractRegister: api.getContractRegister,
}));
vi.mock("@/lib/domain-api/catalogs", () => ({ listLookups: vi.fn().mockResolvedValue({ field_keys: [], items: [] }) }));
vi.mock("@/lib/domain-api/ownership", () => ({ listOwnershipAssignees: vi.fn().mockResolvedValue({ items: [] }) }));

function deadline(overrides: Partial<DeadlineDto> = {}): DeadlineDto {
  return {
    id: "d-end", contract_id: "c-1", contract_label: null, source: "system", system_key: "contract_end",
    kind: "vertragsende", title: "Vertragsende (feste Laufzeit)", due_date: "2029-03-31", remind_on: "2028-11-30", days_until_due: 900,
    overdue: false, assignee_account_id: "u-1", assignee_name: "Ahmad", escalation_account_id: null, escalation_name: null,
    todo_text: null, note: null, status: "open", send_email: true, send_ics: false, done_by_name: null,
    done_at: null, basis_unconfirmed: false, editable_fields: [], ...overrides,
  };
}

const WORK: DetailWorkItem = {
  work_item_id: "w-1", item_type: "missing_cost", severity: "medium", status: "open", title_de: "Kosten fehlen",
  why_de: "Keine Finanzeinträge", action_hint_de: null, target_date: "2026-09-01", days_remaining: -20,
  requires_review: false, source_warning_id: null, contract_equipment_id: null, equipment_id: null,
};

function endCheck(overrides: Partial<EndCheck> = {}): EndCheck {
  return { documented: null, maintained: "2029-03-31", fixedTerm: true, onAdopt: vi.fn().mockResolvedValue(undefined), onKeep: vi.fn().mockResolvedValue(undefined), ...overrides };
}

const rowTexts = (list: HTMLElement) => within(list).getAllByRole("listitem").map((item) => item.textContent ?? "");

describe("Termine & Aufgaben", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listContractDeadlines.mockResolvedValue({ items: [
      deadline(),
      deadline({ id: "d-ret", system_key: "retention_review", kind: "loeschpruefung", title: "Löschprüfung (Aufbewahrungsfrist abgelaufen)", due_date: "2040-01-01", remind_on: "2040-01-01", assignee_name: null }),
      deadline({ id: "d-old", source: "manual", system_key: null, title: "Rückfrage beim Partner", status: "cancelled", due_date: "2025-08-20" }),
    ] });
    api.getContractRegister.mockResolvedValue({ as_of: "2026-10-13", terms: { reminder_dates: ["2028-11-30", "2029-01-06"] } });
    api.deadlineAction.mockResolvedValue({ items: [] });
  });

  it("ordnet offen → Vergangenes → Heute → Kommendes; Erinnerungen als eigene Zeilen; ohne Verstöße (axe)", async () => {
    const { container } = render(<ContractTimeline contractId="c-1" orgSlug="test-klinik" workItems={[WORK]} endCheck={endCheck()} onOpenTarget={vi.fn()} />);
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    const rows = rowTexts(list);
    expect(rows[0]).toMatch(/^offen.*KI-Prüfung.*Abweichung beim Vertragsende prüfen/);
    expect(rows[1]).toMatch(/^01\.09\.2026.*Aufgabe.*Kosten fehlen/);
    expect(rows[2]).toMatch(/^Heute.*13\.10\.2026/);
    expect(rows[3]).toMatch(/^30\.11\.2028.*Erinnerung.*Vertragsende/);
    expect(rows[4]).toMatch(/^06\.01\.2029.*Erinnerung/);
    expect(rows[5]).toMatch(/^31\.03\.2029.*Frist.*Vertragsende.*Feste Laufzeit, endet ohne Kündigung/);
    expect(rows[6]).toMatch(/^01\.01\.2040.*Löschprüfung/);
    expect(screen.getByText("Erledigte und abgebrochene (1)")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Erledigte und abgebrochene" })).getByText("Abgebrochen")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("„Prüfen“ öffnet den Vergleich; ohne Dokumentwert nur „Beibehalten“", async () => {
    const user = userEvent.setup();
    const check = endCheck();
    render(<ContractTimeline contractId="c-1" orgSlug="test-klinik" workItems={[]} endCheck={check} onOpenTarget={vi.fn()} />);
    const button = await screen.findByRole("button", { name: "Prüfen" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    await user.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    const compare = document.getElementById("tl-compare")!;
    expect(within(compare).getByText("Im Dokument").nextElementSibling).toHaveTextContent("–");
    expect(within(compare).getByText("In den Vertragsdaten").nextElementSibling).toHaveTextContent("31.03.2029");
    expect(within(compare).queryByRole("button", { name: "Übernehmen" })).not.toBeInTheDocument();
    await user.click(within(compare).getByRole("button", { name: "Beibehalten" }));
    expect(check.onKeep).toHaveBeenCalled();
    await waitFor(() => expect(document.getElementById("tl-compare")).toBeNull());
  });

  it("mit abweichendem Dokumentwert: „Übernehmen“ nimmt den Wert aus dem Dokument", async () => {
    const user = userEvent.setup();
    const check = endCheck({ documented: "2029-05-04", onShowSource: vi.fn() });
    render(<ContractTimeline contractId="c-1" orgSlug="test-klinik" workItems={[]} endCheck={check} onOpenTarget={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Prüfen" }));
    await user.click(screen.getByRole("button", { name: "Quelle" }));
    expect(check.onShowSource).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Übernehmen" }));
    expect(check.onAdopt).toHaveBeenCalled();
  });

  it("„Erledigt“ schließt einen Termin", async () => {
    const user = userEvent.setup();
    render(<ContractTimeline contractId="c-1" orgSlug="test-klinik" workItems={[]} onOpenTarget={vi.fn()} />);
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    const row = within(list).getAllByRole("listitem").find((item) => item.textContent?.startsWith("31.03.2029"))!;
    await user.click(within(row).getByRole("button", { name: "Erledigt" }));
    expect(api.deadlineAction).toHaveBeenCalledWith("test-klinik", "d-end", "done");
  });

  it("„Kalender an“ schaltet die Kalendereinladung je Termin", async () => {
    const user = userEvent.setup();
    api.updateDeadline.mockResolvedValue({ items: [] });
    render(<ContractTimeline contractId="c-1" orgSlug="test-klinik" workItems={[]} onOpenTarget={vi.fn()} />);
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    const row = within(list).getAllByRole("listitem").find((item) => item.textContent?.startsWith("31.03.2029"))!;
    const toggle = within(row).getByRole("button", { name: "Kalender an" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(api.updateDeadline).toHaveBeenCalledWith("test-klinik", "d-end", { send_ics: true });
  });

  it("leer nur, wenn es gar nichts gibt – mit Link zu den Vertragsdaten", async () => {
    const user = userEvent.setup();
    const onOpenTarget = vi.fn();
    api.listContractDeadlines.mockResolvedValue({ items: [] });
    render(<ContractTimeline contractId="c-1" orgSlug="test-klinik" workItems={[]} onOpenTarget={onOpenTarget} />);
    expect(await screen.findByText("Keine Termine. Sie entstehen automatisch aus den Vertragsdaten.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Vertragsdaten öffnen" }));
    expect(onOpenTarget).toHaveBeenCalledWith({ tab: "register", section: "term" });
  });
});
