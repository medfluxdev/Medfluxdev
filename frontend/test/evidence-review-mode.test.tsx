import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EvidenceReviewMode from "@/components/contracts/detail/EvidenceReviewMode";
import type { EvidenceRef, FactReviewStateDto } from "@/lib/contract-detail-types";
import type { EvidenceReviewItem } from "@/lib/domain-api/register";
import { evidenceNumbers, factsByEvidence } from "@/lib/evidence";

const api = vi.hoisted(() => ({ reviewContractFact: vi.fn(), saveEvidenceReview: vi.fn(), logEvidenceRound: vi.fn(), getDocumentPageText: vi.fn(), startReextraction: vi.fn() }));
vi.mock("@/lib/domain-api/reextraction", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/reextraction")>()),
  startReextraction: api.startReextraction,
}));
vi.mock("@/lib/domain-api/contracts", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/contracts")>()),
  reviewContractFact: api.reviewContractFact,
}));
vi.mock("@/lib/domain-api/register", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/register")>()),
  saveEvidenceReview: api.saveEvidenceReview,
  logEvidenceRound: api.logEvidenceRound,
  getDocumentPageText: api.getDocumentPageText,
}));

const ref = (id: string, page: number, field: string, snippet: string, extra: Partial<EvidenceRef> = {}): EvidenceRef => ({
  evidence_id: id, field_ref: field, document_version_id: "doc-1", original_filename: "Full-Service-Vertrag.pdf", page,
  source_type: "page", paragraph_index: null, table_index: null, snippet, confidence: 0.97, requires_review: false,
  bbox: { x0: 10, y0: 10 + page, x1: 60, y1: 20 + page }, precision: "coarse", geometry_normalized: false, bbox_space: "pdf_points",
  supports_exact_navigation: true, location: "exact", text_verified: true, ...extra,
});
const fact = (key: string, label: string, original: unknown, ids: string[], extra: Partial<FactReviewStateDto> = {}): FactReviewStateDto => ({
  fact_key: key, label_de: label, present: true, state: "unreviewed", state_label_de: "Ungeprüft", original_value: original, effective_value: original,
  reviewer_display_name: null, reviewer_identity_type: null, reviewed_at: null, evidence_ref: null, has_history: false,
  evidence_count: ids.length, linked_evidence: [], linked_evidence_refs: ids, needs_evidence: false, is_critical: false, ...extra,
});

// Lesereihenfolge: Kosten (S. 1) vor Auftraggeber (S. 1, darunter) vor Vertragsbeginn (S. 2) – geführt: Partner, Laufzeit, Kosten.
const EVIDENCE = [
  ref("e-cost", 1, "costs.annual_cost.evidence.0", "Jährlich 8.000,00 EUR", { bbox: { x0: 10, y0: 5, x1: 60, y1: 9 } }),
  ref("e-customer", 1, "identity.customer.evidence.3", "Krankenhaus Nordwest GmbH Frankfurt Steinbacher Hohl 2-26 D-60488 Frankfurtam Main"),
  ref("e-start", 2, "dates.start_date.evidence.0", "beginnt am 01.04.2025", { location: "approx", text_verified: false }),
];
const FACTS = [
  fact("evidence.identity.customer", "Nachweis: Auftraggeber", EVIDENCE[1].snippet, ["e-customer"], { is_evidence_item: true }),
  fact("dates.start_date", "Vertragsbeginn", "2025-04-01", ["e-start"], { register_field: "term_start_date", stored_value: "01.05.2025" }),
  fact("costs.annual", "Jahreskosten", "8000.0", ["e-cost"]),
];

