import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PageTextPicker from "@/components/contracts/detail/PageTextPicker";

const api = vi.hoisted(() => ({ getDocumentPageText: vi.fn() }));
vi.mock("@/lib/domain-api/register", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/register")>()),
  ...api,
}));

beforeEach(() => {
  vi.clearAllMocks();
  api.getDocumentPageText.mockImplementation(async (_org: string, _contract: string, _doc: string, page: number) => ({
    page, pages: [1, 2, 3], text: `Text der Seite ${page}`, fields: [],
  }));
});

describe("Stelle im Dokument markieren: jede Seite ist erreichbar", () => {
  it("startet auf der Seite des Belegs und wechselt per Auswahl und Pfeil auf andere Seiten", async () => {
    const user = userEvent.setup();
    render(<PageTextPicker contractId="c-1" orgSlug="test-klinik" documentVersionId="dv-1" page={2} onPick={vi.fn()} />);
    expect(await screen.findByText("Text der Seite 2")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Seite" })).toHaveValue("2");
    await user.click(screen.getByRole("button", { name: "Nächste Seite" }));
    expect(await screen.findByText("Text der Seite 3")).toBeInTheDocument();
    expect(api.getDocumentPageText).toHaveBeenLastCalledWith("test-klinik", "c-1", "dv-1", 3);
    await user.selectOptions(screen.getByRole("combobox", { name: "Seite" }), "1");
    expect(await screen.findByText("Text der Seite 1")).toBeInTheDocument();
  });

  it("bei mehreren Dokumenten lässt sich das Dokument wechseln", async () => {
    const user = userEvent.setup();
    render(<PageTextPicker contractId="c-1" orgSlug="test-klinik" documentVersionId="dv-1" page={2} onPick={vi.fn()}
      documents={[{ id: "dv-1", label: "Hauptvertrag.pdf" }, { id: "dv-2", label: "Nachtrag.pdf" }]} />);
    await screen.findByText("Text der Seite 2");
    await user.selectOptions(screen.getByRole("combobox", { name: "Dokument" }), "dv-2");
    expect(await screen.findByText("Text der Seite 1")).toBeInTheDocument();
    expect(api.getDocumentPageText).toHaveBeenLastCalledWith("test-klinik", "c-1", "dv-2", 1);
  });
});
