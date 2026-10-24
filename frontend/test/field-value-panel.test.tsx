import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FieldValuePanel from "@/components/contracts/detail/FieldValuePanel";
import type { ContractDetailResponse, DetailDocument, FieldReviewFieldDto } from "@/lib/contract-detail-types";
import { candidate, evidence, field, review } from "./fixtures/field-review";

const api = vi.hoisted(() => ({ decideField: vi.fn(), setFieldEvidence: vi.fn(), reviewContractFact: vi.fn() }));
vi.mock("@/lib/domain-api/contracts", () => api);
vi.mock("@/components/ui/Toast", () => ({ useToast: () => vi.fn() }));

const docs: DetailDocument[] = [
  { document_version_id: "doc-main", role: "main", original_filename: "vertrag.pdf", mime_type: "application/pdf", file_size_bytes: 1, viewer_supported: true },
  { document_version_id: "doc-nachtrag", role: "amendment", original_filename: "nachtrag.pdf", mime_type: "application/pdf", file_size_bytes: 1, viewer_supported: true },
];

/** Vertragsbeginn: der gespeicherte Wert stammt aus dem Hauptvertrag, ein Nachtrag nennt einen späteren. */
function twoValues(): FieldReviewFieldDto {
  return field({
    fact_key: "dates.start_date", label: "Vertragsbeginn", current: "01.01.2026", document_value: "01.01.2026", status: "conflict", status_label: "Widerspruch", version: "v1",
    candidates: [
      candidate({ key: "2026-01-01", display: "01.01.2026", value: "01.01.2026", is_current: true, sources: [{ source: "stored", label: "Gespeichert" }], evidence_ids: ["m1"] }),
      candidate({ key: "2026-02-01", display: "01.02.2026", value: "01.02.2026", is_current: false, sources: [{ source: "document", label: "Aus dem Dokument" }], evidence_ids: ["n1"] }),
    ],
    evidence: [
      evidence({ evidence_id: "m1", page: 3, snippet: "Der Vertrag beginnt am 01.01.2026.", document_version_id: "doc-main", primary: true }),
      evidence({ evidence_id: "n1", page: 8, snippet: "Der Vertragsbeginn wird auf den 01.02.2026 verschoben.", document_version_id: "doc-nachtrag", primary: true }),
    ],
    primary_evidence_id: "m1",
  });
}

function matching(): FieldReviewFieldDto {
  return field({
    fact_key: "identity.title", label: "Vertragsgegenstand / Titel", current: "Full-Service-Vertrag", version: "v1",
    candidates: [candidate({ key: "t", display: "Full-Service-Vertrag", value: "Full-Service-Vertrag", sources: [{ source: "stored", label: "Gespeichert" }, { source: "document", label: "Aus dem Dokument" }], evidence_ids: ["e1"] })],
    evidence: [evidence({ evidence_id: "e1", page: 1, snippet: "Full-Service-Vertrag", document_version_id: "doc-main", text_match: 1 })],
  });
}

function missing(): FieldReviewFieldDto {
  return field({
    fact_key: "identity.contract_type", label: "Vertragsart", status: "missing", status_label: "Nicht gefunden", decision_needed: true, present: false, current: null, document_value: null,
    candidates: [], evidence: [], primary_evidence_id: null, source_state: null, version: "v1",
  });
}

function decidedField(): FieldReviewFieldDto {
  const base = twoValues();
  return {
    ...base, status: "decided", status_label: "Entschieden", decision_needed: false, fact_state: "corrected", reviewer: "A. Prüfer", reviewed_at: "2026-10-24T14:35:00+00:00", current: "01.02.2026",
    candidates: [{ ...base.candidates[0], is_current: false }, { ...base.candidates[1], is_current: true }],
    history: [{ at: "2026-10-24T14:35:00+00:00", kind: "corrected", label: "Korrigiert", by: "A. Prüfer", detail: "Beginn gemäß Nachtrag korrigiert." }],
  };
}

function panel(item: FieldReviewFieldDto, props: Partial<React.ComponentProps<typeof FieldValuePanel>> = {}) {
  const handlers = { onChanged: vi.fn(), onShowEvidence: vi.fn(), onShowPage: vi.fn(), onPrev: vi.fn(), onNext: vi.fn() };
  const utils = render(<FieldValuePanel contractId="c-1" orgSlug="test-klinik" field={item} review={review([item])} documents={docs} canReview
    position={{ index: 2, total: 6 }} nextLabel="Vertragsende" {...handlers} {...props} />);
  return { ...utils, ...handlers };
}

