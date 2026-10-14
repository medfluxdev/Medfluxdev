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
  downloadIcs: vi.fn(),
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
vi.mock("@/lib/ics", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/ics")>()),
  downloadIcs: api.downloadIcs,
}));
vi.mock("@/lib/domain-api/catalogs", () => ({ listLookups: vi.fn().mockResolvedValue({ field_keys: [], items: [] }) }));
vi.mock("@/lib/domain-api/ownership", () => ({ listOwnershipAssignees: vi.fn().mockResolvedValue({ items: [{ id: "u-2", display_name: "Tom Weber" }] }) }));

function deadline(overrides: Partial<DeadlineDto> = {}): DeadlineDto {
  return {
    id: "d-end", contract_id: "c-1", contract_label: null, source: "system", system_key: "contract_end",
    kind: "vertragsende", title: "Vertragsende (feste Laufzeit)", due_date: "2029-03-31", remind_on: "2028-11-30", days_until_due: 900,
    overdue: false, assignee_account_id: "u-1", assignee_name: "Ahmad", escalation_account_id: null, escalation_name: null,
    todo_text: null, note: null, status: "open", send_email: true, send_ics: false, done_by_name: null,
    done_at: null, basis_unconfirmed: false, editable_fields: ["note", "send_email", "send_ics"], ...overrides,
  };
}

const MANUAL_FIELDS = ["kind", "title", "due_date", "remind_on", "assignee_account_id", "escalation_account_id", "todo_text", "note", "send_email", "send_ics"];
const task = (overrides: Partial<DeadlineDto> = {}) => deadline({ id: "d-task", source: "manual", system_key: null, kind: "pruefung", title: "Verlängerung umsetzen", due_date: "2026-12-10", remind_on: "2026-12-10", assignee_account_id: "user-test", assignee_name: "Test Admin", todo_text: "Ergebnis dokumentieren", editable_fields: MANUAL_FIELDS, ...overrides });

const WORK: DetailWorkItem = {
  work_item_id: "w-1", item_type: "missing_cost", severity: "medium", status: "open", title_de: "Kosten fehlen",
  why_de: "Keine Finanzeinträge", action_hint_de: null, target_date: "2026-09-01", days_remaining: -20,
  requires_review: false, source_warning_id: null, contract_equipment_id: null, equipment_id: null,
};

function endCheck(overrides: Partial<EndCheck> = {}): EndCheck {
  return { documented: null, maintained: "2029-03-31", fixedTerm: true, onAdopt: vi.fn().mockResolvedValue(undefined), onKeep: vi.fn().mockResolvedValue(undefined), ...overrides };
}

const rowTexts = (list: HTMLElement) => within(list).getAllByRole("listitem").map((item) => item.textContent ?? "");
const rowStarting = (list: HTMLElement, text: string) => within(list).getAllByRole("listitem").find((item) => item.textContent?.startsWith(text))!;

function renderTimeline(props: Partial<Parameters<typeof ContractTimeline>[0]> = {}) {
  return render(<ContractTimeline contractId="c-1" orgSlug="test-klinik" workItems={[]} onOpenTarget={vi.fn()} {...props} />);
}

