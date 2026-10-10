import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ImportPage from "@/app/import/page";
import type { ImportBatchResponse } from "@/lib/types";

const apiUploadMock = vi.fn();
const apiPostMock = vi.fn();
const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiUpload: (...args: unknown[]) => apiUploadMock(...args),
  apiPost: (...args: unknown[]) => apiPostMock(...args),
  apiGet: (...args: unknown[]) => apiGetMock(...args),
}));

let reviewMode = "manual";
let failedJobs: Record<string, unknown>[] = [];

beforeEach(() => {
  reviewMode = "manual";
  failedJobs = [];
  vi.clearAllMocks();
  apiUploadMock.mockReset();
  apiPostMock.mockReset();
  apiGetMock.mockReset();
  apiGetMock.mockImplementation((path: string) => path.startsWith("/api/review-settings")
    ? Promise.resolve({ review_mode: reviewMode, review_mode_label: "", options: [], can_edit: false })
    : path.startsWith("/api/processing-jobs")
    ? Promise.resolve({ items: failedJobs, total: failedJobs.length })
    : path.startsWith("/api/organization-structure")
    ? Promise.resolve({ hospitals: [{ id: "hospital-1", name: "Klinikum Mitte", code: "KM", is_active: true }], departments: [
      { id: "dept-resp", hospital_id: "hospital-1", parent_id: null, name: "Radiologie", code: "RAD", is_active: true },
      { id: "dept-use", hospital_id: "hospital-1", parent_id: null, name: "Neurochirurgie", code: "NC", is_active: true },
    ] })
    : Promise.resolve({ items: [{ id: "center-1", hospital_id: "hospital-1", department_id: "dept-resp", code: "RAD-1", name: "Radiologie", is_active: true }] }));
});

async function toFiles() {
  await userEvent.click(await screen.findByRole("button", { name: "Weiter zu den Dateien" }));
  await waitFor(() => expect(screen.getByRole("heading", { name: "Dateien auswählen" })).toBeInTheDocument());
}

async function toConfirmAndStart(mode?: RegExp) {
  await userEvent.click(screen.getByRole("button", { name: /Weiter zur Erfassungsart/ }));
  if (mode) await userEvent.click(screen.getByRole("radio", { name: mode }));
  await userEvent.click(screen.getByRole("button", { name: /Weiter zur Prüfung/ }));
  const same = screen.queryByRole("checkbox", { name: /Dateien gehören zu diesem Ziel/ });
  if (same) await userEvent.click(same);
  await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
}

async function selectedFile(name = "wartung.pdf", type = "application/pdf"): Promise<File> {
  return new File(["%PDF-1.7 test"], name, { type });
}

