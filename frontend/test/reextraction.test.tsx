import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ReextractionPanel, { ReextractionBanner, openProposals, parsePages, safeUnchanged } from "@/components/contracts/detail/Reextraction";
import ProposalReviewMode from "@/components/contracts/detail/ProposalReviewMode";
import OpenPoints, { buildOpenPoints } from "@/components/contracts/detail/OpenPoints";
import type { Proposal, ReextractionRun, ReextractionState } from "@/lib/domain-api/reextraction";

const api = vi.hoisted(() => ({
  getReextraction: vi.fn(),
  getReextractionModels: vi.fn(),
  startReextraction: vi.fn(),
  applyReextraction: vi.fn(),
  decideReextraction: vi.fn(),
  confirmUnchanged: vi.fn(),
  discardReextraction: vi.fn(),
  cancelReextraction: vi.fn(),
  getRollbackPreview: vi.fn(),
  rollbackToAnalysis: vi.fn(),
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
    id: "run-3", number: 3, status: "ready", mode: "supplement", mode_label: "Ergänzen", sections: [], fields: [], page_hint: [],
    hint: null, protect_manual: true, reset_confirmations: false, reread_document: false, model_id: null, progress: {},
    summary: { unchanged: 2, new: 2, deviating: 1, missing: 1 }, applied_keys: [], requested_by_name: "Ahmad", message: null,
    queue_position: 0, created_at: "2026-10-18T07:41:00Z", started_at: "2026-10-18T07:41:00Z", finished_at: "2026-10-18T07:43:00Z", stale: false, ...overrides,
  };
}

function proposal(key: string, label: string, kind: Proposal["kind"], current: string | null, proposed: string | null, extra: Partial<Proposal> = {}): Proposal {
  return {
    id: `p-${key}`, key, label, section: "term", kind, protected: false, current, proposed, confidence: 0.96,
    evidence: proposed ? [{ page: 5, quote: `Zitat ${label}`, confidence: 0.96, bbox: null }] : [], register_keys: [],
    decision: "pending", decided_by_name: null, decided_at: null, ...extra,
  };
}

const ROWS: Proposal[] = [
  proposal("sla.response_time", "Reaktionszeit", "new", null, "24 Stunden", { section: "services" }),
  proposal("costs.price_adjustment_clause", "Preisanpassung", "deviating", "Festpreis", "Index-Anpassung ab 2027", { section: "cost", confidence: 0.78 }),
  proposal("identity.contact_person", "Ansprechpartner", "missing", "M. Keller", null, { section: "partner", confidence: null }),
  proposal("dates.duration", "Laufzeit", "unchanged", "4 Jahre", "4 Jahre", { confidence: 0.97 }),
  proposal("dates.start_date", "Vertragsbeginn", "unchanged", "01.04.2025", "01.04.2025", { confidence: 0.99, protected: true }),
];

function state(overrides: Partial<ReextractionState> = {}): ReextractionState {
  return {
    can_start: true, blocked_reason: null, reread_suggested: false, first_analysis: false,
    missing: [{ key: "dates.start_date", label: "Vertragsbeginn" }],
    run: null, rows: [], open_fields: 9, evidence_count: 34, review_minutes: 14, duration_minutes: 2,
    sections: [
      { key: "partner", label: "Vertragsdaten" }, { key: "term", label: "Fristen & Aufgaben" },
      { key: "cost", label: "Finanzen" }, { key: "services", label: "Leistungen & SLA" }, { key: "device", label: "Verknüpfungen (Geräte)" },
    ],
    history: [
      { id: "run-2", number: 2, mode: "full", mode_label: "Vollständig neu bewerten", status: "applied", date: "2026-10-12T10:00:00Z", requested_by_name: "Ahmad", summary: { new: 3 }, accepted: 3, can_rollback: false },
      { id: null, number: 1, mode: "initial", mode_label: "Erstanalyse", status: "applied", date: "2026-10-05T10:00:00Z", requested_by_name: null, summary: {}, accepted: 0, can_rollback: true },
    ],
    new_document: null, can_review: true, ...overrides,
  };
}

function panel(value: ReextractionState, extra: Partial<Parameters<typeof ReextractionPanel>[0]> = {}) {
  const reload = vi.fn();
  const utils = render(<ReextractionPanel contractId="c-1" orgSlug="test-klinik" state={value} reload={reload} onApplied={vi.fn()} {...extra} />);
  return { ...utils, reload };
}

// Im eigenen Unterreiter ist die Karte immer offen.
async function expand(_user: ReturnType<typeof userEvent.setup>) {
  expect(screen.queryByRole("button", { name: /aufklappen$/ })).not.toBeInTheDocument();
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  nav.params = new URLSearchParams();
  api.getReextractionModels.mockResolvedValue({ provider_id: "ollama", current_model: "qwen3-vl:8b", models: [
    { model_id: "qwen3-vl:8b", label: "qwen3-vl:8b", parameter_size: "8B", vision: true, current: true },
    { model_id: "qwen3:14b", label: "qwen3:14b", parameter_size: "14B", vision: false, current: false },
  ] });
});

