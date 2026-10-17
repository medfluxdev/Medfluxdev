import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it, vi } from "vitest";
import DocumentList from "@/components/contracts/detail/DocumentList";
import type { DetailDocument } from "@/lib/contract-detail-types";

const doc = (id: string, name: string, role: string | null, mime = "application/pdf"): DetailDocument => ({
  document_version_id: id, original_filename: name, role, mime_type: mime, file_size_bytes: 1000, viewer_supported: true,
});

const DOCS = [
  doc("d1", "Servicevertrag.pdf", "main"),
  doc("d2", "Nachtrag 01.pdf", "amendment"),
  doc("d3", "Preisvereinbarung.pdf", "price_adjustment"),
  doc("d4", "Leistungsverzeichnis.pdf", "appendix"),
  doc("d5", "Geräteliste.xlsx", "appendix", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
  doc("d6", "Ansprechpartner.docx", "appendix", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
];

describe("Dokumente – Liste ab 6 Dateien", () => {
  it("gruppiert nach Art, sucht, filtert nach Typ und wählt aus", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const { container } = render(<DocumentList documents={DOCS} selectedId="d1" mainId="d1" onSelect={onSelect} />);
    const nav = screen.getByRole("navigation", { name: "Quelldokumente" });
    expect(within(nav).getByRole("button", { name: "Hauptdokument (1)" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: "Nachträge (2)" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: "Anlagen (3)" })).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /Servicevertrag\.pdf/ })).toHaveAttribute("aria-current", "true");
    expect(within(nav).getByRole("button", { name: /Geräteliste\.xlsx/ })).toHaveTextContent("XLSX · Anlage");
    expect(within(nav).getByRole("button", { name: /Preisvereinbarung\.pdf/ })).toHaveTextContent("PDF · Preisvereinbarung");
    expect(await axe(container)).toHaveNoViolations();

    await user.type(screen.getByRole("searchbox", { name: "Dateien durchsuchen" }), "nachtrag");
    expect(within(nav).queryByRole("button", { name: /Servicevertrag/ })).not.toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: "Nachträge (1)" })).toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox", { name: "Dateien durchsuchen" }));

    await user.selectOptions(screen.getByRole("combobox", { name: "Dateityp" }), "word");
    expect(within(nav).getAllByRole("button", { name: /\.(pdf|xlsx|docx)/ }).map((node) => node.textContent)).toEqual([expect.stringContaining("Ansprechpartner.docx")]);
    await user.selectOptions(screen.getByRole("combobox", { name: "Dateityp" }), "");

    await user.click(within(nav).getByRole("button", { name: "Anlagen (3)" }));
    expect(within(nav).queryByRole("button", { name: /Geräteliste/ })).not.toBeInTheDocument();
    await user.click(within(nav).getByRole("button", { name: /Nachtrag 01\.pdf/ }));
    expect(onSelect).toHaveBeenCalledWith(DOCS[1]);
  });
});
