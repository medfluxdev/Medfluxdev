import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDetail from "@/components/contracts/detail/ContractDetail";
import type { ContractDetailResponse, EvidenceRef } from "@/lib/contract-detail-types";

const apiGetMock = vi.fn();
const apiPostMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  apiPost: (...args: unknown[]) => apiPostMock(...args),
  contentUrl: () => "http://test.local/content/x",
}));

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}));

function evidenceFixture(): EvidenceRef[] {
  return [
    {
      evidence_id: "ev-dates",
      field_ref: "dates.start_date",
      document_version_id: "doc-1",
      source_type: "pdf",
      page: 1,
      snippet: "Laufzeit: 01.01.2026 bis 31.12.2029",
      confidence: 0.93,
      requires_review: false,
    },
    {
      evidence_id: "ev-costs",
      field_ref: "costs.annual_recurring",
      document_version_id: "doc-1",
      source_type: "pdf",
      page: 2,
      snippet: "Jährliche Wartung: 12.000 EUR netto.",
      confidence: 0.87,
      requires_review: true,
    },
    {
      evidence_id: "ev-termination",
      field_ref: "termination.notice_period",
      document_version_id: "doc-1",
      source_type: "pdf",
      page: 3,
      snippet: "Kündigungsfrist: 6 Monate zum Vertragsende.",
      confidence: 0.81,
      requires_review: false,
    },
  ];
}

function detailFixture(): ContractDetailResponse {
  return {
    organization_slug: "krankenhaus",
    contract_id: "11111111-1111-1111-1111-111111111111",
    contract_number: "MED-9001",
    contract_title: "MEDTRON Guard Servicevereinbarung",
    supplier: "Medtron GmbH",
    status: "active",
    risk_level: null,
    identity: {
      contract_number: "MED-9001",
      contract_type: "Wartung",
      department: "Kardiologie",
    },
    dates: {
      start_date: "2026-01-01",
      start_date_status: "explicit",
      calculated_end_date: "2029-12-31",
      calculated_end_status: "explicit",
      latest_cancellation_date: "2029-10-01",
      latest_cancellation_status: "computed",
      next_renewal_date: "2029-12-31",
      next_renewal_status: "computed",
      automatic_renewal: true,
      current_status: "active",
      current_status_explanation: "Vertrag ist aktiv.",
      review_required: false,
    },
    costs: {
      annual_recurring: { amount: "12000", currency: "EUR", status: "explicit", explanation: null },
      monthly_recurring: { amount: null, currency: "EUR", status: null, explanation: null },
      total_contract_value_status: null,
      currency_conflict: false,
      tax_basis: null,
    },
    scope: {
      included_services: ["Wartung"],
      excluded_services: [],
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
    equipment: [],
    review: {
      requires_manual_review: false,
      review_reasons: [],
      data_freshness: "current",
      warning_evaluation_as_of_date: "2026-09-06",
    },
    warnings: [],
    documents: [],
    evidence: evidenceFixture(),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGetMock.mockReset();
  apiGetMock.mockRejectedValue(new Error("development mode"));
});

describe("Contract 360 – unabhängige Scroll-Bereiche für Evidence und Quelle (PR-5)", () => {
  it("rendert getrennte Scroll-Bereiche: Faktenspalte, Evidence-Liste und PDF-Viewer", () => {
    const { container } = render(
      <ContractDetail data={detailFixture()} orgSlug="krankenhaus" onReload={() => {}} />
    );

    // Drei voneinander getrennte Regionen existieren nebeneinander in der
    // Workbench: Detail-/Evidence-Inhalt (links), Quellenangaben (rechts),
    // Quelle anzeigen (eigener Bereich).
    const columns = container.querySelector(".detail-columns");
    const main = container.querySelector(".detail-main");
    const aside = container.querySelector(".detail-aside");
    const viewer = container.querySelector(".detail-viewer");
    expect(columns).not.toBeNull();
    expect(main).not.toBeNull();
    expect(aside).not.toBeNull();
    expect(viewer).not.toBeNull();

    // Die Evidence-Liste gehört in die Seitenleiste (nicht in den Viewer).
    expect(aside!.querySelector(".evidence-list")).not.toBeNull();
    expect(viewer!.querySelector(".evidence-list")).toBeNull();

    // Der Viewer ist ein eigenständiger Geschwister-Bereich NACH den Spalten
    // (unabhängiger Scrollbreich, nicht in die Faktenspalte eingebettet).
    expect(viewer!.previousElementSibling).toBe(columns);

    // Definition der Bereiche über sichtbare Abschnittstitel.
    expect(
      screen.getByRole("heading", { name: "Quelldokumente" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Quellenangaben" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Quelle anzeigen" })
    ).toBeInTheDocument();
  });

  it("rendert alle Evidence-Nachweise als bedienbare Listeneinträge in der Seitenleiste", () => {
    const { container } = render(
      <ContractDetail data={detailFixture()} orgSlug="krankenhaus" onReload={() => {}} />
    );

    const aside = container.querySelector(".detail-aside")!;
    const list = aside.querySelector(".evidence-list")!;
    expect(list.querySelectorAll("button").length).toBe(3);
    expect(screen.getAllByText(/Seite \d+/).length).toBeGreaterThanOrEqual(3);
  });

  it("zeigt den Quelle-Bereich auch ohne geladenes Dokument ehrlich als Platzhalter", () => {
    render(
      <ContractDetail data={detailFixture()} orgSlug="krankenhaus" onReload={() => {}} />
    );

    const viewer = screen.getByRole("heading", { name: "Quelle anzeigen" }).closest(".detail-viewer");
    expect(viewer).not.toBeNull();
    expect(viewer!.querySelector(".pdf-viewer")).not.toBeNull();
    expect(
      screen.getByText("Wählen Sie oben ein Quelldokument aus, um die Quelle zu öffnen.")
    ).toBeInTheDocument();
  });
});