describe("Erneut aus dem Dokument erfassen – Auswahl", () => {
  it("ohne Recht: erklärt, wer starten darf (nie leer)", () => {
    panel(state({ can_start: false, history: [] }));
    expect(screen.getByText(/Eine neue Analyse starten dürfen das Vertragsmanagement und die Administration/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyse starten" })).not.toBeInTheDocument();
  });

  it("Server nicht erreichbar: Hinweis mit „Erneut laden“ statt leerer Fläche", async () => {
    const user = userEvent.setup();
    const reload = vi.fn();
    render(<ReextractionPanel contractId="c-1" orgSlug="test-klinik" state={null} reload={reload} onApplied={vi.fn()} loadError="Interner Fehler" />);
    expect(screen.getByRole("alert")).toHaveTextContent(/Die KI-Analyse ist gerade nicht verfügbar \(Interner Fehler\)/);
    await user.click(screen.getByRole("button", { name: "Erneut laden" }));
    expect(reload).toHaveBeenCalled();
  });

  it("zeigt drei Modi mit Umfang; Ergänzen ist voreingestellt und startet mit Optionen", async () => {
    const user = userEvent.setup();
    api.startReextraction.mockResolvedValue(run({ status: "queued" }));
    const { container, reload } = panel(state());
    expect(screen.getByText("Letzte Analyse #2 · 12.10.2026")).toBeInTheDocument();
    await expand(user);
    expect(screen.getByRole("radio", { name: /Ergänzen/ })).toBeChecked();
    expect(screen.getByText("Sicher · 9 offene Felder")).toBeInTheDocument();
    expect(screen.getByText("34 Nachweise · ca. 14 Min. Prüfung")).toBeInTheDocument();
    expect(screen.getByText(/Dauer ca. 2 Minuten · läuft im Hintergrund/)).toBeInTheDocument();
    // Bereiche nur bei „Bereich neu erfassen“, Zurücksetzen nur bei „Vollständig“.
    expect(screen.getByRole("button", { name: "Finanzen" })).toBeDisabled();
    expect(screen.queryByRole("checkbox", { name: /Bestätigungen zurücksetzen/ })).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Manuell gesetzte Werte schützen/ })).toBeChecked();
    await user.type(screen.getByRole("textbox", { name: "Hinweis an die KI (optional)" }), "Preisstaffel steht auf Seite 7");
    await user.type(screen.getByRole("textbox", { name: "Seiten" }), "5–9, 12");
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Analyse starten" }));
    expect(api.startReextraction).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({
      mode: "supplement", fields: [], sections: [], page_hint: [5, 6, 7, 8, 9, 12], hint: "Preisstaffel steht auf Seite 7",
      protect_manual: true, reset_confirmations: false,
    }));
    await waitFor(() => expect(reload).toHaveBeenCalled());
  });

  it("Modus per Tastatur wählen; Bereiche verlangen eine Auswahl", async () => {
    const user = userEvent.setup();
    api.startReextraction.mockResolvedValue(run({ status: "queued" }));
    panel(state());
    await expand(user);
    screen.getByRole("radio", { name: /Bereich neu erfassen/ }).focus();
    await user.keyboard(" ");
    expect(screen.getByRole("radio", { name: /Bereich neu erfassen/ })).toBeChecked();
    expect(screen.getByRole("button", { name: "Analyse starten" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Finanzen" }));
    expect(screen.getByRole("button", { name: "Finanzen" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("1 Bereich gewählt")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Analyse starten" }));
    expect(api.startReextraction).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ mode: "sections", sections: ["cost"] }));
  });

  it("„Bestätigungen zurücksetzen“ nur bei „Vollständig“ und erst nach Rückfrage mit Anzahl", async () => {
    const user = userEvent.setup();
    api.startReextraction.mockResolvedValue(run({ status: "queued" }));
    panel(state());
    await expand(user);
    await user.click(screen.getByRole("radio", { name: /Vollständig neu bewerten/ }));
    const reset = screen.getByRole("checkbox", { name: /Bestätigungen zurücksetzen/ });
    await user.click(reset);
    const dialog = screen.getByRole("dialog", { name: "Bestätigungen zurücksetzen?" });
    expect(within(dialog).getByText(/alle 34 Nachweise/)).toBeInTheDocument();
    expect(reset).not.toBeChecked();
    await user.click(within(dialog).getByRole("button", { name: "Zurücksetzen" }));
    expect(reset).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Analyse starten" }));
    expect(api.startReextraction).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ mode: "full", reset_confirmations: true }));
  });

  it("ohne leere Angaben ist „Ergänzen“ gesperrt", async () => {
    const user = userEvent.setup();
    panel(state({ open_fields: 0 }));
    await expand(user);
    expect(screen.getByRole("radio", { name: /Ergänzen/ })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /Bereich neu erfassen/ })).toBeChecked();
  });

  it("„Im Dokument suchen“ bereitet Ergänzen mit genau diesem Feld vor", async () => {
    const user = userEvent.setup();
    api.startReextraction.mockResolvedValue(run({ status: "queued" }));
    nav.params = new URLSearchParams("tab=documents&subtab=document&abschnitt=reextraction&suchen=notice_period");
    panel(state({ field_search: { notice_period_value: [{ key: "termination.cancellation_period", label: "Kündigungsfrist" }] } }));
    expect(await screen.findByText(/Gesucht: Kündigungsfrist/)).toBeInTheDocument();
    expect(nav.replace).toHaveBeenCalledWith("/contracts/c-1?tab=documents&subtab=document&abschnitt=reextraction", { scroll: false });
    expect(screen.getByText("Sicher · 1 gesuchte Angabe")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Analyse starten" }));
    expect(api.startReextraction).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ mode: "supplement", fields: ["termination.cancellation_period"] }));
  });
});

