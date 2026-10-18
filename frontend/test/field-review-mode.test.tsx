import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FieldReviewMode from "@/components/contracts/detail/FieldReviewMode";
import FieldReviewOverview from "@/components/contracts/detail/FieldReviewOverview";
import type { ContractDetailResponse, FieldReviewDto } from "@/lib/contract-detail-types";
import { decisionFields, groupConfirmable, nextDecision, nextOpenTier, reviewHeadline } from "@/lib/field-review";
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

describe("Geführte Prüfung nach Feldern", () => {
  it("geht wesentliche Felder nacheinander durch, zeigt die Fundstelle im Original und kennt nur Felder – nicht Nachweise", async () => {
    const user = userEvent.setup();
    const model = review([start, end, price, sla]);
    const { onShow, onReload, container } = mode(model);
    const panel = screen.getByRole("region", { name: "Aktuelle Angabe" });
    expect(within(panel).getByRole("heading", { name: "Vertragsbeginn" })).toBeInTheDocument();
    expect(screen.getByText("Angabe 1 von 3")).toBeInTheDocument();
    expect(screen.getByText("3 Entscheidungen offen")).toBeInTheDocument();
    // Das Original springt zur Fundstelle des Hauptnachweises.
    expect(onShow).toHaveBeenCalledWith(expect.objectContaining({ evidence_id: "s1" }));
    expect(await axe(container)).toHaveNoViolations();

    // Bestätigen speichert, die Antwort zeigt das Feld als entschieden → weiter zum nächsten offenen Feld.
    api.decideField.mockResolvedValue(detailAfter(review([decided(start), end, price, sla])));
    await user.click(within(panel).getByRole("button", { name: "Bestätigen" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "dates.start_date", decision: "keep" }));
    expect(onReload).toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Vertragsende" })).toBeInTheDocument();
    expect(screen.getByText("Gespeichert · weiter zu Vertragsende")).toBeInTheDocument();
  });

  it("am Ende der wesentlichen Stufe: „Wesentliche Prüfung abgeschlossen“, nächste Stufe angeboten, kein Anspruch auf Vollständigkeit", async () => {
    const user = userEvent.setup();
    const model = review([start, sla, email]);
    const { onShow } = mode(model);
    api.decideField.mockResolvedValue(detailAfter(review([decided(start), sla, email])));
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));
    const title = await screen.findByRole("heading", { name: "Wesentliche Prüfung abgeschlossen" });
    expect(title).toBeInTheDocument();
    expect(screen.getByText(/Das heißt nicht, dass jede Angabe des Vertrags verifiziert ist/)).toBeInTheDocument();
    // Die nächste Stufe wird angeboten, nicht erzwungen.
    await user.click(screen.getByRole("button", { name: "Weitere wichtige Angaben prüfen · 1" }));
    expect(await screen.findByRole("heading", { name: "Reaktionszeit (SLA)" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Weitere wichtige Angaben prüfen" })).toBeInTheDocument();
    expect(onShow).toHaveBeenCalled();
  });

  it("startet bei der Angabe, von der aus geöffnet wurde (Karte → geführt weiter)", () => {
    mode(review([start, end, price]), { startKey: "costs.monthly_recurring" });
    expect(screen.getByRole("heading", { name: "Wiederkehrende Kosten (monatlich)" })).toBeInTheDocument();
    expect(screen.getByText("Angabe 3 von 3")).toBeInTheDocument();
  });

  it("Weitere Informationen sind nicht Teil des Ablaufs; ein Hinweis nennt sie nur, ohne Zwang", async () => {
    const user = userEvent.setup();
    const onOpenFindings = vi.fn();
    const model = review([decided(start)], { findings: [finding(), finding({ finding_key: "evidence.x", label: "Sonstiges", consequential: false })], findings_open: 2 });
    mode(model, { onOpenFindings });
    expect(screen.getByRole("heading", { name: "Wesentliche Prüfung abgeschlossen" })).toBeInTheDocument();
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
    await user.click(screen.getByRole("button", { name: "Alle Angaben" }));
    const drawer = screen.getByRole("dialog", { name: "Alle Angaben" });
    expect(within(drawer).getByRole("table", { name: "Wesentliche Angaben" })).toBeInTheDocument();
    expect(within(drawer).getByRole("table", { name: "Optionale Angaben" })).toBeInTheDocument();
    await user.click(within(drawer).getByRole("button", { name: "Wiederkehrende Kosten (monatlich)" }));
    expect(await screen.findByRole("heading", { name: "Wiederkehrende Kosten (monatlich)" })).toBeInTheDocument();
  });
});

describe("Prüfung: Überblick und Weitere Informationen", () => {
  function overview(model: FieldReviewDto, canReview = true) {
    const handlers = { onReload: vi.fn(), onStartGuided: vi.fn(), onShowEvidence: vi.fn(), onShowPage: vi.fn() };
    const data = { contract_id: "c-1", field_review: model } as unknown as ContractDetailResponse;
    return { ...render(<FieldReviewOverview data={data} orgSlug="test-klinik" canReview={canReview} {...handlers} />), ...handlers };
  }

  it("zeigt Angaben als Karten mit Wert und Stand; Zähler zählen Angaben, nicht Nachweise, Berechnetes und Weitere Informationen", async () => {
    const user = userEvent.setup();
    const model = review([start, decided(end), price, sla, email, calc], { findings: [finding(), finding({ finding_key: "evidence.y", label: "Skonto", evidence_ids: ["e10"] })], findings_open: 2 });
    const { onStartGuided, container } = overview(model);
    expect(screen.getByText("1 von 3 wesentlichen entschieden")).toBeInTheDocument();
    const terms = screen.getByRole("region", { name: "Laufzeit & Kündigung" });
    expect(terms).toHaveTextContent("1 von 2 entschieden");
    expect(within(terms).getByRole("button", { name: /Vertragsende/ })).toHaveTextContent("31.03.2029");
    expect(within(terms).getByRole("img", { name: "Entschieden" })).toBeInTheDocument();
    expect(within(terms).getByRole("img", { name: "Zu entscheiden" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Service & Leistungen" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^Weitere wichtige Angaben/ }));
    expect(screen.getByRole("region", { name: "Service & Leistungen" })).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Berechnete Werte" })).getByText("Wartet auf Angaben")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Wesentliches prüfen · 2" }));
    expect(onStartGuided).toHaveBeenCalledWith("essential");
  });

  it("Karte bestätigt nur eindeutige, genau belegte Angaben – und nennt vorher, wie viele", async () => {
    const user = userEvent.setup();
    const vat = field({ ...price, fact_key: "costs.vat_rate", label: "MwSt.-Satz", current: "19 %", version: "v1" });
    const disputed = field({ ...price, fact_key: "costs.currency", label: "Währung", status: "conflict", candidates: [price.candidates[0], candidate({ key: "chf", display: "CHF", is_current: false })] });
    api.decideField.mockResolvedValue({ contract_id: "c-1", field_review: review([decided(price), decided(vat), disputed]) });
    const { onReload } = overview(review([price, vat, disputed]));
    const card = screen.getByRole("region", { name: "Preise & Zahlung" });
    expect(within(card).getByText("Widerspruch")).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "2 Angaben bestätigen" }));
    expect(api.decideField).toHaveBeenCalledTimes(2);
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "costs.vat_rate", decision: "keep" }));
    expect(api.decideField).not.toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "costs.currency" }));
    expect(onReload).toHaveBeenCalled();
  });

  it("ohne wesentliche offene Entscheidung: „Wesentliche Prüfung abgeschlossen“, Karte „Abgeschlossen“, nichts Behauptetes", () => {
    overview(review([decided(start), decided(end), sla]));
    expect(screen.getByText("Wesentliche Prüfung abgeschlossen")).toBeInTheDocument();
    expect(screen.getAllByText("Abgeschlossen").length).toBeGreaterThan(0);
    expect(screen.queryByText(/alle .*geprüft/i)).not.toBeInTheDocument();
  });

  it("Suche und „Nur offene“ engen die Karten ein", async () => {
    const user = userEvent.setup();
    overview(review([start, decided(end), price]));
    await user.click(screen.getByRole("button", { name: /^Nur offene/ }));
    expect(screen.queryByRole("button", { name: /Vertragsende/ })).not.toBeInTheDocument();
    await user.type(screen.getByRole("searchbox", { name: "Angabe oder Wert suchen" }), "Kosten");
    expect(screen.getByRole("button", { name: /Wiederkehrende Kosten/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Vertragsbeginn/ })).not.toBeInTheDocument();
  });

  it("fehlende und zurückgestellte Angaben werden benannt", () => {
    const missing = field({ fact_key: "termination.renewal_period", label: "Verlängerungszeitraum", status: "missing", status_label: "Nicht gefunden", present: false, current: null, candidates: [], evidence: [], source_state: null });
    const later = field({ ...price, status: "deferred", status_label: "Zurückgestellt" });
    overview(review([start, missing, later]));
    expect(screen.getByRole("button", { name: /Verlängerungszeitraum/ })).toHaveTextContent("Nicht gefunden");
    expect(screen.getByRole("button", { name: /Wiederkehrende Kosten/ })).toHaveTextContent("Zurückgestellt");
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
    expect(screen.getByText("1 von 2 wesentlichen entschieden")).toBeInTheDocument();

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

  it("eine Angabe anklicken öffnet rechts dieselbe Entscheidungsansicht wie die geführte Prüfung", async () => {
    const user = userEvent.setup();
    const { onStartGuided } = overview(review([start, end]));
    expect(screen.getByText("Details zur Angabe", { selector: "strong" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Vertragsbeginn/ }));
    const panel = screen.getByRole("group", { name: "Details zur Angabe" });
    expect(within(panel).getByRole("heading", { name: "Vertragsbeginn" })).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Bestätigen" })).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Nächste offene" }));
    expect(within(screen.getByRole("group", { name: "Details zur Angabe" })).getByRole("heading", { name: "Vertragsende" })).toBeInTheDocument();
    await user.click(within(screen.getByRole("group", { name: "Details zur Angabe" })).getByRole("button", { name: "Geführt weiter" }));
    expect(onStartGuided).toHaveBeenCalledWith("essential", "dates.end_date");
  });
});
