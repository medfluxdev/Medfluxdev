import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractAttachmentsPanel from "@/components/contracts/detail/ContractAttachmentsPanel";
import ContractRelationsPanel from "@/components/contracts/detail/ContractRelationsPanel";
import type { ContractDocumentDto, ContractRelationsDto } from "@/lib/domain-api/contractDocuments";

const api = vi.hoisted(() => ({
  listContractDocuments: vi.fn(),
  uploadContractDocuments: vi.fn(),
  updateContractDocument: vi.fn(),
  getContractRelations: vi.fn(),
  linkFramework: vi.fn(),
  unlinkFramework: vi.fn(),
}));

vi.mock("@/lib/domain-api/contractDocuments", () => api);
vi.mock("@/lib/domain-api/catalogs", () => ({
  listLookups: vi.fn().mockResolvedValue({ field_keys: [], items: [
    { id: "t1", field_key: "attachment_type", code: "vertrag", label: "Vertrag", description: null, is_active: true, sort_order: 0 },
    { id: "t2", field_key: "attachment_type", code: "nachtrag", label: "Nachtrag", description: null, is_active: true, sort_order: 1 },
    { id: "t3", field_key: "attachment_type", code: "laufzettel", label: "Interner Laufzettel", description: null, is_active: true, sort_order: 2 },
  ] }),
}));

function doc(overrides: Partial<ContractDocumentDto> = {}): ContractDocumentDto {
  return {
    link_id: "l-1", document_version_id: "v-1", original_filename: "vertrag.pdf", title: "vertrag.pdf", attachment_type: "vertrag",
    role: "main", is_main: true, is_valid: true, added_by_name: "Admin", added_at: "2026-10-01T10:00:00Z", analyzable: true, ...overrides,
  };
}

const RELATIONS: ContractRelationsDto = {
  is_framework: false,
  frameworks: [{ relation_id: "r-1", contract_id: "f-1", register_number: "000010", short_description: "Rahmenvertrag MT", business_status: "gueltig", confirmed: false, rationale: "KI-Vorschlag: Dokument nennt Rahmenvertrag mit Nummer RV-2024-77." }],
  members: [],
  framework_options: [{ contract_id: "f-2", register_number: "000011", short_description: "Rahmenvertrag IT" }],
};

describe("Anlagen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listContractDocuments.mockResolvedValue({ items: [doc(), doc({ link_id: "l-2", title: "1. Nachtrag", original_filename: "n.pdf", attachment_type: "nachtrag", role: "amendment", is_main: false })], attachment_types: [] });
    api.uploadContractDocuments.mockResolvedValue({ results: [{ original_filename: "nachtrag2.pdf", status: "analyzed", message: "Analyse abgeschlossen: 2 Änderungsvorschlag/-vorschläge in den Stammdaten.", requires_review: true, document_version_id: "v-3" }], items: [doc()] });
    api.updateContractDocument.mockResolvedValue({ items: [doc()] });
  });

  it("lädt Nachträge hoch, meldet Vorschläge und verwaltet Haupt-/Gültigkeitsstatus", async () => {
    const user = userEvent.setup();
    const onAnalyzed = vi.fn();
    const { container } = render(<ContractAttachmentsPanel contractId="c-1" orgSlug="test-klinik" onAnalyzed={onAnalyzed} />);
    expect(await screen.findByText("1. Nachtrag")).toBeInTheDocument();
    expect(screen.getByText("Hauptdokument")).toBeInTheDocument();
    await waitFor(() => expect(within(screen.getByLabelText("Dokumentart")).getByRole("option", { name: "Interner Laufzettel" })).toBeInTheDocument());
    expect(await axe(container)).toHaveNoViolations();

    const file = new File(["%PDF-1.4"], "nachtrag2.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("Dateien (PDF/DOCX)"), file);
    await user.selectOptions(screen.getByLabelText("Dokumentart"), "nachtrag");
    await user.click(screen.getByRole("button", { name: "Hinzufügen" }));
    expect(api.uploadContractDocuments).toHaveBeenCalledWith("test-klinik", "c-1", expect.objectContaining({ attachmentType: "nachtrag", analyze: true, files: [file] }));
    expect(await screen.findByText(/2 Änderungsvorschlag/)).toBeInTheDocument();
    expect(onAnalyzed).toHaveBeenCalled();
  });

  it("deaktiviert die Analyse für nicht analysierbare Dokumentarten", async () => {
    const user = userEvent.setup();
    render(<ContractAttachmentsPanel contractId="c-1" orgSlug="test-klinik" />);
    await screen.findByText("1. Nachtrag");
    await waitFor(() => expect(within(screen.getByLabelText("Dokumentart")).getByRole("option", { name: "Interner Laufzettel" })).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText("Dokumentart"), "laufzettel");
    expect(screen.getByLabelText(/Mit lokaler KI analysieren/)).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Als Hauptdokument" }));
    expect(api.updateContractDocument).toHaveBeenCalledWith("test-klinik", "c-1", "l-2", { is_main: true });
  });
});