describe("Termine & Aufgaben", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listContractDeadlines.mockResolvedValue({ items: [
      deadline(),
      deadline({ id: "d-ret", system_key: "retention_review", kind: "loeschpruefung", title: "Löschprüfung (Aufbewahrungsfrist abgelaufen)", due_date: "2040-01-01", remind_on: "2040-01-01", assignee_name: null, assignee_account_id: null }),
      deadline({ id: "d-old", source: "manual", system_key: null, title: "Rückfrage beim Partner", status: "cancelled", due_date: "2025-08-20", done_by_name: "Ahmad", done_at: "2025-08-21T10:00:00Z" }),
      deadline({ id: "d-auto", source: "system", system_key: "set_ended", title: "Vertrag auf „Beendet“ setzen", status: "cancelled", due_date: "2026-01-02", note: "Automatisch entfernt: Die Grundlage der Frist hat sich geändert." }),
    ] });
    api.getContractRegister.mockResolvedValue({ as_of: "2026-10-13", terms: { reminder_dates: ["2028-11-30", "2029-03-03"] }, fields: { reminder_todo: { value: "Verlängerung prüfen" } } });
    api.deadlineAction.mockResolvedValue({ items: [] });
    api.updateDeadline.mockResolvedValue({ items: [] });
  });

  it("ordnet offen → Vergangenes → Heute → Kommendes mit Jahresgruppen; feste Spalten; ohne Verstöße (axe)", async () => {
    const { container } = renderTimeline({ workItems: [WORK], endCheck: endCheck() });
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    const rows = rowTexts(list);
    expect(rows[0]).toMatch(/^offen.*KI-Prüfung.*Abweichung beim Vertragsende prüfen/);
    expect(rows[1]).toMatch(/^01\.09\.2026.*überfällig · vor 6 Wochen.*Aufgabe.*Kosten fehlen/);
    expect(rows[2]).toMatch(/^Heute · 13\.10\.2026/);
    expect(rows[3]).toMatch(/^30\.11\.2028.*4 Monate vor Vertragsende.*Erinnerung.*Verlängerung prüfen.*Vertragsende 31\.03\.2029/);
    expect(rows[4]).toMatch(/^03\.03\.2029.*4 Wochen vor Vertragsende.*Erinnerung/);
    expect(rows[5]).toMatch(/^31\.03\.2029.*in 2 Jahren.*Frist.*Vertragsende.*Feste Laufzeit, endet ohne Kündigung/);
    expect(rows[6]).toMatch(/^01\.01\.2040.*Löschprüfung/);
    // Jahresüberschriften (dekorativ) bei jedem Jahreswechsel.
    expect([...list.querySelectorAll(".tl-year")].map((item) => item.textContent)).toEqual(["2026", "2028", "2029", "2040"]);
    // Jede Zeile hat dieselben sechs Spalten.
    for (const row of list.querySelectorAll(".tl-row:not(.tl-row--today)")) {
      expect([...row.children].slice(0, 6).map((cell) => cell.className.split(" ")[0])).toEqual(["tl-dot", "tl-when", "tl-kind", "tl-what", "tl-who", "tl-act"]);
    }
    // Status nur am Punkt: überfällig = kritischer Punkt, sonst die Kennfarbe des Typs.
    expect(rowStarting(list, "01.09.2026").querySelector(".tl-dot--overdue")).not.toBeNull();
    expect(rowStarting(list, "31.03.2029").querySelector(".tl-dot--t-frist")).not.toBeNull();
    expect(screen.getByText("Erledigte und abgebrochene (1)")).toBeInTheDocument();
    // Vom System ersetzte Termine erscheinen nicht als „Abgebrochen“.
    expect(screen.queryByText("Vertrag auf „Beendet“ setzen")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Kennfarben der Typen")).toHaveTextContent("Farbe = Typ");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Erinnerung ohne ToDo: „Erinnerung: Vertragsende“; Person als Initialen + Name", async () => {
    api.getContractRegister.mockResolvedValue({ as_of: "2026-10-13", terms: { reminder_dates: [] }, fields: {} });
    renderTimeline();
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    const reminder = rowStarting(list, "30.11.2028");
    expect(within(reminder).getByText("Erinnerung: Vertragsende")).toBeInTheDocument();
    expect(reminder.querySelector(".tl-avatar")).toHaveTextContent("A");
    expect(rowStarting(list, "01.01.2040").querySelector(".tl-who")).toHaveTextContent("–");
  });

  it("„Prüfen“ öffnet den Vergleich; ohne Dokumentwert nur „Beibehalten“", async () => {
    const user = userEvent.setup();
    const check = endCheck();
    renderTimeline({ endCheck: check });
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
    renderTimeline({ endCheck: check });
    await user.click(await screen.findByRole("button", { name: "Prüfen" }));
    await user.click(screen.getByRole("button", { name: "Quelle" }));
    expect(check.onShowSource).toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Übernehmen" }));
    expect(check.onAdopt).toHaveBeenCalled();
  });

  it("eine Hauptaktion je Zeile: Frist „Öffnen“, Aufgabe „Erledigt“; Rest im „⋯“-Menü", async () => {
    const user = userEvent.setup();
    const onOpenTarget = vi.fn();
    const items = [deadline(), task()];
    api.listContractDeadlines.mockResolvedValue({ items });
    api.deadlineAction.mockResolvedValue({ items });
    renderTimeline({ onOpenTarget });
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    const frist = rowStarting(list, "31.03.2029");
    await user.click(within(frist).getByRole("button", { name: "Öffnen" }));
    expect(onOpenTarget).toHaveBeenCalledWith({ tab: "register", section: "term" });
    expect(within(frist).queryByRole("button", { name: "Erledigt" })).not.toBeInTheDocument();
    // Systemfrist: „Erledigt“ im Menü, kein „Abbrechen“.
    await user.click(within(frist).getByRole("button", { name: "Weitere Aktionen: Vertragsende" }));
    const menu = screen.getByRole("menu");
    expect(within(menu).getAllByRole("menuitem").map((item) => item.textContent)).toEqual(["Bearbeiten", "Zuweisen …", "In Kalender eintragen", "Erledigt"]);
    await user.click(within(menu).getByRole("menuitem", { name: "Erledigt" }));
    expect(api.deadlineAction).toHaveBeenCalledWith("test-klinik", "d-end", "done");

    const aufgabe = rowStarting(list, "10.12.2026");
    await user.click(within(aufgabe).getByRole("button", { name: "Erledigt" }));
    expect(api.deadlineAction).toHaveBeenCalledWith("test-klinik", "d-task", "done");
  });

  it("„⋯“ mit der Tastatur: öffnen, Pfeile, Escape gibt den Fokus zurück; Klick daneben schließt", async () => {
    const user = userEvent.setup();
    api.listContractDeadlines.mockResolvedValue({ items: [task()] });
    renderTimeline();
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    const trigger = within(rowStarting(list, "10.12.2026")).getByRole("button", { name: "Weitere Aktionen: Verlängerung umsetzen" });
    expect(trigger).toHaveAttribute("aria-haspopup", "menu");
    trigger.focus();
    await user.keyboard("{Enter}");
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    const items = within(screen.getByRole("menu")).getAllByRole("menuitem");
    expect(items.map((item) => item.textContent)).toEqual(["Bearbeiten", "Zuweisen …", "In Kalender eintragen", "Abbrechen"]);
    expect(items[0]).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(items[1]).toHaveFocus();
    await user.keyboard("{ArrowUp}{ArrowUp}");
    expect(items[3]).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    await user.click(trigger);
    await user.click(document.body);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("„Abbrechen“ fragt erst nach; „In Kalender eintragen“ lädt eine .ics-Datei", async () => {
    const user = userEvent.setup();
    api.listContractDeadlines.mockResolvedValue({ items: [task()] });
    renderTimeline();
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    const row = () => rowStarting(list, "10.12.2026");
    await user.click(within(row()).getByRole("button", { name: /Weitere Aktionen/ }));
    await user.click(screen.getByRole("menuitem", { name: "In Kalender eintragen" }));
    expect(api.downloadIcs).toHaveBeenCalledWith("termin-2026-12-10", expect.stringContaining("SUMMARY:Verlängerung umsetzen"));

    await user.click(within(row()).getByRole("button", { name: /Weitere Aktionen/ }));
    await user.click(screen.getByRole("menuitem", { name: "Abbrechen" }));
    expect(api.deadlineAction).not.toHaveBeenCalled();
    await user.click(within(row()).getByRole("button", { name: "Ja, abbrechen" }));
    expect(api.deadlineAction).toHaveBeenCalledWith("test-klinik", "d-task", "cancel");
  });

  it("„Zuweisen …“ ändert die Zuständigkeit einer Aufgabe", async () => {
    const user = userEvent.setup();
    api.listContractDeadlines.mockResolvedValue({ items: [task()] });
    renderTimeline();
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    await user.click(within(rowStarting(list, "10.12.2026")).getByRole("button", { name: /Weitere Aktionen/ }));
    await user.click(screen.getByRole("menuitem", { name: "Zuweisen …" }));
    const form = screen.getByRole("form", { name: "„Verlängerung umsetzen“ zuweisen" });
    await screen.findByRole("option", { name: "Tom Weber" });
    await user.selectOptions(within(form).getByLabelText("Zuständig"), "u-2");
    await user.click(within(form).getByRole("button", { name: "Speichern" }));
    expect(api.updateDeadline).toHaveBeenCalledWith("test-klinik", "d-task", { assignee_account_id: "u-2" });
  });

  it("doppelt angelegte Aufgaben: ab der zweiten ein Hinweis, nichts wird gelöscht", async () => {
    api.listContractDeadlines.mockResolvedValue({ items: [task(), task({ id: "d-task-2", title: " verlängerung UMSETZEN", due_date: "2029-03-31" })] });
    renderTimeline();
    const list = await screen.findByRole("list", { name: "Termine und Aufgaben" });
    expect(within(rowStarting(list, "10.12.2026")).queryByText("Doppelt angelegt – eine Aufgabe genügt")).not.toBeInTheDocument();
    expect(within(rowStarting(list, "31.03.2029")).getByText("Doppelt angelegt – eine Aufgabe genügt")).toBeInTheDocument();
  });

  it("Filter: Typ, „Nur meine“, leer mit „Filter zurücksetzen“", async () => {
    const user = userEvent.setup();
    api.listContractDeadlines.mockResolvedValue({ items: [deadline(), task()] });
    renderTimeline();
    const group = await screen.findByRole("group", { name: "Termine filtern" });
    // Offen: Frist, Aufgabe, zwei Erinnerungen (30.11.2028 aus remind_on, 03.03.2029 aus den Vertragsdaten).
    expect(within(group).getByRole("button", { name: /^Alle/ })).toHaveTextContent("Alle 4");
    expect(within(group).getByRole("button", { name: /^Erinnerungen/ })).toHaveTextContent("2");
    await user.click(within(group).getByRole("button", { name: /^Fristen/ }));
    let list = screen.getByRole("list", { name: "Termine und Aufgaben" });
    expect(rowTexts(list).filter((text) => !text.startsWith("Heute"))).toHaveLength(1);
    await user.click(within(group).getByRole("button", { name: /^Alle/ }));
    await user.click(within(group).getByRole("button", { name: "Nur meine" }));
    list = screen.getByRole("list", { name: "Termine und Aufgaben" });
    expect(rowTexts(list).filter((text) => !text.startsWith("Heute"))).toEqual([expect.stringMatching(/Verlängerung umsetzen/)]);
    await user.click(within(group).getByRole("button", { name: /^Fristen/ }));
    expect(screen.getByText(/Keine Einträge für diesen Filter/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Filter zurücksetzen" }));
    expect(within(group).getByRole("button", { name: /^Alle/ })).toHaveAttribute("aria-pressed", "true");
    expect(within(group).getByRole("button", { name: "Nur meine" })).toHaveAttribute("aria-pressed", "false");
  });

  it("Erledigtes eingeklappt: durchgestrichen, „Abgebrochen“, einzige Aktion „Wieder öffnen“", async () => {
    const user = userEvent.setup();
    renderTimeline();
    const details = (await screen.findByText("Erledigte und abgebrochene (1)")).closest("details")!;
    expect(details).not.toHaveAttribute("open");
    const closed = within(details).getByRole("list", { name: "Erledigte und abgebrochene" });
    const row = within(closed).getAllByRole("listitem")[0];
    expect(row).toHaveClass("tl-row--closed");
    expect(within(row).getByText("Abgebrochen")).toBeInTheDocument();
    expect(within(row).getByText(/abgebrochen am 21\.08\.2025 von Ahmad/)).toBeInTheDocument();
    expect(within(row).getAllByRole("button").map((button) => button.textContent)).toEqual(["Wieder öffnen"]);
    await user.click(within(row).getByRole("button", { name: "Wieder öffnen" }));
    expect(api.deadlineAction).toHaveBeenCalledWith("test-klinik", "d-old", "reopen");
  });

  it("leer nur, wenn es gar nichts gibt – mit Link zu den Vertragsdaten", async () => {
    const user = userEvent.setup();
    const onOpenTarget = vi.fn();
    api.listContractDeadlines.mockResolvedValue({ items: [] });
    renderTimeline({ onOpenTarget });
    expect(await screen.findByText("Keine Termine. Sie entstehen automatisch aus den Vertragsdaten.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Vertragsdaten öffnen" }));
    expect(onOpenTarget).toHaveBeenCalledWith({ tab: "register", section: "term" });
  });
});
