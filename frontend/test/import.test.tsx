import { render, screen, waitFor } from "@testing-library/react";
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

async function selectedFile(
  name = "wartung.pdf",
  type = "application/pdf"
): Promise<File> {
  const file = new File(["%PDF-1.7 test"], name, { type });
  return file;
}

describe("Import (STEP 15)", () => {
  it("zeigt den leeren Ausgangszustand klar an", async () => {
    render(<ImportPage />);
    expect(
      screen.getByRole("heading", { name: "Verträge importieren" })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Noch keine Dateien ausgewählt/)
    ).toBeInTheDocument();
  });

  it("erlaubt Auswahl und benennt die Datei ehrlich (nur Anzeigename)", async () => {
    const utils = render(<ImportPage />);
    const input = utils.container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    await userEvent.upload(input, await selectedFile());
    expect(screen.getByText("wartung.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Import starten/ })).toBeInTheDocument();
  });

  it("startet den Import und zeigt ein deterministisches Ergebnis", async () => {
    const res: ImportBatchResponse = {
      total: 2,
      successful: 1,
      failed: 1,
      duplicates: 0,
      documents: [
        {
          original_filename: "wartung.pdf",
          status: "imported",
          size: 1024,
          message: null,
        },
        {
          original_filename: "alt.docx",
          status: "failed",
          size: 2048,
          message: "Kein Text extrahierbar.",
        },
      ],
    };
    apiUploadMock.mockResolvedValue(res);
    const utils = render(<ImportPage />);
    const input = utils.container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    await userEvent.upload(
      input,
      await selectedFile("wartung.pdf"),
      await selectedFile("alt.docx", "application/docx")
    );
    await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
    await waitFor(() =>
      expect(screen.getByText("Import-Ergebnis")).toBeInTheDocument()
    );
    expect(
      screen.getByText("1 von 2 Dateien importiert und analysiert.")
    ).toBeInTheDocument();
    expect(screen.getAllByText("Importiert").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Fehlgeschlagen").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Kein Text extrahierbar.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zu den Verträgen" })).toHaveAttribute(
      "href",
      "/contracts"
    );
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße im Ausgangszustand", async () => {
    const { container } = render(<ImportPage />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("(Defect F) bietet für fehlgeschlagene Analysen eine ehrliche Retry-Aktion", async () => {
    const res: ImportBatchResponse = {
      total: 1,
      successful: 0,
      failed: 1,
      duplicates: 0,
      documents: [
        {
          original_filename: "kaputt.pdf",
          document_version_id: "dv-1234",
          status: "analysis_failed",
          size: 1024,
          analysis_status: "failed",
          message: "Dokumentanalyse konnte nicht abgeschlossen werden.",
        },
      ],
    };
    apiUploadMock.mockResolvedValue(res);
    apiPostMock.mockResolvedValue({
      status: "imported",
      analysis_status: "success",
      message: "Analyse erfolgreich.",
      contract_id: null,
    });

    const utils = render(<ImportPage />);
    const input = utils.container.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement;
    await userEvent.upload(input, await selectedFile("kaputt.pdf"));
    await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
    await waitFor(() =>
      expect(screen.getByText("Import-Ergebnis")).toBeInTheDocument()
    );

    const retry = screen.getByRole("button", { name: "Erneut verarbeiten" });
    await userEvent.click(retry);
    expect(apiPostMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/documents/dv-1234/retry"),
      {}
    );
    await waitFor(() =>
      expect(screen.getByText("Analyse erfolgreich.")).toBeInTheDocument()
    );
    expect(screen.queryByRole("button", { name: "Erneut verarbeiten" })).not.toBeInTheDocument();
  });

  it("(Defect F) täuscht beim Verarbeiten keinen Prozentwert vor", async () => {
    render(<ImportPage />);
    const input = screen.getByRole("button", {
      name: "Dateien hinzufügen. Klicken oder Dateien hierher ziehen.",
    }).closest(".dropzone") as HTMLElement;
    const fileInput = input.querySelector('input[type="file"]') as HTMLInputElement;
    apiUploadMock.mockImplementation(
      () => new Promise(() => {}) // hängt bewusst für die Dauer der Verifikation
    );
    await userEvent.upload(fileInput, await selectedFile("hängt.pdf"));
    await userEvent.click(screen.getByRole("button", { name: /Import starten/ }));
    await waitFor(() => expect(screen.getByText(/Verarbeitung laufen/)).toBeInTheDocument());
    expect(screen.queryByText(/%\s*$/)).not.toBeInTheDocument();
    expect(
      screen.getByText(/Fortschritt wird nicht vorgetäuscht/)
    ).toBeInTheDocument();
  });
});