function renderMode(overrides: Partial<Parameters<typeof EvidenceReviewMode>[0]> = {}) {
  const props = {
    contractId: "c-1", orgSlug: "test-klinik", contractTitle: "Impella® AIC System", evidence: EVIDENCE, numbers: evidenceNumbers(EVIDENCE),
    factByEvidence: factsByEvidence(FACTS), reviews: new Map<string, EvidenceReviewItem>(), startId: null, canReview: true,
    viewer: <div>Original</div>, onShow: vi.fn(), onExit: vi.fn(), onReload: vi.fn(), onSearchAgain: vi.fn(), ...overrides,
  };
  return { ...render(<EvidenceReviewMode {...props} />), props };
}
const panel = () => screen.getByRole("region", { name: "Aktueller Nachweis" });

describe("Nachweise prüfen (geführt)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.reviewContractFact.mockResolvedValue({});
    api.saveEvidenceReview.mockResolvedValue({ items: [] });
    api.logEvidenceRound.mockResolvedValue({ summary: "" });
    api.getDocumentPageText.mockResolvedValue({ page: 2, pages: [1, 2], text: "Der Vertrag beginnt am 01.06.2025.", fields: [] });
  });

  it("führt nach Abschnitt: Partner zuerst; Abgleich ohne gespeicherten Wert, Leiste, Fortschritt und axe", async () => {
    const { container, props } = renderMode();
    expect(screen.getByText("Nachweis 1 von 3")).toBeInTheDocument();
    expect(screen.getByText("Full-Service-Vertrag.pdf · Impella® AIC System")).toBeInTheDocument();
    expect(within(panel()).getByRole("heading", { name: /Auftraggeber/ })).toBeInTheDocument();
    expect(within(panel()).getByText("Vertragsdaten")).toBeInTheDocument();
    expect(within(panel()).getByText("Noch nicht geprüft")).toBeInTheDocument();
    expect(within(panel()).getByText("KI-Sicherheit 97 %")).toBeInTheDocument();
    // Reiner Nachweis: kein gespeicherter Wert; Nummer wie in der Liste (Lesereihenfolge: 2).
    expect(within(panel()).getByText("Kein gespeicherter Wert")).toBeInTheDocument();
    expect(within(panel()).getByText("Wortlaut steht an dieser Stelle im Dokument.")).toBeInTheDocument();
    expect(within(panel()).getByLabelText("Nachweis 2")).toBeInTheDocument();
    expect(props.onShow).toHaveBeenCalledWith(EVIDENCE[1]);
    expect(container.querySelectorAll(".erm-seg i")).toHaveLength(3);
    expect(container.querySelector(".erm-seg i.is-current")).not.toBeNull();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Bestätigen speichert Angabe und Nachweis, geht weiter und meldet es; Abweichung zeigt Wortunterschiede", async () => {
    const user = userEvent.setup();
    const { container, props } = renderMode();
    await user.click(within(panel()).getByRole("button", { name: /^Bestätigen/ }));
    expect(api.reviewContractFact).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "evidence.identity.customer", action: "confirmed", evidence_ref: "e-customer" }));
    expect(api.saveEvidenceReview).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ evidence_id: "e-customer", status: "confirmed" }));
    expect(props.onReload).toHaveBeenCalled();
    await waitFor(() => expect(within(panel()).getByRole("heading", { name: /Vertragsbeginn/ })).toBeInTheDocument());
    expect(screen.getByText("Bestätigt · weiter zu Vertragsbeginn")).toBeInTheDocument();
    expect(container.querySelector(".erm-seg i.is-confirmed")).not.toBeNull();
    // Vertragsbeginn: Dokument 01.04.2025, gespeichert 01.05.2025 → abweichend, Unterschied markiert; ungefähre Lage.
    expect(within(panel()).getByText(/Weicht ab/)).toBeInTheDocument();
    expect(container.querySelectorAll("mark.erm-diff")).toHaveLength(2);
    expect(within(panel()).getByText("Ungefähre Lage")).toBeInTheDocument();
    expect(screen.getByText("1 bestätigt · 0 abweichend")).toBeInTheDocument();
  });

  it("Fundstelle zeigt den gemessenen Anteil des Wortlauts in Prozent; ohne Messung keine Leiste", () => {
    const evidence = [
      ref("e-customer", 1, "identity.customer.evidence.3", EVIDENCE[1].snippet, { confidence: null, text_match: 1 }),
      ref("e-start", 2, "dates.start_date.evidence.0", "beginnt am 01.04.2025", { location: "approx", text_verified: false, text_match: 0.67 }),
    ];
    const { unmount } = renderMode({ evidence, numbers: evidenceNumbers(evidence) });
    expect(within(panel()).getByText("100 % · wörtlich")).toBeInTheDocument();
    expect(within(panel()).queryByText(/^KI-Sicherheit$/)).not.toBeInTheDocument();
    unmount();
    renderMode({ evidence, numbers: evidenceNumbers(evidence), startId: "e-start" });
    expect(within(panel()).getByText("67 %")).toBeInTheDocument();

  });

  it("Ende ohne offene Punkte: „Prüfung abgeschlossen“, keine offenen Prüfpunkte, „Vertrag ansehen“", async () => {
    const user = userEvent.setup();
    const evidence = [EVIDENCE[1]];
    const { props } = renderMode({ evidence, numbers: evidenceNumbers(evidence) });
    await user.click(within(panel()).getByRole("button", { name: /^Bestätigen/ }));
    expect(await within(panel()).findByRole("heading", { name: "Prüfung abgeschlossen" })).toBeInTheDocument();
    expect(within(panel()).getByText("Sie haben 1 Angabe geprüft.")).toBeInTheDocument();
    expect(within(panel()).getByText("Keine offenen Prüfpunkte")).toBeInTheDocument();
    expect(within(panel()).queryByText(/Gespeicherte Angabe/)).not.toBeInTheDocument();
    await user.click(within(panel()).getByRole("button", { name: "Vertrag ansehen" }));
    expect(props.onExit).toHaveBeenCalled();
  });

  it("ohne gemessenen Anteil keine Fundstellen-Leiste", () => {
    renderMode();
    expect(within(panel()).queryByText("Fundstelle")).not.toBeInTheDocument();
  });

  it("gleiche Werte trotz fehlender Leerzeichen stimmen überein", () => {
    renderMode({ startId: "e-cost", factByEvidence: factsByEvidence([...FACTS.slice(0, 2), fact("costs.annual", "Jahreskosten", "8000.0", ["e-cost"], { effective_value: "8000" })]) });
    expect(within(panel()).getByText("Dokument und MedFlux stimmen überein.")).toBeInTheDocument();
  });

  it("Abweichung: „Dokument hat recht“ übernimmt den erkannten Wert", async () => {
    const user = userEvent.setup();
    renderMode({ startId: "e-start" });
    await user.click(within(panel()).getByRole("button", { name: /^Abweichung/ }));
    expect(within(panel()).getByRole("radio", { name: /Dokument hat recht/ })).toBeChecked();
    await user.type(within(panel()).getByLabelText("Notiz (optional)"), "Vertrag nachträglich geändert");
    await user.click(within(panel()).getByRole("button", { name: "Übernehmen · Weiter" }));
    expect(api.reviewContractFact).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({
      fact_key: "dates.start_date", action: "corrected", corrected_value: "01.04.2025", note: "Vertrag nachträglich geändert",
    }));
    expect(api.saveEvidenceReview).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ evidence_id: "e-start", status: "document", note: "Vertrag nachträglich geändert" }));
  });

  it("Abweichung: „MedFlux hat recht“ bestätigt den gespeicherten Wert und markiert den Nachweis als geklärt", async () => {
    const user = userEvent.setup();
    renderMode({ startId: "e-start" });
    await user.click(within(panel()).getByRole("button", { name: /^Abweichung/ }));
    await user.click(within(panel()).getByRole("radio", { name: /MedFlux hat recht/ }));
    await user.click(within(panel()).getByRole("button", { name: "Übernehmen · Weiter" }));
    expect(api.reviewContractFact).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "dates.start_date", action: "confirmed" }));
    expect(api.saveEvidenceReview).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ status: "medflux" }));
  });

  it("Abweichung: „Beides falsch“ verlangt einen Wert, übernimmt markierten Seitentext und speichert von Hand", async () => {
    const user = userEvent.setup();
    renderMode({ startId: "e-start" });
    await user.keyboard("a");
    await user.click(within(panel()).getByRole("radio", { name: /Beides falsch/ }));
    const input = within(panel()).getByLabelText("Richtiger Wert");
    await user.clear(input);
    expect(within(panel()).getByRole("button", { name: "Übernehmen · Weiter" })).toBeDisabled();
    await user.click(within(panel()).getByRole("button", { name: "Text im Dokument markieren und übernehmen" }));
    expect(await within(panel()).findByRole("document", { name: "Text der Seite 2" })).toHaveTextContent("beginnt am 01.06.2025");
    await user.type(input, "01.06.2025");
    await user.click(within(panel()).getByRole("button", { name: "Übernehmen · Weiter" }));
    expect(api.reviewContractFact).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ action: "corrected", corrected_value: "01.06.2025" }));
    expect(api.saveEvidenceReview).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ status: "manual" }));
  });

  it("Filter in „Alle Nachweise“ beschränkt die Prüfung auf die Auswahl; × hebt ihn auf", async () => {
    const user = userEvent.setup();
    renderMode();
    expect(screen.getByText("Nachweis 1 von 3")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Alle Nachweise/ }));
    const drawer = screen.getByRole("dialog", { name: "Alle Nachweise" });
    // Schmales Seitenfenster: Abschnitt unter dem Feldnamen, keine eigene Spalte.
    expect(within(drawer).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual(["#", "Feld · Abschnitt", "Seite", "Status"]);
    // Abschnitte heißen wie die Reiter der Vertragsakte, in deren Reihenfolge.
    expect(within(within(drawer).getByRole("combobox", { name: "Nach Abschnitt filtern" })).getAllByRole("option").map((option) => option.textContent))
      .toEqual(["Alle Abschnitte", "Vertragsdaten", "Fristen & Aufgaben", "Finanzen"]);
    await user.selectOptions(within(drawer).getByRole("combobox", { name: "Nach Abschnitt filtern" }), "Finanzen");
    expect(within(drawer).getByText(/Die Prüfung geht nur die gefilterten Nachweise durch \(1\)/)).toBeInTheDocument();
    expect(within(drawer).getAllByRole("row")).toHaveLength(2); // Kopf + 1
    await user.keyboard("{Escape}");
    // Nur noch der Kosten-Nachweis; Blättern bleibt in der Auswahl.
    expect(screen.getByRole("button", { name: "Nur Finanzen · 1" })).toHaveAttribute("title", "Filter ändern");
    expect(screen.getByText("Nachweis 1 von 1")).toBeInTheDocument();
    expect(within(panel()).getByRole("heading", { name: /Jahreskosten/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Filter aufheben, alle Nachweise prüfen" }));
    expect(screen.getByText(/Nachweis \d von 3/)).toBeInTheDocument();
    expect(within(panel()).getByRole("heading", { name: /Jahreskosten/ })).toBeInTheDocument(); // bleibt beim aktuellen Nachweis
  });

  it("Filter nach Prüfstand: „Offen“ hält die Auswahl fest, auch wenn ein Nachweis bestätigt wird", async () => {
    const user = userEvent.setup();
    renderMode();
    await user.click(screen.getByRole("button", { name: /Alle Nachweise/ }));
    const drawer = screen.getByRole("dialog", { name: "Alle Nachweise" });
    await user.click(within(drawer).getByRole("button", { name: /^Offen/ }));
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Nur Offen · 3" })).toBeInTheDocument();
    await user.click(within(panel()).getByRole("button", { name: /^Bestätigen/ }));
    await waitFor(() => expect(screen.getByText("Nachweis 2 von 3")).toBeInTheDocument());
  });

  it("Tasten: A öffnet, Esc schließt; S überspringt; → blättert; Enter bestätigt", async () => {
    const user = userEvent.setup();
    renderMode();
    await user.keyboard("a");
    expect(within(panel()).getByRole("group", { name: "Was gilt?" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(within(panel()).queryByRole("group", { name: "Was gilt?" })).not.toBeInTheDocument();
    await user.keyboard("s");
    expect(api.saveEvidenceReview).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ evidence_id: "e-customer", status: "skipped" }));
    expect(api.reviewContractFact).not.toHaveBeenCalled();
    await waitFor(() => expect(within(panel()).getByRole("heading", { name: /Vertragsbeginn/ })).toBeInTheDocument());
    await user.keyboard("{ArrowRight}");
    expect(within(panel()).getByRole("heading", { name: /Jahreskosten/ })).toBeInTheDocument();
    within(panel()).getByRole("heading", { name: /Jahreskosten/ }).focus();
    await user.keyboard("{Enter}");
    expect(api.saveEvidenceReview).toHaveBeenLastCalledWith("test-klinik", "c-1", expect.objectContaining({ evidence_id: "e-cost", status: "confirmed" }));
  });

  it("„Alle Nachweise“: Status aus der Prüfung, Filter, Sprung per Klick, Esc schließt", async () => {
    const user = userEvent.setup();
    const reviews = new Map<string, EvidenceReviewItem>([
      ["e-start", { evidence_id: "e-start", fact_key: "dates.start_date", status: "medflux", status_label: "Abweichend · geklärt", note: null, reviewed_by_name: "Prüfer", reviewed_at: "2026-10-18T10:00:00Z" }],
      ["e-cost", { evidence_id: "e-cost", fact_key: "costs.annual", status: "skipped", status_label: "Übersprungen", note: null, reviewed_by_name: "Prüfer", reviewed_at: "2026-10-18T10:00:00Z" }],
    ]);
    renderMode({ reviews });
    await user.click(screen.getByRole("button", { name: /Alle Nachweise/ }));
    const drawer = screen.getByRole("dialog", { name: "Alle Nachweise" });
    const table = within(drawer).getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(4);
    expect(within(table).getByText("Abweichend")).toBeInTheDocument();
    expect(within(table).getByText("Übersprungen")).toBeInTheDocument();
    expect(within(table).getByText("Noch nicht geprüft")).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: /^Abweichend/ }));
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    await user.click(within(table).getByRole("button", { name: "Vertragsbeginn" }));
    expect(screen.queryByRole("dialog", { name: "Alle Nachweise" })).not.toBeInTheDocument();
    expect(within(panel()).getByRole("heading", { name: /Vertragsbeginn/ })).toBeInTheDocument();
    expect(within(panel()).getByText("Abweichend · geklärt")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Alle Nachweise/ }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Alle Nachweise" })).not.toBeInTheDocument();
  });

  it("Ende der Runde: Zusammenfassung, Eintrag im Verlauf, „Übersprungene prüfen“", async () => {
    const user = userEvent.setup();
    const { props } = renderMode();
    await user.click(within(panel()).getByRole("button", { name: /^Bestätigen/ }));
    await waitFor(() => expect(within(panel()).getByRole("heading", { name: /Vertragsbeginn/ })).toBeInTheDocument());
    await user.click(within(panel()).getByRole("button", { name: /^Abweichung/ }));
    await user.click(within(panel()).getByRole("button", { name: "Übernehmen · Weiter" }));
    await waitFor(() => expect(within(panel()).getByRole("heading", { name: /Jahreskosten/ })).toBeInTheDocument());
    await user.click(within(panel()).getByRole("button", { name: /^Überspringen/ }));
    // Eine Runde mit offenen (übersprungenen) Punkten ist nur „beendet“, nicht abgeschlossen.
    expect(await within(panel()).findByRole("heading", { name: "Runde beendet" })).toBeInTheDocument();
    expect(within(panel()).getByText("Sie haben 2 Angaben geprüft und einen neuen Wert in MedFlux gespeichert; 1 übersprungen.")).toBeInTheDocument();
    expect(within(panel()).getByText(/1 Prüfpunkt ist noch offen/)).toBeInTheDocument();
    const rows = within(panel()).getByRole("heading", { name: "Ergebnis Ihrer Prüfung" }).closest("div")!.parentElement!;
    expect(within(rows).getByText("Unverändert bestätigt").nextSibling).toHaveTextContent("1 Angabe");
    expect(within(rows).getByText("Abweichung geklärt").nextSibling).toHaveTextContent("1 Angabe");
    expect(within(rows).getByText("Davon in MedFlux gespeichert").nextSibling).toHaveTextContent("1 Angabe");
    expect(within(rows).getByText("Gespeicherte Angabe")).toBeInTheDocument();
    expect(within(rows).getByText("Vertragsbeginn")).toBeInTheDocument();
    // Kein Blättern mehr am Ende der Runde.
    expect(screen.queryByRole("navigation", { name: "Nachweise blättern" })).not.toBeInTheDocument();
    expect(api.logEvidenceRound).toHaveBeenCalledWith("test-klinik", "c-1", { confirmed: 1, document: 1, skipped: 1 });
    await user.click(within(panel()).getByRole("button", { name: "Prüfung ansehen" }));
    expect(screen.getByRole("dialog", { name: "Alle Nachweise" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.click(within(panel()).getByRole("button", { name: "Übersprungene prüfen" }));
    expect(within(panel()).getByRole("heading", { name: /Jahreskosten/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Zurück zum Vertrag" }));
    expect(props.onExit).toHaveBeenCalled();
  });

  it("„Alle sicheren ≥ 0,95 bestätigen“ fragt mit Anzahl nach und bestätigt nur genau belegte, passende Nachweise", async () => {
    const user = userEvent.setup();
    renderMode();
    await user.click(screen.getByRole("button", { name: "Weitere Aktionen" }));
    await user.click(screen.getByRole("menuitem", { name: /Alle sicheren ≥ 0,95 bestätigen \(2\)/ }));
    const dialog = screen.getByRole("dialog", { name: "Alle sicheren Nachweise bestätigen?" });
    await user.click(within(dialog).getByRole("button", { name: "2 bestätigen" }));
    await waitFor(() => expect(api.saveEvidenceReview).toHaveBeenCalledTimes(2));
    expect(api.saveEvidenceReview.mock.calls.map((call) => call[2].evidence_id).sort()).toEqual(["e-cost", "e-customer"]);
  });

  it("„Nachweis neu erkennen“ liest die Seite gezielt neu, sonst die ganze Seite", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("@/lib/api");
    api.startReextraction.mockRejectedValueOnce(new ApiError("Unbekannte Angaben ausgewählt.", { status: 422 })).mockResolvedValue({});
    const started = vi.fn();
    renderMode({ canRecognize: true, onRecognizeStarted: started });
    await user.click(screen.getByRole("button", { name: "Weitere Aktionen" }));
    await user.click(screen.getByRole("menuitem", { name: "Nachweis neu erkennen" }));
    await waitFor(() => expect(started).toHaveBeenCalled());
    expect(api.startReextraction.mock.calls.map((call) => call[2])).toEqual([
      { mode: "supplement", fields: ["identity.customer"], page_hint: [1] },
      { mode: "full", page_hint: [1] },
    ]);
  });

  it("ohne Prüfrecht nur lesen und blättern", () => {
    renderMode({ canReview: false });
    expect(within(panel()).queryByRole("button", { name: /^Bestätigen/ })).not.toBeInTheDocument();
    expect(within(panel()).getByText(/Nur Lesen/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Weiter" })).toBeInTheDocument();
  });
});
