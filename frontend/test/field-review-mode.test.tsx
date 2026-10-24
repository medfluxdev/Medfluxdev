import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FieldReviewMode from "@/components/contracts/detail/FieldReviewMode";
import FieldReviewOverview from "@/components/contracts/detail/FieldReviewOverview";
import type { ContractDetailResponse, FieldReviewDto } from "@/lib/contract-detail-types";
import { WICHTIG_ALS_PFLICHT, decisionFields, groupConfirmable, levelCounts, levelOf, nextDecision, nextOpenLevel, nextOpenTier, reviewHeadline } from "@/lib/field-review";
import { candidate, evidence, field, finding, review, twoAgreeing } from "./fixtures/field-review";

const api = vi.hoisted(() => ({ decideField: vi.fn(), setFieldEvidence: vi.fn(), decideFinding: vi.fn() }));
vi.mock("@/lib/domain-api/contracts", () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock("@/components/ui/Toast", () => ({ useToast: () => toast }));

const start = field({ fact_key: "dates.start_date", label: "Vertragsbeginn", current: "01.04.2025", document_value: "01.04.2025", candidates: [candidate({ key: "2025-04-01", display: "01.04.2025", value: "01.04.2025", evidence_ids: ["s1"] })], evidence: [evidence({ evidence_id: "s1", page: 1, snippet: "Beginn: 01.04.2025" })], primary_evidence_id: "s1" });
const end = twoAgreeing();
const price = field({ fact_key: "costs.monthly_recurring", label: "Wiederkehrende Kosten (monatlich)", card: "cost", card_label: "Finanzen", current: "1.200,00 EUR", candidates: [candidate({ key: "1200", display: "1.200,00 EUR", value: "1.200,00 EUR", evidence_ids: ["p1"] })], evidence: [evidence({ evidence_id: "p1", page: 2, snippet: "1.200,00 EUR monatlich" })], primary_evidence_id: "p1" });
const sla = field({ fact_key: "sla.response_time", label: "Reaktionszeit (SLA)", tier: "important", card: "services", card_label: "Leistungen & SLA", current: "4 Stunden", is_critical: false, candidates: [candidate({ key: "4h", display: "4 Stunden", value: "4 Stunden", evidence_ids: ["r1"] })], evidence: [evidence({ evidence_id: "r1", page: 4, snippet: "Reaktionszeit 4 Stunden" })], primary_evidence_id: "r1" });
const email = field({ fact_key: "sla.sla_notes", label: "Weitere SLA-Angaben", tier: "optional", card: "services", card_label: "Leistungen & SLA", current: "Mo–Fr", is_critical: false, candidates: [candidate({ key: "mofr", display: "Mo–Fr", value: "Mo–Fr", evidence_ids: ["n1"] })], evidence: [evidence({ evidence_id: "n1", page: 4, snippet: "Mo–Fr" })], primary_evidence_id: "n1" });
const calc = field({ fact_key: "dates.latest_cancellation", label: "Letztes Kündigungsdatum", kind: "calculated", status: "waiting", status_label: "Berechnet – Eingaben offen", decision_needed: false, tier: "important", candidates: [], evidence: [], current: "30.09.2028" });

const refs = [{ evidence_id: "e1", field_ref: "dates.end_date" }, { evidence_id: "s1", field_ref: "dates.start_date" }, { evidence_id: "p1", field_ref: "costs.monthly_recurring" }] as unknown as ContractDetailResponse["evidence"];

function mode(model: FieldReviewDto, props: Partial<React.ComponentProps<typeof FieldReviewMode>> = {}) {
  const handlers = { onShow: vi.fn(), onShowPage: vi.fn(), onExit: vi.fn(), onReload: vi.fn() };
  const utils = render(<FieldReviewMode contractId="c-1" orgSlug="test-klinik" contractTitle="Wartung MRT" data={{ evidence: refs }} review={model}
    startKey={null} canReview viewer={<div>Original</div>} {...handlers} {...props} />);
  return { ...utils, ...handlers };
}

/** Antwort der API nach einer Entscheidung: das Feld ist entschieden. */
function detailAfter(model: FieldReviewDto) {
  return { contract_id: "c-1", field_review: model } as unknown as ContractDetailResponse;
}
function decided(item: ReturnType<typeof field>) {
  return { ...item, status: "decided" as const, status_label: "Entschieden", decision_needed: false, fact_state: "confirmed", reviewer: "A. Prüfer", reviewed_at: "2026-10-18T10:00:00+00:00" };
}

beforeEach(() => vi.clearAllMocks());

describe("Hilfen der Feldprüfung", () => {
  const model = review([start, end, price, sla, email, calc]);

  it("wesentliche Stufe zuerst, danach die nächste; Berechnetes zählt nicht", () => {
    expect(nextOpenTier(model)).toBe("essential");
    expect(decisionFields(model, "essential").map((item) => item.fact_key)).toEqual(["dates.start_date", "dates.end_date", "costs.monthly_recurring"]);
    expect(decisionFields(model).some((item) => item.kind === "calculated")).toBe(false);
    expect(nextDecision(model, "essential", "dates.end_date")?.fact_key).toBe("costs.monthly_recurring");
    expect(nextDecision(model, "essential", "costs.monthly_recurring")?.fact_key).toBe("dates.start_date");
    const only = review([start]);
    expect(nextDecision(only, "essential", "dates.start_date")).toBeNull();
  });

  it("die Überschrift behauptet nie „alles geprüft“", () => {
    expect(reviewHeadline(model)).toEqual({ tone: "ai", text: "3 wesentliche Entscheidungen offen" });
    const done = review([decided(start), decided(end), decided(price), sla]);
    const headline = reviewHeadline(done)!;
    expect(headline.text).toBe("Wesentliche Prüfung abgeschlossen");
    expect(headline.text).not.toMatch(/alle|verifiziert|vollständig/i);
  });

  it("Gruppenbestätigung nur für eindeutige, genau belegte, unstrittige Felder derselben Karte", () => {
    const sibling = field({ ...price, fact_key: "costs.vat_rate", label: "MwSt.-Satz" });
    const disputed = field({ ...price, fact_key: "costs.currency", label: "Währung", status: "conflict", candidates: [price.candidates[0], candidate({ key: "chf", display: "CHF", is_current: false })] });
    const roughly = field({ ...price, fact_key: "payment.billing_interval", label: "Zahlungsrhythmus", source_state: "located" });
    const other = field({ ...sla, tier: "essential", card: "services" });
    const m = review([price, sibling, disputed, roughly, other]);
    expect(groupConfirmable(m, price).map((item) => item.fact_key)).toEqual(["costs.vat_rate"]);
  });
});

describe("Zwei Prüfstufen: Pflicht und Optional", () => {
  it("drei Wichtigkeitsstufen → zwei Prüfstufen; „Wichtig“ geht standardmäßig in Optional auf, einstellbar in Pflicht", () => {
    expect(WICHTIG_ALS_PFLICHT).toBe(false);
    expect(levelOf("essential")).toBe("pflicht");
    expect(levelOf("optional")).toBe("optional");
    expect(levelOf("important")).toBe("optional");
    expect(levelOf("important", true)).toBe("pflicht");
    const model = review([start, end, sla, email, calc]);
    expect(levelCounts(model, "pflicht")).toEqual({ total: 2, open: 2, decided: 0 });
    expect(levelCounts(model, "optional")).toEqual({ total: 2, open: 2, decided: 0 });
    expect(levelCounts(model, "pflicht", true)).toEqual({ total: 3, open: 3, decided: 0 });
    expect(nextOpenLevel(model)).toBe("pflicht");
    expect(nextOpenLevel(review([decided(start), sla]))).toBe("optional");
    expect(nextOpenLevel(review([decided(start), decided(sla)]))).toBeNull();
  });
});

describe("Geführte Prüfung nach Feldern", () => {
  it("geht wesentliche Felder nacheinander durch, zeigt die Fundstelle im Original und kennt nur Felder – nicht Nachweise", async () => {
    const user = userEvent.setup();
    const model = review([start, end, price, sla]);
    const { onShow, onReload, container } = mode(model);
    const panel = screen.getByRole("region", { name: "Aktuelle Angabe" });
    expect(within(panel).getByRole("heading", { name: "Vertragsbeginn" })).toBeInTheDocument();
    const counter = screen.getByText((_, node) => node?.tagName === "SPAN" && node.textContent === "0 / 3 geprüft · 3 offen");
    expect(counter).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Pflicht,.*3 offen/ })).toHaveAttribute("aria-pressed", "true");
    // Das Original springt zur Fundstelle des Hauptnachweises.
    expect(onShow).toHaveBeenCalledWith(expect.objectContaining({ evidence_id: "s1" }));
    expect(await axe(container)).toHaveNoViolations();

    // Bestätigen speichert, die Antwort zeigt das Feld als entschieden → weiter zum nächsten offenen Feld.
    api.decideField.mockResolvedValue(detailAfter(review([decided(start), end, price, sla])));
    await user.click(within(panel).getByRole("button", { name: /^Bestätigen/ }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "dates.start_date", decision: "keep" }));
    expect(onReload).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Vertragsende" })).toBeInTheDocument();
    expect(screen.getByText("Gespeichert · weiter zu Vertragsende")).toBeInTheDocument();
  });

  it("nach der letzten Pflichtangabe geht die Prüfung von selbst zu Optional; „Wichtig“ zählt dort mit", async () => {
    const user = userEvent.setup();
    const model = review([start, sla, email]);
    const { onShow } = mode(model);
    expect(screen.getByRole("heading", { name: "Angaben prüfen" })).toBeInTheDocument();
    api.decideField.mockResolvedValue(detailAfter(review([decided(start), sla, email])));
    await user.click(screen.getByRole("button", { name: /^Bestätigen/ }));
    expect(await screen.findByRole("heading", { name: "Reaktionszeit (SLA)" })).toBeInTheDocument();
    expect(screen.getByText("Pflicht fertig – jetzt Optional")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Optional,.*2 offen/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /^Pflicht, alle entschieden/ })).toHaveAttribute("aria-pressed", "false");
    expect(onShow).toHaveBeenCalled();
  });

  it("die Stufe ist zugleich Filter: Klick, Tasten 1 und 2 wechseln und springen zur ersten offenen Angabe", async () => {
    const user = userEvent.setup();
    mode(review([start, end, sla, email]));
    await user.click(screen.getByRole("button", { name: /^Optional,.*2 offen/ }));
    expect(screen.getByRole("heading", { name: "Reaktionszeit (SLA)" })).toBeInTheDocument();
    await user.keyboard("1");
    expect(screen.getByRole("heading", { name: "Vertragsbeginn" })).toBeInTheDocument();
    await user.keyboard("2");
    expect(screen.getByRole("heading", { name: "Reaktionszeit (SLA)" })).toBeInTheDocument();
  });

  it("Freigabe: „Jetzt freigeben“ erst wenn Pflicht fertig und Optional offen; „Vertrag freigeben“ erst wenn alles geklärt; nie ohne Recht oder bei offener kritischer Angabe", () => {
    const base = { status: "in_review", unresolved_count: 2, critical_unreviewed_count: 0 } as unknown as ContractDetailResponse["contract_review"];
    const view = mode(review([decided(start), sla, email]), { contractReview: base });
    expect(screen.getByRole("button", { name: "Jetzt freigeben" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Vertrag freigeben" })).not.toBeInTheDocument();
    view.unmount();
    mode(review([start, sla, email]), { contractReview: base });
    expect(screen.queryByRole("button", { name: /freigeben/ })).not.toBeInTheDocument();
  });

  it("Freigabe bei allem geklärt: beide Stufen erledigt und „Vertrag freigeben“; gesperrt ohne Recht oder bei kritischer Angabe", () => {
    const all = review([decided(start), decided(sla)]);
    const ok = { status: "in_review", unresolved_count: 0, critical_unreviewed_count: 0 } as unknown as ContractDetailResponse["contract_review"];
    const view = mode(all, { contractReview: ok });
    // Alles geklärt: beide Stufenkarten melden „alle entschieden“.
    expect(screen.getAllByRole("button", { name: /alle entschieden/ })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Vertrag freigeben" })).toBeInTheDocument();
    view.unmount();
    const noRight = mode(all, { contractReview: ok, canReview: false });
    expect(screen.queryByRole("button", { name: "Vertrag freigeben" })).not.toBeInTheDocument();
    noRight.unmount();
    mode(all, { contractReview: { ...ok, critical_unreviewed_count: 1 } as typeof ok });
    expect(screen.queryByRole("button", { name: "Vertrag freigeben" })).not.toBeInTheDocument();
  });

  it("startet bei der Angabe, von der aus geöffnet wurde (Karte → geführt weiter)", () => {
    mode(review([start, end, price]), { startKey: "costs.monthly_recurring" });
    expect(screen.getByRole("heading", { name: "Wiederkehrende Kosten (monatlich)" })).toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.tagName === "SPAN" && node.textContent === "0 / 3 geprüft · 3 offen")).toBeInTheDocument();
  });

  it("Weitere Informationen sind nicht Teil des Ablaufs; ein Hinweis nennt sie nur, ohne Zwang", async () => {
    const user = userEvent.setup();
    const onOpenFindings = vi.fn();
    const model = review([decided(start)], { findings: [finding(), finding({ finding_key: "evidence.x", label: "Sonstiges", consequential: false })], findings_open: 2 });
    mode(model, { onOpenFindings });
    expect(screen.getByRole("heading", { name: "Pflicht abgeschlossen" })).toBeInTheDocument();
    expect(screen.getByText(/2 Weitere Informationen aus dem Dokument liegen zur Ansicht bereit – Sie müssen dazu nichts entscheiden/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ansehen" }));
    expect(onOpenFindings).toHaveBeenCalled();
  });

  it("Gruppenbestätigung zeigt jeden Wert, bestätigt nur die angehakten und nennt Fehler", async () => {
    const user = userEvent.setup();
    const vat = field({ ...price, fact_key: "costs.vat_rate", label: "MwSt.-Satz", current: "19 %", candidates: [candidate({ key: "19", display: "19 %", value: "19 %", evidence_ids: ["p1"] })], version: "v-vat" });
    const currency = field({ ...price, fact_key: "costs.currency", label: "Währung", current: "EUR", candidates: [candidate({ key: "eur", display: "EUR", value: "EUR", evidence_ids: ["p1"] })], version: "v-cur" });
    const model = review([price, vat, currency], { });
    mode(model, { startKey: "costs.monthly_recurring" });
    const group = screen.getByRole("region", { name: /Auch in „Finanzen“/ });
    expect(within(group).getByText("19 %")).toBeInTheDocument();
    expect(within(group).getByText("EUR")).toBeInTheDocument();
    await user.click(within(group).getByRole("checkbox", { name: /Währung/ }));
    api.decideField.mockResolvedValue(detailAfter(review([price, decided(vat), currency])));
    await user.click(within(group).getByRole("button", { name: "1 angezeigte Angabe bestätigen" }));
    expect(api.decideField).toHaveBeenCalledTimes(1);
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", { fact_key: "costs.vat_rate", decision: "keep", expected_version: "v-vat" });
    await waitFor(() => expect(toast).toHaveBeenCalledWith("1 Angabe bestätigt.", "success"));
  });

  it("alle Angaben: Schublade mit Stand je Angabe, Sprung zur gewählten", async () => {
    const user = userEvent.setup();
    mode(review([start, end, decided(price), sla, email, calc]));
    await user.click(screen.getByRole("button", { name: "Übersicht" }));
    const drawer = screen.getByRole("dialog", { name: "Alle Angaben" });
    expect(within(drawer).getByRole("table", { name: "Wesentliche Angaben" })).toBeInTheDocument();
    expect(within(drawer).getByRole("table", { name: "Optionale Angaben" })).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "Wiederkehrende Kosten (monatlich)" }));
    expect(await screen.findByRole("heading", { name: "Wiederkehrende Kosten (monatlich)" })).toBeInTheDocument();
  });
});

