import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDetailPage from "@/app/contracts/[contract-id]/page";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

const apiGetMock = vi.fn();
const apiPostMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  apiPost: (...args: unknown[]) => apiPostMock(...args),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ "contract-id": "11111111-1111-1111-1111-111111111111" }),
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

function factState(state: "unreviewed" | "confirmed") {
  return {
    fact_key: "annual_costs",
    label_de: "Jährliche Kosten",
    present: true,
    state,
    state_label_de: state === "confirmed" ? "Bestätigt" : "Nicht geprüft",
    original_value: "12.000 €",
    effective_value: "12.000 €",
    reviewer_display_name: null,
    reviewer_identity_type: "manual_unverified",
    reviewed_at: null,
    evidence_ref: null,
    has_history: state === "confirmed",
    evidence_count: 0,
    linked_evidence: [],
    linked_evidence_refs: [],
    needs_evidence: false,
    is_critical: false,
  };
}

function fixture(statusLabel: string, state: "unreviewed" | "confirmed"): ContractDetailResponse {
  return {
    organization_slug: "krankenhaus",
    contract_id: "11111111-1111-1111-1111-111111111111",
    is_archived: false,
    archived_at: null,
    contract_number: "MED-9001",
    contract_title: "MEDTRON Guard Servicevereinbarung Accutron MR",
    supplier: "Medtron GmbH",
    status: "active",
    risk_level: "high",
    identity: {},
    dates: {
      start_date: null,
      start_date_status: null,
      calculated_end_date: null,
      calculated_end_status: null,
      latest_cancellation_date: null,
      latest_cancellation_status: null,
      next_renewal_date: null,
      next_renewal_status: null,
      automatic_renewal: false,
      current_status: "active",
      current_status_explanation: "",
      review_required: true,
    },
    costs: {
      annual_recurring: { amount: null, currency: "EUR", status: null, explanation: null },
      monthly_recurring: { amount: null, currency: "EUR", status: null, explanation: null },
      total_contract_value_status: null,
      currency_conflict: false,
      tax_basis: null,
    },
    scope: {
      included_services: [],
      excluded_services: [],
      maintenance: null,
      inspection: null,
      repair: null,
      calibration: null,
      software_updates: null,
      remote_support: null,
      technical_support: null,
      spare_parts_included: null,
      consumables_included: null,
      emergency_service: null,
    },
    sla: {
      response_time: null,
      resolution_time: null,
      service_hours: null,
      emergency_availability: null,
      availability_24_7: null,
      sla_notes: null,
    },
    equipment: [],
    review: {
      requires_manual_review: true,
      review_reasons: [],
      data_freshness: "current",
      warning_evaluation_as_of_date: "2026-09-06",
    },
    warnings: [],
    work_items: [],
    documents: [],
    evidence: [],
    overrides: [],
    audit_log: [],
    import_state: {
      import_state: "analysis_ok",
      state_label_de: "Analyse abgeschlossen",
      document_version_id: "dv-1",
      can_retry: false,
      message: null,
      analysis_status: "ok",
      requires_review: false,
    },
    fact_review_states: [factState(state)],
    fact_reviews: [],
    contract_review: {
      status: state,
      status_label_de: statusLabel,
      reviewer_display_name: null,
      reviewer_identity_type: "manual_unverified",
      authenticated_actor_id: null,
      reviewed_at: null,
      changed_noted_at: null,
      completion_note: null,
      relevant_count: 1,
      reviewed_count: state === "confirmed" ? 1 : 0,
      unresolved_count: state === "confirmed" ? 0 : 1,
      critical_count: 0,
      critical_reviewed_count: 0,
      critical_unreviewed_count: 0,
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Vertrags-Detail: Scroll-Erhalt beim Fakt-Prüfen (UAT Defect C)", () => {
  it("bleibt bei einem Reload gemountet – keine Voll-Ladeanzeige, Panel-Node stabil", async () => {
    const user = userEvent.setup();
    // Erster Aufruf: ungeprüft; erneuter Aufruf (via onReload): Nach-Reload-Stand.
    const detailResponses = [
      fixture("Nicht geprüft", "unreviewed"),
      fixture("Geprüft (Aktualisiert)", "confirmed"),
    ];
    apiGetMock.mockImplementation((path: string) => {
      if (path === "/api/auth/me") {
        return Promise.reject(new Error("development mode"));
      }
      return Promise.resolve(detailResponses.shift());
    });
    apiPostMock.mockResolvedValue({});

    const { container } = render(<ContractDetailPage />);

    // Erstes Laden abwarten: Fakt-Prüf-Panel ist gerendert (onReload aktiv).
    await screen.findByText(/Faktprüfung/);
    const panel = container.querySelector("#fact-review-panel") as HTMLElement;
    expect(panel).not.toBeNull();

    await user.type(screen.getByLabelText("Name der prüfenden Person"), "Klinik-Werksteam");
    const confirmButtons = within(panel).getAllByRole("button", { name: "Bestätigen" });
    await user.click(confirmButtons[0]);

    await waitFor(() =>
      expect(screen.queryByText("Vertrag wird geladen…")).not.toBeInTheDocument()
    );

    // Reload hat frische Daten geliefert …
    expect(
      await screen.findByText("Geprüft (Aktualisiert)")
    ).toBeInTheDocument();

    // … ohne die Seite zu entladen: dasselbe Panel-DOM bleibt stehen,
    // womit die Bildlaufposition beim Fakt-Prüfen erhalten bleibt.
    expect(container.querySelector("#fact-review-panel")).toBe(panel);
    const detailCalls = apiGetMock.mock.calls.filter(
      ([path]) => typeof path === "string" && path.startsWith("/api/contracts/")
    );
    expect(detailCalls).toHaveLength(2);
  });
});