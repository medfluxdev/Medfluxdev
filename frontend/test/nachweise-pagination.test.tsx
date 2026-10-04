import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NachweisePage from "@/app/nachweise/page";

const listContracts = vi.fn();
const getContract = vi.fn();
vi.mock("@/lib/domain-api/contracts", () => ({
  listContracts: (...args: unknown[]) => listContracts(...args),
  getContract: (...args: unknown[]) => getContract(...args),
}));
vi.mock("@/components/contracts/detail/PdfViewer", () => ({ default: () => null }));
vi.mock("@/components/contracts/detail/EvidencePane", () => ({ default: () => null }));
vi.mock("@/components/contracts/detail/SourceLink", () => ({ default: ({ document }: { document: { document_version_id: string } }) => <span>{document.document_version_id}</span> }));

const entry = (id: string) => ({
  contract_id: id, contract_number: id, contract_title: id, supplier: "Supplier",
});

beforeEach(() => {
  vi.clearAllMocks();
  getContract.mockImplementation((id: string) =>
    Promise.resolve({ contract_id: id, documents: [], evidence: [] }));
});

describe("Evidence contract pagination", () => {
  it("loads page two and replaces the previous contract selection", async () => {
    listContracts.mockImplementation((_org: string, query: { page: number }) =>
      Promise.resolve(query.page === 1
        ? { items: [entry("first")], has_more: true, total_count: 101 }
        : { items: [entry("second")], has_more: false, total_count: 101 }));
    render(<NachweisePage />);
    await waitFor(() => expect(screen.getByRole("option", { name: /first/ })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Nächste 100" }));
    await waitFor(() => expect(listContracts).toHaveBeenCalledWith("test-klinik", { page_size: 100, page: 2 }));
    await waitFor(() => expect(screen.getByRole("option", { name: /second/ })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: /first/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nächste 100" })).toBeDisabled();
  });

  it("returns to page one without retaining page-two selection", async () => {
    listContracts.mockImplementation((_org: string, query: { page: number }) =>
      Promise.resolve(query.page === 1
        ? { items: [entry("first")], has_more: true, total_count: 101 }
        : { items: [entry("second")], has_more: false, total_count: 101 }));
    render(<NachweisePage />);
    await waitFor(() => expect(screen.getByRole("option", { name: /first/ })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Nächste 100" }));
    await waitFor(() => expect(screen.getByRole("option", { name: /second/ })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Vorherige 100" }));
    await waitFor(() => expect(screen.getByRole("option", { name: /first/ })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: /second/ })).not.toBeInTheDocument();
  });

  it("ignores a delayed detail response from the previous page", async () => {
    let resolveOld!: (value: unknown) => void;
    const oldDetail = new Promise((resolve) => { resolveOld = resolve; });
    listContracts.mockImplementation((_org: string, query: { page: number }) =>
      Promise.resolve(query.page === 1
        ? { items: [entry("first")], has_more: true, total_count: 101 }
        : { items: [entry("second")], has_more: false, total_count: 101 }));
    getContract.mockImplementation((id: string) => id === "first"
      ? oldDetail
      : Promise.resolve({ contract_id: "second", documents: [], evidence: [] }));
    render(<NachweisePage />);
    await waitFor(() => expect(getContract).toHaveBeenCalledWith("first", "test-klinik"));
    await userEvent.click(screen.getByRole("button", { name: "Nächste 100" }));
    await waitFor(() => expect(getContract).toHaveBeenCalledWith("second", "test-klinik"));
    resolveOld({ contract_id: "first", documents: [{ document_version_id: "STALE-DOCUMENT", viewer_supported: true }], evidence: [] });
    await waitFor(() => expect(screen.getByRole("option", { name: /second/ })).toBeInTheDocument());
    expect(screen.queryByText("STALE-DOCUMENT")).not.toBeInTheDocument();
  });

});