describe("Prüfung: Überblick und Weitere Informationen", () => {
  const crDefaults = { status: "in_review", status_label_de: "In manueller Prüfung", reviewer_display_name: null, completion_note: null, relevant_count: 5, reviewed_count: 2, unresolved_count: 3, critical_count: 2, critical_reviewed_count: 1, critical_unreviewed_count: 1 };

  function overview(model: FieldReviewDto, canReview = true, view: "list" | "single" = "list", contractReview: Record<string, unknown> | null = null) {
    window.localStorage.setItem("medflux.review.view", view);
    const handlers = { onReload: vi.fn(), onStartGuided: vi.fn(), onShowEvidence: vi.fn(), onShowPage: vi.fn() };
    const data = { contract_id: "c-1", field_review: model, contract_review: contractReview } as unknown as ContractDetailResponse;
    return { ...render(<FieldReviewOverview data={data} orgSlug="test-klinik" canReview={canReview} {...handlers} />), ...handlers };
  }
  const setFilter = async (user: ReturnType<typeof userEvent.setup>, label: "Status" | "Priorität", option: string) =>
    user.selectOptions(screen.getByLabelText(label), option);

  it("Kopf: Titel, Stand, Fortschritt in Prozent, Prüfer; Zähler zählen Angaben – nicht Nachweise, Berechnetes oder Weitere Informationen", async () => {
    const model = review([start, decided(end), price, sla, email, calc], { findings: [finding()], findings_open: 1 });
    const { container } = overview(model, true, "list", crDefaults);
    expect(screen.getByRole("heading", { name: "Vertragsprüfung" })).toBeInTheDocument();
    expect(screen.getByText("In manueller Prüfung")).toBeInTheDocument();
    expect(screen.getByText(/2 von 5/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "2 von 5 Angaben entschieden" })).toBeInTheDocument();
    expect(screen.getByText("40 %")).toBeInTheDocument();
    expect(screen.getByText(/Prüfung durch/)).toBeInTheDocument();
    // Wesentliche Lücke: Hinweis und Sprung zur Angabe.
    expect(screen.getByRole("alert")).toHaveTextContent("1 wesentliche Angabe blockiert den Abschluss");
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Filter: Status und Priorität, Chips zum Entfernen, Zurücksetzen und Zähler; Standard sind die offenen Angaben", async () => {
    const user = userEvent.setup();
    overview(review([start, decided(end), price, sla]));
    // Standard: offen.
    expect(screen.queryByRole("button", { name: /Vertragsende/ })).not.toBeInTheDocument();
    expect(screen.getByText("3 Angaben")).toBeInTheDocument();
    expect(screen.getByText("Offen", { selector: ".frv-chip" })).toBeInTheDocument();
    await setFilter(user, "Priorität", "essential");
    expect(screen.getByText("2 Angaben")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Statusfilter entfernen" }));
    expect(screen.getByRole("button", { name: /Vertragsende/, expanded: false })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reaktionszeit/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Zurücksetzen" }));
    expect(screen.getByRole("button", { name: /Reaktionszeit/, expanded: false })).toBeInTheDocument();
    expect(screen.getByText("4 Angaben")).toBeInTheDocument();
    await user.type(screen.getByRole("searchbox", { name: "Angabe oder Wert suchen" }), "Kosten");
    expect(screen.getByRole("button", { name: /Wiederkehrende Kosten/, expanded: false })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Vertragsbeginn/ })).not.toBeInTheDocument();
  });

  it("Karten zeigen Wert, Seite und Stand je Zeile; Zähler der Karte folgen der Priorität, nicht dem Status", async () => {
    const user = userEvent.setup();
    overview(review([start, decided(end), price, sla, calc]));
    await setFilter(user, "Status", "all");
    const terms = screen.getByRole("region", { name: "Laufzeit & Kündigung" });
    expect(terms).toHaveTextContent("1 von 2 entschieden");
    expect(within(terms).getByRole("button", { name: /Vertragsende/ })).toHaveTextContent("31.03.2029");
    expect(within(terms).getByRole("img", { name: "Entschieden" })).toBeInTheDocument();
    expect(within(terms).getByText("S. 3")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Berechnete Werte" })).getByText("Wartet auf Angaben")).toBeInTheDocument();
  });

  it("gemeinsame Bestätigung: Hinweis mit Anzahl, Liste mit Werten zum gezielten Auswählen, Widersprüchliche nie dabei", async () => {
    const user = userEvent.setup();
    const vat = field({ ...price, fact_key: "costs.vat_rate", label: "MwSt.-Satz", current: "19", version: "v1" });
    const disputed = field({ ...price, fact_key: "costs.currency", label: "Währung", status: "conflict", candidates: [price.candidates[0], candidate({ key: "chf", display: "CHF", is_current: false })] });
    api.decideField.mockResolvedValue({ contract_id: "c-1", field_review: review([decided(price), decided(vat), disputed]) });
    const { onReload } = overview(review([price, vat, disputed]));
    expect(screen.getByText("2 Angaben für gemeinsame Bestätigung verfügbar")).toBeInTheDocument();
    const card = screen.getByRole("region", { name: "Preise & Zahlung" });
    expect(within(card).getByText("Widerspruch")).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: /MwSt\.-Satz/, expanded: false })).toHaveTextContent("19 %");
    await user.click(screen.getByRole("button", { name: "2 Angaben ansehen →" }));
    const dialog = screen.getByRole("dialog", { name: "Gemeinsame Bestätigung" });
    expect(within(dialog).queryByText("Währung")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("checkbox", { name: /Wiederkehrende Kosten/ }));
    await user.click(within(dialog).getByRole("button", { name: "1 Angabe bestätigen" }));
    expect(api.decideField).toHaveBeenCalledTimes(1);
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "costs.vat_rate", decision: "keep" }));
    expect(onReload).toHaveBeenCalled();
  });

  it("einzelne eindeutige Angabe lässt sich in der Zeile bestätigen", async () => {
    const user = userEvent.setup();
    api.decideField.mockResolvedValue({ contract_id: "c-1", field_review: review([decided(price)]) });
    overview(review([price]));
    await user.click(screen.getByRole("button", { name: "Wiederkehrende Kosten (monatlich) bestätigen" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "costs.monthly_recurring", decision: "keep" }));
  });

  it("ohne wesentliche offene Entscheidung gibt es keinen Hinweis auf Blockade und nichts wird „verifiziert“ genannt", () => {
    overview(review([decided(start), decided(end), sla]), true, "list", { ...crDefaults, critical_unreviewed_count: 0 });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(/verifiziert|alles geprüft/i)).not.toBeInTheDocument();
  });

  it("fehlende und zurückgestellte Angaben werden benannt", () => {
    const missing = field({ fact_key: "termination.renewal_period", label: "Verlängerungszeitraum", status: "missing", status_label: "Nicht gefunden", present: false, current: null, candidates: [], evidence: [], source_state: null });
    const later = field({ ...price, status: "deferred", status_label: "Zurückgestellt" });
    overview(review([start, missing, later]));
    expect(screen.getByRole("button", { name: /Verlängerungszeitraum/, expanded: false })).toHaveTextContent("Nicht gefunden");
    expect(screen.getByRole("button", { name: /Wiederkehrende Kosten/, expanded: false })).toHaveTextContent("Zurückgestellt");
  });

  it("Weitere Informationen: mit Quelle gezeigt, zuordnen, als Notiz sichern, ausblenden – kein Zähler, keine Pflicht", async () => {
    const user = userEvent.setup();
    api.decideFinding.mockResolvedValue({});
    const model = review([decided(start), end], { findings: [finding(), finding({ finding_key: "evidence.done", label: "Altfund", decision: "dismissed", decided_by: "A. Prüfer", consequential: false })], findings_open: 1, findings_consequential: 1 });
    const { onReload } = overview(model);
    const section = screen.getByRole("region", { name: /Weitere Informationen aus dem Dokument/ });
    expect(within(section).getByText(/Sie müssen nichts davon bestätigen; es fließt in keine Berechnung ein und zählt nicht zur Prüfung/)).toBeInTheDocument();
    expect(within(section).getByText("„3 % Skonto bei Zahlung in 10 Tagen“")).toBeInTheDocument();
    expect(within(section).getByText("KI-Fund, nicht bestätigt")).toBeInTheDocument();
    expect(within(section).getByText("Zur Einschätzung")).toBeInTheDocument();
    const link = within(section).getByRole("button", { name: "Als Kandidat zuordnen" });
    expect(link).toBeDisabled();
    await user.selectOptions(within(section).getByLabelText(/Feld für „Rabatte“/), "dates.end_date");
    await user.click(link);
    expect(api.decideFinding).toHaveBeenCalledWith("c-1", "test-klinik", { finding_key: "evidence.costs.discounts.0", decision: "link", target_fact_key: "dates.end_date" });
    await user.click(within(section).getByRole("button", { name: "Als Notiz sichern" }));
    expect(api.decideFinding).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "note" }));
    await user.click(within(section).getByRole("button", { name: "Ausblenden" }));
    expect(api.decideFinding).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "dismiss" }));
    expect(onReload).toHaveBeenCalledTimes(3);
    await user.click(within(section).getByText("1 bearbeitete Information"));
    await user.click(within(section).getByRole("button", { name: "Wiederherstellen" }));
    expect(api.decideFinding).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ finding_key: "evidence.done", decision: "restore" }));
  });

  it("eine Angabe anklicken klappt dieselbe Entscheidungsansicht wie in der geführten Prüfung direkt darunter auf", async () => {
    const user = userEvent.setup();
    const { onStartGuided } = overview(review([start, end]));
    const row = screen.getByRole("button", { name: /Vertragsbeginn/, expanded: false });
    await user.click(row);
    expect(screen.getByRole("button", { name: /Vertragsbeginn/, expanded: true })).toBeInTheDocument();
    expect(within(row.closest("li")!).getByRole("button", { name: /^Bestätigen/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Vertragsende/, expanded: false }));
    expect(screen.getByRole("button", { name: /Vertragsbeginn/, expanded: false })).toBeInTheDocument();
    await user.click(within(screen.getByRole("button", { name: /Vertragsende/, expanded: true }).closest("li")!).getByRole("button", { name: "Im Dokument weiter prüfen →" }));
    expect(onStartGuided).toHaveBeenCalledWith("essential", "dates.end_date");
  });

  it("Einzelprüfung: nummerierte Liste links mit Stand, Entscheidung rechts, Pfeiltasten und Blättern; Ansicht wird gemerkt", async () => {
    const user = userEvent.setup();
    overview(review([start, end, price]), true, "single");
    const nav = screen.getByRole("navigation", { name: "Angaben" });
    const items = within(nav).getAllByRole("button");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("1");
    expect(items[0]).toHaveAttribute("aria-current", "true");
    const detail = screen.getByRole("region", { name: "Aktuelle Angabe" });
    expect(within(detail).getByRole("heading", { name: "Vertragsbeginn" })).toBeInTheDocument();
    expect(within(detail).getByText("1 / 3")).toBeInTheDocument();
    items[0].focus();
    await user.keyboard("{ArrowDown}");
    expect(within(screen.getByRole("region", { name: "Aktuelle Angabe" })).getByRole("heading", { name: "Vertragsende" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Nächste Angabe →" }));
    expect(within(screen.getByRole("region", { name: "Aktuelle Angabe" })).getByRole("heading", { name: "Wiederkehrende Kosten (monatlich)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nächste Angabe →" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "← Vorherige Angabe" }));
    await user.click(screen.getByRole("button", { name: "Übersicht" }));
    expect(window.localStorage.getItem("medflux.review.view")).toBe("list");
    expect(screen.getByRole("region", { name: "Laufzeit & Kündigung" })).toBeInTheDocument();
  });

  it("Vertragsprüfung ohne Sperre: ⋯-Menü → Review abschließen verlangt Annahme und Notiz; „Im Dokument prüfen“ steht im Menü", async () => {
    const user = userEvent.setup();
    const { onStartGuided } = overview(review([start]), true, "single", { ...crDefaults, critical_unreviewed_count: 0 });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Weitere Aktionen zur Vertragsprüfung" }));
    await user.click(screen.getByRole("menuitem", { name: "Review abschließen …" }));
    const dialog = screen.getByRole("dialog", { name: "Review abschließen" });
    const finish = within(dialog).getByRole("button", { name: "Review abschließen" });
    expect(finish).toBeDisabled();
    await user.click(within(dialog).getByRole("checkbox", { name: /Verbleibende nicht-wesentliche/ }));
    expect(finish).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Abschluss-Notiz/), "Rest bewusst akzeptiert");
    expect(finish).toBeEnabled();
    await user.click(within(dialog).getByRole("button", { name: "Abbrechen" }));
    await user.click(screen.getByRole("button", { name: "Weitere Aktionen zur Vertragsprüfung" }));
    await user.click(screen.getByRole("menuitem", { name: "Im Dokument prüfen" }));
    expect(onStartGuided).toHaveBeenCalledWith("essential");
  });

  it("gesperrt durch wesentliche Angabe: kein Abschluss im Menü, „Angabe prüfen →“ springt zur Angabe", async () => {
    const user = userEvent.setup();
    overview(review([start, end]), true, "single", crDefaults);
    await user.click(screen.getByRole("button", { name: "Weitere Aktionen zur Vertragsprüfung" }));
    expect(screen.queryByRole("menuitem", { name: "Review abschließen …" })).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Angabe prüfen →" }));
    expect(screen.getByRole("region", { name: "Aktuelle Angabe" })).toBeInTheDocument();
  });

  it("abgeschlossene Vertragsprüfung: Status und Prüfer sichtbar, „Review erneut öffnen“ im Menü", async () => {
    const user = userEvent.setup();
    overview(review([decided(start)]), true, "single", { ...crDefaults, status: "reviewed", status_label_de: "Wesentliches geprüft", reviewer_display_name: "A. Prüfer", completion_note: "ok", unresolved_count: 0, reviewed_count: 5, critical_unreviewed_count: 0 });
    expect(screen.getByText("Wesentliches geprüft", { selector: ".frv-status" })).toBeInTheDocument();
    expect(screen.getByText(/Geprüft von/)).toHaveTextContent("Geprüft von A. Prüfer – ok");
    await user.click(screen.getByRole("button", { name: "Weitere Aktionen zur Vertragsprüfung" }));
    expect(screen.getByRole("menuitem", { name: "Review erneut öffnen" })).toBeInTheDocument();
  });

  it("nur Lesen: keine Review-Aktionen, keine gemeinsame Bestätigung", () => {
    overview(review([price, field({ ...price, fact_key: "costs.vat_rate", label: "MwSt.-Satz" })]), false, "single", crDefaults);
    expect(screen.queryByRole("button", { name: "Weitere Aktionen zur Vertragsprüfung" })).toBeInTheDocument(); // „Im Dokument prüfen“ bleibt
    expect(screen.queryByText(/gemeinsame Bestätigung verfügbar/)).not.toBeInTheDocument();
  });
});
