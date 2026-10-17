import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiPost = vi.hoisted(() => vi.fn());
vi.mock("@/lib/domain-api/assistant", () => ({ askAssistant: apiPost }));

import ContractAiSummary, { SUMMARY_PROMPT } from "@/components/contracts/detail/ContractAiSummary";

const REPLY = {
  answer: "Wartungsvertrag mit ABIOMED Europe GmbH für das Impella-System. Laufzeit bis 31.03.2029.",
  contract_id: "c-1",
  evidence: [{ evidence_id: "e-1", field_ref: "dates.end_date", source_type: "page", document_version_id: "v-1", page: 3, source_text: "Der Vertrag endet am 31.03.2029.", requires_review: false }],
};

describe("Übersicht: KI-Zusammenfassung", () => {
  beforeEach(() => { apiPost.mockReset(); });

  it("erstellt die Kurzfassung erst auf Klick, gekennzeichnet als KI-Text, mit Quellen", async () => {
    const user = userEvent.setup();
    apiPost.mockResolvedValue(REPLY);
    const { container } = render(<ContractAiSummary contractId="c-1" orgSlug="test-klinik" />);
    expect(screen.getByRole("heading", { name: "KI-Zusammenfassung" })).toBeInTheDocument();
    expect(apiPost).not.toHaveBeenCalled();
    expect(screen.getByText("Noch keine Zusammenfassung erstellt.")).toBeInTheDocument();
    expect(screen.getByText("Lokal generiert · Ungeprüft · Wird nicht gespeichert.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Zusammenfassung erstellen" }));
    expect(apiPost).toHaveBeenCalledWith("test-klinik", SUMMARY_PROMPT, "c-1", expect.any(AbortSignal));
    expect(await screen.findByText(REPLY.answer)).toBeInTheDocument();
    expect(screen.getByText("KI-Text, nicht geprüft")).toBeInTheDocument();
    expect(screen.getByText("Quellenauszüge (1)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Nachweis öffnen" })).toHaveAttribute("href", "/contracts/c-1?tab=documents&subtab=evidence&source_evidence_id=e-1");
    expect(screen.getByRole("button", { name: "Neu erstellen" })).toBeInTheDocument();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("zeigt die Meldung des Servers, z. B. ohne ausgewähltes Modell", async () => {
    const user = userEvent.setup();
    apiPost.mockImplementation(async () => { throw new Error("Kein lokales KI-Modell ausgewählt."); });
    render(<ContractAiSummary contractId="c-1" orgSlug="test-klinik" />);
    await user.click(screen.getByRole("button", { name: "Zusammenfassung erstellen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Kein lokales KI-Modell ausgewählt.");
  });

  it("lässt sich während der Erstellung abbrechen", async () => {
    const user = userEvent.setup();
    let signal: AbortSignal | undefined;
    apiPost.mockImplementation((_org: string, _message: string, _id: string, given: AbortSignal) => {
      signal = given;
      // Wie fetch: läuft, bis abgebrochen wird.
      return new Promise((_resolve, reject) => given.addEventListener("abort", () => reject(new DOMException("Abgebrochen", "AbortError"))));
    });
    render(<ContractAiSummary contractId="c-1" orgSlug="test-klinik" />);
    await user.click(screen.getByRole("button", { name: "Zusammenfassung erstellen" }));
    expect(screen.getByRole("status")).toHaveTextContent("Zusammenfassung wird erstellt");
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(signal?.aborted).toBe(true);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zusammenfassung erstellen" })).toBeInTheDocument();
  });
});
