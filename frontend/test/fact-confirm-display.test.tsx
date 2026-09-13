import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FactReviewPanel from "@/components/contracts/detail/FactReviewPanel";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

const apiPostMock = vi.fn();
const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  apiPost: (...args: unknown[]) => apiPostMock(...args),
}));

const CONTRACT_ID = "01a07ed3-d22c-7527-831d-3a0fd0fc75e2";
const ORG = "krankenhaus";
const REVIEWED_AT = "2026-09-08T04:50:35.703516+02:00";

function fact(name: string, key: string, state: string, value: string) {
  return {
    fact_key: key,
    label_de: name,
    present: true,
    state,
    state_label_de: "Manuell korrigiert",
    original_value: value,
    effective_value: value,
    reviewer_display_name: "JAMAL",
    reviewer_identity_type: "manual_unverified",
    reviewed_at: REVIEWED_AT,
    evidence_ref: null,
    has_history: true,
    evidence_count: 0,
    linked_evidence: [],
    linked_evidence_refs: [],
    needs_evidence: false,
    is_critical: false,
  };
}

function fixture(): ContractDetailResponse {
  return {
    organization_slug: ORG,
    contract_id: CONTRACT_ID,
    contract_number: "",
    contract_title: "MEDTRON Guard Servicevereinbarung Accutron MR",
    supplier: "MEDTRON AG",
    status: "active",
    risk_level: "high",
    identity: { contract_number: "", contract_type: "Wartung", department: "Kardiologie" },
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
    documents: [],
    evidence: [],
    contract_review: {
      status: "in_review",
      status_label_de: "In manueller Prüfung",
      reviewer_display_name: "JAMAL",
      reviewer_identity_type: "manual_unverified",
      authenticated_actor_id: null,
      reviewed_at: REVIEWED_AT,
      changed_noted_at: null,
      completion_note: null,
      relevant_count: 2,
      reviewed_count: 2,
      unresolved_count: 0,
      critical_count: 0,
      critical_reviewed_count: 0,
      critical_unreviewed_count: 0,
    },
    fact_review_states: [
      fact("Serien- / Inventarnummer", "equipment.serial", "confirmed", "88024307"),
      fact("Vertragspartner / Lieferant", "identity.supplier", "corrected", "MEDTRON AG"),
    ],
    fact_reviews: [
      {
        id: "r-confirmed",
        fact_key: "equipment.serial",
        fact_label_de: "Serien- / Inventarnummer",
        is_critical: false,
        action: "confirmed",
        action_label_de: "Manuell korrigiert",
        original_value: "88024307",
        previous_effective_value: "88024307",
        new_effective_value: "88024307",
        reviewer_display_name: "JAMAL",
        reviewer_identity_type: "manual_unverified",
        authenticated_actor_id: null,
        note: null,
        evidence_ref: null,
        created_at: REVIEWED_AT,
      },
      {
        id: "r-corrected",
        fact_key: "identity.supplier",
        fact_label_de: "Vertragspartner / Lieferant",
        is_critical: false,
        action: "corrected",
        action_label_de: "Manuell korrigiert",
        original_value: "MEDTRON AG",
        previous_effective_value: "MEDTRON AG",
        new_effective_value: "MEDTRON AG",
        reviewer_display_name: "JAMAL",
        reviewer_identity_type: "manual_unverified",
        authenticated_actor_id: null,
        note: null,
        evidence_ref: null,
        created_at: REVIEWED_AT,
      },
    ],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiPostMock.mockReset();
  apiGetMock.mockReset();
  apiGetMock.mockRejectedValue(new Error("development mode"));
});

function liFor(text: string): HTMLElement {
  const el = screen.getByText(text).closest("li");
  if (!el) throw new Error(`fact-state li not found for "${text}"`);
  return el as HTMLElement;
}

const RESULT_LINE = /\d{2}\.\d{2}\.(\d{2}|\d{4}), \d{2}:\d{2}/;

describe("Faktprüfung – Anzeige Bestätigt vs Korrigiert (UAT Defect)", () => {
  it("zeigt confirmed als 'Bestätigt' und corrected als 'Korrigiert' – getrennt, mit Prüfer und Zeit", () => {
    render(<FactReviewPanel data={fixture()} orgSlug={ORG} onReload={() => {}} />);

    const confirmed = within(liFor("Serien- / Inventarnummer"));
    // Bestätigt wirkt nie wie eine Korrektur (auch nicht über das
    // ausführliche Backend-Label "Manuell korrigiert").
    expect(confirmed.queryAllByText("Korrigiert")).toHaveLength(0);
    expect(confirmed.getAllByText("Bestätigt").length).toBeGreaterThan(0);
    // Wer + wann sind sichtbar und enthalten das Datum der Prüfung.
    expect(confirmed.getAllByText(/Prüfer: JAMAL/).length).toBeGreaterThan(0);
    expect(confirmed.getAllByText(RESULT_LINE).length).toBeGreaterThan(0);
    expect(confirmed.getByText("88024307")).toBeInTheDocument();

    const corrected = within(liFor("Vertragspartner / Lieferant"));
    expect(corrected.queryAllByText("Bestätigt")).toHaveLength(0);
    expect(corrected.getAllByText("Korrigiert").length).toBeGreaterThan(0);
    expect(corrected.getAllByText(/Prüfer: JAMAL/).length).toBeGreaterThan(0);
    expect(corrected.getAllByText(RESULT_LINE).length).toBeGreaterThan(0);

    // Beide Prüf-Ergebnisse sichtbar: was geschah (Badge), wer, wann.
    expect(screen.getAllByText(/Prüfer: JAMAL/)).toHaveLength(2);
  });

  it("Historie: 'Bestätigt' zeigt Wertübernahme, 'Korrigiert' zeigt Änderung – nie verwechselt", async () => {
    const user = userEvent.setup();
    render(<FactReviewPanel data={fixture()} orgSlug={ORG} onReload={() => {}} />);

    const confirmedLi = liFor("Serien- / Inventarnummer");
    await user.click(within(confirmedLi).getByRole("button", { name: "Historie" }));
    const confirmedHist = within(confirmedLi);
    // Nur die Bestätigung erhält "Wert übernommen (kein Override)".
    expect(confirmedHist.getAllByText("Wert übernommen (kein Override)").length).toBeGreaterThan(
      0
    );
    expect(confirmedHist.queryByText("→")).not.toBeInTheDocument();

    const correctedLi = liFor("Vertragspartner / Lieferant");
    await user.click(within(correctedLi).getByRole("button", { name: "Historie" }));
    const correctedHist = within(correctedLi);
    expect(correctedHist.queryByText("Wert übernommen (kein Override)")).not.toBeInTheDocument();
  });
});