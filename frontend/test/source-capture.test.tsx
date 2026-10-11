import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SourceCapture from "@/components/contracts/detail/SourceCapture";
import { ApiError } from "@/lib/api";

const api = vi.hoisted(() => ({ getDocumentPageText: vi.fn(), previewDocumentCapture: vi.fn(), captureFromDocument: vi.fn() }));
vi.mock("@/lib/domain-api/register", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/register")>()),
  ...api,
}));

const PAGE = {
  page: 4, pages: [1, 2, 3, 4], text: "§ 3 Laufzeit\nDer Vertrag beginnt am 01.01.2025 und läuft drei Jahre.",
  fields: [{ key: "term_start_date", label: "Vertragsbeginn" }, { key: "initial_term", label: "Laufzeit" }],
};

function capture(extra: { onSaved?: () => void } = {}) {
  return render(<SourceCapture contractId="c-1" orgSlug="test-klinik" documentVersionId="dv-1" page={4} onSaved={extra.onSaved ?? vi.fn()} onClose={vi.fn()} />);
}

function select(node: Node, from: number, to: number) {
  const range = document.createRange();
  range.setStart(node, from);
  range.setEnd(node, to);
  const selection = window.getSelection()!;
  selection.removeAllRanges();
  selection.addRange(range);
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getDocumentPageText.mockResolvedValue(PAGE);
  api.previewDocumentCapture.mockResolvedValue({ preview: "01.01.2025", page: 4, quote: "beginnt am 01.01.2025" });
  api.captureFromDocument.mockResolvedValue({});
});

describe("Angabe aus dem Text übernehmen", () => {
  it("markierte Stelle → Feld → Vorschau → Übernehmen", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    const { container } = capture({ onSaved });
    const text = await screen.findByRole("region", { name: "Text der Seite 4, so wie MedFlux ihn gelesen hat" });
    expect(api.getDocumentPageText).toHaveBeenCalledWith("test-klinik", "c-1", "dv-1", 4);
    const node = text.firstChild!;
    const start = PAGE.text.indexOf("beginnt am 01.01.2025");
    select(node, start, start + "beginnt am 01.01.2025".length);
    fireEvent.mouseUp(text);
    expect(screen.getByRole("textbox", { name: "Markierte Stelle (wörtlich)" })).toHaveValue("beginnt am 01.01.2025");
    // Ohne Feld keine Vorschau und kein Übernehmen.
    expect(screen.getByRole("button", { name: "Übernehmen" })).toBeDisabled();
    await user.selectOptions(screen.getByRole("combobox", { name: "Übernehmen als" }), "term_start_date");
    expect(await screen.findByText("Wird gespeichert als: 01.01.2025")).toBeInTheDocument();
    expect(api.previewDocumentCapture).toHaveBeenCalledWith("test-klinik", "c-1", { field_key: "term_start_date", document_version_id: "dv-1", page: 4, quote: "beginnt am 01.01.2025" });
    expect(await axe(container)).toHaveNoViolations();
    await user.click(screen.getByRole("button", { name: "Übernehmen" }));
    expect(api.captureFromDocument).toHaveBeenCalledWith("test-klinik", "c-1", { field_key: "term_start_date", document_version_id: "dv-1", page: 4, quote: "beginnt am 01.01.2025" });
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("zeigt, warum eine Stelle nicht passt, und speichert dann nicht", async () => {
    const user = userEvent.setup();
    api.previewDocumentCapture.mockRejectedValue(new ApiError("Die markierte Stelle enthält mehrere Daten. Bitte nur das gemeinte Datum markieren.", { status: 422 }));
    capture();
    await screen.findByRole("region", { name: /Text der Seite 4/ });
    await user.type(screen.getByRole("textbox", { name: "Markierte Stelle (wörtlich)" }), "01.01.2025 bis 31.12.2027");
    await user.selectOptions(screen.getByRole("combobox", { name: "Übernehmen als" }), "term_start_date");
    expect(await screen.findByText(/mehrere Daten/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Übernehmen" })).toBeDisabled();
  });

  it("ohne gelesenen Text: ehrlicher Hinweis statt leerem Feld", async () => {
    api.getDocumentPageText.mockResolvedValue({ ...PAGE, text: null });
    capture();
    expect(await screen.findByText(/Für Seite 4 liegt kein gelesener Text vor/)).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
