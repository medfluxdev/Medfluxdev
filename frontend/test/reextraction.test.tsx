import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReextractionPanel, { ReextractionBanner, parsePages } from "@/components/contracts/detail/Reextraction";
import ContractGaps from "@/components/contracts/detail/ContractGaps";
import type { FactRow, ReextractionRun, ReextractionState } from "@/lib/domain-api/reextraction";

const api = vi.hoisted(() => ({
  getReextraction: vi.fn(),
  getReextractionModels: vi.fn(),
  startReextraction: vi.fn(),
  applyReextraction: vi.fn(),
  discardReextraction: vi.fn(),
  cancelReextraction: vi.fn(),
}));
vi.mock("@/lib/domain-api/reextraction", () => api);
const nav = vi.hoisted(() => {
  const replace = vi.fn();
  return { params: new URLSearchParams(), replace, router: { replace, push: () => undefined } };
});
vi.mock("next/navigation", () => ({
  useRouter: () => nav.router,
  usePathname: () => "/contracts/c-1",
  useSearchParams: () => nav.params,
}));

function run(overrides: Partial<ReextractionRun> = {}): ReextractionRun {
  return {
    id: "run-1", status: "ready", mode: "full", fields: [], page_hint: [], reread_document: false, model_id: null,
    summary: { new: 1, changed: 1, missing_again: 1 }, applied_keys: [], requested_by_name: "Manager", message: null,
    queue_position: 0, created_at: "2026-10-11T10:00:00Z", started_at: null, finished_at: null, stale: false, ...overrides,
  };
}

const ROWS: FactRow[] = [
  { key: "dates.start_date", label: "Vertragsbeginn", group: "new", current: null, proposed: "01.01.2025", evidence: [{ page: 4, quote: "Beginn 01.01.2025" }], register_keys: ["term_start_date"], preselected: true },
  { key: "termination.cancellation_period", label: "Kündigungsfrist", group: "changed", current: "3 Monate", proposed: "6 Monate", evidence: [{ page: 5, quote: "sechs Monate" }], register_keys: [], preselected: false },
  { key: "identity.contract_title", label: "Vertragstitel", group: "missing_again", current: "Wartung CT", proposed: null, evidence: [], register_keys: [], preselected: false },
];

function state(overrides: Partial<ReextractionState> = {}): ReextractionState {
  return {
    can_start: true, blocked_reason: null, reread_suggested: false,
    missing: [{ key: "dates.start_date", label: "Vertragsbeginn" }, { key: "dates.duration", label: "Laufzeit" }],
    run: null, rows: [], ...overrides,
  };
}

function panel(value: ReextractionState, extra: { onApplied?: () => void; onShowPage?: (page: number) => void } = {}) {
  const reload = vi.fn();
  const utils = render(<ReextractionPanel contractId="c-1" orgSlug="test-klinik" state={value} reload={reload} onApplied={extra.onApplied ?? vi.fn()} onShowPage={extra.onShowPage} />);
  return { ...utils, reload };
}

beforeEach(() => {
  vi.clearAllMocks();
  nav.params = new URLSearchParams();
  api.getReextractionModels.mockResolvedValue({ provider_id: "ollama", current_model: "qwen3-vl:8b", models: [
    { model_id: "qwen3-vl:8b", label: "qwen3-vl:8b", parameter_size: "8B", vision: true, current: true },
    { model_id: "qwen3:14b", label: "qwen3:14b", parameter_size: "14B", vision: false, current: false },
  ] });
});

