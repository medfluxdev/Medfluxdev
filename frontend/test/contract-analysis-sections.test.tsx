import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractBackendAnalysisPanel from "@/components/contracts/detail/ContractBackendAnalysisPanel";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

vi.mock("@/lib/domain-api/intelligenceAnalytics", () => ({
  getContractRiskAnalysis: vi.fn().mockResolvedValue(null),
  getAuthorityDiagnostics: vi.fn().mockResolvedValue(null),
  simulateContractTermination: vi.fn(),
}));
vi.mock("@/lib/domain-api/processingJobs", () => ({ listProcessingJobs: vi.fn().mockResolvedValue({ items: [] }) }));

function data(sections: ContractDetailResponse["sections"]): ContractDetailResponse {
  return {
    contract_id: "c-1",
    documents: [],
    equipment: [{ id: "e-1", device_name: "Impella", coverage_start: "2025-01-01", coverage_end: null, review_reasons: [] }],
    dates: {},
    costs: {},
    scope: { included_services: ["Wartung"], excluded_services: [], note_de: null },
    sla: { sla_notes: null, availability_24_7: null },
    sections,
  } as unknown as ContractDetailResponse;
}

describe("Backend-Vollanalyse: Abschnitte je Vertragstyp", () => {
  beforeEach(() => vi.clearAllMocks());

  it("Mietvertrag: kein Leistungsumfang, Geräte bleiben", async () => {
    render(<ContractBackendAnalysisPanel data={data({ type_label: "Mietvertrag", scope: false, sla: false, maintenance: false, equipment: true })} organizationSlug="test-klinik" />);
    await waitFor(() => expect(screen.getByText("Geräte – vollständige Vertragsbeziehung")).toBeInTheDocument());
    expect(screen.queryByRole("heading", { name: "Leistungsumfang" })).not.toBeInTheDocument();
  });

  it("Versicherung: weder Leistungsumfang noch Geräte; ohne Typ beides", async () => {
    const { unmount } = render(<ContractBackendAnalysisPanel data={data({ type_label: "Versicherung", scope: false, sla: false, maintenance: false, equipment: false })} organizationSlug="test-klinik" />);
    await waitFor(() => expect(screen.queryByText("Backend-Analyse wird geladen…")).not.toBeInTheDocument());
    expect(screen.queryByText("Vollständige Vertragsdaten aus dem Backend")).not.toBeInTheDocument();
    unmount();
    render(<ContractBackendAnalysisPanel data={data(null)} organizationSlug="test-klinik" />);
    await waitFor(() => expect(screen.getByRole("heading", { name: "Leistungsumfang" })).toBeInTheDocument());
    expect(screen.getByText("Geräte – vollständige Vertragsbeziehung")).toBeInTheDocument();
  });
});
