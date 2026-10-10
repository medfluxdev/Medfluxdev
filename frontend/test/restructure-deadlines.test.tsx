import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DeadlineList from "@/components/deadlines/DeadlineList";
import type { DeadlineDto } from "@/lib/domain-api/deadlines";

const api = vi.hoisted(() => ({ listDeadlines: vi.fn(), listRenewals: vi.fn() }));
vi.mock("@/lib/domain-api/deadlines", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/domain-api/deadlines")>()), listDeadlines: api.listDeadlines }));
vi.mock("@/lib/domain-api/registerGrid", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/domain-api/registerGrid")>()), listRenewals: api.listRenewals }));

function deadline(overrides: Partial<DeadlineDto>): DeadlineDto {
  return {
    id: "d", contract_id: "c-1", contract_label: "000001 · Wartung", source: "system", system_key: "cancel_by", kind: "k", title: "Kündigungsfrist",
    due_date: "2026-10-20", remind_on: "2026-09-20", days_until_due: 10, overdue: false, assignee_account_id: null, assignee_name: null,
    escalation_account_id: null, escalation_name: null, todo_text: null, note: null, status: "open", send_email: true, send_ics: false,
    done_by_name: null, done_at: null, basis_unconfirmed: false, editable_fields: [], ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/fristen");
  api.listRenewals.mockResolvedValue({ as_of: "2026-10-10", days: 1, items: [], not_evaluable: [] });
});

describe("Termine", () => {
  it("zeigt Überfälliges als eigenen Abschnitt mit Signal und unterscheidet berechnet/manuell", async () => {
    api.listDeadlines.mockResolvedValue({ items: [
      deadline({ id: "a", overdue: true, days_until_due: -3, title: "Alt" }),
      deadline({ id: "b", source: "manual", system_key: null, title: "Wiedervorlage", basis_unconfirmed: true }),
    ] });
    render(<DeadlineList organizationSlug="test-klinik" />);
    const overdue = await screen.findByRole("region", { name: "Überfällig (1)" });
    expect(within(overdue).getByText("Alt")).toBeInTheDocument();
    expect(within(overdue).getAllByText("Überfällig").at(-1)!.closest(".signal")).toHaveClass("signal--critical");
    const upcoming = screen.getByRole("region", { name: "Anstehend (1)" });
    expect(within(upcoming).getByText("Manuelle Wiedervorlage")).toBeInTheDocument();
    expect(within(upcoming).getByText("Ungeprüfte KI-Werte").closest(".signal")).toHaveClass("signal--ai");
    expect(document.querySelector(".rg-row-overdue")).toBeNull();
  });

  it("liest „Nur meine“ und den Zeitraum aus der Adresse und schreibt sie zurück", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/fristen?ansicht=termine&nur=meine&zeitraum=7");
    api.listDeadlines.mockResolvedValue({ items: [] });
    render(<DeadlineList organizationSlug="test-klinik" />);
    await waitFor(() => expect(api.listDeadlines).toHaveBeenCalledWith("test-klinik", expect.objectContaining({ mine: true, dueBefore: expect.any(String) })));
    expect(screen.getByLabelText("Nur meine")).toBeChecked();
    expect(await screen.findByText("Keine Termine für diese Auswahl")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Alle offenen Termine anzeigen" }));
    await waitFor(() => expect(api.listDeadlines).toHaveBeenLastCalledWith("test-klinik", expect.objectContaining({ mine: false, dueBefore: undefined })));
    expect(window.location.search).toContain("zeitraum=alle");
  });

  it("nennt Verträge, deren Frist nicht berechenbar ist, statt Vollständigkeit vorzutäuschen", async () => {
    api.listDeadlines.mockResolvedValue({ items: [] });
    api.listRenewals.mockResolvedValue({ as_of: "2026-10-10", days: 1, items: [], not_evaluable: [{ contract_id: "x", register_number: "1", short_description: "A", reason: "Laufzeitangaben unvollständig" }] });
    render(<DeadlineList organizationSlug="test-klinik" />);
    expect(await screen.findByText(/Für 1 Vertrag ist die Kündigungsfrist nicht berechenbar/)).toBeInTheDocument();
  });
});