beforeEach(() => vi.clearAllMocks());

describe("Panel „Werte prüfen“", () => {
  it("Übereinstimmung: eine grüne, vorgewählte Karte mit „in MedFlux“, ein Klick bestätigt", async () => {
    const user = userEvent.setup();
    api.decideField.mockResolvedValue({ contract_id: "c-1" } as ContractDetailResponse);
    const { onChanged, container } = panel(matching());
    expect(screen.getByText("Pflicht")).toBeInTheDocument();
    expect(screen.getByText("3 / 6")).toBeInTheDocument();
    expect(screen.getByText("Dokument und MedFlux sagen dasselbe")).toBeInTheDocument();
    const radio = screen.getByRole("radio", { name: /Full-Service-Vertrag/ });
    expect(radio).toBeChecked();
    expect(screen.getByText("in MedFlux")).toBeInTheDocument();
    expect(screen.getByText(/wörtlich im Dokument/)).toBeInTheDocument();
    expect(screen.queryByText(/Welcher gilt/)).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Begründung (optional)" })).not.toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Bestätigen · Weiter" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ fact_key: "identity.title", decision: "keep" }));
    expect(onChanged).toHaveBeenCalled();
  });

  it("zwei Werte: der Nachtrag ist vorgewählt, der Knopf nennt den Wert, Begründung erscheint erst bei einer Änderung", async () => {
    const user = userEvent.setup();
    api.decideField.mockResolvedValue({ contract_id: "c-1" } as ContractDetailResponse);
    panel(twoValues());
    expect(screen.getByText("2 Werte")).toBeInTheDocument();
    expect(screen.getByText(/Im Zweifel der spätere Nachtrag/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /01\.02\.2026/ })).toBeChecked();
    expect(screen.getByText(/Seite 8 · Nachtrag/)).toBeInTheDocument();
    expect(screen.getByText(/Seite 3 · Hauptdokument/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Begründung (optional)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "01.02.2026 übernehmen · Weiter" })).toBeEnabled();

    // Zurück auf den gespeicherten Wert: die Begründung entfällt, der Knopf bestätigt.
    await user.click(screen.getByRole("radio", { name: /01\.01\.2026/ }));
    expect(screen.queryByRole("textbox", { name: "Begründung (optional)" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bestätigen · Weiter" })).toBeInTheDocument();

    await user.click(screen.getByRole("radio", { name: /01\.02\.2026/ }));
    await user.type(screen.getByRole("textbox", { name: "Begründung (optional)" }), "gemäß Nachtrag");
    await user.click(screen.getByRole("button", { name: "01.02.2026 übernehmen · Weiter" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({
      decision: "accept", candidate_key: "2026-02-01", confirm_change: true, note: "gemäß Nachtrag",
    }));
  });

  it("„Im Dokument zeigen“ springt zur Fundstelle, ohne die Auswahl zu ändern", async () => {
    const user = userEvent.setup();
    const { onShowEvidence } = panel(twoValues());
    await user.click(screen.getAllByRole("button", { name: /Im Dokument zeigen/ })[0]);
    expect(onShowEvidence).toHaveBeenCalledWith(expect.objectContaining({ evidence_id: "m1" }));
    expect(screen.getByRole("radio", { name: /01\.02\.2026/ })).toBeChecked();
  });

  it("„Anderer Wert“ öffnet das Feld an Ort und Stelle; der Knopf nennt den eingegebenen Wert", async () => {
    const user = userEvent.setup();
    api.decideField.mockResolvedValue({ contract_id: "c-1" } as ContractDetailResponse);
    panel(twoValues());
    await user.click(screen.getByRole("button", { name: /Anderer Wert/ }));
    const input = screen.getByRole("textbox", { name: "Anderer Wert" });
    expect(input).toHaveFocus();
    expect(screen.getByRole("button", { name: "Wert übernehmen · Weiter" })).toBeDisabled();
    await user.type(input, "15.02.2026");
    await user.click(screen.getByRole("button", { name: "15.02.2026 übernehmen · Weiter" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "manual", value: "15.02.2026" }));
  });

  it("ohne Wert im Dokument: „Nicht im Vertrag“ ist wählbar, der Knopf speichert genau das; mit Wert gibt es die Wahl nicht", async () => {
    const user = userEvent.setup();
    api.decideField.mockResolvedValue({ contract_id: "c-1" } as ContractDetailResponse);
    const first = panel(missing());
    expect(screen.getByText("Nicht gefunden")).toBeInTheDocument();
    expect(screen.getByText(/Nichts wird vermutet/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Nicht im Vertrag/ }));
    await user.click(screen.getByRole("button", { name: "Als „nicht im Vertrag“ speichern · Weiter" }));
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "not_in_document" }));
    first.unmount();
    panel(matching());
    expect(screen.queryByRole("button", { name: /Nicht im Vertrag/ })).not.toBeInTheDocument();
  });

  it("nach der Entscheidung: Wert groß, Quelle, wer und wann, „Ändern“ öffnet die Auswahl wieder; Begründung und zwei gefaltete Zeilen", async () => {
    const user = userEvent.setup();
    panel(decidedField());
    expect(screen.getByText("Geprüft")).toBeInTheDocument();
    expect(screen.getByText("01.02.2026", { selector: ".vp-big" })).toBeInTheDocument();
    expect(screen.getByText(/Übernommen/)).toHaveTextContent("A. Prüfer");
    expect(screen.getByText("Beginn gemäß Nachtrag korrigiert.")).toBeInTheDocument();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    const alt = screen.getByRole("button", { name: /Anderer Vorschlag/ });
    expect(alt).toHaveAttribute("aria-expanded", "false");
    await user.click(alt);
    expect(alt).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /Verlauf/ })).toHaveTextContent("1 Eintrag");
    await user.click(screen.getByRole("button", { name: /Weiter/ }));
    // „Ändern“ stellt die Auswahl mit dem aktuellen Wert wieder her.
    await user.click(screen.getByRole("button", { name: /Ändern/ }));
    expect(screen.getAllByRole("radio")).toHaveLength(2);
    expect(screen.getByRole("radio", { name: /01\.02\.2026/ })).toBeChecked();
  });

  it("Tasten: Enter führt aus, A öffnet „Anderer Wert“, S stellt zurück, Esc schließt das Feld", async () => {
    const user = userEvent.setup();
    api.decideField.mockResolvedValue({ contract_id: "c-1" } as ContractDetailResponse);
    panel(twoValues());
    await user.keyboard("s");
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "defer" }));
    api.decideField.mockClear();
    await user.keyboard("a");
    expect(screen.getByRole("textbox", { name: "Anderer Wert" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("textbox", { name: "Anderer Wert" })).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /01\.02\.2026/ })).toBeChecked();
    await user.keyboard("{Enter}");
    expect(api.decideField).toHaveBeenCalledWith("c-1", "test-klinik", expect.objectContaining({ decision: "accept", candidate_key: "2026-02-01" }));
  });

  it("Fundstelle ausschließen liegt im ⋯ der Karte und verlangt einen Grund; Zurück und Weiter im Fuß", async () => {
    const user = userEvent.setup();
    api.setFieldEvidence.mockResolvedValue({ contract_id: "c-1" } as ContractDetailResponse);
    const { onPrev, onNext } = panel(twoValues());
    await user.click(screen.getAllByRole("button", { name: /Weitere Aktionen zu/ })[0]);
    await user.click(screen.getByRole("menuitem", { name: "Diese Fundstelle ausschließen" }));
    const form = screen.getByRole("form", { name: "Fundstelle ausschließen" });
    expect(within(form).getByRole("button", { name: "Ausschließen" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Zurück" }));
    await user.click(screen.getByRole("button", { name: "Überspringen" }));
    expect(onPrev).toHaveBeenCalled();
    expect(onNext).toHaveBeenCalled();
    expect(screen.getByText("Vertragsende")).toBeInTheDocument();
  });

  it("nur Lesen: keine Auswahl, kein Hauptknopf – ohne die Werte zu verstecken", () => {
    panel(twoValues(), { canReview: false });
    expect(screen.getAllByRole("radio")[0]).toBeDisabled();
    expect(screen.queryByRole("button", { name: /Weiter$/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Nur Lesen/)).toBeInTheDocument();
  });
});
