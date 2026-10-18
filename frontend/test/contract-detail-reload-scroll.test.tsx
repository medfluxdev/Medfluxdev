import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDetailPage from "@/app/contracts/[contract-id]/page";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";
import { candidate, evidence, field, review } from "./fixtures/field-review";

const apiGetMock = vi.fn();
const apiPostMock = vi.fn();
vi.mock("@/lib/api", () => ({
  scopedApiUrl: (path: string) => `http://test.local${path}`,
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  apiPost: (...args: unknown[]) => apiPostMock(...args),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ "contract-id": "11111111-1111-1111-1111-111111111111" }),
  usePathname: () => "/contracts/11111111-1111-1111-1111-111111111111",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
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
    dates: { start_date: null, start_date_status: null, calculated_end_date: null, calculated_end_status: null, latest_cancellation_date: null, latest_cancellation_status: null, next_renewal_date: null, next_renewal_status: null, automatic_renewal: false, current_status: "active", current_status_explanation: "", review_required: true },
    costs: { annual_recurring: { amount: null, currency: "EUR", status: null, explanation: null }, monthly_recurring: { amount: null, currency: "EUR", status: null, explanation: null }, total_contract_value_status: null, currency_conflict: false, tax_basis: null },
    scope: { included_services: [], excluded_services: [], maintenance: null, inspection: null, repair: null, calibration: null, software_updates: null, remote_support: null, technical_support: null, spare_parts_included: null, consumables_included: null, emergency_service: null },
    sla: { response_time: null, resolution_time: null, service_hours: null, emergency_availability: null, availability_24_7: null, sla_notes: null },
    equipment: [],
    review: { requires_manual_review: true, review_reasons: [], data_freshness: "current", warning_evaluation_as_of_date: "2026-09-06" },
    warnings: [], work_items: [], documents: [], evidence: [], overrides: [], audit_log: [],
    import_state: { import_state: "analysis_ok", state_label_de: "Analyse abgeschlossen", document_version_id: "dv-1", can_retry: false, message: null, analysis_status: "ok", requires_review: false },
    fact_review_states: [factState(state)], fact_reviews: [],
    field_review: review([state === "confirmed"
      ? field({ fact_key: "annual_costs", label: "Jährliche Kosten", status: "decided", status_label: "Entschieden", decision_needed: false, fact_state: "confirmed", current: "12.000 €", candidates: [candidate({ key: "12000", display: "12.000 €", value: "12.000 €", evidence_ids: [] })], evidence: [], source_state: null })
      : field({ fact_key: "annual_costs", label: "Jährliche Kosten", current: "12.000 €", candidates: [candidate({ key: "12000", display: "12.000 €", value: "12.000 €", evidence_ids: ["e1"] })], evidence: [evidence()] })]),
    contract_review: { status: state, status_label_de: statusLabel, reviewer_display_name: null, reviewer_identity_type: "manual_unverified", authenticated_actor_id: null, reviewed_at: null, changed_noted_at: null, completion_note: null, relevant_count: 1, reviewed_count: state === "confirmed" ? 1 : 0, unresolved_count: state === "confirmed" ? 0 : 1, critical_count: 0, critical_reviewed_count: 0, critical_unreviewed_count: 0 },
  };
}

const contractDetailPath = "/api/contracts/11111111-1111-1111-1111-111111111111?organization_slug=test-klinik";

beforeEach(() => {
  vi.clearAllMocks();
  apiGetMock.mockReset();
  apiPostMock.mockReset();
});

describe("Vertrags-Detail: Scroll-Erhalt beim Fakt-Prüfen (UAT Defect C)", () => {
  it("bleibt bei einem Reload im Prüf-Workspace gemountet – keine Voll-Ladeanzeige, Panel-Node stabil", async () => {
    const user = userEvent.setup();
    let contractLoads = 0;
    apiGetMock.mockImplementation((path: unknown) => {
      if (path === contractDetailPath) {
        contractLoads += 1;
        return Promise.resolve(contractLoads === 1 ? fixture("Nicht geprüft", "unreviewed") : fixture("Geprüft (Aktualisiert)", "confirmed"));
      }
      if (typeof path === "string" && path.startsWith("/api/organization-structure")) return Promise.resolve({ hospitals: [], departments: [] });
      if (typeof path === "string" && path.startsWith("/api/cost-centers")) return Promise.resolve({ items: [] });
      if (typeof path === "string" && path.startsWith("/api/ownership/assignees")) return Promise.resolve({ items: [] });
      if (typeof path === "string" && path.startsWith("/api/ownership/contracts/")) return Promise.resolve({ hospital_id: null, department_ids: [], cost_center_id: null, responsible_account_id: null });
      return Promise.resolve({});
    });
    apiPostMock.mockResolvedValue({});

    const { container } = render(<ContractDetailPage />);
    await screen.findByRole("heading", { name: "MEDTRON Guard Servicevereinbarung Accutron MR" });

    await user.click(screen.getByRole("tab", { name: "Dokumente" }));
    await user.click(screen.getByRole("button", { name: "Prüfung" }));

    const panel = container.querySelector("#field-review-panel") as HTMLElement;
    expect(panel).not.toBeNull();
    expect(await screen.findByRole("region", { name: "Prüfung" })).toBe(panel);

    // Karte (Schublade) und geführte Prüfung nutzen dieselbe Entscheidung: hier „Bestätigen“ in der Schublade.
    await user.click(within(panel).getByRole("button", { name: /Jährliche Kosten/, expanded: false }));
    apiPostMock.mockResolvedValue(fixture("Geprüft (Aktualisiert)", "confirmed"));
    await user.click(within(panel).getByRole("button", { name: "Bestätigen", exact: true }));

    await waitFor(() => expect(contractLoads).toBe(2));
    expect(screen.queryByText("Vertrag wird geladen…")).not.toBeInTheDocument();
    expect(await within(panel).findByText(/Wesentliche Prüfung abgeschlossen/)).toBeInTheDocument();
    expect(container.querySelector("#field-review-panel")).toBe(panel);
  });
});