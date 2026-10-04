import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import ContentSearch from "@/components/search/ContentSearch";

const api = vi.hoisted(() => ({
  searchContents: vi.fn().mockResolvedValue({
    query: "24/7 Hotline",
    semantic: false,
    terms: [{ term: "24/7", alternatives: ["rund um die uhr"] }, { term: "hotline", alternatives: ["störungsannahme"] }],
    items: [{
      contract_id: "c-1", register_number: "000001", short_description: "Wartung CT",
      hits: [{ document_version_id: "dv-1", document: "Wartungsvertrag CT.pdf", document_valid: true, page: 2, snippet: "Die 24/7-Hotline ist rund um die Uhr erreichbar.", match: "text" }],
    }],
  }),
  getContentSearchStatus: vi.fn().mockResolvedValue({ documents: 4, indexed: 4, without_text: 1, semantic_model: null }),
}));

vi.mock("@/lib/domain-api/registerGrid", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/domain-api/registerGrid")>()),
  ...api,
}));

describe("Inhaltssuche", () => {
  it("sucht lokal und verlinkt jeden Treffer mit Dokument und Seite", async () => {
    const user = userEvent.setup();
    const { container } = render(<ContentSearch organizationSlug="test-klinik" />);
    expect(await screen.findByText(/4 von 4 Dokumenten durchsuchbar, 1 ohne lesbaren Text/)).toBeInTheDocument();
    expect(screen.getByText(/Ähnlichkeitssuche ist aus/)).toBeInTheDocument();

    await user.type(screen.getByLabelText("Suchbegriff"), "24/7 Hotline");
    await user.click(screen.getByRole("button", { name: "Suchen" }));
    expect(api.searchContents).toHaveBeenCalledWith("test-klinik", "24/7 Hotline");
    const results = await screen.findByRole("heading", { name: "1 Verträge gefunden" });
    const section = results.closest("section")!;
    expect(within(section).getByText(/24\/7 → rund um die uhr/)).toBeInTheDocument();
    expect(within(section).getByText("Die 24/7-Hotline ist rund um die Uhr erreichbar.")).toBeInTheDocument();
    expect(within(section).getByRole("link", { name: "Seite öffnen" })).toHaveAttribute(
      "href", "/contracts/c-1?tab=documents&subtab=document&source_document=dv-1&source_page=2",
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