describe("Erneut aus dem Dokument erfassen – läuft", () => {
  it("zeigt Analyse, Schritt, Fortschritt, Start und Abbrechen", async () => {
    const user = userEvent.setup();
    api.cancelReextraction.mockResolvedValue({ status: "running", cancel_requested: true });
    panel(state({ run: run({ status: "running", progress: { step: 2, steps: 4, label: "Finanzen", found: 4 }, finished_at: null }) }));
    expect(screen.getByText("Läuft")).toBeInTheDocument();
    expect(screen.getByText(/Schritt 2 von 4 · Finanzen · bisher 4 Angaben erkannt/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Fortschritt der Analyse" })).toHaveAttribute("aria-valuenow", "38");
    expect(screen.getByText(/Gestartet .* von Ahmad/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyse starten" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(api.cancelReextraction).toHaveBeenCalledWith("test-klinik", "c-1", "run-3");
  });

  it("wartet in der Warteschlange", () => {
    panel(state({ run: run({ status: "queued", queue_position: 2, started_at: null }) }));
    expect(screen.getByText(/wartet – 2 Analysen vor dieser/)).toBeInTheDocument();
  });
});

describe("Erneut aus dem Dokument erfassen – Ergebnis", () => {
  it("vier Kacheln, Tabelle je Art, Aktionen je Zeile und axe", async () => {
    const user = userEvent.setup();
    const onShowPage = vi.fn();
    const onReviewProposals = vi.fn();
    api.applyReextraction.mockResolvedValue({ applied: 1, keys: ["sla.response_time"], message: "1 Angabe(n) übernommen." });
    api.decideReextraction.mockResolvedValue({ decided: 1, status: "ready" });
    const { container } = panel(state({ run: run(), rows: ROWS }), { onShowPage, onReviewProposals });
    expect(screen.getByRole("heading", { name: "Ergebnis der Analyse #3" })).toBeInTheDocument();
    expect(screen.getByText(/Ergänzen · 18\.10\.2026 .* · noch nichts übernommen/)).toBeInTheDocument();
    expect(screen.getByText("unverändert – nichts zu tun").previousSibling).toHaveTextContent("2");
    expect(screen.getByText("neu gefunden").previousSibling).toHaveTextContent("1");
    expect(screen.getByText("nicht mehr gefunden", { selector: ".ra-tile span" }).previousSibling).toHaveTextContent("1");
    expect(screen.getByText("1 von Hand gepflegte Angabe ist geschützt und wurden nicht vorgeschlagen.")).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByText("96 %")).toBeInTheDocument();
    expect(within(table).getByText("78 %")).toBeInTheDocument();
    expect(within(table).queryByText("Laufzeit")).not.toBeInTheDocument(); // unverändert: nicht in der Liste
    // Bereiche heißen wie die Reiter der Vertragsakte.
    expect(within(within(table).getByRole("row", { name: /Preisanpassung/ })).getByText("Finanzen")).toBeInTheDocument();
    expect(within(within(table).getByRole("row", { name: /Ansprechpartner/ })).getByText("Vertragsdaten")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();

    const newRow = within(table).getByRole("row", { name: /Reaktionszeit/ });
    await user.click(within(newRow).getByRole("button", { name: "Quelle" }));
    expect(onShowPage).toHaveBeenCalledWith(5);
    await user.click(within(newRow).getByRole("button", { name: "Übernehmen" }));
    expect(api.applyReextraction).toHaveBeenCalledWith("test-klinik", "c-1", "run-3", ["sla.response_time"]);

    await user.click(within(within(table).getByRole("row", { name: /Preisanpassung/ })).getByRole("button", { name: "Vergleichen" }));
    expect(onReviewProposals).toHaveBeenCalledWith("costs.price_adjustment_clause");
    const gone = within(table).getByRole("row", { name: /Ansprechpartner/ });
    expect(within(gone).getByText("nicht mehr gefunden")).toBeInTheDocument();
    await user.click(within(gone).getByRole("button", { name: "Behalten" }));
    expect(api.decideReextraction).toHaveBeenCalledWith("test-klinik", "c-1", "run-3", ["identity.contact_person"], "kept_old");

    await user.click(screen.getByRole("button", { name: "Vorschläge prüfen (3)" }));
    expect(onReviewProposals).toHaveBeenCalledWith(null);
  });

  it("„Alle unveränderten bestätigen“ fragt mit Anzahl (nur sichere, nicht geschützte)", async () => {
    const user = userEvent.setup();
    api.confirmUnchanged.mockResolvedValue({ confirmed: 1, facts: 1 });
    panel(state({ run: run(), rows: ROWS }));
    await user.click(screen.getByRole("button", { name: "Alle unveränderten bestätigen (1)" }));
    const dialog = screen.getByRole("dialog", { name: "Alle unveränderten bestätigen?" });
    await user.click(within(dialog).getByRole("button", { name: "1 bestätigen" }));
    expect(api.confirmUnchanged).toHaveBeenCalledWith("test-klinik", "c-1", "run-3");
  });

  it("entschiedene Zeilen zeigen ihre Entscheidung, „Alles verwerfen“ beendet die Analyse", async () => {
    const user = userEvent.setup();
    api.discardReextraction.mockResolvedValue({ status: "discarded" });
    const rows = ROWS.map((row) => (row.kind === "new" ? { ...row, decision: "accepted" as const } : row));
    panel(state({ run: run({ summary: { accepted: 1 } }), rows }));
    expect(screen.getByText(/1 übernommen/)).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /Reaktionszeit/ })).getByText("Übernommen")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Alles verwerfen" }));
    expect(api.discardReextraction).toHaveBeenCalledWith("test-klinik", "c-1", "run-3");
  });

  it("nach „Bestätigungen zurücksetzen“ führt ein Hinweis zur Nachweisprüfung", async () => {
    const user = userEvent.setup();
    const onReviewEvidence = vi.fn();
    panel(state({ run: run({ reset_confirmations: true, mode: "full", mode_label: "Vollständig neu bewerten" }), rows: ROWS }), { onReviewEvidence });
    await user.click(screen.getByRole("button", { name: "Nachweise prüfen" }));
    expect(onReviewEvidence).toHaveBeenCalled();
  });

  it("ein veraltetes Ergebnis kann nicht übernommen werden", () => {
    panel(state({ run: run({ stale: true }), rows: ROWS }));
    expect(screen.getByText(/Vertragsdaten wurden inzwischen geändert/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Vorschläge prüfen/ })).toBeDisabled();
  });

  it("ohne Vorschläge: ehrliche Meldung und nächste Schritte", async () => {
    const user = userEvent.setup();
    const onMarkInDocument = vi.fn();
    panel(state({ run: run(), rows: [ROWS[3]] }), { onMarkInDocument });
    expect(screen.getByText("Keine zusätzlichen Angaben gefunden.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Stelle im Dokument markieren" }));
    expect(onMarkInDocument).toHaveBeenCalled();
  });
});