describe("Erneut aus dem Dokument erfassen", () => {
  it("bleibt ohne Recht und ohne Lauf unsichtbar", () => {
    const { container } = panel(state({ can_start: false }));
    expect(container).toBeEmptyDOMElement();
  });

  it("startet standardmäßig nur die fehlenden Angaben, auf Wunsch mit anderem Modell", async () => {
    const user = userEvent.setup();
    api.startReextraction.mockResolvedValue(run({ status: "queued" }));
    const { reload } = panel(state());
    await user.click(screen.getByRole("button", { name: "Erneut erfassen …" }));
    const dialog = screen.getByRole("dialog", { name: "Erneut aus dem Dokument erfassen" });
    expect(within(dialog).getByRole("radio", { name: "Nur fehlende Angaben suchen" })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: "Vertragsbeginn" })).toBeChecked();
    await user.click(within(dialog).getByRole("checkbox", { name: "Laufzeit" }));
    await user.click(within(dialog).getByText("Erweitert"));
    await waitFor(() => expect(within(dialog).getByRole("combobox", { name: "Modell" })).toBeEnabled());
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Modell" }), "qwen3:14b");
    expect(await axe(dialog)).toHaveNoViolations();
    await user.click(within(dialog).getByRole("button", { name: "Auswertung starten" }));
    expect(api.startReextraction).toHaveBeenCalledWith("test-klinik", "c-1", {
      mode: "missing_fields", fields: ["dates.start_date"], page_hint: [], reread_document: false, model_id: "qwen3:14b",
    });
    expect(reload).toHaveBeenCalled();
  });

  it("schlägt das Neulesen vor, wenn das Dokument ohne Texterkennung gelesen wurde", async () => {
    const user = userEvent.setup();
    panel(state({ reread_suggested: true, missing: [] }));
    await user.click(screen.getByRole("button", { name: "Erneut erfassen …" }));
    expect(screen.getByRole("radio", { name: "Nur fehlende Angaben suchen" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Ganzes Dokument neu auswerten" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Dokument neu lesen (Texterkennung)" })).toBeChecked();
  });

  it("zeigt den Vergleich, wählt nur Neues vor und übernimmt die Auswahl", async () => {
    const user = userEvent.setup();
    const onApplied = vi.fn();
    const onShowPage = vi.fn();
    api.applyReextraction.mockResolvedValue({ applied: 2, keys: [], message: "2 Angabe(n) übernommen." });
    const { container } = panel(state({ run: run(), rows: ROWS }), { onApplied, onShowPage });
    expect(screen.getByRole("checkbox", { name: "Vertragsbeginn übernehmen" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Kündigungsfrist übernehmen" })).not.toBeChecked();
    // Nicht erneut gefunden: keine Auswahl, bisheriger Wert bleibt sichtbar.
    expect(screen.queryByRole("checkbox", { name: "Vertragstitel übernehmen" })).not.toBeInTheDocument();
    expect(screen.getByText("Nicht erneut gefunden – der bisherige Wert bleibt (1)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "S. 4" }));
    expect(onShowPage).toHaveBeenCalledWith(4);
    expect(await axe(container)).toHaveNoViolations();

    await user.click(screen.getByRole("checkbox", { name: "Kündigungsfrist übernehmen" }));
    await user.click(screen.getByRole("button", { name: "Ausgewählte übernehmen (2)" }));
    expect(api.applyReextraction).toHaveBeenCalledWith("test-klinik", "c-1", "run-1", ["dates.start_date", "termination.cancellation_period"]);
    await waitFor(() => expect(onApplied).toHaveBeenCalled());
  });

  it("ein veraltetes Ergebnis kann nicht übernommen werden", () => {
    panel(state({ run: run({ stale: true }), rows: ROWS }));
    expect(screen.getByText(/Vertragsdaten wurden inzwischen geändert/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Ausgewählte übernehmen/ })).not.toBeInTheDocument();
  });

  it("ohne neue Angaben: ehrliche Meldung und nächste Schritte", () => {
    panel(state({ run: run({ summary: { missing_again: 1 } }), rows: [ROWS[2]] }));
    expect(screen.getByText("Keine zusätzlichen Angaben gefunden.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mit anderen Einstellungen versuchen …" })).toBeInTheDocument();
  });

  it("während der Auswertung: Wartestand und Abbrechen", async () => {
    const user = userEvent.setup();
    api.cancelReextraction.mockResolvedValue({ status: "cancelled", cancel_requested: false });
    panel(state({ run: run({ status: "queued", queue_position: 2 }) }));
    expect(screen.getByText("Wartet – 2 Auswertungen vor dieser.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Erneut erfassen …" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(api.cancelReextraction).toHaveBeenCalledWith("test-klinik", "c-1", "run-1");
  });

  it("Hinweis im Kopf führt zum Ergebnis", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(<ReextractionBanner state={state({ run: run() })} onOpen={onOpen} />);
    expect(screen.getByText("Erneute Erfassung abgeschlossen: 2 Angaben zum Prüfen.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Prüfen" }));
    expect(onOpen).toHaveBeenCalled();
  });

  it("„Im Dokument suchen“ öffnet den Dialog mit genau diesem Feld und Seitenangabe", async () => {
    const user = userEvent.setup();
    api.startReextraction.mockResolvedValue(run({ status: "queued" }));
    nav.params = new URLSearchParams("tab=documents&subtab=document&abschnitt=reextraction&suchen=notice_period");
    panel(state({ field_search: { notice_period_value: [{ key: "termination.cancellation_period", label: "Kündigungsfrist" }] } }));
    const dialog = await screen.findByRole("dialog", { name: "Erneut aus dem Dokument erfassen" });
    // Der Parameter wird entfernt, damit ein Neuladen den Dialog nicht wieder öffnet.
    expect(nav.replace).toHaveBeenCalledWith("/contracts/c-1?tab=documents&subtab=document&abschnitt=reextraction", { scroll: false });
    expect(within(dialog).getByRole("checkbox", { name: "Kündigungsfrist" })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: "Vertragsbeginn" })).not.toBeChecked();
    const pagesInput = within(dialog).getByRole("textbox", { name: "Wo steht es? (optional)" });
    await user.type(pagesInput, "abc");
    expect(within(dialog).getByRole("button", { name: "Auswertung starten" })).toBeDisabled();
    await user.clear(pagesInput);
    await user.type(pagesInput, "4–5, 9");
    await user.click(within(dialog).getByRole("button", { name: "Auswertung starten" }));
    expect(api.startReextraction).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({
      mode: "missing_fields", fields: ["termination.cancellation_period"], page_hint: [4, 5, 9],
    }));
  });
});

