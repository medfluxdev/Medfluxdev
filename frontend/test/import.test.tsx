import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ImportPage from "@/app/import/page";
import type { ImportBatchResponse } from "@/lib/types";

const apiUploadMock = vi.fn();
const apiPostMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiUpload: (...args: unknown[]) => apiUploadMock(...args),
  apiPost: (...args: unknown[]) => apiPostMock(...args),
}));

beforeEach(() => {
  vi.clearAllMocks();
  apiUploadMock.mockReset();
  apiPostMock.mockReset();
});

async function selectedFile(name = "wartung.pdf", type = "application/pdf"): Promise<File> {
  return new File(["%PDF-1.7 test"], name, { type });
}

describe("Import (FE-08)", () => {
  it("zeigt Ausgangszustand und Zielbereich klar an", () => {
    render(<ImportPage />);
    expect(screen.getByRole("heading", { name: "Verträge importieren" })).toBeInTheDocument();
    expect(screen.getByText("Zielbereich")).toBeInTheDocument();
    expect(screen.getByText(/Noch keine Dateien ausgewählt/)).toBeInTheDocument();
  });

  it("erlaubt PDF/DOCX und weist nicht unterstützte Dateien vor dem Upload ab", async () => {
    const utils = render(<ImportPage />);
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, [await selectedFile(), await selectedFile("notiz.txt", "text/plain")], { applyAccept: false });
    expect(screen.getByText("wartung.pdf")).toBeInTheDocument();
    expect(screen.queryByText("notiz.txt", { selector: ".file-name" })).not.toBeInTheDocument();
    expect(screen.getByText(/Nicht unterstützte Dateien wurden nicht hinzugefügt/)).toBeInTheDocument();
  });

  it("trennt Import- und Analyseergebnis pro Datei", async () => {
    const res: ImportBatchResponse = {
      total: 2,
      successful: 1,
      failed: 1,
      duplicates: 0,
      documents: [
        { original_filename: "wartung.pdf", status: "imported", size: 1024, analysis_status: "success", message: null },
        { original_filename: "alt.docx", document_version_id: "dv-fail", status: "analysis_failed", size: 2048, analysis_status: "failed", message: "Dokumentanalyse konnte nicht abgeschlossen werden." },
      ],
    };
    apiUploadMock.mockResolvedValue(res);
    const utils = render(<ImportPage />);
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, [await selectedFile("wartung.pdf"), await selectedFile("alt.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")]);
    await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
    await waitFor(() => expect(screen.getByText("Import-Ergebnis")).toBeInTheDocument());

    const importedSummary = screen.getByText("importiert").closest("div");
    const successSummary = screen.getByText("Analyse erfolgreich").closest("div");
    const failedSummary = screen.getByText("Analyse fehlgeschlagen").closest("div");
    expect(importedSummary && within(importedSummary).getByText("2")).toBeTruthy();
    expect(successSummary && within(successSummary).getByText("1")).toBeTruthy();
    expect(failedSummary && within(failedSummary).getByText("1")).toBeTruthy();
    expect(screen.getAllByText("Importiert").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Erfolgreich")).toBeInTheDocument();
    expect(screen.getByText("Fehlgeschlagen")).toBeInTheDocument();
    expect(screen.getByText("Dokumentanalyse konnte nicht abgeschlossen werden.")).toBeInTheDocument();
  });

  it("zeigt Teilanalyse ehrlich und verlinkt direkt auf die manuelle Prüfung", async () => {
    const res: ImportBatchResponse = {
      total: 1,
      successful: 1,
      failed: 0,
      duplicates: 0,
      documents: [{
        original_filename: "teilweise.pdf",
        document_version_id: "dv-partial",
        contract_id: "contract-123",
        status: "imported",
        size: 4096,
        analysis_status: "partial",
        requires_review: true,
        message: "Analyse abgeschlossen; Angaben prüfen.",
      }],
    };
    apiUploadMock.mockResolvedValue(res);
    const utils = render(<ImportPage />);
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, await selectedFile("teilweise.pdf"));
    await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
    await waitFor(() => expect(screen.getByText("Teilanalyse – Prüfung erforderlich")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Zur manuellen Prüfung" })).toHaveAttribute("href", "/contracts/contract-123?tab=documents&subtab=review");
  });

  it("kennzeichnet Duplikate ohne eine erneute Analyse vorzutäuschen", async () => {
    const res: ImportBatchResponse = {
      total: 1,
      successful: 0,
      failed: 0,
      duplicates: 1,
      documents: [{ original_filename: "doppelt.pdf", status: "duplicate", size: 1024, analysis_status: null, message: "Dokument wurde bereits verarbeitet." }],
    };
    apiUploadMock.mockResolvedValue(res);
    const utils = render(<ImportPage />);
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, await selectedFile("doppelt.pdf"));
    await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
    await waitFor(() => expect(screen.getByText("Duplikat")).toBeInTheDocument());
    expect(screen.getByText("Nicht erneut analysiert")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyse erneut starten" })).not.toBeInTheDocument();
  });

  it("bietet für fehlgeschlagene Analysen Retry über die gespeicherte Dokumentversion", async () => {
    const res: ImportBatchResponse = {
      total: 1,
      successful: 0,
      failed: 1,
      duplicates: 0,
      documents: [{ original_filename: "kaputt.pdf", document_version_id: "dv-1234", status: "analysis_failed", size: 1024, analysis_status: "failed", message: "Dokumentanalyse konnte nicht abgeschlossen werden." }],
    };
    apiUploadMock.mockResolvedValue(res);
    apiPostMock.mockResolvedValue({ status: "imported", analysis_status: "success", message: "Analyse erfolgreich.", contract_id: null });

    const utils = render(<ImportPage />);
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, await selectedFile("kaputt.pdf"));
    await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
    await waitFor(() => expect(screen.getByText("Import-Ergebnis")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Analyse erneut starten" }));
    expect(apiPostMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/documents/dv-1234/retry?organization_slug=test-klinik"),
      {},
      120000,
    );
    await waitFor(() => expect(screen.getByText("Analyse erfolgreich.")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Analyse erneut starten" })).not.toBeInTheDocument();
  });

  it("täuscht während synchroner Serververarbeitung keine Prozentwerte oder Live-Stufen vor", async () => {
    render(<ImportPage />);
    const dropzone = screen.getByRole("button", { name: "Dateien hinzufügen. Klicken oder Dateien hierher ziehen." });
    const fileInput = dropzone.querySelector('input[type="file"]') as HTMLInputElement;
    apiUploadMock.mockImplementation(() => new Promise(() => {}));
    await userEvent.upload(fileInput, await selectedFile("hängt.pdf"));
    await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
    await waitFor(() => expect(screen.getByText(/Die aktuelle API meldet keine einzelnen Live-Stufen/)).toBeInTheDocument());
    expect(screen.queryByText(/%\s*$/)).not.toBeInTheDocument();
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße im Ausgangszustand", async () => {
    const { container } = render(<ImportPage />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});