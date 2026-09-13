import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDetailPage from "@/app/contracts/[contract-id]/page";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  contentUrl: (contractId: string, versionId: string) =>
    `http://test.local/content/${contractId}/${versionId}`,
}));

vi.mock("pdfjs-dist", () => {
  const pageStub = {
    getViewport: ({ scale }: { scale: number }) => ({
      width: 400 * scale,
      height: 500 * scale,
    }),
    render: () => ({ promise: Promise.resolve(), cancel: () => {} }),
  };
  const docStub = {
    numPages: 3,
    getPage: async () => pageStub,
    destroy: async () => {},
  };
  return {
    GlobalWorkerOptions: { workerSrc: "" },
    getDocument: () => ({ promise: Promise.resolve(docStub) }),
  };
});

type NavState = { params: { "contract-id": string } };
const nav: NavState = {
  params: { "contract-id": "11111111-1111-1111-1111-111111111111" },
};

vi.mock("next/navigation", () => ({
  useParams: () => nav.params,
  usePathname: () => `/contracts/${nav.params["contract-id"]}`,
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
}));

function detailFixture(overrides: Partial<ContractDetailResponse> = {}): ContractDetailResponse {
  return {
    organization_slug: "krankenhaus",
    contract_id: "11111111-1111-1111-1111-111111111111",
    contract_number: "CN-9876",
    contract_title: "MRT Wartungsvertrag",
    supplier: "Siemens Healthineers",
    status: "active",
    risk_level: "medium",
    identity: {
      contract_number: "CN-9876",
      contract_type: "Wartung",
      department: "Radiologie",
    },
    dates: {
      start_date: "2024-01-01",
      start_date_status: "explicit",
      calculated_end_date: "2027-06-30",
      calculated_end_status: "explicit",
      latest_cancellation_date: "2027-03-01",
      latest_cancellation_status: "computed",
      next_renewal_date: "2027-06-30",
      next_renewal_status: "computed",
      automatic_renewal: true,
      current_status: "active",
      current_status_explanation: "Vertrag ist aktiv.",
      review_required: false,
    },
    costs: {
      annual_recurring: { amount: "42500", currency: "EUR", status: "explicit", explanation: null },
      monthly_recurring: { amount: null, currency: "EUR", status: null, explanation: null },
      total_contract_value_status: null,
      currency_conflict: false,
      tax_basis: null,
    },
    scope: {
      included_services: ["Wartung", "Remote-Support"],
      excluded_services: ["Ersatzteile"],
      maintenance: true,
      inspection: null,
      repair: false,
      calibration: null,
      software_updates: null,
      remote_support: true,
      technical_support: null,
      spare_parts_included: null,
      consumables_included: null,
      emergency_service: null,
    },
    sla: {
      response_time: "4 Stunden",
      resolution_time: null,
      service_hours: null,
      emergency_availability: null,
      availability_24_7: true,
      sla_notes: null,
    },
    equipment: [
      { device_name: "MRT Magnetom", manufacturer: "Siemens", model: "Vida", serial_number: "SN-1", system_name: null, equipment_category: null },
    ],
    review: {
      requires_manual_review: false,
      review_reasons: [],
      data_freshness: "current",
      warning_evaluation_as_of_date: "2026-08-31",
    },
    warnings: [
      {
        warning_type: "cancellation_deadline_approaching",
        severity: "medium",
        title_de: "Kündigungsfrist nähert sich",
        target_kind: "date",
        target_date: "2027-03-01",
        days_remaining: 182,
        requires_action: true,
        requires_review: false,
        action_state: null,
      },
    ],
    documents: [
      {
        document_version_id: "aaaa0000-0000-0000-0000-000000000001",
        role: "main",
        original_filename: "wartung.pdf",
        mime_type: "application/pdf",
        file_size_bytes: 4582,
        viewer_supported: true,
      },
      {
        document_version_id: "aaaa0000-0000-0000-0000-000000000002",
        role: "annex",
        original_filename: "anhang.docx",
        mime_type:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size_bytes: 1200,
        viewer_supported: false,
      },
    ],
    evidence: [
      {
        evidence_id: "e-1",
        field_ref: "dates.start_date",
        document_version_id: "aaaa0000-0000-0000-0000-000000000001",
        original_filename: "wartung.pdf",
        page: 2,
        source_type: "paragraph",
        paragraph_index: 3,
        table_index: null,
        snippet: "Laufzeit beginnt am 01.01.2024.",
        confidence: 0.98,
        requires_review: false,
        bbox: { x0: 40, y0: 200, x1: 200, y1: 260 },
        precision: "coarse",
        geometry_normalized: false,
        bbox_space: "pdf_points",
        supports_exact_navigation: true,
      },
      {
        evidence_id: "e-2",
        field_ref: "costs.annual_cost",
        document_version_id: "aaaa0000-0000-0000-0000-000000000001",
        original_filename: "wartung.pdf",
        page: null,
        source_type: "table",
        paragraph_index: null,
        table_index: 1,
        snippet: "Jährliche Vergütung 42.500 EUR.",
        confidence: 0.9,
        requires_review: true,
        bbox: null,
        precision: "none",
        geometry_normalized: false,
        bbox_space: "pdf_points",
        supports_exact_navigation: false,
      },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGetMock.mockReset();
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    arrayBuffer: async () => new ArrayBuffer(8),
  });
});

