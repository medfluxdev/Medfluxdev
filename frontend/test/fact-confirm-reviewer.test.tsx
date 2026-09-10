import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FactReviewPanel from "@/components/contracts/detail/FactReviewPanel";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

const apiPostMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiPost: (...args: unknown[]) => apiPostMock(...args),
}));

const CONTRACT_ID = "01a07ed3-d22c-7527-831d-3a0fd0fc75e2";
const ORG = "krankenhaus";

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
      status: "unreviewed",
      status_label_de: "Nicht geprüft",
      reviewer_display_name: null,
      reviewer_identity_type: "manual_unverified",
      authenticated_actor_id: null,
      reviewed_at: null,
      changed_noted_at: null,
      completion_note: null,
      relevant_count: 5,
      reviewed_count: 0,
      unresolved_count: 5,
      critical_count: 0,
      critical_reviewed_count: 0,
      critical_unreviewed_count: 0,
    },
    fact_review_states: [
      {
        fact_key: "equipment.serial",
        label_de: "Serien- / Inventarnummer",
        present: true,
        state: "unreviewed",
        state_label_de: "Ungeprüft",
        original_value: "88024307",
        effective_value: "88024307",
        reviewer_display_name: null,
        reviewer_identity_type: null,
        reviewed_at: null,
        evidence_ref: null,
        has_history: false,
        evidence_count: 0,
        linked_evidence: [],
        linked_evidence_refs: [],
        needs_evidence: false,
        is_critical: false,
      },
    ],
    fact_reviews: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiPostMock.mockReset();
});

describe("Faktprüfung – Bestätigen (UAT Defect, MEDTRON)", () => {
  it("reproduziert den Fehler: ohne Prüfer*in wird NICHT ans Backend gesendet, ehrliche Meldung erscheint", async () => {
    const user = userEvent.setup();
    render(
      <FactReviewPanel data={fixture()} orgSlug={ORG} onReload={() => {}} />
    );

    const fact = screen.getByText("Serien- / Inventarnummer").closest("li");
    expect(fact).not.toBeNull();
    const confirm = within(fact as HTMLElement).getByRole("button", {
      name: "Bestätigen",
    });
    await user.click(confirm);

    // Kein Request, keine erfundene Identität, kein stilles Versagen.
    expect(apiPostMock).not.toHaveBeenCalled();
    expect(
      await screen.findByText(
        /Bitte zuerst Prüfer\*in angeben \(Feld oben, z\. B\. „Klinik-Werksteam“\). Ohne Prüfer-Name wird die Prüf-Aktion nicht gespeichert\./
      )
    ).toBeInTheDocument();
  });

  it("Bestätigen mit Prüfer*in speichert die Aktion OHNE Wertänderung und aktualisiert das Review", async () => {
    apiPostMock.mockResolvedValue({});
    const reload = vi.fn();
    const user = userEvent.setup();
    render(
      <FactReviewPanel data={fixture()} orgSlug={ORG} onReload={reload} />
    );

    await user.type(
      screen.getByLabelText("Name der prüfenden Person"),
      "Klinik-Werksteam"
    );
    const fact = screen.getByText("Serien- / Inventarnummer").closest("li");
    const confirm = within(fact as HTMLElement).getByRole("button", {
      name: "Bestätigen",
    });
    await user.click(confirm);

    // Genau ein confirmed-Request für DIESEN Fakt, korrekte org-gebundene URL.
    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock).toHaveBeenCalledWith(
      `/api/contracts/${CONTRACT_ID}/fact-reviews?organization_slug=${ORG}`,
      {
        fact_key: "equipment.serial",
        action: "confirmed",
        reviewer_display_name: "Klinik-Werksteam",
        note: null,
      }
    );
    // confirmed ändert den Wert NIE: kein corrected_value im Payload,
    // Original-/effektiver Wert bleibt im Zustand "88024307".
    const body = apiPostMock.mock.calls[0][1];
    expect(body).not.toHaveProperty("corrected_value");
    expect(
      within(fact as HTMLElement).getByText("88024307")
    ).toBeInTheDocument();

    // Erfolg sichtbar + Review-State wird refresht (persistierter Zustand).
    expect(
      await screen.findByText("Prüf-Aktion gespeichert.")
    ).toBeInTheDocument();
    expect(reload).toHaveBeenCalledTimes(1);
  });
});