describe("Verknüpfungen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getContractRelations.mockResolvedValue(RELATIONS);
    api.linkFramework.mockResolvedValue({ ...RELATIONS, frameworks: [{ ...RELATIONS.frameworks[0], confirmed: true }] });
    api.unlinkFramework.mockResolvedValue({ ...RELATIONS, frameworks: [] });
  });

  it("bestätigt einen KI-Vorschlag und verknüpft manuell", async () => {
    const user = userEvent.setup();
    render(<ContractRelationsPanel contractId="c-1" orgSlug="test-klinik" />);
    expect(await screen.findByText("KI-Vorschlag – bitte bestätigen")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(api.linkFramework).toHaveBeenCalledWith("test-klinik", "c-1", "f-1");
    expect(screen.queryByText("KI-Vorschlag – bitte bestätigen")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Rahmenvertrag auswählen"), "f-2");
    await user.click(screen.getByRole("button", { name: "Verknüpfen" }));
    expect(api.linkFramework).toHaveBeenLastCalledWith("test-klinik", "c-1", "f-2");
  });
});

describe("Import: zu bestehendem Vertrag hinzufügen", () => {
  it("sucht den Vertrag und lädt die Kündigung als Anlage hoch", async () => {
    vi.clearAllMocks();
    const { default: AttachToExistingContract } = await import("@/components/contracts/AttachToExistingContract");
    const contracts = await import("@/lib/domain-api/contracts");
    vi.spyOn(contracts, "listContracts").mockResolvedValue({ items: [{ contract_id: "c-7", register_number: "000007", contract_title: "Wartung MRT", supplier: "MEDTEC" }] } as never);
    api.uploadContractDocuments.mockResolvedValue({ results: [{ original_filename: "kuendigung.pdf", status: "analyzed", message: "Analyse abgeschlossen: 1 Änderungsvorschlag/-vorschläge in den Stammdaten.", requires_review: true, document_version_id: "v-9" }], items: [] });
    const user = userEvent.setup();
    render(<AttachToExistingContract organizationSlug="test-klinik" />);
    await waitFor(() => expect(screen.getByRole("option", { name: "000007 · Wartung MRT" })).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText("Vertrag"), "c-7");
    await user.selectOptions(screen.getByLabelText("Dokumentart"), "vertrag");
    const file = new File(["%PDF-1.4"], "kuendigung.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("Dateien (PDF/DOCX)"), file);
    await user.click(screen.getByRole("button", { name: "Hinzufügen (1)" }));
    expect(api.uploadContractDocuments).toHaveBeenCalledWith("test-klinik", "c-7", { files: [file], attachmentType: "vertrag", analyze: true });
    expect(await screen.findByRole("link", { name: "Vertrag öffnen" })).toHaveAttribute("href", "/contracts/c-7?tab=register");
  });
});
