import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PartnerSuggestions from "@/components/master-data/PartnerSuggestions";
import type { PartnerSuggestion } from "@/lib/domain-api/catalogs";

const api = vi.hoisted(() => ({ getPartnerSuggestions: vi.fn(), applyPartnerSuggestion: vi.fn(), dismissPartnerSuggestion: vi.fn() }));
vi.mock("@/lib/domain-api/catalogs", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/catalogs")>()),
  ...api,
}));

const item = (field: PartnerSuggestion["field"], label: string, value: string, extra: Partial<PartnerSuggestion> = {}): PartnerSuggestion => ({
  field, label, value, current: null, kind: "new", page: 9, quote: `Zitat ${value}`, contract_id: "c-1",
  register_number: "000042", contract_label: "Impella", sources: 1, ...extra,
});
const ITEMS = [
  item("email", "E-Mail", "service@abiomed.example"),
  item("phone", "Telefon", "+49 241 8860 0", { kind: "deviating", current: "0241 999" }),
  item("city", "Ort", "Aachen", { page: 1, sources: 2 }),
];

beforeEach(() => {
  vi.clearAllMocks();
  api.getPartnerSuggestions.mockResolvedValue({ partner: { id: "p-1", short_name: "ABIOMED" }, items: ITEMS, can_apply: true });
  api.applyPartnerSuggestion.mockResolvedValue({});
  api.dismissPartnerSuggestion.mockResolvedValue({ dismissed: true });
});

describe("Für den Vertragspartner gefunden", () => {
  it("auf dem Vertrag: neue und abweichende Angaben mit Quelle; ergänzen, ersetzen, ignorieren; axe", async () => {
    const user = userEvent.setup();
    const { container } = render(<PartnerSuggestions orgSlug="test-klinik" partnerId="p-1" contractId="c-1" />);
    const card = await screen.findByRole("region", { name: "Für den Vertragspartner gefunden" });
    expect(api.getPartnerSuggestions).toHaveBeenCalledWith("test-klinik", "p-1", "c-1");
    expect(within(card).getByText(/Angaben zu „ABIOMED“ gefunden/)).toBeInTheDocument();
    const email = within(card).getByText("service@abiomed.example").closest("li")!;
    expect(within(email).getByText("Neu")).toBeInTheDocument();
    expect(within(email).getByText("Aus dem Vertrag · S. 9")).toHaveAttribute("title", "„Zitat service@abiomed.example“");
    const phone = within(card).getByText("+49 241 8860 0").closest("li")!;
    expect(within(phone).getByText("Abweichend")).toBeInTheDocument();
    expect(within(phone).getByText("bisher: 0241 999")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    await user.click(within(email).getByRole("button", { name: "Beim Partner ergänzen" }));
    expect(api.applyPartnerSuggestion).toHaveBeenCalledWith("test-klinik", "p-1", ITEMS[0]);
    await user.click(within(phone).getByRole("button", { name: "Ignorieren" }));
    await waitFor(() => expect(api.dismissPartnerSuggestion).toHaveBeenCalledWith("test-klinik", "p-1", ITEMS[1]));
    expect(within(phone).getByRole("button", { name: "Beim Partner ersetzen" })).toBeInTheDocument();
    // Mehrere neue: „Alle neuen ergänzen“ übernimmt nur die neuen, nie die abweichenden.
    api.applyPartnerSuggestion.mockClear();
    await user.click(within(card).getByRole("button", { name: "Alle neuen ergänzen (2)" }));
    await waitFor(() => expect(api.applyPartnerSuggestion).toHaveBeenCalledTimes(2));
    expect(api.applyPartnerSuggestion.mock.calls.map((call) => call[2].field)).toEqual(["email", "city"]);
  });

  it("ohne Recht nur lesen; ohne Vorschläge nichts", async () => {
    api.getPartnerSuggestions.mockResolvedValueOnce({ partner: { id: "p-1", short_name: "ABIOMED" }, items: ITEMS, can_apply: false });
    const { unmount } = render(<PartnerSuggestions orgSlug="test-klinik" partnerId="p-1" contractId="c-1" />);
    const card = await screen.findByRole("region", { name: "Für den Vertragspartner gefunden" });
    expect(within(card).queryByRole("button")).not.toBeInTheDocument();
    expect(within(card).getByText(/Vertragspartner pflegen dürfen/)).toBeInTheDocument();
    unmount();
    api.getPartnerSuggestions.mockResolvedValueOnce({ partner: { id: "p-1", short_name: "ABIOMED" }, items: [], can_apply: true });
    const { container } = render(<PartnerSuggestions orgSlug="test-klinik" partnerId="p-1" contractId="c-1" />);
    await waitFor(() => expect(api.getPartnerSuggestions).toHaveBeenCalledTimes(2));
    expect(container).toBeEmptyDOMElement();
  });

  it("im Stammdaten-Fenster: aus allen Verträgen mit Vertragsnummer; nach Übernahme neu laden", async () => {
    const user = userEvent.setup();
    const onApplied = vi.fn();
    render(<PartnerSuggestions orgSlug="test-klinik" partnerId="p-1" variant="drawer" onApplied={onApplied} />);
    const box = await screen.findByRole("region", { name: "Aus Verträgen gefunden" });
    expect(api.getPartnerSuggestions).toHaveBeenCalledWith("test-klinik", "p-1", undefined);
    expect(within(box).getByText("Vertrag 000042 · S. 1 · in 2 Verträgen")).toBeInTheDocument();
    await user.click(within(within(box).getByText("Aachen").closest("li")!).getByRole("button", { name: "Beim Partner ergänzen" }));
    await waitFor(() => expect(onApplied).toHaveBeenCalled());
  });
});