describe("Fehlende Angaben im Dokument suchen", () => {
  it("die Karte „Was fehlt noch?“ bietet die Suche an, der Link öffnet den Dialog mit allen fehlenden Angaben", async () => {
    const gaps = [{ key: "term_start_date", label: "Vertragsbeginn", reason: "nötig für „Gültig“", command: "Vertragsbeginn erfassen", target: { tab: "register" as const, field: "term_start_date" } }];
    const { unmount } = render(<ContractGaps contractId="c-1" gaps={gaps} searchHref="/contracts/c-1?tab=documents&subtab=document&abschnitt=reextraction&suchen=fehlende" />);
    expect(screen.getByRole("link", { name: "Fehlende Angaben im Dokument suchen" })).toHaveAttribute("href", "/contracts/c-1?tab=documents&subtab=document&abschnitt=reextraction&suchen=fehlende");
    unmount();
    render(<ContractGaps contractId="c-1" gaps={gaps} searchHref={null} />);
    expect(screen.queryByRole("link", { name: "Fehlende Angaben im Dokument suchen" })).not.toBeInTheDocument();

    nav.params = new URLSearchParams("tab=documents&suchen=fehlende");
    panel(state());
    const dialog = await screen.findByRole("dialog", { name: "Erneut aus dem Dokument erfassen" });
    expect(within(dialog).getByRole("checkbox", { name: "Vertragsbeginn" })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: "Laufzeit" })).toBeChecked();
  });

  it("während einer Auswertung öffnet der Link keinen zweiten Dialog", () => {
    nav.params = new URLSearchParams("suchen=fehlende");
    panel(state({ run: run({ status: "running" }) }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(nav.replace).toHaveBeenCalled();
  });
});

describe("Seitenangabe", () => {
  it("versteht Einzelseiten, Bereiche und Listen und lehnt Unsinn ab", () => {
    expect(parsePages("")).toEqual([]);
    expect(parsePages("4")).toEqual([4]);
    expect(parsePages("4-6")).toEqual([4, 5, 6]);
    expect(parsePages("7, 4–5")).toEqual([4, 5, 7]);
    expect(parsePages("0")).toBeNull();
    expect(parsePages("6-4")).toBeNull();
    expect(parsePages("1-40")).toBeNull();
    expect(parsePages("Seite 4")).toBeNull();
  });
});
