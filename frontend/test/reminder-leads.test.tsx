import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import ReminderLeadsEditor from "@/components/contracts/detail/ReminderLeadsEditor";
import type { ContractRegister } from "@/lib/domain-api/register";

const api = vi.hoisted(() => ({ saveReminderLeads: vi.fn() }));
vi.mock("@/lib/domain-api/register", () => api);

function register(extra: { value: number; unit: "days" | "weeks" | "months" }[], dates: string[]): ContractRegister {
  return {
    terms: { reminder_dates: dates, reminder_date: dates[0] ?? null },
    reminders: { default_lead_months: 4, lead_months: null, extra_leads: extra },
  } as unknown as ContractRegister;
}

describe("Weitere Erinnerungen", () => {
  it("zeigt die Termine, fügt Erinnerungen hinzu und speichert", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    api.saveReminderLeads.mockResolvedValue(register([{ value: 1, unit: "months" }, { value: 2, unit: "weeks" }], ["2028-11-30", "2029-02-28", "2029-03-17"]));
    const { container } = render(<ReminderLeadsEditor contractId="c-1" orgSlug="test-klinik" register={register([], ["2028-11-30"])} editable onSaved={onSaved} />);
    expect(screen.getByText("Erinnerungen am 30.11.2028.")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("button", { name: "Weitere Erinnerung hinzufügen" }));
    await user.click(screen.getByRole("button", { name: "+ Erinnerung hinzufügen" }));
    await user.type(screen.getByLabelText("Weitere Erinnerung 1: Anzahl"), "1");
    await user.selectOptions(screen.getByLabelText("Weitere Erinnerung 1: Einheit"), "months");
    await user.click(screen.getByRole("button", { name: "+ Erinnerung hinzufügen" }));
    await user.type(screen.getByLabelText("Weitere Erinnerung 2: Anzahl"), "2");
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Speichern" }));
    await waitFor(() => expect(api.saveReminderLeads).toHaveBeenCalledWith("test-klinik", "c-1", [{ value: 1, unit: "months" }, { value: 2, unit: "weeks" }]));
    expect(onSaved).toHaveBeenCalled();
  });

  it("ohne Recht nur lesen", () => {
    render(<ReminderLeadsEditor contractId="c-1" orgSlug="test-klinik" register={register([{ value: 2, unit: "weeks" }], [])} editable={false} onSaved={vi.fn()} />);
    expect(screen.getByText("2 Wochen vor der Frist")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