describe("Verlauf und Zurücknahme", () => {
  it("zeigt Analysen mit Nummer und bietet „Auf diesen Stand zurück“ mit Vorschau", async () => {
    const user = userEvent.setup();
    api.getRollbackPreview.mockResolvedValue({ target: 1, entries: [
      { key: "dates.start_date", label: "Vertragsbeginn", number: 2, current: "01.01.2025", restored: null, conflict: false },
      { key: "identity.supplier", label: "Vertragspartner", number: 2, current: "X", restored: "Y", conflict: true },
    ] });
    api.rollbackToAnalysis.mockResolvedValue({ number: 4, restored: ["dates.start_date"], skipped: 1, message: "Stand von Analyse #1 wiederhergestellt." });
    const onApplied = vi.fn();
    panel(state(), { onApplied });
    await expand(user);
    const history = screen.getByRole("region", { name: "Verlauf der Analysen" });
    expect(within(history).getByText("#2")).toBeInTheDocument();
    expect(within(history).getByText(/Erstanalyse · 05\.10\.2026 · beim Import/)).toBeInTheDocument();
    await user.click(within(history).getByRole("button", { name: "Auf diesen Stand zurück" }));
    const dialog = await screen.findByRole("dialog", { name: "Auf Stand von Analyse #1 zurück?" });
    expect(await within(dialog).findByText("Vertragsbeginn")).toBeInTheDocument();
    expect(within(dialog).getByText(/Bleiben unverändert, weil sie später geändert wurden: Vertragspartner/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "1 Angabe zurücknehmen" }));
    expect(api.rollbackToAnalysis).toHaveBeenCalledWith("test-klinik", "c-1", 1);
    await waitFor(() => expect(onApplied).toHaveBeenCalled());
  });
});