describe("Import (FE-08)", () => {
  it("führt in Schritten: Ziel, Dateien, Prüfen & starten, Ergebnis", async () => {
    render(<ImportPage />);
    expect(screen.getByRole("heading", { name: "Verträge importieren" })).toBeInTheDocument();
    expect(screen.getByText("Zielbereich")).toBeInTheDocument();
    expect(screen.getByText("Ziel").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("link", { name: /Ohne Dokument manuell erfassen/ })).toHaveAttribute("href", "/contracts/new");
    await toFiles();
    expect(screen.getByText(/Noch keine Dateien ausgewählt/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Weiter zur Erfassungsart/ })).toBeDisabled();
  });

  it("erlaubt PDF/DOCX und weist nicht unterstützte Dateien vor dem Upload ab", async () => {
    const utils = render(<ImportPage />);
    await toFiles();
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
    await toFiles();
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, [await selectedFile("wartung.pdf"), await selectedFile("alt.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")]);
    await toConfirmAndStart();
    await waitFor(() => expect(screen.getByText("Import-Ergebnis")).toBeInTheDocument());

    const importedSummary = screen.getByText("importiert").closest("div");
    const successSummary = screen.getByText("Analyse erfolgreich").closest("div");
    const failedSummary = screen.getByText("Analyse fehlgeschlagen").closest("div");
    expect(importedSummary && within(importedSummary).getByText("2")).toBeTruthy();
    expect(successSummary && within(successSummary).getByText("1")).toBeTruthy();
    expect(failedSummary && within(failedSummary).getByText("1")).toBeTruthy();
    expect(screen.getByText("Importiert")).toBeInTheDocument();
    expect(screen.getByText("Importiert – Analyse fehlgeschlagen")).toBeInTheDocument();
    expect(screen.getByText("Erfolgreich")).toBeInTheDocument();
    expect(screen.getByText("Fehlgeschlagen")).toBeInTheDocument();
    expect(screen.getByText("Dokumentanalyse konnte nicht abgeschlossen werden.")).toBeInTheDocument();
  });

  it("sendet die gewählte Vertragszuordnung gemeinsam mit dem Upload", async () => {
    apiUploadMock.mockResolvedValue({ total: 1, successful: 1, failed: 0, duplicates: 0, documents: [] });
    const utils = render(<ImportPage />);
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Krankenhaus für Import" })).toHaveValue("hospital-1"));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Verantwortliche Abteilung für Import" }), "dept-resp");
    await userEvent.selectOptions(screen.getByRole("listbox", { name: "Nutzende Abteilungen für Import" }), "dept-use");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Kostenstelle für Import" }), "center-1");
    await toFiles();
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = await selectedFile();
    await userEvent.upload(input, file);
    await toConfirmAndStart();
    await waitFor(() => expect(apiUploadMock).toHaveBeenCalled());
    expect(apiUploadMock).toHaveBeenCalledWith("/api/documents/import", [file], "test-klinik", undefined, {
      assignment_hospital_id: "hospital-1",
      responsible_department_id: "dept-resp",
      beneficiary_department_ids: ["dept-use"],
      cost_center_id: "center-1",
      intake_mode: "ai_human_review",
      same_destination_confirmed: undefined,
    });
  });

  it("fragt die Erfassungsart ab und speichert bei manueller Eingabe ohne KI-Analyse", async () => {
    apiUploadMock.mockResolvedValue({ total: 1, successful: 1, failed: 0, duplicates: 0, documents: [
      { original_filename: "wartung.pdf", status: "imported", size: 1024, analysis_status: null, contract_id: "c-9", requires_review: false, message: "Original gespeichert" },
    ] });
    const utils = render(<ImportPage />);
    await toFiles();
    await userEvent.upload(utils.container.querySelector('input[type="file"]') as HTMLInputElement, await selectedFile());
    await userEvent.click(screen.getByRole("button", { name: /Weiter zur Erfassungsart/ }));
    expect(screen.getByRole("radio", { name: /mit manueller Prüfung \(empfohlen\)/ })).toBeChecked();
    // Automatische Übernahme ist ohne Freigabe der Organisation gesperrt.
    expect(screen.getByRole("radio", { name: /automatische Übernahme nur verifizierter Angaben/ })).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: /Manuelle Eingabe/ }));
    await userEvent.click(screen.getByRole("button", { name: /Weiter zur Prüfung/ }));
    expect(screen.getByText("Manuelle Eingabe", { selector: "dd" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
    await waitFor(() => expect(apiUploadMock).toHaveBeenCalled());
    expect(apiUploadMock.mock.calls[0][4]).toMatchObject({ intake_mode: "manual" });
    expect(await screen.findByText("Keine Analyse (manuelle Erfassung)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Vertragsdaten erfassen" })).toHaveAttribute("href", "/contracts/c-9?tab=register");
  });

  it("erlaubt die automatische Übernahme nur nach Freigabe", async () => {
    reviewMode = "auto_noncritical";
    const utils = render(<ImportPage />);
    await toFiles();
    await userEvent.upload(utils.container.querySelector('input[type="file"]') as HTMLInputElement, await selectedFile());
    await userEvent.click(screen.getByRole("button", { name: /Weiter zur Erfassungsart/ }));
    await waitFor(() => expect(screen.getByRole("radio", { name: /automatische Übernahme nur verifizierter Angaben/ })).toBeEnabled());
  });

  it("verlangt bei mehreren Dateien die Bestätigung des gemeinsamen Ziels", async () => {
    apiUploadMock.mockResolvedValue({ total: 2, successful: 2, failed: 0, duplicates: 0, documents: [] });
    const utils = render(<ImportPage />);
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Krankenhaus für Import" })).toHaveValue("hospital-1"));
    await toFiles();
    await userEvent.upload(utils.container.querySelector('input[type="file"]') as HTMLInputElement, [await selectedFile("a.pdf"), await selectedFile("b.pdf")]);
    await userEvent.click(screen.getByRole("button", { name: /Weiter zur Erfassungsart/ }));
    await userEvent.click(screen.getByRole("button", { name: /Weiter zur Prüfung/ }));
    const start = screen.getByRole("button", { name: /Import starten/ });
    expect(start).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Alle 2 Dateien gehören zu diesem Ziel (Klinikum Mitte)." }));
    expect(start).toBeEnabled();
    await userEvent.click(start);
    await waitFor(() => expect(apiUploadMock).toHaveBeenCalled());
    expect(apiUploadMock.mock.calls[0][4]).toMatchObject({ same_destination_confirmed: "true" });
  });

  it("listet fehlgeschlagene Importe mit verständlicher Meldung und erneuter Analyse", async () => {
    failedJobs = [
      { id: "run-2", document_version_id: "dv-1", status: "failed", result_label_de: "Lokale KI nicht verfügbar.", original_filename: "impella.pdf", contract_id: "c-1", created_at: "2026-10-09T10:00:00Z", error: null, message: null },
      { id: "run-1", document_version_id: "dv-1", status: "failed", result_label_de: "Älterer Lauf", original_filename: "impella.pdf", contract_id: "c-1", created_at: "2026-10-08T10:00:00Z", error: null, message: null },
    ];
    apiPostMock.mockResolvedValue({ status: "imported", analysis_status: "success" });
    render(<ImportPage />);
    const section = await screen.findByRole("region", { name: "Fehlgeschlagene Importe (1)" });
    expect(within(section).getByText("impella.pdf")).toBeInTheDocument();
    expect(within(section).getByText("Lokale KI nicht verfügbar.")).toBeInTheDocument();
    expect(within(section).queryByText("Älterer Lauf")).not.toBeInTheDocument();
    expect(within(section).getByRole("link", { name: "Vertrag ansehen" })).toHaveAttribute("href", "/contracts/c-1");
    await userEvent.click(within(section).getByRole("button", { name: "Analyse erneut starten" }));
    await waitFor(() => expect(apiPostMock).toHaveBeenCalledWith(expect.stringContaining("/api/documents/dv-1/retry"), {}, expect.any(Number)));
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
    await toFiles();
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, await selectedFile("teilweise.pdf"));
    await toConfirmAndStart();
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
    await toFiles();
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, await selectedFile("doppelt.pdf"));
    await toConfirmAndStart();
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
    await toFiles();
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    await userEvent.upload(input, await selectedFile("kaputt.pdf"));
    await toConfirmAndStart();
    await waitFor(() => expect(screen.getByText("Import-Ergebnis")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Analyse erneut starten" }));
    expect(apiPostMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/documents/dv-1234/retry?organization_slug=test-klinik"),
      {},
      30 * 60 * 1000,
    );
    await waitFor(() => expect(screen.getByText("Analyse erfolgreich.")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Analyse erneut starten" })).not.toBeInTheDocument();
  });

  it("täuscht während synchroner Serververarbeitung keine Prozentwerte oder Live-Stufen vor", async () => {
    render(<ImportPage />);
    await toFiles();
    const dropzone = screen.getByRole("button", { name: "Dateien hinzufügen. Klicken oder Dateien hierher ziehen." });
    const fileInput = dropzone.querySelector('input[type="file"]') as HTMLInputElement;
    apiUploadMock.mockImplementation(() => new Promise(() => {}));
    await userEvent.upload(fileInput, await selectedFile("hängt.pdf"));
    await toConfirmAndStart();
    await waitFor(() => expect(screen.getByText("Dateien werden übertragen und lokal verarbeitet.")).toBeInTheDocument());
    expect(screen.queryByText(/%\s*$/)).not.toBeInTheDocument();
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße im Ausgangszustand", async () => {
    const { container } = render(<ImportPage />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