async function renderWithData(data: ContractDetailResponse) {
  apiGetMock.mockResolvedValue(data);
  const utils = render(<ContractDetailPage />);
  await waitFor(() => expect(apiGetMock).toHaveBeenCalled());
  return utils;
}

describe("Vertrags-Detail + Quellenanzeige (STEP 14)", () => {
  it("lädt und zeigt Detaildaten aus der akzeptierten Wahrheit", async () => {
    await renderWithData(detailFixture());
    expect(
      screen.getByRole("heading", { name: "MRT Wartungsvertrag" })
    ).toBeInTheDocument();
    expect(screen.getAllByText(/CN-9876/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/Siemens/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("42.500,00 €").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/01\.01\.2024/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Kündigungsfrist nähert sich")).toBeInTheDocument();
    expect(screen.getByText("MRT Magnetom")).toBeInTheDocument();
  });

  it("unterstützt PDF-Quelle und meldet DOCX ehrlich als nicht darstellbar", async () => {
    await renderWithData(detailFixture());
    expect(screen.getByText("wartung.pdf")).toBeInTheDocument();
    expect(screen.getByText("anhang.docx")).toBeInTheDocument();
    expect(
      screen.getByText(/DOCX kann derzeit nicht als PDF-Vorschau/).textContent
    ).toContain("DOCX");
  });

  it("zeigt Quellenangaben mit ehrlicher Navigations-Präzision", async () => {
    await renderWithData(detailFixture());
    const pane = screen.getByRole("region", {
      name: "Quellenangaben",
    });
    expect(within(pane).getByText("Positionsbestimmt")).toBeInTheDocument();
    expect(
      within(pane).getByText("Ohne Positionsangabe")
    ).toBeInTheDocument();
    expect(within(pane).getByText(/Konfidenz 98%/)).toBeInTheDocument();
  });

  it("markiert eine ausgewählte PDF-Quelle und zeigt den Viewer", async () => {
    await renderWithData(detailFixture());
    const sourceBtn = screen.getByRole("button", { name: /wartung\.pdf/ });
    await userEvent.click(sourceBtn);
    expect(sourceBtn).toHaveAttribute("aria-pressed", "true");
    await waitFor(() =>
      expect(
        screen.getByRole("toolbar", { name: "PDF-Ansicht steuern" })
      ).toBeInTheDocument()
    );
    expect(screen.getByText(/Seite 1 \/ 3/)).toBeInTheDocument();
  });

  it("navigiert zu einer exakt lokalisierten Quelle", async () => {
    await renderWithData(detailFixture());
    const exactBtn = screen.getByRole("button", { name: /start date/ });
    await userEvent.click(exactBtn);
    await waitFor(() =>
      expect(screen.getByText(/Seitenbereich\) hervorgehoben/)).toBeInTheDocument()
    );
    expect(screen.getByText(/Seite 2 \/ 3/)).toBeInTheDocument();
  });

  it("hat keine automatisierten WCAG-A11y-Verstöße", async () => {
    const { container } = await renderWithData(detailFixture());
    await waitFor(() =>
      expect(
        screen.getByRole("toolbar", { name: "PDF-Ansicht steuern" })
      ).toBeInTheDocument()
    );
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it("(PR-2) klickbarer Fakt öffnet die Quelle im Original", async () => {
    await renderWithData(detailFixture());
    const beginBtn = screen.getByRole("button", { name: "Beginn — Quelle öffnen" });
    await userEvent.click(beginBtn);
    await waitFor(() =>
      expect(screen.getByText(/Seitenbereich\) hervorgehoben/)).toBeInTheDocument()
    );
    expect(screen.getByText(/Seite 2 \/ 3/)).toBeInTheDocument();
    expect(screen.getAllByText("Seite 2 (Seitenbereich)").length).toBeGreaterThanOrEqual(1);
  });

  it("(PR-2) Fakt mit Quelle ohne Seitenangabe springt den Viewer NICHT (keine erfundene Hervorhebung)", async () => {
    await renderWithData(detailFixture());
    const annualBtn = screen.getByRole("button", {
      name: "Jährlich wiederkehrend — Quelle öffnen",
    });
    await userEvent.click(annualBtn);
    expect(screen.getByText(/Seite 1 \/ 3/)).toBeInTheDocument();
    expect(screen.queryByText(/hervorgehoben/)).not.toBeInTheDocument();
    const pane = screen.getByRole("region", { name: "Quellenangaben" });
    expect(
      within(pane).getByText(/Ohne Positionsangabe/)
    ).toBeInTheDocument();
  });

  it("(PR-2) Faktklick behält den Werkstatt-Kontext (Rückkehr ohne Kontextverlust)", async () => {
    await renderWithData(detailFixture());
    const endurance = screen.getByRole("button", {
      name: "Beginn — Quelle öffnen",
    });
    await userEvent.click(endurance);
    await waitFor(() => expect(screen.getByText(/Seite 2 \/ 3/)).toBeInTheDocument());
    const endBtn = screen.getByRole("button", {
      name: "Berechnetes Ende — Quelle öffnen",
    });
    expect(endBtn).toBeInTheDocument();
    await userEvent.click(endBtn);
    expect(
      screen.getByRole("heading", { name: "MRT Wartungsvertrag" })
    ).toBeInTheDocument();
    expect(screen.getByText("Kündigungsfrist nähert sich")).toBeInTheDocument();
  });
});