describe("Hinweise außerhalb der Karte", () => {
  it("Kopfhinweis nennt die Analyse und die offenen Vorschläge", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    render(<ReextractionBanner state={state({ run: run(), rows: ROWS })} onOpen={onOpen} />);
    expect(screen.getByText("Analyse #3 fertig: 3 Vorschläge zum Prüfen.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Prüfen" }));
    expect(onOpen).toHaveBeenCalled();
  });

  it("Offene Punkte: fertige Analyse und neues Dokument", () => {
    const points = buildOpenPoints({ gaps: [], tasks: [], warnings: [], scopeToCheck: 0, scopeTotal: 0, analysis: { number: 3, open: 6, newDocument: "Nachtrag.pdf" } });
    const analysis = points.find((point) => point.key === "analysis");
    expect(analysis?.title).toBe("Analyse #3 fertig");
    expect(analysis?.why).toMatch(/^6 Vorschläge prüfen/);
    expect(analysis?.target).toEqual({ tab: "documents", subtab: "document", section: "vorschlaege-pruefen" });
    const fresh = points.find((point) => point.key === "analysis-new-document");
    expect(fresh?.title).toBe("Neues Dokument – Ergänzen starten?");
    expect(fresh?.why).toContain("„Nachtrag.pdf“");
    expect(buildOpenPoints({ gaps: [], tasks: [], warnings: [], scopeToCheck: 0, scopeTotal: 0, analysis: { number: null, open: 0, newDocument: null } })).toEqual([]);
  });

  it("„Offene Punkte“ bietet die Suche nach fehlenden Angaben an", () => {
    render(<OpenPoints contractId="c-1" points={[]} searchHref="/contracts/c-1?tab=documents&subtab=document&abschnitt=reextraction&suchen=fehlende" onOpen={vi.fn()} />);
    expect(screen.getByRole("link", { name: "Fehlende Angaben im Dokument suchen" })).toHaveAttribute("href", "/contracts/c-1?tab=documents&subtab=document&abschnitt=reextraction&suchen=fehlende");
  });
});

