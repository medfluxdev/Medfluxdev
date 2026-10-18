import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FieldDecision from "@/components/contracts/detail/FieldDecision";
import { ApiError } from "@/lib/api";
import { candidate, conflicting, evidence, field, review, twoAgreeing } from "./fixtures/field-review";

const api = vi.hoisted(() => ({ decideField: vi.fn(), setFieldEvidence: vi.fn(), reviewContractFact: vi.fn() }));
vi.mock("@/lib/domain-api/contracts", () => api);
const toast = vi.hoisted(() => vi.fn());
vi.mock("@/components/ui/Toast", () => ({ useToast: () => toast }));

const DETAIL = { contract_id: "c-1", field_review: null };

function setup(item = twoAgreeing(), props: Partial<React.ComponentProps<typeof FieldDecision>> = {}) {
  const onChanged = vi.fn();
  const utils = render(<FieldDecision contractId="c-1" orgSlug="test-klinik" field={item} review={review([item])} canReview onChanged={onChanged} {...props} />);
  return { ...utils, onChanged };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.decideField.mockResolvedValue(DETAIL);
  api.setFieldEvidence.mockResolvedValue(DETAIL);
});

describe("Entscheidung zu einem Feld", () => {
  it("ein Wert, zwei übereinstimmende Belege: eine Entscheidung genügt, kein Beleg wird einzeln bestätigt", async () => {
    const user = userEvent.setup();
    const { onChanged, container } = setup();
    expect(screen.getByText("2 übereinstimmende Fundstellen – eine Entscheidung genügt")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Bestätigen" })).toHaveLength(1);
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    // Die zweite Fundstelle ist nur „Seite bekannt“ – sie wird nicht als bestätigt ausgegeben.
    expect(screen.getByText("Fundstelle bestätigt")).toBeInTheDocument();
    expect(screen.getByText("Seite bekannt, Stelle ungefähr")).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", {
      fact_key: "dates.end_date", decision: "keep", expected_version: null, candidate_key: "2029-03-31", confirm_change: false,
    });
    expect(onChanged).toHaveBeenCalledWith(DETAIL, { decided: true });
  });

  it("konkurrierende Werte: ein Feld, eine Wahl; die Änderung des gespeicherten Werts wird vorher ausdrücklich gezeigt", async () => {
    const user = userEvent.setup();
    setup(conflicting());
    const group = screen.getByRole("group", { name: "Welcher Wert gilt?" });
    const radios = within(group).getAllByRole("radio");
    expect(radios).toHaveLength(2);
    expect(radios[0]).toBeChecked();
    expect(within(group).getByText("Kein Beleg im Dokument (berechnet)")).toBeInTheDocument();
    expect(screen.queryByText("Das ändert den gespeicherten Wert")).not.toBeInTheDocument();
    await user.click(radios[1]);
    const change = document.querySelector(".fd-change")!;
    expect(change).toHaveTextContent("Das ändert den gespeicherten Wert");
    expect(change).toHaveTextContent("31.03.2029 → 31.03.2028");
    expect(api.decideField).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Änderung übernehmen" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "accept", candidate_key: "2028-03-31", confirm_change: true }));
  });

  it("Beleg ausschließen: Grund nötig, der Wert bleibt, der andere Beleg bleibt erhalten", async () => {
    const user = userEvent.setup();
    setup();
    const second = screen.getByRole("list", { name: "Belege zu 31.03.2029" }).querySelectorAll("li")[1] as HTMLElement;
    await user.click(within(second).getByRole("button", { name: "Ausschließen" }));
    expect(screen.getByText("Der Nachweis bleibt erhalten und sichtbar; der Wert des Felds ändert sich dadurch nicht.")).toBeInTheDocument();
    const submit = within(screen.getByRole("form", { name: "Nachweis ausschließen" })).getByRole("button", { name: "Ausschließen" });
    expect(submit).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Grund"), "wrong_place");
    await user.click(submit);
    expect(api.setFieldEvidence).toHaveBeenCalledWith("c-1", "test-klinik", { fact_key: "dates.end_date", evidence_id: "e2", action: "exclude", expected_version: null, reason: "wrong_place", note: "" });
    expect(api.decideField).not.toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith("Nachweis ausgeschlossen – der Wert bleibt unverändert.", "success");
  });

  it("Hauptnachweis wählen schließt nichts aus; ausgeschlossene Belege bleiben sichtbar und lassen sich wiederherstellen", async () => {
    const user = userEvent.setup();
    const item = twoAgreeing();
    item.evidence[1] = evidence({ ...item.evidence[1], primary: false });
    setup(item);
    await user.click(screen.getByRole("button", { name: "Als Hauptnachweis" }));
    expect(api.setFieldEvidence).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ action: "primary", evidence_id: "e2" }));

    const excluded = twoAgreeing();
    excluded.evidence[1] = evidence({ evidence_id: "e2", primary: false, excluded: true, exclusion_reason: "outdated", exclusion_reason_label: "Überholt (z. B. durch einen Nachtrag)", exclusion_note: "Nachtrag 2", excluded_by: "A. Prüfer" });
    excluded.active_evidence_count = 1;
    setup(excluded);
    expect(screen.getByText("Ausgeschlossen")).toBeInTheDocument();
    expect(screen.getByText(/Überholt .* – Nachtrag 2 · A\. Prüfer/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Wiederherstellen" }));
    expect(api.setFieldEvidence).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ action: "restore", evidence_id: "e2" }));
  });

  it("fehlendes wesentliches Feld: ehrlich benannt, nichts erfunden; Wert eintragen oder „nicht im Dokument“", async () => {
    const user = userEvent.setup();
    const missing = field({ fact_key: "termination.renewal_period", label: "Verlängerungszeitraum", status: "missing", status_label: "Nicht gefunden", reason: "Im Dokument nicht gefunden – Wert eintragen oder „nicht im Dokument“ festhalten.", present: false, current: null, document_value: null, candidates: [], evidence: [], primary_evidence_id: null, source_state: null });
    setup(missing);
    expect(screen.getByText("Im Dokument wurde kein Wert gefunden. Nichts wird vermutet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Bestätigen" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Nicht im Dokument" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "not_in_document" }));
    await user.click(screen.getByRole("button", { name: "Wert eintragen" }));
    await user.type(screen.getByLabelText("Richtiger Wert"), "12 Monate");
    await user.click(screen.getByRole("button", { name: "Speichern" }));
    expect(api.decideField).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "manual", value: "12 Monate" }));
  });

  it("Quelle nicht verfügbar oder nicht aufgelöst: kein „bestätigt“, klarer Hinweis", () => {
    const item = field({ source_state: "unavailable", evidence: [evidence({ document_available: false, source_state: "unavailable", source_state_label: "Dokument nicht verfügbar", location: "none", text_verified: false })] });
    setup(item);
    expect(screen.getAllByText("Dokument nicht verfügbar").length).toBeGreaterThan(0);
    expect(screen.queryByText("Fundstelle bestätigt")).not.toBeInTheDocument();
    expect(screen.getByText(/Der Wert gilt hier nicht als belegt/)).toBeInTheDocument();
  });

  it("Zurückstellen: Entscheidung bleibt offen, das Feld wird nicht als entschieden gemeldet", async () => {
    const user = userEvent.setup();
    const { onChanged } = setup();
    await user.click(screen.getByRole("button", { name: "Zurückstellen" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "defer" }));
    expect(onChanged).toHaveBeenCalledWith(DETAIL, { decided: false });
  });

  it("gleichzeitige Änderung (409): nichts überschrieben, Stand neu geladen, klarer Hinweis", async () => {
    const user = userEvent.setup();
    api.decideField.mockRejectedValue(new ApiError("Das Feld wurde inzwischen geändert.", { status: 409 }));
    const { onChanged } = setup();
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(onChanged).toHaveBeenCalledWith(null, { decided: false });
    expect(screen.getByText(/inzwischen geändert\. Der aktuelle Stand ist geladen/)).toBeInTheDocument();
  });

  it("Speicherfehler: Meldung mit Wiederholmöglichkeit, Eingaben bleiben", async () => {
    const user = userEvent.setup();
    api.decideField.mockRejectedValueOnce(new ApiError("Verbindung zum Server fehlgeschlagen.", { status: 503 }));
    const { onChanged } = setup();
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Verbindung zum Server fehlgeschlagen.");
    expect(onChanged).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(api.decideField).toHaveBeenCalledTimes(2);
    expect(onChanged).toHaveBeenCalled();
  });

  it("berechnete Werte werden nicht einzeln bestätigt und nennen ihre Eingaben", () => {
    const calc = field({ fact_key: "dates.latest_cancellation", label: "Kündigungsfrist (letztes Kündigungsdatum)", kind: "calculated", status: "derived", status_label: "Berechnet", decision_needed: false, current: "30.09.2028", candidates: [], evidence: [],
      inputs: [{ fact_key: "dates.end_date", label: "Vertragsende", present: true, decided: true }, { fact_key: "termination.cancellation_period", label: "Kündigungsfrist", present: true, decided: false }] });
    setup(calc);
    expect(screen.getByText("Berechnet aus geprüften Angaben – keine eigene Bestätigung nötig.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Bestätigen|Zurückstellen/ })).not.toBeInTheDocument();
    expect(screen.getByText("Geklärt")).toBeInTheDocument();
    expect(screen.getByText("Offen")).toBeInTheDocument();
  });

  it("Wert aus einer erneuten Analyse wird dort übernommen, nicht hier", async () => {
    const user = userEvent.setup();
    const item = twoAgreeing();
    item.status = "changed";
    item.candidates.push(candidate({ key: "2030-03-31", display: "31.03.2030", value: "31.03.2030", is_current: false, sources: [{ source: "analysis", label: "Analyse #2" }], evidence_ids: [], inline_evidence: [{ page: 4, quote: "bis zum 31.03.2030" }], support_count: 1, proposal_id: "p1", run_number: 2 }));
    const onOpenAnalysis = vi.fn();
    setup(item, { onOpenAnalysis });
    expect(screen.getByText(/Dieser Wert kommt aus Analyse #2/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dort übernehmen" }));
    expect(onOpenAnalysis).toHaveBeenCalled();
  });

  it("ohne Berechtigung nur lesbar", () => {
    setup(twoAgreeing(), { canReview: false });
    expect(screen.getByText(/Nur Lesen/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Bestätigen|Ausschließen|Von Hand/ })).not.toBeInTheDocument();
  });

  it("entschiedenes Feld wird nicht erneut zur Bestätigung angeboten", () => {
    const done = twoAgreeing();
    done.status = "decided";
    done.status_label = "Entschieden";
    done.decision_needed = false;
    done.reviewer = "A. Prüfer";
    done.reviewed_at = "2026-10-18T10:00:00+00:00";
    setup(done);
    expect(screen.getByRole("button", { name: "Entschieden" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Zurückstellen" })).not.toBeInTheDocument();
    expect(screen.getByText(/Zuletzt entschieden von A\. Prüfer/)).toBeInTheDocument();
  });

  it("Vergleichskästen: Dokument ↔ gespeichert, Abweichung wird markiert und lässt drei Wege zu", async () => {
    const user = userEvent.setup();
    const item = twoAgreeing();
    item.fact_state = "confirmed";
    item.stored_value = "30.06.2029";
    item.document_value = "31.03.2029";
    item.status = "changed";
    setup(item);
    expect(screen.getByText("Im Dokument (erkannt)")).toBeInTheDocument();
    expect(screen.getByText("In MedFlux gespeichert")).toBeInTheDocument();
    expect(screen.getByText("Weicht ab – Unterschiede sind markiert.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Abweichung" }));
    const form = screen.getByRole("form", { name: /Abweichung/ });
    expect(within(form).getAllByRole("radio")).toHaveLength(3);
    await user.click(within(form).getByRole("button", { name: "Übernehmen" }));
    expect(api.decideField).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "manual", value: "31.03.2029", note: "Wert aus dem Dokument übernommen." }));
    await user.click(screen.getByRole("button", { name: "Abweichung" }));
    await user.click(screen.getByRole("radio", { name: /MedFlux hat recht/ }));
    await user.click(screen.getByRole("button", { name: "Übernehmen" }));
    expect(api.decideField).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "keep" }));
  });

  it("stimmen Dokument und gespeicherter Wert überein, sagt es der Kasten; Abweichung führt dann zur Eingabe von Hand", async () => {
    const user = userEvent.setup();
    const item = twoAgreeing();
    item.fact_state = "confirmed";
    item.stored_value = "31.03.2029";
    setup(item);
    expect(screen.getByText("Dokument und MedFlux stimmen überein.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Abweichung" }));
    expect(screen.queryByRole("radio", { name: /Dokument hat recht/ })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Richtiger Wert"), "x");
    expect(screen.getByRole("button", { name: "Text im Dokument markieren und übernehmen" })).toBeInTheDocument();
  });

  it("Tasten der geführten Prüfung: Enter bestätigt, A öffnet die Abweichung, S stellt zurück", async () => {
    const user = userEvent.setup();
    setup(twoAgreeing(), { shortcuts: true });
    await user.keyboard("{Enter}");
    expect(api.decideField).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "keep" }));
    await user.keyboard("s");
    expect(api.decideField).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "defer" }));
    await user.keyboard("a");
    expect(screen.getByRole("form", { name: /Abweichung|Von Hand/ })).toBeInTheDocument();
  });

  it("Erneut öffnen: eine bestätigte Angabe wird wieder zur Entscheidung gestellt (Verlauf bleibt)", async () => {
    const user = userEvent.setup();
    api.reviewContractFact.mockResolvedValue(DETAIL);
    const done = twoAgreeing();
    done.status = "decided";
    done.decision_needed = false;
    done.fact_state = "confirmed";
    done.reviewed_at = "2026-10-18T10:00:00+00:00";
    const { onChanged } = setup(done);
    await user.click(screen.getByRole("button", { name: "Erneut öffnen" }));
    expect(api.reviewContractFact).toHaveBeenCalledWith("c-1", "test-klinik", { fact_key: "dates.end_date", action: "reopened", expected_reviewed_at: "2026-10-18T10:00:00+00:00" });
    expect(onChanged).toHaveBeenCalledWith(DETAIL, { decided: false });
  });

  it("Korrigieren braucht eine Begründung, wenn bereits ein Wert da ist", async () => {
    const user = userEvent.setup();
    setup();
    await user.click(screen.getByRole("button", { name: "Abweichung" }));
    await user.clear(screen.getByLabelText("Richtiger Wert"));
    await user.type(screen.getByLabelText("Richtiger Wert"), "30.06.2029");
    const submit = screen.getByRole("button", { name: "Übernehmen" });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText("Begründung der Korrektur"), "Nachtrag 2");
    expect(submit).toBeEnabled();
    await user.click(submit);
    expect(api.decideField).toHaveBeenLastCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "manual", value: "30.06.2029", note: "Nachtrag 2" }));
  });
});
