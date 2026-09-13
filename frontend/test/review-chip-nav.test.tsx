import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDetail from "@/components/contracts/detail/ContractDetail";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

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

const CONTRACT_ID = "11111111-1111-1111-1111-111111111111";

function detailFixture(): ContractDetailResponse {
  return {
    organization_slug: "krankenhaus",
    contract_id: CONTRACT_ID,
    contract_number: "MED-9001",
    contract_title: "MEDTRON Guard Servicevereinbarung Accutron MR",
    supplier: "Medtron GmbH",
    status: "active",
    risk_level: "high",
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
      requires_manual_review: true,
      review_reasons: ["Messwerte unplausibel"],
      data_freshness: "current",
      warning_evaluation_as_of_date: "2026-09-06",
    },
    warnings: [],
    documents: [],
    evidence: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiGetMock.mockReset();
  apiGetMock.mockRejectedValue(new Error("development mode"));
});

describe("Contract 360 – 'Manuelle Prüfung'-Chip (UAT Defect)", () => {
  it("ist ein echter, per Tastatur fokussierbarer Button", async () => {
    const user = userEvent.setup();
    render(
      <ContractDetail data={detailFixture()} orgSlug="krankenhaus" onReload={() => {}} />
    );

    const chip = screen.getByRole("button", { name: "Manuelle Prüfung" });
    // Tastatur-Fokus per Tab erreichbar.
    chip.focus();
    expect(chip).toHaveFocus();
    expect(chip.tagName).toBe("BUTTON");
  });

  it("öffnet die vertragsbezogene Fakt-Prüfung (Scroll-Ziel + Keyboard-Fokus auf dem Panel)", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <ContractDetail data={detailFixture()} orgSlug="krankenhaus" onReload={() => {}} />
    );

    const panel = container.querySelector("#fact-review-panel");
    expect(panel).not.toBeNull();
    const panelEl = panel as HTMLElement;
    // Panel ist via Keyboard ansteuerbar.
    panelEl.focus();
    expect(panelEl).toHaveFocus();

    await user.click(screen.getByRole("button", { name: "Manuelle Prüfung" }));
    // Klick verschiebt den Fokus in die Fakt-Prüfung dieses Vertrags.
    expect(panelEl).toHaveFocus();
    // Kein Fehler, kein stilles Scheitern.
    expect(screen.queryByText(/konnte nicht geöffnet werden/)).not.toBeInTheDocument();
  });

  it("scheitert nie still: ehrliche Meldung, wenn der Prüfbereich nicht verfügbar ist", async () => {
    const user = userEvent.setup();
    // Ohne onReload wird das FactReviewPanel nicht gerendert -> keinen Bereich finden.
    render(<ContractDetail data={detailFixture()} orgSlug="krankenhaus" />);

    await user.click(screen.getByRole("button", { name: "Manuelle Prüfung" }));
    expect(
      await screen.findByText(/Prüfbereich konnte nicht geöffnet werden/)
    ).toBeInTheDocument();
    // Retry-Aktion ist vorhanden und nicht still.
    expect(
      screen.getByRole("button", { name: "Erneut versuchen" })
    ).toBeInTheDocument();
  });
});