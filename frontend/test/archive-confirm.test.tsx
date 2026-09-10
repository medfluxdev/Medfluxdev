import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDetail from "@/components/contracts/detail/ContractDetail";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

const apiPostMock = vi.fn();
vi.mock("@/lib/api", () => ({
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
      warning_evaluation_as_of_date: "2026-08-31",
    },
    warnings: [],
    documents: [],
    evidence: [],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiPostMock.mockReset();
  pushMock.mockReset();
});

function renderDetail() {
  return render(<ContractDetail data={detailFixture()} orgSlug="krankenhaus" />);
}

describe("Contract 360 – Archivieren (UAT Defect)", () => {
  it("verlangt eine Bestätigung, zeigt die Aktion/Erklärung und archiviert erst nach Abschluss mit Navigation", async () => {
    // 1. Klick → Dialog öffnet sich, Backend wird NOCH NICHT aufgerufen.
    let resolvePost!: (value: { archived: boolean }) => void;
    apiPostMock.mockReturnValue(
      new Promise((resolve) => {
        resolvePost = resolve;
      })
    );
    const user = userEvent.setup();
    renderDetail();

    await user.click(screen.getByRole("button", { name: "Archivieren" }));

    const dialog = await screen.findByRole("dialog", {
      name: "Vertrag archivieren?",
    });
    expect(dialog).toHaveTextContent("Nr. CN-9876");
    expect(dialog).toHaveTextContent("MRT Wartungsvertrag");
    // Nicht-destruktive Erklärung: nichts wird gelöscht, Historie bleibt.
    expect(dialog).toHaveTextContent(/löscht/);
    expect(dialog).toHaveTextContent(/Belege/);
    expect(dialog).toHaveTextContent(/Review-Geschichte/);
    expect(dialog).toHaveTextContent(/Audit-Historie/);
    expect(apiPostMock).not.toHaveBeenCalled();

    // 2. Abbrechen schließt den Dialog ohne Zustandsänderung.
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(apiPostMock).not.toHaveBeenCalled();

    // 3. Erneut öffnen und bestätigen → echter API-Aufruf mit korrekter URL.
    await user.click(screen.getByRole("button", { name: "Archivieren" }));
    await screen.findByRole("dialog", { name: "Vertrag archivieren?" });
    const confirm = screen.getByRole("button", { name: "Vertrag archivieren" });
    await user.click(confirm);

    // 4. Während der Request läuft: honoriger Busy-State, kein Doppel-Submit.
    expect(screen.getByRole("button", { name: "Wird verarbeitet…" })).toBeDisabled();
    expect(apiPostMock).toHaveBeenCalledTimes(1);
    expect(apiPostMock).toHaveBeenCalledWith(
      `/api/contracts/${CONTRACT_ID}/archive?organization_slug=krankenhaus`,
      {}
    );

    // 5. Erfolg → Erfolgsfeedback + Navigation zum Archiv.
    resolvePost({ archived: true });
    await waitFor(() =>
      expect(
        screen.getByText("Vertrag archiviert – wird ins Archiv verschoben…")
      ).toBeInTheDocument()
    );
    await waitFor(
      () => expect(pushMock).toHaveBeenCalledWith("/archiv"),
      { timeout: 2500 }
    );
    expect(pushMock).toHaveBeenCalledTimes(1);
  });

  it("zeigt bei Fehler den Vertrag unverändert an und erlaubt einen Retry", async () => {
    const user = userEvent.setup();
    renderDetail();

    // Fehlerfall
    apiPostMock.mockRejectedValueOnce(new Error("backend down"));
    await user.click(screen.getByRole("button", { name: "Archivieren" }));
    await screen.findByRole("dialog", { name: "Vertrag archivieren?" });
    await user.click(screen.getByRole("button", { name: "Vertrag archivieren" }));

    await waitFor(() =>
      expect(
        screen.getByText(
          "Archivieren fehlgeschlagen – der Vertrag bleibt im aktiven Portfolio."
        )
      ).toBeInTheDocument()
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    // Vertrag selbst ist unverändert: weiterhin "Archivieren"-Button sichtbar,
    // kein Erfolgsfeedback, keine Navigation.
    expect(screen.getByRole("button", { name: "Archivieren" })).toBeInTheDocument();
    expect(
      screen.queryByText("Vertrag archiviert – wird ins Archiv verschoben…")
    ).not.toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();

    // Retry über "Erneut versuchen" → Dialog → Erfolg → Navigation.
    apiPostMock.mockResolvedValueOnce({ archived: true });
    await user.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    await screen.findByRole("dialog", { name: "Vertrag archivieren?" });
    await user.click(screen.getByRole("button", { name: "Vertrag archivieren" }));

    await waitFor(
      () => expect(pushMock).toHaveBeenCalledWith("/archiv"),
      { timeout: 2500 }
    );
    expect(apiPostMock).toHaveBeenCalledTimes(2);
  });
});