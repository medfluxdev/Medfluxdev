import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AiReviewButton, { REGISTER_CHANGED_EVENT, openAiValues } from "@/components/contracts/detail/AiReviewButton";
import type { ContractRegister, RegisterField } from "@/lib/domain-api/register";

const api = vi.hoisted(() => ({ getContractRegister: vi.fn(), updateContractRegister: vi.fn() }));
vi.mock("@/lib/domain-api/register", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/register")>()),
  ...api,
}));

function field(label: string, origin: RegisterField["origin"]): RegisterField {
  return { value: "x", label, group: "identity", display: null, origin, source_field: null, extraction_id: null, ai_proposed_value: null, confirmed_by_name: null, confirmed_at: null, updated_by_name: null, updated_at: null };
}

function register(fields: Record<string, RegisterField>): ContractRegister {
  return { has_ai_analysis: true, review_pending: true, fields } as unknown as ContractRegister;
}

const OPEN = register({
  short_description: field("Kurzbeschreibung", "ai"),
  term_model: field("Vertragsart", "ai"),
  initial_term_value: field("Laufzeit", "ai"),
  initial_term_unit: field("Laufzeit (Einheit)", "ai"),
  notice_period_value: field("Kündigungsfrist", "ai_confirmed"),
  internal_number: field("Interne Nummer", "manual"),
});

beforeEach(() => {
  vi.clearAllMocks();
  api.getContractRegister.mockResolvedValue(OPEN);
});

describe("KI-Prüfung im Kopf der Vertragsakte", () => {
  it("zählt Zeiträume einmal (Anzahl + Einheit = ein Feld)", () => {
    expect(openAiValues(OPEN).map((item) => [item.label, item.keys])).toEqual([
      ["Kurzbeschreibung", ["short_description"]],
      ["Vertragsart", ["term_model"]],
      ["Laufzeit", ["initial_term_value", "initial_term_unit"]],
    ]);
  });

  it("zeigt die offenen Werte, bestätigt einzeln und meldet die Änderung", async () => {
    const user = userEvent.setup();
    api.updateContractRegister.mockResolvedValue(register({ ...OPEN.fields, initial_term_value: field("Laufzeit", "ai_confirmed"), initial_term_unit: field("Laufzeit (Einheit)", "ai_confirmed") }));
    const changed = vi.fn();
    window.addEventListener(REGISTER_CHANGED_EVENT, changed);
    const { container } = render(<AiReviewButton contractId="c-1" orgSlug="test-klinik" reviewPending canEdit />);
    await user.click(await screen.findByRole("button", { name: /KI-Werte prüfen · 3/ }));
    const panel = screen.getByRole("group", { name: "KI-Werte prüfen" });
    expect(within(panel).getByText("3 KI-Werte noch nicht bestätigt")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: "Laufzeit" })).toHaveAttribute("href", "/contracts/c-1?tab=register&feld=initial_term");
    expect(within(panel).getByRole("link", { name: "Im Dokument prüfen (offen)" })).toHaveAttribute("href", "/contracts/c-1?tab=documents&subtab=review");
    expect(await axe(container)).toHaveNoViolations();
    await user.click(within(panel).getByRole("button", { name: "Laufzeit bestätigen" }));
    expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: {}, confirm: ["initial_term_value", "initial_term_unit"] });
    await waitFor(() => expect(changed).toHaveBeenCalled());
    expect(await screen.findByRole("button", { name: /KI-Werte prüfen · 2/ })).toBeInTheDocument();
    window.removeEventListener(REGISTER_CHANGED_EVENT, changed);
  });

  it("„Alle bestätigen“ bestätigt alle offenen Felder auf einmal", async () => {
    const user = userEvent.setup();
    api.updateContractRegister.mockResolvedValue(register({}));
    render(<AiReviewButton contractId="c-1" orgSlug="test-klinik" reviewPending={false} canEdit />);
    await user.click(await screen.findByRole("button", { name: /KI-Werte prüfen · 3/ }));
    await user.click(screen.getByRole("button", { name: "Alle bestätigen" }));
    expect(api.updateContractRegister).toHaveBeenCalledWith("test-klinik", "c-1", { changes: {}, confirm: ["short_description", "term_model", "initial_term_value", "initial_term_unit"] });
  });

  it("ohne Bearbeitungsrecht nur ansehen; ohne offene Werte nur die Dokumentprüfung", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<AiReviewButton contractId="c-1" orgSlug="test-klinik" reviewPending canEdit={false} />);
    await user.click(await screen.findByRole("button", { name: /KI-Werte prüfen · 3/ }));
    expect(screen.queryByRole("button", { name: /bestätigen/i })).not.toBeInTheDocument();
    unmount();

    api.getContractRegister.mockResolvedValue(register({ short_description: field("Kurzbeschreibung", "ai_confirmed") }));
    render(<AiReviewButton contractId="c-1" orgSlug="test-klinik" reviewPending canEdit />);
    expect(await screen.findByRole("button", { name: /KI-Prüfung offen/ })).toBeInTheDocument();
  });

  it("verschwindet, wenn nichts mehr zu prüfen ist", async () => {
    api.getContractRegister.mockResolvedValue(register({ short_description: field("Kurzbeschreibung", "ai_confirmed") }));
    const { container } = render(<AiReviewButton contractId="c-1" orgSlug="test-klinik" reviewPending={false} canEdit />);
    await waitFor(() => expect(api.getContractRegister).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