describe("Vorschläge prüfen (geführt)", () => {
  function mode(extra: Partial<Parameters<typeof ProposalReviewMode>[0]> = {}) {
    const props = {
      contractId: "c-1", orgSlug: "test-klinik", contractTitle: "Impella", run: run(), proposals: ROWS, startKey: null, viewer: <div>Original</div>,
      canDecide: true, onShow: vi.fn(), onExit: vi.fn(), onChanged: vi.fn(), onEditManually: vi.fn(), ...extra,
    };
    return { ...render(<ProposalReviewMode {...props} />), props };
  }
  const panelRegion = () => screen.getByRole("region", { name: "Aktueller Vorschlag" });

  it("geht die offenen Vorschläge durch: Übernehmen, Behalten (Taste B), Unterschiede, Fundstelle, axe", async () => {
    const user = userEvent.setup();
    api.applyReextraction.mockResolvedValue({ applied: 1, keys: [], message: "" });
    api.decideReextraction.mockResolvedValue({ decided: 1, status: "ready" });
    const { container, props } = mode();
    expect(screen.getByText("Vorschlag 1 von 3")).toBeInTheDocument();
    expect(within(panelRegion()).getByRole("heading", { name: "Reaktionszeit" })).toBeInTheDocument();
    expect(props.onShow).toHaveBeenCalledWith(expect.objectContaining({ page: 5 }));
    expect(await axe(container)).toHaveNoViolations();
    await user.click(within(panelRegion()).getByRole("button", { name: /^Übernehmen/ }));
    expect(api.applyReextraction).toHaveBeenCalledWith("test-klinik", "c-1", "run-3", ["sla.response_time"]);
    await waitFor(() => expect(within(panelRegion()).getByRole("heading", { name: "Preisanpassung" })).toBeInTheDocument());
    expect(container.querySelectorAll("mark.erm-diff").length).toBeGreaterThan(0);
    await user.keyboard("b");
    expect(api.decideReextraction).toHaveBeenCalledWith("test-klinik", "c-1", "run-3", ["costs.price_adjustment_clause"], "kept_old");
    await waitFor(() => expect(within(panelRegion()).getByRole("heading", { name: "Ansprechpartner" })).toBeInTheDocument());
    expect(within(panelRegion()).getByText(/Nicht mehr gefunden – der gespeicherte Wert bleibt/)).toBeInTheDocument();
    await user.keyboard("s");
    expect(within(panelRegion()).getByRole("heading", { name: "Vorschläge entschieden" })).toBeInTheDocument();
    expect(within(panelRegion()).getByText(/2 von 3 entschieden; 1 übersprungen/)).toBeInTheDocument();
    expect(props.onChanged).toHaveBeenCalledTimes(2);
  });

  it("startet beim gewählten Vorschlag; ohne Recht nur lesen", () => {
    mode({ startKey: "identity.contact_person", canDecide: false });
    expect(within(panelRegion()).getByRole("heading", { name: "Ansprechpartner" })).toBeInTheDocument();
    expect(within(panelRegion()).getByText(/Nur Lesen/)).toBeInTheDocument();
  });

  it("„Selbst erfassen“ merkt die Entscheidung und öffnet das Feld", async () => {
    const user = userEvent.setup();
    api.decideReextraction.mockResolvedValue({ decided: 1, status: "ready" });
    const rows = [proposal("dates.start_date", "Vertragsbeginn", "deviating", "01.04.2025", "01.05.2025", { register_keys: ["term_start_date"] })];
    const { props } = mode({ proposals: rows });
    await user.click(within(panelRegion()).getByRole("button", { name: /Selbst erfassen/ }));
    expect(api.decideReextraction).toHaveBeenCalledWith("test-klinik", "c-1", "run-3", ["dates.start_date"], "manual");
    await waitFor(() => expect(props.onEditManually).toHaveBeenCalledWith("term_start_date"));
  });
});

describe("Hilfsfunktionen", () => {
  it("Seitenangabe versteht Einzelseiten, Bereiche, Listen und „alle“", () => {
    expect(parsePages("")).toEqual([]);
    expect(parsePages("alle")).toEqual([]);
    expect(parsePages("4")).toEqual([4]);
    expect(parsePages("5–9, 12")).toEqual([5, 6, 7, 8, 9, 12]);
    expect(parsePages("0")).toBeNull();
    expect(parsePages("6-4")).toBeNull();
    expect(parsePages("1-40")).toBeNull();
    expect(parsePages("Seite 4")).toBeNull();
  });

  it("offene und sichere unveränderte Vorschläge", () => {
    expect(openProposals(ROWS).map((row) => row.key)).toEqual(["sla.response_time", "costs.price_adjustment_clause", "identity.contact_person"]);
    expect(safeUnchanged(ROWS).map((row) => row.key)).toEqual(["dates.duration"]);
  });
});
