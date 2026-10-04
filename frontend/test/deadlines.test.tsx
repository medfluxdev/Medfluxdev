import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDeadlinesPanel from "@/components/contracts/detail/ContractDeadlinesPanel";
import InboxView from "@/components/deadlines/InboxView";
import NotificationCenter from "@/components/shell/NotificationCenter";
import type { DeadlineDto, InboxDto } from "@/lib/domain-api/deadlines";

const api = vi.hoisted(() => ({
  listContractDeadlines: vi.fn(),
  createContractDeadline: vi.fn(),
  updateDeadline: vi.fn(),
  deadlineAction: vi.fn(),
  getInbox: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}));

vi.mock("@/lib/domain-api/deadlines", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/deadlines")>()),
  ...api,
}));
vi.mock("@/lib/domain-api/catalogs", () => ({
  listLookups: vi.fn().mockResolvedValue({ field_keys: [], items: [{ id: "k1", field_key: "deadline_kind", code: "pruefung", label: "Prüfung", description: null, is_active: true, sort_order: 0 }] }),
}));
vi.mock("@/lib/domain-api/ownership", () => ({
  listOwnershipAssignees: vi.fn().mockResolvedValue({ items: [{ id: "u-2", display_name: "Vertretung", email: "v@x", role: "contract_manager", hospital_id: null, department_id: null }] }),
}));
vi.mock("@/lib/domain-api/notifications", () => ({
  listNotifications: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}));

function deadline(overrides: Partial<DeadlineDto> = {}): DeadlineDto {
  return {
    id: "d-1", contract_id: "c-1", contract_label: "000001 · Wartung MRT", source: "system", system_key: "cancel_by",
    kind: "kuendigungsfrist", title: "Kündigungsfrist", due_date: "2027-06-30", remind_on: "2027-03-30", days_until_due: 269,
    overdue: false, assignee_account_id: "u-1", assignee_name: "Manager", escalation_account_id: "u-3", escalation_name: "Chefin",
    todo_text: "Verlängerung prüfen", note: null, status: "open", send_email: true, send_ics: false, done_by_name: null,
    done_at: null, basis_unconfirmed: true, editable_fields: ["note", "send_email", "send_ics"], ...overrides,
  };
}

const INBOX: InboxDto = {
  unread_count: 1,
  notifications: [
    { id: "n-1", kind: "deadline_reminder", title: "Erinnerung: Kündigungsfrist am 30.06.2027", body: "Vertrag 000001", contract_id: "c-1", deadline_id: "d-1", on_behalf_of_name: "Manager", created_at: "2027-03-30T05:00:00Z", read_at: null },
    { id: "n-2", kind: "deadline_assigned", title: "Neuer Termin", body: null, contract_id: "c-1", deadline_id: "d-2", on_behalf_of_name: null, created_at: "2027-03-01T05:00:00Z", read_at: "2027-03-02T05:00:00Z" },
  ],
  deadlines: [deadline({ overdue: true, days_until_due: -2 })],
  representing: [{ account_id: "u-1", display_name: "Manager" }],
};

describe("Termine eines Vertrags", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listContractDeadlines.mockResolvedValue({ items: [deadline(), deadline({ id: "d-9", source: "manual", system_key: null, title: "Alt", status: "done", done_by_name: "Manager", basis_unconfirmed: false })] });
    api.deadlineAction.mockResolvedValue({ items: [deadline({ status: "done" })] });
    api.createContractDeadline.mockResolvedValue({ items: [deadline()] });
  });

  it("zeigt berechnete Fristen mit KI-Hinweis und erledigt sie", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContractDeadlinesPanel contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("Kündigungsfrist")).toBeInTheDocument();
    expect(screen.getByText("Aus Stammdaten berechnet")).toBeInTheDocument();
    expect(screen.getByText("Basiert auf ungeprüften KI-Werten")).toBeInTheDocument();
    expect(screen.getAllByText(/Eskalation: Chefin/)[0]).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Abbrechen" })).not.toBeInTheDocument();
    expect(screen.getByText("Erledigte und abgebrochene Termine (1)")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Erledigt" }));
    expect(api.deadlineAction).toHaveBeenCalledWith("test-klinik", "d-1", "done");
  });

  it("legt einen manuellen Termin mit Zuständigkeit an", async () => {
    const user = userEvent.setup();
    render(<ContractDeadlinesPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByText("Kündigungsfrist");
    await user.click(screen.getByRole("button", { name: "Termin hinzufügen" }));
    const form = screen.getByRole("form", { name: "Neuer Termin" });
    await user.type(within(form).getByLabelText("Bezeichnung *"), "Wartungsprotokoll anfordern");
    await user.type(within(form).getByLabelText("Fällig am *"), "2026-11-15");
    await waitFor(() => expect(within(within(form).getByLabelText("Zuständig")).getByRole("option", { name: "Vertretung" })).toBeInTheDocument());
    await user.selectOptions(within(form).getByLabelText("Zuständig"), "u-2");
    await user.click(within(form).getByLabelText("Kalendereinladung (ICS)"));
    await user.click(within(form).getByRole("button", { name: "Termin anlegen" }));
    expect(api.createContractDeadline).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({
      title: "Wartungsprotokoll anfordern", due_date: "2026-11-15", assignee_account_id: "u-2", send_ics: true, send_email: true,
    }));
  });
});

describe("Postfach", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getInbox.mockResolvedValue(INBOX);
    api.markNotificationRead.mockResolvedValue({ marked: 1 });
    api.markAllNotificationsRead.mockResolvedValue({ marked: 1 });
  });

  it("zeigt Wiedervorlage, Vertretung und markiert als gelesen", async () => {
    const user = userEvent.setup();
    render(<InboxView organizationSlug="test-klinik" />);
    expect(await screen.findByText(/Sie vertreten derzeit: Manager/)).toBeInTheDocument();
    expect(screen.getByText(/überfällig/)).toBeInTheDocument();
    expect(screen.getByText("Erinnerung · Vertretung für Manager")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Als gelesen markieren" }));
    expect(api.markNotificationRead).toHaveBeenCalledWith("test-klinik", "n-1");
    await user.click(screen.getByRole("button", { name: "Alle als gelesen markieren" }));
    expect(api.markAllNotificationsRead).toHaveBeenCalledWith("test-klinik");
  });

  it("zählt ungelesene Erinnerungen in der Glocke", async () => {
    render(<NotificationCenter />);
    expect(await screen.findByLabelText("1 offene Hinweise")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Postfach öffnen (1 ungelesen)" })).toHaveAttribute("href", "/postfach");
  });
});
