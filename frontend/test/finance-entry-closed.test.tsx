import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ getFinance: vi.fn() }));
vi.mock("@/lib/domain-api/finance", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/domain-api/finance")>()), ...api }));
vi.mock("@/lib/domain-api/catalogs", () => ({ listLookups: vi.fn().mockResolvedValue({ field_keys: [], items: [] }) }));
vi.mock("@/lib/domain-api/organizations", () => ({ listCostCenters: vi.fn().mockResolvedValue({ items: [] }) }));

describe("Finanzen: Karten starten zu", () => {
  it("„Eintrag erfassen“ in „Zu prüfen“ öffnet das Formular, auch wenn „Finanzeinträge“ noch zu ist", async () => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_CARDS_START_CLOSED", "true");
    window.sessionStorage.clear();
    api.getFinance.mockResolvedValue({
      contract_id: "c-1", as_of: "2026-10-04", entries: [], summaries: [], services: [], allocations: [], primary_cost_center_id: null,
      price_adjustment: { kind: null, percent: null, index_name: null, next_date: null, interval_months: null },
      suggestions: { entries: [], services: [] },
    });
    const { default: Panel } = await import("@/components/contracts/detail/ContractFinancePanel");
    const user = userEvent.setup();
    render(<Panel contractId="c-1" orgSlug="test-klinik" documentCosts={{
      annual_recurring: { amount: null }, availability: { manual_input_required: true, summary_de: "Kein Betrag.", explanation_de: null, found_facts: [], missing_inputs: ["Betrag"] },
    } as never} />);
    // „Zu prüfen“ ist zu: aufklappen, dann „Eintrag erfassen“
    await user.click(await screen.findByRole("button", { name: /Zu prüfen aufklappen/ }));
    await user.click(screen.getByRole("button", { name: "Eintrag erfassen" }));
    expect(await screen.findByRole("form", { name: /Finanzeintrag anlegen/ })).toBeVisible();
    vi.unstubAllEnvs();
  });
});
